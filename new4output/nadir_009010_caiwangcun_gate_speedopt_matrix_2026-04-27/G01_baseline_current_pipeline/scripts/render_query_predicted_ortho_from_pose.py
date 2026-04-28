#!/usr/bin/env python3
"""Render predicted UAV orthophotos from formal best-pose estimates.

Purpose:
- orthorectify each query image onto the corresponding truth-tile grid using
  the best pose solved by the formal Pose v1 pipeline;
- keep predicted orthophotos strictly on the truth tile CRS / transform /
  resolution / extent so later comparisons are grid-aligned;
- emit explicit per-query status rows instead of silently falling back to
  planar approximations when pose or DSM support is missing.

Main inputs:
- `summary/per_query_best_pose.csv`;
- `manifest/pose_manifest.json`;
- `input/formal_dsm_manifest.csv`;
- `<output_root>/query_ortho_truth_manifest.csv`;
- `<output_root>/truth_tiles/*.tif`;
- original query images referenced by the formal manifest.

Main outputs:
- `<output_root>/pred_tiles/<query_id>_pred_ortho.tif`;
- `<output_root>/pred_tiles/pred_tile_manifest.csv`;
- `<output_root>/pred_tiles/_summary.json`.

Applicable task constraints:
- render only the per-query best pose, not all retrieval candidates;
- use the candidate-linked DSM raster only; do not fall back to a flat ground
  model when DSM sampling fails;
- output grids must match the truth crop grids exactly.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np

from pose_ortho_truth_utils import (
    DEFAULT_FORMAL_BUNDLE_ROOT,
    ensure_dir,
    load_csv,
    load_json,
    parse_float_list,
    resolve_runtime_path,
    resolve_output_root,
    write_csv,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_FORMAL_BUNDLE_ROOT))
    parser.add_argument("--best-pose-csv", default=None)
    parser.add_argument("--pose-manifest-json", default=None)
    parser.add_argument("--dsm-manifest-csv", default=None)
    parser.add_argument("--truth-manifest-csv", default=None)
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--output-root", default=None)
    return parser.parse_args()


def load_query_image(image_path: Path) -> np.ndarray:
    import cv2

    raw = np.fromfile(str(image_path), dtype=np.uint8)
    if raw.size == 0:
        raise FileNotFoundError(f"Query image is empty or unreadable: {image_path}")
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Failed to decode query image: {image_path}")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def build_intrinsics(query_rows: list[dict[str, object]]) -> dict[str, dict[str, float]]:
    intrinsics_map: dict[str, dict[str, float]] = {}
    for row in query_rows:
        values = row.get("intrinsics", {}).get("values", {})
        if {"fx_px", "fy_px", "cx_px", "cy_px"}.issubset(values):
            intrinsics_map[str(row["query_id"])] = {
                "fx_px": float(values["fx_px"]),
                "fy_px": float(values["fy_px"]),
                "cx_px": float(values["cx_px"]),
                "cy_px": float(values["cy_px"]),
                "k1": float(values.get("k1", 0.0)),
                "k2": float(values.get("k2", 0.0)),
                "p1": float(values.get("p1", 0.0)),
                "p2": float(values.get("p2", 0.0)),
            }
    return intrinsics_map


def sample_raster_bilinear(
    band: np.ndarray,
    transform,
    xs: np.ndarray,
    ys: np.ndarray,
    nodata_value: float | int | None,
) -> tuple[np.ndarray, np.ndarray]:
    inv_transform = ~transform
    cols, rows = inv_transform * (xs, ys)
    valid = (
        np.isfinite(cols)
        & np.isfinite(rows)
        & (cols >= 0.0)
        & (rows >= 0.0)
        & (cols <= band.shape[1] - 1.0)
        & (rows <= band.shape[0] - 1.0)
    )
    values = np.full(xs.shape, np.nan, dtype=np.float32)
    if not np.any(valid):
        return values, valid

    cols_valid = cols[valid]
    rows_valid = rows[valid]
    x0 = np.floor(cols_valid).astype(np.int32)
    y0 = np.floor(rows_valid).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, band.shape[1] - 1)
    y1 = np.clip(y0 + 1, 0, band.shape[0] - 1)
    dx = cols_valid - x0
    dy = rows_valid - y0

    v00 = band[y0, x0].astype(np.float32)
    v10 = band[y0, x1].astype(np.float32)
    v01 = band[y1, x0].astype(np.float32)
    v11 = band[y1, x1].astype(np.float32)
    nodata_mask = np.zeros(v00.shape, dtype=bool)
    if nodata_value is not None and not math.isnan(float(nodata_value)):
        nodata_mask = (v00 == nodata_value) | (v10 == nodata_value) | (v01 == nodata_value) | (v11 == nodata_value)
    interp = (
        v00 * (1.0 - dx) * (1.0 - dy)
        + v10 * dx * (1.0 - dy)
        + v01 * (1.0 - dx) * dy
        + v11 * dx * dy
    )
    keep = ~nodata_mask
    valid_indices = np.flatnonzero(valid)
    values.flat[valid_indices[keep]] = interp[keep]
    valid.flat[valid_indices[~keep]] = False
    return values, valid


def remap_rgb(
    query_rgb: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    import cv2

    map_x = xs.astype(np.float32)
    map_y = ys.astype(np.float32)
    height, width = query_rgb.shape[:2]
    inside = (
        np.isfinite(map_x)
        & np.isfinite(map_y)
        & (map_x >= 0.0)
        & (map_y >= 0.0)
        & (map_x <= width - 1.0)
        & (map_y <= height - 1.0)
    )
    clipped_x = np.where(inside, map_x, 0.0)
    clipped_y = np.where(inside, map_y, 0.0)
    rgb = np.empty((3, ys.shape[0], xs.shape[1]), dtype=np.uint8)
    bgr = query_rgb[:, :, ::-1]
    for band_idx in range(3):
        remapped = cv2.remap(
            bgr[:, :, band_idx],
            clipped_x,
            clipped_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        rgb[band_idx] = remapped
    rgb = rgb[::-1]
    return rgb, inside


def render_one(
    best_row: dict[str, str],
    truth_row: dict[str, str],
    intrinsics: dict[str, float],
    dsm_row: dict[str, str],
    out_path: Path,
    block_size: int,
) -> tuple[str, str, dict[str, object]]:
    try:
        import cv2
        import rasterio
    except Exception as exc:  # pragma: no cover - dependency guard
        raise SystemExit("opencv-python and rasterio are required for predicted orthophoto rendering") from exc

    truth_path = resolve_runtime_path(truth_row["truth_crop_path"])
    if not truth_path.exists():
        return "missing_truth_crop", f"truth crop not found: {truth_path}", {}
    dsm_path = resolve_runtime_path(dsm_row["raster_path"])
    if not dsm_path.exists():
        return "missing_dsm_raster", f"dsm raster not found: {dsm_path}", {}

    query_image_path = resolve_runtime_path(truth_row["query_image_path"])
    if not query_image_path.exists():
        return "missing_query_image", f"query image not found: {query_image_path}", {}

    query_rgb = load_query_image(query_image_path)
    camera_matrix = np.array(
        [
            [intrinsics["fx_px"], 0.0, intrinsics["cx_px"]],
            [0.0, intrinsics["fy_px"], intrinsics["cy_px"]],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    dist_coeffs = np.array(
        [
            intrinsics.get("k1", 0.0),
            intrinsics.get("k2", 0.0),
            intrinsics.get("p1", 0.0),
            intrinsics.get("p2", 0.0),
        ],
        dtype=np.float64,
    )
    rvec = np.array(parse_float_list(best_row["best_rvec"]), dtype=np.float64).reshape(3, 1)
    tvec = np.array(parse_float_list(best_row["best_tvec"]), dtype=np.float64).reshape(3, 1)

    with rasterio.open(truth_path) as truth_ds, rasterio.open(dsm_path) as dsm_ds:
        if truth_ds.crs is None or dsm_ds.crs is None:
            return "missing_crs", "truth or dsm raster has no CRS", {}
        if str(truth_ds.crs) != str(dsm_ds.crs):
            return "crs_mismatch", f"truth_crs={truth_ds.crs}, dsm_crs={dsm_ds.crs}", {}

        truth_profile = truth_ds.profile.copy()
        truth_transform = truth_ds.transform
        truth_height = truth_ds.height
        truth_width = truth_ds.width
        dsm = dsm_ds.read(1)
        dsm_nodata = dsm_ds.nodata

        rgba = np.zeros((4, truth_height, truth_width), dtype=np.uint8)
        valid_pixel_count = 0
        projected_pixel_count = 0

        for row0 in range(0, truth_height, block_size):
            row1 = min(truth_height, row0 + block_size)
            for col0 in range(0, truth_width, block_size):
                col1 = min(truth_width, col0 + block_size)
                rows = np.arange(row0, row1, dtype=np.float64)
                cols = np.arange(col0, col1, dtype=np.float64)
                grid_cols, grid_rows = np.meshgrid(cols, rows)
                world_x, world_y = truth_transform * (grid_cols + 0.5, grid_rows + 0.5)
                world_z, dsm_valid = sample_raster_bilinear(
                    dsm,
                    dsm_ds.transform,
                    world_x,
                    world_y,
                    dsm_nodata,
                )
                if not np.any(dsm_valid):
                    continue
                object_points = np.stack(
                    [world_x[dsm_valid], world_y[dsm_valid], world_z[dsm_valid]],
                    axis=1,
                ).astype(np.float64)
                projected, _ = cv2.projectPoints(object_points, rvec, tvec, camera_matrix, dist_coeffs)
                projected = projected.reshape(-1, 2)
                map_x = np.full(world_x.shape, np.nan, dtype=np.float32)
                map_y = np.full(world_y.shape, np.nan, dtype=np.float32)
                map_x[dsm_valid] = projected[:, 0].astype(np.float32)
                map_y[dsm_valid] = projected[:, 1].astype(np.float32)
                rgb_block, inside = remap_rgb(query_rgb, map_x, map_y)
                valid = dsm_valid & inside
                rgba[:3, row0:row1, col0:col1] = rgb_block
                rgba[3, row0:row1, col0:col1] = np.where(valid, 255, 0).astype(np.uint8)
                valid_pixel_count += int(np.count_nonzero(valid))
                projected_pixel_count += int(np.count_nonzero(dsm_valid))

        if projected_pixel_count <= 0:
            return "dsm_intersection_failed", "no valid DSM samples on the truth grid", {}
        if valid_pixel_count <= 0:
            return "pred_projection_failed", "projection produced no valid query pixels", {}

        truth_profile.update(
            driver="GTiff",
            count=4,
            dtype="uint8",
            compress="lzw",
            tiled=True,
            nodata=None,
        )
        ensure_dir(out_path.parent)
        with rasterio.open(out_path, "w", **truth_profile) as dst:
            dst.write(rgba)

        metadata = {
            "truth_crop_path": str(truth_path).replace("\\", "/"),
            "dsm_raster_path": str(dsm_path).replace("\\", "/"),
            "query_image_path": str(query_image_path).replace("\\", "/"),
            "valid_pixel_count": valid_pixel_count,
            "projected_pixel_count": projected_pixel_count,
            "valid_pixel_ratio": float(valid_pixel_count / max(truth_height * truth_width, 1)),
        }
        return "ok", "", metadata


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    eval_root = resolve_output_root(bundle_root, args.output_root)
    pred_root = eval_root / "pred_tiles"
    ensure_dir(pred_root)

    best_pose_csv = Path(args.best_pose_csv) if args.best_pose_csv else bundle_root / "summary" / "per_query_best_pose.csv"
    pose_manifest_json = Path(args.pose_manifest_json) if args.pose_manifest_json else bundle_root / "manifest" / "pose_manifest.json"
    dsm_manifest_csv = Path(args.dsm_manifest_csv) if args.dsm_manifest_csv else bundle_root / "input" / "formal_dsm_manifest.csv"
    truth_manifest_csv = Path(args.truth_manifest_csv) if args.truth_manifest_csv else eval_root / "query_ortho_truth_manifest.csv"

    best_rows = load_csv(resolve_runtime_path(best_pose_csv))
    truth_rows = load_csv(resolve_runtime_path(truth_manifest_csv))
    dsm_rows = load_csv(resolve_runtime_path(dsm_manifest_csv))
    pose_manifest = load_json(resolve_runtime_path(pose_manifest_json))

    selected_query_ids = set(args.query_id)
    best_by_query = {row["query_id"]: row for row in best_rows if not selected_query_ids or row["query_id"] in selected_query_ids}
    truth_by_query = {row["query_id"]: row for row in truth_rows if not selected_query_ids or row["query_id"] in selected_query_ids}
    dsm_by_candidate = {row["dsm_id"]: row for row in dsm_rows}
    intrinsics_by_query = build_intrinsics(pose_manifest.get("queries", []))

    manifest_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()

    for query_id in sorted(set(best_by_query) | set(truth_by_query)):
        best_row = best_by_query.get(query_id)
        truth_row = truth_by_query.get(query_id)
        pred_path = pred_root / f"{query_id}_pred_ortho.tif"
        out_row = {
            "query_id": query_id,
            "flight_id": "",
            "best_candidate_id": "",
            "truth_crop_path": "",
            "pred_crop_path": str(pred_path).replace("\\", "/"),
            "dsm_raster_path": "",
            "status": "",
            "status_detail": "",
            "valid_pixel_count": "",
            "projected_pixel_count": "",
            "valid_pixel_ratio": "",
        }

        if best_row is None:
            out_row["status"] = "missing_best_pose"
            out_row["status_detail"] = "query missing from per_query_best_pose.csv"
            status_counts[out_row["status"]] += 1
            manifest_rows.append(out_row)
            continue
        out_row["flight_id"] = best_row.get("flight_id", "")
        out_row["best_candidate_id"] = best_row.get("best_candidate_id", "")
        if truth_row is None:
            out_row["status"] = "missing_truth_manifest"
            out_row["status_detail"] = "query missing from truth manifest"
            status_counts[out_row["status"]] += 1
            manifest_rows.append(out_row)
            continue
        out_row["truth_crop_path"] = truth_row["truth_crop_path"]
        if truth_row.get("status") != "ready":
            out_row["status"] = truth_row.get("status", "truth_manifest_not_ready")
            out_row["status_detail"] = "truth manifest row is not ready"
            status_counts[out_row["status"]] += 1
            manifest_rows.append(out_row)
            continue
        if best_row.get("best_status") != "ok":
            out_row["status"] = "best_pose_not_ok"
            out_row["status_detail"] = f"best_status={best_row.get('best_status', '')}"
            status_counts[out_row["status"]] += 1
            manifest_rows.append(out_row)
            continue
        intrinsics = intrinsics_by_query.get(query_id)
        if intrinsics is None:
            out_row["status"] = "intrinsics_missing"
            out_row["status_detail"] = "query intrinsics are missing from pose_manifest.json"
            status_counts[out_row["status"]] += 1
            manifest_rows.append(out_row)
            continue
        dsm_row = dsm_by_candidate.get(best_row["best_candidate_id"])
        if dsm_row is None:
            out_row["status"] = "missing_dsm_binding"
            out_row["status_detail"] = "best candidate has no DSM manifest row"
            status_counts[out_row["status"]] += 1
            manifest_rows.append(out_row)
            continue
        out_row["dsm_raster_path"] = dsm_row["raster_path"]

        if pred_path.exists() and not args.overwrite:
            status = "exists"
            detail = "predicted orthophoto already exists"
            metadata = {}
        else:
            status, detail, metadata = render_one(
                best_row,
                truth_row,
                intrinsics,
                dsm_row,
                pred_path,
                args.block_size,
            )
        out_row["status"] = status
        out_row["status_detail"] = detail
        for key, value in metadata.items():
            out_row[key] = value
        status_counts[status] += 1
        manifest_rows.append(out_row)

    write_csv(pred_root / "pred_tile_manifest.csv", manifest_rows)
    write_json(
        pred_root / "_summary.json",
        {
            "bundle_root": str(bundle_root),
            "best_pose_csv": str(resolve_runtime_path(best_pose_csv)),
            "pose_manifest_json": str(resolve_runtime_path(pose_manifest_json)),
            "dsm_manifest_csv": str(resolve_runtime_path(dsm_manifest_csv)),
            "truth_manifest_csv": str(resolve_runtime_path(truth_manifest_csv)),
            "row_count": len(manifest_rows),
            "status_counts": dict(status_counts),
            "generated_at_unix": time.time(),
        },
    )
    print(pred_root / "_summary.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build one real query + DOM + DSM sample case for pose Baseline v1.

Purpose:
- materialize a real-sample debug case under `new2output/pose_baseline_v1`;
- derive a DOM patch, a local DSM raster, and baseline manifests from an
  existing UAV flight workspace and one selected query image.

Main inputs:
- one selected query row with latitude / longitude and image path;
- the flight's `odm_orthophoto/odm_orthophoto.tif`;
- the flight's `odm_georeferencing/odm_georeferenced_model.laz`;
- the flight's `cameras.json`.

Main outputs:
- `real_sample_case/input/query_manifest.csv`
- `real_sample_case/input/dom_manifest.csv`
- `real_sample_case/input/dsm_manifest.csv`
- `real_sample_case/input/coarse_topk.csv`
- `real_sample_case/input/query_image.*`
- `real_sample_case/input/dom_patch.tif`
- `real_sample_case/input/local_dsm.tif`
- `real_sample_case/input/case_metadata.json`

Applicable task constraints:
- this utility is only for a real-input small-sample closure test;
- it must not be presented as formal retrieval evaluation;
- it may use the query's original metadata only to build a debug reference
  patch and local DSM around the known location.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from pathlib import Path

import laspy
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from rasterio.windows import from_bounds


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_baseline_v1"
DEFAULT_SELECTED_SUMMARY = (
    PROJECT_ROOT
    / "new1output"
    / "query_reselect_2026-03-26_v2"
    / "selected_queries"
    / "selected_images_summary.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--selected-summary-csv", default=str(DEFAULT_SELECTED_SUMMARY))
    parser.add_argument("--flight-id", default=None)
    parser.add_argument("--image-name", default="DJI_20251031135154_0001_V.JPG")
    parser.add_argument("--query-id", default="real_case_q001")
    parser.add_argument("--candidate-id", default="real_case_dom001")
    parser.add_argument("--patch-size-m", type=float, default=180.0)
    parser.add_argument("--dsm-resolution-m", type=float, default=1.0)
    parser.add_argument("--point-search-margin-m", type=float, default=20.0)
    parser.add_argument("--fill-empty-cells-iters", type=int, default=2)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def find_row(
    rows: list[dict[str, str]], flight_id: str | None, image_name: str
) -> dict[str, str]:
    if flight_id:
        for row in rows:
            if row["flight_id"] == flight_id and row["image_name"] == image_name:
                return row
        raise SystemExit(f"Selected query not found: {flight_id} / {image_name}")

    matches = [row for row in rows if row["image_name"] == image_name]
    if not matches:
        raise SystemExit(f"Selected query not found by image_name: {image_name}")
    if len(matches) > 1:
        flights = ", ".join(sorted({row["flight_id"] for row in matches}))
        raise SystemExit(
            "Multiple selected queries share the same image_name; "
            f"please pass --flight-id explicitly. image_name={image_name}, flights={flights}"
        )
    return matches[0]


def derive_intrinsics(cameras_json: Path) -> dict[str, float]:
    payload = json.loads(cameras_json.read_text(encoding="utf-8"))
    camera = next(iter(payload.values()))
    width = float(camera["width"])
    height = float(camera["height"])
    scale = max(width, height)
    return {
        "width_px": int(width),
        "height_px": int(height),
        "fx_px": float(camera["focal_x"]) * scale,
        "fy_px": float(camera["focal_y"]) * scale,
        "cx_px": width / 2.0 + float(camera.get("c_x", 0.0)) * scale,
        "cy_px": height / 2.0 + float(camera.get("c_y", 0.0)) * scale,
        "k1": float(camera.get("k1", 0.0)),
        "k2": float(camera.get("k2", 0.0)),
        "p1": float(camera.get("p1", 0.0)),
        "p2": float(camera.get("p2", 0.0)),
    }


def patch_affine_dict(transform_obj) -> dict[str, float]:
    return {
        "geo_x0": float(transform_obj.c),
        "geo_x_col": float(transform_obj.a),
        "geo_x_row": float(transform_obj.b),
        "geo_y0": float(transform_obj.f),
        "geo_y_col": float(transform_obj.d),
        "geo_y_row": float(transform_obj.e),
    }


def fill_nodata_cells(
    grid: np.ndarray, nodata_value: float, iterations: int
) -> tuple[np.ndarray, int]:
    """Fill small DSM holes from neighbouring valid cells for debug-case continuity."""
    if iterations <= 0:
        return grid, 0

    filled = grid.copy()
    total_filled = 0
    for _ in range(iterations):
        updates: list[tuple[int, int, float]] = []
        for row in range(filled.shape[0]):
            row0 = max(0, row - 1)
            row1 = min(filled.shape[0], row + 2)
            for col in range(filled.shape[1]):
                if filled[row, col] != nodata_value:
                    continue
                col0 = max(0, col - 1)
                col1 = min(filled.shape[1], col + 2)
                neighbourhood = filled[row0:row1, col0:col1]
                valid = neighbourhood[neighbourhood != nodata_value]
                if valid.size == 0:
                    continue
                updates.append((row, col, float(np.max(valid))))
        if not updates:
            break
        for row, col, value in updates:
            filled[row, col] = np.float32(value)
        total_filled += len(updates)
    return filled, total_filled


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    case_root = bundle_root / "real_sample_case"
    input_root = case_root / "input"
    ensure_dir(input_root)

    selected_rows = load_csv(Path(args.selected_summary_csv))
    selected_row = find_row(selected_rows, args.flight_id, args.image_name)
    flight_id = selected_row["flight_id"]

    flight_root = Path(selected_row["original_path"]).parent
    query_src = Path(selected_row["copied_path"])
    orthophoto_path = flight_root / "odm_orthophoto" / "odm_orthophoto.tif"
    laz_path = flight_root / "odm_georeferencing" / "odm_georeferenced_model.laz"
    cameras_json = flight_root / "cameras.json"
    if not orthophoto_path.exists():
        raise SystemExit(f"Orthophoto not found: {orthophoto_path}")
    if not laz_path.exists():
        raise SystemExit(f"LAZ point cloud not found: {laz_path}")
    if not cameras_json.exists():
        raise SystemExit(f"cameras.json not found: {cameras_json}")

    intr = derive_intrinsics(cameras_json)

    with rasterio.open(orthophoto_path) as ortho_ds:
        ortho_crs = ortho_ds.crs
        transformer = Transformer.from_crs("EPSG:4326", ortho_crs, always_xy=True)
        center_x, center_y = transformer.transform(
            float(selected_row["longitude"]), float(selected_row["latitude"])
        )
        half = args.patch_size_m / 2.0
        min_x = center_x - half
        max_x = center_x + half
        min_y = center_y - half
        max_y = center_y + half

        window = from_bounds(min_x, min_y, max_x, max_y, ortho_ds.transform)
        window = window.round_offsets().round_lengths()
        patch = ortho_ds.read(window=window)
        patch_transform = ortho_ds.window_transform(window)
        patch_profile = ortho_ds.profile.copy()
        patch_profile.update(
            width=patch.shape[2],
            height=patch.shape[1],
            transform=patch_transform,
            driver="GTiff",
        )
        dom_patch_tif = input_root / "dom_patch.tif"
        with rasterio.open(dom_patch_tif, "w", **patch_profile) as dst:
            dst.write(patch)

    # Copy the real query image into the case root without touching the source.
    query_dst = input_root / query_src.name
    if query_src.resolve() != query_dst.resolve():
        shutil.copy2(query_src, query_dst)

    # Rasterize a local DSM from the LAZ point cloud over the DOM patch extent.
    laz = laspy.read(laz_path)
    xs = np.asarray(laz.x)
    ys = np.asarray(laz.y)
    zs = np.asarray(laz.z)
    margin = args.point_search_margin_m
    mask = (
        (xs >= min_x - margin)
        & (xs <= max_x + margin)
        & (ys >= min_y - margin)
        & (ys <= max_y + margin)
    )
    xs = xs[mask]
    ys = ys[mask]
    zs = zs[mask]
    if xs.size == 0:
        raise SystemExit("No point-cloud samples found inside the requested patch bounds")

    dsm_res = float(args.dsm_resolution_m)
    width = int(math.ceil((max_x - min_x) / dsm_res))
    height = int(math.ceil((max_y - min_y) / dsm_res))
    nodata = -9999.0
    dsm_grid = np.full((height, width), nodata, dtype=np.float32)

    cols = np.floor((xs - min_x) / dsm_res).astype(np.int64)
    rows = np.floor((max_y - ys) / dsm_res).astype(np.int64)
    valid = (cols >= 0) & (cols < width) & (rows >= 0) & (rows < height)
    cols = cols[valid]
    rows = rows[valid]
    zs = zs[valid]
    for row, col, z in zip(rows, cols, zs):
        current = dsm_grid[row, col]
        if current == nodata or z > current:
            dsm_grid[row, col] = np.float32(z)

    dsm_grid, filled_cell_count = fill_nodata_cells(
        dsm_grid, nodata_value=nodata, iterations=int(args.fill_empty_cells_iters)
    )

    dsm_transform = from_origin(min_x, max_y, dsm_res, dsm_res)
    dsm_path = input_root / "local_dsm.tif"
    with rasterio.open(
        dsm_path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype="float32",
        crs=ortho_crs,
        transform=dsm_transform,
        nodata=nodata,
    ) as dst:
        dst.write(dsm_grid, 1)

    query_manifest_rows = [
        {
            "query_id": args.query_id,
            "flight_id": flight_id,
            "image_path": str(query_dst).replace("\\", "/"),
            "width_px": intr["width_px"],
            "height_px": intr["height_px"],
            "fx_px": f"{intr['fx_px']:.6f}",
            "fy_px": f"{intr['fy_px']:.6f}",
            "cx_px": f"{intr['cx_px']:.6f}",
            "cy_px": f"{intr['cy_px']:.6f}",
            "k1": f"{intr['k1']:.12f}",
            "k2": f"{intr['k2']:.12f}",
            "p1": f"{intr['p1']:.12f}",
            "p2": f"{intr['p2']:.12f}",
        }
    ]
    write_csv(input_root / "query_manifest.csv", query_manifest_rows)

    affine = patch_affine_dict(patch_transform)
    dom_manifest_rows = [
        {
            "candidate_id": args.candidate_id,
            "image_path": str(dom_patch_tif).replace("\\", "/"),
            "crs": str(ortho_crs),
            **affine,
        }
    ]
    write_csv(input_root / "dom_manifest.csv", dom_manifest_rows)

    dsm_manifest_rows = [
        {
            "dsm_id": "real_case_dsm001",
            "raster_path": str(dsm_path).replace("\\", "/"),
            "crs": str(ortho_crs),
            "nodata": nodata,
        }
    ]
    write_csv(input_root / "dsm_manifest.csv", dsm_manifest_rows)

    coarse_rows = [
        {
            "query_id": args.query_id,
            "candidate_id": args.candidate_id,
            "rank": 1,
            "score": 1.0,
        }
    ]
    write_csv(input_root / "coarse_topk.csv", coarse_rows)

    metadata = {
        "case_name": "real_sample_case",
        "purpose": "real-input small-sample geometry closure test",
        "flight_id": flight_id,
        "image_name": args.image_name,
        "query_id": args.query_id,
        "candidate_id": args.candidate_id,
        "query_source_path": str(query_src).replace("\\", "/"),
        "orthophoto_path": str(orthophoto_path).replace("\\", "/"),
        "laz_path": str(laz_path).replace("\\", "/"),
        "dom_patch_path": str(dom_patch_tif).replace("\\", "/"),
        "dsm_raster_path": str(dsm_path).replace("\\", "/"),
        "center_lon": float(selected_row["longitude"]),
        "center_lat": float(selected_row["latitude"]),
        "center_x_dom_crs": center_x,
        "center_y_dom_crs": center_y,
        "dom_patch_bounds": [min_x, min_y, max_x, max_y],
        "dom_patch_crs": str(ortho_crs),
        "dsm_resolution_m": dsm_res,
        "point_search_margin_m": args.point_search_margin_m,
        "fill_empty_cells_iters": int(args.fill_empty_cells_iters),
        "filled_cell_count": int(filled_cell_count),
        "intrinsics": intr,
    }
    (input_root / "case_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(input_root)


if __name__ == "__main__":
    main()

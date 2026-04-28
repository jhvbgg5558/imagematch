#!/usr/bin/env python3
"""Diagnose predicted-orthophoto frame support for a formal pose gate.

Purpose:
- separate DSM support, projection support, pose error, frame offset, and
  oversized truth-grid effects for rendered predicted orthophotos;
- emit compact per-query metrics and representative figures for manual QA;
- keep the diagnostics read-only with respect to pose and validation outputs.

Main inputs:
- formal best-pose outputs;
- CaiWangCun DOM-truth validation outputs;
- candidate-linked DSM rasters used by the pose branch.

Main outputs:
- `frame_sanity/per_query_frame_sanity.csv`;
- `frame_sanity/overall_frame_sanity.json`;
- `frame_sanity/failure_buckets.csv`;
- `frame_sanity/figures/*.png`.

Applicable task constraints:
- the predicted orthophoto is a single-query best-pose reprojection product,
  not a full orthomosaic reconstruction;
- no ODM LAZ, SRTM, or fallback surface is used by this diagnostic.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np

from pose_ortho_truth_utils import (
    ensure_dir,
    load_csv,
    parse_float_list,
    parse_footprint_polygon_xy,
    resolve_runtime_path,
    write_csv,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--suite-root", required=True)
    parser.add_argument("--output-root", default="")
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--representative-query-id", action="append", default=["q_003"])
    return parser.parse_args()


def polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for idx, (x0, y0) in enumerate(points):
        x1, y1 = points[(idx + 1) % len(points)]
        area += x0 * y1 - x1 * y0
    return abs(area) * 0.5


def fmt(value: float | None, digits: int = 6) -> str:
    if value is None or not math.isfinite(value):
        return ""
    return f"{value:.{digits}f}"


def summarize(values: list[float]) -> dict[str, float | None]:
    clean = [float(v) for v in values if math.isfinite(float(v))]
    if not clean:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    arr = np.asarray(clean, dtype=np.float64)
    return {
        "count": int(arr.size),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def read_alpha(path: Path) -> tuple[np.ndarray, object, object]:
    import rasterio

    with rasterio.open(path) as ds:
        data = ds.read()
        if data.shape[0] < 4:
            alpha = np.any(data[:3] > 0, axis=0).astype(np.uint8) * 255
        else:
            alpha = data[3]
        return alpha, ds.transform, ds.crs


def read_rgb_alpha(path: Path) -> tuple[np.ndarray, np.ndarray]:
    import rasterio

    with rasterio.open(path) as ds:
        data = ds.read()
    rgb = np.moveaxis(data[:3], 0, 2).astype(np.uint8)
    alpha = data[3] if data.shape[0] >= 4 else (np.any(data[:3] > 0, axis=0).astype(np.uint8) * 255)
    return rgb, alpha


def dsm_valid_on_grid(dsm_path: Path, pred_path: Path) -> np.ndarray:
    import rasterio
    from rasterio.warp import Resampling, reproject

    with rasterio.open(dsm_path) as dsm_ds, rasterio.open(pred_path) as pred_ds:
        dsm = dsm_ds.read(1)
        nodata = dsm_ds.nodata
        if nodata is None or (isinstance(nodata, float) and math.isnan(float(nodata))):
            valid_src = np.isfinite(dsm)
        else:
            valid_src = np.isfinite(dsm) & (dsm != nodata)
        valid_dst = np.zeros((pred_ds.height, pred_ds.width), dtype=np.uint8)
        reproject(
            source=valid_src.astype(np.uint8),
            destination=valid_dst,
            src_transform=dsm_ds.transform,
            src_crs=dsm_ds.crs,
            dst_transform=pred_ds.transform,
            dst_crs=pred_ds.crs,
            src_nodata=0,
            dst_nodata=0,
            resampling=Resampling.nearest,
        )
        return valid_dst > 0


def mask_bbox(mask: np.ndarray, transform) -> dict[str, float | None]:
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return {
            "min_x": None,
            "min_y": None,
            "max_x": None,
            "max_y": None,
            "center_x": None,
            "center_y": None,
            "area_m2": 0.0,
            "aspect_ratio": None,
        }
    min_col = int(xs.min())
    max_col = int(xs.max()) + 1
    min_row = int(ys.min())
    max_row = int(ys.max()) + 1
    left, top = transform * (min_col, min_row)
    right, bottom = transform * (max_col, max_row)
    min_x, max_x = sorted([float(left), float(right)])
    min_y, max_y = sorted([float(bottom), float(top)])
    width = max_x - min_x
    height = max_y - min_y
    return {
        "min_x": min_x,
        "min_y": min_y,
        "max_x": max_x,
        "max_y": max_y,
        "center_x": min_x + width / 2.0,
        "center_y": min_y + height / 2.0,
        "area_m2": width * height,
        "aspect_ratio": width / height if height > 0 else None,
    }


def camera_center_xy(best_row: dict[str, str]) -> tuple[float, float] | None:
    if not best_row.get("best_rvec") or not best_row.get("best_tvec"):
        return None
    import cv2

    rvec = np.array(parse_float_list(best_row["best_rvec"]), dtype=np.float64).reshape(3, 1)
    tvec = np.array(parse_float_list(best_row["best_tvec"]), dtype=np.float64).reshape(3, 1)
    rot, _ = cv2.Rodrigues(rvec)
    center = -rot.T @ tvec
    return float(center[0, 0]), float(center[1, 0])


def truth_bbox(row: dict[str, str]) -> tuple[float, float, float, float]:
    return (
        float(row["crop_min_x"]),
        float(row["crop_min_y"]),
        float(row["crop_max_x"]),
        float(row["crop_max_y"]),
    )


def classify(row: dict[str, object]) -> str:
    dsm_valid = float(row.get("dsm_sample_valid_ratio_on_truth_grid") or 0.0)
    pred_valid = float(row.get("pred_valid_pixel_ratio") or 0.0)
    center_offset = float(row.get("center_offset_m") or 0.0)
    horizontal_error = float(row.get("horizontal_error_m") or 0.0)
    camera_offset = float(row.get("camera_center_offset_m") or 0.0)
    truth_area_ratio = float(row.get("truth_to_footprint_area_ratio") or 0.0)
    camera_inside = str(row.get("camera_center_inside_truth_bbox", "")).lower() == "true"
    if dsm_valid < 0.5:
        return "dsm_limited"
    if camera_offset > 100.0 and center_offset > 100.0:
        return "frame_or_pose_offset"
    if horizontal_error > 50.0:
        return "pose_error"
    if truth_area_ratio > 3.0 and camera_inside and pred_valid < 0.5:
        return "single_view_or_large_truth_grid"
    if pred_valid < 0.1 and dsm_valid >= 0.8:
        return "projection_limited"
    return "ok_or_manual_review"


def save_figures(query_id: str, rgb: np.ndarray, alpha: np.ndarray, dsm_valid: np.ndarray, out_root: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ensure_dir(out_root)
    alpha_mask = alpha > 0
    overlay = np.zeros((*alpha.shape, 3), dtype=np.uint8)
    overlay[alpha_mask & dsm_valid] = np.array([0, 180, 0], dtype=np.uint8)
    overlay[alpha_mask & ~dsm_valid] = np.array([220, 50, 50], dtype=np.uint8)
    overlay[~alpha_mask & dsm_valid] = np.array([60, 120, 220], dtype=np.uint8)

    items = [
        (rgb, f"{query_id} predicted RGB", f"{query_id}_frame_overlay.png"),
        (alpha_mask.astype(np.uint8), f"{query_id} predicted valid mask", f"{query_id}_truth_vs_pred_bbox.png"),
        (dsm_valid.astype(np.uint8), f"{query_id} DSM valid on truth grid", f"{query_id}_dsm_valid_mask_on_truth_grid.png"),
        (overlay, f"{query_id} alpha vs DSM valid", f"{query_id}_offset_vectors.png"),
    ]
    for image, title, filename in items:
        plt.figure(figsize=(6, 6))
        plt.imshow(image, cmap="gray" if image.ndim == 2 else None)
        plt.title(title)
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(out_root / filename, dpi=150, bbox_inches="tight", pad_inches=0.05)
        plt.close()


def main() -> None:
    args = parse_args()
    bundle_root = resolve_runtime_path(args.bundle_root)
    suite_root = resolve_runtime_path(args.suite_root)
    output_root = (
        resolve_runtime_path(args.output_root)
        if args.output_root
        else suite_root / "ortho_alignment" / "frame_sanity"
    )
    figures_root = output_root / "figures"
    ensure_dir(output_root)
    ensure_dir(figures_root)

    query_filter = set(args.query_id)
    representative_ids = set(args.representative_query_id)

    best_rows = load_csv(bundle_root / "summary" / "per_query_best_pose.csv")
    dsm_rows = load_csv(bundle_root / "input" / "formal_dsm_manifest.csv")
    truth_rows = load_csv(suite_root / "ortho_alignment" / "query_ortho_truth_manifest.csv")
    pred_rows = load_csv(suite_root / "ortho_alignment" / "pred_tiles" / "pred_tile_manifest.csv")
    ortho_rows = load_csv(suite_root / "ortho_alignment" / "per_query_ortho_accuracy.csv")
    pose_path = suite_root / "pose_vs_at" / "per_query_pose_vs_at.csv"
    pose_rows = load_csv(pose_path) if pose_path.exists() else []

    best_by_query = {row["query_id"]: row for row in best_rows if not query_filter or row["query_id"] in query_filter}
    dsm_by_candidate = {row["candidate_tile_id"]: row for row in dsm_rows}
    truth_by_query = {row["query_id"]: row for row in truth_rows if not query_filter or row["query_id"] in query_filter}
    pred_by_query = {row["query_id"]: row for row in pred_rows if not query_filter or row["query_id"] in query_filter}
    ortho_by_query = {row["query_id"]: row for row in ortho_rows if not query_filter or row["query_id"] in query_filter}
    pose_by_query = {row["query_id"]: row for row in pose_rows if not query_filter or row["query_id"] in query_filter}

    result_rows: list[dict[str, object]] = []
    for query_id in sorted(set(best_by_query) & set(truth_by_query) & set(pred_by_query)):
        best = best_by_query[query_id]
        truth = truth_by_query[query_id]
        pred = pred_by_query[query_id]
        ortho = ortho_by_query.get(query_id, {})
        pose = pose_by_query.get(query_id, {})
        dsm = dsm_by_candidate.get(best.get("best_candidate_id", ""))
        pred_path = resolve_runtime_path(pred.get("pred_crop_path", ""))
        if dsm is None or not pred_path.exists() or pred.get("status") not in {"ok", "exists"}:
            result_rows.append(
                {
                    "query_id": query_id,
                    "best_candidate_id": best.get("best_candidate_id", ""),
                    "frame_sanity_status": "missing_inputs",
                    "diagnosis_primary": "missing_inputs",
                }
            )
            continue

        dsm_path = resolve_runtime_path(dsm["raster_path"])
        alpha, transform, _ = read_alpha(pred_path)
        alpha_mask = alpha > 0
        dsm_valid = dsm_valid_on_grid(dsm_path, pred_path)
        pred_bbox = mask_bbox(alpha_mask, transform)
        dsm_bbox = mask_bbox(dsm_valid, transform)
        bbox = truth_bbox(truth)
        truth_center_x = 0.5 * (bbox[0] + bbox[2])
        truth_center_y = 0.5 * (bbox[1] + bbox[3])
        truth_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        footprint_area = polygon_area(parse_footprint_polygon_xy(truth["footprint_polygon_xy"]))
        cam_xy = camera_center_xy(best)
        camera_offset = None
        camera_inside = ""
        if cam_xy is not None:
            camera_offset = math.hypot(cam_xy[0] - truth_center_x, cam_xy[1] - truth_center_y)
            camera_inside = str(bbox[0] <= cam_xy[0] <= bbox[2] and bbox[1] <= cam_xy[1] <= bbox[3]).lower()

        pred_center_delta = None
        if pred_bbox["center_x"] is not None and pred_bbox["center_y"] is not None:
            pred_center_delta = math.hypot(
                float(pred_bbox["center_x"]) - truth_center_x,
                float(pred_bbox["center_y"]) - truth_center_y,
            )
        dsm_center_delta = None
        if dsm_bbox["center_x"] is not None and dsm_bbox["center_y"] is not None:
            dsm_center_delta = math.hypot(
                float(dsm_bbox["center_x"]) - truth_center_x,
                float(dsm_bbox["center_y"]) - truth_center_y,
            )

        row = {
            "query_id": query_id,
            "best_candidate_id": best.get("best_candidate_id", ""),
            "frame_sanity_status": "ok",
            "dsm_sample_valid_ratio_on_truth_grid": float(np.count_nonzero(dsm_valid) / dsm_valid.size),
            "dsm_nodata_ratio_on_truth_grid": float(1.0 - np.count_nonzero(dsm_valid) / dsm_valid.size),
            "pred_valid_pixel_ratio": float(np.count_nonzero(alpha_mask) / alpha_mask.size),
            "projected_pixel_count": pred.get("projected_pixel_count", ""),
            "center_offset_m": ortho.get("center_offset_m", ""),
            "camera_center_offset_m": camera_offset,
            "camera_center_inside_truth_bbox": camera_inside,
            "bbox_center_delta_m": pred_center_delta,
            "truth_grid_center_to_pred_valid_center_offset_m": pred_center_delta,
            "truth_grid_center_to_dsm_valid_center_offset_m": dsm_center_delta,
            "horizontal_error_m": pose.get("horizontal_error_m", ""),
            "view_dir_angle_error_deg": pose.get("view_dir_angle_error_deg", ""),
            "best_inlier_ratio": best.get("best_inlier_ratio", ""),
            "best_reproj_error": best.get("best_reproj_error", ""),
            "truth_to_footprint_area_ratio": truth_area / footprint_area if footprint_area > 0 else math.nan,
            "pred_valid_bbox_area_ratio": float(pred_bbox["area_m2"] or 0.0) / truth_area if truth_area > 0 else math.nan,
            "pred_valid_bbox_aspect_ratio": pred_bbox["aspect_ratio"],
            "pred_crop_path": pred.get("pred_crop_path", ""),
            "dsm_raster_path": dsm.get("raster_path", ""),
        }
        row["diagnosis_primary"] = classify(row)
        result_rows.append(row)

        if query_id in representative_ids:
            rgb, alpha_full = read_rgb_alpha(pred_path)
            save_figures(query_id, rgb, alpha_full, dsm_valid, figures_root)

    csv_rows = []
    for row in result_rows:
        csv_rows.append({key: fmt(value) if isinstance(value, float) else value for key, value in row.items()})
    write_csv(output_root / "per_query_frame_sanity.csv", csv_rows)

    counts = Counter(str(row.get("diagnosis_primary", "")) for row in result_rows)
    numeric_fields = [
        "dsm_sample_valid_ratio_on_truth_grid",
        "pred_valid_pixel_ratio",
        "center_offset_m",
        "camera_center_offset_m",
        "bbox_center_delta_m",
        "horizontal_error_m",
        "truth_to_footprint_area_ratio",
    ]
    summaries = {}
    for field in numeric_fields:
        values = []
        for row in result_rows:
            value = row.get(field)
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                pass
        summaries[field] = summarize(values)
    write_json(
        output_root / "overall_frame_sanity.json",
        {
            "bundle_root": str(bundle_root),
            "suite_root": str(suite_root),
            "row_count": len(result_rows),
            "diagnosis_counts": dict(counts),
            "numeric_summaries": summaries,
            "generated_at_unix": time.time(),
        },
    )
    bucket_rows = [{"diagnosis_primary": key, "count": value} for key, value in sorted(counts.items())]
    write_csv(output_root / "failure_buckets.csv", bucket_rows)
    print(output_root / "overall_frame_sanity.json")


if __name__ == "__main__":
    main()

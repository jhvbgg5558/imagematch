#!/usr/bin/env python3
"""Diagnose partial-coverage holes in predicted orthophoto tiles.

Purpose:
- quantify whether predicted-ortho holes are primarily explained by DSM
  invalid regions, by pose / back-projection effects, or by oversized truth
  grids;
- produce one reproducible diagnosis table for all queries plus a standard
  visual case package for representative queries such as `q_003`;
- keep all measurements aligned to the existing pose-validation suite grids
  rather than introducing a new resampling convention.

Main inputs:
- `<bundle-root>/summary/per_query_best_pose.csv`;
- `<bundle-root>/input/formal_dsm_manifest.csv`;
- `<suite-root>/ortho_alignment/per_query_ortho_accuracy.csv`;
- `<suite-root>/ortho_alignment/pred_tiles/pred_tile_manifest.csv`;
- `<suite-root>/ortho_alignment/query_ortho_truth_manifest.csv`;
- `<satellite-suite-root>/satellite_truth/query_satellite_truth_manifest.csv`;
- `<suite-root>/pose_vs_at/per_query_pose_vs_at.csv` for pose plausibility.

Main outputs:
- `<output-root>/all_queries_hole_diagnosis.csv`;
- `<output-root>/all_queries_hole_diagnosis.json`;
- `<output-root>/q_003_diagnosis.json`;
- `<output-root>/figures/*.png` visualizing `pred_rgb`, alpha, DSM-valid mask,
  and alpha-vs-DSM overlap.

Applicable task constraints:
- diagnose the existing rendered outputs only; do not modify the renderer;
- treat predicted orthophotos as valid projected coverage on the truth grid,
  not as complete orthophoto reconstructions;
- use the candidate-linked DSM raster that was actually used by the pose
  branch, and compare DSM validity on the predicted-ortho grid directly.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

from pose_ortho_truth_utils import ensure_dir, load_csv, parse_footprint_polygon_xy, resolve_runtime_path, write_csv, write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT_ROOT = (
    PROJECT_ROOT / "new3output" / "nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-root", default=str(DEFAULT_EXPERIMENT_ROOT))
    parser.add_argument("--bundle-root", default="")
    parser.add_argument("--suite-root", default="")
    parser.add_argument("--satellite-suite-root", default="")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--representative-query-id", action="append", default=["q_003"])
    return parser.parse_args()


def polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    accum = 0.0
    for idx, (x0, y0) in enumerate(points):
        x1, y1 = points[(idx + 1) % len(points)]
        accum += x0 * y1 - x1 * y0
    return abs(accum) * 0.5


def fmt_float(value: float | None, digits: int = 6) -> str:
    if value is None or not math.isfinite(value):
        return ""
    return f"{value:.{digits}f}"


def load_truth_grid_area(row: dict[str, str]) -> tuple[float, float]:
    crop_min_x = float(row["crop_min_x"])
    crop_min_y = float(row["crop_min_y"])
    crop_max_x = float(row["crop_max_x"])
    crop_max_y = float(row["crop_max_y"])
    return crop_max_x - crop_min_x, crop_max_y - crop_min_y


def load_pred_rgb_alpha(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(path) as ds:
        data = ds.read()
    if data.shape[0] < 4:
        raise ValueError(f"Predicted orthophoto is expected to contain RGBA bands: {path}")
    rgb = np.moveaxis(data[:3], 0, 2).astype(np.uint8)
    alpha = data[3].astype(np.uint8)
    return rgb, alpha


def reproject_dsm_valid_mask(dsm_path: Path, pred_path: Path) -> np.ndarray:
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


def compute_overlap_metrics(alpha_mask: np.ndarray, dsm_valid_mask: np.ndarray) -> dict[str, float]:
    total = float(alpha_mask.size)
    alpha_valid = alpha_mask > 0
    dsm_valid = dsm_valid_mask.astype(bool)
    inter = np.logical_and(alpha_valid, dsm_valid)
    union = np.logical_or(alpha_valid, dsm_valid)
    alpha_count = float(np.count_nonzero(alpha_valid))
    dsm_count = float(np.count_nonzero(dsm_valid))
    inter_count = float(np.count_nonzero(inter))
    return {
        "pred_valid_ratio": alpha_count / total,
        "dsm_valid_ratio_on_pred_grid": dsm_count / total,
        "intersection_ratio": inter_count / total,
        "iou_alpha_vs_dsm_valid": (inter_count / float(np.count_nonzero(union))) if np.count_nonzero(union) else 0.0,
        "alpha_outside_dsm_valid_ratio": float(np.count_nonzero(alpha_valid & ~dsm_valid)) / total,
        "dsm_valid_but_alpha_empty_ratio": float(np.count_nonzero(~alpha_valid & dsm_valid)) / total,
        "alpha_outside_dsm_valid_share_of_alpha": (
            float(np.count_nonzero(alpha_valid & ~dsm_valid)) / alpha_count if alpha_count > 0 else 0.0
        ),
    }


def classify_diagnosis(
    overlap: dict[str, float],
    *,
    center_offset_m: float | None,
    horizontal_error_m: float | None,
    view_dir_angle_error_deg: float | None,
    truth_to_footprint_area_ratio: float,
) -> tuple[str, str, bool, bool, bool]:
    truth_patch_is_large_context = truth_to_footprint_area_ratio > 3.0
    pose_is_geometrically_plausible = (
        center_offset_m is not None
        and horizontal_error_m is not None
        and view_dir_angle_error_deg is not None
        and center_offset_m <= 10.0
        and horizontal_error_m <= 10.0
        and view_dir_angle_error_deg <= 2.0
    )
    pred_holes_match_water_or_low_height_regions = (
        overlap["iou_alpha_vs_dsm_valid"] >= 0.85 and overlap["alpha_outside_dsm_valid_ratio"] <= 0.05
    )

    if pred_holes_match_water_or_low_height_regions:
        primary = "dsm_limited"
    elif not pose_is_geometrically_plausible and overlap["alpha_outside_dsm_valid_ratio"] > 0.10:
        primary = "pose_limited"
    elif truth_patch_is_large_context and center_offset_m is not None and center_offset_m > 10.0:
        primary = "truth_grid_too_large"
    elif (
        overlap["iou_alpha_vs_dsm_valid"] >= 0.60
        or truth_patch_is_large_context
        or not pose_is_geometrically_plausible
    ):
        primary = "mixed_dsm_and_pose"
    else:
        primary = "unclear_manual_review"

    secondary_reasons: list[str] = []
    if truth_patch_is_large_context:
        secondary_reasons.append("truth_grid_large_context")
    if not pose_is_geometrically_plausible:
        secondary_reasons.append("pose_not_plausible")
    if overlap["iou_alpha_vs_dsm_valid"] >= 0.60:
        secondary_reasons.append("dsm_overlap_nontrivial")
    if not secondary_reasons:
        secondary_reasons.append("manual_review")
    return (
        primary,
        ",".join(secondary_reasons),
        truth_patch_is_large_context,
        pose_is_geometrically_plausible,
        pred_holes_match_water_or_low_height_regions,
    )


def save_mask_figure(mask: np.ndarray, out_path: Path, title: str) -> None:
    ensure_dir(out_path.parent)
    plt.figure(figsize=(6, 6))
    plt.imshow(mask, cmap="gray", vmin=0, vmax=1)
    plt.axis("off")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.05)
    plt.close()


def save_rgb_figure(rgb: np.ndarray, out_path: Path, title: str) -> None:
    ensure_dir(out_path.parent)
    plt.figure(figsize=(6, 6))
    plt.imshow(rgb)
    plt.axis("off")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.05)
    plt.close()


def save_overlap_figure(alpha_mask: np.ndarray, dsm_valid_mask: np.ndarray, out_path: Path, title: str) -> None:
    ensure_dir(out_path.parent)
    overlay = np.zeros((*alpha_mask.shape, 3), dtype=np.uint8)
    alpha = alpha_mask > 0
    dsm = dsm_valid_mask.astype(bool)
    overlay[np.logical_and(alpha, dsm)] = np.array([0, 180, 0], dtype=np.uint8)
    overlay[np.logical_and(alpha, ~dsm)] = np.array([220, 50, 50], dtype=np.uint8)
    overlay[np.logical_and(~alpha, dsm)] = np.array([60, 120, 220], dtype=np.uint8)
    plt.figure(figsize=(6, 6))
    plt.imshow(overlay)
    plt.axis("off")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.05)
    plt.close()


def write_case_figures(query_id: str, rgb: np.ndarray, alpha_mask: np.ndarray, dsm_valid_mask: np.ndarray, figures_root: Path) -> None:
    save_rgb_figure(rgb, figures_root / f"{query_id}_pred_rgb.png", f"{query_id} pred_rgb")
    save_mask_figure(alpha_mask > 0, figures_root / f"{query_id}_pred_alpha_mask.png", f"{query_id} pred_alpha_mask")
    save_mask_figure(
        dsm_valid_mask,
        figures_root / f"{query_id}_dsm_valid_mask_on_pred_grid.png",
        f"{query_id} dsm_valid_mask_on_pred_grid",
    )
    save_overlap_figure(
        alpha_mask,
        dsm_valid_mask,
        figures_root / f"{query_id}_alpha_vs_dsm_overlap_overlay.png",
        f"{query_id} alpha_vs_dsm_overlap_overlay",
    )


def main() -> None:
    args = parse_args()
    experiment_root = resolve_runtime_path(args.experiment_root)
    bundle_root = resolve_runtime_path(args.bundle_root) if args.bundle_root else experiment_root / "pose_v1_formal"
    suite_root = resolve_runtime_path(args.suite_root) if args.suite_root else bundle_root / "eval_pose_validation_suite_odm_truth"
    satellite_suite_root = (
        resolve_runtime_path(args.satellite_suite_root)
        if args.satellite_suite_root
        else bundle_root / "eval_pose_validation_suite_satellite_truth"
    )
    output_root = (
        resolve_runtime_path(args.output_root)
        if args.output_root
        else experiment_root / "reports" / "predicted_ortho_hole_diagnosis"
    )
    figures_root = output_root / "figures"
    ensure_dir(output_root)
    ensure_dir(figures_root)

    query_filter = set(args.query_id)
    representative_ids = list(dict.fromkeys(args.representative_query_id))

    best_rows = load_csv(bundle_root / "summary" / "per_query_best_pose.csv")
    dsm_rows = load_csv(bundle_root / "input" / "formal_dsm_manifest.csv")
    ortho_rows = load_csv(suite_root / "ortho_alignment" / "per_query_ortho_accuracy.csv")
    pred_rows = load_csv(suite_root / "ortho_alignment" / "pred_tiles" / "pred_tile_manifest.csv")
    truth_rows = load_csv(suite_root / "ortho_alignment" / "query_ortho_truth_manifest.csv")
    pose_rows = load_csv(suite_root / "pose_vs_at" / "per_query_pose_vs_at.csv")
    sat_truth_rows = load_csv(satellite_suite_root / "satellite_truth" / "query_satellite_truth_manifest.csv")
    sat_ortho_rows = load_csv(
        satellite_suite_root / "ortho_alignment_satellite" / "per_query_ortho_accuracy.csv"
    )

    best_by_query = {row["query_id"]: row for row in best_rows if not query_filter or row["query_id"] in query_filter}
    ortho_by_query = {row["query_id"]: row for row in ortho_rows if not query_filter or row["query_id"] in query_filter}
    pred_by_query = {row["query_id"]: row for row in pred_rows if not query_filter or row["query_id"] in query_filter}
    truth_by_query = {row["query_id"]: row for row in truth_rows if not query_filter or row["query_id"] in query_filter}
    pose_by_query = {row["query_id"]: row for row in pose_rows if not query_filter or row["query_id"] in query_filter}
    sat_truth_by_query = {
        row["query_id"]: row for row in sat_truth_rows if not query_filter or row["query_id"] in query_filter
    }
    sat_ortho_by_query = {
        row["query_id"]: row for row in sat_ortho_rows if not query_filter or row["query_id"] in query_filter
    }
    dsm_by_candidate = {row["candidate_tile_id"]: row for row in dsm_rows}

    if ortho_by_query:
        valid_rows = [row for row in ortho_by_query.values() if row.get("common_valid_ratio") not in {"", None}]
        if valid_rows:
            high_row = max(valid_rows, key=lambda row: float(row["common_valid_ratio"]))
            low_row = min(valid_rows, key=lambda row: float(row["common_valid_ratio"]))
            representative_ids = list(dict.fromkeys(representative_ids + [high_row["query_id"], low_row["query_id"]]))

    result_rows: list[dict[str, object]] = []

    for query_id in sorted(best_by_query):
        best_row = best_by_query[query_id]
        candidate_id = best_row["best_candidate_id"]
        dsm_row = dsm_by_candidate[candidate_id]
        ortho_row = ortho_by_query[query_id]
        pred_row = pred_by_query[query_id]
        truth_row = truth_by_query[query_id]
        pose_row = pose_by_query.get(query_id, {})
        sat_truth_row = sat_truth_by_query.get(query_id, {})
        sat_ortho_row = sat_ortho_by_query.get(query_id, {})

        pred_path = resolve_runtime_path(pred_row["pred_crop_path"])
        dsm_path = resolve_runtime_path(dsm_row["raster_path"])
        rgb, alpha = load_pred_rgb_alpha(pred_path)
        dsm_valid_mask = reproject_dsm_valid_mask(dsm_path, pred_path)
        overlap = compute_overlap_metrics(alpha, dsm_valid_mask)

        footprint_points = parse_footprint_polygon_xy(truth_row["footprint_polygon_xy"])
        footprint_area_m2 = polygon_area(footprint_points)
        crop_w, crop_h = load_truth_grid_area(truth_row)
        truth_patch_area_m2 = crop_w * crop_h
        truth_to_footprint_area_ratio = truth_patch_area_m2 / footprint_area_m2 if footprint_area_m2 > 0 else math.nan

        center_offset_m = float(ortho_row["center_offset_m"]) if ortho_row.get("center_offset_m") else None
        horizontal_error_m = float(pose_row["horizontal_error_m"]) if pose_row.get("horizontal_error_m") else None
        view_dir_angle_error_deg = (
            float(pose_row["view_dir_angle_error_deg"]) if pose_row.get("view_dir_angle_error_deg") else None
        )
        primary, secondary, truth_large, pose_plausible, holes_match_low_regions = classify_diagnosis(
            overlap,
            center_offset_m=center_offset_m,
            horizontal_error_m=horizontal_error_m,
            view_dir_angle_error_deg=view_dir_angle_error_deg,
            truth_to_footprint_area_ratio=truth_to_footprint_area_ratio,
        )

        sat_truth_patch_area_m2 = None
        sat_truth_to_footprint_area_ratio = None
        if sat_truth_row:
            sat_w = float(sat_truth_row["crop_max_x"]) - float(sat_truth_row["crop_min_x"])
            sat_h = float(sat_truth_row["crop_max_y"]) - float(sat_truth_row["crop_min_y"])
            sat_truth_patch_area_m2 = sat_w * sat_h
            sat_truth_to_footprint_area_ratio = (
                sat_truth_patch_area_m2 / footprint_area_m2 if footprint_area_m2 > 0 else math.nan
            )

        row = {
            "query_id": query_id,
            "best_candidate_id": candidate_id,
            "pred_valid_ratio": fmt_float(overlap["pred_valid_ratio"]),
            "common_valid_ratio": ortho_row.get("common_valid_ratio", ""),
            "ortho_iou": ortho_row.get("ortho_iou", ""),
            "center_offset_m": ortho_row.get("center_offset_m", ""),
            "horizontal_error_m": fmt_float(horizontal_error_m),
            "view_dir_angle_error_deg": fmt_float(view_dir_angle_error_deg),
            "dsm_valid_ratio_on_pred_grid": fmt_float(overlap["dsm_valid_ratio_on_pred_grid"]),
            "iou_alpha_vs_dsm_valid": fmt_float(overlap["iou_alpha_vs_dsm_valid"]),
            "alpha_outside_dsm_valid_ratio": fmt_float(overlap["alpha_outside_dsm_valid_ratio"]),
            "dsm_valid_but_alpha_empty_ratio": fmt_float(overlap["dsm_valid_but_alpha_empty_ratio"]),
            "truth_patch_area_m2": fmt_float(truth_patch_area_m2, 3),
            "footprint_area_m2": fmt_float(footprint_area_m2, 3),
            "truth_to_footprint_area_ratio": fmt_float(truth_to_footprint_area_ratio),
            "satellite_truth_patch_area_m2": fmt_float(sat_truth_patch_area_m2, 3) if sat_truth_patch_area_m2 else "",
            "satellite_truth_to_footprint_area_ratio": (
                fmt_float(sat_truth_to_footprint_area_ratio) if sat_truth_to_footprint_area_ratio else ""
            ),
            "satellite_common_valid_ratio": sat_ortho_row.get("common_valid_ratio", ""),
            "satellite_ortho_iou": sat_ortho_row.get("ortho_iou", ""),
            "satellite_center_offset_m": sat_ortho_row.get("center_offset_m", ""),
            "truth_patch_is_large_context": str(bool(truth_large)).lower(),
            "pose_is_geometrically_plausible": str(bool(pose_plausible)).lower(),
            "pred_holes_match_water_or_low_height_regions": str(bool(holes_match_low_regions)).lower(),
            "camera_center_inside_truth_bbox": sat_truth_row.get("camera_center_inside_truth_bbox", ""),
            "diagnosis_primary": primary,
            "diagnosis_secondary": secondary,
            "pred_crop_path": pred_row.get("pred_crop_path", ""),
            "dsm_raster_path": dsm_row.get("raster_path", ""),
        }
        result_rows.append(row)

        if query_id in representative_ids:
            write_case_figures(query_id, rgb, alpha, dsm_valid_mask, figures_root)

    write_csv(output_root / "all_queries_hole_diagnosis.csv", result_rows)
    write_json(
        output_root / "all_queries_hole_diagnosis.json",
        {
            "experiment_root": str(experiment_root),
            "bundle_root": str(bundle_root),
            "suite_root": str(suite_root),
            "satellite_suite_root": str(satellite_suite_root),
            "row_count": len(result_rows),
            "representative_query_ids": representative_ids,
            "diagnosis_counts": {
                key: sum(1 for row in result_rows if row["diagnosis_primary"] == key)
                for key in sorted({str(row["diagnosis_primary"]) for row in result_rows})
            },
            "rows": result_rows,
        },
    )

    q003_row = next((row for row in result_rows if row["query_id"] == "q_003"), None)
    if q003_row is not None:
        write_json(output_root / "q_003_diagnosis.json", q003_row)


if __name__ == "__main__":
    main()

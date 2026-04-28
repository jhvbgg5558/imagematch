#!/usr/bin/env python3
"""Evaluate predicted orthophotos against satellite truth patches.

Purpose:
- compute per-query quantitative alignment metrics on the shared grid between
  satellite truth patches and predicted orthophotos;
- keep the satellite-truth validation separate from the UAV orthophoto-truth
  suite;
- emit explicit failure rows whenever truth or predicted orthophotos are
  missing, misaligned, or have no shared valid support.

Main inputs:
- `summary/per_query_best_pose.csv`;
- `<output_root>/satellite_truth/query_satellite_truth_manifest.csv`;
- `<output_root>/pred_tiles/pred_tile_manifest.csv`;
- satellite truth and predicted orthophoto tiles on a shared grid.

Main outputs:
- `<output_root>/ortho_alignment_satellite/per_query_ortho_accuracy.csv`;
- `<output_root>/ortho_alignment_satellite/overall_ortho_accuracy.json`;
- `<output_root>/ortho_alignment_satellite/per_flight_ortho_accuracy.csv`;
- `<output_root>/ortho_alignment_satellite/failure_buckets.csv`.

Applicable task constraints:
- evaluate only the best pose per query;
- treat the satellite truth patch as offline validation only;
- refuse CRS / transform / resolution mismatches instead of implicitly
  resampling during evaluation.
"""

from __future__ import annotations

import argparse
import math
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from pose_ortho_truth_utils import (
    DEFAULT_FORMAL_BUNDLE_ROOT,
    centroid_from_mask,
    global_ssim,
    grayscale_from_image,
    load_csv,
    mask_iou,
    ncc,
    overlap_ratio,
    resolve_runtime_path,
    resolve_output_root,
    summarize_numeric,
    valid_mask_from_image,
    write_csv,
    write_json,
)
from satellite_truth_utils import DEFAULT_BUNDLE_ROOT, DEFAULT_SUITE_DIRNAME, resolve_satellite_suite_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--best-pose-csv", default=None)
    parser.add_argument("--truth-manifest-csv", default=None)
    parser.add_argument("--pred-manifest-csv", default=None)
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--output-root", default=None)
    return parser.parse_args()


def compute_phase_corr(
    truth_gray: np.ndarray,
    pred_gray: np.ndarray,
    common_mask: np.ndarray,
    resolution_m: float,
) -> tuple[float, float, float]:
    import cv2

    truth = np.where(common_mask, truth_gray, 0.0).astype(np.float32)
    pred = np.where(common_mask, pred_gray, 0.0).astype(np.float32)
    if np.count_nonzero(common_mask) < 4:
        return math.nan, math.nan, math.nan
    shift_xy, _ = cv2.phaseCorrelate(truth, pred)
    shift_x_m = float(shift_xy[0] * resolution_m)
    shift_y_m = float(shift_xy[1] * resolution_m)
    return shift_x_m, shift_y_m, float(math.hypot(shift_x_m, shift_y_m))


def evaluate_one(truth_path: Path, pred_path: Path) -> tuple[str, str, dict[str, float | None]]:
    try:
        import rasterio
    except Exception as exc:  # pragma: no cover - dependency guard
        raise SystemExit("rasterio is required for orthophoto evaluation") from exc

    if not truth_path.exists():
        return "missing_truth_crop", f"truth crop not found: {truth_path}", {}
    if not pred_path.exists():
        return "missing_pred_ortho", f"predicted orthophoto not found: {pred_path}", {}

    with rasterio.open(truth_path) as truth_ds, rasterio.open(pred_path) as pred_ds:
        if truth_ds.crs is None or pred_ds.crs is None:
            return "missing_crs", "truth or predicted orthophoto has no CRS", {}
        if str(truth_ds.crs) != str(pred_ds.crs):
            return "crs_mismatch", f"truth_crs={truth_ds.crs}, pred_crs={pred_ds.crs}", {}
        if truth_ds.width != pred_ds.width or truth_ds.height != pred_ds.height:
            return "shape_mismatch", "truth and predicted orthophotos have different raster shapes", {}
        if truth_ds.transform != pred_ds.transform:
            return "transform_mismatch", "truth and predicted orthophotos have different transforms", {}

        truth_data = truth_ds.read()
        pred_data = pred_ds.read()
        truth_mask = valid_mask_from_image(truth_data, truth_ds.nodata)
        pred_mask = valid_mask_from_image(pred_data, pred_ds.nodata)
        common_mask = truth_mask & pred_mask
        common_valid_ratio = float(np.count_nonzero(common_mask) / common_mask.size)
        if np.count_nonzero(common_mask) <= 0:
            return "no_common_valid_pixels", "truth and predicted orthophotos do not overlap on valid pixels", {
                "common_valid_ratio": common_valid_ratio,
                "ortho_iou": 0.0,
                "ortho_overlap_ratio": 0.0,
            }

        truth_gray = grayscale_from_image(truth_data)
        pred_gray = grayscale_from_image(pred_data)
        resolution_x = abs(float(truth_ds.transform.a))
        resolution_y = abs(float(truth_ds.transform.e))
        resolution_m = 0.5 * (resolution_x + resolution_y)
        shift_x_m, shift_y_m, shift_error_m = compute_phase_corr(
            truth_gray,
            pred_gray,
            common_mask,
            resolution_m,
        )
        truth_center = centroid_from_mask(truth_mask, truth_ds.transform)
        pred_center = centroid_from_mask(pred_mask, pred_ds.transform)
        center_offset_m = math.nan
        if truth_center is not None and pred_center is not None:
            center_offset_m = float(math.hypot(pred_center[0] - truth_center[0], pred_center[1] - truth_center[1]))

        metrics = {
            "phase_corr_shift_x_m": shift_x_m,
            "phase_corr_shift_y_m": shift_y_m,
            "phase_corr_error_m": shift_error_m,
            "center_offset_m": center_offset_m,
            "ortho_iou": float(mask_iou(truth_mask, pred_mask)),
            "ortho_overlap_ratio": float(overlap_ratio(pred_mask, truth_mask)),
            "ncc": float(ncc(truth_gray, pred_gray, common_mask)),
            "ssim": float(global_ssim(truth_gray, pred_gray, common_mask)),
            "common_valid_ratio": common_valid_ratio,
        }
        return "ok", "", metrics


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    suite_root = resolve_satellite_suite_root(bundle_root, args.output_root)
    ortho_root = suite_root / "ortho_alignment_satellite"
    best_pose_csv = Path(args.best_pose_csv) if args.best_pose_csv else bundle_root / "summary" / "per_query_best_pose.csv"
    truth_manifest_csv = (
        Path(args.truth_manifest_csv)
        if args.truth_manifest_csv
        else suite_root / "satellite_truth" / "query_satellite_truth_manifest.csv"
    )
    pred_manifest_csv = (
        Path(args.pred_manifest_csv)
        if args.pred_manifest_csv
        else suite_root / "pred_tiles" / "pred_tile_manifest.csv"
    )

    best_rows = load_csv(resolve_runtime_path(best_pose_csv))
    truth_rows = load_csv(resolve_runtime_path(truth_manifest_csv))
    pred_rows = load_csv(resolve_runtime_path(pred_manifest_csv))
    selected_query_ids = set(args.query_id)

    best_by_query = {row["query_id"]: row for row in best_rows if not selected_query_ids or row["query_id"] in selected_query_ids}
    truth_by_query = {row["query_id"]: row for row in truth_rows if not selected_query_ids or row["query_id"] in selected_query_ids}
    pred_by_query = {row["query_id"]: row for row in pred_rows if not selected_query_ids or row["query_id"] in selected_query_ids}

    result_rows: list[dict[str, object]] = []
    failure_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    per_flight_metrics: defaultdict[str, list[dict[str, object]]] = defaultdict(list)

    for query_id in sorted(set(best_by_query) | set(truth_by_query) | set(pred_by_query)):
        best_row = best_by_query.get(query_id)
        truth_row = truth_by_query.get(query_id)
        pred_row = pred_by_query.get(query_id)
        base_row: dict[str, object] = {
            "query_id": query_id,
            "flight_id": "",
            "best_candidate_id": "",
            "truth_crop_path": "",
            "pred_crop_path": "",
            "phase_corr_shift_x_m": "",
            "phase_corr_shift_y_m": "",
            "phase_corr_error_m": "",
            "center_offset_m": "",
            "ortho_iou": "",
            "ortho_overlap_ratio": "",
            "ncc": "",
            "ssim": "",
            "common_valid_ratio": "",
            "best_inlier_count": "",
            "best_inlier_ratio": "",
            "best_reproj_error": "",
            "best_score": "",
            "eval_status": "",
            "eval_status_detail": "",
        }
        if best_row is not None:
            base_row["flight_id"] = best_row.get("flight_id", "")
            base_row["best_candidate_id"] = best_row.get("best_candidate_id", "")
            base_row["best_inlier_count"] = best_row.get("best_inlier_count", "")
            base_row["best_inlier_ratio"] = best_row.get("best_inlier_ratio", "")
            base_row["best_reproj_error"] = best_row.get("best_reproj_error", "")
            base_row["best_score"] = best_row.get("best_score", "")
        if truth_row is not None:
            base_row["truth_crop_path"] = truth_row.get("truth_crop_path", "")
            if not base_row["flight_id"]:
                base_row["flight_id"] = truth_row.get("flight_id", "")
        if pred_row is not None:
            base_row["pred_crop_path"] = pred_row.get("pred_crop_path", "")

        if best_row is None:
            status = "missing_best_pose"
            detail = "query missing from best-pose summary"
            metrics = {}
        elif truth_row is None:
            status = "missing_truth_manifest"
            detail = "query missing from satellite truth manifest"
            metrics = {}
        elif pred_row is None:
            status = "missing_pred_manifest"
            detail = "query missing from predicted ortho manifest"
            metrics = {}
        elif pred_row.get("status") not in {"ok", "exists"}:
            status = pred_row.get("status", "pred_ortho_failed")
            detail = pred_row.get("status_detail", "predicted orthophoto stage failed")
            metrics = {}
        else:
            status, detail, metrics = evaluate_one(
                resolve_runtime_path(base_row["truth_crop_path"]),
                resolve_runtime_path(base_row["pred_crop_path"]),
            )

        base_row["eval_status"] = status
        base_row["eval_status_detail"] = detail
        for key, value in metrics.items():
            if value is None or (isinstance(value, float) and not math.isfinite(value)):
                base_row[key] = ""
            else:
                base_row[key] = f"{float(value):.6f}"
        status_counts[status] += 1
        result_rows.append(base_row)
        if status != "ok":
            failure_rows.append(
                {
                    "query_id": query_id,
                    "flight_id": base_row["flight_id"],
                    "status": status,
                    "detail": detail,
                }
            )
        if base_row["flight_id"]:
            per_flight_metrics[str(base_row["flight_id"])].append(base_row)

    write_csv(ortho_root / "per_query_ortho_accuracy.csv", result_rows)
    write_csv(ortho_root / "failure_buckets.csv", failure_rows)

    numeric_payload = {
        "phase_corr_error_m": summarize_numeric([float(row["phase_corr_error_m"]) for row in result_rows if row["eval_status"] == "ok" and row["phase_corr_error_m"] != ""]),
        "center_offset_m": summarize_numeric([float(row["center_offset_m"]) for row in result_rows if row["eval_status"] == "ok" and row["center_offset_m"] != ""]),
        "ortho_iou": summarize_numeric([float(row["ortho_iou"]) for row in result_rows if row["eval_status"] == "ok" and row["ortho_iou"] != ""]),
        "ssim": summarize_numeric([float(row["ssim"]) for row in result_rows if row["eval_status"] == "ok" and row["ssim"] != ""]),
    }
    write_json(
        ortho_root / "overall_ortho_accuracy.json",
        {
            "bundle_root": str(bundle_root),
            "truth_manifest_csv": str(resolve_runtime_path(truth_manifest_csv)),
            "pred_manifest_csv": str(resolve_runtime_path(pred_manifest_csv)),
            "status_counts": dict(status_counts),
            **numeric_payload,
            "generated_at_unix": time.time(),
        },
    )

    per_flight_rows = []
    for flight_id in sorted(per_flight_metrics):
        rows = per_flight_metrics[flight_id]
        ok_rows = [row for row in rows if row["eval_status"] == "ok"]
        per_flight_rows.append(
            {
                "flight_id": flight_id,
                "short_flight_id": flight_id.split("_")[2] if len(flight_id.split("_")) >= 3 else flight_id,
                "query_count": len(rows),
                "ok_count": len(ok_rows),
                "phase_corr_error_m_mean": summarize_numeric([float(row["phase_corr_error_m"]) for row in ok_rows if row["phase_corr_error_m"] != ""])["mean"],
                "center_offset_m_mean": summarize_numeric([float(row["center_offset_m"]) for row in ok_rows if row["center_offset_m"] != ""])["mean"],
                "ortho_iou_mean": summarize_numeric([float(row["ortho_iou"]) for row in ok_rows if row["ortho_iou"] != ""])["mean"],
                "ssim_mean": summarize_numeric([float(row["ssim"]) for row in ok_rows if row["ssim"] != ""])["mean"],
            }
        )
    write_csv(ortho_root / "per_flight_ortho_accuracy.csv", per_flight_rows)

    print(ortho_root / "overall_ortho_accuracy.json")


if __name__ == "__main__":
    main()

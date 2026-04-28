#!/usr/bin/env python3
"""Evaluate tie-point ground XY error between predicted and truth orthophotos.

Purpose:
- compute query-level local geometric accuracy from matched tie-points between
  `eval_ortho_truth/truth_tiles` and `eval_ortho_truth/pred_tiles`;
- keep the new metric anchored on `truth vs pred` only, without reusing runtime
  DOM products or pose-stage correspondences;
- export per-query tie-point details, aggregate summaries, and explicit failure
  buckets that remain compatible with the existing orthophoto-truth pipeline.

Main inputs:
- `<ortho_output_root>/per_query_ortho_accuracy.csv`;
- truth and predicted orthophoto GeoTIFF tiles on a shared grid.

Main outputs:
- `<output_root>/per_query_tiepoint_ground_error.csv`;
- `<output_root>/overall_tiepoint_ground_error.json`;
- `<output_root>/per_flight_tiepoint_ground_error.csv`;
- `<output_root>/tiepoint_failure_buckets.csv`;
- `<output_root>/tiepoints/per_query_matches/<query_id>_tiepoints.csv`.

Applicable task constraints:
- evaluate only `truth vs pred` on their shared truth grid;
- restrict feature extraction and matching to `common_valid_mask`;
- per-query tie-point detail CSVs contain only RANSAC inliers, matching the
  formal RMSE/inlier metric scope;
- keep XY planar ground error as the formal metric; do not add Z here.
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
    ensure_dir,
    grayscale_from_image,
    load_csv,
    resolve_runtime_path,
    resolve_output_root,
    summarize_numeric_extended,
    valid_mask_from_image,
    write_csv,
    write_json,
)


DETAIL_FIELDS = [
    "query_id",
    "match_index",
    "truth_col_px",
    "truth_row_px",
    "pred_col_px",
    "pred_row_px",
    "truth_x_m",
    "truth_y_m",
    "pred_x_m",
    "pred_y_m",
    "dx_m",
    "dy_m",
    "dxy_m",
]


def trim_features(keypoints, descriptors: np.ndarray | None, max_features: int):
    if descriptors is None or not keypoints:
        return keypoints, descriptors
    if max_features <= 0 or len(keypoints) <= max_features:
        return keypoints, descriptors
    order = sorted(
        range(len(keypoints)),
        key=lambda idx: float(getattr(keypoints[idx], "response", 0.0)),
        reverse=True,
    )[:max_features]
    trimmed_keypoints = [keypoints[idx] for idx in order]
    trimmed_descriptors = descriptors[np.asarray(order, dtype=np.int64)]
    return trimmed_keypoints, trimmed_descriptors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_FORMAL_BUNDLE_ROOT))
    parser.add_argument("--ortho-accuracy-csv", default=None)
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--min-inliers", type=int, default=6)
    parser.add_argument("--ratio-test", type=float, default=0.75)
    parser.add_argument("--ransac-threshold-px", type=float, default=4.0)
    parser.add_argument("--max-features-per-image", type=int, default=200000)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--ortho-output-root", default=None)
    return parser.parse_args()


def to_uint8(gray: np.ndarray, mask: np.ndarray) -> np.ndarray:
    values = gray[mask]
    if values.size == 0:
        return np.zeros_like(gray, dtype=np.uint8)
    lo = float(np.percentile(values, 2))
    hi = float(np.percentile(values, 98))
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((gray - lo) * (255.0 / (hi - lo)), 0.0, 255.0)
    return scaled.astype(np.uint8)


def compute_ground_xy(transform, cols: np.ndarray, rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = transform * (cols + 0.5, rows + 0.5)
    return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)


def evaluate_one(
    truth_path: Path,
    pred_path: Path,
    min_inliers: int,
    ratio_test: float,
    ransac_threshold_px: float,
    max_features_per_image: int,
) -> tuple[str, str, dict[str, float | int], list[dict[str, object]]]:
    try:
        import cv2
        import rasterio
    except Exception as exc:  # pragma: no cover - dependency guard
        raise SystemExit("cv2 and rasterio are required for tie-point evaluation") from exc

    if not truth_path.exists():
        return "missing_truth_ortho", f"truth orthophoto not found: {truth_path}", {}, []
    if not pred_path.exists():
        return "missing_pred_ortho", f"predicted orthophoto not found: {pred_path}", {}, []

    with rasterio.open(truth_path) as truth_ds, rasterio.open(pred_path) as pred_ds:
        if truth_ds.crs is None or pred_ds.crs is None:
            return "missing_crs", "truth or predicted orthophoto has no CRS", {}, []
        if str(truth_ds.crs) != str(pred_ds.crs):
            return "crs_mismatch", f"truth_crs={truth_ds.crs}, pred_crs={pred_ds.crs}", {}, []
        if truth_ds.width != pred_ds.width or truth_ds.height != pred_ds.height:
            return "shape_mismatch", "truth and predicted orthophotos have different raster shapes", {}, []
        if truth_ds.transform != pred_ds.transform:
            return "transform_mismatch", "truth and predicted orthophotos have different transforms", {}, []

        truth_data = truth_ds.read()
        pred_data = pred_ds.read()
        truth_mask = valid_mask_from_image(truth_data, truth_ds.nodata)
        pred_mask = valid_mask_from_image(pred_data, pred_ds.nodata)
        common_mask = truth_mask & pred_mask
        if np.count_nonzero(common_mask) <= 0:
            return "no_common_valid_pixels", "truth and predicted orthophotos do not overlap on valid pixels", {}, []

        truth_gray = grayscale_from_image(truth_data)
        pred_gray = grayscale_from_image(pred_data)
        truth_u8 = to_uint8(truth_gray, common_mask)
        pred_u8 = to_uint8(pred_gray, common_mask)
        mask_u8 = (common_mask.astype(np.uint8) * 255)

        try:
            sift = cv2.SIFT_create()
            truth_kp, truth_desc = sift.detectAndCompute(truth_u8, mask_u8)
            pred_kp, pred_desc = sift.detectAndCompute(pred_u8, mask_u8)
        except Exception as exc:
            return "feature_extraction_failed", f"SIFT detection failed: {exc}", {}, []

        if truth_desc is None or pred_desc is None or not truth_kp or not pred_kp:
            return "no_tiepoints_found", "no valid SIFT features found in the common valid region", {}, []

        truth_kp, truth_desc = trim_features(truth_kp, truth_desc, max_features_per_image)
        pred_kp, pred_desc = trim_features(pred_kp, pred_desc, max_features_per_image)
        if truth_desc is None or pred_desc is None or not truth_kp or not pred_kp:
            return "no_tiepoints_found", "no valid SIFT features remained after feature trimming", {}, []

        matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
        try:
            raw_matches = matcher.knnMatch(truth_desc, pred_desc, k=2)
        except cv2.error as exc:
            return "descriptor_matching_failed", f"OpenCV knnMatch failed: {exc}", {}, []
        good_matches = []
        for item in raw_matches:
            if len(item) < 2:
                continue
            first, second = item
            if second.distance <= 0:
                continue
            if first.distance < ratio_test * second.distance:
                good_matches.append(first)

        if not good_matches:
            return "no_tiepoints_found", "descriptor matching produced no ratio-test survivors", {}, []

        truth_pts = np.float32([truth_kp[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        pred_pts = np.float32([pred_kp[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        _, inlier_mask = cv2.findHomography(truth_pts, pred_pts, cv2.RANSAC, ransac_threshold_px)
        if inlier_mask is None or int(np.count_nonzero(inlier_mask)) <= 0:
            return "ransac_rejected_all", "RANSAC rejected all tentative tie-points", {
                "tiepoint_match_count": len(good_matches),
                "tiepoint_inlier_count": 0,
                "tiepoint_inlier_ratio": 0.0,
            }, []

        inlier_flat = inlier_mask.ravel().astype(bool)
        inlier_count = int(np.count_nonzero(inlier_flat))
        inlier_ratio = float(inlier_count / len(good_matches))
        if inlier_count < min_inliers:
            return "too_few_tiepoints", f"RANSAC retained {inlier_count} inliers, below min_inliers={min_inliers}", {
                "tiepoint_match_count": len(good_matches),
                "tiepoint_inlier_count": inlier_count,
                "tiepoint_inlier_ratio": inlier_ratio,
            }, []

        truth_xy = truth_pts[inlier_flat, 0, :]
        pred_xy = pred_pts[inlier_flat, 0, :]
        truth_cols = truth_xy[:, 0].astype(np.float64)
        truth_rows = truth_xy[:, 1].astype(np.float64)
        pred_cols = pred_xy[:, 0].astype(np.float64)
        pred_rows = pred_xy[:, 1].astype(np.float64)
        truth_x_m, truth_y_m = compute_ground_xy(truth_ds.transform, truth_cols, truth_rows)
        pred_x_m, pred_y_m = compute_ground_xy(pred_ds.transform, pred_cols, pred_rows)
        dx = pred_x_m - truth_x_m
        dy = pred_y_m - truth_y_m
        dxy = np.hypot(dx, dy)

        xy_stats = summarize_numeric_extended(dxy.tolist())
        detail_rows: list[dict[str, object]] = []
        for idx in range(inlier_count):
            detail_rows.append(
                {
                    "query_id": "",
                    "match_index": idx,
                    "truth_col_px": f"{truth_cols[idx]:.6f}",
                    "truth_row_px": f"{truth_rows[idx]:.6f}",
                    "pred_col_px": f"{pred_cols[idx]:.6f}",
                    "pred_row_px": f"{pred_rows[idx]:.6f}",
                    "truth_x_m": f"{truth_x_m[idx]:.6f}",
                    "truth_y_m": f"{truth_y_m[idx]:.6f}",
                    "pred_x_m": f"{pred_x_m[idx]:.6f}",
                    "pred_y_m": f"{pred_y_m[idx]:.6f}",
                    "dx_m": f"{dx[idx]:.6f}",
                    "dy_m": f"{dy[idx]:.6f}",
                    "dxy_m": f"{dxy[idx]:.6f}",
                }
            )

        metrics = {
            "tiepoint_match_count": len(good_matches),
            "tiepoint_inlier_count": inlier_count,
            "tiepoint_inlier_ratio": inlier_ratio,
            "tiepoint_xy_error_mean_m": xy_stats["mean"],
            "tiepoint_xy_error_median_m": xy_stats["median"],
            "tiepoint_xy_error_rmse_m": xy_stats["rmse"],
            "tiepoint_xy_error_p90_m": xy_stats["p90"],
            "tiepoint_xy_error_max_m": xy_stats["max"],
            "tiepoint_dx_mean_m": float(np.mean(dx)),
            "tiepoint_dy_mean_m": float(np.mean(dy)),
        }
        return "tiepoint_eval_ok", "", metrics, detail_rows


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    eval_root = resolve_output_root(bundle_root, args.output_root)
    ortho_root = resolve_output_root(bundle_root, args.ortho_output_root)
    ortho_accuracy_csv = Path(args.ortho_accuracy_csv) if args.ortho_accuracy_csv else ortho_root / "per_query_ortho_accuracy.csv"
    rows = load_csv(resolve_runtime_path(ortho_accuracy_csv))
    selected_query_ids = set(args.query_id)
    if selected_query_ids:
        rows = [row for row in rows if row["query_id"] in selected_query_ids]

    tiepoint_root = eval_root / "tiepoints"
    per_query_match_root = tiepoint_root / "per_query_matches"
    ensure_dir(per_query_match_root)

    result_rows: list[dict[str, object]] = []
    failure_rows: list[dict[str, object]] = []
    per_flight_rows_map: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    status_counts: Counter[str] = Counter()
    matchable_query_count = 0
    detail_csv_count = 0
    missing_detail_query_ids: list[str] = []
    pooled_dxy_all: list[float] = []
    pooled_dxy_by_flight: defaultdict[str, list[float]] = defaultdict(list)

    for row in rows:
        query_id = row["query_id"]
        base_row: dict[str, object] = {
            "query_id": query_id,
            "flight_id": row.get("flight_id", ""),
            "best_candidate_id": row.get("best_candidate_id", ""),
            "truth_crop_path": row.get("truth_crop_path", ""),
            "pred_crop_path": row.get("pred_crop_path", ""),
            "tiepoint_match_count": "",
            "tiepoint_inlier_count": "",
            "tiepoint_inlier_ratio": "",
            "tiepoint_xy_error_mean_m": "",
            "tiepoint_xy_error_median_m": "",
            "tiepoint_xy_error_rmse_m": "",
            "tiepoint_xy_error_p90_m": "",
            "tiepoint_xy_error_max_m": "",
            "tiepoint_dx_mean_m": "",
            "tiepoint_dy_mean_m": "",
            "eval_status": "",
            "eval_status_detail": "",
        }

        upstream_status = row.get("eval_status", "")
        if upstream_status != "ok":
            status = "upstream_eval_failed"
            detail = f"upstream orthophoto evaluation status={upstream_status}"
            metrics = {}
            detail_rows = []
        else:
            matchable_query_count += 1
            status, detail, metrics, detail_rows = evaluate_one(
                resolve_runtime_path(row["truth_crop_path"]),
                resolve_runtime_path(row["pred_crop_path"]),
                min_inliers=args.min_inliers,
                ratio_test=args.ratio_test,
                ransac_threshold_px=args.ransac_threshold_px,
                max_features_per_image=args.max_features_per_image,
            )

        base_row["eval_status"] = status
        base_row["eval_status_detail"] = detail
        for key, value in metrics.items():
            if value is None or (isinstance(value, float) and not math.isfinite(value)):
                base_row[key] = ""
            elif isinstance(value, int):
                base_row[key] = str(value)
            else:
                base_row[key] = f"{float(value):.6f}"

        if detail_rows:
            for detail_row in detail_rows:
                detail_row["query_id"] = query_id
            ordered_detail_rows = [
                {field: detail_row.get(field, "") for field in DETAIL_FIELDS}
                for detail_row in detail_rows
            ]
            pooled_values = [float(detail_row["dxy_m"]) for detail_row in ordered_detail_rows]
            pooled_dxy_all.extend(pooled_values)
            pooled_dxy_by_flight[str(base_row["flight_id"])].extend(pooled_values)
            write_csv(per_query_match_root / f"{query_id}_tiepoints.csv", ordered_detail_rows)
            detail_csv_count += 1
        else:
            missing_detail_query_ids.append(query_id)

        status_counts[status] += 1
        result_rows.append(base_row)
        if status != "tiepoint_eval_ok":
            failure_rows.append(
                {
                    "query_id": query_id,
                    "flight_id": base_row["flight_id"],
                    "best_candidate_id": base_row["best_candidate_id"],
                    "failure_bucket": status,
                    "detail": detail,
                }
            )
        else:
            per_flight_rows_map[str(base_row["flight_id"])].append(base_row)

    ok_rows = [row for row in result_rows if row["eval_status"] == "tiepoint_eval_ok"]
    overall_payload = {
        "query_count": len(result_rows),
        "evaluated_query_count": len(ok_rows),
        "matchable_query_count": matchable_query_count,
        "tiepoint_xy_error_mean_m": summarize_numeric_extended(pooled_dxy_all)["mean"],
        "tiepoint_xy_error_median_m": summarize_numeric_extended(pooled_dxy_all)["median"],
        "tiepoint_xy_error_rmse_m": summarize_numeric_extended(pooled_dxy_all)["rmse"],
        "tiepoint_xy_error_p90_m": summarize_numeric_extended(pooled_dxy_all)["p90"],
        "tiepoint_match_count_mean": summarize_numeric_extended(
            [float(row["tiepoint_match_count"]) for row in ok_rows if row["tiepoint_match_count"] != ""]
        )["mean"],
        "tiepoint_inlier_ratio_mean": summarize_numeric_extended(
            [float(row["tiepoint_inlier_ratio"]) for row in ok_rows if row["tiepoint_inlier_ratio"] != ""]
        )["mean"],
        "eval_status_counts": dict(status_counts),
        "tiepoint_detail_scope": "ratio_test_ransac_inliers",
        "tiepoint_detail_csv_dir": str(per_query_match_root),
        "tiepoint_detail_csv_pattern": "<query_id>_tiepoints.csv",
        "tiepoint_detail_csv_fields": DETAIL_FIELDS,
        "tiepoint_detail_csv_count": detail_csv_count,
        "missing_tiepoint_detail_query_ids": missing_detail_query_ids,
        "generated_at_unix": time.time(),
    }

    per_flight_rows: list[dict[str, object]] = []
    for flight_id, flight_rows in sorted(per_flight_rows_map.items()):
        pooled_dxy = pooled_dxy_by_flight.get(flight_id, [])
        per_flight_rows.append(
            {
                "flight_id": flight_id,
                "query_count": len(flight_rows),
                "tiepoint_xy_error_mean_m": summarize_numeric_extended(pooled_dxy)["mean"],
                "tiepoint_xy_error_median_m": summarize_numeric_extended(pooled_dxy)["median"],
                "tiepoint_xy_error_rmse_m": summarize_numeric_extended(pooled_dxy)["rmse"],
                "tiepoint_xy_error_p90_m": summarize_numeric_extended(pooled_dxy)["p90"],
                "tiepoint_match_count_mean": summarize_numeric_extended(
                    [float(row["tiepoint_match_count"]) for row in flight_rows if row["tiepoint_match_count"] != ""]
                )["mean"],
                "tiepoint_inlier_ratio_mean": summarize_numeric_extended(
                    [float(row["tiepoint_inlier_ratio"]) for row in flight_rows if row["tiepoint_inlier_ratio"] != ""]
                )["mean"],
            }
        )

    write_csv(eval_root / "per_query_tiepoint_ground_error.csv", result_rows)
    write_json(eval_root / "overall_tiepoint_ground_error.json", overall_payload)
    write_csv(
        eval_root / "per_flight_tiepoint_ground_error.csv",
        per_flight_rows
        or [
            {
                "flight_id": "",
                "query_count": 0,
                "tiepoint_xy_error_mean_m": "",
                "tiepoint_xy_error_median_m": "",
                "tiepoint_xy_error_rmse_m": "",
                "tiepoint_xy_error_p90_m": "",
                "tiepoint_match_count_mean": "",
                "tiepoint_inlier_ratio_mean": "",
            }
        ],
    )
    write_csv(
        eval_root / "tiepoint_failure_buckets.csv",
        failure_rows
        or [
            {
                "query_id": "",
                "flight_id": "",
                "best_candidate_id": "",
                "failure_bucket": "",
                "detail": "",
            }
        ],
    )
    print(eval_root / "overall_tiepoint_ground_error.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Evaluate satellite-truth tie-point ground XY error with RoMa v2."""

from __future__ import annotations

import argparse
import math
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from romav2 import RoMaV2

from pose_ortho_truth_utils import (
    ensure_dir,
    grayscale_from_image,
    load_csv,
    resolve_output_root,
    resolve_runtime_path,
    summarize_numeric_extended,
    valid_mask_from_image,
    write_csv,
    write_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = (
    PROJECT_ROOT
    / "new3output"
    / "nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16"
    / "pose_v1_formal"
)
DEFAULT_SUITE_DIRNAME = "eval_pose_validation_suite_sattruth_srtm"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--ortho-accuracy-csv", default=None)
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--min-inliers", type=int, default=6)
    parser.add_argument("--sample-count", type=int, default=5000)
    parser.add_argument("--ransac-threshold-px", type=float, default=4.0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--setting", default="satast")
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--ortho-output-root", default=None)
    return parser.parse_args()


def build_model(setting: str, device_name: str) -> RoMaV2:
    if device_name == "auto":
        use_cuda = torch.cuda.is_available()
    else:
        use_cuda = device_name.startswith("cuda")
    if use_cuda:
        torch.set_default_device("cuda")
    torch.set_float32_matmul_precision("highest")
    cfg = RoMaV2.Cfg(setting=setting, compile=False, name=f"RoMaV2-{setting}")
    return RoMaV2(cfg)


def compute_ground_xy(transform, cols: np.ndarray, rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = transform * (cols + 0.5, rows + 0.5)
    return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)


def to_uint8_rgb(data: np.ndarray) -> np.ndarray:
    if data.ndim == 2:
        data = data[np.newaxis, :, :]
    if data.shape[0] == 1:
        stacked = np.repeat(data, 3, axis=0)
    elif data.shape[0] == 2:
        stacked = np.repeat(data[:1], 3, axis=0)
    else:
        stacked = data[:3]
    stacked = np.moveaxis(stacked, 0, -1)
    if stacked.dtype == np.uint8:
        return stacked
    if np.issubdtype(stacked.dtype, np.integer):
        info = np.iinfo(stacked.dtype)
        scaled = (stacked.astype(np.float32) - float(info.min)) * (255.0 / max(float(info.max - info.min), 1.0))
        return np.clip(scaled, 0.0, 255.0).astype(np.uint8)
    values = stacked[np.isfinite(stacked)]
    if values.size == 0:
        return np.zeros_like(stacked, dtype=np.uint8)
    lo = float(np.percentile(values, 2))
    hi = float(np.percentile(values, 98))
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((stacked - lo) * (255.0 / (hi - lo)), 0.0, 255.0)
    return scaled.astype(np.uint8)


def save_temp_geotiff(path: Path, data_rgb: np.ndarray, profile: dict[str, object]) -> None:
    import rasterio

    ensure_dir(path.parent)
    out_profile = profile.copy()
    out_profile.update(
        driver="GTiff",
        count=3,
        height=data_rgb.shape[0],
        width=data_rgb.shape[1],
        compress="lzw",
        tiled=True,
    )
    with rasterio.open(path, "w", **out_profile) as dst:
        dst.write(np.moveaxis(data_rgb, -1, 0))


def prepare_pair(truth_path: Path, pred_path: Path) -> tuple[str, str, dict[str, object]]:
    try:
        import rasterio
    except Exception as exc:  # pragma: no cover - dependency guard
        raise SystemExit("rasterio is required for tie-point evaluation") from exc

    if not truth_path.exists():
        return "missing_truth_ortho", f"truth crop not found: {truth_path}", {}
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
        if np.count_nonzero(common_mask) <= 0:
            return "no_common_valid_pixels", "truth and predicted orthophotos do not overlap on valid pixels", {}

        rows, cols = np.where(common_mask)
        row_min = int(rows.min())
        row_max = int(rows.max()) + 1
        col_min = int(cols.min())
        col_max = int(cols.max()) + 1
        crop_mask = common_mask[row_min:row_max, col_min:col_max]
        crop_truth = truth_data[:, row_min:row_max, col_min:col_max].copy()
        crop_pred = pred_data[:, row_min:row_max, col_min:col_max].copy()
        crop_truth[:, ~crop_mask] = 0
        crop_pred[:, ~crop_mask] = 0

        return "ok", "", {
            "truth_rgb": to_uint8_rgb(crop_truth),
            "pred_rgb": to_uint8_rgb(crop_pred),
            "common_mask": crop_mask,
            "row_min": row_min,
            "col_min": col_min,
            "truth_transform": truth_ds.transform,
            "pred_transform": pred_ds.transform,
            "truth_profile": truth_ds.profile.copy(),
            "pred_profile": pred_ds.profile.copy(),
        }


@torch.inference_mode()
def match_with_romav2(
    model: RoMaV2,
    truth_path: Path,
    pred_path: Path,
    sample_count: int,
    ransac_threshold_px: float,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    import cv2

    preds = model.match(truth_path, pred_path)
    matches, overlap, _, _ = model.sample(preds, sample_count)

    truth_img = cv2.imread(str(truth_path), cv2.IMREAD_UNCHANGED)
    pred_img = cv2.imread(str(pred_path), cv2.IMREAD_UNCHANGED)
    if truth_img is None or pred_img is None:
        raise FileNotFoundError(f"Failed to read pair: {truth_path} / {pred_path}")

    truth_h, truth_w = truth_img.shape[:2]
    pred_h, pred_w = pred_img.shape[:2]
    kpts_truth, kpts_pred = model.to_pixel_coordinates(matches, truth_h, truth_w, pred_h, pred_w)
    truth_np = kpts_truth.detach().cpu().numpy().astype(np.float32)
    pred_np = kpts_pred.detach().cpu().numpy().astype(np.float32)
    overlap_np = overlap.detach().cpu().numpy().astype(np.float32)

    if len(truth_np) < 4:
        return [], {
            "match_count": int(len(truth_np)),
            "inlier_count": 0,
            "inlier_ratio": 0.0,
            "geom_valid": False,
            "romav2_match_score": float(overlap_np.mean()) if len(overlap_np) else 0.0,
            "status": "insufficient_matches",
        }

    rows: list[dict[str, object]] = []
    for idx, (truth_pt, pred_pt) in enumerate(zip(truth_np, pred_np), start=1):
        rows.append(
            {
                "row_id": idx,
                "truth_x": f"{float(truth_pt[0]):.6f}",
                "truth_y": f"{float(truth_pt[1]):.6f}",
                "pred_x": f"{float(pred_pt[0]):.6f}",
                "pred_y": f"{float(pred_pt[1]):.6f}",
                "match_score": f"{float(overlap_np[idx - 1]):.6f}",
            }
        )

    homography, mask = cv2.findHomography(
        truth_np,
        pred_np,
        method=cv2.USAC_MAGSAC,
        ransacReprojThreshold=ransac_threshold_px,
        confidence=0.999999,
        maxIters=10000,
    )
    if homography is None or mask is None:
        inlier_mask = np.zeros((len(rows),), dtype=bool)
    else:
        inlier_mask = mask.ravel().astype(bool)

    inlier_count = int(inlier_mask.sum())
    inlier_ratio = float(inlier_count / len(rows)) if rows else 0.0
    summary = {
        "match_count": len(rows),
        "inlier_count": inlier_count,
        "inlier_ratio": inlier_ratio,
        "geom_valid": bool(homography is not None and inlier_count > 0),
        "romav2_match_score": float(overlap_np.mean()) if len(overlap_np) else 0.0,
        "status": "ok",
        "inlier_mask": inlier_mask,
    }
    return rows, summary


def evaluate_one(
    truth_path: Path,
    pred_path: Path,
    min_inliers: int,
    sample_count: int,
    ransac_threshold_px: float,
    model: RoMaV2,
    scratch_root: Path,
) -> tuple[str, str, dict[str, float | int], list[dict[str, object]]]:
    status, detail, prepared = prepare_pair(truth_path, pred_path)
    if status != "ok":
        return status, detail, {}, []

    truth_rgb = prepared["truth_rgb"]
    pred_rgb = prepared["pred_rgb"]
    common_mask = prepared["common_mask"]
    row_min = int(prepared["row_min"])
    col_min = int(prepared["col_min"])
    truth_transform = prepared["truth_transform"]
    pred_transform = prepared["pred_transform"]
    truth_profile = prepared["truth_profile"]
    pred_profile = prepared["pred_profile"]

    with tempfile.TemporaryDirectory(prefix="roma_tie_", dir=str(scratch_root)) as tmpdir:
        tmp_root = Path(tmpdir)
        truth_temp = tmp_root / "truth_crop.tif"
        pred_temp = tmp_root / "pred_crop.tif"
        save_temp_geotiff(truth_temp, truth_rgb, truth_profile)
        save_temp_geotiff(pred_temp, pred_rgb, pred_profile)

        try:
            match_rows, summary = match_with_romav2(
                model=model,
                truth_path=truth_temp,
                pred_path=pred_temp,
                sample_count=sample_count,
                ransac_threshold_px=ransac_threshold_px,
            )
        except Exception as exc:
            return "matcher_failed", f"RoMa v2 matching failed: {exc}", {}, []

    if not match_rows:
        if summary.get("status") == "insufficient_matches":
            return "no_tiepoints_found", "RoMa v2 produced fewer than 4 tentative matches", {}, []
        return "no_tiepoints_found", "RoMa v2 produced no tentative matches", {}, []

    truth_cols: list[float] = []
    truth_rows: list[float] = []
    pred_cols: list[float] = []
    pred_rows: list[float] = []
    keep_indices: list[int] = []
    height, width = common_mask.shape

    for idx, row in enumerate(match_rows):
        truth_col_local = float(row["truth_x"])
        truth_row_local = float(row["truth_y"])
        pred_col_local = float(row["pred_x"])
        pred_row_local = float(row["pred_y"])

        truth_col_i = int(math.floor(truth_col_local))
        truth_row_i = int(math.floor(truth_row_local))
        pred_col_i = int(math.floor(pred_col_local))
        pred_row_i = int(math.floor(pred_row_local))
        if (
            truth_col_i < 0
            or truth_row_i < 0
            or pred_col_i < 0
            or pred_row_i < 0
            or truth_col_i >= width
            or pred_col_i >= width
            or truth_row_i >= height
            or pred_row_i >= height
        ):
            continue
        if not common_mask[truth_row_i, truth_col_i] or not common_mask[pred_row_i, pred_col_i]:
            continue

        truth_col = truth_col_local + col_min
        truth_row = truth_row_local + row_min
        pred_col = pred_col_local + col_min
        pred_row = pred_row_local + row_min
        keep_indices.append(idx)
        truth_cols.append(truth_col)
        truth_rows.append(truth_row)
        pred_cols.append(pred_col)
        pred_rows.append(pred_row)

    if len(keep_indices) < 4:
        return "no_tiepoints_found", "RoMa v2 matches did not survive the common-valid-mask filter", {}, []

    truth_cols_np = np.asarray(truth_cols, dtype=np.float64)
    truth_rows_np = np.asarray(truth_rows, dtype=np.float64)
    pred_cols_np = np.asarray(pred_cols, dtype=np.float64)
    pred_rows_np = np.asarray(pred_rows, dtype=np.float64)

    import cv2

    truth_pts = np.float32(np.column_stack([truth_cols_np - col_min, truth_rows_np - row_min])).reshape(-1, 1, 2)
    pred_pts = np.float32(np.column_stack([pred_cols_np - col_min, pred_rows_np - row_min])).reshape(-1, 1, 2)
    _, inlier_mask = cv2.findHomography(truth_pts, pred_pts, cv2.RANSAC, ransac_threshold_px)
    if inlier_mask is None or int(np.count_nonzero(inlier_mask)) <= 0:
        return "ransac_rejected_all", "RANSAC rejected all tentative RoMa tie-points", {
            "tiepoint_match_count": len(keep_indices),
            "tiepoint_inlier_count": 0,
            "tiepoint_inlier_ratio": 0.0,
        }, []

    inlier_flat = inlier_mask.ravel().astype(bool)
    inlier_count = int(np.count_nonzero(inlier_flat))
    inlier_ratio = float(inlier_count / len(keep_indices))
    if inlier_count < min_inliers:
        return "too_few_tiepoints", f"RANSAC retained {inlier_count} inliers, below min_inliers={min_inliers}", {
            "tiepoint_match_count": len(keep_indices),
            "tiepoint_inlier_count": inlier_count,
            "tiepoint_inlier_ratio": inlier_ratio,
        }, []

    truth_x_m, truth_y_m = compute_ground_xy(truth_transform, truth_cols_np, truth_rows_np)
    pred_x_m, pred_y_m = compute_ground_xy(pred_transform, pred_cols_np, pred_rows_np)
    dx = pred_x_m - truth_x_m
    dy = pred_y_m - truth_y_m
    dxy = np.hypot(dx, dy)

    detail_rows: list[dict[str, object]] = []
    inlier_detail_indices = np.flatnonzero(inlier_flat)
    for out_idx, src_idx in enumerate(inlier_detail_indices):
        detail_rows.append(
            {
                "query_id": "",
                "match_index": out_idx,
                "truth_col_px": f"{truth_cols_np[src_idx]:.6f}",
                "truth_row_px": f"{truth_rows_np[src_idx]:.6f}",
                "pred_col_px": f"{pred_cols_np[src_idx]:.6f}",
                "pred_row_px": f"{pred_rows_np[src_idx]:.6f}",
                "truth_x_m": f"{truth_x_m[src_idx]:.6f}",
                "truth_y_m": f"{truth_y_m[src_idx]:.6f}",
                "pred_x_m": f"{pred_x_m[src_idx]:.6f}",
                "pred_y_m": f"{pred_y_m[src_idx]:.6f}",
                "dx_m": f"{dx[src_idx]:.6f}",
                "dy_m": f"{dy[src_idx]:.6f}",
                "dxy_m": f"{dxy[src_idx]:.6f}",
            }
        )

    xy_stats = summarize_numeric_extended(dxy[inlier_flat].tolist())
    metrics = {
        "tiepoint_match_count": len(keep_indices),
        "tiepoint_inlier_count": inlier_count,
        "tiepoint_inlier_ratio": inlier_ratio,
        "tiepoint_xy_error_mean_m": xy_stats["mean"],
        "tiepoint_xy_error_median_m": xy_stats["median"],
        "tiepoint_xy_error_rmse_m": xy_stats["rmse"],
        "tiepoint_xy_error_p90_m": xy_stats["p90"],
        "tiepoint_xy_error_max_m": xy_stats["max"],
        "tiepoint_dx_mean_m": float(np.mean(dx[inlier_flat])),
        "tiepoint_dy_mean_m": float(np.mean(dy[inlier_flat])),
    }
    return "tiepoint_eval_ok", "", metrics, detail_rows


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    suite_root = resolve_runtime_path(args.output_root) if args.output_root else resolve_output_root(bundle_root, None, DEFAULT_SUITE_DIRNAME)
    ortho_root = resolve_runtime_path(args.ortho_output_root) if args.ortho_output_root else suite_root
    ortho_accuracy_csv = (
        Path(args.ortho_accuracy_csv)
        if args.ortho_accuracy_csv
        else ortho_root / "ortho_alignment_satellite" / "per_query_ortho_accuracy.csv"
    )
    rows = load_csv(resolve_runtime_path(ortho_accuracy_csv))
    selected_query_ids = set(args.query_id)
    if selected_query_ids:
        rows = [row for row in rows if row["query_id"] in selected_query_ids]

    tiepoint_root = suite_root / "tiepoint_ground_error"
    per_query_match_root = tiepoint_root / "tiepoints" / "per_query_matches"
    scratch_root = tiepoint_root / "_roma_scratch"
    ensure_dir(per_query_match_root)
    ensure_dir(scratch_root)

    model = build_model(args.setting, args.device)

    result_rows: list[dict[str, object]] = []
    failure_rows: list[dict[str, object]] = []
    per_flight_rows_map: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    status_counts: Counter[str] = Counter()
    matchable_query_count = 0
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
                sample_count=args.sample_count,
                ransac_threshold_px=args.ransac_threshold_px,
                model=model,
                scratch_root=scratch_root,
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
            pooled_dxy = [float(detail_row["dxy_m"]) for detail_row in detail_rows]
            pooled_dxy_all.extend(pooled_dxy)
            pooled_dxy_by_flight[str(base_row["flight_id"])].extend(pooled_dxy)
            write_csv(per_query_match_root / f"{query_id}_tiepoints.csv", detail_rows)

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
        if base_row["flight_id"]:
            per_flight_rows_map[str(base_row["flight_id"])].append(base_row)

    write_csv(tiepoint_root / "per_query_tiepoint_ground_error.csv", result_rows)
    write_csv(tiepoint_root / "tiepoint_failure_buckets.csv", failure_rows)

    overall_summary = {
        "bundle_root": str(bundle_root),
        "ortho_accuracy_csv": str(resolve_runtime_path(ortho_accuracy_csv)),
        "matchable_query_count": matchable_query_count,
        "status_counts": dict(status_counts),
        "tiepoint_xy_error_mean_m": summarize_numeric_extended(pooled_dxy_all)["mean"],
        "tiepoint_xy_error_median_m": summarize_numeric_extended(pooled_dxy_all)["median"],
        "tiepoint_xy_error_rmse_m": summarize_numeric_extended(pooled_dxy_all)["rmse"],
        "tiepoint_xy_error_p90_m": summarize_numeric_extended(pooled_dxy_all)["p90"],
        "tiepoint_xy_error_max_m": summarize_numeric_extended(pooled_dxy_all)["max"],
        "tiepoint_match_count_mean": summarize_numeric_extended(
            [float(row["tiepoint_match_count"]) for row in result_rows if row["eval_status"] == "tiepoint_eval_ok" and row["tiepoint_match_count"] != ""]
        )["mean"],
        "tiepoint_inlier_ratio_mean": summarize_numeric_extended(
            [float(row["tiepoint_inlier_ratio"]) for row in result_rows if row["eval_status"] == "tiepoint_eval_ok" and row["tiepoint_inlier_ratio"] != ""]
        )["mean"],
        "generated_at_unix": time.time(),
    }
    write_json(tiepoint_root / "overall_tiepoint_ground_error.json", overall_summary)

    per_flight_rows = []
    for flight_id in sorted(per_flight_rows_map):
        rows_for_flight = per_flight_rows_map[flight_id]
        ok_rows = [row for row in rows_for_flight if row["eval_status"] == "tiepoint_eval_ok"]
        pooled = pooled_dxy_by_flight.get(flight_id, [])
        per_flight_rows.append(
            {
                "flight_id": flight_id,
                "short_flight_id": flight_id.split("_")[2] if len(flight_id.split("_")) >= 3 else flight_id,
                "query_count": len(rows_for_flight),
                "ok_count": len(ok_rows),
                "tiepoint_xy_error_mean_m": summarize_numeric_extended(pooled)["mean"],
                "tiepoint_xy_error_median_m": summarize_numeric_extended(pooled)["median"],
                "tiepoint_xy_error_rmse_m": summarize_numeric_extended(pooled)["rmse"],
                "tiepoint_xy_error_p90_m": summarize_numeric_extended(pooled)["p90"],
                "tiepoint_match_count_mean": summarize_numeric_extended(
                    [float(row["tiepoint_match_count"]) for row in ok_rows if row["tiepoint_match_count"] != ""]
                )["mean"],
                "tiepoint_inlier_ratio_mean": summarize_numeric_extended(
                    [float(row["tiepoint_inlier_ratio"]) for row in ok_rows if row["tiepoint_inlier_ratio"] != ""]
                )["mean"],
            }
        )
    write_csv(tiepoint_root / "per_flight_tiepoint_ground_error.csv", per_flight_rows)

    print(tiepoint_root / "overall_tiepoint_ground_error.json")


if __name__ == "__main__":
    main()

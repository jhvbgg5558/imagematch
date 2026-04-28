#!/usr/bin/env python3
"""Render tie-point overlays and error heatmaps for orthophoto ground error.

Purpose:
- visualize matched tie-points used in the local ground-error evaluation;
- show both point distribution and per-point XY error magnitude for each query;
- keep visualization outputs tied to the stable `truth vs pred` evaluation chain.

Main inputs:
- `<output_root>/per_query_tiepoint_ground_error.csv`;
- `<output_root>/tiepoints/per_query_matches/*.csv`;
- truth orthophoto tiles and predicted orthophoto tiles.

Main outputs:
- `<output_root>/viz_tiepoints/<query_id>_tiepoints_overlay.png`;
- `<output_root>/viz_tiepoints/<query_id>_tiepoints_error_heatmap.png`;
- `<output_root>/viz_tiepoints/_summary.json`.

Applicable task constraints:
- visualize only tie-points derived from `truth vs pred`;
- keep upstream failures explicit instead of silently skipping them.
"""

from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

import numpy as np

from pose_ortho_truth_utils import (
    DEFAULT_FORMAL_BUNDLE_ROOT,
    ensure_dir,
    grayscale_from_image,
    load_csv,
    resolve_output_root,
    resolve_runtime_path,
    write_csv,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_FORMAL_BUNDLE_ROOT))
    parser.add_argument("--tiepoint-csv", default=None)
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--output-root", default=None)
    return parser.parse_args()


def save_png(path: Path, rgb: np.ndarray) -> None:
    import cv2

    ensure_dir(path.parent)
    ok, encoded = cv2.imencode(".png", rgb[:, :, ::-1])
    if not ok:
        raise RuntimeError(f"Failed to encode PNG: {path}")
    encoded.tofile(str(path))


def read_raster(path: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as ds:
        return ds.read()


def to_gray_rgb(data: np.ndarray) -> np.ndarray:
    gray = grayscale_from_image(data)
    gray = np.clip(gray, 0, 255).astype(np.uint8)
    return np.repeat(gray[:, :, None], 3, axis=2)


def error_color(error_m: float, max_error_m: float) -> tuple[int, int, int]:
    ratio = 0.0 if max_error_m <= 0 else min(max(error_m / max_error_m, 0.0), 1.0)
    red = int(255 * ratio)
    green = int(255 * (1.0 - ratio))
    blue = 32
    return blue, green, red


def render_overlay(
    truth_rgb: np.ndarray,
    pred_rgb: np.ndarray,
    match_rows: list[dict[str, str]],
    out_overlay: Path,
    out_heatmap: Path,
) -> None:
    import cv2

    overlay = np.clip(0.55 * truth_rgb.astype(np.float32) + 0.45 * pred_rgb.astype(np.float32), 0, 255).astype(np.uint8)
    heatmap = overlay.copy()
    overlay_bgr = overlay[:, :, ::-1].copy()
    heatmap_bgr = heatmap[:, :, ::-1].copy()
    max_error_m = max((float(row["dxy_m"]) for row in match_rows), default=1.0)
    for row in match_rows:
        truth_pt = (int(round(float(row["truth_col_px"]))), int(round(float(row["truth_row_px"]))))
        pred_pt = (int(round(float(row["pred_col_px"]))), int(round(float(row["pred_row_px"]))))
        error_m = float(row["dxy_m"])
        cv2.line(overlay_bgr, truth_pt, pred_pt, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.circle(overlay_bgr, truth_pt, 3, (0, 255, 0), -1, cv2.LINE_AA)
        cv2.circle(overlay_bgr, pred_pt, 3, (255, 0, 0), -1, cv2.LINE_AA)
        color = error_color(error_m, max_error_m)
        cv2.circle(heatmap_bgr, truth_pt, 4, color, -1, cv2.LINE_AA)

    save_png(out_overlay, overlay_bgr[:, :, ::-1])
    save_png(out_heatmap, heatmap_bgr[:, :, ::-1])


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    eval_root = resolve_output_root(bundle_root, args.output_root)
    tiepoint_csv = Path(args.tiepoint_csv) if args.tiepoint_csv else eval_root / "per_query_tiepoint_ground_error.csv"
    rows = load_csv(resolve_runtime_path(tiepoint_csv))
    selected_query_ids = set(args.query_id)
    if selected_query_ids:
        rows = [row for row in rows if row["query_id"] in selected_query_ids]

    out_root = eval_root / "viz_tiepoints"
    ensure_dir(out_root)
    status_counts: Counter[str] = Counter()
    failure_rows: list[dict[str, object]] = []

    for row in rows:
        query_id = row["query_id"]
        status = row.get("eval_status", "")
        if status != "tiepoint_eval_ok":
            status_counts[status or "missing_status"] += 1
            failure_rows.append(
                {
                    "query_id": query_id,
                    "flight_id": row.get("flight_id", ""),
                    "best_candidate_id": row.get("best_candidate_id", ""),
                    "failure_bucket": status or "missing_status",
                    "detail": row.get("eval_status_detail", ""),
                }
            )
            continue

        overlay_path = out_root / f"{query_id}_tiepoints_overlay.png"
        heatmap_path = out_root / f"{query_id}_tiepoints_error_heatmap.png"
        if overlay_path.exists() and heatmap_path.exists() and not args.overwrite:
            status_counts["exists"] += 1
            continue

        match_csv = eval_root / "tiepoints" / "per_query_matches" / f"{query_id}_tiepoints.csv"
        if not match_csv.exists():
            status_counts["missing_tiepoint_details"] += 1
            failure_rows.append(
                {
                    "query_id": query_id,
                    "flight_id": row.get("flight_id", ""),
                    "best_candidate_id": row.get("best_candidate_id", ""),
                    "failure_bucket": "missing_tiepoint_details",
                    "detail": f"missing detail CSV: {match_csv}",
                }
            )
            continue

        truth_path = resolve_runtime_path(row["truth_crop_path"])
        pred_path = resolve_runtime_path(row["pred_crop_path"])
        if not truth_path.exists() or not pred_path.exists():
            status_counts["missing_raster_inputs"] += 1
            failure_rows.append(
                {
                    "query_id": query_id,
                    "flight_id": row.get("flight_id", ""),
                    "best_candidate_id": row.get("best_candidate_id", ""),
                    "failure_bucket": "missing_raster_inputs",
                    "detail": f"truth_exists={truth_path.exists()}, pred_exists={pred_path.exists()}",
                }
            )
            continue

        match_rows = load_csv(match_csv)
        if not match_rows:
            status_counts["missing_tiepoint_details"] += 1
            failure_rows.append(
                {
                    "query_id": query_id,
                    "flight_id": row.get("flight_id", ""),
                    "best_candidate_id": row.get("best_candidate_id", ""),
                    "failure_bucket": "missing_tiepoint_details",
                    "detail": f"empty detail CSV: {match_csv}",
                }
            )
            continue

        truth_rgb = to_gray_rgb(read_raster(truth_path))
        pred_rgb = to_gray_rgb(read_raster(pred_path))
        render_overlay(truth_rgb, pred_rgb, match_rows, overlay_path, heatmap_path)
        status_counts["ok"] += 1

    write_json(
        out_root / "_summary.json",
        {
            "bundle_root": str(bundle_root),
            "tiepoint_csv": str(resolve_runtime_path(tiepoint_csv)),
            "row_count": len(rows),
            "status_counts": dict(status_counts),
            "generated_at_unix": time.time(),
        },
    )
    write_csv(
        out_root / "_failure_rows.csv",
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
    print(out_root / "_summary.json")


if __name__ == "__main__":
    main()

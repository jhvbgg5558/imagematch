#!/usr/bin/env python3
"""Evaluate geometry diagnostics for the satellite-truth validation suite.

Purpose:
- provide a geometry-oriented diagnostic layer when the truth source is a
  satellite GeoTIFF crop rather than a camera-pose reference;
- check whether the best pose center lies inside the satellite truth crop and
  how far it is from the crop center;
- keep the diagnostics separate from runtime retrieval and from the
  orthophoto-alignment / tie-point metrics.

Main inputs:
- `summary/per_query_best_pose.csv`;
- `<output_root>/satellite_truth/query_satellite_truth_manifest.csv`.

Main outputs:
- `<output_root>/pose_vs_satellite_truth_geometry/per_query_pose_vs_satellite_truth_geometry.csv`;
- `<output_root>/pose_vs_satellite_truth_geometry/overall_satellite_truth_geometry.json`;
- `<output_root>/pose_vs_satellite_truth_geometry/failure_buckets.csv`.

Applicable task constraints:
- satellite truth must not be treated as a direct pose reference;
- fixed tiles are selection anchors only, not the final truth;
- geometry diagnostics must stay offline and query-specific.
"""

from __future__ import annotations

import argparse
import math
import time
from collections import Counter
from pathlib import Path

from pose_ortho_truth_utils import DEFAULT_FORMAL_BUNDLE_ROOT, load_csv, resolve_runtime_path, write_csv, write_json
from satellite_truth_utils import DEFAULT_BUNDLE_ROOT, resolve_satellite_suite_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--best-pose-csv", default=None)
    parser.add_argument("--truth-manifest-csv", default=None)
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--output-root", default=None)
    return parser.parse_args()


def to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    suite_root = resolve_satellite_suite_root(bundle_root, args.output_root)
    geom_root = suite_root / "pose_vs_satellite_truth_geometry"
    best_pose_csv = Path(args.best_pose_csv) if args.best_pose_csv else bundle_root / "summary" / "per_query_best_pose.csv"
    truth_manifest_csv = (
        Path(args.truth_manifest_csv)
        if args.truth_manifest_csv
        else suite_root / "satellite_truth" / "query_satellite_truth_manifest.csv"
    )

    best_rows = load_csv(resolve_runtime_path(best_pose_csv))
    truth_rows = load_csv(resolve_runtime_path(truth_manifest_csv))
    selected_query_ids = set(args.query_id)

    best_by_query = {row["query_id"]: row for row in best_rows if not selected_query_ids or row["query_id"] in selected_query_ids}
    truth_by_query = {row["query_id"]: row for row in truth_rows if not selected_query_ids or row["query_id"] in selected_query_ids}

    result_rows: list[dict[str, object]] = []
    failure_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()

    for query_id in sorted(set(best_by_query) | set(truth_by_query)):
        best_row = best_by_query.get(query_id)
        truth_row = truth_by_query.get(query_id)
        base_row: dict[str, object] = {
            "query_id": query_id,
            "flight_id": "",
            "best_candidate_id": "",
            "selected_truth_tile_id": "",
            "truth_source_type": "",
            "truth_source_tif": "",
            "truth_crop_path": "",
            "truth_crop_center_x": "",
            "truth_crop_center_y": "",
            "truth_crop_bbox_area_m2": "",
            "best_camera_center_x": "",
            "best_camera_center_y": "",
            "best_camera_center_z": "",
            "camera_center_inside_truth_bbox": "",
            "camera_center_offset_m": "",
            "best_candidate_is_selected_truth_tile": "",
            "selected_truth_tile_coverage_ratio": "",
            "selected_truth_tile_valid_pixel_ratio": "",
            "selected_truth_tile_black_pixel_ratio": "",
            "eval_status": "",
            "eval_status_detail": "",
        }
        if best_row is not None:
            base_row["flight_id"] = best_row.get("flight_id", "")
            base_row["best_candidate_id"] = best_row.get("best_candidate_id", "")
            base_row["best_camera_center_x"] = best_row.get("best_camera_center_x", "")
            base_row["best_camera_center_y"] = best_row.get("best_camera_center_y", "")
            base_row["best_camera_center_z"] = best_row.get("best_camera_center_z", "")
        if truth_row is not None:
            base_row["selected_truth_tile_id"] = truth_row.get("truth_source_tile_id", "")
            base_row["truth_source_type"] = truth_row.get("truth_source_type", "")
            base_row["truth_source_tif"] = truth_row.get("truth_source_tif", "")
            base_row["truth_crop_path"] = truth_row.get("truth_crop_path", "")
            base_row["selected_truth_tile_coverage_ratio"] = truth_row.get("truth_source_coverage_ratio", "")
            base_row["selected_truth_tile_valid_pixel_ratio"] = truth_row.get("truth_source_valid_pixel_ratio", "")
            base_row["selected_truth_tile_black_pixel_ratio"] = truth_row.get("truth_source_black_pixel_ratio", "")

        if best_row is None:
            status = "missing_best_pose"
            detail = "query missing from best-pose summary"
        elif truth_row is None:
            status = "missing_truth_manifest"
            detail = "query missing from satellite truth manifest"
        else:
            crop_min_x = to_float(truth_row.get("crop_min_x"))
            crop_min_y = to_float(truth_row.get("crop_min_y"))
            crop_max_x = to_float(truth_row.get("crop_max_x"))
            crop_max_y = to_float(truth_row.get("crop_max_y"))
            cam_x = to_float(best_row.get("best_camera_center_x"))
            cam_y = to_float(best_row.get("best_camera_center_y"))
            if None in {crop_min_x, crop_min_y, crop_max_x, crop_max_y, cam_x, cam_y}:
                status = "missing_geometry_values"
                detail = "one or more geometry values are missing"
            else:
                center_x = 0.5 * (crop_min_x + crop_max_x)
                center_y = 0.5 * (crop_min_y + crop_max_y)
                inside = crop_min_x <= cam_x <= crop_max_x and crop_min_y <= cam_y <= crop_max_y
                base_row["truth_crop_center_x"] = f"{center_x:.6f}"
                base_row["truth_crop_center_y"] = f"{center_y:.6f}"
                base_row["truth_crop_bbox_area_m2"] = f"{max(crop_max_x - crop_min_x, 0.0) * max(crop_max_y - crop_min_y, 0.0):.6f}"
                base_row["camera_center_inside_truth_bbox"] = "1" if inside else "0"
                base_row["camera_center_offset_m"] = f"{math.hypot(cam_x - center_x, cam_y - center_y):.6f}"
                base_row["best_candidate_is_selected_truth_tile"] = "1" if best_row.get("best_candidate_id", "") == truth_row.get("truth_source_tile_id", "") else "0"
                status = "ok"
                detail = ""

        base_row["eval_status"] = status
        base_row["eval_status_detail"] = detail
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

    write_csv(geom_root / "per_query_pose_vs_satellite_truth_geometry.csv", result_rows)
    write_csv(geom_root / "failure_buckets.csv", failure_rows)
    write_json(
        geom_root / "overall_satellite_truth_geometry.json",
        {
            "bundle_root": str(bundle_root),
            "truth_manifest_csv": str(resolve_runtime_path(truth_manifest_csv)),
            "status_counts": dict(status_counts),
            "generated_at_unix": time.time(),
        },
    )
    print(geom_root / "overall_satellite_truth_geometry.json")


if __name__ == "__main__":
    main()

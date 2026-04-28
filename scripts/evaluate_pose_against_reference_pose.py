#!/usr/bin/env python3
"""Compare formal best-pose results against reference AT poses.

Purpose:
- compute per-query position and orientation deltas between the formal best
  pose and a reference pose derived from the local UAV air-triangulation
  products;
- keep pose-vs-AT evaluation separate from orthophoto overlap validation;
- emit explicit failure rows whenever best pose or reference pose inputs are
  missing or incomplete.

Main inputs:
- `summary/per_query_best_pose.csv`;
- `<output_root>/query_reference_pose_manifest.csv`.

Main outputs:
- `<output_root>/per_query_pose_vs_at.csv`;
- `<output_root>/overall_pose_vs_at.json`;
- `<output_root>/per_flight_pose_vs_at.csv`;
- `<output_root>/pose_vs_at_failure_buckets.csv`.

Applicable task constraints:
- compare only the per-query best pose, not all candidates;
- interpret the result as relative offset to the air-triangulation reference,
  not as an absolute truth guarantee.
"""

from __future__ import annotations

import argparse
import math
import time
from collections import Counter, defaultdict
from pathlib import Path

from pose_ortho_truth_utils import (
    DEFAULT_FORMAL_BUNDLE_ROOT,
    DEFAULT_VALIDATION_SUITE_DIRNAME,
    angle_diff_deg,
    load_csv,
    orientation_from_world_to_camera_rvec,
    parse_float_list,
    resolve_runtime_path,
    summarize_numeric,
    view_dir_angle_error_deg,
    write_csv,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_FORMAL_BUNDLE_ROOT))
    parser.add_argument("--best-pose-csv", default=None)
    parser.add_argument("--reference-pose-csv", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--query-id", action="append", default=[])
    return parser.parse_args()


def resolve_pose_eval_root(bundle_root: Path, output_root: str | None) -> Path:
    if output_root:
        return resolve_runtime_path(output_root)
    return bundle_root / DEFAULT_VALIDATION_SUITE_DIRNAME / "pose_vs_at"


def parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    out_root = resolve_pose_eval_root(bundle_root, args.output_root)
    best_pose_csv = Path(args.best_pose_csv) if args.best_pose_csv else bundle_root / "summary" / "per_query_best_pose.csv"
    reference_pose_csv = (
        Path(args.reference_pose_csv)
        if args.reference_pose_csv
        else out_root / "query_reference_pose_manifest.csv"
    )

    best_rows = load_csv(resolve_runtime_path(best_pose_csv))
    reference_rows = load_csv(resolve_runtime_path(reference_pose_csv))
    selected_query_ids = set(args.query_id)

    best_by_query = {
        row["query_id"]: row
        for row in best_rows
        if not selected_query_ids or row["query_id"] in selected_query_ids
    }
    reference_by_query = {
        row["query_id"]: row
        for row in reference_rows
        if not selected_query_ids or row["query_id"] in selected_query_ids
    }

    result_rows: list[dict[str, object]] = []
    failure_rows: list[dict[str, object]] = []
    per_flight_rows_map: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    status_counts: Counter[str] = Counter()

    for query_id in sorted(set(best_by_query) | set(reference_by_query)):
        best_row = best_by_query.get(query_id)
        reference_row = reference_by_query.get(query_id)
        base_row: dict[str, object] = {
            "query_id": query_id,
            "flight_id": "",
            "best_candidate_id": "",
            "reference_pose_source": "",
            "best_camera_center_x": "",
            "best_camera_center_y": "",
            "best_camera_center_z": "",
            "reference_camera_center_x": "",
            "reference_camera_center_y": "",
            "reference_camera_center_z": "",
            "dx_m": "",
            "dy_m": "",
            "dz_m": "",
            "horizontal_error_m": "",
            "spatial_error_m": "",
            "best_yaw_deg": "",
            "best_pitch_deg": "",
            "best_roll_deg": "",
            "reference_yaw_deg": "",
            "reference_pitch_deg": "",
            "reference_roll_deg": "",
            "yaw_error_deg": "",
            "pitch_error_deg": "",
            "roll_error_deg": "",
            "view_dir_angle_error_deg": "",
            "best_score": "",
            "eval_status": "",
            "eval_status_detail": "",
        }

        if best_row is not None:
            base_row["flight_id"] = best_row.get("flight_id", "")
            base_row["best_candidate_id"] = best_row.get("best_candidate_id", "")
            base_row["best_camera_center_x"] = best_row.get("best_camera_center_x", "")
            base_row["best_camera_center_y"] = best_row.get("best_camera_center_y", "")
            base_row["best_camera_center_z"] = best_row.get("best_camera_center_z", "")
            base_row["best_score"] = best_row.get("best_score", "")
        if reference_row is not None:
            if not base_row["flight_id"]:
                base_row["flight_id"] = reference_row.get("flight_id", "")
            base_row["reference_pose_source"] = reference_row.get("reference_pose_source", "")
            base_row["reference_camera_center_x"] = reference_row.get("reference_camera_center_x", "")
            base_row["reference_camera_center_y"] = reference_row.get("reference_camera_center_y", "")
            base_row["reference_camera_center_z"] = reference_row.get("reference_camera_center_z", "")
            base_row["reference_yaw_deg"] = reference_row.get("reference_yaw_deg", "")
            base_row["reference_pitch_deg"] = reference_row.get("reference_pitch_deg", "")
            base_row["reference_roll_deg"] = reference_row.get("reference_roll_deg", "")

        if best_row is None:
            status = "missing_best_pose"
            detail = "query missing from per_query_best_pose.csv"
        elif best_row.get("best_status") != "ok":
            status = "best_pose_not_ok"
            detail = f"best_status={best_row.get('best_status', '')}"
        elif reference_row is None:
            status = "missing_reference_pose_manifest"
            detail = "query missing from query_reference_pose_manifest.csv"
        elif reference_row.get("status") != "ready":
            status = reference_row.get("status", "reference_pose_not_ready")
            detail = reference_row.get("status_detail", "reference pose manifest row is not ready")
        else:
            status = "ok"
            detail = ""
            best_x = parse_float(best_row.get("best_camera_center_x"))
            best_y = parse_float(best_row.get("best_camera_center_y"))
            best_z = parse_float(best_row.get("best_camera_center_z"))
            ref_x = parse_float(reference_row.get("reference_camera_center_x"))
            ref_y = parse_float(reference_row.get("reference_camera_center_y"))
            ref_z = parse_float(reference_row.get("reference_camera_center_z"))
            if None in {best_x, best_y, best_z, ref_x, ref_y, ref_z}:
                status = "missing_position_values"
                detail = "best pose or reference pose is missing camera-center values"
            else:
                dx_m = float(best_x - ref_x)
                dy_m = float(best_y - ref_y)
                dz_m = float(best_z - ref_z)
                base_row["dx_m"] = f"{dx_m:.6f}"
                base_row["dy_m"] = f"{dy_m:.6f}"
                base_row["dz_m"] = f"{dz_m:.6f}"
                base_row["horizontal_error_m"] = f"{math.hypot(dx_m, dy_m):.6f}"
                base_row["spatial_error_m"] = f"{math.sqrt(dx_m * dx_m + dy_m * dy_m + dz_m * dz_m):.6f}"

                try:
                    best_orientation = orientation_from_world_to_camera_rvec(parse_float_list(best_row["best_rvec"]))
                except Exception as exc:
                    best_orientation = None
                    status = "missing_best_orientation"
                    detail = str(exc)
                if best_orientation is not None:
                    base_row["best_yaw_deg"] = f"{best_orientation['yaw_deg']:.6f}"
                    base_row["best_pitch_deg"] = f"{best_orientation['pitch_deg']:.6f}"
                    base_row["best_roll_deg"] = f"{best_orientation['roll_deg']:.6f}"
                    reference_view = [
                        parse_float(reference_row.get("reference_view_dir_x")),
                        parse_float(reference_row.get("reference_view_dir_y")),
                        parse_float(reference_row.get("reference_view_dir_z")),
                    ]
                    if None not in reference_view:
                        angle_error = view_dir_angle_error_deg(
                            [
                                best_orientation["view_dir_x"],
                                best_orientation["view_dir_y"],
                                best_orientation["view_dir_z"],
                            ],
                            reference_view,
                        )
                        if angle_error is not None:
                            base_row["view_dir_angle_error_deg"] = f"{angle_error:.6f}"
                    ref_yaw = parse_float(reference_row.get("reference_yaw_deg"))
                    ref_pitch = parse_float(reference_row.get("reference_pitch_deg"))
                    ref_roll = parse_float(reference_row.get("reference_roll_deg"))
                    if ref_yaw is not None:
                        base_row["yaw_error_deg"] = f"{angle_diff_deg(best_orientation['yaw_deg'], ref_yaw):.6f}"
                    if ref_pitch is not None:
                        base_row["pitch_error_deg"] = f"{angle_diff_deg(best_orientation['pitch_deg'], ref_pitch):.6f}"
                    if ref_roll is not None:
                        base_row["roll_error_deg"] = f"{angle_diff_deg(best_orientation['roll_deg'], ref_roll):.6f}"

        base_row["eval_status"] = status
        base_row["eval_status_detail"] = detail
        result_rows.append(base_row)
        status_counts[status] += 1
        if status != "ok":
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

    ok_rows = [row for row in result_rows if row["eval_status"] == "ok"]
    overall_payload = {
        "query_count": len(result_rows),
        "evaluated_query_count": len(ok_rows),
        "horizontal_error_m": summarize_numeric(
            [float(row["horizontal_error_m"]) for row in ok_rows if row["horizontal_error_m"] != ""]
        ),
        "spatial_error_m": summarize_numeric(
            [float(row["spatial_error_m"]) for row in ok_rows if row["spatial_error_m"] != ""]
        ),
        "view_dir_angle_error_deg": summarize_numeric(
            [float(row["view_dir_angle_error_deg"]) for row in ok_rows if row["view_dir_angle_error_deg"] != ""]
        ),
        "yaw_error_deg": summarize_numeric(
            [float(row["yaw_error_deg"]) for row in ok_rows if row["yaw_error_deg"] != ""]
        ),
        "pitch_error_deg": summarize_numeric(
            [float(row["pitch_error_deg"]) for row in ok_rows if row["pitch_error_deg"] != ""]
        ),
        "roll_error_deg": summarize_numeric(
            [float(row["roll_error_deg"]) for row in ok_rows if row["roll_error_deg"] != ""]
        ),
        "eval_status_counts": dict(status_counts),
        "generated_at_unix": time.time(),
    }

    per_flight_rows: list[dict[str, object]] = []
    for flight_id, rows in sorted(per_flight_rows_map.items()):
        per_flight_rows.append(
            {
                "flight_id": flight_id,
                "query_count": len(rows),
                "horizontal_error_m_mean": summarize_numeric(
                    [float(row["horizontal_error_m"]) for row in rows if row["horizontal_error_m"] != ""]
                )["mean"],
                "spatial_error_m_mean": summarize_numeric(
                    [float(row["spatial_error_m"]) for row in rows if row["spatial_error_m"] != ""]
                )["mean"],
                "view_dir_angle_error_deg_mean": summarize_numeric(
                    [float(row["view_dir_angle_error_deg"]) for row in rows if row["view_dir_angle_error_deg"] != ""]
                )["mean"],
                "yaw_error_deg_mean": summarize_numeric(
                    [float(row["yaw_error_deg"]) for row in rows if row["yaw_error_deg"] != ""]
                )["mean"],
                "pitch_error_deg_mean": summarize_numeric(
                    [float(row["pitch_error_deg"]) for row in rows if row["pitch_error_deg"] != ""]
                )["mean"],
                "roll_error_deg_mean": summarize_numeric(
                    [float(row["roll_error_deg"]) for row in rows if row["roll_error_deg"] != ""]
                )["mean"],
            }
        )

    write_csv(out_root / "per_query_pose_vs_at.csv", result_rows)
    write_json(out_root / "overall_pose_vs_at.json", overall_payload)
    write_csv(
        out_root / "per_flight_pose_vs_at.csv",
        per_flight_rows
        or [
            {
                "flight_id": "",
                "query_count": 0,
                "horizontal_error_m_mean": "",
                "spatial_error_m_mean": "",
                "view_dir_angle_error_deg_mean": "",
                "yaw_error_deg_mean": "",
                "pitch_error_deg_mean": "",
                "roll_error_deg_mean": "",
            }
        ],
    )
    write_csv(
        out_root / "pose_vs_at_failure_buckets.csv",
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
    print(out_root / "overall_pose_vs_at.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build per-query reference pose rows for pose-vs-AT evaluation.

Purpose:
- bind each formal query to a reference camera pose derived from the local UAV
  air-triangulation products when available;
- prefer georeferenced ODM `odm_report/shots.geojson` poses as the formal
  reference and fall back to `query_truth/queries_truth_seed.csv` only when the
  ODM source is missing or incomplete;
- emit a deterministic manifest for downstream position/orientation comparison.

Main inputs:
- `query_truth/queries_truth_seed.csv`;
- local UAV flight workspaces under the raw UAV root.

Main outputs:
- `<output_root>/query_reference_pose_manifest.csv`;
- `<output_root>/query_reference_pose_manifest.json`.

Applicable task constraints:
- runtime pose outputs and offline reference pose assets must remain separate;
- layer-2 is interpreted as relative offset to an AT/ODM reference pose, not as
  an absolute truth guarantee;
- output position/orientation fields are reference-only and do not affect the
  formal pose-solving chain.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from pose_ortho_truth_utils import (
    DEFAULT_FORMAL_BUNDLE_ROOT,
    DEFAULT_QUERY_ROOT,
    DEFAULT_RAW_UAV_ROOT,
    DEFAULT_VALIDATION_SUITE_DIRNAME,
    ensure_dir,
    load_csv,
    normalize_angle_deg,
    orientation_from_world_to_camera_rvec,
    orientation_from_yaw_pitch_roll,
    resolve_runtime_path,
    write_csv,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_FORMAL_BUNDLE_ROOT))
    parser.add_argument(
        "--query-seed-csv",
        default=str(DEFAULT_QUERY_ROOT / "query_truth" / "queries_truth_seed.csv"),
    )
    parser.add_argument("--raw-uav-root", default=str(DEFAULT_RAW_UAV_ROOT))
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


def find_flight_root(raw_uav_root: Path, flight_id: str) -> Path | None:
    if not raw_uav_root.exists():
        return None

    exact = raw_uav_root / flight_id
    if exact.exists():
        return exact

    prefix = "_".join(flight_id.split("_")[:3])
    matches = [path for path in raw_uav_root.iterdir() if path.is_dir() and path.name.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    return None


def load_shots_by_filename(flight_root: Path) -> tuple[dict[str, dict[str, object]], Path | None]:
    shots_path = flight_root / "odm_report" / "shots.geojson"
    if not shots_path.exists():
        return {}, None
    payload = json.loads(shots_path.read_text(encoding="utf-8"))
    mapping: dict[str, dict[str, object]] = {}
    for feature in payload.get("features", []):
        properties = feature.get("properties", {})
        filename = str(properties.get("filename", ""))
        if filename:
            mapping[filename] = feature
    return mapping, shots_path


def build_reference_from_shot(
    shot_feature: dict[str, object],
    query_crs: str,
) -> dict[str, object]:
    properties = shot_feature.get("properties", {})
    geometry = shot_feature.get("geometry", {})
    coordinates = geometry.get("coordinates", ["", "", ""])
    translation = [float(item) for item in properties.get("translation", [])]
    rotation = [float(item) for item in properties.get("rotation", [])]
    orientation = orientation_from_world_to_camera_rvec(rotation)
    return {
        "reference_crs": query_crs,
        "reference_camera_center_x": f"{translation[0]:.6f}",
        "reference_camera_center_y": f"{translation[1]:.6f}",
        "reference_camera_center_z": f"{translation[2]:.6f}",
        "reference_rotation_repr": json.dumps(rotation, ensure_ascii=False),
        "reference_rotation_source": "odm_report_shots_geojson.rotation",
        "reference_yaw_deg": f"{orientation['yaw_deg']:.6f}",
        "reference_pitch_deg": f"{orientation['pitch_deg']:.6f}",
        "reference_roll_deg": f"{orientation['roll_deg']:.6f}",
        "reference_view_dir_x": f"{orientation['view_dir_x']:.9f}",
        "reference_view_dir_y": f"{orientation['view_dir_y']:.9f}",
        "reference_view_dir_z": f"{orientation['view_dir_z']:.9f}",
        "reference_source_type": "odm_report_shots_geojson",
        "reference_geometry_lon": str(coordinates[0]),
        "reference_geometry_lat": str(coordinates[1]),
        "reference_geometry_alt": str(coordinates[2]),
    }


def build_reference_from_seed(seed_row: dict[str, str]) -> dict[str, object]:
    query_x = parse_float(seed_row.get("query_x"))
    query_y = parse_float(seed_row.get("query_y"))
    altitude = parse_float(seed_row.get("absolute_altitude"))
    yaw_deg = parse_float(seed_row.get("gimbal_yaw_degree"))
    pitch_deg = parse_float(seed_row.get("gimbal_pitch_degree"))
    roll_deg = parse_float(seed_row.get("gimbal_roll_degree"))
    if query_x is None or query_y is None or altitude is None:
        raise ValueError("query_truth seed row is missing reference position values")
    if yaw_deg is None or pitch_deg is None or roll_deg is None:
        raise ValueError("query_truth seed row is missing gimbal orientation values")
    orientation = orientation_from_yaw_pitch_roll(yaw_deg, pitch_deg, roll_deg)
    return {
        "reference_crs": seed_row.get("query_crs", ""),
        "reference_camera_center_x": f"{query_x:.6f}",
        "reference_camera_center_y": f"{query_y:.6f}",
        "reference_camera_center_z": f"{altitude:.6f}",
        "reference_rotation_repr": json.dumps(
            {
                "yaw_deg": normalize_angle_deg(yaw_deg),
                "pitch_deg": pitch_deg,
                "roll_deg": normalize_angle_deg(roll_deg),
            },
            ensure_ascii=False,
        ),
        "reference_rotation_source": "queries_truth_seed.gimbal_ypr",
        "reference_yaw_deg": f"{orientation['yaw_deg']:.6f}",
        "reference_pitch_deg": f"{orientation['pitch_deg']:.6f}",
        "reference_roll_deg": f"{orientation['roll_deg']:.6f}",
        "reference_view_dir_x": f"{orientation['view_dir_x']:.9f}",
        "reference_view_dir_y": f"{orientation['view_dir_y']:.9f}",
        "reference_view_dir_z": f"{orientation['view_dir_z']:.9f}",
        "reference_source_type": "queries_truth_seed_fallback",
        "reference_geometry_lon": seed_row.get("longitude", ""),
        "reference_geometry_lat": seed_row.get("latitude", ""),
        "reference_geometry_alt": seed_row.get("absolute_altitude", ""),
    }


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    out_root = resolve_pose_eval_root(bundle_root, args.output_root)
    ensure_dir(out_root)

    query_rows = load_csv(resolve_runtime_path(args.query_seed_csv))
    selected_query_ids = set(args.query_id)
    raw_uav_root = resolve_runtime_path(args.raw_uav_root)

    shots_cache: dict[str, tuple[dict[str, dict[str, object]], Path | None, Path | None]] = {}
    out_rows: list[dict[str, object]] = []
    status_counts: dict[str, int] = {}
    reference_source_type_counts: dict[str, int] = {}

    for row in query_rows:
        query_id = row["query_id"]
        if selected_query_ids and query_id not in selected_query_ids:
            continue
        flight_id = row["flight_id"]
        image_name = row["image_name"]
        flight_root = find_flight_root(raw_uav_root, flight_id)
        if flight_id not in shots_cache:
            if flight_root is None:
                shots_cache[flight_id] = ({}, None, None)
            else:
                shots_map, shots_path = load_shots_by_filename(flight_root)
                shots_cache[flight_id] = (shots_map, shots_path, flight_root)
        shots_map, shots_path, resolved_flight_root = shots_cache[flight_id]
        shot_feature = shots_map.get(image_name)

        base_row: dict[str, object] = {
            "query_id": query_id,
            "flight_id": flight_id,
            "image_name": image_name,
            "query_image_path": row.get("query_image_path", ""),
            "reference_pose_source": "",
            "reference_crs": row.get("query_crs", ""),
            "reference_camera_center_x": "",
            "reference_camera_center_y": "",
            "reference_camera_center_z": "",
            "reference_rotation_repr": "",
            "reference_rotation_source": "",
            "reference_yaw_deg": "",
            "reference_pitch_deg": "",
            "reference_roll_deg": "",
            "reference_view_dir_x": "",
            "reference_view_dir_y": "",
            "reference_view_dir_z": "",
            "reference_source_type": "",
            "reference_geometry_lon": "",
            "reference_geometry_lat": "",
            "reference_geometry_alt": "",
            "seed_query_x": row.get("query_x", ""),
            "seed_query_y": row.get("query_y", ""),
            "seed_absolute_altitude": row.get("absolute_altitude", ""),
            "seed_gimbal_yaw_deg": row.get("gimbal_yaw_degree", ""),
            "seed_gimbal_pitch_deg": row.get("gimbal_pitch_degree", ""),
            "seed_gimbal_roll_deg": row.get("gimbal_roll_degree", ""),
            "status": "",
            "status_detail": "",
        }

        try:
            if shot_feature is not None and shots_path is not None:
                base_row.update(build_reference_from_shot(shot_feature, row.get("query_crs", "")))
                base_row["reference_pose_source"] = str(shots_path).replace("\\", "/")
                base_row["status"] = "ready"
                base_row["status_detail"] = "reference pose derived from ODM shots.geojson"
            else:
                base_row.update(build_reference_from_seed(row))
                base_row["reference_pose_source"] = str(resolve_runtime_path(args.query_seed_csv)).replace("\\", "/")
                base_row["status"] = "ready"
                if resolved_flight_root is None:
                    base_row["status_detail"] = "ODM flight root missing; fell back to queries_truth_seed"
                else:
                    base_row["status_detail"] = "ODM shot pose missing; fell back to queries_truth_seed"
        except Exception as exc:
            base_row["status"] = "missing_reference_pose"
            base_row["status_detail"] = str(exc)

        status_counts[str(base_row["status"])] = status_counts.get(str(base_row["status"]), 0) + 1
        source_type = str(base_row.get("reference_source_type", "")) or "unknown"
        reference_source_type_counts[source_type] = reference_source_type_counts.get(source_type, 0) + 1
        out_rows.append(base_row)

    manifest_csv = out_root / "query_reference_pose_manifest.csv"
    manifest_json = out_root / "query_reference_pose_manifest.json"
    write_csv(manifest_csv, out_rows)
    write_json(
        manifest_json,
        {
            "bundle_root": str(bundle_root),
            "query_seed_csv": str(resolve_runtime_path(args.query_seed_csv)),
            "raw_uav_root": str(raw_uav_root),
            "row_count": len(out_rows),
            "status_counts": status_counts,
            "reference_source_type_counts": reference_source_type_counts,
            "reference_priority": [
                "odm_report/shots.geojson",
                "queries_truth_seed.csv fallback",
            ],
            "generated_at_unix": time.time(),
        },
    )
    print(manifest_csv)


if __name__ == "__main__":
    main()

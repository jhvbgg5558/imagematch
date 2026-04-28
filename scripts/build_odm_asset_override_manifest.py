#!/usr/bin/env python3
"""Build the flight-level ODM asset override manifest for isolated experiments.

Purpose:
- resolve the authoritative ODM assets for the selected UAV flights without
  mutating the raw flight workspaces;
- emit one manifest row per flight so downstream truth and DSM stages can use
  explicit override paths instead of implicit flight-root conventions.

Main inputs:
- raw UAV flight workspaces under `D:\数据\武汉影像\无人机0.1m`;
- explicit flight IDs for the active experiment.

Main outputs:
- `<experiment-root>/plan/flight_asset_override_manifest.csv`
- `<experiment-root>/plan/flight_asset_override_manifest.json`

Applicable task constraints:
- this manifest is read-only indirection metadata;
- runtime satellite DOM assets remain unchanged;
- if a raster DSM is unavailable, the georeferenced ODM LAZ model is recorded
  as the fallback DSM-equivalent source for downstream materialization.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from pose_ortho_truth_utils import DEFAULT_RAW_UAV_ROOT, ensure_dir, resolve_runtime_path, write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT_ROOT = (
    PROJECT_ROOT / "new3output" / "nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16"
)
DEFAULT_FLIGHTS = (
    "DJI_202510311347_009_新建面状航线1",
    "DJI_202510311413_010_新建面状航线1",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-uav-root", default=str(DEFAULT_RAW_UAV_ROOT))
    parser.add_argument("--experiment-root", default=str(DEFAULT_EXPERIMENT_ROOT))
    parser.add_argument("--out-csv", default=None)
    parser.add_argument("--asset-version-tag", default="odm_refresh_2026-04-16")
    parser.add_argument("--flight-id", action="append", default=[])
    return parser.parse_args()


def find_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    raw_uav_root = resolve_runtime_path(args.raw_uav_root)
    experiment_root = resolve_runtime_path(args.experiment_root)
    out_csv = (
        resolve_runtime_path(args.out_csv)
        if args.out_csv
        else experiment_root / "plan" / "flight_asset_override_manifest.csv"
    )
    flight_ids = tuple(args.flight_id) if args.flight_id else DEFAULT_FLIGHTS

    rows: list[dict[str, object]] = []
    for flight_id in flight_ids:
        flight_root = raw_uav_root / flight_id
        orthophoto_path = flight_root / "odm_orthophoto" / "odm_orthophoto.tif"
        shots_geojson_path = flight_root / "odm_report" / "shots.geojson"
        cameras_json_path = flight_root / "cameras.json"
        dsm_raster_path = find_existing(
            flight_root / "odm_dem" / "dsm.tif",
            flight_root / "odm_dem" / "odm_dsm.tif",
            flight_root / "odm_dem" / "odm_dem.tif",
            flight_root / "odm_dem" / "dem.tif",
        )
        laz_path = flight_root / "odm_georeferencing" / "odm_georeferenced_model.laz"
        dsm_source_path = dsm_raster_path if dsm_raster_path is not None else laz_path
        dsm_source_kind = "raster" if dsm_raster_path is not None else "laz"

        status = "ready"
        missing: list[str] = []
        if not flight_root.exists():
            status = "missing_flight_root"
            missing.append("flight_root")
        if not orthophoto_path.exists():
            status = "missing_odm_orthophoto"
            missing.append("odm_orthophoto")
        if not shots_geojson_path.exists():
            status = "missing_shots_geojson"
            missing.append("shots_geojson")
        if not cameras_json_path.exists():
            status = "missing_cameras_json"
            missing.append("cameras_json")
        if not dsm_source_path.exists():
            status = "missing_odm_dsm_source"
            missing.append("odm_dsm_source")

        rows.append(
            {
                "flight_id": flight_id,
                "flight_root": str(flight_root).replace("\\", "/"),
                "odm_orthophoto_path": str(orthophoto_path).replace("\\", "/"),
                "odm_dsm_path": str(dsm_source_path).replace("\\", "/"),
                "odm_dsm_source_kind": dsm_source_kind,
                "shots_geojson_path": str(shots_geojson_path).replace("\\", "/"),
                "cameras_json_path": str(cameras_json_path).replace("\\", "/"),
                "asset_version_tag": args.asset_version_tag,
                "status": status,
                "missing_fields": ";".join(missing),
            }
        )

    write_csv(out_csv, rows)
    write_json(
        out_csv.with_suffix(".json"),
        {
            "raw_uav_root": str(raw_uav_root),
            "experiment_root": str(experiment_root),
            "asset_version_tag": args.asset_version_tag,
            "row_count": len(rows),
            "status_counts": {
                key: sum(1 for row in rows if row["status"] == key)
                for key in sorted({str(row["status"]) for row in rows})
            },
            "generated_at_unix": time.time(),
            "rows": rows,
        },
    )
    print(out_csv)


if __name__ == "__main__":
    main()

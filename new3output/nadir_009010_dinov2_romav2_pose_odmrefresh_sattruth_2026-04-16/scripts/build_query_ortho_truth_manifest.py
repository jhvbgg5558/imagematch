#!/usr/bin/env python3
"""Build a query-to-UAV-orthophoto truth manifest for formal pose evaluation.

Purpose:
- bind each formal query to its flight-level UAV orthophoto truth source;
- define a deterministic truth crop bbox around the query footprint;
- keep truth-orthophoto sourcing separate from runtime pose estimation.

Main inputs:
- `query_truth/queries_truth_seed.csv` for query metadata and footprint polygons;
- local UAV flight workspaces under `D:\数据\武汉影像\无人机0.1m`.
- optional flight-asset override manifest that redirects each flight to a
  specific ODM orthophoto version without mutating the raw flight workspace.

Main outputs:
- `<output_root>/query_ortho_truth_manifest.csv`
- `<output_root>/query_ortho_truth_manifest.json`

Applicable task constraints:
- truth orthophoto is evaluation-only and must not change retrieval or pose
  runtime behavior;
- when a flight-asset override manifest is provided, orthophoto sourcing must
  come from that manifest and must not silently fall back to the legacy flight
  root assets;
- the query image is not guaranteed to be orthophoto.
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
    bounds_from_polygon,
    ensure_dir,
    load_csv,
    resolve_runtime_path,
    resolve_output_root,
    write_csv,
    write_json,
    parse_footprint_polygon_xy,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_FORMAL_BUNDLE_ROOT))
    parser.add_argument(
        "--query-seed-csv",
        default=str(DEFAULT_QUERY_ROOT / "query_truth" / "queries_truth_seed.csv"),
    )
    parser.add_argument("--raw-uav-root", default=str(DEFAULT_RAW_UAV_ROOT))
    parser.add_argument("--flight-asset-manifest", default=None)
    parser.add_argument("--crop-margin-m", type=float, default=80.0)
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--output-root", default=None)
    return parser.parse_args()


def load_flight_asset_manifest(path: Path) -> dict[str, dict[str, str]]:
    rows = load_csv(path)
    if not rows:
        raise SystemExit(f"flight asset manifest is empty: {path}")
    mapping: dict[str, dict[str, str]] = {}
    for row in rows:
        flight_id = row.get("flight_id", "")
        if flight_id == "":
            raise SystemExit(f"flight asset manifest row is missing flight_id: {path}")
        mapping[flight_id] = row
    return mapping


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    eval_root = resolve_output_root(bundle_root, args.output_root)
    ensure_dir(eval_root)

    query_rows = load_csv(resolve_runtime_path(args.query_seed_csv))
    selected_query_ids = set(args.query_id)
    raw_uav_root = resolve_runtime_path(args.raw_uav_root)
    asset_manifest_path = (
        resolve_runtime_path(args.flight_asset_manifest)
        if args.flight_asset_manifest
        else None
    )
    asset_manifest = (
        load_flight_asset_manifest(asset_manifest_path)
        if asset_manifest_path is not None
        else {}
    )

    out_rows: list[dict[str, object]] = []
    status_counts: dict[str, int] = {}

    for row in query_rows:
        query_id = row["query_id"]
        if selected_query_ids and query_id not in selected_query_ids:
            continue
        flight_id = row["flight_id"]
        flight_root = raw_uav_root / flight_id
        asset_row = asset_manifest.get(flight_id)
        if asset_manifest_path is not None:
            if asset_row is None:
                orthophoto_path = Path("")
                status = "missing_flight_asset_override"
                truth_source_type = "odm_orthophoto_override"
                truth_asset_version_tag = ""
            else:
                orthophoto_path = resolve_runtime_path(asset_row.get("odm_orthophoto_path", ""))
                status = "ready" if orthophoto_path.exists() else "missing_truth_orthophoto"
                truth_source_type = "odm_orthophoto_override"
                truth_asset_version_tag = asset_row.get("asset_version_tag", "")
        else:
            orthophoto_path = flight_root / "odm_orthophoto" / "odm_orthophoto.tif"
            status = "ready" if orthophoto_path.exists() else "missing_truth_orthophoto"
            truth_source_type = "uav_flight_odm_orthophoto"
            truth_asset_version_tag = ""
        footprint_points = parse_footprint_polygon_xy(row["footprint_polygon_xy"])
        min_x, min_y, max_x, max_y = bounds_from_polygon(footprint_points)
        crop_min_x = min_x - args.crop_margin_m
        crop_min_y = min_y - args.crop_margin_m
        crop_max_x = max_x + args.crop_margin_m
        crop_max_y = max_y + args.crop_margin_m
        status_counts[status] = status_counts.get(status, 0) + 1
        truth_tile_path = eval_root / "truth_tiles" / f"{query_id}_truth_ortho.tif"
        out_rows.append(
            {
                "query_id": query_id,
                "flight_id": flight_id,
                "image_name": row["image_name"],
                "query_image_path": row["query_image_path"],
                "query_x": row["query_x"],
                "query_y": row["query_y"],
                "truth_crs": row["query_crs"],
                "truth_ortho_source": str(orthophoto_path).replace("\\", "/"),
                "truth_source_type": truth_source_type,
                "truth_asset_version_tag": truth_asset_version_tag,
                "footprint_polygon_xy": json.dumps(footprint_points, ensure_ascii=False),
                "crop_margin_m": f"{float(args.crop_margin_m):.3f}",
                "crop_min_x": f"{crop_min_x:.6f}",
                "crop_min_y": f"{crop_min_y:.6f}",
                "crop_max_x": f"{crop_max_x:.6f}",
                "crop_max_y": f"{crop_max_y:.6f}",
                "truth_crop_path": str(truth_tile_path).replace("\\", "/"),
                "status": status,
            }
        )

    manifest_csv = eval_root / "query_ortho_truth_manifest.csv"
    manifest_json = eval_root / "query_ortho_truth_manifest.json"
    write_csv(manifest_csv, out_rows)
    write_json(
        manifest_json,
        {
            "bundle_root": str(bundle_root),
            "query_seed_csv": str(resolve_runtime_path(args.query_seed_csv)),
            "raw_uav_root": str(raw_uav_root),
            "flight_asset_manifest": str(asset_manifest_path) if asset_manifest_path else "",
            "row_count": len(out_rows),
            "status_counts": status_counts,
            "generated_at_unix": time.time(),
        },
    )
    print(manifest_csv)


if __name__ == "__main__":
    main()

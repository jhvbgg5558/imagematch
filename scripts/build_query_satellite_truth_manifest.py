#!/usr/bin/env python3
"""Build the satellite-truth manifest for the satellite validation subchain.

Purpose:
- bind each selected query to a canonical source satellite GeoTIFF;
- define a deterministic crop bbox around the query footprint;
- keep the satellite-truth source separate from the runtime retrieval chain.

Main inputs:
- `query_truth/queries_truth_seed.csv` under the active experiment root;
- the coverage-truth table exported from the fixed satellite library;
- source satellite GeoTIFFs referenced by the selected truth rows.

Main outputs:
- `<output_root>/query_satellite_truth_manifest.csv`
- `<output_root>/query_satellite_truth_manifest.json`

Applicable task constraints:
- truth must be a crop from the original satellite GeoTIFF, not a fixed tile
  copied as the final truth patch;
- top-k candidate stitching must not be used to fabricate truth;
- the satellite-truth suite must live under
  `pose_v1_formal/eval_pose_validation_suite_satellite_truth`.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from satellite_truth_utils import (
    DEFAULT_BUNDLE_ROOT,
    DEFAULT_QUERY_SEED_CSV,
    DEFAULT_QUERY_TRUTH_CSV,
    DEFAULT_QUERY_TRUTH_TILES_CSV,
    choose_truth_row,
    group_by_query,
    resolve_satellite_suite_root,
)
from pose_ortho_truth_utils import (
    bounds_from_polygon,
    ensure_dir,
    load_csv,
    parse_footprint_polygon_xy,
    resolve_runtime_path,
    write_csv,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--query-seed-csv", default=str(DEFAULT_QUERY_SEED_CSV))
    parser.add_argument("--query-truth-tiles-csv", default=str(DEFAULT_QUERY_TRUTH_TILES_CSV))
    parser.add_argument("--query-truth-csv", default=str(DEFAULT_QUERY_TRUTH_CSV))
    parser.add_argument("--crop-margin-m", type=float, default=80.0)
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--output-root", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    suite_root = resolve_satellite_suite_root(bundle_root, args.output_root)
    ensure_dir(suite_root)

    query_rows = load_csv(resolve_runtime_path(args.query_seed_csv))
    truth_rows = load_csv(resolve_runtime_path(args.query_truth_tiles_csv))
    truth_summary_rows = load_csv(resolve_runtime_path(args.query_truth_csv))

    query_by_id = {row["query_id"]: row for row in query_rows}
    truth_by_query = group_by_query(truth_rows)
    truth_summary_by_query = {row["query_id"]: row for row in truth_summary_rows}
    selected_query_ids = set(args.query_id)

    out_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    source_tile_counts: Counter[str] = Counter()

    for query_id in sorted(query_by_id):
        if selected_query_ids and query_id not in selected_query_ids:
            continue
        seed_row = query_by_id[query_id]
        q_truth_rows = truth_by_query.get(query_id, [])
        if not q_truth_rows:
            status = "missing_truth_rows"
            status_counts[status] += 1
            out_rows.append(
                {
                    "query_id": query_id,
                    "flight_id": seed_row.get("flight_id", ""),
                    "image_name": seed_row.get("image_name", ""),
                    "query_image_path": seed_row.get("query_image_path", ""),
                    "query_x": seed_row.get("query_x", ""),
                    "query_y": seed_row.get("query_y", ""),
                    "query_crs": seed_row.get("query_crs", ""),
                    "footprint_polygon_xy": seed_row.get("footprint_polygon_xy", ""),
                    "crop_margin_m": f"{float(args.crop_margin_m):.3f}",
                    "crop_min_x": "",
                    "crop_min_y": "",
                    "crop_max_x": "",
                    "crop_max_y": "",
                    "truth_source_tif": "",
                    "truth_source_tile_id": "",
                    "truth_source_tile_size_m": "",
                    "truth_source_coverage_ratio": "",
                    "truth_source_valid_pixel_ratio": "",
                    "truth_source_black_pixel_ratio": "",
                    "truth_source_selection_rule": "satellite truth rows missing",
                    "truth_source_type": "satellite_source_tif_crop",
                    "truth_asset_version_tag": "",
                    "truth_crop_path": "",
                    "status": status,
                }
            )
            continue

        selected_truth = choose_truth_row(q_truth_rows)
        footprint_points = parse_footprint_polygon_xy(seed_row["footprint_polygon_xy"])
        min_x, min_y, max_x, max_y = bounds_from_polygon(footprint_points)
        crop_min_x = min_x - args.crop_margin_m
        crop_min_y = min_y - args.crop_margin_m
        crop_max_x = max_x + args.crop_margin_m
        crop_max_y = max_y + args.crop_margin_m

        source_tif = str(selected_truth.get("source_tif", ""))
        truth_asset_version_tag = "satellite_source_geo_tif_crop_v1"
        truth_crop_path = suite_root / "satellite_truth" / "truth_patches" / f"{query_id}_truth_satellite.tif"
        status = "ready" if source_tif else "missing_source_tif"
        status_counts[status] += 1
        source_tile_counts[selected_truth.get("tile_id", "")] += 1

        summary_row = truth_summary_by_query.get(query_id, {})
        out_rows.append(
            {
                "query_id": query_id,
                "flight_id": seed_row.get("flight_id", ""),
                "image_name": seed_row.get("image_name", ""),
                "query_image_path": seed_row.get("query_image_path", ""),
                "query_x": seed_row.get("query_x", ""),
                "query_y": seed_row.get("query_y", ""),
                "query_crs": seed_row.get("query_crs", ""),
                "footprint_polygon_xy": json.dumps(footprint_points, ensure_ascii=False),
                "crop_margin_m": f"{float(args.crop_margin_m):.3f}",
                "crop_min_x": f"{crop_min_x:.6f}",
                "crop_min_y": f"{crop_min_y:.6f}",
                "crop_max_x": f"{crop_max_x:.6f}",
                "crop_max_y": f"{crop_max_y:.6f}",
                "truth_source_tif": source_tif.replace("\\", "/"),
                "truth_source_tile_id": selected_truth.get("tile_id", ""),
                "truth_source_tile_size_m": selected_truth.get("tile_size_m", ""),
                "truth_source_coverage_ratio": selected_truth.get("coverage_ratio", ""),
                "truth_source_valid_pixel_ratio": selected_truth.get("valid_pixel_ratio", ""),
                "truth_source_black_pixel_ratio": selected_truth.get("black_pixel_ratio", ""),
                "truth_source_selection_rule": "strict_truth -> coverage_ratio -> valid_pixel_ratio -> lower black_pixel_ratio -> smaller tile_size_m",
                "truth_source_type": "satellite_source_tif_crop",
                "truth_asset_version_tag": truth_asset_version_tag,
                "truth_crop_path": str(truth_crop_path).replace("\\", "/"),
                "status": status,
                "truth_count_total": summary_row.get("truth_count_total", ""),
                "strict_truth_count_total": summary_row.get("strict_truth_count_total", ""),
                "soft_truth_count_total": summary_row.get("soft_truth_count_total", ""),
            }
        )

    manifest_csv = suite_root / "satellite_truth" / "query_satellite_truth_manifest.csv"
    manifest_json = suite_root / "satellite_truth" / "query_satellite_truth_manifest.json"
    write_csv(manifest_csv, out_rows)
    write_json(
        manifest_json,
        {
            "bundle_root": str(bundle_root),
            "query_seed_csv": str(resolve_runtime_path(args.query_seed_csv)),
            "query_truth_tiles_csv": str(resolve_runtime_path(args.query_truth_tiles_csv)),
            "query_truth_csv": str(resolve_runtime_path(args.query_truth_csv)),
            "row_count": len(out_rows),
            "status_counts": dict(status_counts),
            "source_tile_counts": dict(source_tile_counts),
            "generated_at_unix": time.time(),
        },
    )
    print(manifest_csv)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build a formal pose-v1 DSM cache manifest per candidate tile bbox.

Purpose:
- convert the formal candidate manifest into a per-candidate DSM cache plan
  under `new2output/pose_v1_formal/dsm_cache/`;
- keep DSM preparation aligned to candidate satellite tiles expanded by 250 m,
  without using query truth coordinates at runtime.

Main inputs:
- `input/formal_candidate_manifest.csv`

Main outputs:
- `input/formal_dsm_manifest.csv`
- `input/formal_dsm_manifest.json`
- `dsm_cache/requests/<dsm_source_name>_requests.csv`

Applicable task constraints:
- v1 DSM regions are built from candidate tile bbox plus a fixed 250 m margin;
- each DSM row remains tied to a candidate tile ID;
- this script prepares cache metadata only and does not use query truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--candidate-manifest-csv", default=None)
    parser.add_argument("--dsm-source-name", default="srtm")
    parser.add_argument("--dsm-source-type", default=None)
    parser.add_argument("--dsm-asset-version-tag", default="")
    parser.add_argument("--upstream-dsm-path", default="")
    parser.add_argument("--expand-margin-m", type=float, default=250.0)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    input_root = bundle_root / "input"
    logs_root = bundle_root / "logs"
    cache_root = bundle_root / "dsm_cache"
    requests_root = cache_root / "requests"
    rasters_root = cache_root / "rasters"
    ensure_dir(input_root)
    ensure_dir(logs_root)
    ensure_dir(requests_root)
    ensure_dir(rasters_root)

    candidate_manifest_csv = (
        Path(args.candidate_manifest_csv)
        if args.candidate_manifest_csv
        else input_root / "formal_candidate_manifest.csv"
    )
    dsm_source_type = args.dsm_source_type if args.dsm_source_type else args.dsm_source_name
    requests_filename = f"{args.dsm_source_name}_requests.csv"
    candidate_rows = load_csv(candidate_manifest_csv)
    if not candidate_rows:
        raise SystemExit(f"candidate manifest is empty: {candidate_manifest_csv}")

    candidate_dedup: dict[str, dict[str, object]] = {}
    request_dedup: dict[tuple[float, float, float, float], dict[str, object]] = {}
    margin = float(args.expand_margin_m)
    for row in candidate_rows:
        candidate_tile_id = row["candidate_tile_id"]
        if candidate_tile_id in candidate_dedup:
            continue
        min_x = float(row["min_x"]) - margin
        min_y = float(row["min_y"]) - margin
        max_x = float(row["max_x"]) + margin
        max_y = float(row["max_y"]) + margin
        bbox_key = (min_x, min_y, max_x, max_y)
        request_id = f"{args.dsm_source_name}_{candidate_tile_id}"
        raster_path = rasters_root / f"{request_id}.tif"
        dsm_row = {
            "dsm_id": candidate_tile_id,
            "candidate_tile_id": candidate_tile_id,
            "dsm_source_name": args.dsm_source_name,
            "dsm_source_type": dsm_source_type,
            "dsm_asset_version_tag": args.dsm_asset_version_tag,
            "upstream_dsm_path": args.upstream_dsm_path,
            "crs": row.get("crs", "EPSG:32650"),
            "tile_min_x": row["min_x"],
            "tile_min_y": row["min_y"],
            "tile_max_x": row["max_x"],
            "tile_max_y": row["max_y"],
            "expand_margin_m": f"{margin:.3f}",
            "request_min_x": f"{min_x:.6f}",
            "request_min_y": f"{min_y:.6f}",
            "request_max_x": f"{max_x:.6f}",
            "request_max_y": f"{max_y:.6f}",
            "raster_path": str(raster_path).replace("\\", "/"),
            "status": "planned",
            "download_request_id": request_id,
        }
        candidate_dedup[candidate_tile_id] = dsm_row
        if bbox_key not in request_dedup:
            request_dedup[bbox_key] = {
                "download_request_id": request_id,
                "dsm_source_name": args.dsm_source_name,
                "dsm_source_type": dsm_source_type,
                "dsm_asset_version_tag": args.dsm_asset_version_tag,
                "upstream_dsm_path": args.upstream_dsm_path,
                "crs": row.get("crs", "EPSG:32650"),
                "request_min_x": f"{min_x:.6f}",
                "request_min_y": f"{min_y:.6f}",
                "request_max_x": f"{max_x:.6f}",
                "request_max_y": f"{max_y:.6f}",
                "primary_candidate_tile_id": candidate_tile_id,
                "raster_path": str(raster_path).replace("\\", "/"),
                "status": "planned",
            }

    dsm_rows = list(candidate_dedup.values())
    request_rows = list(request_dedup.values())

    write_csv(input_root / "formal_dsm_manifest.csv", dsm_rows)
    write_csv(requests_root / requests_filename, request_rows)
    write_json(
        input_root / "formal_dsm_manifest.json",
        {
            "bundle_root": str(bundle_root),
            "candidate_manifest_csv": str(candidate_manifest_csv.resolve()),
            "dsm_source_name": args.dsm_source_name,
            "dsm_source_type": dsm_source_type,
            "dsm_asset_version_tag": args.dsm_asset_version_tag,
            "upstream_dsm_path": args.upstream_dsm_path,
            "expand_margin_m": margin,
            "dsm_count": len(dsm_rows),
            "unique_request_count": len(request_rows),
            "dsm_rows": dsm_rows,
            "generated_at_unix": time.time(),
        },
    )
    (logs_root / "build_candidate_dsm_cache.log").write_text(
        "\n".join(
            [
                "stage=build_candidate_dsm_cache",
                f"dsm_source_name={args.dsm_source_name}",
                f"dsm_source_type={dsm_source_type}",
                f"dsm_asset_version_tag={args.dsm_asset_version_tag}",
                f"upstream_dsm_path={args.upstream_dsm_path}",
                f"expand_margin_m={margin}",
                f"dsm_count={len(dsm_rows)}",
                f"unique_request_count={len(request_rows)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(input_root / "formal_dsm_manifest.csv")


if __name__ == "__main__":
    main()

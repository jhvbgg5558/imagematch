#!/usr/bin/env python3
"""Crop satellite truth patches for the satellite-truth validation suite.

Purpose:
- materialize per-query truth patches from the selected source satellite
  GeoTIFFs;
- preserve a single shared truth grid per query for later alignment and
  tie-point evaluation;
- keep the truth crop side isolated from runtime candidate selection.

Main inputs:
- `<output_root>/satellite_truth/query_satellite_truth_manifest.csv`
- source satellite GeoTIFFs referenced by the selected manifest rows

Main outputs:
- `<output_root>/satellite_truth/truth_patches/<query_id>_truth_satellite.tif`
- `<output_root>/satellite_truth/truth_patches/_summary.json`

Applicable task constraints:
- the crop must come from the source satellite GeoTIFF, not from fixed tiles
  copied as final truth;
- top-k candidate stitching must not be used to fabricate truth;
- the crop grid is for offline validation only.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from satellite_truth_utils import DEFAULT_BUNDLE_ROOT, DEFAULT_SUITE_DIRNAME, resolve_satellite_suite_root
from pose_ortho_truth_utils import (
    clamp_bounds,
    ensure_dir,
    load_csv,
    resolve_runtime_path,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--truth-manifest-csv", default=None)
    parser.add_argument("--target-resolution-m", type=float, default=0.5)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--output-root", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    suite_root = resolve_satellite_suite_root(bundle_root, args.output_root)
    manifest_csv = (
        Path(args.truth_manifest_csv)
        if args.truth_manifest_csv
        else suite_root / "satellite_truth" / "query_satellite_truth_manifest.csv"
    )
    rows = load_csv(resolve_runtime_path(manifest_csv))
    out_root = suite_root / "satellite_truth" / "truth_patches"
    ensure_dir(out_root)

    try:
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.transform import from_origin
        from rasterio.windows import from_bounds
    except Exception as exc:  # pragma: no cover - dependency guard
        raise SystemExit("rasterio is required to crop satellite truth patches") from exc

    built = 0
    status_counts: dict[str, int] = {}

    for row in rows:
        status = row.get("status", "")
        if status not in {"ready", "exists"}:
            status_counts[status or "not_ready"] = status_counts.get(status or "not_ready", 0) + 1
            continue

        out_path = resolve_runtime_path(row["truth_crop_path"])
        if out_path.exists() and not args.overwrite:
            status_counts["exists"] = status_counts.get("exists", 0) + 1
            built += 1
            continue

        src_path = resolve_runtime_path(row["truth_source_tif"])
        if not src_path.exists():
            status_counts["missing_source_tif"] = status_counts.get("missing_source_tif", 0) + 1
            continue

        with rasterio.open(src_path) as src:
            left, bottom, right, top = clamp_bounds(
                float(row["crop_min_x"]),
                float(row["crop_min_y"]),
                float(row["crop_max_x"]),
                float(row["crop_max_y"]),
                src.bounds,
            )
            if right <= left or top <= bottom:
                status_counts["no_overlap_with_source_tif"] = status_counts.get("no_overlap_with_source_tif", 0) + 1
                continue

            if (
                abs(left - float(row["crop_min_x"])) > 1e-6
                or abs(bottom - float(row["crop_min_y"])) > 1e-6
                or abs(right - float(row["crop_max_x"])) > 1e-6
                or abs(top - float(row["crop_max_y"])) > 1e-6
            ):
                crop_status = "clamped_to_source_bounds"
            else:
                crop_status = "ready"

            res = float(args.target_resolution_m)
            width = max(1, int(round((right - left) / res)))
            height = max(1, int(round((top - bottom) / res)))
            window = from_bounds(left, bottom, right, top, src.transform)
            data = src.read(
                window=window,
                out_shape=(src.count, height, width),
                resampling=Resampling.bilinear,
            )
            transform = from_origin(left, top, res, res)
            profile = src.profile.copy()
            profile.update(
                driver="GTiff",
                width=width,
                height=height,
                transform=transform,
                compress="lzw",
                tiled=True,
            )
            ensure_dir(out_path.parent)
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(data)
            built += 1
            status_counts[crop_status] = status_counts.get(crop_status, 0) + 1

    write_json(
        out_root / "_summary.json",
        {
            "bundle_root": str(bundle_root),
            "truth_manifest_csv": str(resolve_runtime_path(manifest_csv)),
            "target_resolution_m": float(args.target_resolution_m),
            "row_count": len(rows),
            "built_count": built,
            "status_counts": status_counts,
            "generated_at_unix": time.time(),
        },
    )
    print(out_root / "_summary.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Crop truth UAV orthophoto tiles for formal pose orthorectification checks.

Purpose:
- materialize per-query truth orthophoto crops from flight-level ODM
  orthophotos;
- normalize truth crops to a fixed evaluation grid for later comparison
  against pose-rendered predicted orthophotos.

Main inputs:
- `<output_root>/query_ortho_truth_manifest.csv`;
- source `odm_orthophoto/odm_orthophoto.tif` rasters from the UAV flight
  workspaces.

Main outputs:
- `<output_root>/truth_tiles/<query_id>_truth_ortho.tif`
- `<output_root>/truth_tiles/_summary.json`

Applicable task constraints:
- truth orthophoto remains evaluation-only;
- the fixed evaluation grid must not alter the runtime pose pipeline.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from pose_ortho_truth_utils import (
    DEFAULT_FORMAL_BUNDLE_ROOT,
    clamp_bounds,
    ensure_dir,
    load_csv,
    resolve_runtime_path,
    resolve_output_root,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_FORMAL_BUNDLE_ROOT))
    parser.add_argument("--truth-manifest-csv", default=None)
    parser.add_argument("--target-resolution-m", type=float, default=0.5)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--output-root", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    eval_root = resolve_output_root(bundle_root, args.output_root)
    manifest_csv = Path(args.truth_manifest_csv) if args.truth_manifest_csv else eval_root / "query_ortho_truth_manifest.csv"
    rows = load_csv(resolve_runtime_path(manifest_csv))
    out_root = eval_root / "truth_tiles"
    ensure_dir(out_root)

    try:
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.transform import from_origin
        from rasterio.windows import from_bounds
    except Exception as exc:  # pragma: no cover - dependency guard
        raise SystemExit("rasterio is required to crop orthophoto truth tiles") from exc

    built = 0
    status_counts: dict[str, int] = {}

    for row in rows:
        status = row["status"]
        if status != "ready":
            status_counts[status] = status_counts.get(status, 0) + 1
            continue
        out_path = resolve_runtime_path(row["truth_crop_path"])
        if out_path.exists() and not args.overwrite:
            status_counts["exists"] = status_counts.get("exists", 0) + 1
            built += 1
            continue
        src_path = resolve_runtime_path(row["truth_ortho_source"])
        with rasterio.open(src_path) as src:
            left, bottom, right, top = clamp_bounds(
                float(row["crop_min_x"]),
                float(row["crop_min_y"]),
                float(row["crop_max_x"]),
                float(row["crop_max_y"]),
                src.bounds,
            )
            if right <= left or top <= bottom:
                status_counts["no_overlap_with_truth_source"] = status_counts.get("no_overlap_with_truth_source", 0) + 1
                continue
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
            status_counts["ready"] = status_counts.get("ready", 0) + 1

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

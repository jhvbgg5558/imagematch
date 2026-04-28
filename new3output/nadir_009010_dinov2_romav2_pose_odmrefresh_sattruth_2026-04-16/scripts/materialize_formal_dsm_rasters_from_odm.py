#!/usr/bin/env python3
"""Materialize candidate DSM rasters from ODM raster or LAZ asset overrides.

Purpose:
- build one merged ODM-derived DSM source for the active experiment from the
  override manifest assets;
- crop per-candidate DSM rasters from that merged source into the formal
  `dsm_cache/rasters/` layout expected by downstream PnP scripts.

Main inputs:
- `input/formal_dsm_manifest.csv`;
- `plan/flight_asset_override_manifest.csv`;
- ODM raster DSM paths when available, otherwise georeferenced ODM LAZ point
  clouds recorded in the override manifest.

Main outputs:
- `dsm_cache/source/odm_dsm_merged.tif`
- `dsm_cache/rasters/*.tif`
- refreshed `input/formal_dsm_manifest.csv`
- `dsm_cache/rasters/_summary.json`

Applicable task constraints:
- runtime candidate DOM assets remain the fixed satellite library;
- DSM preparation stays candidate-oriented by request bbox;
- when only LAZ point clouds exist, DSM is rasterized from the merged ODM
  point clouds instead of falling back to SRTM.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT_ROOT = (
    PROJECT_ROOT / "new3output" / "nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_EXPERIMENT_ROOT / "pose_v1_formal"))
    parser.add_argument(
        "--flight-asset-manifest",
        default=str(DEFAULT_EXPERIMENT_ROOT / "plan" / "flight_asset_override_manifest.csv"),
    )
    parser.add_argument("--formal-dsm-manifest-csv", default=None)
    parser.add_argument("--out-root", default=None)
    parser.add_argument("--merged-raster-path", default=None)
    parser.add_argument("--target-crs", default="EPSG:32650")
    parser.add_argument("--target-resolution-m", type=float, default=1.0)
    parser.add_argument("--fill-empty-cells-iters", type=int, default=2)
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


def resolve_runtime_path(raw_path: str | Path) -> Path:
    text = str(raw_path)
    if os.name == "nt" and text.startswith("/mnt/") and len(text) > 6:
        drive_letter = text[5]
        remainder = text[7:].replace("/", "\\")
        return Path(f"{drive_letter.upper()}:\\{remainder}")
    if os.name != "nt" and len(text) >= 3 and text[1:3] == ":\\":
        drive_letter = text[0].lower()
        remainder = text[3:].replace("\\", "/")
        return Path(f"/mnt/{drive_letter}/{remainder}")
    return Path(text)


def fill_nodata_cells(grid: np.ndarray, nodata_value: float, iterations: int) -> tuple[np.ndarray, int]:
    if iterations <= 0:
        return grid, 0
    filled = grid.copy()
    total_filled = 0
    for _ in range(iterations):
        updates: list[tuple[int, int, float]] = []
        for row in range(filled.shape[0]):
            row0 = max(0, row - 1)
            row1 = min(filled.shape[0], row + 2)
            for col in range(filled.shape[1]):
                if filled[row, col] != nodata_value:
                    continue
                col0 = max(0, col - 1)
                col1 = min(filled.shape[1], col + 2)
                neighbourhood = filled[row0:row1, col0:col1]
                valid = neighbourhood[neighbourhood != nodata_value]
                if valid.size == 0:
                    continue
                updates.append((row, col, float(np.max(valid))))
        if not updates:
            break
        for row, col, value in updates:
            filled[row, col] = np.float32(value)
        total_filled += len(updates)
    return filled, total_filled


def load_override_rows(path: Path) -> list[dict[str, str]]:
    rows = load_csv(path)
    if not rows:
        raise SystemExit(f"flight asset manifest is empty: {path}")
    bad = [row["flight_id"] for row in rows if row.get("status") != "ready"]
    if bad:
        raise SystemExit(f"flight asset manifest has non-ready rows: {bad}")
    return rows


def build_union_bounds(dsm_rows: list[dict[str, str]]) -> tuple[float, float, float, float]:
    min_x = min(float(row["request_min_x"]) for row in dsm_rows)
    min_y = min(float(row["request_min_y"]) for row in dsm_rows)
    max_x = max(float(row["request_max_x"]) for row in dsm_rows)
    max_y = max(float(row["request_max_y"]) for row in dsm_rows)
    return min_x, min_y, max_x, max_y


def burn_laz_into_grid(
    grid: np.ndarray,
    min_x: float,
    max_y: float,
    resolution: float,
    nodata: float,
    source_path: Path,
) -> dict[str, object]:
    import laspy

    laz = laspy.read(source_path)
    xs = np.asarray(laz.x)
    ys = np.asarray(laz.y)
    zs = np.asarray(laz.z)
    width = grid.shape[1]
    height = grid.shape[0]
    cols = np.floor((xs - min_x) / resolution).astype(np.int64)
    rows = np.floor((max_y - ys) / resolution).astype(np.int64)
    valid = (cols >= 0) & (cols < width) & (rows >= 0) & (rows < height)
    cols = cols[valid]
    rows = rows[valid]
    zs = zs[valid]
    if cols.size == 0:
        return {"source_path": str(source_path), "accepted_point_count": 0}

    flat = grid.reshape(-1)
    flat_index = rows * width + cols
    current = flat[flat_index]
    replace = (current == nodata) | (zs > current)
    if np.any(replace):
        np.maximum.at(flat, flat_index[replace], zs[replace].astype(np.float32))
    return {"source_path": str(source_path), "accepted_point_count": int(cols.size)}


def merge_rasters_into_grid(
    grid: np.ndarray,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    resolution: float,
    nodata: float,
    source_path: Path,
    target_crs: str,
) -> dict[str, object]:
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.warp import reproject

    dst_transform = from_origin(min_x, max_y, resolution, resolution)
    temp = np.full_like(grid, nodata, dtype=np.float32)
    with rasterio.open(source_path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=temp,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=target_crs,
            dst_nodata=nodata,
            resampling=Resampling.bilinear,
        )
        src_nodata = src.nodata
    valid = np.isfinite(temp)
    valid &= temp != nodata
    if src_nodata is not None and not math.isnan(float(src_nodata)):
        valid &= temp != float(src_nodata)
    grid_valid = (grid != nodata) & np.isfinite(grid)
    grid[valid & ~grid_valid] = temp[valid & ~grid_valid]
    both_valid = valid & grid_valid
    grid[both_valid] = np.maximum(grid[both_valid], temp[both_valid])
    return {"source_path": str(source_path), "accepted_pixel_count": int(np.count_nonzero(valid))}


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    manifest_path = (
        Path(args.formal_dsm_manifest_csv)
        if args.formal_dsm_manifest_csv
        else bundle_root / "input" / "formal_dsm_manifest.csv"
    )
    out_root = Path(args.out_root) if args.out_root else bundle_root / "dsm_cache" / "rasters"
    merged_raster_path = (
        Path(args.merged_raster_path)
        if args.merged_raster_path
        else bundle_root / "dsm_cache" / "source" / "odm_dsm_merged.tif"
    )
    override_rows = load_override_rows(resolve_runtime_path(args.flight_asset_manifest))
    dsm_rows = load_csv(manifest_path)
    if not dsm_rows:
        raise SystemExit(f"formal DSM manifest is empty: {manifest_path}")

    ensure_dir(out_root)
    ensure_dir(merged_raster_path.parent)

    min_x, min_y, max_x, max_y = build_union_bounds(dsm_rows)
    resolution = float(args.target_resolution_m)
    width = max(1, int(math.ceil((max_x - min_x) / resolution)))
    height = max(1, int(math.ceil((max_y - min_y) / resolution)))
    nodata = -9999.0
    merged = np.full((height, width), nodata, dtype=np.float32)
    source_stats: list[dict[str, object]] = []

    for row in override_rows:
        source_path = resolve_runtime_path(row["odm_dsm_path"])
        source_kind = row.get("odm_dsm_source_kind", "")
        if source_kind == "laz":
            source_stats.append(
                burn_laz_into_grid(
                    merged,
                    min_x=min_x,
                    max_y=max_y,
                    resolution=resolution,
                    nodata=nodata,
                    source_path=source_path,
                )
            )
        else:
            source_stats.append(
                merge_rasters_into_grid(
                    merged,
                    min_x=min_x,
                    min_y=min_y,
                    max_x=max_x,
                    max_y=max_y,
                    resolution=resolution,
                    nodata=nodata,
                    source_path=source_path,
                    target_crs=args.target_crs,
                )
            )

    merged, filled_cell_count = fill_nodata_cells(
        merged,
        nodata_value=nodata,
        iterations=int(args.fill_empty_cells_iters),
    )

    import rasterio
    from rasterio.transform import from_origin
    from rasterio.windows import from_bounds

    merged_transform = from_origin(min_x, max_y, resolution, resolution)
    with rasterio.open(
        merged_raster_path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype="float32",
        crs=args.target_crs,
        transform=merged_transform,
        nodata=nodata,
        compress="lzw",
        tiled=True,
    ) as dst:
        dst.write(merged, 1)

    status_counts: dict[str, int] = {}
    built_examples: list[dict[str, object]] = []
    for row in dsm_rows:
        raster_path = resolve_runtime_path(row["raster_path"])
        ensure_dir(raster_path.parent)
        try:
            with rasterio.open(merged_raster_path) as src:
                window = from_bounds(
                    float(row["request_min_x"]),
                    float(row["request_min_y"]),
                    float(row["request_max_x"]),
                    float(row["request_max_y"]),
                    src.transform,
                )
                window = window.round_offsets().round_lengths()
                data = src.read(1, window=window)
                profile = src.profile.copy()
                profile.update(
                    width=int(window.width),
                    height=int(window.height),
                    transform=src.window_transform(window),
                )
            with rasterio.open(raster_path, "w", **profile) as dst:
                dst.write(data, 1)
            row["status"] = "ready"
            row["dsm_source_name"] = row.get("dsm_source_name", "odm")
            row["dsm_source_type"] = row.get("dsm_source_type", "odm_dsm_override")
            row["dsm_asset_version_tag"] = row.get("dsm_asset_version_tag", "")
            row["upstream_dsm_path"] = str(merged_raster_path).replace("\\", "/")
            if len(built_examples) < 10:
                built_examples.append(
                    {
                        "dsm_id": row["dsm_id"],
                        "raster_path": str(raster_path).replace("\\", "/"),
                        "width": profile["width"],
                        "height": profile["height"],
                    }
                )
        except Exception as exc:  # pragma: no cover
            row["status"] = f"failed:{type(exc).__name__}"
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

    write_csv(manifest_path, dsm_rows)
    write_json(
        out_root / "_summary.json",
        {
            "bundle_root": str(bundle_root),
            "formal_dsm_manifest_csv": str(manifest_path.resolve()),
            "flight_asset_manifest": str(resolve_runtime_path(args.flight_asset_manifest)),
            "merged_raster_path": str(merged_raster_path.resolve()),
            "planned_count": len(dsm_rows),
            "built_count": sum(1 for row in dsm_rows if row.get("status") == "ready"),
            "failed_count": sum(1 for row in dsm_rows if str(row.get("status", "")).startswith("failed:")),
            "source_type": "odm_dsm_override",
            "target_crs": args.target_crs,
            "target_resolution_m": resolution,
            "union_bounds": {
                "min_x": min_x,
                "min_y": min_y,
                "max_x": max_x,
                "max_y": max_y,
            },
            "filled_cell_count": int(filled_cell_count),
            "source_stats": source_stats,
            "status_counts": status_counts,
            "built_examples": built_examples,
            "generated_at_unix": time.time(),
        },
    )
    print(out_root / "_summary.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Batch reproject GeoTIFF tiles to a target CRS.

This script is designed for large tile sets and supports resume by skipping
output files that already exist.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from time import perf_counter
from concurrent.futures import ProcessPoolExecutor, as_completed

import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch reproject GeoTIFF tiles.")
    parser.add_argument("--src-dir", required=True, help="Source directory containing .tif tiles")
    parser.add_argument("--dst-dir", required=True, help="Destination directory for reprojected .tif tiles")
    parser.add_argument("--dst-crs", default="EPSG:32650", help="Target CRS (default: EPSG:32650)")
    parser.add_argument(
        "--resampling",
        default="bilinear",
        choices=["nearest", "bilinear", "cubic"],
        help="Resampling method (default: bilinear)",
    )
    parser.add_argument(
        "--pattern",
        default="*.tif",
        help="Glob pattern for source files (default: *.tif)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)",
    )
    return parser.parse_args()


def to_resampling(name: str) -> Resampling:
    return {
        "nearest": Resampling.nearest,
        "bilinear": Resampling.bilinear,
        "cubic": Resampling.cubic,
    }[name]


def reproject_one(src_path: str, dst_path: str, dst_crs: str, rs_name: str) -> tuple[str, str]:
    src = Path(src_path)
    dst = Path(dst_path)
    if dst.exists():
        return (src.name, "skipped")

    rs_method = to_resampling(rs_name)
    try:
        with rasterio.open(src) as src_ds:
            transform, width, height = calculate_default_transform(
                src_ds.crs,
                dst_crs,
                src_ds.width,
                src_ds.height,
                *src_ds.bounds,
            )

            profile = src_ds.profile.copy()
            profile.update(
                crs=dst_crs,
                transform=transform,
                width=width,
                height=height,
                compress="lzw",
                tiled=True,
                BIGTIFF="IF_SAFER",
            )

            with rasterio.open(dst, "w", **profile) as dst_ds:
                for band in range(1, src_ds.count + 1):
                    reproject(
                        source=rasterio.band(src_ds, band),
                        destination=rasterio.band(dst_ds, band),
                        src_transform=src_ds.transform,
                        src_crs=src_ds.crs,
                        dst_transform=transform,
                        dst_crs=dst_crs,
                        resampling=rs_method,
                    )
        return (src.name, "done")
    except Exception:
        return (src.name, "failed")


def main() -> None:
    args = parse_args()
    src_dir = Path(args.src_dir)
    dst_dir = Path(args.dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(src_dir.glob(args.pattern))
    if not files:
        raise SystemExit(f"No files matched {args.pattern} under {src_dir}")

    total = len(files)
    done = 0
    skipped = 0
    failed = 0
    t0 = perf_counter()

    print(f"Source: {src_dir}")
    print(f"Target: {dst_dir}")
    print(f"Target CRS: {args.dst_crs}")
    print(f"Tiles: {total}")

    workers = max(1, args.workers)
    if workers == 1:
        for idx, src_path in enumerate(files, start=1):
            name, status = reproject_one(
                str(src_path),
                str(dst_dir / src_path.name),
                args.dst_crs,
                args.resampling,
            )
            if status == "done":
                done += 1
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1
                print(f"[ERROR] {name}")

            if idx % 50 == 0 or idx == total:
                elapsed = perf_counter() - t0
                print(
                    f"[{idx}/{total}] done={done} skipped={skipped} failed={failed} "
                    f"elapsed={elapsed/60:.1f}min"
                )
    else:
        print(f"Workers: {workers} (cpu_count={os.cpu_count()})")
        tasks = []
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for src_path in files:
                tasks.append(
                    ex.submit(
                        reproject_one,
                        str(src_path),
                        str(dst_dir / src_path.name),
                        args.dst_crs,
                        args.resampling,
                    )
                )
            for idx, fut in enumerate(as_completed(tasks), start=1):
                name, status = fut.result()
                if status == "done":
                    done += 1
                elif status == "skipped":
                    skipped += 1
                else:
                    failed += 1
                    print(f"[ERROR] {name}")

                if idx % 100 == 0 or idx == total:
                    elapsed = perf_counter() - t0
                    print(
                        f"[{idx}/{total}] done={done} skipped={skipped} failed={failed} "
                        f"elapsed={elapsed/60:.1f}min"
                    )

    elapsed = perf_counter() - t0
    print(
        f"Finished. done={done} skipped={skipped} failed={failed} "
        f"total={total} elapsed={elapsed/60:.1f}min"
    )


if __name__ == "__main__":
    main()

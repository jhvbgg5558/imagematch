#!/usr/bin/env python3
"""Scan raster files and report unreadable inputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from time import perf_counter

import rasterio


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan raster files for readability.")
    parser.add_argument("--src-dir", required=True, help="Directory containing raster files.")
    parser.add_argument("--pattern", default="*.tif", help="Glob pattern under src-dir.")
    parser.add_argument(
        "--report-csv",
        required=True,
        help="CSV report path. Includes readable and unreadable files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    src_dir = Path(args.src_dir)
    report_csv = Path(args.report_csv)
    report_csv.parent.mkdir(parents=True, exist_ok=True)

    paths = sorted(src_dir.glob(args.pattern))
    if not paths:
        raise SystemExit(f"No files matched {args.pattern} under {src_dir}")

    t0 = perf_counter()
    ok_count = 0
    bad_count = 0

    with report_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "path",
                "status",
                "epsg",
                "width",
                "height",
                "bands",
                "res_x",
                "res_y",
                "error",
            ]
        )

        for idx, path in enumerate(paths, start=1):
            try:
                with rasterio.open(path) as ds:
                    writer.writerow(
                        [
                            str(path),
                            "ok",
                            ds.crs.to_epsg() if ds.crs else "",
                            ds.width,
                            ds.height,
                            ds.count,
                            ds.res[0],
                            ds.res[1],
                            "",
                        ]
                    )
                ok_count += 1
            except Exception as exc:  # pragma: no cover - depends on external files
                writer.writerow([str(path), "bad", "", "", "", "", "", "", str(exc)])
                bad_count += 1

            if idx % 500 == 0 or idx == len(paths):
                elapsed = perf_counter() - t0
                print(
                    f"[{idx}/{len(paths)}] ok={ok_count} bad={bad_count} "
                    f"elapsed={elapsed/60:.1f}min"
                )

    print(f"Report written to {report_csv}")
    print(f"Finished. ok={ok_count} bad={bad_count} total={len(paths)}")


if __name__ == "__main__":
    main()

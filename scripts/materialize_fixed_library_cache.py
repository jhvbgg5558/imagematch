#!/usr/bin/env python3
"""Materialize model-specific resized caches from the raw fixed satellite library.

Inputs:
- tile metadata CSV from the raw fixed satellite library
- target square input size

Outputs:
- resized cached images
- cache manifest CSV mapping tile_id to cached image path

Used for:
- model-specific preprocessing after raw fixed satellite assets are already built
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create resized cache for fixed satellite library tiles.")
    parser.add_argument("--tile-metadata-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--cache-manifest-csv", required=True)
    parser.add_argument("--input-size", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    manifest_csv = Path(args.cache_manifest_csv)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_csv.parent.mkdir(parents=True, exist_ok=True)

    with open(args.tile_metadata_csv, "r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    out_rows: list[dict[str, str]] = []
    for row in rows:
        src = Path(row["image_path"])
        dst = out_dir / src.name
        with Image.open(src) as img:
            resized = img.convert("RGB").resize((args.input_size, args.input_size), Image.BICUBIC)
            resized.save(dst)
        out_rows.append(
            {
                "tile_id": row["tile_id"],
                "tile_size_m": row["tile_size_m"],
                "source_image_path": str(src),
                "cached_image_path": str(dst),
                "input_size": str(args.input_size),
            }
        )

    with manifest_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Cached tiles: {len(out_rows)}")


if __name__ == "__main__":
    main()

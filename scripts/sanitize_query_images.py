#!/usr/bin/env python3
"""Create metadata-stripped query image copies for retrieval experiments."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create metadata-free copies of selected UAV query images.")
    parser.add_argument("--selected-query-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--manifest-csv", required=True)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def sanitize_image(src: Path, dst: Path) -> str:
    ensure_dir(dst.parent)
    with Image.open(src) as img:
        clean = img.convert("RGB")
        if dst.suffix.lower() in {".jpg", ".jpeg"}:
            clean.save(dst, format="JPEG", quality=95, subsampling=0)
        else:
            clean.save(dst)
    return "pillow_reencode_without_metadata"


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    manifest_csv = Path(args.manifest_csv)
    ensure_dir(out_dir)
    ensure_dir(manifest_csv.parent)

    with open(args.selected_query_csv, "r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("No selected queries found.")

    manifest_rows: list[dict[str, str]] = []
    for idx, row in enumerate(rows, start=1):
        query_id = f"q_{idx:03d}"
        flight_id = row["flight_id"]
        image_name = row["image_name"]
        src = Path(row["copied_path"])
        dst = out_dir / flight_id / image_name
        method = sanitize_image(src, dst)
        manifest_rows.append(
            {
                "query_id": query_id,
                "flight_id": flight_id,
                "image_name": image_name,
                "original_query_path": str(src),
                "sanitized_query_path": str(dst),
                "has_metadata_removed": "1",
                "sanitization_method": method,
            }
        )

    with manifest_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"Sanitized queries: {len(manifest_rows)}")
    print(f"Output dir: {out_dir}")
    print(f"Manifest: {manifest_csv}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create downsampled query images for the new4 resolution sweep.

Purpose:
- derive controlled lower-resolution query images for G04 while preserving the
  original metadata-free query contract;
- rewrite the query manifest so DINO, RoMa, and Pose v1 consume the
  downsampled image paths;
- record the pixel scale needed for downstream intrinsics scaling.

Main inputs:
- `query_inputs/query_manifest.csv` with sanitized query image paths;
- `queries_truth_seed.csv` containing relative altitude and calibrated focal
  length used only to estimate this controlled sweep's approximate query GSD.

Main outputs:
- downsampled metadata-free query images;
- rewritten query manifest CSV;
- JSON summary with per-query scale factors.

Applicable task constraints:
- runtime queries still have no geolocation metadata and are not assumed to be
  orthophotos;
- this script intentionally introduces an external resolution sweep variable
  only for the G04 speed/accuracy experiment, not as the default task protocol.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-manifest-csv", required=True)
    parser.add_argument("--query-seed-csv", required=True)
    parser.add_argument("--out-query-manifest-csv", required=True)
    parser.add_argument("--out-image-root", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--target-gsd-m", type=float, required=True)
    return parser.parse_args()


def resolve_runtime_path(raw_path: str | Path) -> Path:
    text = str(raw_path)
    if os.name == "nt" and text.startswith("/mnt/") and len(text) > 6:
        drive_letter = text[5].upper()
        remainder = text[7:].replace("/", "\\")
        return Path(f"{drive_letter}:\\{remainder}")
    if os.name != "nt" and len(text) >= 3 and text[1:3] in {":\\", ":/"}:
        drive_letter = text[0].lower()
        remainder = text[3:].replace("\\", "/")
        return Path(f"/mnt/{drive_letter}/{remainder}")
    return Path(text)


def as_manifest_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        raise SystemExit("no rows to write")
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def float_or_none(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def main() -> None:
    args = parse_args()
    if args.target_gsd_m <= 0:
        raise SystemExit("--target-gsd-m must be positive")

    manifest_csv = resolve_runtime_path(args.query_manifest_csv)
    seed_csv = resolve_runtime_path(args.query_seed_csv)
    out_manifest_csv = resolve_runtime_path(args.out_query_manifest_csv)
    out_image_root = resolve_runtime_path(args.out_image_root)
    summary_json = resolve_runtime_path(args.summary_json)

    query_rows = load_csv(manifest_csv)
    seed_rows = load_csv(seed_csv)
    if not query_rows:
        raise SystemExit(f"query manifest is empty: {manifest_csv}")
    seed_by_query = {row["query_id"]: row for row in seed_rows}

    output_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for row in query_rows:
        query_id = row["query_id"]
        seed = seed_by_query.get(query_id)
        if seed is None:
            raise SystemExit(f"query seed row not found for {query_id}")
        altitude_m = float_or_none(seed.get("relative_altitude"))
        focal_px = float_or_none(seed.get("calibrated_focal_length_px"))
        if altitude_m is None or focal_px is None or focal_px <= 0:
            raise SystemExit(f"missing altitude/focal metadata for {query_id}")
        estimated_gsd_m = altitude_m / focal_px
        scale = min(1.0, estimated_gsd_m / args.target_gsd_m)
        image_path = resolve_runtime_path(row["sanitized_query_path"])
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            original_width, original_height = image.size
            new_width = max(1, int(round(original_width * scale)))
            new_height = max(1, int(round(original_height * scale)))
            actual_scale_x = new_width / original_width
            actual_scale_y = new_height / original_height
            if new_width == original_width and new_height == original_height:
                resized = image
            else:
                resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            flight_dir = out_image_root / row["flight_id"]
            ensure_dir(flight_dir)
            out_image = flight_dir / image_path.name
            resized.save(out_image, quality=95)

        out_row: dict[str, Any] = dict(row)
        out_row["sanitized_query_path"] = as_manifest_path(out_image)
        out_row["downsample_target_gsd_m"] = f"{args.target_gsd_m:.12f}"
        out_row["estimated_query_gsd_m"] = f"{estimated_gsd_m:.12f}"
        out_row["downsample_scale"] = f"{scale:.12f}"
        out_row["original_width_px"] = original_width
        out_row["original_height_px"] = original_height
        out_row["downsampled_width_px"] = new_width
        out_row["downsampled_height_px"] = new_height
        out_row["intrinsics_scale_x"] = f"{actual_scale_x:.12f}"
        out_row["intrinsics_scale_y"] = f"{actual_scale_y:.12f}"
        output_rows.append(out_row)
        summary_rows.append(
            {
                "query_id": query_id,
                "flight_id": row["flight_id"],
                "image_name": row["image_name"],
                "source_image": as_manifest_path(image_path),
                "downsampled_image": as_manifest_path(out_image),
                "target_gsd_m": args.target_gsd_m,
                "estimated_query_gsd_m": estimated_gsd_m,
                "requested_scale": scale,
                "intrinsics_scale_x": actual_scale_x,
                "intrinsics_scale_y": actual_scale_y,
                "original_width_px": original_width,
                "original_height_px": original_height,
                "downsampled_width_px": new_width,
                "downsampled_height_px": new_height,
            }
        )

    write_csv(out_manifest_csv, output_rows)
    write_json(
        summary_json,
        {
            "query_manifest_csv": as_manifest_path(manifest_csv),
            "out_query_manifest_csv": as_manifest_path(out_manifest_csv),
            "out_image_root": as_manifest_path(out_image_root),
            "target_gsd_m": args.target_gsd_m,
            "query_count": len(output_rows),
            "queries": summary_rows,
        },
    )
    print(out_manifest_csv)


if __name__ == "__main__":
    main()

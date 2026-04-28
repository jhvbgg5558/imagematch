#!/usr/bin/env python3
"""Create scale-filtered metadata and feature subsets from a fixed satellite library."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Subset fixed-library metadata and feature NPZ by scale.")
    parser.add_argument("--metadata-csv", required=True)
    parser.add_argument("--features-npz", required=True)
    parser.add_argument("--allowed-scales", required=True, nargs="+", type=float)
    parser.add_argument("--output-metadata-csv", required=True)
    parser.add_argument("--output-features-npz", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    allowed = {f"{float(scale):.1f}" for scale in args.allowed_scales}

    with open(args.metadata_csv, "r", newline="", encoding="utf-8-sig") as f:
        metadata_rows = list(csv.DictReader(f))
    if not metadata_rows:
        raise SystemExit("Metadata CSV is empty.")

    filtered_rows = [row for row in metadata_rows if row["tile_size_m"] in allowed]
    if not filtered_rows:
        raise SystemExit(f"No rows matched allowed scales: {sorted(allowed)}")

    keep_ids = {row["tile_id"] for row in filtered_rows}
    data = np.load(args.features_npz, allow_pickle=True)
    ids = [str(x) for x in data["ids"].tolist()]
    features = data["features"].astype("float32")
    keep_idx = [idx for idx, tile_id in enumerate(ids) if tile_id in keep_ids]
    subset_ids = np.array([ids[idx] for idx in keep_idx], dtype=object)
    subset_features = features[keep_idx]

    output_metadata_csv = Path(args.output_metadata_csv)
    output_features_npz = Path(args.output_features_npz)
    output_metadata_csv.parent.mkdir(parents=True, exist_ok=True)
    output_features_npz.parent.mkdir(parents=True, exist_ok=True)

    with output_metadata_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(filtered_rows[0].keys()))
        writer.writeheader()
        writer.writerows(filtered_rows)

    np.savez_compressed(output_features_npz, ids=subset_ids, features=subset_features)

    print(f"Allowed scales: {sorted(allowed, key=float)}")
    print(f"Metadata rows: {len(filtered_rows)}")
    print(f"Feature rows: {subset_features.shape[0]}")
    print(f"Output metadata: {output_metadata_csv}")
    print(f"Output features: {output_features_npz}")


if __name__ == "__main__":
    main()

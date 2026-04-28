#!/usr/bin/env python3
"""Build a FAISS index from extracted feature vectors."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import faiss
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build FAISS index from .npz features.")
    parser.add_argument("--features-npz", required=True, help="NPZ from extract_dino_features.py")
    parser.add_argument("--metadata-csv", required=True, help="Metadata CSV from stage 1 or query prep")
    parser.add_argument("--id-column", default="tile_id", help="ID column used to join metadata")
    parser.add_argument(
        "--index-type",
        default="ip",
        choices=["ip", "l2"],
        help="FAISS index type: inner product or L2",
    )
    parser.add_argument("--output-index", required=True, help="Output FAISS index path")
    parser.add_argument(
        "--output-mapping-json",
        required=True,
        help="Output JSON mapping FAISS row -> id -> metadata",
    )
    return parser.parse_args()


def load_metadata(path: Path, id_column: str) -> dict[str, dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if id_column not in reader.fieldnames:
            raise SystemExit(f"Metadata CSV missing id column {id_column!r}")
        return {row[id_column]: row for row in reader}


def main() -> None:
    args = parse_args()
    output_index = Path(args.output_index)
    output_mapping = Path(args.output_mapping_json)
    output_index.parent.mkdir(parents=True, exist_ok=True)
    output_mapping.parent.mkdir(parents=True, exist_ok=True)

    data = np.load(args.features_npz, allow_pickle=True)
    ids = data["ids"]
    features = data["features"].astype("float32")
    if features.ndim != 2 or features.shape[0] == 0:
        raise SystemExit("Feature matrix is empty or malformed.")

    if args.index_type == "ip":
        index = faiss.IndexFlatIP(features.shape[1])
    else:
        index = faiss.IndexFlatL2(features.shape[1])

    index.add(features)
    faiss.write_index(index, str(output_index))

    metadata = load_metadata(Path(args.metadata_csv), args.id_column)
    mapping = []
    missing = 0
    for idx, sample_id in enumerate(ids.tolist()):
        sample_id = str(sample_id)
        row = metadata.get(sample_id)
        if row is None:
            missing += 1
            row = {args.id_column: sample_id}
        mapping.append({"faiss_row": idx, "id": sample_id, "metadata": row})

    with output_mapping.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "index_type": args.index_type,
                "dimension": int(features.shape[1]),
                "count": int(features.shape[0]),
                "missing_metadata": missing,
                "items": mapping,
            },
            f,
            ensure_ascii=False,
        )

    print(f"Index saved to {output_index}")
    print(f"Mapping saved to {output_mapping}")
    print(f"Finished. vectors={features.shape[0]} dim={features.shape[1]} missing_metadata={missing}")


if __name__ == "__main__":
    main()

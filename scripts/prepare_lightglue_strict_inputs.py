#!/usr/bin/env python3
"""Prepare stage3/stage4 inputs for LightGlue reranking on the current strict-truth task."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", required=True, help="Strict baseline result dir containing query_inputs and query_truth.")
    parser.add_argument("--coarse-retrieval-csv", required=True, help="Top-k coarse retrieval CSV.")
    parser.add_argument("--out-root", required=True, help="Output root that will contain stage3 and stage4.")
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    result_dir = Path(args.result_dir)
    out_root = Path(args.out_root)
    stage3 = out_root / "stage3"
    stage4 = out_root / "stage4"
    stage3.mkdir(parents=True, exist_ok=True)
    stage4.mkdir(parents=True, exist_ok=True)

    manifest_rows = {row["query_id"]: row for row in load_csv(result_dir / "query_inputs" / "query_manifest.csv")}
    seed_rows = {row["query_id"]: row for row in load_csv(result_dir / "query_truth" / "queries_truth_seed.csv")}
    truth_rows = load_csv(result_dir / "query_truth" / "query_truth_strict_only.csv")
    retrieval_rows = load_csv(Path(args.coarse_retrieval_csv))

    truth_ids: dict[str, list[str]] = defaultdict(list)
    for row in truth_rows:
        truth_ids[row["query_id"]].append(row["tile_id"])

    by_flight_queries: dict[str, list[dict[str, str]]] = defaultdict(list)
    for query_id, seed in seed_rows.items():
        manifest = manifest_rows[query_id]
        by_flight_queries[seed["flight_id"]].append(
            {
                "query_id": query_id,
                "flight_id": seed["flight_id"],
                "image_path": manifest["sanitized_query_path"],
                "truth_tile_ids": "|".join(truth_ids.get(query_id, [])),
                "center_x": seed["query_x"],
                "center_y": seed["query_y"],
            }
        )

    by_flight_retrieval: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in retrieval_rows:
        flight_id = seed_rows[row["query_id"]]["flight_id"]
        by_flight_retrieval[flight_id].append(row)

    query_fields = ["query_id", "flight_id", "image_path", "truth_tile_ids", "center_x", "center_y"]
    retrieval_fields = list(retrieval_rows[0].keys())
    for flight_id, rows in sorted(by_flight_queries.items()):
        write_csv(stage3 / flight_id / "queries.csv", sorted(rows, key=lambda x: x["query_id"]), query_fields)
        flight_retrieval = sorted(by_flight_retrieval[flight_id], key=lambda x: (x["query_id"], int(x["rank"])))
        write_csv(stage4 / flight_id / f"retrieval_top{max(int(r['rank']) for r in flight_retrieval)}.csv", flight_retrieval, retrieval_fields)

    print(f"Prepared LightGlue inputs under {out_root}")


if __name__ == "__main__":
    main()

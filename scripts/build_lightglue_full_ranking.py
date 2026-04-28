#!/usr/bin/env python3
"""Merge LightGlue Top-50 reranked results with baseline full-library retrieval."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lightglue-dir", required=True)
    parser.add_argument("--baseline-retrieval-csv", required=True)
    parser.add_argument("--out-csv", required=True)
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    lightglue_dir = Path(args.lightglue_dir)
    baseline_rows = load_csv(Path(args.baseline_retrieval_csv))

    baseline_by_query: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in baseline_rows:
        baseline_by_query[row["query_id"]].append(row)
    for rows in baseline_by_query.values():
        rows.sort(key=lambda r: int(r["rank"]))

    lg_rows_by_query: dict[str, list[dict[str, str]]] = defaultdict(list)
    for reranked_csv in sorted((lightglue_dir / "stage7").glob("*/*reranked_top50.csv")):
        for row in load_csv(reranked_csv):
            lg_rows_by_query[row["query_id"]].append(row)
    for rows in lg_rows_by_query.values():
        rows.sort(key=lambda r: int(r["rank"]))

    fieldnames = [
        "query_id",
        "rank",
        "candidate_tile_id",
        "score",
        "candidate_scale_level_m",
        "candidate_center_x",
        "candidate_center_y",
        "is_intersection_truth_hit",
        "source",
        "raw_rank",
    ]
    merged_rows: list[dict[str, object]] = []

    for query_id in sorted(baseline_by_query):
        top50 = lg_rows_by_query.get(query_id)
        if not top50:
            raise SystemExit(f"Missing LightGlue reranked rows for {query_id}")
        used_tiles = set()
        next_rank = 1

        for row in top50:
            tile_id = row["candidate_tile_id"]
            used_tiles.add(tile_id)
            merged_rows.append(
                {
                    "query_id": query_id,
                    "rank": next_rank,
                    "candidate_tile_id": tile_id,
                    "score": row["fused_score"],
                    "candidate_scale_level_m": row["candidate_scale_level_m"],
                    "candidate_center_x": row["candidate_center_x"],
                    "candidate_center_y": row["candidate_center_y"],
                    "is_intersection_truth_hit": row["is_intersection_truth_hit"],
                    "source": "lightglue_top50",
                    "raw_rank": row["raw_rank"],
                }
            )
            next_rank += 1

        for row in baseline_by_query[query_id]:
            tile_id = row["candidate_tile_id"]
            if tile_id in used_tiles:
                continue
            merged_rows.append(
                {
                    "query_id": query_id,
                    "rank": next_rank,
                    "candidate_tile_id": tile_id,
                    "score": row["score"],
                    "candidate_scale_level_m": row["candidate_scale_level_m"],
                    "candidate_center_x": row["candidate_center_x"],
                    "candidate_center_y": row["candidate_center_y"],
                    "is_intersection_truth_hit": row["is_intersection_truth_hit"],
                    "source": "baseline_51plus",
                    "raw_rank": row["rank"],
                }
            )
            next_rank += 1

        expected = len(baseline_by_query[query_id])
        actual = next_rank - 1
        if actual != expected:
            raise SystemExit(f"{query_id}: expected {expected} rows after merge, got {actual}")

    write_csv(Path(args.out_csv), merged_rows, fieldnames)
    print(Path(args.out_csv))


if __name__ == "__main__":
    main()

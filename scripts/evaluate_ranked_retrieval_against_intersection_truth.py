#!/usr/bin/env python3
"""Evaluate an existing ranked retrieval CSV against intersection truth and export top-k curves."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval-csv", required=True)
    parser.add_argument("--query-seed-csv", required=True)
    parser.add_argument("--query-truth-tiles-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--curve-csv", required=True)
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_truth(seed_csv: Path, truth_csv: Path) -> dict[str, dict[str, object]]:
    with seed_csv.open("r", newline="", encoding="utf-8-sig") as f:
        seed = {row["query_id"]: row for row in csv.DictReader(f)}

    truth_ids: dict[str, list[str]] = defaultdict(list)
    with truth_csv.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("is_intersection_truth", "1") != "1":
                continue
            truth_ids[row["query_id"]].append(row["tile_id"])

    out = {}
    for qid, row in seed.items():
        out[qid] = {
            "flight_id": row["flight_id"],
            "query_x": float(row["query_x"]),
            "query_y": float(row["query_y"]),
            "truth_ids": truth_ids.get(qid, []),
        }
    return out


def hit_at_k(pred_ids: list[str], truth_ids: list[str], k: int) -> bool:
    truth = set(truth_ids)
    return any(pid in truth for pid in pred_ids[:k])


def first_rank(pred_ids: list[str], truth_ids: list[str]) -> int | None:
    truth = set(truth_ids)
    for idx, pid in enumerate(pred_ids, start=1):
        if pid in truth:
            return idx
    return None


def main() -> None:
    args = parse_args()
    retrieval_rows = load_csv(Path(args.retrieval_csv))
    truth = load_truth(Path(args.query_seed_csv), Path(args.query_truth_tiles_csv))

    by_query: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in retrieval_rows:
        by_query[row["query_id"]].append(row)
    for rows in by_query.values():
        rows.sort(key=lambda r: int(r["rank"]))

    summary_path = Path(args.summary_json)
    curve_path = Path(args.curve_csv)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    curve_path.parent.mkdir(parents=True, exist_ok=True)

    hit_counts = {1: 0, 5: 0, 10: 0, 20: 0, 50: 0}
    reciprocal_rank_sum = 0.0
    top1_errors = []
    per_query = []

    with curve_path.open("w", newline="", encoding="utf-8-sig") as cf:
        curve_writer = csv.writer(cf)
        curve_writer.writerow(
            ["query_id", "flight_id", "k", "cumulative_truth_hits", "total_truth_count", "cumulative_truth_ratio"]
        )

        for qid in sorted(by_query):
            rows = by_query[qid]
            meta = truth[qid]
            truth_ids = meta["truth_ids"]
            truth_set = set(truth_ids)
            pred_ids: list[str] = []
            cumulative_hits = 0
            top1_error_m = None
            for row in rows:
                rank = int(row["rank"])
                tile_id = row["candidate_tile_id"]
                pred_ids.append(tile_id)
                if tile_id in truth_set:
                    cumulative_hits += 1
                if rank == 1:
                    dx = float(row.get("candidate_center_x", 0.0)) - float(meta["query_x"])
                    dy = float(row.get("candidate_center_y", 0.0)) - float(meta["query_y"])
                    top1_error_m = math.hypot(dx, dy)
                total_truth = len(truth_ids)
                curve_writer.writerow(
                    [
                        qid,
                        meta["flight_id"],
                        rank,
                        cumulative_hits,
                        total_truth,
                        0.0 if total_truth == 0 else cumulative_hits / total_truth,
                    ]
                )

            q_stats = {
                "query_id": qid,
                "flight_id": meta["flight_id"],
                "truth_count": len(truth_ids),
                "first_truth_rank": first_rank(pred_ids, truth_ids),
                "intersection_hit@1": hit_at_k(pred_ids, truth_ids, 1),
                "intersection_hit@5": hit_at_k(pred_ids, truth_ids, 5),
                "intersection_hit@10": hit_at_k(pred_ids, truth_ids, 10),
                "intersection_hit@20": hit_at_k(pred_ids, truth_ids, 20),
                "intersection_hit@50": hit_at_k(pred_ids, truth_ids, 50),
                "intersection_reciprocal_rank": 0.0,
                "top1_error_m": top1_error_m,
            }
            if q_stats["first_truth_rank"] is not None:
                q_stats["intersection_reciprocal_rank"] = 1.0 / int(q_stats["first_truth_rank"])
            per_query.append(q_stats)
            reciprocal_rank_sum += q_stats["intersection_reciprocal_rank"]
            if top1_error_m is not None:
                top1_errors.append(top1_error_m)
            for k in hit_counts:
                hit_counts[k] += int(q_stats[f"intersection_hit@{k}"])

    total = len(per_query)
    summary = {
        "query_count": total,
        "intersection_recall@1": hit_counts[1] / total if total else 0.0,
        "intersection_recall@5": hit_counts[5] / total if total else 0.0,
        "intersection_recall@10": hit_counts[10] / total if total else 0.0,
        "intersection_recall@20": hit_counts[20] / total if total else 0.0,
        "intersection_recall@50": hit_counts[50] / total if total else 0.0,
        "intersection_mrr": reciprocal_rank_sum / total if total else 0.0,
        "top1_error_m_mean": sum(top1_errors) / len(top1_errors) if top1_errors else None,
        "per_query": per_query,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(summary_path)
    print(curve_path)


if __name__ == "__main__":
    main()

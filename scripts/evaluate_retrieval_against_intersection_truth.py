#!/usr/bin/env python3
"""Evaluate retrieval against intersection-truth labels and export full top-k truth curves."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import faiss
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-features-npz", required=True)
    parser.add_argument("--query-seed-csv", required=True)
    parser.add_argument("--query-truth-tiles-csv", required=True)
    parser.add_argument("--faiss-index", required=True)
    parser.add_argument("--mapping-json", required=True)
    parser.add_argument("--top-k", type=int, default=0, help="Use 0 to search all tiles.")
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--curve-csv", required=True)
    return parser.parse_args()


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
    output_csv = Path(args.output_csv)
    summary_json = Path(args.summary_json)
    curve_csv = Path(args.curve_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    curve_csv.parent.mkdir(parents=True, exist_ok=True)

    qdata = np.load(args.query_features_npz, allow_pickle=True)
    qids = [str(x) for x in qdata["ids"].tolist()]
    qfeatures = qdata["features"].astype("float32")
    if qfeatures.ndim != 2 or qfeatures.shape[0] == 0:
        raise SystemExit("Query features are empty or malformed.")

    truth = load_truth(Path(args.query_seed_csv), Path(args.query_truth_tiles_csv))
    with Path(args.mapping_json).open("r", encoding="utf-8") as f:
        items = json.load(f)["items"]
    index = faiss.read_index(args.faiss_index)
    search_k = args.top_k if args.top_k > 0 else int(index.ntotal)
    scores, indices = index.search(qfeatures, search_k)

    hit_counts = {1: 0, 5: 0, 10: 0, 20: 0}
    reciprocal_rank_sum = 0.0
    top1_errors = []
    per_query = []

    with output_csv.open("w", newline="", encoding="utf-8-sig") as of, curve_csv.open("w", newline="", encoding="utf-8-sig") as cf:
        retrieval_writer = csv.writer(of)
        retrieval_writer.writerow(
            [
                "query_id", "rank", "candidate_tile_id", "score", "candidate_scale_level_m",
                "candidate_center_x", "candidate_center_y", "is_intersection_truth_hit",
            ]
        )
        curve_writer = csv.writer(cf)
        curve_writer.writerow(
            [
                "query_id", "flight_id", "k", "cumulative_truth_hits", "total_truth_count", "cumulative_truth_ratio",
            ]
        )

        for row_idx, qid in enumerate(qids):
            meta = truth[qid]
            truth_ids = meta["truth_ids"]
            truth_set = set(truth_ids)
            pred_ids: list[str] = []
            cumulative_hits = 0
            top1_error_m = None
            for rank, (score, idx) in enumerate(zip(scores[row_idx], indices[row_idx]), start=1):
                if idx < 0:
                    continue
                item = items[idx]
                md = item["metadata"]
                tile_id = item["id"]
                pred_ids.append(tile_id)
                is_truth_hit = tile_id in truth_set
                if is_truth_hit:
                    cumulative_hits += 1
                if rank == 1:
                    dx = float(md.get("center_x", 0.0)) - float(meta["query_x"])
                    dy = float(md.get("center_y", 0.0)) - float(meta["query_y"])
                    top1_error_m = math.hypot(dx, dy)
                retrieval_writer.writerow(
                    [
                        qid, rank, tile_id, float(score), md.get("tile_size_m", md.get("scale_level_m", "")),
                        md.get("center_x", ""), md.get("center_y", ""), int(is_truth_hit),
                    ]
                )
                total_truth = len(truth_ids)
                curve_writer.writerow(
                    [
                        qid, meta["flight_id"], rank, cumulative_hits, total_truth,
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
                "intersection_reciprocal_rank": 0.0,
                "top1_error_m": top1_error_m,
            }
            if q_stats["first_truth_rank"] is not None:
                q_stats["intersection_reciprocal_rank"] = 1.0 / int(q_stats["first_truth_rank"])
            per_query.append(q_stats)
            reciprocal_rank_sum += q_stats["intersection_reciprocal_rank"]
            if top1_error_m is not None:
                top1_errors.append(top1_error_m)
            for k in (1, 5, 10, 20):
                hit_counts[k] += int(q_stats[f"intersection_hit@{k}"])

    total = len(qids)
    summary = {
        "top_k": search_k,
        "query_count": total,
        "intersection_recall@1": hit_counts[1] / total if total else 0.0,
        "intersection_recall@5": hit_counts[5] / total if total else 0.0,
        "intersection_recall@10": hit_counts[10] / total if total else 0.0,
        "intersection_recall@20": hit_counts[20] / total if total else 0.0,
        "intersection_mrr": reciprocal_rank_sum / total if total else 0.0,
        "top1_error_m_mean": sum(top1_errors) / len(top1_errors) if top1_errors else None,
        "per_query": per_query,
    }
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Results saved to {output_csv}")
    print(f"Curves saved to {curve_csv}")
    print(f"Summary saved to {summary_json}")


if __name__ == "__main__":
    main()

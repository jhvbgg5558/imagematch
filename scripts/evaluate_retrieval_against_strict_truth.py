#!/usr/bin/env python3
"""Evaluate retrieval against strict-truth labels derived from refined coverage truth."""

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
    parser = argparse.ArgumentParser(description="Evaluate query retrieval against strict truth.")
    parser.add_argument("--query-features-npz", required=True)
    parser.add_argument("--query-seed-csv", required=True)
    parser.add_argument("--query-truth-tiles-csv", required=True)
    parser.add_argument("--faiss-index", required=True)
    parser.add_argument("--mapping-json", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    return parser.parse_args()


def load_truth(seed_csv: Path, truth_csv: Path) -> dict[str, dict[str, object]]:
    with seed_csv.open("r", newline="", encoding="utf-8-sig") as f:
        seed = {row["query_id"]: row for row in csv.DictReader(f)}

    strict_truth: dict[str, list[str]] = defaultdict(list)
    center_truth: dict[str, list[str]] = defaultdict(list)
    with truth_csv.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("is_strict_truth", "1") != "1":
                continue
            qid = row["query_id"]
            strict_truth[qid].append(row["tile_id"])
            if row["contains_query_center"] == "1":
                center_truth[qid].append(row["tile_id"])

    out = {}
    for qid, row in seed.items():
        out[qid] = {
            "query_x": float(row["query_x"]),
            "query_y": float(row["query_y"]),
            "strict_truth_ids": strict_truth.get(qid, []),
            "center_truth_ids": center_truth.get(qid, []),
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
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_json.parent.mkdir(parents=True, exist_ok=True)

    qdata = np.load(args.query_features_npz, allow_pickle=True)
    qids = [str(x) for x in qdata["ids"].tolist()]
    qfeatures = qdata["features"].astype("float32")
    if qfeatures.ndim != 2 or qfeatures.shape[0] == 0:
        raise SystemExit("Query features are empty or malformed.")

    truth = load_truth(Path(args.query_seed_csv), Path(args.query_truth_tiles_csv))
    with Path(args.mapping_json).open("r", encoding="utf-8") as f:
        items = json.load(f)["items"]

    index = faiss.read_index(args.faiss_index)
    scores, indices = index.search(qfeatures, args.top_k)

    strict_hit1 = strict_hit5 = strict_hit10 = 0
    center_hit1 = center_hit5 = center_hit10 = 0
    strict_rr_sum = 0.0
    top1_errors = []
    per_query = []
    truth_scale_hits: dict[str, int] = defaultdict(int)

    with output_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "query_id",
                "rank",
                "candidate_tile_id",
                "score",
                "candidate_scale_level_m",
                "candidate_center_x",
                "candidate_center_y",
                "is_strict_truth_hit",
                "is_center_strict_truth_hit",
            ]
        )
        for row_idx, qid in enumerate(qids):
            meta = truth[qid]
            strict_truth_ids = meta["strict_truth_ids"]
            center_truth_ids = meta["center_truth_ids"]
            pred_ids = []
            top1_error_m = None
            for rank, (score, idx) in enumerate(zip(scores[row_idx], indices[row_idx]), start=1):
                if idx < 0:
                    continue
                item = items[idx]
                md = item["metadata"]
                tile_id = item["id"]
                pred_ids.append(tile_id)
                strict_hit = tile_id in strict_truth_ids
                center_hit = tile_id in center_truth_ids
                if rank == 1:
                    dx = float(md.get("center_x", 0.0)) - float(meta["query_x"])
                    dy = float(md.get("center_y", 0.0)) - float(meta["query_y"])
                    top1_error_m = math.hypot(dx, dy)
                if strict_hit:
                    truth_scale_hits[md.get("tile_size_m", "")] += 1
                writer.writerow(
                    [
                        qid,
                        rank,
                        tile_id,
                        float(score),
                        md.get("scale_level_m", ""),
                        md.get("center_x", ""),
                        md.get("center_y", ""),
                        int(strict_hit),
                        int(center_hit),
                    ]
                )

            q_hit1 = hit_at_k(pred_ids, strict_truth_ids, 1)
            q_hit5 = hit_at_k(pred_ids, strict_truth_ids, 5)
            q_hit10 = hit_at_k(pred_ids, strict_truth_ids, 10)
            q_ctr1 = hit_at_k(pred_ids, center_truth_ids, 1)
            q_ctr5 = hit_at_k(pred_ids, center_truth_ids, 5)
            q_ctr10 = hit_at_k(pred_ids, center_truth_ids, 10)
            strict_rank = first_rank(pred_ids, strict_truth_ids)
            strict_rr = 0.0 if strict_rank is None else 1.0 / strict_rank

            strict_hit1 += int(q_hit1)
            strict_hit5 += int(q_hit5)
            strict_hit10 += int(q_hit10)
            center_hit1 += int(q_ctr1)
            center_hit5 += int(q_ctr5)
            center_hit10 += int(q_ctr10)
            strict_rr_sum += strict_rr
            if top1_error_m is not None:
                top1_errors.append(top1_error_m)

            per_query.append(
                {
                    "query_id": qid,
                    "strict_truth_count": len(strict_truth_ids),
                    "center_strict_truth_count": len(center_truth_ids),
                    "topk_tile_ids": pred_ids,
                    "first_strict_truth_rank": strict_rank,
                    "strict_hit@1": q_hit1,
                    "strict_hit@5": q_hit5,
                    "strict_hit@10": q_hit10,
                    "center_strict_hit@1": q_ctr1,
                    "center_strict_hit@5": q_ctr5,
                    "center_strict_hit@10": q_ctr10,
                    "strict_reciprocal_rank": strict_rr,
                    "top1_error_m": top1_error_m,
                }
            )

    total = len(qids)
    summary = {
        "top_k": args.top_k,
        "query_count": total,
        "strict_recall@1": strict_hit1 / total if total else 0.0,
        "strict_recall@5": strict_hit5 / total if total else 0.0,
        "strict_recall@10": strict_hit10 / total if total else 0.0,
        "strict_mrr": strict_rr_sum / total if total else 0.0,
        "center_strict_recall@1": center_hit1 / total if total else 0.0,
        "center_strict_recall@5": center_hit5 / total if total else 0.0,
        "center_strict_recall@10": center_hit10 / total if total else 0.0,
        "top1_error_m_mean": sum(top1_errors) / len(top1_errors) if top1_errors else None,
        "strict_hit_count@1": strict_hit1,
        "strict_hit_count@5": strict_hit5,
        "strict_hit_count@10": strict_hit10,
        "center_strict_hit_count@1": center_hit1,
        "center_strict_hit_count@5": center_hit5,
        "center_strict_hit_count@10": center_hit10,
        "truth_scale_hit_counts": dict(sorted(truth_scale_hits.items(), key=lambda kv: float(kv[0]) if kv[0] else -1)),
        "per_query": per_query,
    }
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Results saved to {output_csv}")
    print(f"Summary saved to {summary_json}")
    print(
        f"Finished. queries={total} "
        f"strict_recall@1={summary['strict_recall@1']:.3f} "
        f"strict_recall@5={summary['strict_recall@5']:.3f} "
        f"strict_recall@10={summary['strict_recall@10']:.3f} "
        f"strict_mrr={summary['strict_mrr']:.3f} "
        f"center_strict_recall@1={summary['center_strict_recall@1']:.3f}"
    )


if __name__ == "__main__":
    main()

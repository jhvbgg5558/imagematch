#!/usr/bin/env python3
"""Evaluate retrieval against coverage-based truth tables."""

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
    parser = argparse.ArgumentParser(description="Evaluate query retrieval against coverage-based truth.")
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
    coverage_truth: dict[str, list[str]] = defaultdict(list)
    center_truth: dict[str, list[str]] = defaultdict(list)
    with truth_csv.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            qid = row["query_id"]
            coverage_truth[qid].append(row["tile_id"])
            if row["contains_query_center"] == "1":
                center_truth[qid].append(row["tile_id"])
    out = {}
    for qid, row in seed.items():
        out[qid] = {
            "query_x": float(row["query_x"]),
            "query_y": float(row["query_y"]),
            "coverage_truth_ids": coverage_truth.get(qid, []),
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
        mapping = json.load(f)["items"]
    items = mapping
    index = faiss.read_index(args.faiss_index)
    scores, indices = index.search(qfeatures, args.top_k)

    cov_hit1 = cov_hit5 = cov_hit10 = 0
    ctr_hit1 = ctr_hit5 = ctr_hit10 = 0
    cov_rr_sum = 0.0
    top1_errors = []
    per_query = []

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
                "is_coverage_truth_hit",
                "is_center_truth_hit",
            ]
        )
        for row_idx, qid in enumerate(qids):
            meta = truth[qid]
            cov_truth_ids = meta["coverage_truth_ids"]
            ctr_truth_ids = meta["center_truth_ids"]
            pred_ids = []
            top1_error_m = None
            for rank, (score, idx) in enumerate(zip(scores[row_idx], indices[row_idx]), start=1):
                if idx < 0:
                    continue
                item = items[idx]
                md = item["metadata"]
                tile_id = item["id"]
                pred_ids.append(tile_id)
                cov_hit = tile_id in cov_truth_ids
                ctr_hit = tile_id in ctr_truth_ids
                if rank == 1:
                    dx = float(md.get("center_x", 0.0)) - float(meta["query_x"])
                    dy = float(md.get("center_y", 0.0)) - float(meta["query_y"])
                    top1_error_m = math.hypot(dx, dy)
                writer.writerow(
                    [
                        qid,
                        rank,
                        tile_id,
                        float(score),
                        md.get("scale_level_m", ""),
                        md.get("center_x", ""),
                        md.get("center_y", ""),
                        int(cov_hit),
                        int(ctr_hit),
                    ]
                )

            q_cov1 = hit_at_k(pred_ids, cov_truth_ids, 1)
            q_cov5 = hit_at_k(pred_ids, cov_truth_ids, 5)
            q_cov10 = hit_at_k(pred_ids, cov_truth_ids, 10)
            q_ctr1 = hit_at_k(pred_ids, ctr_truth_ids, 1)
            q_ctr5 = hit_at_k(pred_ids, ctr_truth_ids, 5)
            q_ctr10 = hit_at_k(pred_ids, ctr_truth_ids, 10)
            cov_rank = first_rank(pred_ids, cov_truth_ids)
            cov_rr = 0.0 if cov_rank is None else 1.0 / cov_rank

            cov_hit1 += int(q_cov1)
            cov_hit5 += int(q_cov5)
            cov_hit10 += int(q_cov10)
            ctr_hit1 += int(q_ctr1)
            ctr_hit5 += int(q_ctr5)
            ctr_hit10 += int(q_ctr10)
            cov_rr_sum += cov_rr
            if top1_error_m is not None:
                top1_errors.append(top1_error_m)

            per_query.append(
                {
                    "query_id": qid,
                    "coverage_truth_count": len(cov_truth_ids),
                    "center_truth_count": len(ctr_truth_ids),
                    "topk_tile_ids": pred_ids,
                    "first_coverage_truth_rank": cov_rank,
                    "coverage_hit@1": q_cov1,
                    "coverage_hit@5": q_cov5,
                    "coverage_hit@10": q_cov10,
                    "center_hit@1": q_ctr1,
                    "center_hit@5": q_ctr5,
                    "center_hit@10": q_ctr10,
                    "coverage_reciprocal_rank": cov_rr,
                    "top1_error_m": top1_error_m,
                }
            )

    total = len(qids)
    summary = {
        "top_k": args.top_k,
        "query_count": total,
        "coverage_recall@1": cov_hit1 / total if total else 0.0,
        "coverage_recall@5": cov_hit5 / total if total else 0.0,
        "coverage_recall@10": cov_hit10 / total if total else 0.0,
        "coverage_mrr": cov_rr_sum / total if total else 0.0,
        "center_recall@1": ctr_hit1 / total if total else 0.0,
        "center_recall@5": ctr_hit5 / total if total else 0.0,
        "center_recall@10": ctr_hit10 / total if total else 0.0,
        "top1_error_m_mean": sum(top1_errors) / len(top1_errors) if top1_errors else None,
        "coverage_hit_count@1": cov_hit1,
        "coverage_hit_count@5": cov_hit5,
        "coverage_hit_count@10": cov_hit10,
        "center_hit_count@1": ctr_hit1,
        "center_hit_count@5": ctr_hit5,
        "center_hit_count@10": ctr_hit10,
        "per_query": per_query,
    }
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Results saved to {output_csv}")
    print(f"Summary saved to {summary_json}")
    print(
        f"Finished. queries={total} "
        f"coverage_recall@1={summary['coverage_recall@1']:.3f} "
        f"coverage_recall@5={summary['coverage_recall@5']:.3f} "
        f"coverage_recall@10={summary['coverage_recall@10']:.3f} "
        f"coverage_mrr={summary['coverage_mrr']:.3f} "
        f"center_recall@1={summary['center_recall@1']:.3f}"
    )


if __name__ == "__main__":
    main()

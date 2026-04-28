#!/usr/bin/env python3
"""Run FAISS retrieval for query features and evaluate against query truth tables."""

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
    parser = argparse.ArgumentParser(description="Evaluate query retrieval against fixed-library truth tables.")
    parser.add_argument("--query-features-npz", required=True)
    parser.add_argument("--query-seed-csv", required=True)
    parser.add_argument("--query-truth-tiles-csv", required=True)
    parser.add_argument("--faiss-index", required=True)
    parser.add_argument("--mapping-json", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    return parser.parse_args()


def load_query_info(seed_csv: Path, truth_tiles_csv: Path) -> dict[str, dict[str, object]]:
    with seed_csv.open("r", newline="", encoding="utf-8-sig") as f:
        seed_rows = {row["query_id"]: row for row in csv.DictReader(f)}

    truth_ids: dict[str, list[str]] = defaultdict(list)
    with truth_tiles_csv.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            truth_ids[row["query_id"]].append(row["tile_id"])

    out: dict[str, dict[str, object]] = {}
    for query_id, row in seed_rows.items():
        out[query_id] = {
            "row": row,
            "truth_tile_ids": truth_ids.get(query_id, []),
            "query_x": float(row["query_x"]),
            "query_y": float(row["query_y"]),
        }
    return out


def hit_at_k(pred_ids: list[str], truth_ids: list[str], k: int) -> bool:
    truth = set(truth_ids)
    return any(pid in truth for pid in pred_ids[:k])


def first_truth_rank(pred_ids: list[str], truth_ids: list[str]) -> int | None:
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

    query_info = load_query_info(Path(args.query_seed_csv), Path(args.query_truth_tiles_csv))

    with Path(args.mapping_json).open("r", encoding="utf-8") as f:
        mapping = json.load(f)
    items = mapping["items"]

    index = faiss.read_index(args.faiss_index)
    scores, indices = index.search(qfeatures, args.top_k)

    per_query = []
    hit1 = hit5 = hit10 = 0
    reciprocal_rank_sum = 0.0
    top1_errors = []
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
                "is_truth_hit",
            ]
        )

        for row_idx, qid in enumerate(qids):
            meta = query_info.get(qid)
            if meta is None:
                raise SystemExit(f"Missing query metadata for {qid}")
            truth_ids = meta["truth_tile_ids"]
            pred_ids = []
            top1_error_m = None

            for rank, (score, idx) in enumerate(zip(scores[row_idx], indices[row_idx]), start=1):
                if idx < 0:
                    continue
                item = items[idx]
                md = item["metadata"]
                tile_id = item["id"]
                pred_ids.append(tile_id)
                is_hit = tile_id in truth_ids
                if rank == 1:
                    dx = float(md.get("center_x", 0.0)) - float(meta["query_x"])
                    dy = float(md.get("center_y", 0.0)) - float(meta["query_y"])
                    top1_error_m = math.hypot(dx, dy)
                if is_hit:
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
                        int(is_hit),
                    ]
                )

            q_hit1 = hit_at_k(pred_ids, truth_ids, 1)
            q_hit5 = hit_at_k(pred_ids, truth_ids, 5)
            q_hit10 = hit_at_k(pred_ids, truth_ids, 10)
            rr_rank = first_truth_rank(pred_ids, truth_ids)
            reciprocal_rank = 0.0 if rr_rank is None else 1.0 / rr_rank
            hit1 += int(q_hit1)
            hit5 += int(q_hit5)
            hit10 += int(q_hit10)
            reciprocal_rank_sum += reciprocal_rank
            if top1_error_m is not None:
                top1_errors.append(top1_error_m)

            per_query.append(
                {
                    "query_id": qid,
                    "truth_tile_count": len(truth_ids),
                    "topk_tile_ids": pred_ids,
                    "first_truth_rank": rr_rank,
                    "hit@1": q_hit1,
                    "hit@5": q_hit5,
                    "hit@10": q_hit10,
                    "reciprocal_rank": reciprocal_rank,
                    "top1_error_m": top1_error_m,
                }
            )

    total = len(qids)
    summary = {
        "top_k": args.top_k,
        "query_count": total,
        "recall@1": hit1 / total if total else 0.0,
        "recall@5": hit5 / total if total else 0.0,
        "recall@10": hit10 / total if total else 0.0,
        "mrr": reciprocal_rank_sum / total if total else 0.0,
        "top1_error_m_mean": sum(top1_errors) / len(top1_errors) if top1_errors else None,
        "hit_count@1": hit1,
        "hit_count@5": hit5,
        "hit_count@10": hit10,
        "truth_scale_hit_counts": dict(sorted(truth_scale_hits.items(), key=lambda kv: float(kv[0]) if kv[0] else -1)),
        "per_query": per_query,
    }
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Results saved to {output_csv}")
    print(f"Summary saved to {summary_json}")
    print(
        f"Finished. queries={total} "
        f"recall@1={summary['recall@1']:.3f} "
        f"recall@5={summary['recall@5']:.3f} "
        f"recall@10={summary['recall@10']:.3f} "
        f"mrr={summary['mrr']:.3f} "
        f"top1_error_m_mean={summary['top1_error_m_mean'] if summary['top1_error_m_mean'] is not None else 'na'}"
    )


if __name__ == "__main__":
    main()

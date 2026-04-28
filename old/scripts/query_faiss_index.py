#!/usr/bin/env python3
"""Run FAISS retrieval for query images and compute hit statistics."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import faiss
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query FAISS index with DINOv2 query features.")
    parser.add_argument("--query-features-npz", required=True, help="Query feature NPZ.")
    parser.add_argument("--query-metadata-csv", required=True, help="Query metadata CSV.")
    parser.add_argument("--faiss-index", required=True, help="FAISS index path.")
    parser.add_argument("--mapping-json", required=True, help="Index mapping JSON.")
    parser.add_argument("--query-id-column", default="query_id", help="Query id column.")
    parser.add_argument("--top-k", type=int, default=10, help="Top-K retrieval depth.")
    parser.add_argument("--output-csv", required=True, help="Retrieval results CSV.")
    parser.add_argument("--summary-json", required=True, help="Summary metrics JSON.")
    return parser.parse_args()


def load_query_truth(path: Path, query_id_column: str) -> dict[str, dict[str, object]]:
    out = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            truth_ids = [x for x in row.get("truth_tile_ids", "").split("|") if x]
            out[row[query_id_column]] = {
                "row": row,
                "truth_tile_ids": truth_ids,
                "center_x": float(row.get("center_x", 0.0) or 0.0),
                "center_y": float(row.get("center_y", 0.0) or 0.0),
            }
    return out


def hit_at_k(pred_ids: list[str], truth_ids: list[str], k: int) -> bool:
    truth = set(truth_ids)
    return any(pid in truth for pid in pred_ids[:k])


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

    query_truth = load_query_truth(Path(args.query_metadata_csv), args.query_id_column)

    with Path(args.mapping_json).open("r", encoding="utf-8") as f:
        mapping = json.load(f)
    items = mapping["items"]

    index = faiss.read_index(args.faiss_index)
    scores, indices = index.search(qfeatures, args.top_k)

    per_query = []
    total = len(qids)
    hit1 = hit5 = hit10 = 0
    reciprocal_rank_sum = 0.0
    top1_errors = []

    with output_csv.open("w", newline="", encoding="utf-8") as f:
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
            query_meta = query_truth.get(qid, {})
            truth_ids = query_meta.get("truth_tile_ids", [])
            pred_ids = []
            first_hit_rank = None
            top1_error_m = None
            for rank, (score, idx) in enumerate(zip(scores[row_idx], indices[row_idx]), start=1):
                if idx < 0:
                    continue
                item = items[idx]
                metadata = item["metadata"]
                tile_id = item["id"]
                pred_ids.append(tile_id)
                is_hit = tile_id in truth_ids
                if first_hit_rank is None and is_hit:
                    first_hit_rank = rank
                if rank == 1:
                    try:
                        dx = float(metadata.get("center_x", 0.0)) - float(query_meta.get("center_x", 0.0))
                        dy = float(metadata.get("center_y", 0.0)) - float(query_meta.get("center_y", 0.0))
                        top1_error_m = math.hypot(dx, dy)
                    except (TypeError, ValueError):
                        top1_error_m = None
                writer.writerow(
                    [
                        qid,
                        rank,
                        tile_id,
                        float(score),
                        metadata.get("scale_level_m", ""),
                        metadata.get("center_x", ""),
                        metadata.get("center_y", ""),
                        int(is_hit),
                    ]
                )

            q_hit1 = hit_at_k(pred_ids, truth_ids, 1)
            q_hit5 = hit_at_k(pred_ids, truth_ids, 5)
            q_hit10 = hit_at_k(pred_ids, truth_ids, 10)
            hit1 += int(q_hit1)
            hit5 += int(q_hit5)
            hit10 += int(q_hit10)
            reciprocal_rank = 0.0 if first_hit_rank is None else 1.0 / first_hit_rank
            reciprocal_rank_sum += reciprocal_rank
            if top1_error_m is not None:
                top1_errors.append(top1_error_m)
            per_query.append(
                {
                    "query_id": qid,
                    "truth_tile_ids": truth_ids,
                    "topk_tile_ids": pred_ids,
                    "hit@1": q_hit1,
                    "hit@5": q_hit5,
                    "hit@10": q_hit10,
                    "reciprocal_rank": reciprocal_rank,
                    "top1_error_m": top1_error_m,
                }
            )

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

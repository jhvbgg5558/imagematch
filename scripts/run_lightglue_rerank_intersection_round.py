#!/usr/bin/env python3
"""Batch-run intersection-truth LightGlue reranking and record stage timing."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-round-root", required=True)
    parser.add_argument("--tiles-csv", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--max-num-keypoints", type=int, default=256)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--min-inliers", type=int, default=5)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.5)
    parser.add_argument("--promotion-rank-gate", type=int, default=5)
    parser.add_argument("--ranking-mode", choices=["gate_only", "fused"], default="fused")
    parser.add_argument("--global-weight", type=float, default=0.4)
    parser.add_argument("--geom-weight", type=float, default=0.6)
    parser.add_argument("--valid-bonus", type=float, default=0.1)
    parser.add_argument("--promotion-bonus", type=float, default=0.05)
    parser.add_argument("--timing-json", required=True)
    return parser.parse_args()


def run_timed(cmd: list[str]) -> float:
    print("+", " ".join(cmd))
    start = time.perf_counter()
    subprocess.run(cmd, check=True)
    return time.perf_counter() - start


def main() -> None:
    args = parse_args()
    input_root = Path(args.input_round_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    script_path = Path(__file__).resolve().parent / "rerank_with_lightglue_intersection.py"
    stage3_root = input_root / "stage3"
    stage7_root = out_root / "stage7"
    stage7_root.mkdir(parents=True, exist_ok=True)

    aggregate = []
    flight_timings = []
    total_rerank_seconds = 0.0
    for query_dir in sorted(stage3_root.iterdir()):
        if not query_dir.is_dir():
            continue
        flight_id = query_dir.name
        retrieval_csv = input_root / "stage4" / flight_id / f"retrieval_top{args.top_k}.csv"
        if not retrieval_csv.exists():
            raise SystemExit(f"Missing retrieval CSV: {retrieval_csv}")

        flight_out = stage7_root / flight_id
        flight_out.mkdir(parents=True, exist_ok=True)
        reranked_csv = flight_out / f"reranked_top{args.top_k}.csv"
        metrics_csv = flight_out / "per_query_geom_metrics.csv"
        summary_json = flight_out / f"rerank_top{args.top_k}.json"

        cmd = [
            args.python_bin,
            str(script_path),
            "--query-metadata-csv", str(query_dir / "queries.csv"),
            "--retrieval-csv", str(retrieval_csv),
            "--tiles-csv", args.tiles_csv,
            "--output-csv", str(reranked_csv),
            "--metrics-csv", str(metrics_csv),
            "--summary-json", str(summary_json),
            "--top-k", str(args.top_k),
            "--max-num-keypoints", str(args.max_num_keypoints),
            "--device", args.device,
            "--min-inliers", str(args.min_inliers),
            "--min-inlier-ratio", str(args.min_inlier_ratio),
            "--promotion-rank-gate", str(args.promotion_rank_gate),
            "--ranking-mode", str(args.ranking_mode),
            "--global-weight", str(args.global_weight),
            "--geom-weight", str(args.geom_weight),
            "--valid-bonus", str(args.valid_bonus),
            "--promotion-bonus", str(args.promotion_bonus),
        ]
        elapsed = run_timed(cmd)
        total_rerank_seconds += elapsed
        summary = json.loads(summary_json.read_text(encoding="utf-8"))
        aggregate.append(
            {
                "flight_id": flight_id,
                "query_count": summary["query_count"],
                "intersection_recall@1": summary["intersection_recall@1"],
                "intersection_recall@5": summary["intersection_recall@5"],
                "intersection_recall@10": summary["intersection_recall@10"],
                "intersection_recall@20": summary["intersection_recall@20"],
                "intersection_recall@50": summary["intersection_recall@50"],
                "intersection_mrr": summary["intersection_mrr"],
                "top1_error_m_mean": summary["top1_error_m_mean"],
            }
        )
        flight_timings.append({"flight_id": flight_id, "elapsed_seconds": elapsed})

    (out_root / "aggregate_summary.json").write_text(json.dumps({"flights": aggregate}, ensure_ascii=False, indent=2), encoding="utf-8")
    timing_payload = {
        "stage": "lightglue_rerank",
        "top_k": args.top_k,
        "elapsed_seconds": total_rerank_seconds,
        "per_flight": flight_timings,
    }
    timing_json = Path(args.timing_json)
    timing_json.parent.mkdir(parents=True, exist_ok=True)
    timing_json.write_text(json.dumps(timing_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Aggregate JSON saved to {out_root / 'aggregate_summary.json'}")
    print(f"Timing JSON saved to {timing_json}")


if __name__ == "__main__":
    main()

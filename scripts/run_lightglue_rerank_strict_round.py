#!/usr/bin/env python3
"""Batch-run strict-truth LightGlue reranking on a prepared current-task round."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-round-root", required=True)
    parser.add_argument("--tiles-csv", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--top-k", type=int, default=20)
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
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    input_root = Path(args.input_round_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    script_path = Path(__file__).resolve().parent / "rerank_with_lightglue_strict.py"
    stage3_root = input_root / "stage3"
    stage7_root = out_root / "stage7"
    stage7_root.mkdir(parents=True, exist_ok=True)

    aggregate = []
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
        analysis_md = flight_out / "analysis.md"

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
            "--ranking-mode", args.ranking_mode,
            "--global-weight", str(args.global_weight),
            "--geom-weight", str(args.geom_weight),
            "--valid-bonus", str(args.valid_bonus),
            "--promotion-bonus", str(args.promotion_bonus),
        ]
        run(cmd)

        summary = json.loads(summary_json.read_text(encoding="utf-8"))
        aggregate.append(
            {
                "flight_id": flight_id,
                "query_count": summary["query_count"],
                "strict_recall@1": summary["strict_recall@1"],
                "strict_recall@5": summary["strict_recall@5"],
                "strict_recall@10": summary["strict_recall@10"],
                "strict_recall@20": summary["strict_recall@20"],
                "strict_mrr": summary["strict_mrr"],
                "top1_error_m_mean": summary["top1_error_m_mean"],
            }
        )
        analysis_md.write_text(
            "\n".join(
                [
                    "# LightGlue Rerank Analysis",
                    "",
                    f"- Flight: {flight_id}",
                    f"- Query count: {summary['query_count']}",
                    f"- Strict Recall@1: {summary['strict_recall@1']:.3f}",
                    f"- Strict Recall@5: {summary['strict_recall@5']:.3f}",
                    f"- Strict Recall@10: {summary['strict_recall@10']:.3f}",
                    f"- Strict Recall@20: {summary['strict_recall@20']:.3f}",
                    f"- Strict MRR: {summary['strict_mrr']:.3f}",
                    f"- Top-1 error mean (m): {summary['top1_error_m_mean'] if summary['top1_error_m_mean'] is not None else 'na'}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    aggregate_json = out_root / "aggregate_summary.json"
    aggregate_md = out_root / "aggregate_summary.md"
    aggregate_json.write_text(json.dumps({"flights": aggregate}, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# LightGlue Rerank Strict Summary", ""]
    for item in aggregate:
        lines.extend(
            [
                f"## {item['flight_id']}",
                f"- Query count: {item['query_count']}",
                f"- Strict Recall@1: {item['strict_recall@1']:.3f}",
                f"- Strict Recall@5: {item['strict_recall@5']:.3f}",
                f"- Strict Recall@10: {item['strict_recall@10']:.3f}",
                f"- Strict Recall@20: {item['strict_recall@20']:.3f}",
                f"- Strict MRR: {item['strict_mrr']:.3f}",
                f"- Top-1 error mean (m): {item['top1_error_m_mean'] if item['top1_error_m_mean'] is not None else 'na'}",
                "",
            ]
        )
    aggregate_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Aggregate JSON saved to {aggregate_json}")
    print(f"Aggregate markdown saved to {aggregate_md}")


if __name__ == "__main__":
    main()

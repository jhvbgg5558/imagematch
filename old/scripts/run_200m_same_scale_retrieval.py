#!/usr/bin/env python3
"""Run strict 200m same-scale retrieval using prepared assets."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exp-root", required=True)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--top-k", type=int, default=10)
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    exp_root = Path(args.exp_root)
    stage3_root = exp_root / "stage3"
    stage4_root = exp_root / "stage4"
    stage7_root = exp_root / "stage7"
    stage7_root.mkdir(parents=True, exist_ok=True)

    scripts_dir = Path("/mnt/d/aiproject/imagematch/scripts")
    aggregate = []
    for query_dir in sorted(stage3_root.iterdir()):
        if not query_dir.is_dir():
            continue
        flight_id = query_dir.name
        stage4_dir = stage4_root / flight_id
        stage7_dir = stage7_root / flight_id
        stage7_dir.mkdir(parents=True, exist_ok=True)

        retrieval_csv = stage4_dir / f"retrieval_top{args.top_k}.csv"
        retrieval_json = stage4_dir / f"retrieval_top{args.top_k}.json"
        analysis_json = stage7_dir / "analysis.json"
        analysis_md = stage7_dir / "analysis.md"

        run(
            [
                args.python_bin,
                str(scripts_dir / "query_faiss_index.py"),
                "--query-features-npz",
                str(stage4_dir / "query_features.npz"),
                "--query-metadata-csv",
                str(query_dir / "queries.csv"),
                "--faiss-index",
                str(exp_root / "stage2" / "satellite_tiles_200m_ip.index"),
                "--mapping-json",
                str(exp_root / "stage2" / "satellite_tiles_200m_mapping.json"),
                "--query-id-column",
                "query_id",
                "--top-k",
                str(args.top_k),
                "--output-csv",
                str(retrieval_csv),
                "--summary-json",
                str(retrieval_json),
            ]
        )

        run(
            [
                args.python_bin,
                str(scripts_dir / "analyze_retrieval_results.py"),
                "--query-metadata-csv",
                str(query_dir / "queries.csv"),
                "--retrieval-summary-json",
                str(retrieval_json),
                "--output-json",
                str(analysis_json),
                "--output-md",
                str(analysis_md),
            ]
        )
        analysis = json.loads(analysis_json.read_text(encoding="utf-8"))
        aggregate.append(
            {
                "flight_id": flight_id,
                "query_count": analysis["overall"]["query_count"],
                "recall@1": analysis["overall"]["recall@1"],
                "recall@5": analysis["overall"]["recall@5"],
                "recall@10": analysis["overall"]["recall@10"],
                "mrr": analysis["overall"]["mrr"],
                "top1_error_m_mean": analysis["overall"]["top1_error_m_mean"],
                "per_scale": analysis["per_scale"],
            }
        )

    (exp_root / "aggregate_summary.json").write_text(
        json.dumps({"flights": aggregate}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = ["# Strict 200m Same-Scale Summary", ""]
    for item in aggregate:
        lines.extend(
            [
                f"## {item['flight_id']}",
                f"- Query count: {item['query_count']}",
                f"- Recall@1: {item['recall@1']:.3f}",
                f"- Recall@5: {item['recall@5']:.3f}",
                f"- Recall@10: {item['recall@10']:.3f}",
                f"- MRR: {item['mrr']:.3f}",
                f"- Top-1 error mean (m): {item['top1_error_m_mean'] if item['top1_error_m_mean'] is not None else 'na'}",
                "",
            ]
        )
    (exp_root / "aggregate_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Aggregate summary written to {exp_root}")


if __name__ == "__main__":
    main()

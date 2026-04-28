#!/usr/bin/env python3
"""Analyze stage4 retrieval results and export stage7 summary tables."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze retrieval results for stage7 reporting.")
    parser.add_argument("--query-metadata-csv", required=True, help="Stage3 query metadata CSV.")
    parser.add_argument("--retrieval-summary-json", required=True, help="Stage4 summary JSON.")
    parser.add_argument("--output-json", required=True, help="Stage7 analysis JSON.")
    parser.add_argument("--output-md", required=True, help="Stage7 markdown summary.")
    return parser.parse_args()


def load_query_scales(path: Path) -> dict[str, float]:
    out = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out[row["query_id"]] = float(row["scale_m"])
    return out


def main() -> None:
    args = parse_args()
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    query_scales = load_query_scales(Path(args.query_metadata_csv))
    with Path(args.retrieval_summary_json).open("r", encoding="utf-8") as f:
        summary = json.load(f)

    per_scale = defaultdict(list)
    top1_hits = []
    top5_only = []
    for item in summary["per_query"]:
        qid = item["query_id"]
        scale = query_scales.get(qid)
        if scale is None:
            continue
        per_scale[scale].append(item)
        if item["hit@1"]:
            top1_hits.append(qid)
        elif item["hit@5"]:
            top5_only.append(qid)

    scale_stats = {}
    for scale, items in sorted(per_scale.items()):
        n = len(items)
        scale_stats[str(int(scale))] = {
            "query_count": n,
            "recall@1": sum(int(x["hit@1"]) for x in items) / n if n else 0.0,
            "recall@5": sum(int(x["hit@5"]) for x in items) / n if n else 0.0,
            "recall@10": sum(int(x["hit@10"]) for x in items) / n if n else 0.0,
            "mrr": sum(float(x.get("reciprocal_rank", 0.0)) for x in items) / n if n else 0.0,
            "top1_error_m_mean": (
                sum(float(x["top1_error_m"]) for x in items if x.get("top1_error_m") is not None)
                / sum(1 for x in items if x.get("top1_error_m") is not None)
                if any(x.get("top1_error_m") is not None for x in items)
                else None
            ),
            "top1_hit_queries": [x["query_id"] for x in items if x["hit@1"]],
            "top5_only_queries": [x["query_id"] for x in items if (not x["hit@1"]) and x["hit@5"]],
        }

    report = {
        "overall": {
            "query_count": summary["query_count"],
            "recall@1": summary["recall@1"],
            "recall@5": summary["recall@5"],
            "recall@10": summary["recall@10"],
            "mrr": summary.get("mrr", 0.0),
            "top1_error_m_mean": summary.get("top1_error_m_mean"),
        },
        "per_scale": scale_stats,
        "top1_hit_queries": top1_hits,
        "top5_only_queries": top5_only,
    }

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    lines = [
        "# Stage7 First-Round Analysis",
        "",
        "## Overall",
        f"- Query count: {summary['query_count']}",
        f"- Recall@1: {summary['recall@1']:.3f}",
        f"- Recall@5: {summary['recall@5']:.3f}",
        f"- Recall@10: {summary['recall@10']:.3f}",
        f"- MRR: {summary.get('mrr', 0.0):.3f}",
        f"- Top-1 error mean (m): {summary.get('top1_error_m_mean') if summary.get('top1_error_m_mean') is not None else 'na'}",
        "",
        "## Per Scale",
    ]
    for scale, stats in scale_stats.items():
        lines.extend(
            [
                f"- {scale}m: queries={stats['query_count']} "
                f"R@1={stats['recall@1']:.3f} "
                f"R@5={stats['recall@5']:.3f} "
                f"R@10={stats['recall@10']:.3f} "
                f"MRR={stats['mrr']:.3f} "
                f"Top1Err={stats['top1_error_m_mean'] if stats['top1_error_m_mean'] is not None else 'na'}",
            ]
        )
    lines.extend(
        [
            "",
            "## Hit Breakdown",
            f"- Top1 hit queries: {', '.join(top1_hits) if top1_hits else 'none'}",
            f"- Top5-only hit queries: {', '.join(top5_only) if top5_only else 'none'}",
        ]
    )
    with output_md.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Analysis JSON saved to {output_json}")
    print(f"Analysis markdown saved to {output_md}")
    print("Finished.")


if __name__ == "__main__":
    main()

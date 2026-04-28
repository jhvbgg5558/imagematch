#!/usr/bin/env python3
"""Summarize three-scale vs four-scale retrieval results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize three-scale vs four-scale retrieval outputs.")
    parser.add_argument("--three-scale-summary", required=True)
    parser.add_argument("--four-scale-summary", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    return parser.parse_args()


def load_summary(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_per_query_map(summary: dict) -> dict[str, dict]:
    return {row["query_id"]: row for row in summary["per_query"]}


def main() -> None:
    args = parse_args()
    three = load_summary(args.three_scale_summary)
    four = load_summary(args.four_scale_summary)
    three_map = build_per_query_map(three)
    four_map = build_per_query_map(four)

    improved = []
    degraded = []
    unchanged = []
    new_top1 = []
    for query_id in sorted(four_map):
        row4 = four_map[query_id]
        row3 = three_map[query_id]
        r3 = row3["first_truth_rank"] or 999999
        r4 = row4["first_truth_rank"] or 999999
        item = {
            "query_id": query_id,
            "three_scale_first_truth_rank": row3["first_truth_rank"],
            "four_scale_first_truth_rank": row4["first_truth_rank"],
        }
        if r4 < r3:
            improved.append(item)
        elif r4 > r3:
            degraded.append(item)
        else:
            unchanged.append(item)
        if row4["hit@1"] and not row3["hit@1"]:
            new_top1.append(item)

    summary = {
        "three_scale_metrics": {
            "recall@1": three["recall@1"],
            "recall@5": three["recall@5"],
            "recall@10": three["recall@10"],
            "mrr": three["mrr"],
            "top1_error_m_mean": three["top1_error_m_mean"],
        },
        "four_scale_metrics": {
            "recall@1": four["recall@1"],
            "recall@5": four["recall@5"],
            "recall@10": four["recall@10"],
            "mrr": four["mrr"],
            "top1_error_m_mean": four["top1_error_m_mean"],
        },
        "metric_deltas": {
            "recall@1": four["recall@1"] - three["recall@1"],
            "recall@5": four["recall@5"] - three["recall@5"],
            "recall@10": four["recall@10"] - three["recall@10"],
            "mrr": four["mrr"] - three["mrr"],
            "top1_error_m_mean": (
                None
                if three["top1_error_m_mean"] is None or four["top1_error_m_mean"] is None
                else four["top1_error_m_mean"] - three["top1_error_m_mean"]
            ),
        },
        "improved_query_count": len(improved),
        "degraded_query_count": len(degraded),
        "unchanged_query_count": len(unchanged),
        "new_top1_hits_with_300m": new_top1,
        "improved_queries": improved,
        "degraded_queries": degraded,
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with output_md.open("w", encoding="utf-8") as f:
        f.write("# DINOv2 三尺度 vs 四尺度对比\n\n")
        f.write("| metric | three_scale | four_scale | delta |\n")
        f.write("| --- | --- | --- | --- |\n")
        for metric in ["recall@1", "recall@5", "recall@10", "mrr", "top1_error_m_mean"]:
            f.write(
                f"| {metric} | {summary['three_scale_metrics'][metric]} | "
                f"{summary['four_scale_metrics'][metric]} | {summary['metric_deltas'][metric]} |\n"
            )
        f.write("\n")
        f.write(f"- improved queries: {len(improved)}\n")
        f.write(f"- degraded queries: {len(degraded)}\n")
        f.write(f"- unchanged queries: {len(unchanged)}\n")
        f.write(f"- new top1 hits with 300m: {len(new_top1)}\n")

    print(f"Comparison summary JSON: {output_json}")
    print(f"Comparison summary Markdown: {output_md}")


if __name__ == "__main__":
    main()

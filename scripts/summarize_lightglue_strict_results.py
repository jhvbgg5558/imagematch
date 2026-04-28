#!/usr/bin/env python3
"""Aggregate LightGlue strict rerank outputs into overall and per-query comparison assets."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-result-dir", required=True)
    parser.add_argument("--lightglue-result-dir", required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def short_flight_name(flight_id: str) -> str:
    parts = flight_id.split("_")
    return parts[2] if len(parts) >= 3 else flight_id


def coarse_recall_at_k(summary: dict, k: int) -> float:
    key = f"strict_recall@{k}"
    if key in summary:
        return float(summary[key])
    rows = summary.get("per_query", [])
    if not rows:
        return 0.0
    hit_key = f"strict_hit@{k}"
    hits = 0
    for row in rows:
        if hit_key in row:
            hits += int(bool(row.get(hit_key, False)))
            continue
        first_rank = row.get("first_strict_truth_rank")
        hits += int(first_rank is not None and int(first_rank) <= k)
    return hits / len(rows)


def hit_at_k(row: dict, k: int) -> int:
    key = f"strict_hit@{k}"
    if key in row:
        return int(bool(row[key]))
    first_rank = row.get("first_strict_truth_rank")
    return int(first_rank is not None and int(first_rank) <= k)


def main() -> None:
    args = parse_args()
    baseline_dir = Path(args.baseline_result_dir)
    lightglue_dir = Path(args.lightglue_result_dir)

    baseline_summary = load_json(baseline_dir / "retrieval" / "summary.json")
    baseline_seed = {row["query_id"]: row for row in load_csv(baseline_dir / "query_truth" / "queries_truth_seed.csv")}
    coarse_summary = load_json(lightglue_dir / "coarse" / "summary_top20.json")
    coarse_per_query = {row["query_id"]: row for row in coarse_summary["per_query"]}
    aggregate = load_json(lightglue_dir / "aggregate_summary.json")

    lg_per_query: dict[str, dict] = {}
    per_flight = []
    weighted = {"strict_recall@1": 0.0, "strict_recall@5": 0.0, "strict_recall@10": 0.0, "strict_recall@20": 0.0, "strict_mrr": 0.0, "top1_error_m_mean": 0.0}
    total_q = 0
    for item in aggregate["flights"]:
        qcount = int(item["query_count"])
        total_q += qcount
        for key in weighted:
            weighted[key] += float(item[key]) * qcount
        flight_id = item["flight_id"]
        per_flight.append(
            {
                "flight_id": flight_id,
                "flight_tag": short_flight_name(flight_id),
                "baseline_strict_recall@1": "",
                "baseline_strict_recall@5": "",
                "baseline_strict_recall@10": "",
                "baseline_strict_mrr": "",
                "lightglue_strict_recall@1": f"{float(item['strict_recall@1']):.6f}",
                "lightglue_strict_recall@5": f"{float(item['strict_recall@5']):.6f}",
                "lightglue_strict_recall@10": f"{float(item['strict_recall@10']):.6f}",
                "lightglue_strict_recall@20": f"{float(item['strict_recall@20']):.6f}",
                "lightglue_strict_mrr": f"{float(item['strict_mrr']):.6f}",
                "lightglue_top1_error_m_mean": f"{float(item['top1_error_m_mean']):.6f}",
            }
        )
        flight_summary = load_json(lightglue_dir / "stage7" / flight_id / "rerank_top20.json")
        for row in flight_summary["per_query"]:
            lg_per_query[row["query_id"]] = row

    by_flight_baseline = defaultdict(list)
    for row in baseline_summary["per_query"]:
        by_flight_baseline[baseline_seed[row["query_id"]]["flight_id"]].append(row)
    for row in per_flight:
        b_rows = by_flight_baseline[row["flight_id"]]
        qcount = len(b_rows)
        row["baseline_strict_recall@1"] = f"{sum(int(r['strict_hit@1']) for r in b_rows) / qcount:.6f}"
        row["baseline_strict_recall@5"] = f"{sum(int(r['strict_hit@5']) for r in b_rows) / qcount:.6f}"
        row["baseline_strict_recall@10"] = f"{sum(int(r['strict_hit@10']) for r in b_rows) / qcount:.6f}"
        row["baseline_strict_mrr"] = f"{sum(float(r['strict_reciprocal_rank']) for r in b_rows) / qcount:.6f}"

    overall = {
        "query_count": total_q,
        "baseline_strict_recall@1": float(baseline_summary["strict_recall@1"]),
        "baseline_strict_recall@5": float(baseline_summary["strict_recall@5"]),
        "baseline_strict_recall@10": float(baseline_summary["strict_recall@10"]),
        "baseline_strict_mrr": float(baseline_summary["strict_mrr"]),
        "baseline_top1_error_m_mean": float(baseline_summary["top1_error_m_mean"]),
        "coarse_strict_recall@20": coarse_recall_at_k(coarse_summary, 20),
        "lightglue_strict_recall@1": weighted["strict_recall@1"] / total_q,
        "lightglue_strict_recall@5": weighted["strict_recall@5"] / total_q,
        "lightglue_strict_recall@10": weighted["strict_recall@10"] / total_q,
        "lightglue_strict_recall@20": weighted["strict_recall@20"] / total_q,
        "lightglue_strict_mrr": weighted["strict_mrr"] / total_q,
        "lightglue_top1_error_m_mean": weighted["top1_error_m_mean"] / total_q,
    }
    overall["delta_strict_recall@1"] = overall["lightglue_strict_recall@1"] - overall["baseline_strict_recall@1"]
    overall["delta_strict_recall@5"] = overall["lightglue_strict_recall@5"] - overall["baseline_strict_recall@5"]
    overall["delta_strict_recall@10"] = overall["lightglue_strict_recall@10"] - overall["baseline_strict_recall@10"]
    overall["delta_strict_mrr"] = overall["lightglue_strict_mrr"] - overall["baseline_strict_mrr"]

    (lightglue_dir / "overall_summary.json").write_text(json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8")

    comparison_rows = []
    for b_row in baseline_summary["per_query"]:
        qid = b_row["query_id"]
        lg_row = lg_per_query[qid]
        coarse_row = coarse_per_query[qid]
        baseline_rank = b_row["first_strict_truth_rank"]
        lg_rank = lg_row["first_strict_truth_rank"]
        comparison_rows.append(
            {
                "query_id": qid,
                "flight_id": baseline_seed[qid]["flight_id"],
                "baseline_first_strict_truth_rank": "" if baseline_rank is None else baseline_rank,
                "baseline_strict_hit@10": int(b_row["strict_hit@10"]),
                "coarse_first_strict_truth_rank": "" if coarse_row["first_strict_truth_rank"] is None else coarse_row["first_strict_truth_rank"],
                "coarse_strict_hit@10": hit_at_k(coarse_row, 10),
                "coarse_strict_hit@20": hit_at_k(coarse_row, 20),
                "lightglue_first_strict_truth_rank": "" if lg_rank is None else lg_rank,
                "lightglue_strict_hit@10": int(lg_row["strict_hit@10"]),
                "lightglue_strict_hit@20": int(lg_row["strict_hit@20"]),
                "promoted_11_20_to_top10": int(
                    coarse_row["first_strict_truth_rank"] is not None
                    and 11 <= coarse_row["first_strict_truth_rank"] <= 20
                    and bool(lg_row["strict_hit@10"])
                ),
            }
        )
    write_csv(lightglue_dir / "per_query_comparison.csv", comparison_rows)
    write_csv(lightglue_dir / "per_flight_comparison.csv", per_flight)
    print(f"Summary assets written to {lightglue_dir}")


if __name__ == "__main__":
    main()

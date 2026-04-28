#!/usr/bin/env python3
"""Plot full-library top-k truth-count curves and k_full_truth stats."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


FLIGHT_COLORS = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curve-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def group_by_query(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        out[row["query_id"]].append(row)
    for qrows in out.values():
        qrows.sort(key=lambda r: int(r["k"]))
    return out


def mean_curve(rows: list[dict[str, str]], value_key: str) -> tuple[list[int], list[float]]:
    by_k: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        by_k[int(row["k"])].append(float(row[value_key]))
    ks = sorted(by_k)
    vals = [sum(by_k[k]) / len(by_k[k]) for k in ks]
    return ks, vals


def k_full_truth_for_query(qrows: list[dict[str, str]]) -> int | None:
    total_truth = int(float(qrows[0]["total_truth_count"])) if qrows else 0
    if total_truth <= 0:
        return 0
    for row in qrows:
        if int(float(row["cumulative_truth_hits"])) >= total_truth:
            return int(row["k"])
    return None


def percentile_int(values: list[int], p: float) -> int:
    if not values:
        return -1
    arr = sorted(values)
    idx = max(0, min(len(arr) - 1, int(math.ceil(p * len(arr))) - 1))
    return arr[idx]


def write_k_full_outputs(
    rows: list[dict[str, str]],
    out_csv: Path,
    out_json: Path,
) -> tuple[dict[str, int], dict[str, dict[str, float | int]]]:
    by_query = group_by_query(rows)
    per_query_rows: list[dict[str, object]] = []
    by_flight_kvals: dict[str, list[int]] = defaultdict(list)
    k_full_map: dict[str, int] = {}

    for qid, qrows in sorted(by_query.items()):
        flight_id = qrows[0]["flight_id"]
        total_truth = int(float(qrows[0]["total_truth_count"]))
        k_full = k_full_truth_for_query(qrows)
        reached = k_full is not None
        per_query_rows.append(
            {
                "query_id": qid,
                "flight_id": flight_id,
                "total_truth_count": total_truth,
                "k_full_truth": "" if k_full is None else k_full,
                "reached_full_truth": int(reached),
            }
        )
        if k_full is not None:
            by_flight_kvals[flight_id].append(k_full)
            k_full_map[qid] = k_full

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["query_id", "flight_id", "total_truth_count", "k_full_truth", "reached_full_truth"],
        )
        writer.writeheader()
        writer.writerows(per_query_rows)

    all_kvals = sorted(k_full_map.values())
    total_queries = len(per_query_rows)
    reached_queries = len(all_kvals)
    summary: dict[str, object] = {
        "query_count": total_queries,
        "reached_count": reached_queries,
        "reached_ratio": reached_queries / total_queries if total_queries else 0.0,
        "overall": {},
        "per_flight": {},
    }

    if all_kvals:
        summary["overall"] = {
            "mean": float(statistics.mean(all_kvals)),
            "median": int(statistics.median(all_kvals)),
            "p90": percentile_int(all_kvals, 0.90),
            "p95": percentile_int(all_kvals, 0.95),
            "max": int(max(all_kvals)),
        }
    else:
        summary["overall"] = {"mean": None, "median": None, "p90": None, "p95": None, "max": None}

    for flight_id, kvals in sorted(by_flight_kvals.items()):
        flight_total = sum(1 for r in per_query_rows if r["flight_id"] == flight_id)
        reached = len(kvals)
        if kvals:
            summary["per_flight"][flight_id] = {
                "query_count": flight_total,
                "reached_count": reached,
                "reached_ratio": reached / flight_total if flight_total else 0.0,
                "mean": float(statistics.mean(kvals)),
                "median": int(statistics.median(kvals)),
                "p90": percentile_int(kvals, 0.90),
                "p95": percentile_int(kvals, 0.95),
                "max": int(max(kvals)),
            }
        else:
            summary["per_flight"][flight_id] = {
                "query_count": flight_total,
                "reached_count": 0,
                "reached_ratio": 0.0,
                "mean": None,
                "median": None,
                "p90": None,
                "p95": None,
                "max": None,
            }

    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return k_full_map, summary["per_flight"]  # type: ignore[return-value]


def plot_overall(rows: list[dict[str, str]], out_path: Path, overall_stats: dict[str, object]) -> None:
    ks, vals = mean_curve(rows, "cumulative_truth_hits")
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    ax.plot(ks, vals, color="#1f77b4", linewidth=2.2)
    ax.set_xlabel("Retrieved Satellite Tile Count (K)")
    ax.set_ylabel("Mean Truth Count Found")
    ax.set_title("Overall Top-K Curve (Truth Count)")
    ax.grid(alpha=0.25)
    median_k = overall_stats.get("median")
    p90_k = overall_stats.get("p90")
    if isinstance(median_k, int) and median_k >= 0:
        ax.axvline(median_k, color="#2ca02c", linestyle="--", linewidth=1.4, label=f"median k_full={median_k}")
    if isinstance(p90_k, int) and p90_k >= 0:
        ax.axvline(p90_k, color="#d62728", linestyle="--", linewidth=1.4, label=f"p90 k_full={p90_k}")
    if ax.get_legend_handles_labels()[0]:
        ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_flight(rows: list[dict[str, str]], flight_id: str, out_path: Path, stats: dict[str, float | int | None]) -> None:
    ks, vals = mean_curve(rows, "cumulative_truth_hits")
    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    ax.plot(ks, vals, color=FLIGHT_COLORS[hash(flight_id) % len(FLIGHT_COLORS)], linewidth=2.2)
    ax.set_xlabel("Retrieved Satellite Tile Count (K)")
    ax.set_ylabel("Mean Truth Count Found")
    ax.set_title(f"{flight_id.split('_')[2]} Top-K Curve (Truth Count)")
    ax.grid(alpha=0.25)
    median_k = stats.get("median")
    p90_k = stats.get("p90")
    if isinstance(median_k, int) and median_k >= 0:
        ax.axvline(median_k, color="#2ca02c", linestyle="--", linewidth=1.3, label=f"median k_full={median_k}")
    if isinstance(p90_k, int) and p90_k >= 0:
        ax.axvline(p90_k, color="#d62728", linestyle="--", linewidth=1.3, label=f"p90 k_full={p90_k}")
    if ax.get_legend_handles_labels()[0]:
        ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    rows = load_csv(Path(args.curve_csv))
    out_dir = Path(args.out_dir)
    agg_dir = out_dir / "_aggregate"
    ensure_dir(agg_dir)

    k_full_csv = out_dir / "k_full_truth_per_query.csv"
    k_full_json = out_dir / "k_full_truth_summary.json"
    _, per_flight_stats = write_k_full_outputs(rows, k_full_csv, k_full_json)

    summary_data = json.loads(k_full_json.read_text(encoding="utf-8"))
    plot_overall(rows, agg_dir / "overall_topk_truth_count_curve_all.png", summary_data["overall"])

    by_flight: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_flight[row["flight_id"]].append(row)

    for flight_id, frows in sorted(by_flight.items()):
        flight_dir = out_dir / flight_id
        ensure_dir(flight_dir)
        stats = per_flight_stats.get(flight_id, {})
        plot_flight(frows, flight_id, flight_dir / "topk_truth_count_curve_all.png", stats)

    print(out_dir)


if __name__ == "__main__":
    main()

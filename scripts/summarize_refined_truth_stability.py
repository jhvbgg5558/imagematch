#!/usr/bin/env python3
"""Summarize refined truth stability across all queries."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize refined truth stability for all queries.")
    parser.add_argument("--result-dir", required=True, help="Directory containing query_truth.csv and query_truth_tiles.csv")
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def short_flight_name(flight_id: str) -> str:
    parts = flight_id.split("_")
    return parts[2] if len(parts) >= 3 else flight_id


def plot_strict_truth_count_by_query(rows: list[dict[str, str]], out_path: Path) -> None:
    labels = [row["query_id"] for row in rows]
    vals = [int(row["strict_truth_count_total"]) for row in rows]
    fig, ax = plt.subplots(figsize=(14, 5.2))
    bars = ax.bar(labels, vals, color="#1a7f37")
    ax.set_ylabel("Strict Truth Count")
    ax.set_title("Strict Truth Count by Query")
    ax.tick_params(axis="x", rotation=45)
    ax.axhline(2, color="#555555", linestyle="--", linewidth=1, label="stable threshold = 2")
    ax.legend()
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.05, f"{val}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_truth_total_vs_strict(rows: list[dict[str, str]], out_path: Path) -> None:
    labels = [row["query_id"] for row in rows]
    strict = np.array([int(row["strict_truth_count_total"]) for row in rows])
    soft = np.array([int(row["soft_truth_count_total"]) for row in rows])
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(14, 5.2))
    ax.bar(x, strict, label="Strict", color="#1a7f37")
    ax.bar(x, soft, bottom=strict, label="Soft", color="#f59e0b")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Truth Count")
    ax.set_title("Truth Total vs Strict by Query")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    totals = strict + soft
    for xi, total in zip(x, totals):
        ax.text(xi, total + 0.08, f"{int(total)}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_strict_truth_count_by_flight(rows: list[dict[str, str]], out_path: Path) -> None:
    by_flight: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        by_flight[row["flight_id"]].append(int(row["strict_truth_count_total"]))
    labels = [short_flight_name(f) for f in by_flight]
    means = [sum(v) / len(v) for v in by_flight.values()]
    mins = [min(v) for v in by_flight.values()]
    maxs = [max(v) for v in by_flight.values()]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    bars = ax.bar(x, means, color="#4c78a8")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Mean Strict Truth Count")
    ax.set_title("Strict Truth Count by Flight")
    for xi, lo, hi in zip(x, mins, maxs):
        ax.vlines(xi, lo, hi, colors="#333333", linewidth=2)
        ax.hlines([lo, hi], xi - 0.12, xi + 0.12, colors="#333333", linewidth=2)
    for bar, val in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.05, f"{val:.2f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_scale_breakdown(rows: list[dict[str, str]], out_path: Path) -> None:
    scales = ["200m", "300m", "500m", "700m"]
    strict_vals = [sum(int(row[f"strict_truth_count_{scale}"]) for row in rows) for scale in scales]
    soft_vals = [sum(int(row[f"soft_truth_count_{scale}"]) for row in rows) for scale in scales]
    x = np.arange(len(scales))
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    ax.bar(x, strict_vals, label="Strict", color="#1a7f37")
    ax.bar(x, soft_vals, bottom=strict_vals, label="Soft", color="#f59e0b")
    ax.set_xticks(x, scales)
    ax.set_ylabel("Truth Tile Count")
    ax.set_title("Scale Breakdown: Strict vs Soft")
    ax.legend()
    totals = [a + b for a, b in zip(strict_vals, soft_vals)]
    for xi, total in zip(x, totals):
        ax.text(xi, total + 1, f"{int(total)}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    result_dir = Path(args.result_dir)
    query_truth_path = result_dir / "query_truth.csv"
    if not query_truth_path.exists():
        raise SystemExit(f"Missing {query_truth_path}")

    rows = sorted(load_csv(query_truth_path), key=lambda row: row["query_id"])
    summary_csv_rows: list[dict[str, str]] = []
    by_flight: dict[str, list[dict[str, str]]] = defaultdict(list)
    zero_total = 0
    zero_strict = 0
    below_stable = 0
    for row in rows:
        total = int(row["truth_count_total"])
        strict = int(row["strict_truth_count_total"])
        soft = int(row["soft_truth_count_total"])
        stable = int(strict >= 2)
        zero_total += int(total == 0)
        zero_strict += int(strict == 0)
        below_stable += int(strict < 2)
        by_flight[row["flight_id"]].append(row)
        summary_csv_rows.append(
            {
                "query_id": row["query_id"],
                "flight_id": row["flight_id"],
                "truth_count_total": str(total),
                "strict_truth_count_total": str(strict),
                "soft_truth_count_total": str(soft),
                "is_zero_truth": str(int(total == 0)),
                "is_zero_strict": str(int(strict == 0)),
                "is_stable_strict_ge_2": str(stable),
            }
        )

    write_csv(result_dir / "stability_summary.csv", summary_csv_rows)

    figure_dir = result_dir / "stability_figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    plot_strict_truth_count_by_query(rows, figure_dir / "strict_truth_count_by_query.png")
    plot_truth_total_vs_strict(rows, figure_dir / "truth_total_vs_strict_by_query.png")
    plot_strict_truth_count_by_flight(rows, figure_dir / "strict_truth_count_by_flight.png")
    plot_scale_breakdown(rows, figure_dir / "scale_breakdown_strict_soft.png")

    lines = [
        "# Refined Truth Stability Summary",
        "",
        f"- Query count: {len(rows)}",
        f"- Zero truth queries: {zero_total}",
        f"- Zero strict-truth queries: {zero_strict}",
        f"- Queries with strict truth < 2: {below_stable}",
        f"- Mean truth count total: {sum(int(r['truth_count_total']) for r in rows) / len(rows):.2f}",
        f"- Mean strict truth count: {sum(int(r['strict_truth_count_total']) for r in rows) / len(rows):.2f}",
        f"- Mean soft truth count: {sum(int(r['soft_truth_count_total']) for r in rows) / len(rows):.2f}",
        "",
        "## By Flight",
        "",
    ]
    for flight_id, flight_rows in by_flight.items():
        strict_vals = [int(r["strict_truth_count_total"]) for r in flight_rows]
        total_vals = [int(r["truth_count_total"]) for r in flight_rows]
        lines.append(
            f"- `{short_flight_name(flight_id)}`: "
            f"queries=`{len(flight_rows)}`, "
            f"avg_total=`{sum(total_vals)/len(total_vals):.2f}`, "
            f"avg_strict=`{sum(strict_vals)/len(strict_vals):.2f}`, "
            f"strict_range=`{min(strict_vals)}..{max(strict_vals)}`, "
            f"zero_strict=`{sum(1 for v in strict_vals if v == 0)}`"
        )
    lines.extend(["", "## Per Query", ""])
    for row in rows:
        lines.append(
            f"- `{row['query_id']}` / `{short_flight_name(row['flight_id'])}`: "
            f"total=`{row['truth_count_total']}`, "
            f"strict=`{row['strict_truth_count_total']}`, "
            f"soft=`{row['soft_truth_count_total']}`"
        )
    (result_dir / "stability_summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

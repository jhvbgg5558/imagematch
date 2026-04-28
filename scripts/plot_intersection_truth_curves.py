#!/usr/bin/env python3
"""Plot top-k cumulative truth curves for intersection-truth evaluation."""

from __future__ import annotations

import argparse
import csv
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
    parser.add_argument("--max-k", type=int, default=0, help="Use 0 to keep all K.")
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def mean_curve(rows: list[dict[str, str]], value_key: str, max_k: int) -> tuple[list[int], list[float]]:
    by_k: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        k = int(row["k"])
        if max_k > 0 and k > max_k:
            continue
        by_k[k].append(float(row[value_key]))
    ks = sorted(by_k)
    vals = [sum(by_k[k]) / len(by_k[k]) for k in ks]
    return ks, vals


def plot_overall(rows: list[dict[str, str]], out_dir: Path, max_k: int) -> None:
    ks, vals = mean_curve(rows, "cumulative_truth_hits", max_k)
    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    ax.plot(ks, vals, color="#1f77b4", linewidth=2.2)
    ax.set_xlabel("Retrieved Satellite Tile Count (K)")
    ax.set_ylabel("Mean Truth Count Found")
    ax.set_title("Intersection Truth Cumulative Hits vs Retrieved Tile Count")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "overall_topk_truth_count_curve.png", dpi=180)
    plt.close(fig)

    ks_r, vals_r = mean_curve(rows, "cumulative_truth_ratio", max_k)
    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    ax.plot(ks_r, vals_r, color="#ff7f0e", linewidth=2.2)
    ax.set_xlabel("Retrieved Satellite Tile Count (K)")
    ax.set_ylabel("Mean Truth Ratio Found")
    ax.set_title("Intersection Truth Cumulative Ratio vs Retrieved Tile Count")
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "overall_topk_truth_ratio_curve.png", dpi=180)
    plt.close(fig)


def plot_by_flight(rows: list[dict[str, str]], out_dir: Path, max_k: int) -> None:
    by_flight: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_flight[row["flight_id"]].append(row)

    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    for idx, flight_id in enumerate(sorted(by_flight)):
        ks, vals = mean_curve(by_flight[flight_id], "cumulative_truth_hits", max_k)
        ax.plot(ks, vals, linewidth=2.0, color=FLIGHT_COLORS[idx % len(FLIGHT_COLORS)], label=flight_id.split("_")[2])
    ax.set_xlabel("Retrieved Satellite Tile Count (K)")
    ax.set_ylabel("Mean Truth Count Found")
    ax.set_title("Intersection Truth Cumulative Hits by Flight")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "flight_topk_truth_count_curve.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    for idx, flight_id in enumerate(sorted(by_flight)):
        ks, vals = mean_curve(by_flight[flight_id], "cumulative_truth_ratio", max_k)
        ax.plot(ks, vals, linewidth=2.0, color=FLIGHT_COLORS[idx % len(FLIGHT_COLORS)], label=flight_id.split("_")[2])
    ax.set_xlabel("Retrieved Satellite Tile Count (K)")
    ax.set_ylabel("Mean Truth Ratio Found")
    ax.set_title("Intersection Truth Cumulative Ratio by Flight")
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "flight_topk_truth_ratio_curve.png", dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    rows = load_csv(Path(args.curve_csv))
    plot_overall(rows, out_dir, args.max_k)
    plot_by_flight(rows, out_dir, args.max_k)
    print(out_dir)


if __name__ == "__main__":
    main()

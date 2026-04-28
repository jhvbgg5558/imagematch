#!/usr/bin/env python3
"""Create aggregate visualizations for multi-flight validation results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize aggregate multi-flight metrics.")
    parser.add_argument("--aggregate-json", required=True, help="Aggregate summary JSON path.")
    parser.add_argument("--out-dir", required=True, help="Directory for output figures.")
    return parser.parse_args()


def plot_overall(flights: list[dict], out_path: Path) -> None:
    labels = [item["flight_id"] for item in flights]
    r1 = [item["recall@1"] for item in flights]
    r5 = [item["recall@5"] for item in flights]
    r10 = [item["recall@10"] for item in flights]

    x = np.arange(len(labels))
    width = 0.22
    fig, ax = plt.subplots(figsize=(12, 5.6))
    ax.bar(x - width, r1, width, label="Recall@1")
    ax.bar(x, r5, width, label="Recall@5")
    ax.bar(x + width, r10, width, label="Recall@10")
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Recall")
    ax.set_title("Multi-Flight Retrieval Recall")
    ax.set_xticks(x, labels)
    ax.tick_params(axis="x", rotation=20)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def plot_scale_comparison(flights: list[dict], out_path: Path) -> None:
    labels = [item["flight_id"] for item in flights]
    scales = sorted({scale for item in flights for scale in item["per_scale"].keys()}, key=lambda x: float(x))
    if not scales:
        return

    x = np.arange(len(labels))
    series = []
    for scale in scales:
        series.append((f"{scale}m R@1", [item["per_scale"].get(scale, {}).get("recall@1", 0.0) for item in flights]))
        series.append((f"{scale}m R@5", [item["per_scale"].get(scale, {}).get("recall@5", 0.0) for item in flights]))
    width = 0.8 / len(series)
    fig, ax = plt.subplots(figsize=(12, 5.6))
    start = -0.4 + width / 2
    for idx, (label, vals) in enumerate(series):
        ax.bar(x + start + idx * width, vals, width, label=label)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Recall")
    ax.set_title("Scale Comparison Across Flights")
    ax.set_xticks(x, labels)
    ax.tick_params(axis="x", rotation=20)
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with Path(args.aggregate_json).open("r", encoding="utf-8") as f:
        data = json.load(f)
    flights = data["flights"]

    plot_overall(flights, out_dir / "multi_flight_recall.png")
    plot_scale_comparison(flights, out_dir / "multi_flight_scale_comparison.png")
    print(f"Aggregate figures written to {out_dir}")


if __name__ == "__main__":
    main()

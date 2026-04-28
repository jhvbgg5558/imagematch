#!/usr/bin/env python3
"""Visualize pooling comparison results across methods and flights."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


METHOD_ORDER = ["pooler", "cls", "mean", "gem"]
METHOD_COLORS = {
    "pooler": "#355070",
    "cls": "#6d597a",
    "mean": "#b56576",
    "gem": "#e56b6f",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize pooling comparison results.")
    parser.add_argument("--comparison-root", required=True)
    parser.add_argument("--overall-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def short_flight_name(flight_id: str) -> str:
    parts = flight_id.split("_")
    if len(parts) >= 3:
        candidate = parts[2]
        if candidate.isdigit():
            return candidate
        return candidate
    return flight_id


def collect_per_flight_rows(comparison_root: Path, methods: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for method in methods:
        method_root = comparison_root / method
        for retrieval_json in sorted((method_root / "stage4").glob("*_retrieval_top10.json")):
            flight_id = retrieval_json.name.replace("_retrieval_top10.json", "")
            timing_json = method_root / "timing" / f"{flight_id}_timing_summary.json"
            retrieval = load_json(retrieval_json)
            timing = load_json(timing_json)
            errors = [
                float(item["top1_error_m"])
                for item in retrieval["per_query"]
                if item.get("top1_error_m") is not None
            ]
            rows.append(
                {
                    "method": method,
                    "flight_id": flight_id,
                    "query_count": int(retrieval["query_count"]),
                    "recall@1": float(retrieval["recall@1"]),
                    "recall@5": float(retrieval["recall@5"]),
                    "recall@10": float(retrieval["recall@10"]),
                    "mrr": float(retrieval.get("mrr", 0.0)),
                    "top1_error_m_mean": sum(errors) / len(errors) if errors else None,
                    "feature_ms_mean": float(timing["feature_timing"]["mean_ms"]),
                    "retrieval_ms_mean": float(timing["retrieval_timing"]["mean_ms"]),
                    "total_ms_mean": float(timing["total_timing"]["mean_ms"]),
                }
            )
    rows.sort(key=lambda x: (METHOD_ORDER.index(x["method"]), x["flight_id"]))
    return rows


def write_per_flight_csv(rows: list[dict[str, object]], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "method",
                "flight_id",
                "query_count",
                "recall@1",
                "recall@5",
                "recall@10",
                "mrr",
                "top1_error_m_mean",
                "feature_ms_mean",
                "retrieval_ms_mean",
                "total_ms_mean",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def plot_overall_recall(overall_rows: list[dict[str, str]], out_path: Path) -> None:
    methods = [row["method"] for row in overall_rows]
    r1 = [float(row["recall@1"]) for row in overall_rows]
    r5 = [float(row["recall@5"]) for row in overall_rows]
    r10 = [float(row["recall@10"]) for row in overall_rows]

    x = np.arange(len(methods))
    width = 0.22
    fig, ax = plt.subplots(figsize=(10, 5.4))
    ax.bar(x - width, r1, width, label="Recall@1", color="#355070")
    ax.bar(x, r5, width, label="Recall@5", color="#6d597a")
    ax.bar(x + width, r10, width, label="Recall@10", color="#e56b6f")
    ax.set_xticks(x, [m.upper() for m in methods])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Recall")
    ax.set_title("Pooling Comparison Recall")
    ax.legend()
    for vals, offset in [(r1, -width), (r5, 0), (r10, width)]:
        for i, v in enumerate(vals):
            ax.text(x[i] + offset, v + 0.02, f"{v:.2f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_overall_dashboard(overall_rows: list[dict[str, str]], out_path: Path) -> None:
    methods = [row["method"] for row in overall_rows]
    metrics = [
        ("MRR", "mrr", None),
        ("Top-1 Error (m)", "top1_error_m_mean", None),
        ("Feature Time (ms)", "feature_ms_mean", None),
        ("Retrieval Time (ms)", "retrieval_ms_mean", None),
        ("Total Time (ms)", "total_ms_mean", None),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    axes = axes.flatten()

    recall_ax = axes[0]
    x = np.arange(len(methods))
    width = 0.22
    recall_ax.bar(x - width, [float(row["recall@1"]) for row in overall_rows], width, label="R@1", color="#355070")
    recall_ax.bar(x, [float(row["recall@5"]) for row in overall_rows], width, label="R@5", color="#6d597a")
    recall_ax.bar(x + width, [float(row["recall@10"]) for row in overall_rows], width, label="R@10", color="#e56b6f")
    recall_ax.set_title("Recall")
    recall_ax.set_xticks(x, [m.upper() for m in methods])
    recall_ax.set_ylim(0, 1.05)
    recall_ax.legend(fontsize=8)

    for ax, (title, key, ylim) in zip(axes[1:], metrics):
        vals = [float(row[key]) for row in overall_rows]
        colors = [METHOD_COLORS[m] for m in methods]
        ax.bar(methods, vals, color=colors)
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=20)
        if ylim is not None:
            ax.set_ylim(*ylim)
        for i, v in enumerate(vals):
            ax.text(i, v * 1.01 if v != 0 else 0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=8)

    fig.suptitle("Pooling Comparison Dashboard", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_per_flight_heatmaps(rows: list[dict[str, object]], out_path: Path) -> None:
    flights = sorted({row["flight_id"] for row in rows})
    methods = [m for m in METHOD_ORDER if any(row["method"] == m for row in rows)]
    metrics = ["recall@1", "recall@5", "recall@10", "mrr"]
    titles = ["Recall@1", "Recall@5", "Recall@10", "MRR"]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    for ax, metric, title in zip(axes, metrics, titles):
        data = np.zeros((len(methods), len(flights)), dtype=float)
        for i, method in enumerate(methods):
            for j, flight in enumerate(flights):
                row = next(item for item in rows if item["method"] == method and item["flight_id"] == flight)
                data[i, j] = float(row[metric])
        im = ax.imshow(data, cmap="YlGnBu", vmin=0.0, vmax=1.0, aspect="auto")
        ax.set_xticks(np.arange(len(flights)), [short_flight_name(f) for f in flights])
        ax.set_yticks(np.arange(len(methods)), [m.upper() for m in methods])
        ax.set_title(title)
        for i in range(len(methods)):
            for j in range(len(flights)):
                ax.text(j, i, f"{data[i, j]:.2f}", ha="center", va="center", color="black", fontsize=9)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("Per-Flight Accuracy Heatmaps", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_error_latency_heatmaps(rows: list[dict[str, object]], out_path: Path) -> None:
    flights = sorted({row["flight_id"] for row in rows})
    methods = [m for m in METHOD_ORDER if any(row["method"] == m for row in rows)]
    metrics = ["top1_error_m_mean", "feature_ms_mean", "retrieval_ms_mean", "total_ms_mean"]
    titles = ["Top-1 Error (m)", "Feature Time (ms)", "Retrieval Time (ms)", "Total Time (ms)"]
    cmaps = ["OrRd", "PuBu", "PuBu", "PuBu"]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    for ax, metric, title, cmap in zip(axes, metrics, titles, cmaps):
        data = np.zeros((len(methods), len(flights)), dtype=float)
        for i, method in enumerate(methods):
            for j, flight in enumerate(flights):
                row = next(item for item in rows if item["method"] == method and item["flight_id"] == flight)
                data[i, j] = float(row[metric])
        im = ax.imshow(data, cmap=cmap, aspect="auto")
        ax.set_xticks(np.arange(len(flights)), [short_flight_name(f) for f in flights])
        ax.set_yticks(np.arange(len(methods)), [m.upper() for m in methods])
        ax.set_title(title)
        for i in range(len(methods)):
            for j in range(len(flights)):
                ax.text(j, i, f"{data[i, j]:.1f}", ha="center", va="center", color="black", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("Per-Flight Error and Latency Heatmaps", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_tradeoff(overall_rows: list[dict[str, str]], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    for row in overall_rows:
        method = row["method"]
        x = float(row["total_ms_mean"])
        y = float(row["recall@1"])
        size = 80 + 220 * float(row["mrr"])
        ax.scatter(x, y, s=size, color=METHOD_COLORS[method], alpha=0.85, edgecolor="black", linewidth=0.8)
        ax.text(x + 8, y + 0.01, method.upper(), fontsize=10)
    ax.set_xlabel("Mean Total Time per Query (ms)")
    ax.set_ylabel("Recall@1")
    ax.set_title("Speed vs Accuracy Trade-off")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    comparison_root = Path(args.comparison_root)
    overall_csv = Path(args.overall_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    overall_rows = load_csv(overall_csv)
    methods = [row["method"] for row in overall_rows]
    per_flight_rows = collect_per_flight_rows(comparison_root, methods)
    write_per_flight_csv(per_flight_rows, comparison_root / "per_flight_metrics.csv")

    plot_overall_recall(overall_rows, out_dir / "overall_recall_bar.png")
    plot_overall_dashboard(overall_rows, out_dir / "overall_dashboard.png")
    plot_per_flight_heatmaps(per_flight_rows, out_dir / "per_flight_accuracy_heatmaps.png")
    plot_error_latency_heatmaps(per_flight_rows, out_dir / "per_flight_error_latency_heatmaps.png")
    plot_tradeoff(overall_rows, out_dir / "speed_accuracy_tradeoff.png")

    print(f"Figures written to {out_dir}")
    print(f"Per-flight CSV rebuilt at {comparison_root / 'per_flight_metrics.csv'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate same-scale pooling visualizations in per-flight and aggregate layouts."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


METHOD_ORDER = ["pooler", "cls", "mean", "gem"]
METHOD_LABELS = {
    "pooler": "POOLER",
    "cls": "CLS",
    "mean": "MEAN",
    "gem": "GEM",
}
METHOD_COLORS = {
    "pooler": "#355070",
    "cls": "#6d597a",
    "mean": "#b56576",
    "gem": "#e56b6f",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison-root", required=True)
    parser.add_argument("--stage3-root", required=True)
    parser.add_argument("--overall-csv", required=True)
    parser.add_argument("--per-flight-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def short_flight_name(flight_id: str) -> str:
    parts = flight_id.split("_")
    return parts[2] if len(parts) >= 3 else flight_id


def plot_metric_by_method(rows: list[dict[str, str]], metric_key: str, ylabel: str, out_path: Path, title: str) -> None:
    methods = [row["method"] for row in rows]
    vals = [float(row[metric_key]) for row in rows]
    colors = [METHOD_COLORS.get(m, "#4c4c4c") for m in methods]
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    bars = ax.bar(methods, vals, color=colors)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(vals) * 0.02 if max(vals) else 0.01, f"{val:.3f}", ha="center", va="bottom", fontsize=9)
    if "Recall" in ylabel or metric_key == "mrr":
        ax.set_ylim(0, min(1.05, max(vals) + 0.15))
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_multi_flight_recall(rows: list[dict[str, str]], out_path: Path) -> None:
    flights = sorted({row["flight_id"] for row in rows})
    methods = [m for m in METHOD_ORDER if any(row["method"] == m for row in rows)]
    x = np.arange(len(flights))
    width = 0.8 / max(1, len(methods))
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), sharey=True)
    for ax, metric in zip(axes, ["recall@1", "recall@5", "recall@10"]):
        for idx, method in enumerate(methods):
            vals = []
            for flight in flights:
                row = next(item for item in rows if item["method"] == method and item["flight_id"] == flight)
                vals.append(float(row[metric]))
            offset = -0.4 + width / 2 + idx * width
            ax.bar(x + offset, vals, width, label=METHOD_LABELS[method], color=METHOD_COLORS[method])
        ax.set_xticks(x, [short_flight_name(f) for f in flights])
        ax.set_ylim(0, 1.05)
        ax.set_title(metric.upper())
        ax.grid(axis="y", alpha=0.2)
    axes[0].set_ylabel("Recall")
    axes[-1].legend(loc="upper right", fontsize=8)
    fig.suptitle("Multi-Flight Recall Comparison")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    comparison_root = Path(args.comparison_root)
    stage3_root = Path(args.stage3_root)
    overall_rows = load_csv(Path(args.overall_csv))
    per_flight_rows = load_csv(Path(args.per_flight_csv))
    out_dir = Path(args.out_dir)
    aggregate_dir = out_dir / "_aggregate"
    out_dir.mkdir(parents=True, exist_ok=True)
    aggregate_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = Path(__file__).resolve().parent
    py = sys.executable

    for method in [row["method"] for row in overall_rows]:
        method_root = comparison_root / method
        mapping_json = method_root / "stage2" / f"satellite_tiles_ip_{method}_mapping.json"
        for query_csv in sorted(stage3_root.glob("*/queries.csv")):
            flight_id = query_csv.parent.name
            retrieval_csv = method_root / "stage4" / f"{flight_id}_retrieval_top{args.top_k}.csv"
            analysis_json = method_root / "stage7" / f"{flight_id}_analysis.json"
            flight_out_dir = out_dir / method / flight_id
            cmd = [
                py,
                str(scripts_dir / "visualize_retrieval_results.py"),
                "--query-metadata-csv",
                str(query_csv),
                "--retrieval-results-csv",
                str(retrieval_csv),
                "--analysis-json",
                str(analysis_json),
                "--mapping-json",
                str(mapping_json),
                "--top-k",
                str(args.top_k),
                "--out-dir",
                str(flight_out_dir),
            ]
            run(cmd)

    plot_metric_by_method(
        overall_rows,
        "recall@1",
        "Recall",
        aggregate_dir / "pooling_same_scale_recall1.png",
        "Pooling Same-Scale Recall@1",
    )
    plot_metric_by_method(
        overall_rows,
        "recall@5",
        "Recall",
        aggregate_dir / "pooling_same_scale_recall5.png",
        "Pooling Same-Scale Recall@5",
    )
    plot_metric_by_method(
        overall_rows,
        "recall@10",
        "Recall",
        aggregate_dir / "pooling_same_scale_recall10.png",
        "Pooling Same-Scale Recall@10",
    )
    plot_metric_by_method(
        overall_rows,
        "mrr",
        "MRR",
        aggregate_dir / "pooling_same_scale_mrr.png",
        "Pooling Same-Scale MRR",
    )
    plot_metric_by_method(
        overall_rows,
        "top1_error_m_mean",
        "Meters",
        aggregate_dir / "pooling_same_scale_top1_error.png",
        "Pooling Same-Scale Top-1 Error",
    )
    plot_metric_by_method(
        overall_rows,
        "feature_ms_mean",
        "Milliseconds",
        aggregate_dir / "pooling_same_scale_feature_ms.png",
        "Pooling Same-Scale Feature Time",
    )
    plot_metric_by_method(
        overall_rows,
        "total_ms_mean",
        "Milliseconds",
        aggregate_dir / "pooling_same_scale_total_ms.png",
        "Pooling Same-Scale Total Time",
    )
    plot_multi_flight_recall(per_flight_rows, aggregate_dir / "multi_flight_recall.png")
    print(f"Visualizations written to {out_dir}")


if __name__ == "__main__":
    main()

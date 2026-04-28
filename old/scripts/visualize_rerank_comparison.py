#!/usr/bin/env python3
"""Create aggregate comparison plots for baseline and rerank rounds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-aggregate-json", required=True)
    parser.add_argument("--round1-aggregate-json", required=True)
    parser.add_argument("--round2-aggregate-json", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def load(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["flight_id"]: item for item in data["flights"]}


def short_label(flight_id: str) -> str:
    parts = flight_id.split("_")
    return parts[2] if len(parts) >= 3 else flight_id


def plot_compare(
    baseline: dict[str, dict],
    round1: dict[str, dict],
    round2: dict[str, dict],
    metric: str,
    title: str,
    out_path: Path,
) -> None:
    if any(metric not in dataset[k] for dataset in (baseline, round1, round2) for k in dataset.keys() if k in baseline):
        return
    labels = list(baseline.keys())
    tick_labels = [short_label(x) for x in labels]
    x = np.arange(len(labels))
    width = 0.22
    base_vals = [baseline[k][metric] for k in labels]
    r1_vals = [round1[k][metric] for k in labels]
    r2_vals = [round2[k][metric] for k in labels]
    fig, ax = plt.subplots(figsize=(12, 5.6))
    ax.bar(x - width, base_vals, width, label="Baseline")
    ax.bar(x, r1_vals, width, label="Round1 SIFT")
    ax.bar(x + width, r2_vals, width, label="Round2 Gate")
    ax.set_ylim(0, 1.1 if "recall" in metric or metric == "mrr" else max(base_vals + r1_vals + r2_vals) * 1.15)
    ax.set_xticks(x, tick_labels)
    ax.tick_params(axis="x", rotation=20)
    ax.set_title(title)
    ax.legend()
    for vals, offset in [(base_vals, -width), (r1_vals, 0), (r2_vals, width)]:
        for i, v in enumerate(vals):
            ax.text(x[i] + offset, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    baseline = load(Path(args.baseline_aggregate_json))
    round1 = load(Path(args.round1_aggregate_json))
    round2 = load(Path(args.round2_aggregate_json))

    plot_compare(baseline, round1, round2, "recall@1", "Baseline vs Rerank Recall@1", out_dir / "compare_recall1.png")
    plot_compare(baseline, round1, round2, "recall@5", "Baseline vs Rerank Recall@5", out_dir / "compare_recall5.png")
    plot_compare(baseline, round1, round2, "recall@10", "Baseline vs Rerank Recall@10", out_dir / "compare_recall10.png")
    plot_compare(baseline, round1, round2, "mrr", "Baseline vs Rerank MRR", out_dir / "compare_mrr.png")
    print(f"Aggregate comparison figures written to {out_dir}")


if __name__ == "__main__":
    main()

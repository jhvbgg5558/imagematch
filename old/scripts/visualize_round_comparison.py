#!/usr/bin/env python3
"""Compare two aggregate validation rounds in one figure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize comparison between two validation rounds.")
    parser.add_argument("--baseline-json", required=True)
    parser.add_argument("--candidate-json", required=True)
    parser.add_argument("--out-path", required=True)
    return parser.parse_args()


def load(path: Path) -> dict[str, dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {item["flight_id"]: item for item in data["flights"]}


def main() -> None:
    args = parse_args()
    baseline = load(Path(args.baseline_json))
    candidate = load(Path(args.candidate_json))
    flights = [f for f in baseline.keys() if f in candidate]

    labels = flights
    b_r5 = [baseline[f]["recall@5"] for f in flights]
    c_r5 = [candidate[f]["recall@5"] for f in flights]
    b_r10 = [baseline[f]["recall@10"] for f in flights]
    c_r10 = [candidate[f]["recall@10"] for f in flights]

    x = np.arange(len(labels))
    width = 0.18
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.bar(x - 1.5 * width, b_r5, width, label="Baseline R@5")
    ax.bar(x - 0.5 * width, c_r5, width, label="200m-only R@5")
    ax.bar(x + 0.5 * width, b_r10, width, label="Baseline R@10")
    ax.bar(x + 1.5 * width, c_r10, width, label="200m-only R@10")
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Recall")
    ax.set_title("Validation Round Comparison")
    ax.set_xticks(x, labels)
    ax.tick_params(axis="x", rotation=20)
    ax.legend(ncol=2)
    fig.tight_layout()
    out = Path(args.out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print(f"Comparison figure saved to {out}")


if __name__ == "__main__":
    main()

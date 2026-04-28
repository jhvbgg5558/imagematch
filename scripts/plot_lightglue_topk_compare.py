#!/usr/bin/env python3
"""Plot baseline vs LightGlue top-k comparison curves."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-full-curve-csv", required=True)
    parser.add_argument("--lightglue-full-curve-csv", required=True)
    parser.add_argument("--baseline-unique-curve-csv", required=True)
    parser.add_argument("--lightglue-unique-curve-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def mean_curve(rows: list[dict[str, str]], value_key: str) -> tuple[list[int], list[float]]:
    by_k: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        by_k[int(row["k"])].append(float(row[value_key]))
    ks = sorted(by_k)
    vals = [sum(by_k[k]) / len(by_k[k]) for k in ks]
    return ks, vals


def plot_compare(
    baseline_rows: list[dict[str, str]],
    lightglue_rows: list[dict[str, str]],
    value_key: str,
    ylabel: str,
    title: str,
    out_path: Path,
) -> None:
    ks_b, vals_b = mean_curve(baseline_rows, value_key)
    ks_l, vals_l = mean_curve(lightglue_rows, value_key)
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    ax.plot(ks_b, vals_b, color="#4e79a7", linewidth=2.2, label="Baseline")
    ax.plot(ks_l, vals_l, color="#e15759", linewidth=2.2, label="LightGlue Top50 rerank + baseline tail")
    ax.axvline(50, color="#777777", linestyle="--", linewidth=1.2, label="rerank boundary K=50")
    ax.set_xlabel("Retrieved Satellite Tile Count (K)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline_full = load_csv(Path(args.baseline_full_curve_csv))
    lightglue_full = load_csv(Path(args.lightglue_full_curve_csv))
    baseline_unique = [r for r in load_csv(Path(args.baseline_unique_curve_csv)) if r["scope"] == "overall"]
    lightglue_unique = [r for r in load_csv(Path(args.lightglue_unique_curve_csv)) if r["scope"] == "overall"]

    plot_compare(
        baseline_full,
        lightglue_full,
        "cumulative_truth_hits",
        "Mean Truth Count Found",
        "Baseline vs LightGlue Top-K Curve (Full Truth)",
        out_dir / "baseline_vs_lightglue_full_truth_curve.png",
    )
    plot_compare(
        baseline_unique,
        lightglue_unique,
        "cumulative_truth_hits",
        "Found Unique Truth Tile Count",
        "Baseline vs LightGlue Top-K Curve (Unique Truth Tiles)",
        out_dir / "baseline_vs_lightglue_unique_truth_curve.png",
    )
    print(out_dir)


if __name__ == "__main__":
    main()

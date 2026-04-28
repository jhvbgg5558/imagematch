#!/usr/bin/env python3
"""Visualize LightGlue strict rerank outputs and baseline comparisons."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw


QUERY_BORDER = "#555555"
HIT_BORDER = "#1a7f37"
MISS_BORDER = "#b42318"
BASELINE_COLOR = "#1f77b4"
LIGHTGLUE_COLOR = "#ff7f0e"
UPPER_COLOR = "#2ca02c"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-result-dir", required=True)
    parser.add_argument("--lightglue-result-dir", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def add_border(img: Image.Image, color: str, width: int = 8) -> Image.Image:
    out = Image.new("RGB", (img.width + width * 2, img.height + width * 2), color)
    out.paste(img, (width, width))
    return out


def labeled_thumb(path: Path, label_lines: list[str], border_color: str, size: int = 320) -> Image.Image:
    with Image.open(path) as img:
        thumb = img.convert("RGB").resize((size, size))
    thumb = add_border(thumb, border_color, width=8)
    draw = ImageDraw.Draw(thumb)
    banner_h = 58
    draw.rectangle((0, 0, thumb.width, banner_h), fill=(0, 0, 0))
    y = 6
    for line in label_lines[:3]:
        draw.text((8, y), line, fill=(255, 255, 255))
        y += 16
    return thumb


def make_contact_sheet(images: list[Image.Image], cols: int = 3, gap: int = 12) -> Image.Image:
    w = max(img.width for img in images)
    h = max(img.height for img in images)
    rows = math.ceil(len(images) / cols)
    canvas = Image.new("RGB", (cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap), (245, 245, 245))
    for idx, img in enumerate(images):
        r = idx // cols
        c = idx % cols
        x = gap + c * (w + gap)
        y = gap + r * (h + gap)
        canvas.paste(img, (x, y))
    return canvas


def load_reranked(path: Path) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in load_csv(path):
        out[row["query_id"]].append(row)
    for rows in out.values():
        rows.sort(key=lambda x: int(x["rank"]))
    return out


def plot_overall_compare(overall: dict, out_path: Path) -> None:
    labels = ["Strict R@1", "Strict R@5", "Strict R@10", "Strict MRR"]
    baseline_vals = [
        overall["baseline_strict_recall@1"],
        overall["baseline_strict_recall@5"],
        overall["baseline_strict_recall@10"],
        overall["baseline_strict_mrr"],
    ]
    lightglue_vals = [
        overall["lightglue_strict_recall@1"],
        overall["lightglue_strict_recall@5"],
        overall["lightglue_strict_recall@10"],
        overall["lightglue_strict_mrr"],
    ]
    x = np.arange(len(labels))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    b1 = ax.bar(x - width / 2, baseline_vals, width, label="Baseline", color=BASELINE_COLOR)
    b2 = ax.bar(x + width / 2, lightglue_vals, width, label="LightGlue", color=LIGHTGLUE_COLOR)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Value")
    ax.set_title("Baseline vs LightGlue Strict Metrics")
    ax.legend()
    for bars in (b1, b2):
        for bar in bars:
            value = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_lightglue_overall(overall: dict, out_path: Path) -> None:
    labels = ["Strict R@1", "Strict R@5", "Strict R@10", "Strict MRR"]
    vals = [
        overall["lightglue_strict_recall@1"],
        overall["lightglue_strict_recall@5"],
        overall["lightglue_strict_recall@10"],
        overall["lightglue_strict_mrr"],
    ]
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    bars = ax.bar(np.arange(len(labels)), vals, color=[LIGHTGLUE_COLOR] * 4)
    ax.set_xticks(np.arange(len(labels)), labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Value")
    ax.set_title(f"LightGlue Strict Metrics | Top1Err={overall['lightglue_top1_error_m_mean']:.1f}m")
    for bar, value in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_top1_error_mean(overall: dict, out_path: Path) -> None:
    labels = ["Baseline", "LightGlue"]
    vals = [
        overall["baseline_top1_error_m_mean"],
        overall["lightglue_top1_error_m_mean"],
    ]
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    bars = ax.bar(np.arange(len(labels)), vals, color=[BASELINE_COLOR, LIGHTGLUE_COLOR])
    ax.set_xticks(np.arange(len(labels)), labels)
    ax.set_ylabel("Top-1 Error Mean (m)")
    ax.set_title("Baseline vs LightGlue Top-1 Error Mean")
    ymax = max(vals) * 1.18 if max(vals) > 0 else 1.0
    ax.set_ylim(0, ymax)
    for bar, value in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, value + ymax * 0.02, f"{value:.1f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_top20_upper_bound(overall: dict, out_path: Path) -> None:
    labels = ["Baseline R@10", "Coarse R@20", "LightGlue R@10"]
    vals = [
        overall["baseline_strict_recall@10"],
        overall["coarse_strict_recall@20"],
        overall["lightglue_strict_recall@10"],
    ]
    colors = [BASELINE_COLOR, UPPER_COLOR, LIGHTGLUE_COLOR]
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    bars = ax.bar(np.arange(len(labels)), vals, color=colors)
    ax.set_xticks(np.arange(len(labels)), labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Recall")
    ax.set_title("Top-20 Candidate Upper Bound vs Final Top-10")
    for bar, value in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_multi_flight(per_flight_rows: list[dict[str, str]], out_path: Path) -> None:
    labels = [row["flight_tag"] for row in per_flight_rows]
    x = np.arange(len(labels))
    width = 0.25
    r1 = [float(row["lightglue_strict_recall@1"]) for row in per_flight_rows]
    r5 = [float(row["lightglue_strict_recall@5"]) for row in per_flight_rows]
    r10 = [float(row["lightglue_strict_recall@10"]) for row in per_flight_rows]
    fig, ax = plt.subplots(figsize=(12, 5.0))
    b1 = ax.bar(x - width, r1, width, label="Recall@1", color=BASELINE_COLOR)
    b2 = ax.bar(x, r5, width, label="Recall@5", color=LIGHTGLUE_COLOR)
    b3 = ax.bar(x + width, r10, width, label="Recall@10", color=UPPER_COLOR)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Recall")
    ax.set_title("LightGlue Strict Multi-Flight Recall")
    ax.legend()
    for bars in (b1, b2, b3):
        for bar in bars:
            value = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.2f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_rank_delta(comp_rows: list[dict[str, str]], flight_id: str, out_path: Path) -> None:
    rows = [row for row in comp_rows if row["flight_id"] == flight_id]
    rows.sort(key=lambda x: x["query_id"])
    labels = [row["query_id"] for row in rows]
    vals = []
    colors = []
    for row in rows:
        b = row["baseline_first_strict_truth_rank"]
        l = row["lightglue_first_strict_truth_rank"]
        b_rank = 21 if b == "" else int(b)
        l_rank = 21 if l == "" else int(l)
        vals.append(b_rank - l_rank)
        colors.append(UPPER_COLOR if (b_rank - l_rank) > 0 else MISS_BORDER if (b_rank - l_rank) < 0 else "#888888")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    bars = ax.bar(labels, vals, color=colors)
    ax.axhline(0, color="#333333", linewidth=1)
    ax.set_ylabel("Baseline Rank - LightGlue Rank")
    ax.set_title(f"Flight {flight_id.split('_')[2]} Rank Delta by Query")
    ax.tick_params(axis="x", rotation=45)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + (0.2 if val >= 0 else -0.6), f"{val}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_query_rr(summary: dict, out_path: Path, flight_tag: str) -> None:
    rows = summary["per_query"]
    rows.sort(key=lambda x: x["query_id"])
    labels = [row["query_id"] for row in rows]
    vals = [float(row["strict_reciprocal_rank"]) for row in rows]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    bars = ax.bar(labels, vals, color=LIGHTGLUE_COLOR)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Strict Reciprocal Rank")
    ax.set_title(f"Flight {flight_tag} Query Selection Scores")
    ax.tick_params(axis="x", rotation=45)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02, f"{val:.2f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def save_query_contact_sheet(query_path: Path, qid: str, flight_tag: str, rows: list[dict[str, str]], tile_meta: dict[str, dict[str, str]], out_path: Path, top_k: int) -> None:
    images = [labeled_thumb(query_path, [f"query_id: {qid}", f"flight_id: {flight_tag}", "strict truth"], QUERY_BORDER)]
    for row in rows[:top_k]:
        tile_id = row["candidate_tile_id"]
        md = tile_meta[tile_id]
        score = float(row.get("fused_score", row.get("global_score", "0")))
        images.append(
            labeled_thumb(
                Path(md["image_path"]),
                [f"rank: {row['rank']}", f"tile: {tile_id}", f"scale: {int(float(md['tile_size_m']))}m score: {score:.3f}"],
                HIT_BORDER if row["is_strict_truth_hit"] == "1" else MISS_BORDER,
            )
        )
    make_contact_sheet(images, cols=3).save(out_path)


def main() -> None:
    args = parse_args()
    baseline_dir = Path(args.baseline_result_dir)
    lightglue_dir = Path(args.lightglue_result_dir)
    figure_dir = lightglue_dir / "figures"
    ensure_dir(figure_dir / "_aggregate")
    ensure_dir(figure_dir / "_compare")

    overall = load_json(lightglue_dir / "overall_summary.json")
    per_flight_rows = load_csv(lightglue_dir / "per_flight_comparison.csv")
    comp_rows = load_csv(lightglue_dir / "per_query_comparison.csv")
    manifest_rows = {row["query_id"]: row for row in load_csv(baseline_dir / "query_inputs" / "query_manifest.csv")}
    tile_meta = {row["tile_id"]: row for row in load_csv(baseline_dir / "fixed_satellite_library" / "tiles.csv")}

    plot_overall_compare(overall, figure_dir / "_aggregate" / "overall_metrics_bar.png")
    plot_multi_flight(per_flight_rows, figure_dir / "_aggregate" / "multi_flight_recall.png")
    plot_top1_error_mean(overall, figure_dir / "_aggregate" / "top1_error_distribution.png")
    plot_top20_upper_bound(overall, figure_dir / "_aggregate" / "top20_upper_bound.png")
    plot_overall_compare(overall, figure_dir / "_compare" / "baseline_vs_lightglue_compare.png")
    plot_lightglue_overall(overall, figure_dir / "_compare" / "lightglue_metrics_bar.png")

    for row in per_flight_rows:
        flight_id = row["flight_id"]
        flight_dir = figure_dir / flight_id
        ensure_dir(flight_dir)
        summary = load_json(lightglue_dir / "stage7" / flight_id / "rerank_top20.json")
        reranked = load_reranked(lightglue_dir / "stage7" / flight_id / "reranked_top20.csv")
        plot_query_rr(summary, flight_dir / "query_selection_scores.png", row["flight_tag"])
        plot_rank_delta(comp_rows, flight_id, flight_dir / "query_rank_delta.png")
        plot_row = {
            "lightglue_strict_recall@1": float(row["lightglue_strict_recall@1"]),
            "lightglue_strict_recall@5": float(row["lightglue_strict_recall@5"]),
            "lightglue_strict_recall@10": float(row["lightglue_strict_recall@10"]),
            "lightglue_strict_mrr": float(row["lightglue_strict_mrr"]),
        }
        labels = ["Strict R@1", "Strict R@5", "Strict R@10", "Strict MRR"]
        vals = [
            plot_row["lightglue_strict_recall@1"],
            plot_row["lightglue_strict_recall@5"],
            plot_row["lightglue_strict_recall@10"],
            plot_row["lightglue_strict_mrr"],
        ]
        fig, ax = plt.subplots(figsize=(9.0, 4.8))
        bars = ax.bar(np.arange(len(labels)), vals, color=[LIGHTGLUE_COLOR, LIGHTGLUE_COLOR, LIGHTGLUE_COLOR, BASELINE_COLOR])
        ax.set_xticks(np.arange(len(labels)), labels)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Value")
        ax.set_title(f"Flight {row['flight_tag']} Strict Metrics")
        for bar, value in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center", fontsize=9)
        fig.tight_layout()
        fig.savefig(flight_dir / "metrics_bar.png", dpi=180)
        plt.close(fig)

        qids = sorted(reranked.keys())
        for qid in qids:
            query_path = Path(manifest_rows[qid]["sanitized_query_path"])
            save_query_contact_sheet(query_path, qid, flight_id, reranked[qid], tile_meta, flight_dir / f"{qid}_top10.png", args.top_k)

    print(f"Figures written to {figure_dir}")


if __name__ == "__main__":
    main()

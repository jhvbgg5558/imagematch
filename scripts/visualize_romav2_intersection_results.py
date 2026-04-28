#!/usr/bin/env python3
"""Visualize RoMa v2 intersection rerank outputs and baseline comparisons."""

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
ROMA_COLOR = "#ff7f0e"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-result-dir", required=True)
    parser.add_argument("--romav2-result-dir", required=True)
    parser.add_argument("--tiles-csv", required=True)
    parser.add_argument("--query-manifest-csv", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--rerank-top-k", type=int, default=20)
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
    labels = ["R@1", "R@5", "R@10", "MRR"]
    baseline_vals = [
        overall["baseline_intersection_recall@1"],
        overall["baseline_intersection_recall@5"],
        overall["baseline_intersection_recall@10"],
        overall["baseline_intersection_mrr"],
    ]
    roma_vals = [
        overall["romav2_intersection_recall@1"],
        overall["romav2_intersection_recall@5"],
        overall["romav2_intersection_recall@10"],
        overall["romav2_intersection_mrr"],
    ]
    x = np.arange(len(labels))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    b1 = ax.bar(x - width / 2, baseline_vals, width, label="Baseline", color=BASELINE_COLOR)
    b2 = ax.bar(x + width / 2, roma_vals, width, label="RoMa v2", color=ROMA_COLOR)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Value")
    ax.set_title("Baseline vs RoMa v2 Intersection Metrics")
    ax.legend()
    for bars in (b1, b2):
        for bar in bars:
            value = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_top1_error_mean(overall: dict, out_path: Path) -> None:
    labels = ["Baseline", "RoMa v2"]
    vals = [overall["baseline_top1_error_m_mean"], overall["romav2_top1_error_m_mean"]]
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    bars = ax.bar(np.arange(len(labels)), vals, color=[BASELINE_COLOR, ROMA_COLOR])
    ax.set_xticks(np.arange(len(labels)), labels)
    ax.set_ylabel("Top-1 Error Mean (m)")
    ax.set_title("Baseline vs RoMa v2 Top-1 Error Mean")
    ymax = max(vals) * 1.18 if max(vals) > 0 else 1.0
    ax.set_ylim(0, ymax)
    for bar, value in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, value + ymax * 0.02, f"{value:.1f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_multi_flight(per_flight_rows: list[dict[str, str]], out_path: Path) -> None:
    labels = [row["flight_tag"] for row in per_flight_rows]
    x = np.arange(len(labels))
    width = 0.35
    baseline = [float(row["baseline_intersection_recall@10"]) for row in per_flight_rows]
    roma = [float(row["romav2_intersection_recall@10"]) for row in per_flight_rows]
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    b1 = ax.bar(x - width / 2, baseline, width, label="Baseline R@10", color=BASELINE_COLOR)
    b2 = ax.bar(x + width / 2, roma, width, label="RoMa v2 R@10", color=ROMA_COLOR)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Recall")
    ax.set_title("RoMa v2 Multi-Flight Recall@10")
    ax.legend()
    for bars in (b1, b2):
        for bar in bars:
            value = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.2f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def save_query_contact_sheet(query_path: Path, qid: str, flight_tag: str, rows: list[dict[str, str]], tile_meta: dict[str, dict[str, str]], out_path: Path, top_k: int) -> None:
    images = [labeled_thumb(query_path, [f"query_id: {qid}", f"flight_id: {flight_tag}", "intersection truth"], QUERY_BORDER)]
    for row in rows[:top_k]:
        tile_id = row["candidate_tile_id"]
        md = tile_meta[tile_id]
        inlier_count = int(row.get("inlier_count", "0") or 0)
        score = float(row.get("fused_score", row.get("global_score", "0")))
        images.append(
            labeled_thumb(
                Path(md["image_path"]),
                [
                    f"rank: {row['rank']}",
                    f"tile: {tile_id}",
                    f"scale: {int(float(md['tile_size_m']))}m inliers: {inlier_count} fused: {score:.3f}",
                ],
                HIT_BORDER if row["is_intersection_truth_hit"] == "1" else MISS_BORDER,
            )
        )
    make_contact_sheet(images, cols=3).save(out_path)


def main() -> None:
    args = parse_args()
    baseline_dir = Path(args.baseline_result_dir)
    romav2_dir = Path(args.romav2_result_dir)
    figure_dir = romav2_dir / "figures"
    ensure_dir(figure_dir / "_aggregate")

    overall = load_json(romav2_dir / "overall_summary.json")
    per_flight_rows = load_csv(romav2_dir / "per_flight_comparison.csv")
    query_comp = {row["query_id"]: row for row in load_csv(romav2_dir / "per_query_comparison.csv")}
    query_manifest = {row["query_id"]: row for row in load_csv(Path(args.query_manifest_csv))}
    tiles = {row["tile_id"]: row for row in load_csv(Path(args.tiles_csv))}

    plot_overall_compare(overall, figure_dir / "_aggregate" / "baseline_vs_romav2_compare.png")
    plot_top1_error_mean(overall, figure_dir / "_aggregate" / "baseline_vs_romav2_top1_error.png")
    plot_multi_flight(per_flight_rows, figure_dir / "_aggregate" / "romav2_multi_flight_r10.png")

    for flight_dir in sorted((romav2_dir / "stage7").iterdir()):
        if not flight_dir.is_dir():
            continue
        out_flight = figure_dir / flight_dir.name
        ensure_dir(out_flight)
        reranked = load_reranked(flight_dir / f"reranked_top{args.rerank_top_k}.csv")
        for qid, rows in reranked.items():
            flight_tag = flight_dir.name.split("_")[2]
            save_query_contact_sheet(
                query_path=Path(query_manifest[qid]["sanitized_query_path"]),
                qid=qid,
                flight_tag=flight_tag,
                rows=rows,
                tile_meta=tiles,
                out_path=out_flight / f"{qid}_top{args.top_k}.png",
                top_k=args.top_k,
            )

    print(f"Visualization assets written to {figure_dir}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Visualize single-run intersection-truth retrieval results."""

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
METRIC_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd"]


def configure_fonts() -> None:
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize intersection-truth retrieval outputs.")
    parser.add_argument("--result-dir", required=True, help="Experiment root directory.")
    parser.add_argument("--query-seed-csv", required=True)
    parser.add_argument("--query-truth-tiles-csv", required=True)
    parser.add_argument("--query-manifest-csv", required=True)
    parser.add_argument("--out-dir", required=True, help="Directory for output figures.")
    parser.add_argument("--top-k", type=int, default=10)
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_mapping(path: Path) -> dict[str, dict[str, str]]:
    data = load_json(path)
    return {item["id"]: item["metadata"] for item in data["items"]}


def load_truth_tiles(path: Path) -> dict[str, set[str]]:
    truth: dict[str, set[str]] = defaultdict(set)
    for row in load_csv(path):
        if row.get("is_intersection_truth", "1") == "1":
            truth[row["query_id"]].add(row["tile_id"])
    return truth


def load_retrieval(path: Path) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in load_csv(path):
        out[row["query_id"]].append(row)
    for rows in out.values():
        rows.sort(key=lambda item: int(item["rank"]))
    return out


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


def per_flight_metrics(summary: dict, seed_rows: dict[str, dict[str, str]]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in summary["per_query"]:
        grouped[seed_rows[row["query_id"]]["flight_id"]].append(row)

    out: dict[str, dict[str, float]] = {}
    for flight_id, rows in grouped.items():
        total = len(rows)
        errs = [float(row["top1_error_m"]) for row in rows if row["top1_error_m"] is not None]
        out[flight_id] = {
            "intersection_recall@1": sum(int(row["intersection_hit@1"]) for row in rows) / total if total else 0.0,
            "intersection_recall@5": sum(int(row["intersection_hit@5"]) for row in rows) / total if total else 0.0,
            "intersection_recall@10": sum(int(row["intersection_hit@10"]) for row in rows) / total if total else 0.0,
            "intersection_mrr": sum(float(row["intersection_reciprocal_rank"]) for row in rows) / total if total else 0.0,
            "top1_error_m_mean": sum(errs) / len(errs) if errs else float("nan"),
        }
    return out


def plot_metrics_bar(metrics: dict[str, float], title: str, out_path: Path) -> None:
    labels = ["Intersection R@1", "Intersection R@5", "Intersection R@10", "Intersection MRR"]
    values = [
        metrics["intersection_recall@1"],
        metrics["intersection_recall@5"],
        metrics["intersection_recall@10"],
        metrics["intersection_mrr"],
    ]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar(np.arange(len(labels)), values, color=METRIC_COLORS)
    ax.set_xticks(np.arange(len(labels)), labels)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Value")
    suffix = f" | Top1Err={metrics['top1_error_m_mean']:.1f}m" if not math.isnan(metrics["top1_error_m_mean"]) else ""
    ax.set_title(title + suffix)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_query_rr(summary: dict, seed_rows: dict[str, dict[str, str]], flight_id: str, out_path: Path) -> None:
    rows = [row for row in summary["per_query"] if seed_rows[row["query_id"]]["flight_id"] == flight_id]
    rows.sort(key=lambda item: item["query_id"])
    qids = [row["query_id"] for row in rows]
    vals = [float(row["intersection_reciprocal_rank"]) for row in rows]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    bars = ax.bar(qids, vals, color="#1f77b4")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Intersection Reciprocal Rank")
    flight_tag = seed_rows[rows[0]["query_id"]]["flight_id"].split("_")[2] if rows else flight_id
    ax.set_title(f"Flight {flight_tag} Query Selection Scores")
    ax.tick_params(axis="x", rotation=45)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02, f"{val:.2f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def save_query_contact_sheet(
    query_id: str,
    manifest_rows: dict[str, dict[str, str]],
    seed_rows: dict[str, dict[str, str]],
    retrieval_rows: dict[str, list[dict[str, str]]],
    mapping: dict[str, dict[str, str]],
    truth: dict[str, set[str]],
    out_path: Path,
    top_k: int,
) -> None:
    qrow = manifest_rows[query_id]
    srow = seed_rows[query_id]
    query_path = Path(qrow["sanitized_query_path"])
    images = [
        labeled_thumb(
            query_path,
            [query_id, srow["flight_id"].split("_")[2], "intersection truth"],
            QUERY_BORDER,
        )
    ]
    for row in retrieval_rows.get(query_id, [])[:top_k]:
        tile_id = row["candidate_tile_id"]
        md = mapping[tile_id]
        scale = int(float(md["tile_size_m"]))
        hit = tile_id in truth.get(query_id, set())
        images.append(
            labeled_thumb(
                Path(md["image_path"]),
                [f"#{row['rank']} {tile_id}", f"{scale}m", f"{float(row['score']):.3f}"],
                HIT_BORDER if hit else MISS_BORDER,
            )
        )
    sheet = make_contact_sheet(images, cols=3)
    sheet.save(out_path)


def plot_overall_metrics(summary: dict, out_path: Path) -> None:
    labels = ["Intersection R@1", "Intersection R@5", "Intersection R@10", "Intersection MRR"]
    values = [
        float(summary["intersection_recall@1"]),
        float(summary["intersection_recall@5"]),
        float(summary["intersection_recall@10"]),
        float(summary["intersection_mrr"]),
    ]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar(np.arange(len(labels)), values, color=METRIC_COLORS)
    ax.set_xticks(np.arange(len(labels)), labels)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Value")
    ax.set_title(f"Intersection Metrics | Top1Err={float(summary['top1_error_m_mean']):.1f}m")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_multi_flight_recall(flight_metrics: dict[str, dict[str, float]], out_path: Path) -> None:
    flights = sorted(flight_metrics)
    x = np.arange(len(flights))
    width = 0.25
    fig, ax = plt.subplots(figsize=(14, 5.4))
    r1 = [flight_metrics[f]["intersection_recall@1"] for f in flights]
    r5 = [flight_metrics[f]["intersection_recall@5"] for f in flights]
    r10 = [flight_metrics[f]["intersection_recall@10"] for f in flights]
    b1 = ax.bar(x - width, r1, width, label="Recall@1", color=METRIC_COLORS[0])
    b2 = ax.bar(x, r5, width, label="Recall@5", color=METRIC_COLORS[1])
    b3 = ax.bar(x + width, r10, width, label="Recall@10", color=METRIC_COLORS[2])
    ax.set_xticks(x, [f.split("_")[2] for f in flights])
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Recall")
    ax.set_title("Intersection Multi-Flight Recall")
    ax.legend()
    for bars in (b1, b2, b3):
        for bar in bars:
            value = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.2f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_top1_error_distribution(summary: dict, out_path: Path) -> None:
    rows = sorted(summary["per_query"], key=lambda row: row["query_id"])
    qids = [row["query_id"] for row in rows]
    vals = [float(row["top1_error_m"]) for row in rows]
    colors = [HIT_BORDER if row["intersection_hit@1"] else MISS_BORDER for row in rows]
    fig, ax = plt.subplots(figsize=(15, 5.4))
    bars = ax.bar(qids, vals, color=colors)
    ax.set_ylabel("Top-1 Error (m)")
    ax.set_title("Top-1 Error Distribution by Query")
    ax.tick_params(axis="x", rotation=45)
    max_val = max(vals) if vals else 0.0
    for bar, value in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, value + max_val * 0.01, f"{value:.0f}", ha="center", fontsize=7, rotation=90)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def write_readme(out_dir: Path, top_k: int) -> None:
    lines = [
        "# Intersection Retrieval Figures",
        "",
        "- Evaluation truth: intersection truth (non-zero area overlap).",
        f"- Contact sheets use top-{top_k} candidates from retrieval_top20.csv.",
        "- Aggregate metrics source: retrieval/summary_top20.json.",
        "",
        "## Directory Layout",
        "",
        "- _aggregate/: overall and multi-flight charts.",
        "- <flight_id>/: per-flight charts and per-query top-k contact sheets.",
    ]
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    configure_fonts()
    result_dir = Path(args.result_dir)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    ensure_dir(out_dir / "_aggregate")

    manifest_rows = {row["query_id"]: row for row in load_csv(Path(args.query_manifest_csv))}
    seed_rows = {row["query_id"]: row for row in load_csv(Path(args.query_seed_csv))}
    truth_tiles = load_truth_tiles(Path(args.query_truth_tiles_csv))
    retrieval = load_retrieval(result_dir / "retrieval" / "retrieval_top20.csv")
    summary = load_json(result_dir / "retrieval" / "summary_top20.json")
    mapping = load_mapping(result_dir / "faiss" / "satellite_tiles_ip_mapping.json")
    flight_metrics = per_flight_metrics(summary, seed_rows)

    aggregate_dir = out_dir / "_aggregate"
    plot_overall_metrics(summary, aggregate_dir / "overall_metrics_bar.png")
    plot_multi_flight_recall(flight_metrics, aggregate_dir / "multi_flight_recall.png")
    plot_top1_error_distribution(summary, aggregate_dir / "top1_error_distribution.png")

    flight_to_queries: dict[str, list[str]] = defaultdict(list)
    for qid, row in seed_rows.items():
        flight_to_queries[row["flight_id"]].append(qid)

    for flight_id, query_ids in sorted(flight_to_queries.items()):
        flight_dir = out_dir / flight_id
        ensure_dir(flight_dir)
        flight_tag = flight_id.split("_")[2]
        plot_metrics_bar(flight_metrics[flight_id], f"Flight {flight_tag}", flight_dir / "metrics_bar.png")
        plot_query_rr(summary, seed_rows, flight_id, flight_dir / "query_selection_scores.png")
        for qid in sorted(query_ids):
            save_query_contact_sheet(
                qid,
                manifest_rows,
                seed_rows,
                retrieval,
                mapping,
                truth_tiles,
                flight_dir / f"{qid}_top{args.top_k}.png",
                args.top_k,
            )
    write_readme(out_dir, args.top_k)
    print(f"Visualization outputs written to {out_dir}")


if __name__ == "__main__":
    main()

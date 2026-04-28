#!/usr/bin/env python3
"""Visualize three-scale vs four-scale DINOv2 retrieval results."""

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


THREE_COLOR = "#1f77b4"
FOUR_COLOR = "#ff7f0e"
QUERY_BORDER = "#555555"
HIT_BORDER = "#1a7f37"
MISS_BORDER = "#b42318"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize three-scale vs four-scale DINOv2 retrieval outputs.")
    parser.add_argument("--three-scale-dir", required=True)
    parser.add_argument("--four-scale-dir", required=True)
    parser.add_argument("--three-scale-truth-dir", required=True)
    parser.add_argument("--four-scale-truth-dir", required=True)
    parser.add_argument("--query-manifest-csv", required=True)
    parser.add_argument("--out-dir", required=True)
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


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    return {row["query_id"]: row for row in load_csv(path)}


def load_seed(path: Path) -> dict[str, dict[str, str]]:
    return {row["query_id"]: row for row in load_csv(path)}


def load_truth_tiles(path: Path) -> dict[str, set[str]]:
    truth: dict[str, set[str]] = defaultdict(set)
    for row in load_csv(path):
        truth[row["query_id"]].add(row["tile_id"])
    return truth


def load_retrieval(path: Path) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in load_csv(path):
        out[row["query_id"]].append(row)
    for rows in out.values():
        rows.sort(key=lambda item: int(item["rank"]))
    return out


def load_mapping(path: Path) -> dict[str, dict[str, str]]:
    data = load_json(path)
    return {item["id"]: item["metadata"] for item in data["items"]}


def add_border(img: Image.Image, color: str, width: int = 8) -> Image.Image:
    out = Image.new("RGB", (img.width + width * 2, img.height + width * 2), color)
    out.paste(img, (width, width))
    return out


def labeled_thumb(path: Path, label_lines: list[str], border_color: str, size: int = 320) -> Image.Image:
    with Image.open(path) as img:
        thumb = img.convert("RGB").resize((size, size))
    thumb = add_border(thumb, border_color, width=8)
    banner_h = 54
    draw = ImageDraw.Draw(thumb)
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


def reciprocal_rank_from_rank(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / rank


def per_flight_metrics(summary: dict, seed_rows: dict[str, dict[str, str]]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in summary["per_query"]:
        grouped[seed_rows[row["query_id"]]["flight_id"]].append(row)

    out: dict[str, dict[str, float]] = {}
    for flight_id, rows in grouped.items():
        total = len(rows)
        hit1 = sum(int(row["hit@1"]) for row in rows)
        hit5 = sum(int(row["hit@5"]) for row in rows)
        hit10 = sum(int(row["hit@10"]) for row in rows)
        mrr = sum(float(row["reciprocal_rank"]) for row in rows) / total if total else 0.0
        errs = [float(row["top1_error_m"]) for row in rows if row["top1_error_m"] is not None]
        out[flight_id] = {
            "recall@1": hit1 / total if total else 0.0,
            "recall@5": hit5 / total if total else 0.0,
            "recall@10": hit10 / total if total else 0.0,
            "mrr": mrr,
            "top1_error_m_mean": sum(errs) / len(errs) if errs else float("nan"),
        }
    return out


def plot_flight_metrics(metrics: dict[str, float], title: str, out_path: Path) -> None:
    labels = ["Recall@1", "Recall@5", "Recall@10", "MRR"]
    vals = [metrics["recall@1"], metrics["recall@5"], metrics["recall@10"], metrics["mrr"]]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar(x, vals, color=[THREE_COLOR, FOUR_COLOR, "#4daf4a", "#984ea3"])
    ax.set_ylim(0, 1.1)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Value")
    top1_err = metrics["top1_error_m_mean"]
    suffix = f" | Top1Err={top1_err:.1f}m" if not math.isnan(top1_err) else ""
    ax.set_title(title + suffix)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02, f"{val:.3f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def plot_query_rr(
    summary: dict,
    seed_rows: dict[str, dict[str, str]],
    flight_id: str,
    out_path: Path,
    color: str,
    title: str,
) -> None:
    rows = [row for row in summary["per_query"] if seed_rows[row["query_id"]]["flight_id"] == flight_id]
    rows.sort(key=lambda item: item["query_id"])
    qids = [row["query_id"] for row in rows]
    vals = [float(row["reciprocal_rank"]) for row in rows]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    bars = ax.bar(qids, vals, color=color)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Reciprocal Rank")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=45)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02, f"{val:.2f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def save_query_contact_sheet(
    query_id: str,
    flight_id: str,
    manifest_rows: dict[str, dict[str, str]],
    retrieval_rows: dict[str, list[dict[str, str]]],
    mapping: dict[str, dict[str, str]],
    truth: dict[str, set[str]],
    scale_tag: str,
    out_path: Path,
    top_k: int,
) -> None:
    qrow = manifest_rows[query_id]
    imgs = [
        labeled_thumb(
            Path(qrow["sanitized_query_path"]),
            [query_id, flight_id.split("_")[2], scale_tag],
            QUERY_BORDER,
        )
    ]
    for row in retrieval_rows.get(query_id, [])[:top_k]:
        tile_id = row["candidate_tile_id"]
        md = mapping[tile_id]
        hit = tile_id in truth.get(query_id, set())
        imgs.append(
            labeled_thumb(
                Path(md["image_path"]),
                [f"#{row['rank']} {tile_id}", f"{int(float(md['tile_size_m']))}m", f"{float(row['score']):.3f}"],
                HIT_BORDER if hit else MISS_BORDER,
            )
        )
    sheet = make_contact_sheet(imgs, cols=3)
    sheet.save(out_path)


def plot_metric_compare(name: str, three_val: float, four_val: float, out_path: Path, ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.8))
    labels = ["three_scale", "four_scale"]
    vals = [three_val, four_val]
    bars = ax.bar(labels, vals, color=[THREE_COLOR, FOUR_COLOR])
    ax.set_ylabel(ylabel)
    ax.set_title(name)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + (0.02 if ylabel != "Meters" else max(vals) * 0.01), f"{val:.3f}", ha="center")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def plot_overall_dashboard(three: dict, four: dict, cmp_summary: dict, out_path: Path) -> None:
    metrics = ["recall@1", "recall@5", "recall@10", "mrr", "top1_error_m_mean"]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    axes = axes.flatten()
    for idx, metric in enumerate(metrics):
        ax = axes[idx]
        vals = [three[metric], four[metric]]
        ax.bar(["3-scale", "4-scale"], vals, color=[THREE_COLOR, FOUR_COLOR])
        ax.set_title(metric)
        for x, v in enumerate(vals):
            ax.text(x, v + (0.02 if metric != "top1_error_m_mean" else max(vals) * 0.01), f"{v:.3f}", ha="center")
    ax = axes[-1]
    vals = [cmp_summary["improved_query_count"], cmp_summary["degraded_query_count"], cmp_summary["unchanged_query_count"]]
    ax.bar(["improved", "degraded", "unchanged"], vals, color=["#2ca02c", "#d62728", "#7f7f7f"])
    ax.set_title("Rank Shift Counts")
    for x, v in enumerate(vals):
        ax.text(x, v + 0.2, str(v), ha="center")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def plot_multi_flight_recall(
    three_metrics: dict[str, dict[str, float]],
    four_metrics: dict[str, dict[str, float]],
    out_path: Path,
) -> None:
    flights = sorted(three_metrics)
    metric_keys = ["recall@1", "recall@5", "recall@10"]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), sharey=True)
    x = np.arange(len(flights))
    width = 0.35
    for ax, metric in zip(axes, metric_keys):
        v3 = [three_metrics[f][metric] for f in flights]
        v4 = [four_metrics[f][metric] for f in flights]
        ax.bar(x - width / 2, v3, width, label="3-scale", color=THREE_COLOR)
        ax.bar(x + width / 2, v4, width, label="4-scale", color=FOUR_COLOR)
        ax.set_title(metric)
        ax.set_xticks(x, [f.split("_")[2] for f in flights], rotation=0)
        ax.set_ylim(0, 1.0)
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def plot_rank_shift(cmp_summary: dict, out_path: Path) -> None:
    improved = {row["query_id"]: row for row in cmp_summary["improved_queries"]}
    degraded = {row["query_id"]: row for row in cmp_summary["degraded_queries"]}
    all_ids = sorted(set(improved) | set(degraded))
    if not all_ids:
        all_ids = [f"q_{i:03d}" for i in range(1, 41)]
    vals = []
    for qid in all_ids:
        if qid in improved:
            row = improved[qid]
        elif qid in degraded:
            row = degraded[qid]
        else:
            vals.append(0)
            continue
        r3 = row["three_scale_first_truth_rank"] or 99
        r4 = row["four_scale_first_truth_rank"] or 99
        vals.append(r3 - r4)
    colors = ["#2ca02c" if v > 0 else "#d62728" if v < 0 else "#7f7f7f" for v in vals]
    fig, ax = plt.subplots(figsize=(13, 4.8))
    ax.bar(all_ids, vals, color=colors)
    ax.axhline(0, color="black", linewidth=1)
    ax.set_ylabel("three_scale_rank - four_scale_rank")
    ax.set_title("First Truth Rank Shift")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def plot_new_top1_queries(cmp_summary: dict, out_path: Path) -> None:
    rows = cmp_summary["new_top1_hits_with_300m"]
    labels = [row["query_id"] for row in rows] or ["none"]
    vals = [1] * len(rows) or [0]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(labels, vals, color=FOUR_COLOR)
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("New Top1 Hit")
    ax.set_title("Queries with New Top1 Hits After Adding 300m")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def visualize_single_scale(
    scale_name: str,
    scale_tag: str,
    result_dir: Path,
    truth_dir: Path,
    manifest_rows: dict[str, dict[str, str]],
    out_root: Path,
    top_k: int,
    color: str,
) -> dict[str, dict[str, float]]:
    summary = load_json(result_dir / "summary.json")
    retrieval = load_retrieval(result_dir / "retrieval_top10.csv")
    mapping = load_mapping(result_dir / "satellite_tiles_ip_mapping.json")
    seed_rows = load_seed(truth_dir / "queries_truth_seed.csv")
    truth = load_truth_tiles(truth_dir / "query_truth_tiles.csv")
    flight_metrics = per_flight_metrics(summary, seed_rows)

    flight_to_queries: dict[str, list[str]] = defaultdict(list)
    for qid, row in seed_rows.items():
        flight_to_queries[row["flight_id"]].append(qid)

    for flight_id, query_ids in flight_to_queries.items():
        flight_dir = out_root / scale_name / flight_id
        ensure_dir(flight_dir)
        plot_flight_metrics(flight_metrics[flight_id], f"{scale_tag} {flight_id}", flight_dir / "metrics_bar.png")
        plot_query_rr(summary, seed_rows, flight_id, flight_dir / "query_selection_scores.png", color, f"{scale_tag} Reciprocal Rank")
        for qid in sorted(query_ids):
            save_query_contact_sheet(
                qid,
                flight_id,
                manifest_rows,
                retrieval,
                mapping,
                truth,
                scale_tag,
                flight_dir / f"{qid}_top{top_k}.png",
                top_k,
            )
    return flight_metrics


def main() -> None:
    args = parse_args()
    three_dir = Path(args.three_scale_dir)
    four_dir = Path(args.four_scale_dir)
    three_truth = Path(args.three_scale_truth_dir)
    four_truth = Path(args.four_scale_truth_dir)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    ensure_dir(out_dir / "_aggregate")

    manifest_rows = load_manifest(Path(args.query_manifest_csv))
    three_summary = load_json(three_dir / "summary.json")
    four_summary = load_json(four_dir / "summary.json")
    cmp_summary = load_json(out_dir.parent / "comparison_summary.json") if (out_dir.parent / "comparison_summary.json").exists() else {}

    three_metrics = visualize_single_scale(
        "three_scale",
        "3-scale",
        three_dir,
        three_truth,
        manifest_rows,
        out_dir,
        args.top_k,
        THREE_COLOR,
    )
    four_metrics = visualize_single_scale(
        "four_scale",
        "4-scale",
        four_dir,
        four_truth,
        manifest_rows,
        out_dir,
        args.top_k,
        FOUR_COLOR,
    )

    agg = out_dir / "_aggregate"
    plot_metric_compare("Recall@1", three_summary["recall@1"], four_summary["recall@1"], agg / "three_vs_four_recall1.png", "Recall")
    plot_metric_compare("Recall@5", three_summary["recall@5"], four_summary["recall@5"], agg / "three_vs_four_recall5.png", "Recall")
    plot_metric_compare("Recall@10", three_summary["recall@10"], four_summary["recall@10"], agg / "three_vs_four_recall10.png", "Recall")
    plot_metric_compare("MRR", three_summary["mrr"], four_summary["mrr"], agg / "three_vs_four_mrr.png", "MRR")
    plot_metric_compare(
        "Top1 Error Mean",
        three_summary["top1_error_m_mean"],
        four_summary["top1_error_m_mean"],
        agg / "three_vs_four_top1_error.png",
        "Meters",
    )
    if cmp_summary:
        plot_overall_dashboard(three_summary, four_summary, cmp_summary, agg / "three_vs_four_overall_dashboard.png")
        plot_rank_shift(cmp_summary, agg / "three_vs_four_rank_shift.png")
        plot_new_top1_queries(cmp_summary, agg / "three_vs_four_new_top1_queries.png")
    plot_multi_flight_recall(three_metrics, four_metrics, agg / "three_vs_four_multi_flight_recall.png")
    print(f"Visualization outputs written to {out_dir}")


if __name__ == "__main__":
    main()

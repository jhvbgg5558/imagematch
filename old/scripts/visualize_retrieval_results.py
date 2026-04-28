#!/usr/bin/env python3
"""Visualize retrieval results for stage7 reporting."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize retrieval results and metrics.")
    parser.add_argument("--query-metadata-csv", required=True)
    parser.add_argument("--retrieval-results-csv", required=True)
    parser.add_argument("--analysis-json", required=True)
    parser.add_argument("--mapping-json", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def load_queries(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["query_id"]: row for row in reader}


def load_results(path: Path) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.setdefault(row["query_id"], []).append(row)
    for rows in out.values():
        rows.sort(key=lambda x: int(x["rank"]))
    return out


def load_mapping(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {item["id"]: item["metadata"] for item in data["items"]}


def add_border(img: Image.Image, color: str, width: int = 8) -> Image.Image:
    bordered = Image.new("RGB", (img.width + 2 * width, img.height + 2 * width), color)
    bordered.paste(img, (width, width))
    return bordered


def labeled_thumb(path: Path, label: str, hit: bool | None = None, size: int = 320) -> Image.Image:
    with Image.open(path) as img:
        thumb = img.convert("RGB").resize((size, size))
    color = "#1a7f37" if hit else "#b42318" if hit is not None else "#444444"
    thumb = add_border(thumb, color=color, width=8)
    draw = ImageDraw.Draw(thumb)
    draw.rectangle((0, 0, thumb.width, 34), fill=(0, 0, 0))
    draw.text((8, 8), label, fill=(255, 255, 255))
    return thumb


def make_contact_sheet(images: list[Image.Image], cols: int = 3, gap: int = 12, bg=(245, 245, 245)) -> Image.Image:
    if not images:
        raise ValueError("No images to compose")
    w = max(img.width for img in images)
    h = max(img.height for img in images)
    rows = math.ceil(len(images) / cols)
    canvas = Image.new("RGB", (cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap), bg)
    for idx, img in enumerate(images):
        r = idx // cols
        c = idx % cols
        x = gap + c * (w + gap)
        y = gap + r * (h + gap)
        canvas.paste(img, (x, y))
    return canvas


def plot_metrics(analysis: dict, out_path: Path) -> None:
    scale_keys = sorted(analysis["per_scale"].keys(), key=lambda x: float(x))
    labels = ["Overall"] + [f"{k}m" for k in scale_keys]
    r1 = [analysis["overall"]["recall@1"]] + [analysis["per_scale"][k]["recall@1"] for k in scale_keys]
    r5 = [analysis["overall"]["recall@5"]] + [analysis["per_scale"][k]["recall@5"] for k in scale_keys]
    r10 = [analysis["overall"]["recall@10"]] + [analysis["per_scale"][k]["recall@10"] for k in scale_keys]

    x = np.arange(len(labels))
    width = 0.22
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(x - width, r1, width, label="Recall@1")
    ax.bar(x, r5, width, label="Recall@5")
    ax.bar(x + width, r10, width, label="Recall@10")
    ax.set_ylim(0, 1.1)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Recall")
    ax.set_title("Stage7 First-Round Retrieval Metrics")
    ax.legend()
    for vals, offset in [(r1, -width), (r5, 0), (r10, width)]:
        for i, v in enumerate(vals):
            ax.text(x[i] + offset, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def plot_query_scale_scores(queries: dict[str, dict[str, str]], out_path: Path) -> None:
    qids = list(queries.keys())
    scores = [float(queries[q]["score"]) for q in qids]
    scales = [int(float(queries[q]["scale_m"])) for q in qids]
    colors = ["#1f77b4" if s == 120 else "#ff7f0e" for s in scales]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar(qids, scores, color=colors)
    ax.set_ylabel("Selection Score")
    ax.set_title("Query Block Selection Scores")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    queries = load_queries(Path(args.query_metadata_csv))
    results = load_results(Path(args.retrieval_results_csv))
    with Path(args.analysis_json).open("r", encoding="utf-8") as f:
        analysis = json.load(f)
    mapping = load_mapping(Path(args.mapping_json))

    plot_metrics(analysis, out_dir / "metrics_bar.png")
    plot_query_scale_scores(queries, out_dir / "query_selection_scores.png")

    for qid, qrow in queries.items():
        query_img = labeled_thumb(Path(qrow["image_path"]), f"{qid} query", hit=None)
        candidate_imgs = [query_img]
        for row in results.get(qid, [])[: args.top_k]:
            tile_id = row["candidate_tile_id"]
            meta = mapping[tile_id]
            label = f"#{row['rank']} {tile_id}"
            hit = row["is_truth_hit"] == "1"
            candidate_imgs.append(labeled_thumb(Path(meta["image_path"]), label, hit=hit))
        sheet = make_contact_sheet(candidate_imgs, cols=3)
        sheet.save(out_dir / f"{qid}_top{args.top_k}.png")

    print(f"Visualization outputs written to {out_dir}")


if __name__ == "__main__":
    main()

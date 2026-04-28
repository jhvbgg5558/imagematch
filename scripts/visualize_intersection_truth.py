#!/usr/bin/env python3
"""Visualize intersection-truth tiles for all queries and aggregate stats."""

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


THUMB_SIZE = 320
QUERY_BORDER = "#555555"
TRUTH_BORDER = "#1a7f37"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", required=True, help="Directory containing intersection truth outputs.")
    parser.add_argument("--out-dir", required=True, help="Target directory under newoutput for the visualizations.")
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def add_border(img: Image.Image, color: str, width: int = 8) -> Image.Image:
    out = Image.new("RGB", (img.width + 2 * width, img.height + 2 * width), color)
    out.paste(img, (width, width))
    return out


def labeled_thumb(path: Path, label_lines: list[str], border_color: str) -> Image.Image:
    with Image.open(path) as img:
        thumb = img.convert("RGB").resize((THUMB_SIZE, THUMB_SIZE))
    thumb = add_border(thumb, border_color)
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


def plot_truth_counts(
    labels: list[str],
    values: list[float],
    path: Path,
    title: str,
    ylabel: str,
    figsize: tuple[int, int] = (12, 4.5),
) -> None:
    fig, ax = plt.subplots(figsize=figsize)
    bars = ax.bar(labels, values, color="#1f77b4")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=45)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.2, f"{int(val)}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_scale_breakdown(
    rows: list[dict[str, str]],
    path: Path,
    title: str,
    figsize: tuple[int, int] = (13, 5.2),
) -> None:
    labels = [row["query_id"] for row in rows]
    x = np.arange(len(labels))
    scales = ["truth_count_200m", "truth_count_300m", "truth_count_500m", "truth_count_700m"]
    v200 = np.array([float(row[scales[0]]) for row in rows])
    v300 = np.array([float(row[scales[1]]) for row in rows])
    v500 = np.array([float(row[scales[2]]) for row in rows])
    v700 = np.array([float(row[scales[3]]) for row in rows])
    fig, ax = plt.subplots(figsize=figsize)
    ax.bar(x, v200, label="200m", color="#4c78a8")
    ax.bar(x, v300, bottom=v200, label="300m", color="#f58518")
    ax.bar(x, v500, bottom=v200 + v300, label="500m", color="#54a24b")
    ax.bar(x, v700, bottom=v200 + v300 + v500, label="700m", color="#b279a2")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45)
    ax.set_ylabel("Truth Tile Count")
    ax.set_title(title)
    ax.legend()
    totals = v200 + v300 + v500 + v700
    for xi, total in zip(x, totals):
        ax.text(xi, total + 0.4, f"{int(total)}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def build_summary_md(summary: dict, rows: list[dict[str, str]], out_path: Path, label: str) -> None:
    labels = sorted(rows, key=lambda r: r["query_id"])
    richest = max(labels, key=lambda r: int(r["truth_count_total"]))
    sparsest = min(labels, key=lambda r: int(r["truth_count_total"]))
    lines = [
        f"# {label} Intersection Truth Summary",
        "",
        f"- Query count: {len(labels)}",
        f"- Total truth tiles: {summary['truth_tile_count']}",
        f"- Mean truth count: {summary['mean_truth_count']:.2f}",
        f"- Scales: 200m={summary['scale_counts']['200m']}, 300m={summary['scale_counts']['300m']}, 500m={summary['scale_counts']['500m']}, 700m={summary['scale_counts']['700m']}",
        "",
        "## Highlighted Queries",
        "",
        f"- Most truth-rich: `{richest['query_id']}` with {richest['truth_count_total']} tiles.",
        f"- Least truth-rich: `{sparsest['query_id']}` with {sparsest['truth_count_total']} tiles.",
        "",
        "## Notes",
        "",
        "- True tiles are defined by any non-zero area intersection with the query footprint.",
        "- Larger scales and overlap increase the number of truth tiles, which explains why some candidates now cover the query range without being strict-truth-level matches.",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_query_contact_sheet(
    query_row: dict[str, str],
    tile_rows: list[dict[str, str]],
    out_dir: Path,
    flight_tag: str,
) -> None:
    truths = sorted(
        tile_rows,
        key=lambda row: (float(row["tile_size_m"]), -float(row["intersection_area_m2"])),
    )
    page_size = 11
    for page_idx in range(math.ceil(len(truths) / page_size)):
        chunk = truths[page_idx * page_size : (page_idx + 1) * page_size]
        images = [
            labeled_thumb(
                Path(query_row["query_image_path"]),
                [query_row["query_id"], f"flight {flight_tag}", "intersection truth"],
                QUERY_BORDER,
            )
        ]
        for row in chunk:
            images.append(
                labeled_thumb(
                    Path(row["image_path"]),
                    [
                        row["tile_id"],
                        f"{int(float(row['tile_size_m']))}m",
                        f"area={float(row['intersection_area_m2']):.1f}m²",
                    ],
                    TRUTH_BORDER,
                )
            )
        sheet = make_contact_sheet(images, cols=3)
        suffix = "" if page_idx == 0 and len(truths) <= page_size else f"_p{page_idx+1}"
        out_path = out_dir / f"{query_row['query_id']}_query_vs_truth{suffix}.png"
        sheet.save(out_path)


def aggregate_summary(rows: list[dict[str, str]]) -> dict:
    total_truth = sum(int(row["truth_count_total"]) for row in rows)
    mean_truth = total_truth / len(rows) if rows else 0.0
    scale_counts = {
        "200m": sum(int(row["truth_count_200m"]) for row in rows),
        "300m": sum(int(row["truth_count_300m"]) for row in rows),
        "500m": sum(int(row["truth_count_500m"]) for row in rows),
        "700m": sum(int(row["truth_count_700m"]) for row in rows),
    }
    return {
        "query_count": len(rows),
        "truth_tile_count": total_truth,
        "mean_truth_count": mean_truth,
        "scale_counts": scale_counts,
    }


def main() -> None:
    args = parse_args()
    result_dir = Path(args.result_dir)
    out_dir = Path(args.out_dir)
    query_csv = result_dir / "query_truth" / "query_truth.csv"
    tile_csv = result_dir / "query_truth" / "query_truth_tiles.csv"
    summary_json = result_dir / "query_truth" / "intersection_truth_summary.json"

    ensure_dir(out_dir)
    aggregate_dir = out_dir / "_aggregate"
    ensure_dir(aggregate_dir)

    query_rows = load_csv(query_csv)
    tile_rows = load_csv(tile_csv)

    # map query_id -> list of truth tiles
    truth_map: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in tile_rows:
        truth_map[row["query_id"]].append(row)

    flights: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in query_rows:
        flights[row["flight_id"]].append(row)

    agg_summary = aggregate_summary(query_rows)
    summary_path = aggregate_dir / "summary.md"
    build_summary_md(agg_summary, query_rows, summary_path, "Overall")

    overall_truth_count_path = aggregate_dir / "overall_truth_count_distribution.png"
    str_labels = [row["query_id"] for row in sorted(query_rows, key=lambda r: r["query_id"])]
    values = [float(row["truth_count_total"]) for row in sorted(query_rows, key=lambda r: r["query_id"])]
    plot_truth_counts(str_labels, values, overall_truth_count_path, "Intersection Truth Count per Query", "Truth Tile Count")

    overall_scale_path = aggregate_dir / "overall_truth_scale_breakdown.png"
    plot_scale_breakdown(sorted(query_rows, key=lambda r: r["query_id"]), overall_scale_path, "Intersection Truth Scale Breakdown")

    flight_truth_count_path = aggregate_dir / "flight_truth_count_distribution.png"
    flight_labels = []
    flight_values = []
    for flight_id, rows in flights.items():
        flight_labels.append(flight_id.split("_")[2])
        flight_values.append(sum(int(row["truth_count_total"]) for row in rows) / len(rows))
    plot_truth_counts(flight_labels, flight_values, flight_truth_count_path, "Mean Intersection Truth per Flight", "Mean Truth Count")

    flight_scale_path = aggregate_dir / "flight_truth_scale_breakdown.png"
    fig, ax = plt.subplots(figsize=(8, 4.5))
    indices = np.arange(len(flight_labels))
    width = 0.2
    scales = ["200m", "300m", "500m", "700m"]
    colors = ["#4c78a8", "#f58518", "#54a24b", "#b279a2"]
    for i, scale in enumerate(scales):
        totals = []
        for flight_id, rows in flights.items():
            totals.append(sum(int(row[f"truth_count_{scale}"]) for row in rows))
        ax.bar(indices + i * width, totals, width, label=scale, color=colors[i])
    ax.set_xticks(indices + width * 1.5)
    ax.set_xticklabels([f.split("_")[2] for f in flights], rotation=45)
    ax.set_ylabel("Truth Tile Count")
    ax.set_title("Flight-level Scale Breakdown")
    ax.legend()
    fig.tight_layout()
    fig.savefig(flight_scale_path, dpi=180)
    plt.close(fig)

    # per-flight outputs
    for flight_id, rows in flights.items():
        flight_dir = out_dir / flight_id
        ensure_dir(flight_dir)
        sub_summary = aggregate_summary(rows)
        build_summary_md(sub_summary, rows, flight_dir / "summary.md", f"{flight_id} (flight-level)")
        plot_truth_counts(
            [row["query_id"] for row in sorted(rows, key=lambda r: r["query_id"])],
            [float(row["truth_count_total"]) for row in sorted(rows, key=lambda r: r["query_id"])],
            flight_dir / "truth_count_distribution.png",
            f"{flight_id} Intersection Truth Count",
            "Truth Tile Count",
        )
        plot_scale_breakdown(sorted(rows, key=lambda r: r["query_id"]), flight_dir / "truth_scale_breakdown.png", f"{flight_id} Truth Scale Breakdown")
        for row in sorted(rows, key=lambda r: r["query_id"]):
            tiles = truth_map[row["query_id"]]
            build_query_contact_sheet(row, tiles, flight_dir, flight_id.split("_")[2])

    # copy intersection summary for reference
    if summary_json.exists():
        target = aggregate_dir / summary_json.name
        target.write_text(summary_json.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Intersection truth visualization written to {out_dir}")


if __name__ == "__main__":
    main()

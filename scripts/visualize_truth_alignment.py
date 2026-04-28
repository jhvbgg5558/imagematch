#!/usr/bin/env python3
"""Visualize query images with their coverage-truth tiles for one flight."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw


QUERY_BORDER = "#555555"
TRUTH_BORDER = "#1a7f37"
SOFT_BORDER = "#f59e0b"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize query images together with coverage-truth tiles.")
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--flight-id", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


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


def short_flight_name(flight_id: str) -> str:
    parts = flight_id.split("_")
    return parts[2] if len(parts) >= 3 else flight_id


def plot_truth_count_distribution(query_rows: list[dict[str, str]], out_path: Path) -> None:
    query_rows = sorted(query_rows, key=lambda row: row["query_id"])
    labels = [row["query_id"] for row in query_rows]
    vals = [float(row["truth_count_total"]) for row in query_rows]
    fig, ax = plt.subplots(figsize=(12, 4.8))
    bars = ax.bar(labels, vals, color="#1f77b4")
    ax.set_ylabel("Truth Tile Count")
    ax.set_title("Flight 009 Truth Count Distribution")
    ax.tick_params(axis="x", rotation=45)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.15, f"{int(val)}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_truth_scale_breakdown(query_rows: list[dict[str, str]], out_path: Path) -> None:
    query_rows = sorted(query_rows, key=lambda row: row["query_id"])
    labels = [row["query_id"] for row in query_rows]
    x = np.arange(len(labels))
    v200 = np.array([float(row["truth_count_200m"]) for row in query_rows])
    v300 = np.array([float(row["truth_count_300m"]) for row in query_rows])
    v500 = np.array([float(row["truth_count_500m"]) for row in query_rows])
    v700 = np.array([float(row["truth_count_700m"]) for row in query_rows])
    fig, ax = plt.subplots(figsize=(13, 5.2))
    ax.bar(x, v200, label="200m", color="#4c78a8")
    ax.bar(x, v300, bottom=v200, label="300m", color="#f58518")
    ax.bar(x, v500, bottom=v200 + v300, label="500m", color="#54a24b")
    ax.bar(x, v700, bottom=v200 + v300 + v500, label="700m", color="#b279a2")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Truth Tile Count")
    ax.set_title("Flight 009 Truth Scale Breakdown")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    totals = v200 + v300 + v500 + v700
    for xi, total in zip(x, totals):
        ax.text(xi, total + 0.15, f"{int(total)}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def build_summary_md(
    flight_id: str,
    query_rows: list[dict[str, str]],
    truth_tiles: dict[str, list[dict[str, str]]],
    out_path: Path,
) -> None:
    query_rows = sorted(query_rows, key=lambda row: row["query_id"])
    richest = max(query_rows, key=lambda row: int(row["truth_count_total"]))
    sparsest = min(query_rows, key=lambda row: int(row["truth_count_total"]))
    best_overlap = None
    for row in query_rows:
        top = truth_tiles[row["query_id"]][0]
        if best_overlap is None or float(top["coverage_ratio"]) > float(best_overlap["coverage_ratio"]):
            best_overlap = top

    lines = [
        "# Flight 009 Truth Visualization Summary",
        "",
        f"- Flight: {flight_id}",
        f"- Query count: {len(query_rows)}",
        f"- Mean truth count: {sum(float(r['truth_count_total']) for r in query_rows) / len(query_rows):.2f}",
        f"- Coverage threshold: {query_rows[0]['coverage_threshold']}",
        f"- Footprint core ratio: {query_rows[0]['footprint_core_ratio']}",
        (f"- Min valid ratio: {query_rows[0]['min_valid_ratio']}" if 'min_valid_ratio' in query_rows[0] else "- Min valid ratio: not applied"),
        "",
        "## Quick Observations",
        "",
        f"- Most truth-rich query: `{richest['query_id']}` with `{richest['truth_count_total']}` truth tiles.",
        f"- Most compact query: `{sparsest['query_id']}` with `{sparsest['truth_count_total']}` truth tiles.",
        f"- Highest top truth overlap: `{best_overlap['query_id']}` top tile `{best_overlap['tile_id']}` with coverage ratio `{float(best_overlap['coverage_ratio']):.3f}`.",
        "- This flight contains many 500m and 700m truth tiles, so the optimized truth set is often region-level similar rather than patch-level identical.",
        "- Queries with only large-scale truth tiles are expected to look less visually identical than old center-point truth, but they better reflect shared ground coverage.",
        "",
        "## Per Query",
        "",
    ]
    for row in query_rows:
        top = truth_tiles[row["query_id"]][0]
        lines.append(
            f"- `{row['query_id']}`: truth_count=`{row['truth_count_total']}`, "
            f"strict=`{row.get('strict_truth_count_total', '-')}`, soft=`{row.get('soft_truth_count_total', '-')}`, "
            f"top_truth=`{top['tile_id']}`, top_scale=`{int(float(top['tile_size_m']))}m`, "
            f"top_coverage_ratio=`{float(top['coverage_ratio']):.3f}`, "
            f"top_valid_ratio=`{float(top.get('valid_pixel_ratio', '1.0')):.3f}`"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_query_truth_sheet(
    query_row: dict[str, str],
    truth_rows: list[dict[str, str]],
    out_path: Path,
    flight_tag: str,
) -> None:
    images = [
        labeled_thumb(
            Path(query_row["query_image_path"]),
            [
                query_row["query_id"],
                f"flight {flight_tag}",
                f"truth_count={query_row['truth_count_total']}",
            ],
            QUERY_BORDER,
        )
    ]
    for row in truth_rows:
        is_strict = row.get("is_strict_truth", "1") == "1"
        valid_ratio = row.get("valid_pixel_ratio")
        validity_line = f"valid={float(valid_ratio):.3f}" if valid_ratio is not None else f"center={row['contains_query_center']}"
        images.append(
            labeled_thumb(
                Path(row["image_path"]),
                [
                    f"{row['tile_id']}",
                    f"{int(float(row['tile_size_m']))}m cov={float(row['coverage_ratio']):.3f}",
                    validity_line if is_strict else f"soft valid={float(valid_ratio):.3f}",
                ],
                TRUTH_BORDER if is_strict else SOFT_BORDER,
            )
        )
    sheet = make_contact_sheet(images, cols=3)
    sheet.save(out_path)


def main() -> None:
    args = parse_args()
    result_dir = Path(args.result_dir)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

    query_rows = [row for row in load_csv(result_dir / "query_truth" / "query_truth.csv") if row["flight_id"] == args.flight_id]
    tiles_rows = [row for row in load_csv(result_dir / "query_truth" / "query_truth_tiles.csv") if row["query_id"] in {r["query_id"] for r in query_rows}]

    truth_tiles: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in tiles_rows:
        truth_tiles[row["query_id"]].append(row)
    for rows in truth_tiles.values():
        rows.sort(
            key=lambda row: (
                -int(row.get("is_strict_truth", "1")),
                -float(row["coverage_ratio"]),
                -float(row.get("valid_pixel_ratio", "1.0")),
            )
        )

    flight_tag = short_flight_name(args.flight_id)
    for query_row in sorted(query_rows, key=lambda row: row["query_id"]):
        build_query_truth_sheet(
            query_row,
            truth_tiles[query_row["query_id"]],
            out_dir / f"{query_row['query_id']}_query_vs_truth.png",
            flight_tag,
        )

    plot_truth_count_distribution(query_rows, out_dir / "truth_count_distribution.png")
    plot_truth_scale_breakdown(query_rows, out_dir / "truth_scale_breakdown.png")
    build_summary_md(args.flight_id, query_rows, truth_tiles, out_dir / "summary.md")
    print(f"Truth visualization outputs written to {out_dir}")


if __name__ == "__main__":
    main()

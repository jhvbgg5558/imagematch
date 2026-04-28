#!/usr/bin/env python3
"""Visualize current-task query/satellite inputs, ROI, preprocessing, and scale stats."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SCALE_COLORS = {
    "200.0": "#1f77b4",
    "300.0": "#ff7f0e",
    "500.0": "#2ca02c",
    "700.0": "#d62728",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-seed-csv", required=True)
    parser.add_argument("--query-manifest-csv", required=True)
    parser.add_argument("--selected-summary-csv", required=True)
    parser.add_argument("--tile-metadata-csv", required=True)
    parser.add_argument("--roi-summary-json", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--roi-buffer-meters", type=float, default=250.0)
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def polygon_from_text(text: str) -> list[tuple[float, float]]:
    return [(float(x), float(y)) for x, y in json.loads(text)]


def bbox_area(bounds: tuple[float, float, float, float]) -> float:
    return max(0.0, bounds[2] - bounds[0]) * max(0.0, bounds[3] - bounds[1])


def draw_bbox(ax, bounds: tuple[float, float, float, float], color: str, label: str, linewidth: float = 2.0, linestyle: str = "-") -> None:
    min_x, min_y, max_x, max_y = bounds
    xs = [min_x, max_x, max_x, min_x, min_x]
    ys = [min_y, min_y, max_y, max_y, min_y]
    ax.plot(xs, ys, color=color, linewidth=linewidth, linestyle=linestyle, label=label)


def plot_query_satellite_overview(seed_rows: list[dict[str, str]], tile_rows: list[dict[str, str]], roi_bounds: tuple[float, float, float, float], raw_bbox: tuple[float, float, float, float], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 9))
    by_scale: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in tile_rows:
        by_scale[row["tile_size_m"]].append((float(row["center_x"]), float(row["center_y"])))
    for scale, pts in sorted(by_scale.items(), key=lambda kv: float(kv[0])):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.scatter(xs, ys, s=8, c=SCALE_COLORS.get(scale, "#777777"), alpha=0.35, label=f"tiles {int(float(scale))}m")

    flight_colors = ["#111111", "#4e79a7", "#f28e2b", "#59a14f"]
    by_flight: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in seed_rows:
        by_flight[row["flight_id"]].append(row)
    for idx, (flight_id, rows) in enumerate(sorted(by_flight.items())):
        xs = [float(r["query_x"]) for r in rows]
        ys = [float(r["query_y"]) for r in rows]
        ax.scatter(xs, ys, s=24, color=flight_colors[idx % len(flight_colors)], edgecolors="white", linewidths=0.3, label=f"query {flight_id.split('_')[2]}")

    draw_bbox(ax, raw_bbox, "#666666", "raw bbox", linewidth=1.8, linestyle="--")
    draw_bbox(ax, roi_bounds, "#111111", "roi + buffer", linewidth=2.2)
    ax.set_title("Current Task Input Overview: Queries, ROI, and Multi-Scale Satellite Tiles")
    ax.set_xlabel("X (EPSG:32650)")
    ax.set_ylabel("Y (EPSG:32650)")
    ax.legend(loc="best", fontsize=8)
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_query_footprints(seed_rows: list[dict[str, str]], roi_bounds: tuple[float, float, float, float], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 9))
    flight_colors = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759"]
    by_flight: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in seed_rows:
        by_flight[row["flight_id"]].append(row)
    for idx, (flight_id, rows) in enumerate(sorted(by_flight.items())):
        color = flight_colors[idx % len(flight_colors)]
        for row in rows:
            poly = polygon_from_text(row["footprint_polygon_xy"])
            xs = [p[0] for p in poly] + [poly[0][0]]
            ys = [p[1] for p in poly] + [poly[0][1]]
            ax.plot(xs, ys, color=color, alpha=0.35, linewidth=1.0)
        ax.plot([], [], color=color, linewidth=2.0, label=f"flight {flight_id.split('_')[2]}")
    draw_bbox(ax, roi_bounds, "#111111", "roi + buffer", linewidth=2.0)
    ax.set_title("Query Ground Footprints Under Current Metadata-Derived Geometry")
    ax.set_xlabel("X (EPSG:32650)")
    ax.set_ylabel("Y (EPSG:32650)")
    ax.legend(loc="best", fontsize=8)
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_scale_tile_counts(tile_rows: list[dict[str, str]], out_path: Path) -> dict[str, int]:
    counts = Counter(row["tile_size_m"] for row in tile_rows)
    labels = [f"{int(float(scale))}m" for scale in sorted(counts, key=float)]
    values = [counts[scale] for scale in sorted(counts, key=float)]
    colors = [SCALE_COLORS.get(scale, "#777777") for scale in sorted(counts, key=float)]
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    bars = ax.bar(np.arange(len(labels)), values, color=colors)
    ax.set_xticks(np.arange(len(labels)), labels)
    ax.set_ylabel("Tile Count")
    ax.set_title("Satellite Tile Count by Scale")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + max(values) * 0.01, f"{value}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return {k: int(v) for k, v in counts.items()}


def plot_query_footprint_areas(seed_rows: list[dict[str, str]], out_path: Path) -> None:
    rows = sorted(seed_rows, key=lambda r: r["query_id"])
    labels = [r["query_id"] for r in rows]
    values = [float(r["footprint_area_m2"]) / 1e4 for r in rows]
    fig, ax = plt.subplots(figsize=(13, 4.8))
    bars = ax.bar(labels, values, color="#4e79a7")
    ax.set_ylabel("Footprint Area (ha)")
    ax.set_title("Query Footprint Area by Query")
    ax.tick_params(axis="x", rotation=45)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + max(values) * 0.01, f"{value:.1f}", ha="center", fontsize=7)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_flight_query_counts(seed_rows: list[dict[str, str]], out_path: Path) -> None:
    counts = Counter(row["flight_id"].split("_")[2] for row in seed_rows)
    labels = sorted(counts)
    values = [counts[x] for x in labels]
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    bars = ax.bar(labels, values, color="#59a14f")
    ax.set_ylabel("Query Count")
    ax.set_title("Selected Query Count by Flight")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.1, f"{value}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_sanitization_overview(query_manifest_rows: list[dict[str, str]], out_path: Path) -> None:
    total = len(query_manifest_rows)
    removed = sum(int(row["has_metadata_removed"]) for row in query_manifest_rows)
    values = [removed, total - removed]
    labels = ["metadata removed", "remaining metadata flag=0"]
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    bars = ax.bar(np.arange(len(labels)), values, color=["#1f77b4", "#bbbbbb"])
    ax.set_xticks(np.arange(len(labels)), labels)
    ax.set_ylabel("Query Count")
    ax.set_title("Query Sanitization Status")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.1, f"{value}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

    seed_rows = load_csv(Path(args.query_seed_csv))
    query_manifest_rows = load_csv(Path(args.query_manifest_csv))
    selected_rows = load_csv(Path(args.selected_summary_csv))
    tile_rows = load_csv(Path(args.tile_metadata_csv))
    roi_summary = load_json(Path(args.roi_summary_json))

    roi_bounds = tuple(float(x) for x in roi_summary["roi_bounds"])
    raw_bbox = (
        roi_bounds[0] + args.roi_buffer_meters,
        roi_bounds[1] + args.roi_buffer_meters,
        roi_bounds[2] - args.roi_buffer_meters,
        roi_bounds[3] - args.roi_buffer_meters,
    )
    roi_area_m2 = bbox_area(roi_bounds)
    raw_bbox_area_m2 = bbox_area(raw_bbox)
    buffer_area_gain_m2 = roi_area_m2 - raw_bbox_area_m2

    plot_query_satellite_overview(seed_rows, tile_rows, roi_bounds, raw_bbox, out_dir / "query_satellite_overview.png")
    plot_query_footprints(seed_rows, roi_bounds, out_dir / "query_footprints_overview.png")
    scale_counts = plot_scale_tile_counts(tile_rows, out_dir / "scale_tile_count_bar.png")
    plot_query_footprint_areas(seed_rows, out_dir / "query_footprint_area_by_query.png")
    plot_flight_query_counts(seed_rows, out_dir / "flight_query_count_bar.png")
    plot_sanitization_overview(query_manifest_rows, out_dir / "query_sanitization_status.png")

    summary = {
        "query_count": len(seed_rows),
        "selected_query_rows": len(selected_rows),
        "sanitized_query_count": len(query_manifest_rows),
        "flight_ids": roi_summary["flight_ids"],
        "query_crs": seed_rows[0]["query_crs"] if seed_rows else "",
        "satellite_crs": roi_summary["satellite_crs"],
        "roi_buffer_meters": args.roi_buffer_meters,
        "raw_bbox": raw_bbox,
        "raw_bbox_area_m2": raw_bbox_area_m2,
        "roi_bounds": roi_bounds,
        "roi_area_m2": roi_area_m2,
        "buffer_area_gain_m2": buffer_area_gain_m2,
        "tile_count_total": len(tile_rows),
        "tile_count_by_scale": {f"{int(float(k))}m": int(v) for k, v in sorted(scale_counts.items(), key=lambda kv: float(kv[0]))},
        "footprint_area_m2_mean": sum(float(r["footprint_area_m2"]) for r in seed_rows) / len(seed_rows) if seed_rows else 0.0,
        "footprint_area_m2_min": min(float(r["footprint_area_m2"]) for r in seed_rows) if seed_rows else 0.0,
        "footprint_area_m2_max": max(float(r["footprint_area_m2"]) for r in seed_rows) if seed_rows else 0.0,
    }
    (out_dir / "dataset_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 当前输入数据与 ROI 说明",
        "",
        f"- Query 数量：`{summary['query_count']}`",
        f"- 航线数量：`{len(summary['flight_ids'])}`",
        f"- Query 坐标系：`{summary['query_crs']}`",
        f"- 卫片坐标系：`{summary['satellite_crs']}`",
        f"- ROI buffer：`{summary['roi_buffer_meters']:.1f}m`",
        f"- 原始 flight bbox 面积：`{summary['raw_bbox_area_m2'] / 1e6:.3f} km^2`",
        f"- 外扩后 ROI 面积：`{summary['roi_area_m2'] / 1e6:.3f} km^2`",
        f"- 外扩增加面积：`{summary['buffer_area_gain_m2'] / 1e6:.3f} km^2`",
        f"- 卫片 tile 总数：`{summary['tile_count_total']}`",
        "",
        "## 各尺度 tile 数",
        "",
    ]
    for scale, count in summary["tile_count_by_scale"].items():
        lines.append(f"- `{scale}`: `{count}`")
    lines.extend(
        [
            "",
            "## Query footprint 面积统计",
            "",
            f"- 平均：`{summary['footprint_area_m2_mean'] / 1e4:.2f} ha`",
            f"- 最小：`{summary['footprint_area_m2_min'] / 1e4:.2f} ha`",
            f"- 最大：`{summary['footprint_area_m2_max'] / 1e4:.2f} ha`",
            "",
            "## 当前预处理链路",
            "",
            "- 先从 4 条航线中选取代表性原始无人机图像作为 query 候选。",
            "- 再用 Pillow 重编码生成无 EXIF/XMP/GPS 的 query 副本，作为正式检索输入。",
            "- 卫片库先依据 ROI + fixed buffer 切出多尺度 tile，再对这些 tile 提取 DINOv2 特征并建 FAISS 索引。",
            "- 当前卫片库保留 native crop resolution，不在切片阶段统一缩放到固定像素尺寸。",
        ]
    )
    (out_dir / "dataset_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(out_dir)


if __name__ == "__main__":
    main()

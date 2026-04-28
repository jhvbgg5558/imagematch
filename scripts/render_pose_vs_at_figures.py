#!/usr/bin/env python3
"""Render core pose-vs-AT metric figures for formal Pose v1.

Purpose:
- visualize layer-2 `best pose vs ODM/AT reference pose` metrics from the
  unified validation suite;
- highlight the current largest-error query dynamically instead of relying on
  a hardcoded historical query id;
- emit a figure README and manifest next to the generated PNGs.

Main inputs:
- `pose_vs_at/per_query_pose_vs_at.csv`;
- `pose_vs_at/per_flight_pose_vs_at.csv`;
- `pose_vs_at/overall_pose_vs_at.json`;
- `pose_vs_at/query_reference_pose_manifest.json`.

Main outputs:
- `pose_vs_at/figures/*.png`;
- `pose_vs_at/figures/README.md`;
- `pose_vs_at/figures/figure_manifest.json`.

Applicable task constraints:
- this script visualizes offline evaluation only and must not modify the
  runtime pose outputs;
- layer-2 is a relative `best pose vs ODM/AT reference pose` diagnostic branch;
- highlighted outliers must come from the current input CSV rather than a
  historical experiment assumption.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FIGURE_SPECS = [
    (
        "figure_1_position_error_distribution.png",
        "位置误差分布",
        "展示 horizontal_error_m 和 spatial_error_m 的分布，用于查看整体位置误差水平和异常值。",
    ),
    (
        "figure_2_orientation_error_distribution.png",
        "姿态误差分布",
        "展示 view_dir_angle_error_deg 与 yaw/pitch/roll 误差分布，用于查看整体姿态偏差水平。",
    ),
    (
        "figure_3_per_query_horizontal_error.png",
        "逐 query 水平误差",
        "按 query 展示 horizontal_error_m，并动态高亮当前最大 horizontal error 的 query。",
    ),
    (
        "figure_4_per_query_view_dir_error.png",
        "逐 query 视线方向误差",
        "按 query 展示 view_dir_angle_error_deg，并高亮同一异常 query 以便对照。",
    ),
    (
        "figure_5_per_flight_pose_error.png",
        "分航线 pose 误差对比",
        "按航线展示 horizontal_error_m_mean 和 view_dir_angle_error_deg_mean，用于比较航线差异。",
    ),
    (
        "figure_6_dx_dy_scatter.png",
        "dx/dy 偏移散点图",
        "展示 best pose 相对参考位姿的平面偏移方向，并高亮当前异常 query。",
    ),
    (
        "figure_7_horizontal_vs_viewdir_scatter.png",
        "位置误差与视向误差耦合",
        "展示 horizontal_error_m 与 view_dir_angle_error_deg 是否同步变差。",
    ),
    (
        "figure_8_reference_source_status.png",
        "参考源与状态统计",
        "展示 reference source 和 eval_status 分布，用于审计数据来源与评估完成情况。",
    ),
]

FIGURE_INPUT_TABLES = {
    "figure_1_position_error_distribution.png": ("per_query_pose_vs_at.csv",),
    "figure_2_orientation_error_distribution.png": ("per_query_pose_vs_at.csv",),
    "figure_3_per_query_horizontal_error.png": ("per_query_pose_vs_at.csv",),
    "figure_4_per_query_view_dir_error.png": ("per_query_pose_vs_at.csv",),
    "figure_5_per_flight_pose_error.png": ("per_flight_pose_vs_at.csv",),
    "figure_6_dx_dy_scatter.png": ("per_query_pose_vs_at.csv",),
    "figure_7_horizontal_vs_viewdir_scatter.png": ("per_query_pose_vs_at.csv",),
    "figure_8_reference_source_status.png": (
        "per_query_pose_vs_at.csv",
        "query_reference_pose_manifest.json",
    ),
}

HIGHLIGHT_COLOR = "#d95f02"
DEFAULT_COLOR = "#4c78a8"
SECONDARY_COLOR = "#2f4b7c"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pose-root",
        default="new2output/pose_v1_formal/eval_pose_validation_suite/pose_vs_at",
        help="Layer-2 pose_vs_at output root.",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Figure output root. Defaults to <pose-root>/figures.",
    )
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def to_float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    return float(value) if value != "" else float("nan")


def safe_short_flight(flight_id: str) -> str:
    parts = flight_id.split("_")
    return parts[2] if len(parts) >= 3 else flight_id


def metric_payload(overall: dict[str, Any], key: str) -> dict[str, float]:
    payload = overall.get(key, {})
    return payload if isinstance(payload, dict) else {}


def fmt(value: float | None, digits: int = 4) -> str:
    if value is None or not math.isfinite(value):
        return "-"
    return f"{value:.{digits}f}"


def maybe_import_pandas():
    try:
        import pandas as pd  # type: ignore

        return pd
    except Exception:
        return None


def prepare_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore

    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "savefig.dpi": 180,
            "font.size": 10,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    return plt


def choose_highlight_row(ok_rows: list[dict[str, str]]) -> dict[str, str] | None:
    if not ok_rows:
        return None
    return max(ok_rows, key=lambda row: to_float(row, "horizontal_error_m"))


def annotate_highlight(ax, x: float, y: float, text: str) -> None:
    ax.annotate(
        text,
        xy=(x, y),
        xytext=(8, 8),
        textcoords="offset points",
        arrowprops={"arrowstyle": "->", "lw": 0.8, "color": HIGHLIGHT_COLOR},
        color=HIGHLIGHT_COLOR,
        fontsize=9,
        fontweight="bold",
    )


def highlight_color(row: dict[str, str], highlight_query_id: str | None) -> str:
    return HIGHLIGHT_COLOR if row["query_id"] == highlight_query_id else DEFAULT_COLOR


def save_position_distribution(plt, ok_rows: list[dict[str, str]], out_path: Path, highlight_query_id: str | None) -> None:
    values = [
        [to_float(row, "horizontal_error_m") for row in ok_rows],
        [to_float(row, "spatial_error_m") for row in ok_rows],
    ]
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    box = ax.boxplot(
        values,
        tick_labels=["horizontal_error_m", "spatial_error_m"],
        patch_artist=True,
        showfliers=False,
    )
    for patch, color in zip(box["boxes"], [DEFAULT_COLOR, "#f58518"]):
        patch.set_facecolor(color)
        patch.set_alpha(0.35)
    for idx, metric_values in enumerate(values, start=1):
        jitter = [idx + (i % 7 - 3) * 0.012 for i in range(len(metric_values))]
        colors = [HIGHLIGHT_COLOR if ok_rows[i]["query_id"] == highlight_query_id else SECONDARY_COLOR for i in range(len(metric_values))]
        ax.scatter(jitter, metric_values, s=22, c=colors, alpha=0.8, zorder=3)
    ax.set_title("Position Error Distribution")
    ax.set_ylabel("Error (m)")
    ax.set_yscale("symlog", linthresh=10)
    if highlight_query_id:
        ax.text(0.02, 0.95, f"Highlighted query: {highlight_query_id}", transform=ax.transAxes, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def save_orientation_distribution(plt, ok_rows: list[dict[str, str]], out_path: Path, highlight_query_id: str | None) -> None:
    keys = ["view_dir_angle_error_deg", "yaw_error_deg", "pitch_error_deg", "roll_error_deg"]
    values = [[to_float(row, key) for row in ok_rows] for key in keys]
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    box = ax.boxplot(values, tick_labels=keys, patch_artist=True, showfliers=False)
    colors = ["#54a24b", "#e45756", "#72b7b2", "#b279a2"]
    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.35)
    for idx, metric_values in enumerate(values, start=1):
        jitter = [idx + (i % 7 - 3) * 0.012 for i in range(len(metric_values))]
        point_colors = [HIGHLIGHT_COLOR if ok_rows[i]["query_id"] == highlight_query_id else SECONDARY_COLOR for i in range(len(metric_values))]
        ax.scatter(jitter, metric_values, s=22, c=point_colors, alpha=0.8, zorder=3)
    ax.set_title("Orientation Error Distribution")
    ax.set_ylabel("Error (deg)")
    ax.tick_params(axis="x", rotation=15)
    ax.set_yscale("symlog", linthresh=2)
    if highlight_query_id:
        ax.text(0.02, 0.95, f"Highlighted query: {highlight_query_id}", transform=ax.transAxes, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def save_per_query_bar(
    plt,
    ok_rows: list[dict[str, str]],
    key: str,
    title: str,
    ylabel: str,
    out_path: Path,
    highlight_query_id: str | None,
) -> None:
    rows = sorted(ok_rows, key=lambda row: row["query_id"])
    xs = list(range(len(rows)))
    values = [to_float(row, key) for row in rows]
    colors = [highlight_color(row, highlight_query_id) for row in rows]
    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.bar(xs, values, color=colors, width=0.82)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticks(xs)
    ax.set_xticklabels([row["query_id"] for row in rows], rotation=90)
    highlight_idx = next((idx for idx, row in enumerate(rows) if row["query_id"] == highlight_query_id), None)
    if highlight_idx is not None:
        annotate_highlight(ax, float(highlight_idx), values[highlight_idx], str(highlight_query_id))
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def save_per_flight(plt, rows: list[dict[str, str]], out_path: Path) -> None:
    labels = [safe_short_flight(row["flight_id"]) for row in rows]
    horizontal = [to_float(row, "horizontal_error_m_mean") for row in rows]
    view = [to_float(row, "view_dir_angle_error_deg_mean") for row in rows]
    xs = list(range(len(rows)))
    fig, ax1 = plt.subplots(figsize=(8.5, 4.8))
    ax1.bar([x - 0.18 for x in xs], horizontal, width=0.36, color=DEFAULT_COLOR, label="horizontal_error_m_mean")
    ax1.set_ylabel("Horizontal error mean (m)")
    ax2 = ax1.twinx()
    ax2.bar([x + 0.18 for x in xs], view, width=0.36, color="#f58518", alpha=0.85, label="view_dir_angle_error_deg_mean")
    ax2.set_ylabel("View-dir angle error mean (deg)")
    ax1.set_title("Per-flight Pose Error")
    ax1.set_xticks(xs)
    ax1.set_xticklabels(labels)
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def save_dx_dy_scatter(plt, ok_rows: list[dict[str, str]], out_path: Path, highlight_query_id: str | None) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 6.2))
    for row in ok_rows:
        color = highlight_color(row, highlight_query_id)
        size = 90 if row["query_id"] == highlight_query_id else 36
        x = to_float(row, "dx_m")
        y = to_float(row, "dy_m")
        ax.scatter(x, y, c=color, s=size, alpha=0.85)
        if row["query_id"] == highlight_query_id:
            annotate_highlight(ax, x, y, str(highlight_query_id))
    ax.axhline(0, color="#666666", lw=0.8)
    ax.axvline(0, color="#666666", lw=0.8)
    ax.set_title("Camera Center Offset: dx vs dy")
    ax.set_xlabel("dx_m (best - reference)")
    ax.set_ylabel("dy_m (best - reference)")
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def save_horizontal_vs_viewdir(plt, ok_rows: list[dict[str, str]], out_path: Path, highlight_query_id: str | None) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 5.2))
    for row in ok_rows:
        color = highlight_color(row, highlight_query_id)
        size = 90 if row["query_id"] == highlight_query_id else 40
        x = to_float(row, "horizontal_error_m")
        y = to_float(row, "view_dir_angle_error_deg")
        ax.scatter(x, y, c=color, s=size, alpha=0.85)
        if row["query_id"] == highlight_query_id:
            annotate_highlight(ax, x, y, str(highlight_query_id))
    ax.set_title("Horizontal Error vs View Direction Error")
    ax.set_xlabel("horizontal_error_m")
    ax.set_ylabel("view_dir_angle_error_deg")
    ax.set_xscale("symlog", linthresh=10)
    ax.set_yscale("symlog", linthresh=2)
    ax.text(0.02, 0.95, "Both axes use symlog scale.", transform=ax.transAxes, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def save_reference_status(plt, ok_rows: list[dict[str, str]], reference_manifest: dict[str, Any], out_path: Path) -> None:
    eval_counts = Counter(row["eval_status"] for row in ok_rows)
    source_counts = reference_manifest.get("reference_source_type_counts", {})
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.4))
    axes[0].bar(list(source_counts.keys()), list(source_counts.values()), color="#54a24b")
    axes[0].set_title("Reference Source")
    axes[0].set_ylabel("Count")
    axes[0].tick_params(axis="x", rotation=20)
    axes[1].bar(list(eval_counts.keys()), list(eval_counts.values()), color=DEFAULT_COLOR)
    axes[1].set_title("Evaluation Status")
    axes[1].set_ylabel("Count")
    for ax in axes:
        for patch in ax.patches:
            ax.text(
                patch.get_x() + patch.get_width() / 2,
                patch.get_height(),
                str(int(patch.get_height())),
                ha="center",
                va="bottom",
                fontsize=10,
            )
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def build_readme(
    out_root: Path,
    overall: dict[str, Any],
    reference_manifest: dict[str, Any],
    ok_rows: list[dict[str, str]],
    highlight_row: dict[str, str] | None,
) -> str:
    h = metric_payload(overall, "horizontal_error_m")
    v = metric_payload(overall, "view_dir_angle_error_deg")
    highlight_text = ""
    if highlight_row:
        highlight_text = (
            f"- 当前动态高亮 query 为 `{highlight_row['query_id']}`："
            f"`horizontal_error_m={float(highlight_row['horizontal_error_m']):.4f} m`，"
            f"`view_dir_angle_error_deg={float(highlight_row['view_dir_angle_error_deg']):.4f} deg`。"
        )
    lines = [
        "# Pose-vs-AT 图表说明",
        "",
        "这些图来自 `pose_vs_at` 结果，是对 `best pose vs ODM/AT reference pose` 的离线诊断可视化。",
        "图中的高亮点不再写死为历史 query，而是根据当前 `per_query_pose_vs_at.csv` 自动选择 `horizontal_error_m` 最大的 query。",
        "",
        "## 当前统计",
        f"- `query_count={overall.get('query_count')}`，`evaluated_query_count={overall.get('evaluated_query_count')}`。",
        f"- `horizontal_error_m`: mean={fmt(h.get('mean'))} m, median={fmt(h.get('median'))} m, p90={fmt(h.get('p90'))} m。",
        f"- `view_dir_angle_error_deg`: mean={fmt(v.get('mean'))} deg, median={fmt(v.get('median'))} deg, p90={fmt(v.get('p90'))} deg。",
        f"- `reference_source_type_counts={reference_manifest.get('reference_source_type_counts', {})}`。",
    ]
    if highlight_text:
        lines.append(highlight_text)
    lines.extend(
        [
            "",
            "## 图表说明",
            "- `figure_1_position_error_distribution.png`：位置误差分布图，使用 symlog 纵轴以同时显示主体样本和高误差样本。",
            "- `figure_2_orientation_error_distribution.png`：姿态误差分布图。",
            "- `figure_3_per_query_horizontal_error.png`：逐 query 水平误差柱状图，动态高亮当前最大 horizontal error 的 query。",
            "- `figure_4_per_query_view_dir_error.png`：逐 query 视线方向误差柱状图，高亮同一 query 便于对照。",
            "- `figure_5_per_flight_pose_error.png`：分航线位置与视向误差均值对比图。",
            "- `figure_6_dx_dy_scatter.png`：best pose 相对 reference pose 的 dx/dy 平面偏移散点图。",
            "- `figure_7_horizontal_vs_viewdir_scatter.png`：水平误差与视向误差耦合散点图。",
            "- `figure_8_reference_source_status.png`：reference source 与 eval status 统计图。",
            "",
            "## 输入文件",
            "- `per_query_pose_vs_at.csv`",
            "- `per_flight_pose_vs_at.csv`",
            "- `overall_pose_vs_at.json`",
            "- `query_reference_pose_manifest.json`",
            "",
            f"输出目录：`{out_root}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    pose_root = Path(args.pose_root)
    out_root = Path(args.output_root) if args.output_root else pose_root / "figures"
    out_root.mkdir(parents=True, exist_ok=True)

    per_query = load_csv(pose_root / "per_query_pose_vs_at.csv")
    per_flight = load_csv(pose_root / "per_flight_pose_vs_at.csv")
    overall = load_json(pose_root / "overall_pose_vs_at.json")
    reference_manifest = load_json(pose_root / "query_reference_pose_manifest.json")
    ok_rows = [row for row in per_query if row.get("eval_status") == "ok"]
    highlight_row = choose_highlight_row(ok_rows)
    highlight_query_id = highlight_row["query_id"] if highlight_row else None

    _pd = maybe_import_pandas()
    plt = prepare_matplotlib()

    output_paths = {filename: out_root / filename for filename, _title, _desc in FIGURE_SPECS}
    save_position_distribution(plt, ok_rows, output_paths["figure_1_position_error_distribution.png"], highlight_query_id)
    save_orientation_distribution(plt, ok_rows, output_paths["figure_2_orientation_error_distribution.png"], highlight_query_id)
    save_per_query_bar(
        plt,
        ok_rows,
        "horizontal_error_m",
        "Per-query Horizontal Error",
        "horizontal_error_m (m)",
        output_paths["figure_3_per_query_horizontal_error.png"],
        highlight_query_id,
    )
    save_per_query_bar(
        plt,
        ok_rows,
        "view_dir_angle_error_deg",
        "Per-query View Direction Error",
        "view_dir_angle_error_deg",
        output_paths["figure_4_per_query_view_dir_error.png"],
        highlight_query_id,
    )
    save_per_flight(plt, per_flight, output_paths["figure_5_per_flight_pose_error.png"])
    save_dx_dy_scatter(plt, ok_rows, output_paths["figure_6_dx_dy_scatter.png"], highlight_query_id)
    save_horizontal_vs_viewdir(plt, ok_rows, output_paths["figure_7_horizontal_vs_viewdir_scatter.png"], highlight_query_id)
    save_reference_status(plt, ok_rows, reference_manifest, output_paths["figure_8_reference_source_status.png"])

    generated_at = datetime.now(timezone.utc).isoformat()
    figure_payload = {
        "pose_root": str(pose_root),
        "output_root": str(out_root),
        "input_files": {
            "per_query": str(pose_root / "per_query_pose_vs_at.csv"),
            "per_flight": str(pose_root / "per_flight_pose_vs_at.csv"),
            "overall": str(pose_root / "overall_pose_vs_at.json"),
            "reference_manifest": str(pose_root / "query_reference_pose_manifest.json"),
        },
        "pandas_available": _pd is not None,
        "figure_count": len(FIGURE_SPECS),
        "summary": {
            "query_count": len(per_query),
            "evaluated_query_count": len(ok_rows),
            "reference_source_type_counts": reference_manifest.get("reference_source_type_counts", {}),
            "highlight_query_id": highlight_query_id,
            "highlight_horizontal_error_m": float(highlight_row["horizontal_error_m"]) if highlight_row else None,
            "highlight_view_dir_angle_error_deg": float(highlight_row["view_dir_angle_error_deg"]) if highlight_row else None,
        },
        "figures": [
            {
                "filename": filename,
                "title": title,
                "description": description,
                "input_tables": list(FIGURE_INPUT_TABLES.get(filename, ())),
                "path": str(out_root / filename),
                "generated_at_utc": generated_at,
            }
            for filename, title, description in FIGURE_SPECS
        ],
        "generated_at_utc": generated_at,
        "generated_at_unix": time.time(),
    }
    write_json(out_root / "figure_manifest.json", figure_payload)
    write_text(out_root / "README.md", build_readme(out_root, overall, reference_manifest, ok_rows, highlight_row))
    print(out_root)


if __name__ == "__main__":
    main()

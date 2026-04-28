#!/usr/bin/env python3
"""Analyze RoMa v2 benefit boundaries for the current UAV-to-orthophoto task.

Purpose:
- Build a per-query benefit-boundary table from the finalized `query v2 +
  intersection truth` results.
- Generate locked bucket summaries, supplementary tables, figures, and case
  lists under a dedicated `new1output` work directory.

Main inputs:
- RoMa coarse Top-20 retrieval from `romav2_eval_2026-03-30_gpu/coarse`
- RoMa summary assets from `romav2_eval_2026-03-30_gpu`
- Query truth and query metadata from `query_reselect_2026-03-26_v2`

Main outputs:
- `tables/per_query_boundary_analysis.csv` and related summary tables
- `figures/*.png`
- `cases/representative_cases.csv` and `cases/cd_failure_labels.csv`
- `logs/analysis_log.json`

Task constraints:
- Query is a single arbitrary UAV image without geographic metadata during
  retrieval and is not guaranteed to be orthophoto.
- The main analysis must use only the RoMa pipeline coarse Top-20 file as the
  coarse source of truth; independent baseline retrieval is excluded from main
  bucket logic.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        default="new1output/query_reselect_2026-03-26_v2",
        help="Source result directory for query v2 + intersection truth.",
    )
    parser.add_argument(
        "--output-dir",
        default="new1output/benefit_boundary_analysis_2026-03-31",
        help="Output directory for benefit boundary analysis assets.",
    )
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    ensure_dir(path.parent)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def float_or_none(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def int_or_none(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def bool_from_rank(rank: int | None, target: int) -> int:
    return int(rank is not None and rank <= target)


def safe_mean(values: Iterable[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return statistics.fmean(clean)


def safe_median(values: Iterable[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return float(statistics.median(clean))


def format_num(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "NA"
    return f"{value:.{digits}f}"


def bucket_order() -> list[str]:
    return ["A", "B", "C", "D"]


def choose_main_bucket(coarse_top1_hit: int, coarse_top20_hit: int, romav2_top1_hit: int) -> str:
    if coarse_top1_hit == 1 and romav2_top1_hit == 1:
        return "A"
    if coarse_top1_hit == 0 and coarse_top20_hit == 1 and romav2_top1_hit == 1:
        return "B"
    if coarse_top20_hit == 1 and romav2_top1_hit == 0:
        return "C"
    return "D"


def slug_flight(flight_id: str) -> str:
    parts = flight_id.split("_")
    return parts[2] if len(parts) >= 3 else flight_id


def detect_d_label(row: dict[str, object]) -> tuple[str, str]:
    truth_count = int(row["truth_count_total"])
    footprint_area = float(row["footprint_area_m2"])
    pitch_group = str(row["pitch_group"])
    if truth_count <= 180 or footprint_area <= 1_050_000:
        return ("truth_sparse_limited", "Low truth-count or small footprint suggests sparse retrievable support.")
    if pitch_group == "tilted":
        return ("representation_failure", "Truth is not sparse, but tilted view still misses coarse Top-20.")
    return ("representation_failure", "Truth is not sparse, so coarse recall miss is more consistent with representation failure.")


def detect_c_hint(row: dict[str, object]) -> tuple[str, str]:
    c_variant = str(row["c_variant"])
    inlier_count = int(row["romav2_top1_inlier_count"] or 0)
    inlier_ratio = float(row["romav2_top1_inlier_ratio"] or 0.0)
    truth_count = int(row["truth_count_total"])
    pitch_group = str(row["pitch_group"])
    if c_variant == "C_drop_out":
        return ("hard_negative_dominance", "Truth drops out after rerank, suggesting aggressive promotion of hard negatives.")
    if pitch_group == "tilted":
        return ("large_viewpoint_gap", "Tilted query remains unresolved after rerank.")
    if truth_count <= 180:
        return ("limited_overlap", "Truth exists in coarse Top-20 but support is relatively sparse.")
    if inlier_count < 60 or inlier_ratio < 0.02:
        return ("appearance_gap_ortho_vs_oblique", "Weak geometry support despite truth recall suggests ortho-oblique appearance gap.")
    return ("hard_negative_dominance", "Truth is retained but not promoted, consistent with unresolved hard negatives.")


def build_representative_cases(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["main_bucket"])].append(row)

    selected: list[dict[str, object]] = []

    def pick(bucket: str, count: int, key_fn) -> None:
        seen_flights: set[str] = set()
        candidates = sorted(grouped.get(bucket, []), key=key_fn)
        for row in candidates:
            flight_id = str(row["flight_id"])
            if flight_id in seen_flights and len(seen_flights) < len({str(r["flight_id"]) for r in candidates}):
                continue
            selected.append(row)
            seen_flights.add(flight_id)
            if sum(1 for item in selected if item["main_bucket"] == bucket) >= count:
                break
        if sum(1 for item in selected if item["main_bucket"] == bucket) >= count:
            return
        for row in candidates:
            if row in selected:
                continue
            selected.append(row)
            if sum(1 for item in selected if item["main_bucket"] == bucket) >= count:
                break

    pick("A", 2, lambda r: (0 if int(r["a_shrink"]) == 1 else 1, float(r["delta_top1_error_m"] or 0.0)))
    pick("B", 4, lambda r: (-int(r["b_core"]), -int(r["b_strong_rank"]), -(int(r["rank_gain"]) if r["rank_gain"] != "" else -999), float(r["delta_top1_error_m"] or 0.0)))

    c_candidates = grouped.get("C", [])
    c_selected = 0
    for variant in ["C_drop_out", "C_retained"]:
        variant_rows = [row for row in c_candidates if row["c_variant"] == variant]
        if not variant_rows:
            continue
        variant_rows = sorted(
            variant_rows,
            key=lambda r: (
                0 if int(r["c_near_miss"]) == 1 else 1,
                int(r["romav2_first_truth_rank"] or 999),
                float(r["delta_top1_error_m"] or 0.0),
            ),
        )
        selected.append(variant_rows[0])
        c_selected += 1
        if c_selected >= 3:
            break
    if c_selected < 3:
        remaining = [row for row in sorted(c_candidates, key=lambda r: (int(r["romav2_first_truth_rank"] or 999), float(r["delta_top1_error_m"] or 0.0))) if row not in selected]
        for row in remaining:
            selected.append(row)
            c_selected += 1
            if c_selected >= 3:
                break

    d_candidates = grouped.get("D", [])
    d_selected = 0
    for variant in ["truth_sparse_limited", "representation_failure"]:
        variant_rows = [row for row in d_candidates if row["d_variant"] == variant]
        if not variant_rows:
            continue
        selected.append(sorted(variant_rows, key=lambda r: (int(r["truth_count_total"]), float(r["footprint_area_m2"])))[0])
        d_selected += 1
    if d_selected < 2:
        remaining = [row for row in sorted(d_candidates, key=lambda r: (int(r["truth_count_total"]), float(r["footprint_area_m2"]))) if row not in selected]
        for row in remaining:
            selected.append(row)
            d_selected += 1
            if d_selected >= 2:
                break

    out_rows: list[dict[str, object]] = []
    for row in selected:
        out_rows.append(
            {
                "query_id": row["query_id"],
                "flight_id": row["flight_id"],
                "main_bucket": row["main_bucket"],
                "pitch_group": row["pitch_group"],
                "tags": row["tags"],
                "coarse_first_truth_rank": row["coarse_first_truth_rank"],
                "romav2_first_truth_rank": row["romav2_first_truth_rank"],
                "coarse_top1_error_m": row["coarse_top1_error_m"],
                "romav2_top1_error_m": row["romav2_top1_error_m"],
                "delta_top1_error_m": row["delta_top1_error_m"],
                "rank_gain": row["rank_gain"],
                "c_variant": row["c_variant"],
                "d_variant": row["d_variant"],
                "selection_reason": (
                    "A_shrink exemplar" if row["main_bucket"] == "A" and int(row["a_shrink"]) == 1 else
                    "B gain exemplar" if row["main_bucket"] == "B" else
                    "C failure boundary exemplar" if row["main_bucket"] == "C" else
                    "D coarse-limit exemplar"
                ),
            }
        )
    return out_rows


def save_bar_chart(labels: list[str], values: list[float], out_path: Path, title: str, ylabel: str, color: str = "#4C72B0") -> None:
    ensure_dir(out_path.parent)
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    bars = ax.bar(labels, values, color=color)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ymax = max(values) * 1.2 if values else 1.0
    ax.set_ylim(0, ymax if ymax > 0 else 1.0)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.03, f"{value:.0f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def save_stacked_bucket_by_flight(rows: list[dict[str, object]], out_path: Path) -> None:
    ensure_dir(out_path.parent)
    flights = sorted({str(row["flight_short"]) for row in rows})
    buckets = bucket_order()
    counts = {bucket: [0] * len(flights) for bucket in buckets}
    for row in rows:
        counts[str(row["main_bucket"])][flights.index(str(row["flight_short"]))] += 1
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    bottom = [0] * len(flights)
    colors = {"A": "#4C72B0", "B": "#55A868", "C": "#C44E52", "D": "#8172B2"}
    for bucket in buckets:
        ax.bar(flights, counts[bucket], bottom=bottom, label=bucket, color=colors[bucket])
        bottom = [bottom[i] + counts[bucket][i] for i in range(len(flights))]
    ax.set_title("Bucket Distribution by Flight")
    ax.set_ylabel("Query Count")
    ax.legend(title="Bucket")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def save_rank_scatter(rows: list[dict[str, object]], out_path: Path) -> None:
    ensure_dir(out_path.parent)
    colors = {"A": "#4C72B0", "B": "#55A868", "C": "#C44E52"}
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    plotted = [row for row in rows if row["coarse_first_truth_rank"] != "" and row["romav2_first_truth_rank"] != ""]
    for bucket in ["A", "B", "C"]:
        subset = [row for row in plotted if row["main_bucket"] == bucket]
        if not subset:
            continue
        ax.scatter(
            [int(row["coarse_first_truth_rank"]) for row in subset],
            [int(row["romav2_first_truth_rank"]) for row in subset],
            label=bucket,
            color=colors[bucket],
            s=45,
            alpha=0.8,
        )
    max_rank = max(
        max(int(row["coarse_first_truth_rank"]) for row in plotted),
        max(int(row["romav2_first_truth_rank"]) for row in plotted),
    ) if plotted else 20
    ax.plot([0, max_rank + 1], [0, max_rank + 1], linestyle="--", color="#666666", linewidth=1)
    ax.set_xlim(0.5, max_rank + 0.5)
    ax.set_ylim(0.5, max_rank + 0.5)
    ax.invert_xaxis()
    ax.invert_yaxis()
    ax.set_xlabel("Coarse First Truth Rank")
    ax.set_ylabel("RoMa v2 First Truth Rank")
    d_count = sum(1 for row in rows if row["main_bucket"] == "D")
    ax.set_title(f"Rank Change Scatter (D omitted: {d_count})")
    ax.legend(title="Bucket")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def save_boxplot(groups: dict[str, list[float]], out_path: Path, title: str, ylabel: str) -> None:
    ensure_dir(out_path.parent)
    labels = [label for label in bucket_order() if groups.get(label)]
    data = [groups[label] for label in labels]
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.boxplot(data, tick_labels=labels, patch_artist=True)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def save_pitch_distribution(rows: list[dict[str, object]], out_path: Path) -> None:
    ensure_dir(out_path.parent)
    buckets = ["B", "C", "D"]
    pitch_groups = sorted({str(row["pitch_group"]) for row in rows})
    width = 0.22
    x = list(range(len(pitch_groups)))
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    colors = {"B": "#55A868", "C": "#C44E52", "D": "#8172B2"}
    for idx, bucket in enumerate(buckets):
        vals = []
        for pitch_group in pitch_groups:
            vals.append(sum(1 for row in rows if row["main_bucket"] == bucket and row["pitch_group"] == pitch_group))
        ax.bar([pos + width * (idx - 1) for pos in x], vals, width=width, label=bucket, color=colors[bucket])
    ax.set_xticks(x, pitch_groups)
    ax.set_ylabel("Query Count")
    ax.set_title("Pitch Group Distribution for B/C/D Buckets")
    ax.legend(title="Bucket")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def save_truthcount_footprint_distribution(rows: list[dict[str, object]], out_path: Path) -> None:
    ensure_dir(out_path.parent)
    buckets = ["B", "C", "D"]
    colors = {"B": "#55A868", "C": "#C44E52", "D": "#8172B2"}
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    for bucket in buckets:
        subset = [row for row in rows if row["main_bucket"] == bucket]
        if not subset:
            continue
        ax.scatter(
            [float(row["truth_count_total"]) for row in subset],
            [float(row["footprint_area_m2"]) for row in subset],
            label=bucket,
            color=colors[bucket],
            s=50,
            alpha=0.8,
        )
    ax.set_xlabel("Truth Count Total")
    ax.set_ylabel("Footprint Area (m^2)")
    ax.set_title("Truth Count vs Footprint Area")
    ax.legend(title="Bucket")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def save_b_rank_gain_distribution(rows: list[dict[str, object]], out_path: Path) -> None:
    ensure_dir(out_path.parent)
    gains = [int(row["rank_gain"]) for row in rows if row["main_bucket"] == "B" and row["rank_gain"] != ""]
    if not gains:
        gains = [0]
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.hist(gains, bins=min(max(len(set(gains)), 1), 10), color="#55A868", edgecolor="white")
    ax.set_xlabel("Rank Gain")
    ax.set_ylabel("Count")
    ax.set_title("B Bucket Rank Gain Distribution")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    source_dir = Path(args.source_dir)
    out_dir = Path(args.output_dir)
    tables_dir = out_dir / "tables"
    figures_dir = out_dir / "figures"
    cases_dir = out_dir / "cases"
    logs_dir = out_dir / "logs"
    review_dir = out_dir / "review"
    reports_dir = out_dir / "reports"
    for path in [tables_dir, figures_dir, cases_dir, logs_dir, review_dir, reports_dir, out_dir / "plan"]:
        ensure_dir(path)

    coarse_summary = load_json(source_dir / "romav2_eval_2026-03-30_gpu" / "coarse" / "summary_top20.json")
    roma_per_query: dict[str, dict] = {}
    stage7_dir = source_dir / "romav2_eval_2026-03-30_gpu" / "stage7"
    geom_top1_map: dict[str, dict[str, str]] = {}
    for flight_dir in sorted(stage7_dir.iterdir()):
        if not flight_dir.is_dir():
            continue
        rerank_summary = load_json(flight_dir / "rerank_top20.json")
        for row in rerank_summary["per_query"]:
            roma_per_query[row["query_id"]] = row
        geom_rows = load_csv(flight_dir / "per_query_geom_metrics.csv")
        top1_by_query: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in geom_rows:
            top1_by_query[row["query_id"]].append(row)
        for query_id, rows in top1_by_query.items():
            rows.sort(key=lambda row: int(row["raw_rank"]))
            geom_top1_map[query_id] = rows[0]

    coarse_per_query = {row["query_id"]: row for row in coarse_summary["per_query"]}
    comparison_rows = {row["query_id"]: row for row in load_csv(source_dir / "romav2_eval_2026-03-30_gpu" / "per_query_comparison.csv")}
    truth_rows = {row["query_id"]: row for row in load_csv(source_dir / "query_truth" / "query_truth.csv")}
    seed_rows = {row["query_id"]: row for row in load_csv(source_dir / "query_truth" / "queries_truth_seed.csv")}
    selected_rows = load_csv(source_dir / "selected_queries" / "selected_images_summary.csv")
    selected_by_key = {(row["flight_id"], row["image_name"]): row for row in selected_rows}

    per_query_rows: list[dict[str, object]] = []
    for query_id in sorted(truth_rows.keys()):
        truth = truth_rows[query_id]
        _seed = seed_rows[query_id]
        coarse = coarse_per_query[query_id]
        roma = roma_per_query[query_id]
        comp = comparison_rows[query_id]
        selected = selected_by_key[(truth["flight_id"], truth["image_name"])]

        coarse_rank = int_or_none(str(comp["coarse_first_truth_rank"]))
        roma_rank = int_or_none(str(comp["romav2_first_truth_rank"]))
        coarse_top1_hit = bool_from_rank(coarse_rank, 1)
        coarse_top20_hit = bool_from_rank(coarse_rank, 20)
        romav2_top1_hit = bool_from_rank(roma_rank, 1)
        romav2_top20_hit = bool_from_rank(roma_rank, 20)
        main_bucket = choose_main_bucket(coarse_top1_hit, coarse_top20_hit, romav2_top1_hit)
        rank_gain = coarse_rank - roma_rank if coarse_rank is not None and roma_rank is not None else None
        coarse_top1_error_m = float(coarse["top1_error_m"])
        romav2_top1_error_m = float(roma["top1_error_m"])
        delta_top1_error_m = romav2_top1_error_m - coarse_top1_error_m

        c_variant = ""
        c_near_miss = 0
        if main_bucket == "C":
            c_variant = "C_retained" if romav2_top20_hit == 1 else "C_drop_out"
            c_near_miss = int(c_variant == "C_retained" and roma_rank is not None and roma_rank <= 3)

        d_variant = ""
        if main_bucket == "D":
            d_variant, _ = detect_d_label(
                {
                    "truth_count_total": truth["truth_count_total"],
                    "footprint_area_m2": truth["footprint_area_m2"],
                    "pitch_group": selected["pitch_group"],
                }
            )

        geom_top1 = geom_top1_map.get(query_id, {})
        row = {
            "query_id": query_id,
            "flight_id": truth["flight_id"],
            "flight_short": slug_flight(truth["flight_id"]),
            "image_name": truth["image_name"],
            "query_image_path": truth["query_image_path"],
            "pitch_group": selected["pitch_group"],
            "tags": selected["tags"],
            "gimbal_pitch_degree": selected["gimbal_pitch_degree"],
            "gimbal_yaw_degree": selected["gimbal_yaw_degree"],
            "flight_pitch_degree": selected["flight_pitch_degree"],
            "coarse_first_truth_rank": "" if coarse_rank is None else coarse_rank,
            "coarse_top1_hit": coarse_top1_hit,
            "coarse_top20_hit": coarse_top20_hit,
            "romav2_first_truth_rank": "" if roma_rank is None else roma_rank,
            "romav2_top1_hit": romav2_top1_hit,
            "romav2_top20_hit": romav2_top20_hit,
            "coarse_top1_error_m": round(coarse_top1_error_m, 6),
            "romav2_top1_error_m": round(romav2_top1_error_m, 6),
            "delta_top1_error_m": round(delta_top1_error_m, 6),
            "rank_gain": "" if rank_gain is None else rank_gain,
            "promoted_to_top1": int(coarse_top1_hit == 0 and coarse_top20_hit == 1 and romav2_top1_hit == 1),
            "promoted_within_top20": int(rank_gain is not None and rank_gain > 0),
            "main_bucket": main_bucket,
            "c_variant": c_variant,
            "c_near_miss": c_near_miss,
            "d_variant": d_variant,
            "a_shrink": int(main_bucket == "A" and delta_top1_error_m <= -100.0),
            "b_core": int(main_bucket == "B" and rank_gain is not None and rank_gain >= 3),
            "b_strong_rank": int(main_bucket == "B" and rank_gain is not None and rank_gain >= 5),
            "b_strong_error": int(main_bucket == "B" and delta_top1_error_m <= -200.0),
            "footprint_area_m2": round(float(truth["footprint_area_m2"]), 3),
            "truth_count_total": int(truth["truth_count_total"]),
            "truth_count_200m": int(truth["truth_count_200m"]),
            "truth_count_300m": int(truth["truth_count_300m"]),
            "truth_count_500m": int(truth["truth_count_500m"]),
            "truth_count_700m": int(truth["truth_count_700m"]),
            "query_x": round(float(truth["query_x"]), 3),
            "query_y": round(float(truth["query_y"]), 3),
            "coarse_truth_count": int(coarse["truth_count"]),
            "romav2_truth_count": int(roma["truth_count"]),
            "romav2_top1_raw_rank": int_or_none(geom_top1.get("raw_rank")),
            "romav2_top1_global_score": float_or_none(geom_top1.get("global_score")),
            "romav2_top1_match_score": float_or_none(geom_top1.get("romav2_match_score")),
            "romav2_top1_inlier_count": int_or_none(geom_top1.get("inlier_count")),
            "romav2_top1_inlier_ratio": float_or_none(geom_top1.get("inlier_ratio")),
            "romav2_top1_reproj_error_mean": float_or_none(geom_top1.get("reproj_error_mean")),
            "romav2_top1_geom_valid": int_or_none(geom_top1.get("geom_valid")),
            "romav2_top1_geom_quality": float_or_none(geom_top1.get("geom_quality")),
            "romav2_top1_fused_score": float_or_none(geom_top1.get("fused_score")),
            "selection_reason": selected["selection_reason"],
        }
        per_query_rows.append(row)

    write_csv(tables_dir / "per_query_boundary_analysis.csv", per_query_rows, list(per_query_rows[0].keys()))

    bucket_counts = Counter(str(row["main_bucket"]) for row in per_query_rows)
    bucket_summary_rows = []
    for bucket in bucket_order():
        count = bucket_counts.get(bucket, 0)
        bucket_summary_rows.append({"main_bucket": bucket, "query_count": count, "query_ratio": round(count / len(per_query_rows), 6)})
    write_csv(tables_dir / "bucket_summary.csv", bucket_summary_rows)
    write_csv(tables_dir / "table_1_bucket_counts.csv", bucket_summary_rows)

    flights = sorted({str(row["flight_id"]) for row in per_query_rows})
    table2_rows = []
    for flight in flights:
        subset = [row for row in per_query_rows if row["flight_id"] == flight]
        table2_rows.append(
            {
                "flight_id": flight,
                "flight_short": slug_flight(flight),
                "query_count": len(subset),
                "A_count": sum(1 for row in subset if row["main_bucket"] == "A"),
                "B_count": sum(1 for row in subset if row["main_bucket"] == "B"),
                "C_count": sum(1 for row in subset if row["main_bucket"] == "C"),
                "D_count": sum(1 for row in subset if row["main_bucket"] == "D"),
            }
        )
    write_csv(tables_dir / "table_2_bucket_by_flight.csv", table2_rows)

    table3_rows = []
    for bucket in bucket_order():
        subset = [row for row in per_query_rows if row["main_bucket"] == bucket]
        table3_rows.append(
            {
                "main_bucket": bucket,
                "query_count": len(subset),
                "coarse_first_truth_rank_mean": format_num(safe_mean(int(row["coarse_first_truth_rank"]) if row["coarse_first_truth_rank"] != "" else None for row in subset)),
                "romav2_first_truth_rank_mean": format_num(safe_mean(int(row["romav2_first_truth_rank"]) if row["romav2_first_truth_rank"] != "" else None for row in subset)),
                "delta_top1_error_m_mean": format_num(safe_mean(float(row["delta_top1_error_m"]) for row in subset)),
                "delta_top1_error_m_median": format_num(safe_median(float(row["delta_top1_error_m"]) for row in subset)),
            }
        )
    write_csv(tables_dir / "table_3_rank_error_summary.csv", table3_rows)

    table4_rows = []
    for bucket in ["B", "C", "D"]:
        subset = [row for row in per_query_rows if row["main_bucket"] == bucket]
        table4_rows.append(
            {
                "main_bucket": bucket,
                "query_count": len(subset),
                "footprint_area_mean_m2": format_num(safe_mean(float(row["footprint_area_m2"]) for row in subset)),
                "footprint_area_median_m2": format_num(safe_median(float(row["footprint_area_m2"]) for row in subset)),
                "truth_count_total_mean": format_num(safe_mean(float(row["truth_count_total"]) for row in subset)),
                "truth_count_total_median": format_num(safe_median(float(row["truth_count_total"]) for row in subset)),
                "truth_count_200m_mean": format_num(safe_mean(float(row["truth_count_200m"]) for row in subset)),
                "truth_count_300m_mean": format_num(safe_mean(float(row["truth_count_300m"]) for row in subset)),
                "truth_count_500m_mean": format_num(safe_mean(float(row["truth_count_500m"]) for row in subset)),
                "truth_count_700m_mean": format_num(safe_mean(float(row["truth_count_700m"]) for row in subset)),
            }
        )
    write_csv(tables_dir / "table_4_truth_footprint_summary.csv", table4_rows)

    total_delta_r1_hits = sum(1 for row in per_query_rows if row["romav2_top1_hit"] == 1) - sum(1 for row in per_query_rows if row["coarse_top1_hit"] == 1)
    supp_a_rows = []
    for bucket in bucket_order():
        subset = [row for row in per_query_rows if row["main_bucket"] == bucket]
        direct_new_hits = sum(1 for row in subset if row["coarse_top1_hit"] == 0 and row["romav2_top1_hit"] == 1)
        supp_a_rows.append(
            {
                "main_bucket": bucket,
                "query_count": len(subset),
                "direct_new_top1_hits": direct_new_hits,
                "share_of_total_new_top1_hits": format_num((direct_new_hits / total_delta_r1_hits) if total_delta_r1_hits else None, 6),
                "interpretation": (
                    "Already correct at Top-1; limited direct contribution to R@1 gain." if bucket == "A" else
                    "Main source of new Top-1 hits after reranking." if bucket == "B" else
                    "Coarse recall exists but rerank does not finish correction." if bucket == "C" else
                    "Upper bound is constrained by coarse recall."
                ),
            }
        )
    write_csv(tables_dir / "supp_table_A_r1_contribution.csv", supp_a_rows)

    c_rows = [row for row in per_query_rows if row["main_bucket"] == "C"]
    supp_b_rows = [
        {"c_variant": "C_total", "query_count": len(c_rows), "query_ratio": round(len(c_rows) / len(per_query_rows), 6)},
        {"c_variant": "C_retained", "query_count": sum(1 for row in c_rows if row["c_variant"] == "C_retained"), "query_ratio": round(sum(1 for row in c_rows if row["c_variant"] == "C_retained") / len(per_query_rows), 6)},
        {"c_variant": "C_drop_out", "query_count": sum(1 for row in c_rows if row["c_variant"] == "C_drop_out"), "query_ratio": round(sum(1 for row in c_rows if row["c_variant"] == "C_drop_out") / len(per_query_rows), 6)},
        {"c_variant": "C_near_miss", "query_count": sum(1 for row in c_rows if int(row["c_near_miss"]) == 1), "query_ratio": round(sum(1 for row in c_rows if int(row["c_near_miss"]) == 1) / len(per_query_rows), 6)},
    ]
    write_csv(tables_dir / "supp_table_B_c_bucket_breakdown.csv", supp_b_rows)

    pitch_groups = sorted({str(row["pitch_group"]) for row in per_query_rows})
    supp_c_rows = []
    for pitch_group in pitch_groups:
        subset = [row for row in per_query_rows if row["pitch_group"] == pitch_group]
        total = len(subset)
        supp_c_rows.append(
            {
                "pitch_group": pitch_group,
                "query_count": total,
                "B_count": sum(1 for row in subset if row["main_bucket"] == "B"),
                "B_ratio_within_pitch_group": format_num(sum(1 for row in subset if row["main_bucket"] == "B") / total if total else None, 6),
                "C_count": sum(1 for row in subset if row["main_bucket"] == "C"),
                "C_ratio_within_pitch_group": format_num(sum(1 for row in subset if row["main_bucket"] == "C") / total if total else None, 6),
                "D_count": sum(1 for row in subset if row["main_bucket"] == "D"),
                "D_ratio_within_pitch_group": format_num(sum(1 for row in subset if row["main_bucket"] == "D") / total if total else None, 6),
            }
        )
    write_csv(tables_dir / "supp_table_C_pitch_group_bucket_ratio.csv", supp_c_rows)

    save_bar_chart([row["main_bucket"] for row in bucket_summary_rows], [row["query_count"] for row in bucket_summary_rows], figures_dir / "figure_1_bucket_counts.png", "Main Bucket Counts", "Query Count")
    save_stacked_bucket_by_flight(per_query_rows, figures_dir / "figure_2_bucket_by_flight.png")
    save_rank_scatter(per_query_rows, figures_dir / "figure_3_rank_scatter.png")
    error_groups = {bucket: [float(row["delta_top1_error_m"]) for row in per_query_rows if row["main_bucket"] == bucket] for bucket in bucket_order()}
    save_boxplot(error_groups, figures_dir / "figure_4_top1_error_delta_boxplot.png", "Top-1 Error Delta by Bucket", "Delta Top-1 Error (m)")
    save_pitch_distribution(per_query_rows, figures_dir / "figure_5_pitch_distribution.png")
    save_truthcount_footprint_distribution(per_query_rows, figures_dir / "figure_6_truthcount_footprint_distribution.png")
    save_b_rank_gain_distribution(per_query_rows, figures_dir / "figure_7_b_rank_gain_distribution.png")

    representative_cases = build_representative_cases(per_query_rows)
    write_csv(cases_dir / "representative_cases.csv", representative_cases)

    failure_rows = []
    for row in per_query_rows:
        if row["main_bucket"] not in {"C", "D"}:
            continue
        if row["main_bucket"] == "C":
            auto_label, auto_note = detect_c_hint(row)
        else:
            auto_label, auto_note = detect_d_label(row)
        failure_rows.append(
            {
                "query_id": row["query_id"],
                "flight_id": row["flight_id"],
                "main_bucket": row["main_bucket"],
                "c_variant": row["c_variant"],
                "d_variant": row["d_variant"],
                "pitch_group": row["pitch_group"],
                "tags": row["tags"],
                "truth_count_total": row["truth_count_total"],
                "footprint_area_m2": row["footprint_area_m2"],
                "coarse_first_truth_rank": row["coarse_first_truth_rank"],
                "romav2_first_truth_rank": row["romav2_first_truth_rank"],
                "romav2_top1_inlier_count": row["romav2_top1_inlier_count"],
                "romav2_top1_inlier_ratio": row["romav2_top1_inlier_ratio"],
                "auto_label_hint": auto_label,
                "auto_note": auto_note,
                "manual_label_1": "",
                "manual_label_2": "",
                "manual_note": "",
            }
        )
    write_csv(cases_dir / "cd_failure_labels.csv", failure_rows, fieldnames=[
        "query_id", "flight_id", "main_bucket", "c_variant", "d_variant", "pitch_group", "tags",
        "truth_count_total", "footprint_area_m2", "coarse_first_truth_rank", "romav2_first_truth_rank",
        "romav2_top1_inlier_count", "romav2_top1_inlier_ratio", "auto_label_hint", "auto_note",
        "manual_label_1", "manual_label_2", "manual_note",
    ])

    (review_dir / "review_notes.md").write_text(
        "# Review Notes\n\nPending formal review by agent3.\n\n- Main bucket counts generated.\n- C bucket refinement generated.\n- Failure-label template initialized for C/D queries.\n",
        encoding="utf-8",
    )
    (reports_dir / "benefit_boundary_analysis_report.md").write_text(
        "# RoMa v2 Benefit Boundary Analysis Report\n\nPending formal review and narrative write-up by agent3.\n",
        encoding="utf-8",
    )

    write_json(
        logs_dir / "analysis_log.json",
        {
            "source_dir": str(source_dir),
            "output_dir": str(out_dir),
            "query_count": len(per_query_rows),
            "bucket_counts": dict(bucket_counts),
            "total_delta_top1_hits": total_delta_r1_hits,
            "generated_tables": sorted(path.name for path in tables_dir.iterdir()),
            "generated_figures": sorted(path.name for path in figures_dir.iterdir()),
            "generated_case_files": sorted(path.name for path in cases_dir.iterdir()),
        },
    )


if __name__ == "__main__":
    main()

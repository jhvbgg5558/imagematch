#!/usr/bin/env python3
"""Plot top-k curves using unique candidate tiles ranked by score."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


FLIGHT_COLORS = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval-csv", required=True)
    parser.add_argument("--query-seed-csv", required=True)
    parser.add_argument("--query-truth-tiles-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def first_k_full_truth(sorted_items: list[tuple[str, float]], truth_set: set[str]) -> int | None:
    if not truth_set:
        return 0
    hits = 0
    for idx, (tile_id, _) in enumerate(sorted_items, start=1):
        if tile_id in truth_set:
            hits += 1
            if hits >= len(truth_set):
                return idx
    return None


def build_unique_rankings(
    retrieval_rows: list[dict[str, str]],
    query_to_flight: dict[str, str],
) -> tuple[dict[str, list[tuple[str, float]]], list[tuple[str, float]]]:
    # For each flight, keep one score per tile: max score across all queries in that flight.
    by_flight_scores: dict[str, dict[str, float]] = defaultdict(dict)
    overall_scores: dict[str, float] = {}
    for row in retrieval_rows:
        qid = row["query_id"]
        flight_id = query_to_flight[qid]
        tile_id = row["candidate_tile_id"]
        score = float(row["score"])
        if tile_id not in by_flight_scores[flight_id] or score > by_flight_scores[flight_id][tile_id]:
            by_flight_scores[flight_id][tile_id] = score
        if tile_id not in overall_scores or score > overall_scores[tile_id]:
            overall_scores[tile_id] = score

    by_flight_sorted: dict[str, list[tuple[str, float]]] = {}
    for flight_id, score_map in by_flight_scores.items():
        by_flight_sorted[flight_id] = sorted(score_map.items(), key=lambda x: x[1], reverse=True)
    overall_sorted = sorted(overall_scores.items(), key=lambda x: x[1], reverse=True)
    return by_flight_sorted, overall_sorted


def write_curve_csv(
    out_csv: Path,
    by_flight_ranked: dict[str, list[tuple[str, float]]],
    overall_ranked: list[tuple[str, float]],
    truth_by_flight: dict[str, set[str]],
    overall_truth: set[str],
) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "scope",
                "flight_id",
                "k",
                "cumulative_truth_hits",
                "total_truth_count",
                "cumulative_truth_ratio",
            ]
        )

        for flight_id, ranked in sorted(by_flight_ranked.items()):
            truth_set = truth_by_flight.get(flight_id, set())
            hits = 0
            total = len(truth_set)
            for k, (tile_id, _) in enumerate(ranked, start=1):
                if tile_id in truth_set:
                    hits += 1
                ratio = 0.0 if total == 0 else hits / total
                writer.writerow(["flight", flight_id, k, hits, total, ratio])

        hits = 0
        total = len(overall_truth)
        for k, (tile_id, _) in enumerate(overall_ranked, start=1):
            if tile_id in overall_truth:
                hits += 1
            ratio = 0.0 if total == 0 else hits / total
            writer.writerow(["overall", "ALL", k, hits, total, ratio])


def write_summary_json(
    out_json: Path,
    by_flight_ranked: dict[str, list[tuple[str, float]]],
    overall_ranked: list[tuple[str, float]],
    truth_by_flight: dict[str, set[str]],
    overall_truth: set[str],
) -> dict:
    summary: dict[str, object] = {"overall": {}, "per_flight": {}}
    overall_k = first_k_full_truth(overall_ranked, overall_truth)
    summary["overall"] = {
        "total_truth_unique_tiles": len(overall_truth),
        "candidate_unique_tiles": len(overall_ranked),
        "k_full_truth": overall_k,
        "reached_full_truth": overall_k is not None,
    }
    per_flight: dict[str, object] = {}
    for flight_id, ranked in sorted(by_flight_ranked.items()):
        truth_set = truth_by_flight.get(flight_id, set())
        k_full = first_k_full_truth(ranked, truth_set)
        per_flight[flight_id] = {
            "total_truth_unique_tiles": len(truth_set),
            "candidate_unique_tiles": len(ranked),
            "k_full_truth": k_full,
            "reached_full_truth": k_full is not None,
        }
    summary["per_flight"] = per_flight
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def plot_curve_from_rows(rows: list[dict[str, str]], title: str, out_path: Path) -> None:
    ks = [int(r["k"]) for r in rows]
    vals = [int(r["cumulative_truth_hits"]) for r in rows]
    total = int(rows[0]["total_truth_count"]) if rows else 0
    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    ax.plot(ks, vals, color="#1f77b4", linewidth=2.2)
    ax.set_xlabel("Retrieved Unique Satellite Tile Count (K)")
    ax.set_ylabel("Found Unique Truth Tile Count")
    ax.set_title(title)
    if total > 0:
        ax.axhline(total, color="#2ca02c", linestyle="--", linewidth=1.2, label=f"total truth={total}")
        ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    agg_dir = out_dir / "_aggregate"
    ensure_dir(out_dir)
    ensure_dir(agg_dir)

    seed_rows = load_csv(Path(args.query_seed_csv))
    truth_rows = load_csv(Path(args.query_truth_tiles_csv))
    retrieval_rows = load_csv(Path(args.retrieval_csv))

    query_to_flight = {row["query_id"]: row["flight_id"] for row in seed_rows}
    truth_by_flight: dict[str, set[str]] = defaultdict(set)
    overall_truth: set[str] = set()
    for row in truth_rows:
        if row.get("is_intersection_truth", "1") != "1":
            continue
        qid = row["query_id"]
        flight_id = query_to_flight[qid]
        tile_id = row["tile_id"]
        truth_by_flight[flight_id].add(tile_id)
        overall_truth.add(tile_id)

    by_flight_ranked, overall_ranked = build_unique_rankings(retrieval_rows, query_to_flight)

    curve_csv = out_dir / "topk_unique_truth_curve.csv"
    write_curve_csv(curve_csv, by_flight_ranked, overall_ranked, truth_by_flight, overall_truth)
    summary_json = out_dir / "k_full_truth_unique_tile_summary.json"
    write_summary_json(summary_json, by_flight_ranked, overall_ranked, truth_by_flight, overall_truth)

    curve_rows = load_csv(curve_csv)
    overall_rows = [r for r in curve_rows if r["scope"] == "overall"]
    plot_curve_from_rows(
        overall_rows,
        "Overall Top-K Curve (Unique Truth Tiles)",
        agg_dir / "overall_topk_unique_truth_count_curve.png",
    )

    by_flight_curve_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in curve_rows:
        if row["scope"] == "flight":
            by_flight_curve_rows[row["flight_id"]].append(row)

    for idx, flight_id in enumerate(sorted(by_flight_curve_rows)):
        rows = sorted(by_flight_curve_rows[flight_id], key=lambda r: int(r["k"]))
        flight_dir = out_dir / flight_id
        ensure_dir(flight_dir)
        # override default color for each flight for visual distinction
        ks = [int(r["k"]) for r in rows]
        vals = [int(r["cumulative_truth_hits"]) for r in rows]
        total = int(rows[0]["total_truth_count"]) if rows else 0
        fig, ax = plt.subplots(figsize=(8.8, 5.2))
        ax.plot(ks, vals, color=FLIGHT_COLORS[idx % len(FLIGHT_COLORS)], linewidth=2.2)
        ax.set_xlabel("Retrieved Unique Satellite Tile Count (K)")
        ax.set_ylabel("Found Unique Truth Tile Count")
        ax.set_title(f"{flight_id.split('_')[2]} Top-K Curve (Unique Truth Tiles)")
        if total > 0:
            ax.axhline(total, color="#2ca02c", linestyle="--", linewidth=1.2, label=f"total truth={total}")
            ax.legend()
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(flight_dir / "topk_unique_truth_count_curve.png", dpi=180)
        plt.close(fig)

    print(out_dir)


if __name__ == "__main__":
    main()

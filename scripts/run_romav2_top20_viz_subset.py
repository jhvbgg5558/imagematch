#!/usr/bin/env python3
"""Render a small subset of RoMa v2 Top-20 match-point visualizations.

Purpose:
- sanity-check visualization throughput on a controlled subset before running
  the full bundle-level Top-20 visualization;
- reuse the same matching and drawing logic as the formal visualization script
  without changing the formal rerank outputs.

Main inputs:
- an existing RoMa v2 result directory with `input_round/stage3` and
  `stage7/*/reranked_topK.csv`;
- locked tile CSV and query image sources from the current UAV task.

Main outputs:
- subset PNGs under a caller-provided output directory;
- `summary_top20_match_points.csv` and `summary_top20_match_points.md` for the
  tested subset only.

Applicable task constraints:
- the query is a single arbitrary UAV image;
- the query has no geographic metadata;
- the query is not guaranteed to be orthophoto;
- no external resolution normalization is applied before matching unless it is
  already part of the reused model pipeline.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

from visualize_romav2_top20_match_points import (
    build_model,
    build_summary_md,
    draw_pair,
    draw_placeholder,
    ensure_dir,
    load_csv,
    load_query_rows,
    load_selected_lookup,
    match_pair,
    read_rgb,
    resolve_query_path,
    safe_name,
    short_flight_name,
    write_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--romav2-result-dir", required=True)
    parser.add_argument("--tiles-csv", required=True)
    parser.add_argument("--selected-summary-csv", required=True)
    parser.add_argument("--query-input-root", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--query-id", action="append", required=True)
    parser.add_argument("--max-rank", type=int, default=3)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--setting", default="satast")
    parser.add_argument("--sample-count", type=int, default=5000)
    parser.add_argument("--ransac-reproj-thresh", type=float, default=4.0)
    parser.add_argument("--min-inliers", type=int, default=20)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.01)
    parser.add_argument("--target-long-side", type=int, default=900)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    romav2_result_dir = Path(args.romav2_result_dir)
    out_root = Path(args.out_root)
    figures_dir = out_root / "figures"
    ensure_dir(figures_dir)

    wanted = set(args.query_id)
    tiles = {row["tile_id"]: row for row in load_csv(Path(args.tiles_csv))}
    query_rows = load_query_rows(romav2_result_dir / "input_round" / "stage3")
    selected_lookup = load_selected_lookup(Path(args.selected_summary_csv))
    query_input_root = Path(args.query_input_root)
    model = build_model(args.setting, args.device)
    summary_rows: list[dict[str, object]] = []

    for flight_dir in sorted((romav2_result_dir / "stage7").iterdir()):
        if not flight_dir.is_dir():
            continue
        rerank_csv = flight_dir / "reranked_top20.csv"
        if not rerank_csv.exists():
            continue
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in load_csv(rerank_csv):
            if row["query_id"] in wanted:
                grouped[row["query_id"]].append(row)
        for qid, rows in grouped.items():
            rows.sort(key=lambda row: int(row["rank"]))
            query_row = query_rows[qid]
            query_path = resolve_query_path(query_row, selected_lookup, query_input_root)
            query_output_dir = figures_dir / flight_dir.name / qid
            ensure_dir(query_output_dir)
            for row in rows[: args.max_rank]:
                rank = int(row["rank"])
                tile_id = row["candidate_tile_id"]
                tile_row = tiles[tile_id]
                tile_path = Path(tile_row["image_path"])
                out_path = query_output_dir / f"rank{rank:02d}_{safe_name(tile_id)}.png"
                title = (
                    f"{qid} | {short_flight_name(flight_dir.name)} | rank={rank} | "
                    f"tile={tile_id} | hit={row['is_intersection_truth_hit']}"
                )
                print(f"[{flight_dir.name}] {qid} rank {rank:02d}/{args.max_rank} tile {tile_id}", flush=True)

                status = "ok"
                match_count = 0
                inlier_count = 0
                inlier_ratio = 0.0
                geom_valid = 0
                romav2_match_score = ""
                reproj_error_mean = ""
                try:
                    query_img = read_rgb(query_path)
                    tile_img = read_rgb(tile_path)
                    match_info = match_pair(
                        model=model,
                        query_path=query_path,
                        tile_path=tile_path,
                        sample_count=args.sample_count,
                        ransac_reproj_thresh=args.ransac_reproj_thresh,
                        min_inliers=args.min_inliers,
                        min_inlier_ratio=args.min_inlier_ratio,
                    )
                    match_count = int(match_info["match_count"])
                    inlier_count = int(match_info["inlier_count"])
                    inlier_ratio = float(match_info["inlier_ratio"])
                    geom_valid = int(bool(match_info["geom_valid"]))
                    romav2_match_score = f"{float(match_info['romav2_match_score']):.6f}"
                    reproj_error_mean = (
                        "" if match_info["reproj_error_mean"] is None else f"{float(match_info['reproj_error_mean']):.6f}"
                    )
                    status = str(match_info["status"])
                    title_full = f"{title} | inliers={inlier_count}/{match_count}"
                    if match_count >= 4:
                        draw_pair(
                            query_img=query_img,
                            tile_img=tile_img,
                            query_keypoints=np.asarray(match_info["query_keypoints"]),
                            tile_keypoints=np.asarray(match_info["tile_keypoints"]),
                            inlier_mask=np.asarray(match_info["inlier_mask"]),
                            title=title_full,
                            out_path=out_path,
                            tile_hit=row["is_intersection_truth_hit"] == "1",
                            target_long_side=args.target_long_side,
                        )
                    else:
                        draw_placeholder(
                            title=title_full,
                            reason=status,
                            out_path=out_path,
                            tile_hit=row["is_intersection_truth_hit"] == "1",
                        )
                except Exception as exc:
                    status = f"error:{type(exc).__name__}"
                    draw_placeholder(
                        title=title,
                        reason=status,
                        out_path=out_path,
                        tile_hit=row["is_intersection_truth_hit"] == "1",
                    )

                summary_rows.append(
                    {
                        "flight_id": flight_dir.name,
                        "flight_tag": short_flight_name(flight_dir.name),
                        "query_id": qid,
                        "rank": rank,
                        "candidate_tile_id": tile_id,
                        "is_intersection_truth_hit": int(row["is_intersection_truth_hit"]),
                        "match_count": match_count,
                        "inlier_count": inlier_count,
                        "inlier_ratio": f"{inlier_ratio:.6f}",
                        "geom_valid": geom_valid,
                        "romav2_match_score": romav2_match_score,
                        "reproj_error_mean": reproj_error_mean,
                        "status": status,
                        "query_path": str(query_path),
                        "tile_path": str(tile_path),
                        "output_path": str(out_path),
                    }
                )

    summary_csv = out_root / "summary_top20_match_points.csv"
    write_csv(summary_csv, summary_rows)
    summary_md = out_root / "summary_top20_match_points.md"
    summary_md.write_text(build_summary_md(out_root, summary_csv, summary_rows, args.max_rank), encoding="utf-8")
    print(figures_dir)
    print(summary_csv)
    print(summary_md)


if __name__ == "__main__":
    main()

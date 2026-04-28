#!/usr/bin/env python3
"""Run the UAV orthophoto-truth evaluation pipeline for formal Pose v1.

Purpose:
- orchestrate truth-manifest preparation, truth-crop materialization,
  predicted-orthophoto rendering, metric evaluation, and overlay export;
- support a fixed 5-query gate before expanding to all 40 formal queries;
- keep gate sample selection deterministic and recorded in the output summary.

Main inputs:
- formal pose outputs under `new2output/pose_v1_formal`;
- query truth metadata under `new1output/query_reselect_2026-03-26_v2`;
- local UAV flight orthophotos under `D:\数据\武汉影像\无人机0.1m`.

Main outputs:
- `<output_root>/*`;
- `<output_root>/phase_gate_summary.json` or
  `<output_root>/full_run_summary.json`.

Applicable task constraints:
- truth orthophoto is evaluation-only;
- DOM overlays remain diagnostic-only;
- gate and full runs must reuse the same script interfaces and metric schema.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from pose_ortho_truth_utils import (
    DEFAULT_FORMAL_BUNDLE_ROOT,
    DEFAULT_QUERY_ROOT,
    load_csv,
    load_json,
    resolve_runtime_path,
    resolve_output_root,
    write_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_FORMAL_BUNDLE_ROOT))
    parser.add_argument(
        "--query-seed-csv",
        default=str(DEFAULT_QUERY_ROOT / "query_truth" / "queries_truth_seed.csv"),
    )
    parser.add_argument("--phase", choices=("gate", "full"), default="gate")
    parser.add_argument("--gate-count", type=int, default=5)
    parser.add_argument("--target-resolution-m", type=float, default=0.5)
    parser.add_argument("--crop-margin-m", type=float, default=80.0)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--output-root", default=None)
    return parser.parse_args()


def summarize_by_query_pnp_failures(pnp_rows: list[dict[str, str]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in pnp_rows:
        if row.get("status") == "pnp_failed":
            counts[row["query_id"]] += 1
    return dict(counts)


def choose_gate_queries(
    best_rows: list[dict[str, str]],
    pnp_rows: list[dict[str, str]],
    truth_rows: list[dict[str, str]],
    gate_count: int,
) -> list[str]:
    truth_by_query = {row["query_id"]: row for row in truth_rows}
    best_ok = [row for row in best_rows if row.get("best_status") == "ok" and row["query_id"] in truth_by_query]
    best_ok_sorted = sorted(best_ok, key=lambda row: float(row["best_score"]))
    if len(best_ok_sorted) <= gate_count:
        return [row["query_id"] for row in best_ok_sorted]

    by_flight: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in best_ok_sorted:
        by_flight[row["flight_id"]].append(row)

    pnp_failed_counts = summarize_by_query_pnp_failures(pnp_rows)
    footprint_sorted = sorted(
        best_ok_sorted,
        key=lambda row: float(truth_by_query[row["query_id"]].get("footprint_area_m2", 0.0)),
        reverse=True,
    )

    selected: list[str] = []

    def add_query(query_id: str) -> None:
        if query_id not in selected:
            selected.append(query_id)

    flights = sorted(by_flight)
    if flights:
        add_query(max(by_flight[flights[0]], key=lambda row: float(row["best_score"]))["query_id"])
    if len(flights) >= 2:
        median_rows = sorted(by_flight[flights[1]], key=lambda row: float(row["best_score"]))
        add_query(median_rows[len(median_rows) // 2]["query_id"])
    if len(flights) >= 3:
        add_query(min(by_flight[flights[2]], key=lambda row: float(row["best_score"]))["query_id"])
    if len(flights) >= 4:
        add_query(footprint_sorted[0]["query_id"])

    pnp_failed_sorted = sorted(best_ok_sorted, key=lambda row: pnp_failed_counts.get(row["query_id"], 0), reverse=True)
    if pnp_failed_sorted and pnp_failed_counts.get(pnp_failed_sorted[0]["query_id"], 0) > 0:
        add_query(pnp_failed_sorted[0]["query_id"])

    for row in best_ok_sorted:
        if len(selected) >= gate_count:
            break
        add_query(row["query_id"])

    return selected[:gate_count]


def run_step(step_name: str, command: list[str]) -> dict[str, object]:
    started = time.time()
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return {
        "step_name": step_name,
        "command": command,
        "returncode": completed.returncode,
        "elapsed_sec": time.time() - started,
    }


def step_succeeded(step_results: list[dict[str, object]], step_name: str) -> bool:
    for item in step_results:
        if item["step_name"] == step_name:
            return int(item["returncode"]) == 0
    return False


def build_query_flags(query_ids: list[str]) -> list[str]:
    flags: list[str] = []
    for query_id in query_ids:
        flags.extend(["--query-id", query_id])
    return flags


def load_summary_if_exists(path: Path) -> dict[str, object]:
    if path.exists():
        return load_json(path)
    return {}


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    eval_root = resolve_output_root(bundle_root, args.output_root)
    query_seed_rows = load_csv(resolve_runtime_path(args.query_seed_csv))

    best_pose_csv = bundle_root / "summary" / "per_query_best_pose.csv"
    pnp_results_csv = bundle_root / "pnp" / "pnp_results.csv"
    best_rows = load_csv(resolve_runtime_path(best_pose_csv))
    pnp_rows = load_csv(resolve_runtime_path(pnp_results_csv))

    if args.query_id:
        selected_query_ids = args.query_id
    elif args.phase == "full":
        selected_query_ids = [row["query_id"] for row in best_rows]
    else:
        selected_query_ids = choose_gate_queries(best_rows, pnp_rows, query_seed_rows, args.gate_count)

    query_flags = build_query_flags(selected_query_ids)
    overwrite_flags = ["--overwrite"] if args.overwrite else []

    steps = [
        (
            "build_query_ortho_truth_manifest",
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "build_query_ortho_truth_manifest.py"),
                "--bundle-root",
                str(bundle_root),
                "--query-seed-csv",
                str(resolve_runtime_path(args.query_seed_csv)),
                "--crop-margin-m",
                str(args.crop_margin_m),
                "--output-root",
                str(eval_root),
                *query_flags,
            ],
        ),
        (
            "crop_query_ortho_truth_tiles",
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "crop_query_ortho_truth_tiles.py"),
                "--bundle-root",
                str(bundle_root),
                "--target-resolution-m",
                str(args.target_resolution_m),
                "--output-root",
                str(eval_root),
                *overwrite_flags,
            ],
        ),
        (
            "render_query_predicted_ortho_from_pose",
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "render_query_predicted_ortho_from_pose.py"),
                "--bundle-root",
                str(bundle_root),
                "--block-size",
                str(args.block_size),
                "--output-root",
                str(eval_root),
                *query_flags,
                *overwrite_flags,
            ],
        ),
        (
            "evaluate_pose_ortho_alignment",
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "evaluate_pose_ortho_alignment.py"),
                "--bundle-root",
                str(bundle_root),
                "--output-root",
                str(eval_root),
                *query_flags,
            ],
        ),
        (
            "render_pose_ortho_overlay_viz",
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "render_pose_ortho_overlay_viz.py"),
                "--bundle-root",
                str(bundle_root),
                "--output-root",
                str(eval_root),
                *query_flags,
                *overwrite_flags,
            ],
        ),
        (
            "evaluate_pose_ortho_tiepoint_ground_error",
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "evaluate_pose_ortho_tiepoint_ground_error.py"),
                "--bundle-root",
                str(bundle_root),
                "--output-root",
                str(eval_root),
                "--ortho-output-root",
                str(eval_root),
                *query_flags,
            ],
        ),
        (
            "render_pose_ortho_tiepoint_viz",
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "render_pose_ortho_tiepoint_viz.py"),
                "--bundle-root",
                str(bundle_root),
                "--output-root",
                str(eval_root),
                *query_flags,
                *overwrite_flags,
            ],
        ),
    ]

    step_results = [run_step(step_name, command) for step_name, command in steps]
    failed_step_names = [str(item["step_name"]) for item in step_results if int(item["returncode"]) != 0]
    overall_summary = (
        load_summary_if_exists(eval_root / "overall_ortho_accuracy.json")
        if step_succeeded(step_results, "evaluate_pose_ortho_alignment")
        else {}
    )
    truth_summary = (
        load_summary_if_exists(eval_root / "truth_tiles" / "_summary.json")
        if step_succeeded(step_results, "crop_query_ortho_truth_tiles")
        else {}
    )
    pred_summary = (
        load_summary_if_exists(eval_root / "pred_tiles" / "_summary.json")
        if step_succeeded(step_results, "render_query_predicted_ortho_from_pose")
        else {}
    )
    truth_viz_summary = (
        load_summary_if_exists(eval_root / "viz_overlay_truth" / "_summary.json")
        if step_succeeded(step_results, "render_pose_ortho_overlay_viz")
        else {}
    )
    dom_viz_summary = truth_viz_summary and load_summary_if_exists(eval_root / "viz_overlay_dom" / "_summary.json") or {}
    tiepoint_overall_summary = (
        load_summary_if_exists(eval_root / "overall_tiepoint_ground_error.json")
        if step_succeeded(step_results, "evaluate_pose_ortho_tiepoint_ground_error")
        else {}
    )
    tiepoint_viz_summary = (
        load_summary_if_exists(eval_root / "viz_tiepoints" / "_summary.json")
        if step_succeeded(step_results, "render_pose_ortho_tiepoint_viz")
        else {}
    )

    pnp_failed_counts = summarize_by_query_pnp_failures(
        [row for row in pnp_rows if row["query_id"] in selected_query_ids]
    )
    phase_payload = {
        "phase": args.phase,
        "query_count": len(selected_query_ids),
        "selected_query_ids": selected_query_ids,
        "target_resolution_m": args.target_resolution_m,
        "crop_margin_m": args.crop_margin_m,
        "steps": step_results,
        "pipeline_status": "ok" if not failed_step_names else "failed",
        "failed_step_names": failed_step_names,
        "truth_tile_summary": truth_summary,
        "pred_tile_summary": pred_summary,
        "overlay_truth_summary": truth_viz_summary,
        "overlay_dom_summary": dom_viz_summary,
        "overall_ortho_accuracy": overall_summary,
        "overall_tiepoint_ground_error": tiepoint_overall_summary,
        "overlay_tiepoint_summary": tiepoint_viz_summary,
        "pnp_failed_candidate_counts": pnp_failed_counts,
        "generated_at_unix": time.time(),
    }
    out_path = eval_root / ("phase_gate_summary.json" if args.phase == "gate" else "full_run_summary.json")
    write_json(out_path, phase_payload)
    print(out_path)


if __name__ == "__main__":
    main()

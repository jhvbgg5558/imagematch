#!/usr/bin/env python3
"""Run the satellite-truth + SRTM-compatible three-layer validation suite.

Purpose:
- orchestrate satellite truth patch generation, pose-vs-AT diagnostics, and
  RoMa v2 tie-point ground error under one dedicated suite root;
- keep layer semantics aligned with the formal pose suite while replacing only
  the truth source and the layer-3 matcher;
- write a compatibility subset of layer-1 files under `ortho_alignment/` so
  existing summary/report generators can be reused without changing runtime
  semantics.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from pose_ortho_truth_utils import load_csv, load_json, write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = (
    PROJECT_ROOT
    / "new3output"
    / "nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16"
    / "pose_v1_formal"
)
DEFAULT_SUITE_DIRNAME = "eval_pose_validation_suite_sattruth_srtm"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--query-seed-csv", required=True)
    parser.add_argument("--query-truth-tiles-csv", required=True)
    parser.add_argument("--query-truth-csv", required=True)
    parser.add_argument("--phase", choices=("gate", "full"), default="gate")
    parser.add_argument("--gate-count", type=int, default=5)
    parser.add_argument("--crop-margin-m", type=float, default=80.0)
    parser.add_argument("--target-resolution-m", type=float, default=0.5)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--min-inliers", type=int, default=6)
    parser.add_argument("--roma-sample-count", type=int, default=5000)
    parser.add_argument("--roma-setting", default="satast")
    parser.add_argument("--device", default="cuda")
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


def build_query_flags(query_ids: list[str]) -> list[str]:
    flags: list[str] = []
    for query_id in query_ids:
        flags.extend(["--query-id", query_id])
    return flags


def run_step(step_name: str, command: list[str]) -> dict[str, object]:
    started = time.time()
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return {
        "step_name": step_name,
        "command": command,
        "returncode": completed.returncode,
        "elapsed_sec": time.time() - started,
    }


def load_summary_if_exists(path: Path) -> dict[str, object]:
    if path.exists():
        return load_json(path)
    return {}


def copy_file_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def mirror_ortho_outputs(suite_root: Path) -> None:
    sat_root = suite_root / "ortho_alignment_satellite"
    compat_root = suite_root / "ortho_alignment"
    compat_root.mkdir(parents=True, exist_ok=True)
    for name in (
        "per_query_ortho_accuracy.csv",
        "overall_ortho_accuracy.json",
        "per_flight_ortho_accuracy.csv",
        "failure_buckets.csv",
        "full_run_summary.json",
        "phase_gate_summary.json",
    ):
        copy_file_if_exists(sat_root / name, compat_root / name)
    copy_file_if_exists(suite_root / "satellite_truth" / "query_satellite_truth_manifest.csv", compat_root / "query_ortho_truth_manifest.csv")


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    suite_root = Path(args.output_root) if args.output_root else bundle_root / DEFAULT_SUITE_DIRNAME
    suite_root.mkdir(parents=True, exist_ok=True)
    (suite_root / "reports").mkdir(parents=True, exist_ok=True)
    (suite_root / "logs").mkdir(parents=True, exist_ok=True)

    query_seed_rows = load_csv(Path(args.query_seed_csv))
    best_rows = load_csv(bundle_root / "summary" / "per_query_best_pose.csv")
    pnp_rows = load_csv(bundle_root / "pnp" / "pnp_results.csv")

    if args.query_id:
        selected_query_ids = args.query_id
    elif args.phase == "full":
        selected_query_ids = [row["query_id"] for row in best_rows]
    else:
        selected_query_ids = choose_gate_queries(best_rows, pnp_rows, query_seed_rows, args.gate_count)

    query_flags = build_query_flags(selected_query_ids)
    overwrite_flags = ["--overwrite"] if args.overwrite else []
    ortho_sat_root = suite_root / "ortho_alignment_satellite"
    ortho_compat_root = suite_root / "ortho_alignment"
    pose_root = suite_root / "pose_vs_at"
    tie_root = suite_root / "tiepoint_ground_error"
    truth_manifest_csv = suite_root / "satellite_truth" / "query_satellite_truth_manifest.csv"

    steps = [
        (
            "build_query_satellite_truth_manifest",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "build_query_satellite_truth_manifest.py"),
                "--bundle-root",
                str(bundle_root),
                "--query-seed-csv",
                str(args.query_seed_csv),
                "--query-truth-tiles-csv",
                str(args.query_truth_tiles_csv),
                "--query-truth-csv",
                str(args.query_truth_csv),
                "--crop-margin-m",
                str(args.crop_margin_m),
                "--output-root",
                str(suite_root),
                *query_flags,
            ],
        ),
        (
            "crop_query_satellite_truth_patches",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "crop_query_satellite_truth_patches.py"),
                "--bundle-root",
                str(bundle_root),
                "--truth-manifest-csv",
                str(truth_manifest_csv),
                "--target-resolution-m",
                str(args.target_resolution_m),
                "--output-root",
                str(suite_root),
                *overwrite_flags,
            ],
        ),
        (
            "render_query_predicted_ortho_from_pose",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "render_query_predicted_ortho_from_pose.py"),
                "--bundle-root",
                str(bundle_root),
                "--truth-manifest-csv",
                str(truth_manifest_csv),
                "--block-size",
                str(args.block_size),
                "--output-root",
                str(suite_root),
                *query_flags,
                *overwrite_flags,
            ],
        ),
        (
            "evaluate_pose_satellite_alignment",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "evaluate_pose_satellite_alignment.py"),
                "--bundle-root",
                str(bundle_root),
                "--truth-manifest-csv",
                str(truth_manifest_csv),
                "--output-root",
                str(suite_root),
                *query_flags,
            ],
        ),
    ]
    step_results = [run_step(step_name, command) for step_name, command in steps]
    if all(int(item["returncode"]) == 0 for item in step_results):
        mirror_ortho_outputs(suite_root)

    remaining_steps = [
        (
            "render_pose_ortho_overlay_viz",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "render_pose_ortho_overlay_viz.py"),
                "--bundle-root",
                str(bundle_root),
                "--truth-manifest-csv",
                str(truth_manifest_csv),
                "--pred-manifest-csv",
                str(suite_root / "pred_tiles" / "pred_tile_manifest.csv"),
                "--output-root",
                str(ortho_compat_root),
                *query_flags,
                *overwrite_flags,
            ],
        ),
        (
            "build_query_reference_pose_manifest",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "build_query_reference_pose_manifest.py"),
                "--bundle-root",
                str(bundle_root),
                "--query-seed-csv",
                str(args.query_seed_csv),
                "--output-root",
                str(pose_root),
                *query_flags,
            ],
        ),
        (
            "evaluate_pose_against_reference_pose",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "evaluate_pose_against_reference_pose.py"),
                "--bundle-root",
                str(bundle_root),
                "--output-root",
                str(pose_root),
                *query_flags,
            ],
        ),
        (
            "render_pose_vs_at_figures",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "render_pose_vs_at_figures.py"),
                "--pose-root",
                str(pose_root),
            ],
        ),
        (
            "evaluate_pose_satellite_tiepoint_ground_error_romav2",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "evaluate_pose_satellite_tiepoint_ground_error_romav2.py"),
                "--bundle-root",
                str(bundle_root),
                "--ortho-accuracy-csv",
                str(ortho_sat_root / "per_query_ortho_accuracy.csv"),
                "--output-root",
                str(suite_root),
                "--ortho-output-root",
                str(suite_root),
                "--device",
                args.device,
                "--setting",
                args.roma_setting,
                "--sample-count",
                str(args.roma_sample_count),
                "--min-inliers",
                str(args.min_inliers),
                *query_flags,
            ],
        ),
        (
            "render_pose_ortho_tiepoint_viz",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "render_pose_ortho_tiepoint_viz.py"),
                "--bundle-root",
                str(bundle_root),
                "--output-root",
                str(tie_root),
                *query_flags,
                *overwrite_flags,
            ],
        ),
        (
            "summarize_pose_validation_suite",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "summarize_pose_validation_suite.py"),
                "--bundle-root",
                str(bundle_root),
                "--output-root",
                str(suite_root),
                "--ortho-root",
                str(ortho_compat_root),
                "--pose-root",
                str(pose_root),
                "--tiepoint-root",
                str(tie_root),
                "--phase",
                args.phase,
                *query_flags,
            ],
        ),
    ]
    step_results.extend(run_step(step_name, command) for step_name, command in remaining_steps)

    failed_step_names = [str(item["step_name"]) for item in step_results if int(item["returncode"]) != 0]
    ortho_overall = load_summary_if_exists(ortho_compat_root / "overall_ortho_accuracy.json")
    pose_overall = load_summary_if_exists(pose_root / "overall_pose_vs_at.json")
    tie_overall = load_summary_if_exists(tie_root / "overall_tiepoint_ground_error.json")

    summary_payload = {
        "phase": args.phase,
        "query_count": len(selected_query_ids),
        "selected_query_ids": selected_query_ids,
        "suite_root": str(suite_root),
        "ortho_alignment_satellite_root": str(ortho_sat_root),
        "ortho_root": str(ortho_compat_root),
        "pose_vs_at_root": str(pose_root),
        "tiepoint_ground_error_root": str(tie_root),
        "steps": step_results,
        "pipeline_status": "ok" if not failed_step_names else "failed",
        "failed_step_names": failed_step_names,
        "overall_ortho_accuracy": ortho_overall,
        "overall_pose_vs_at": pose_overall,
        "overall_tiepoint_ground_error": tie_overall,
        "pnp_failed_candidate_counts": summarize_by_query_pnp_failures(
            [row for row in pnp_rows if row["query_id"] in selected_query_ids]
        ),
        "generated_at_unix": time.time(),
    }
    out_path = suite_root / ("phase_gate_summary.json" if args.phase == "gate" else "full_run_summary.json")
    write_json(out_path, summary_payload)
    (suite_root / "logs" / "run_pose_validation_suite_sattruth_srtm.log").write_text(
        "\n".join(
            [
                "stage=run_pose_validation_suite_sattruth_srtm",
                f"phase={args.phase}",
                f"pipeline_status={summary_payload['pipeline_status']}",
                f"query_count={len(selected_query_ids)}",
                f"suite_root={suite_root}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(out_path)


if __name__ == "__main__":
    main()

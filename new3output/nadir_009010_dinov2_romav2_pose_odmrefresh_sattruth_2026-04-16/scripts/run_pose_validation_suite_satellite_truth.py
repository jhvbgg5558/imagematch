#!/usr/bin/env python3
"""Run the satellite-truth validation suite for formal Pose v1.

Purpose:
- orchestrate satellite truth manifest selection, truth patch cropping,
  orthophoto alignment, geometry diagnostics, and tie-point evaluation under a
  dedicated satellite-truth suite root;
- keep the satellite-truth outputs isolated from the existing UAV
  orthophoto-truth validation root;
- emit suite-level summaries and reports under
  `pose_v1_formal/eval_pose_validation_suite_satellite_truth`.

Main inputs:
- formal pose outputs under the active `pose_v1_formal` bundle root;
- selected query truth metadata under the active experiment root;
- coverage-truth satellite tile tables from the fixed satellite library.

Main outputs:
- `eval_pose_validation_suite_satellite_truth/*`.

Applicable task constraints:
- the satellite truth must be derived from source GeoTIFF crops;
- fixed tiles are selection anchors only and must not be written as final
  truth patches;
- top-k candidate stitching must not be used to fabricate truth.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from pose_ortho_truth_utils import load_csv, load_json, resolve_runtime_path, write_json
from satellite_truth_utils import (
    DEFAULT_BUNDLE_ROOT,
    DEFAULT_QUERY_SEED_CSV,
    DEFAULT_QUERY_TRUTH_CSV,
    DEFAULT_QUERY_TRUTH_TILES_CSV,
    DEFAULT_SUITE_DIRNAME,
    resolve_satellite_suite_root,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--query-seed-csv", default=str(DEFAULT_QUERY_SEED_CSV))
    parser.add_argument("--query-truth-tiles-csv", default=str(DEFAULT_QUERY_TRUTH_TILES_CSV))
    parser.add_argument("--query-truth-csv", default=str(DEFAULT_QUERY_TRUTH_CSV))
    parser.add_argument("--phase", choices=("gate", "full"), default="gate")
    parser.add_argument("--gate-count", type=int, default=5)
    parser.add_argument("--crop-margin-m", type=float, default=80.0)
    parser.add_argument("--target-resolution-m", type=float, default=0.5)
    parser.add_argument("--min-inliers", type=int, default=6)
    parser.add_argument("--ratio-test", type=float, default=0.75)
    parser.add_argument("--ransac-threshold-px", type=float, default=4.0)
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


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    suite_root = resolve_satellite_suite_root(bundle_root, args.output_root)
    ensure_paths = [suite_root, suite_root / "reports", suite_root / "logs"]
    for path in ensure_paths:
        path.mkdir(parents=True, exist_ok=True)

    query_seed_rows = load_csv(resolve_runtime_path(args.query_seed_csv))
    best_pose_csv = bundle_root / "summary" / "per_query_best_pose.csv"
    pnp_results_csv = bundle_root / "pnp" / "pnp_results.csv"
    best_rows = load_csv(resolve_runtime_path(best_pose_csv)) if best_pose_csv.exists() else []
    pnp_rows = load_csv(resolve_runtime_path(pnp_results_csv)) if pnp_results_csv.exists() else []

    if args.query_id:
        selected_query_ids = args.query_id
    elif args.phase == "full":
        selected_query_ids = [row["query_id"] for row in best_rows]
    else:
        selected_query_ids = choose_gate_queries(best_rows, pnp_rows, query_seed_rows, args.gate_count)

    query_flags = build_query_flags(selected_query_ids)
    overwrite_flags = ["--overwrite"] if args.overwrite else []

    truth_manifest_csv = suite_root / "satellite_truth" / "query_satellite_truth_manifest.csv"
    steps = [
        (
            "build_query_satellite_truth_manifest",
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "build_query_satellite_truth_manifest.py"),
                "--bundle-root",
                str(bundle_root),
                "--query-seed-csv",
                str(resolve_runtime_path(args.query_seed_csv)),
                "--query-truth-tiles-csv",
                str(resolve_runtime_path(args.query_truth_tiles_csv)),
                "--query-truth-csv",
                str(resolve_runtime_path(args.query_truth_csv)),
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
                sys.executable,
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
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "render_query_predicted_ortho_from_pose.py"),
                "--bundle-root",
                str(bundle_root),
                "--truth-manifest-csv",
                str(truth_manifest_csv),
                "--block-size",
                "256",
                "--output-root",
                str(suite_root),
                *query_flags,
                *overwrite_flags,
            ],
        ),
        (
            "evaluate_pose_satellite_alignment",
            [
                sys.executable,
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
        (
            "evaluate_pose_satellite_geometry",
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "evaluate_pose_satellite_geometry.py"),
                "--bundle-root",
                str(bundle_root),
                "--truth-manifest-csv",
                str(truth_manifest_csv),
                "--output-root",
                str(suite_root),
                *query_flags,
            ],
        ),
        (
            "evaluate_pose_satellite_tiepoint_ground_error",
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "evaluate_pose_satellite_tiepoint_ground_error.py"),
                "--bundle-root",
                str(bundle_root),
                "--ortho-accuracy-csv",
                str(suite_root / "ortho_alignment_satellite" / "per_query_ortho_accuracy.csv"),
                "--output-root",
                str(suite_root),
                "--ortho-output-root",
                str(suite_root),
                *query_flags,
            ],
        ),
    ]

    step_results = [run_step(step_name, command) for step_name, command in steps]

    ortho_overall = load_summary_if_exists(suite_root / "ortho_alignment_satellite" / "overall_ortho_accuracy.json")
    geom_overall = load_summary_if_exists(suite_root / "pose_vs_satellite_truth_geometry" / "overall_satellite_truth_geometry.json")
    tie_overall = load_summary_if_exists(suite_root / "tiepoint_ground_error_satellite" / "overall_tiepoint_ground_error.json")
    manifest = load_summary_if_exists(suite_root / "satellite_truth" / "query_satellite_truth_manifest.json")

    pipeline_status = "ok" if all(item["returncode"] == 0 for item in step_results) else "failed"
    full_summary = {
        "bundle_root": str(bundle_root),
        "suite_root": str(suite_root),
        "phase": args.phase,
        "pipeline_status": pipeline_status,
        "selected_query_ids": selected_query_ids,
        "query_count": len(selected_query_ids),
        "steps": step_results,
        "satellite_truth_manifest": manifest,
        "overall_ortho_accuracy": ortho_overall,
        "overall_satellite_truth_geometry": geom_overall,
        "overall_tiepoint_ground_error": tie_overall,
        "generated_at_unix": time.time(),
    }
    summary_path = suite_root / ("phase_gate_summary.json" if args.phase == "gate" else "full_run_summary.json")
    write_json(summary_path, full_summary)

    report_step = run_step(
        "generate_pose_validation_suite_satellite_truth_word_report",
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "generate_pose_validation_suite_satellite_truth_word_report.py"),
            "--suite-root",
            str(suite_root),
        ],
    )
    step_results.append(report_step)
    localization_step = run_step(
        "generate_pose_localization_accuracy_satellite_truth_report",
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "generate_pose_localization_accuracy_satellite_truth_report.py"),
            "--suite-root",
            str(suite_root),
        ],
    )
    step_results.append(localization_step)
    full_summary["steps"] = step_results
    full_summary["pipeline_status"] = "ok" if all(item["returncode"] == 0 for item in step_results) else "failed"
    write_json(summary_path, full_summary)

    (suite_root / "logs" / "run_pose_validation_suite_satellite_truth.log").write_text(
        "\n".join(
            [
                "stage=run_pose_validation_suite_satellite_truth",
                f"phase={args.phase}",
                f"pipeline_status={pipeline_status}",
                f"query_count={len(selected_query_ids)}",
                f"suite_root={suite_root}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(suite_root / ("phase_gate_summary.json" if args.phase == "gate" else "full_run_summary.json"))


if __name__ == "__main__":
    main()

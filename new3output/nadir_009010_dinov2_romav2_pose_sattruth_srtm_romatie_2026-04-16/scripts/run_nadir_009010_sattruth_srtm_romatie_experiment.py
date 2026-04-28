#!/usr/bin/env python3
"""Run the isolated satellite-truth + SRTM + RoMa-tiepoint experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REUSE_ROOT = PROJECT_ROOT / "new2output" / "nadir_009010_dinov2_romav2_pose_2026-04-10"
DEFAULT_EXPERIMENT_ROOT = (
    PROJECT_ROOT
    / "new3output"
    / "nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16"
)
DEFAULT_TILES_CSV = (
    PROJECT_ROOT
    / "output"
    / "coverage_truth_200_300_500_700_dinov2_baseline"
    / "fixed_satellite_library"
    / "tiles.csv"
)
DEFAULT_SOURCE_HGT = PROJECT_ROOT / "new2output" / "N30E114.hgt"
SCRIPT_SNAPSHOT_NAMES = (
    "build_formal_query_manifest.py",
    "build_formal_candidate_manifest.py",
    "build_candidate_dsm_cache.py",
    "materialize_formal_dsm_rasters.py",
    "build_pose_manifest.py",
    "validate_pose_assets.py",
    "run_formal_pose_v1_pipeline.py",
    "run_pose_validation_suite_sattruth_srtm.py",
    "evaluate_pose_satellite_tiepoint_ground_error_romav2.py",
    "generate_pose_localization_accuracy_word_report.py",
    "generate_sattruth_srtm_romatie_vs_baseline_report.py",
    "run_nadir_009010_sattruth_srtm_romatie_experiment.py",
)
REUSED_DIRS = (
    "selected_queries",
    "query_inputs",
    "query_truth",
    "query_features",
    "retrieval",
    "romav2_rerank",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-root", default=str(DEFAULT_EXPERIMENT_ROOT))
    parser.add_argument("--reuse-retrieval-root", default=str(DEFAULT_REUSE_ROOT))
    parser.add_argument("--validation-phase", choices=("gate", "full"), default="gate")
    parser.add_argument("--pose-phase", choices=("sample", "full"), default="")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--roma-setting", default="satast")
    parser.add_argument("--roma-sample-count", type=int, default=5000)
    parser.add_argument("--sample-query-count", type=int, default=5)
    parser.add_argument("--pose-sample-count", type=int, default=2000)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def run_cmd(command: list[str], log_path: Path, dry_run: bool) -> None:
    ensure_dir(log_path.parent)
    rendered = " ".join(command)
    print("+", rendered)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_now()}] + {rendered}\n")
    if dry_run:
        return
    with log_path.open("a", encoding="utf-8") as handle:
        subprocess.run(command, cwd=PROJECT_ROOT, stdout=handle, stderr=subprocess.STDOUT, text=True, check=True)


def sync_reused_assets(reuse_root: Path, experiment_root: Path, overwrite: bool) -> None:
    for dirname in REUSED_DIRS:
        src = reuse_root / dirname
        dst = experiment_root / dirname
        if not src.exists():
            raise SystemExit(f"missing reused asset directory: {src}")
        if dst.exists() and overwrite:
            shutil.rmtree(dst)
        if not dst.exists():
            shutil.copytree(src, dst)


def copy_script_snapshots(experiment_root: Path) -> None:
    snapshot_root = experiment_root / "scripts"
    ensure_dir(snapshot_root)
    rows: list[dict[str, object]] = []
    for name in SCRIPT_SNAPSHOT_NAMES:
        src = PROJECT_ROOT / "scripts" / name
        if not src.exists():
            continue
        dst = snapshot_root / name
        shutil.copy2(src, dst)
        rows.append(
            {
                "file": name,
                "source_path": str(src),
                "snapshot_path": str(dst),
                "sha256": sha256_file(src),
                "copied_at_utc": utc_now(),
            }
        )
    write_json(snapshot_root / "script_manifest.json", {"scripts": rows})


def pose_phase_from_args(args: argparse.Namespace) -> str:
    if args.pose_phase:
        return args.pose_phase
    return "full" if args.validation_phase == "full" else "sample"


def main() -> None:
    args = parse_args()
    experiment_root = Path(args.experiment_root)
    reuse_root = Path(args.reuse_retrieval_root)
    pose_root = experiment_root / "pose_v1_formal"
    logs_root = experiment_root / "logs"
    for dirname in (*REUSED_DIRS, "reports", "plan", "scripts", "pose_v1_formal", "logs"):
        ensure_dir(experiment_root / dirname)

    sync_reused_assets(reuse_root, experiment_root, args.overwrite)
    copy_script_snapshots(experiment_root)

    run_log = logs_root / f"run_sattruth_srtm_romatie_{args.validation_phase}.log"
    pose_phase = pose_phase_from_args(args)
    query_manifest = experiment_root / "query_inputs" / "query_manifest.csv"
    selected_summary = experiment_root / "selected_queries" / "selected_images_summary.csv"
    retrieval_top20 = experiment_root / "retrieval" / "retrieval_top20.csv"
    query_truth_csv = experiment_root / "query_truth" / "query_truth.csv"
    query_truth_tiles_csv = experiment_root / "query_truth" / "query_truth_tiles.csv"
    query_seed_csv = experiment_root / "query_truth" / "queries_truth_seed.csv"
    suite_root = pose_root / "eval_pose_validation_suite_sattruth_srtm"

    write_json(
        experiment_root / "plan" / "experiment_contract.json",
        {
            "experiment_root": str(experiment_root),
            "reuse_retrieval_root": str(reuse_root),
            "validation_phase": args.validation_phase,
            "pose_phase": pose_phase,
            "runtime_task_definition": "uav_to_fixed_satellite_library_localization",
            "main_variable_changes": [
                "truth orthophoto: UAV orthophoto -> satellite truth patch",
                "PnP DSM: SRTM retained",
                "layer-3 tiepoint matcher: SIFT/BF -> RoMa v2",
            ],
            "generated_at_utc": utc_now(),
        },
    )

    run_cmd(
        [
            args.python_bin,
            "scripts/build_formal_query_manifest.py",
            "--bundle-root",
            str(pose_root),
            "--query-manifest-csv",
            str(query_manifest),
            "--selected-summary-csv",
            str(selected_summary),
        ],
        run_log,
        args.dry_run,
    )
    run_cmd(
        [
            args.python_bin,
            "scripts/build_formal_candidate_manifest.py",
            "--bundle-root",
            str(pose_root),
            "--retrieval-top20-csv",
            str(retrieval_top20),
            "--tiles-csv",
            str(DEFAULT_TILES_CSV),
            "--query-truth-tiles-csv",
            str(query_truth_tiles_csv),
            "--query-truth-csv",
            str(query_truth_csv),
        ],
        run_log,
        args.dry_run,
    )
    run_cmd(
        [
            args.python_bin,
            "scripts/build_candidate_dsm_cache.py",
            "--bundle-root",
            str(pose_root),
            "--dsm-source-name",
            "srtm",
            "--dsm-source-type",
            "srtm_hgt",
            "--dsm-asset-version-tag",
            "srtm_1arcsec_locked",
            "--upstream-dsm-path",
            str(DEFAULT_SOURCE_HGT),
        ],
        run_log,
        args.dry_run,
    )
    run_cmd(
        [
            args.python_bin,
            "scripts/materialize_formal_dsm_rasters.py",
            "--bundle-root",
            str(pose_root),
            "--source-hgt",
            str(DEFAULT_SOURCE_HGT),
        ],
        run_log,
        args.dry_run,
    )
    run_cmd(
        [
            args.python_bin,
            "scripts/build_pose_manifest.py",
            "--bundle-root",
            str(pose_root),
            "--query-manifest-csv",
            str(pose_root / "input" / "formal_query_manifest.csv"),
            "--dom-manifest-csv",
            str(pose_root / "input" / "formal_candidate_manifest.csv"),
            "--dsm-manifest-csv",
            str(pose_root / "input" / "formal_dsm_manifest.csv"),
            "--coarse-topk-csv",
            str(retrieval_top20),
        ],
        run_log,
        args.dry_run,
    )
    run_cmd(
        [args.python_bin, "scripts/validate_pose_assets.py", "--bundle-root", str(pose_root)],
        run_log,
        args.dry_run,
    )

    formal_cmd = [
        args.python_bin,
        "scripts/run_formal_pose_v1_pipeline.py",
        "--bundle-root",
        str(pose_root),
        "--phase",
        pose_phase,
        "--device",
        args.device,
        "--skip-dsm-build",
        "--sample-count",
        str(args.pose_sample_count),
        "--python-exe",
        args.python_bin,
    ]
    if pose_phase == "sample":
        formal_cmd.extend(["--sample-query-count", str(args.sample_query_count)])
    run_cmd(formal_cmd, run_log, args.dry_run)

    run_cmd(
        [
            args.python_bin,
            "scripts/run_pose_validation_suite_sattruth_srtm.py",
            "--bundle-root",
            str(pose_root),
            "--python-bin",
            str(args.python_bin),
            "--query-seed-csv",
            str(query_seed_csv),
            "--query-truth-tiles-csv",
            str(query_truth_tiles_csv),
            "--query-truth-csv",
            str(query_truth_csv),
            "--phase",
            args.validation_phase,
            "--output-root",
            str(suite_root),
            "--device",
            args.device,
            "--roma-setting",
            args.roma_setting,
            "--roma-sample-count",
            str(args.roma_sample_count),
            *(["--overwrite"] if args.overwrite else []),
        ],
        run_log,
        args.dry_run,
    )
    run_cmd(
        [
            args.python_bin,
            "scripts/generate_pose_localization_accuracy_word_report.py",
            "--suite-root",
            str(suite_root),
            "--out-docx",
            str(suite_root / "reports" / "formal_pose_v1_validation_suite_sattruth_srtm_report.docx"),
        ],
        run_log,
        args.dry_run,
    )
    run_cmd(
        [
            args.python_bin,
            "scripts/generate_pose_localization_accuracy_word_report.py",
            "--suite-root",
            str(suite_root),
            "--out-docx",
            str(suite_root / "reports" / "pose_localization_accuracy_sattruth_srtm_romatie_report.docx"),
        ],
        run_log,
        args.dry_run,
    )
    run_cmd(
        [
            args.python_bin,
            "scripts/generate_sattruth_srtm_romatie_vs_baseline_report.py",
            "--baseline-root",
            str(reuse_root),
            "--experiment-root",
            str(experiment_root),
        ],
        run_log,
        args.dry_run,
    )

    if not args.dry_run:
        summary = {
            "experiment_root": str(experiment_root),
            "validation_phase": args.validation_phase,
            "pose_phase": pose_phase,
            "query_count": len(load_csv(experiment_root / "query_inputs" / "query_manifest.csv")),
            "suite_root": str(suite_root),
            "suite_summary_json": str(
                suite_root / ("phase_gate_summary.json" if args.validation_phase == "gate" else "full_run_summary.json")
            ),
            "generated_at_utc": utc_now(),
        }
        write_json(experiment_root / "plan" / f"run_sattruth_srtm_romatie_{args.validation_phase}_summary.json", summary)


if __name__ == "__main__":
    main()

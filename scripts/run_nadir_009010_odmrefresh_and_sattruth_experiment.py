#!/usr/bin/env python3
"""Run the isolated new3output ODM-refresh experiment variants.

Purpose:
- reuse the locked 009/010 retrieval assets from the completed new2output run
  while rebuilding only the truth orthophoto layer, the PnP DSM layer, and
  the downstream pose/validation outputs under a new3output root;
- keep the runtime task unchanged as UAV-to-satellite localization;
- optionally run the independent satellite-truth validation suite on the same
  best-pose results and generate a cross-suite comparison report;
- support an ODM-only rerun path that fixes both orthophoto-truth and ODM DSM
  resampling to a uniform experiment resolution while skipping all report
  generation.

Main inputs:
- reused retrieval-side assets from the completed
  `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10`;
- raw UAV flight workspaces for 009/010 to resolve ODM orthophoto and DSM
  override assets;
- the fixed satellite library metadata reused by the original experiment.

Main outputs:
- all new assets under an isolated `new3output/...` experiment root;
- `pose_v1_formal/eval_pose_validation_suite_odm_truth/`;
- `pose_v1_formal/eval_pose_validation_suite_satellite_truth/`;
- optional `reports/odm_truth_vs_satellite_truth_comparison.md` and `.docx`.

Applicable task constraints:
- runtime candidate DOM retrieval remains the fixed satellite library;
- query intrinsics are not replaced in this experiment;
- only truth orthophoto and PnP DSM are refreshed from ODM assets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REUSE_ROOT = PROJECT_ROOT / "new2output" / "nadir_009010_dinov2_romav2_pose_2026-04-10"
DEFAULT_EXPERIMENT_ROOT = (
    PROJECT_ROOT / "new3output" / "nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_0p1m_2026-04-17"
)
DEFAULT_TILES_CSV = (
    PROJECT_ROOT
    / "output"
    / "coverage_truth_200_300_500_700_dinov2_baseline"
    / "fixed_satellite_library"
    / "tiles.csv"
)

SCRIPT_SNAPSHOT_NAMES = (
    "build_odm_asset_override_manifest.py",
    "build_query_ortho_truth_manifest.py",
    "build_candidate_dsm_cache.py",
    "materialize_formal_dsm_rasters_from_odm.py",
    "run_pose_validation_suite.py",
    "run_pose_validation_suite_satellite_truth.py",
    "generate_odm_truth_vs_satellite_truth_comparison_report.py",
    "run_nadir_009010_odmrefresh_and_sattruth_experiment.py",
    "build_query_satellite_truth_manifest.py",
    "crop_query_satellite_truth_patches.py",
    "evaluate_pose_satellite_alignment.py",
    "evaluate_pose_satellite_geometry.py",
    "evaluate_pose_satellite_tiepoint_ground_error.py",
    "generate_pose_validation_suite_satellite_truth_word_report.py",
    "generate_pose_localization_accuracy_satellite_truth_report.py",
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
    parser.add_argument(
        "--phase",
        choices=("odm_truth_only", "satellite_truth_only", "full"),
        default="full",
    )
    parser.add_argument("--validation-phase", choices=("gate", "full"), default="gate")
    parser.add_argument("--pose-phase", choices=("sample", "full"), default="")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--flight-asset-manifest", default="")
    parser.add_argument("--asset-version-tag", default="odm_refresh_0p1m_2026-04-17")
    parser.add_argument("--target-resolution-m", type=float, default=0.1)
    parser.add_argument("--dsm-target-resolution-m", type=float, default=0.1)
    parser.add_argument("--skip-reports", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pose-sample-count", type=int, default=2000)
    parser.add_argument("--sample-query-count", type=int, default=5)
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


def load_json_if_exists(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def build_or_validate_override_manifest(args: argparse.Namespace, experiment_root: Path, run_log: Path) -> Path:
    manifest_path = (
        Path(args.flight_asset_manifest)
        if args.flight_asset_manifest
        else experiment_root / "plan" / "flight_asset_override_manifest.csv"
    )
    if not args.flight_asset_manifest:
        run_cmd(
            [
                args.python_bin,
                "scripts/build_odm_asset_override_manifest.py",
                "--experiment-root",
                str(experiment_root),
                "--asset-version-tag",
                args.asset_version_tag,
                "--out-csv",
                str(manifest_path),
            ],
            run_log,
            args.dry_run,
        )
    if args.dry_run:
        return manifest_path
    rows = load_csv(manifest_path)
    if len(rows) != 2:
        raise SystemExit(f"flight asset override manifest must contain exactly 2 rows: {manifest_path}")
    bad = [row["flight_id"] for row in rows if row.get("status") != "ready"]
    if bad:
        raise SystemExit(f"flight asset override manifest contains non-ready rows: {bad}")
    return manifest_path


def pose_phase_from_args(args: argparse.Namespace) -> str:
    if args.pose_phase:
        return args.pose_phase
    return "full" if args.validation_phase == "full" else "sample"


def build_main_variable_changes(args: argparse.Namespace) -> list[str]:
    changes = [
        "truth orthophoto: historical ODM orthophoto -> override ODM orthophoto",
        "PnP DSM: SRTM crop cache -> ODM DSM override cache",
        f"uniform experiment resampling: orthophoto truth {args.target_resolution_m:.3f} m, ODM DSM {args.dsm_target_resolution_m:.3f} m",
    ]
    if args.phase in {"satellite_truth_only", "full"}:
        changes.append("parallel satellite truth validation suite added")
    return changes


def main() -> None:
    args = parse_args()
    experiment_root = Path(args.experiment_root)
    reuse_root = Path(args.reuse_retrieval_root)
    pose_root = experiment_root / "pose_v1_formal"
    logs_root = experiment_root / "logs"
    ensure_dir(experiment_root)
    ensure_dir(logs_root)
    for dirname in (*REUSED_DIRS, "reports", "plan", "scripts", "pose_v1_formal"):
        ensure_dir(experiment_root / dirname)

    sync_reused_assets(reuse_root, experiment_root, args.overwrite)
    copy_script_snapshots(experiment_root)

    run_log = logs_root / f"run_{args.phase}_{args.validation_phase}.log"
    pose_phase = pose_phase_from_args(args)
    manifest_path = build_or_validate_override_manifest(args, experiment_root, run_log)

    query_manifest = experiment_root / "query_inputs" / "query_manifest.csv"
    selected_summary = experiment_root / "selected_queries" / "selected_images_summary.csv"
    retrieval_top20 = experiment_root / "retrieval" / "retrieval_top20.csv"
    query_truth_csv = experiment_root / "query_truth" / "query_truth.csv"
    query_truth_tiles_csv = experiment_root / "query_truth" / "query_truth_tiles.csv"
    query_seed_csv = experiment_root / "query_truth" / "queries_truth_seed.csv"

    write_json(
        experiment_root / "plan" / "experiment_contract.json",
        {
            "experiment_root": str(experiment_root),
            "reuse_retrieval_root": str(reuse_root),
            "phase": args.phase,
            "validation_phase": args.validation_phase,
            "pose_phase": pose_phase,
            "runtime_task_definition": "uav_to_fixed_satellite_library_localization",
            "main_variable_changes": build_main_variable_changes(args),
            "query_intrinsics_policy": "reuse existing per-flight cameras.json derivation; do not replace query intrinsics in this experiment",
            "flight_asset_manifest": str(manifest_path),
            "report_policy": "skip_all_reports" if args.skip_reports else "allow_default_reports",
            "resampling_policy": {
                "orthophoto_truth_target_resolution_m": float(args.target_resolution_m),
                "odm_dsm_target_resolution_m": float(args.dsm_target_resolution_m),
                "policy": "uniform_experiment_resampling",
            },
            "generated_at_utc": utc_now(),
        },
    )

    if args.phase in {"odm_truth_only", "full"}:
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
                "odm_dsm_override",
                "--dsm-source-type",
                "odm_dsm_override",
                "--dsm-asset-version-tag",
                args.asset_version_tag,
                "--upstream-dsm-path",
                str(manifest_path),
            ],
            run_log,
            args.dry_run,
        )
        run_cmd(
            [
                args.python_bin,
                "scripts/materialize_formal_dsm_rasters_from_odm.py",
                "--bundle-root",
                str(pose_root),
                "--flight-asset-manifest",
                str(manifest_path),
                "--target-resolution-m",
                str(args.dsm_target_resolution_m),
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

        odm_suite_root = pose_root / "eval_pose_validation_suite_odm_truth"
        validation_cmd = [
            args.python_bin,
            "scripts/run_pose_validation_suite.py",
            "--bundle-root",
            str(pose_root),
            "--query-seed-csv",
            str(query_seed_csv),
            "--flight-asset-manifest",
            str(manifest_path),
            "--phase",
            args.validation_phase,
            "--output-root",
            str(odm_suite_root),
            "--target-resolution-m",
            str(args.target_resolution_m),
        ]
        if args.overwrite:
            validation_cmd.append("--overwrite")
        run_cmd(validation_cmd, run_log, args.dry_run)
        run_cmd(
            [
                args.python_bin,
                "scripts/render_pose_vs_at_figures.py",
                "--pose-root",
                str(odm_suite_root / "pose_vs_at"),
            ],
            run_log,
            args.dry_run,
        )
        if not args.skip_reports:
            run_cmd(
                [
                    args.python_bin,
                    "scripts/generate_pose_validation_suite_word_report.py",
                    "--suite-root",
                    str(odm_suite_root),
                    "--out-docx",
                    str(odm_suite_root / "reports" / "formal_pose_v1_validation_suite_odm_truth_report.docx"),
                ],
                run_log,
                args.dry_run,
            )
            run_cmd(
                [
                    args.python_bin,
                    "scripts/generate_pose_localization_accuracy_word_report.py",
                    "--suite-root",
                    str(odm_suite_root),
                    "--out-docx",
                    str(odm_suite_root / "reports" / "pose_localization_accuracy_odm_truth_report.docx"),
                ],
                run_log,
                args.dry_run,
            )

    if args.phase in {"satellite_truth_only", "full"}:
        satellite_suite_root = pose_root / "eval_pose_validation_suite_satellite_truth"
        sat_cmd = [
            args.python_bin,
            "scripts/run_pose_validation_suite_satellite_truth.py",
            "--bundle-root",
            str(pose_root),
            "--query-seed-csv",
            str(query_seed_csv),
            "--query-truth-tiles-csv",
            str(query_truth_tiles_csv),
            "--query-truth-csv",
            str(query_truth_csv),
            "--phase",
            args.validation_phase,
            "--output-root",
            str(satellite_suite_root),
        ]
        if args.overwrite:
            sat_cmd.append("--overwrite")
        run_cmd(sat_cmd, run_log, args.dry_run)

    if args.phase == "full" and not args.skip_reports:
        run_cmd(
            [
                args.python_bin,
                "scripts/generate_odm_truth_vs_satellite_truth_comparison_report.py",
                "--baseline-root",
                str(reuse_root),
                "--experiment-root",
                str(experiment_root),
            ],
            run_log,
            args.dry_run,
        )

    dsm_summary_path = pose_root / "dsm_cache" / "rasters" / "_summary.json"
    merged_raster_path = pose_root / "dsm_cache" / "source" / "odm_dsm_merged.tif"
    suite_summary_name = "phase_gate_summary.json" if args.validation_phase == "gate" else "full_run_summary.json"
    odm_suite_summary_path = pose_root / "eval_pose_validation_suite_odm_truth" / suite_summary_name
    dsm_summary = load_json_if_exists(dsm_summary_path)
    odm_suite_summary = load_json_if_exists(odm_suite_summary_path)

    write_json(
        experiment_root / "plan" / f"run_{args.phase}_{args.validation_phase}_summary.json",
        {
            "experiment_root": str(experiment_root),
            "reuse_root": str(reuse_root),
            "phase": args.phase,
            "validation_phase": args.validation_phase,
            "pose_phase": pose_phase,
            "flight_asset_manifest": str(manifest_path),
            "skip_reports": args.skip_reports,
            "target_resolution_m": float(args.target_resolution_m),
            "dsm_target_resolution_m": float(args.dsm_target_resolution_m),
            "dsm_summary_path": str(dsm_summary_path),
            "odm_truth_suite_summary_path": str(odm_suite_summary_path),
            "runtime_cost_indicators": {
                "dsm_merged_raster_bytes": merged_raster_path.stat().st_size if merged_raster_path.exists() else None,
                "dsm_raster_count": dsm_summary.get("built_count"),
                "dsm_target_resolution_m": dsm_summary.get("target_resolution_m"),
                "suite_pipeline_status": odm_suite_summary.get("pipeline_status"),
                "suite_query_count": odm_suite_summary.get("query_count"),
            },
            "dry_run": args.dry_run,
            "completed_at_utc": utc_now(),
        },
    )
    print(experiment_root)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run the CaiWangCun DOM/DSM full-replacement 009/010 full pass.

Purpose:
- expand the verified CaiWangCun full-replacement gate to all 40 query images;
- materialize an isolated full-run root without overwriting gate outputs;
- reuse gate-verified CaiWangCun retrieval assets, then rebuild formal pose
  inputs, DSM cache, full pose, full validation, frame sanity, QA, and reports.

Main inputs:
- the completed CaiWangCun full-replacement gate root;
- the project's formal pose and validation scripts;
- the gate-verified CaiWangCun DOM/DSM mosaic, candidate library, retrieval, and
  rerank assets.

Main outputs:
- `new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21`;
- full pose outputs for all 40 queries;
- CaiWangCun DOM-truth full validation outputs and frame-sanity diagnostics;
- full acceptance summaries and a final Markdown/Word report.

Applicable task constraints:
- query, DINOv2, RoMa v2, PnP, and validation algorithms remain unchanged from
  the accepted gate;
- validation truth and query truth are offline evaluation inputs, not runtime
  geolocation for retrieval;
- no ODM LAZ, SRTM, or old satellite candidate library fallback is permitted.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_nadir_009010_caiwangcun_fullreplace_gate_experiment import (
    as_manifest_path,
    ensure_dir,
    load_csv,
    materialize_dsm_from_mosaic,
    resolve_runtime_path,
    run_cmd,
    sha256_file,
    write_csv,
    write_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE_ROOT = (
    PROJECT_ROOT / "new3output" / "nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20"
)
DEFAULT_FULL_ROOT = (
    PROJECT_ROOT / "new3output" / "nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21"
)

COPY_DIRS = (
    "selected_queries",
    "query_inputs",
    "query_features",
    "query_truth",
    "source_mosaic",
    "candidate_library",
    "candidate_features",
    "faiss",
    "romav2_rerank",
    "retrieval",
)

SCRIPT_SNAPSHOT_NAMES = (
    "run_nadir_009010_caiwangcun_fullreplace_full_experiment.py",
    "run_nadir_009010_caiwangcun_fullreplace_gate_experiment.py",
    "build_caiwangcun_candidate_library.py",
    "diagnose_pose_frame_sanity.py",
    "build_formal_query_manifest.py",
    "build_formal_candidate_manifest.py",
    "build_candidate_dsm_cache.py",
    "build_pose_manifest.py",
    "run_formal_pose_v1_pipeline.py",
    "run_pose_validation_suite.py",
    "generate_caiwangcun_fullreplace_full_report.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-root", default=str(DEFAULT_GATE_ROOT))
    parser.add_argument("--experiment-root", default=str(DEFAULT_FULL_ROOT))
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--target-crs", default="EPSG:32650")
    parser.add_argument("--target-resolution-m", type=float, default=0.14)
    parser.add_argument("--pose-sample-count", type=int, default=5000)
    parser.add_argument("--crop-margin-m", type=float, default=80.0)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-materialize", action="store_true")
    parser.add_argument("--skip-pose", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def copytree_replace(src: Path, dst: Path, overwrite: bool) -> None:
    if not src.exists():
        raise SystemExit(f"missing source directory: {src}")
    if dst.exists() and overwrite:
        shutil.rmtree(dst)
    if not dst.exists():
        shutil.copytree(src, dst)


def copy_file_replace(src: Path, dst: Path, overwrite: bool) -> None:
    if not src.exists():
        raise SystemExit(f"missing source file: {src}")
    if dst.exists() and not overwrite:
        return
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)


def replace_text_in_file(path: Path, old_root: Path, new_root: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return False
    old_variants = {
        as_manifest_path(old_root),
        str(old_root).replace("/", "\\"),
    }
    new_posix = as_manifest_path(new_root)
    changed = False
    for old in old_variants:
        if old in text:
            text = text.replace(old, new_posix)
            changed = True
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def rewrite_manifest_paths(root: Path, old_root: Path, new_root: Path) -> dict[str, Any]:
    changed_files: list[str] = []
    for suffix in ("*.csv", "*.json", "*.txt", "*.md"):
        for path in root.rglob(suffix):
            if replace_text_in_file(path, old_root, new_root):
                changed_files.append(as_manifest_path(path))
    return {
        "old_root": as_manifest_path(old_root),
        "new_root": as_manifest_path(new_root),
        "changed_file_count": len(changed_files),
        "changed_files": changed_files[:200],
    }


def find_stale_root_references(root: Path, stale_root: Path) -> list[str]:
    stale = as_manifest_path(stale_root)
    allowed_names = {
        "full_preflight_audit.json",
        "full_asset_reuse_audit.json",
        "run_full_summary.json",
    }
    hits: list[str] = []
    for suffix in ("*.csv", "*.json", "*.txt", "*.md"):
        for path in root.rglob(suffix):
            if path.name in allowed_names:
                continue
            try:
                if stale in path.read_text(encoding="utf-8-sig"):
                    hits.append(as_manifest_path(path))
            except UnicodeDecodeError:
                continue
    return hits


def copy_script_snapshots(experiment_root: Path) -> None:
    snapshot_root = experiment_root / "scripts"
    ensure_dir(snapshot_root)
    rows: list[dict[str, Any]] = []
    for name in SCRIPT_SNAPSHOT_NAMES:
        src = PROJECT_ROOT / "scripts" / name
        if not src.exists():
            continue
        dst = snapshot_root / name
        shutil.copy2(src, dst)
        rows.append(
            {
                "file": name,
                "source_path": as_manifest_path(src),
                "snapshot_path": as_manifest_path(dst),
                "sha256": sha256_file(src),
                "copied_at_utc": utc_now(),
            }
        )
    write_json(snapshot_root / "script_manifest.json", {"scripts": rows})


def check_required_gate_assets(gate_root: Path) -> dict[str, Any]:
    required = [
        gate_root / "source_mosaic" / "caiwangcun_ortho_0p14m_epsg32650.tif",
        gate_root / "source_mosaic" / "caiwangcun_dsm_0p14m_epsg32650.tif",
        gate_root / "candidate_library" / "tiles.csv",
        gate_root / "candidate_features" / "caiwangcun_tile_dinov2_pooler.npz",
        gate_root / "candidate_features" / "caiwangcun_tile_dinov2_status.csv",
        gate_root / "faiss" / "caiwangcun_tiles_ip.index",
        gate_root / "faiss" / "caiwangcun_tiles_ip_mapping.json",
        gate_root / "retrieval" / "retrieval_top20.csv",
        gate_root / "romav2_rerank" / "coarse" / "summary_top20.json",
        gate_root / "pose_v1_formal" / "dsm_cache" / "rasters" / "_summary.json",
        gate_root / "pose_v1_formal" / "eval_pose_validation_suite_caiwangcun_truth" / "phase_gate_summary.json",
    ]
    missing = [as_manifest_path(path) for path in required if not path.exists()]
    stage7_files = list((gate_root / "romav2_rerank" / "stage7").rglob("reranked_top20.csv"))
    if len(stage7_files) < 2:
        missing.append(as_manifest_path(gate_root / "romav2_rerank" / "stage7" / "*reranked_top20.csv"))
    payload = {
        "gate_root": as_manifest_path(gate_root),
        "required_count": len(required) + 1,
        "missing": missing,
        "stage7_reranked_file_count": len(stage7_files),
        "candidate_tile_count": count_csv_rows(gate_root / "candidate_library" / "tiles.csv"),
        "retrieval_top20_rows": count_csv_rows(gate_root / "retrieval" / "retrieval_top20.csv"),
        "generated_at_utc": utc_now(),
    }
    if missing:
        raise SystemExit(f"missing required gate assets: {missing[:5]}")
    return payload


def check_runtime_environment() -> dict[str, Any]:
    checks: dict[str, Any] = {"generated_at_utc": utc_now()}
    try:
        import docx  # noqa: F401
        import matplotlib  # noqa: F401
        import PIL  # noqa: F401

        checks["python_report_libs"] = "ok"
    except ImportError as exc:
        checks["python_report_libs"] = f"missing:{exc}"
    try:
        import torch

        checks["cuda_available"] = bool(torch.cuda.is_available())
        checks["cuda_device_count"] = int(torch.cuda.device_count())
    except ImportError as exc:
        checks["cuda_available"] = f"torch_missing:{exc}"
    usage = shutil.disk_usage(PROJECT_ROOT)
    checks["disk_free_gb"] = round(usage.free / (1024**3), 2)
    checks["disk_total_gb"] = round(usage.total / (1024**3), 2)
    return checks


def materialize_full_root(gate_root: Path, experiment_root: Path, overwrite: bool) -> dict[str, Any]:
    ensure_dir(experiment_root / "plan")
    copied: list[dict[str, Any]] = []
    for dirname in COPY_DIRS:
        src = gate_root / dirname
        dst = experiment_root / dirname
        copytree_replace(src, dst, overwrite)
        copied.append({"kind": "dir", "name": dirname, "src": as_manifest_path(src), "dst": as_manifest_path(dst)})
    for name in ("caiwangcun_asset_manifest.csv", "caiwangcun_source_tile_manifest.csv", "retrieval_candidate_id_audit.json"):
        src = gate_root / "plan" / name
        if src.exists():
            dst = experiment_root / "plan" / name
            copy_file_replace(src, dst, overwrite)
            copied.append({"kind": "file", "name": f"plan/{name}", "src": as_manifest_path(src), "dst": as_manifest_path(dst)})
    rewrite = rewrite_manifest_paths(experiment_root, gate_root, experiment_root)
    copy_script_snapshots(experiment_root)
    stale_hits = find_stale_root_references(experiment_root, gate_root)
    if stale_hits:
        raise SystemExit(f"stale gate-root references remain after path rewrite: {stale_hits[:10]}")
    return {
        "copied": copied,
        "path_rewrite": rewrite,
        "stale_gate_reference_count": len(stale_hits),
        "generated_at_utc": utc_now(),
    }


def build_formal_inputs(args: argparse.Namespace, bundle_root: Path, experiment_root: Path, log_path: Path) -> None:
    retrieval_top20 = experiment_root / "retrieval" / "retrieval_top20.csv"
    tiles_csv = experiment_root / "candidate_library" / "tiles.csv"
    query_truth_tiles_csv = experiment_root / "query_truth" / "query_truth_tiles.csv"
    dsm_mosaic = experiment_root / "source_mosaic" / "caiwangcun_dsm_0p14m_epsg32650.tif"
    run_cmd(
        [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "build_formal_query_manifest.py"),
            "--bundle-root",
            str(bundle_root),
            "--query-manifest-csv",
            str(experiment_root / "query_inputs" / "query_manifest.csv"),
            "--selected-summary-csv",
            str(experiment_root / "selected_queries" / "selected_images_summary.csv"),
        ],
        log_path,
        args.dry_run,
    )
    run_cmd(
        [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "build_formal_candidate_manifest.py"),
            "--bundle-root",
            str(bundle_root),
            "--retrieval-top20-csv",
            str(retrieval_top20),
            "--tiles-csv",
            str(tiles_csv),
            "--query-truth-tiles-csv",
            str(query_truth_tiles_csv),
            "--query-truth-csv",
            str(experiment_root / "query_truth" / "query_truth.csv"),
        ],
        log_path,
        args.dry_run,
    )
    run_cmd(
        [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "build_candidate_dsm_cache.py"),
            "--bundle-root",
            str(bundle_root),
            "--dsm-source-name",
            "caiwangcun_dsm_0p14m_epsg32650",
            "--dsm-source-type",
            "finished_caiwangcun_dsm",
            "--dsm-asset-version-tag",
            "caiwangcun_fullreplace_domdsm_0p14m_epsg32650",
            "--upstream-dsm-path",
            str(dsm_mosaic),
            "--expand-margin-m",
            "250",
        ],
        log_path,
        args.dry_run,
    )
    if not args.dry_run:
        source_root = bundle_root / "dsm_cache" / "source"
        ensure_dir(source_root)
        shutil.copy2(dsm_mosaic, source_root / "caiwangcun_dsm_0p14m_epsg32650.tif")
        materialize_dsm_from_mosaic(
            bundle_root,
            bundle_root / "input" / "formal_dsm_manifest.csv",
            dsm_mosaic,
            args.target_crs,
        )
    run_cmd(
        [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "build_pose_manifest.py"),
            "--bundle-root",
            str(bundle_root),
            "--query-manifest-csv",
            str(bundle_root / "input" / "formal_query_manifest.csv"),
            "--dom-manifest-csv",
            str(bundle_root / "input" / "formal_candidate_manifest.csv"),
            "--dsm-manifest-csv",
            str(bundle_root / "input" / "formal_dsm_manifest.csv"),
            "--coarse-topk-csv",
            str(retrieval_top20),
        ],
        log_path,
        args.dry_run,
    )


def summarize_acceptance(experiment_root: Path, gate_root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    bundle_root = experiment_root / "pose_v1_formal"
    suite_root = bundle_root / "eval_pose_validation_suite_caiwangcun_truth"
    dsm_summary = load_json(bundle_root / "dsm_cache" / "rasters" / "_summary.json")
    input_summary = load_json(bundle_root / "manifest" / "input_summary.json")
    pose_summary = load_json(bundle_root / "summary" / "pose_overall_summary.json")
    validation_summary_path = suite_root / "full_run_summary.json"
    frame_summary_path = suite_root / "ortho_alignment" / "frame_sanity" / "overall_frame_sanity.json"
    validation_summary = load_json(validation_summary_path) if validation_summary_path.exists() else {}
    frame_summary = load_json(frame_summary_path) if frame_summary_path.exists() else {}
    per_query_best = load_csv(bundle_root / "summary" / "per_query_best_pose.csv")
    failure_rows: list[dict[str, str]] = []
    for row in per_query_best:
        if row.get("best_status") != "ok":
            failure_rows.append(
                {
                    "query_id": row.get("query_id", ""),
                    "failure_bucket": "pose_best_not_ok",
                    "detail": row.get("best_status", ""),
                }
            )
    if frame_summary_path.exists():
        frame_rows = load_csv(suite_root / "ortho_alignment" / "frame_sanity" / "per_query_frame_sanity.csv")
        for row in frame_rows:
            if row.get("diagnosis") not in ("ok_or_manual_review", "single_view_coverage_limited"):
                failure_rows.append(
                    {
                        "query_id": row.get("query_id", ""),
                        "failure_bucket": row.get("diagnosis", "frame_sanity"),
                        "detail": row.get("diagnosis_detail", ""),
                    }
                )
    payload = {
        "experiment_root": as_manifest_path(experiment_root),
        "gate_root": as_manifest_path(gate_root),
        "candidate_tile_count": count_csv_rows(experiment_root / "candidate_library" / "tiles.csv"),
        "candidate_feature_status_count": count_csv_rows(experiment_root / "candidate_features" / "caiwangcun_tile_dinov2_status.csv"),
        "faiss_mapping_count": faiss_mapping_count(experiment_root / "faiss" / "caiwangcun_tiles_ip_mapping.json"),
        "retrieval_top20_rows": count_csv_rows(experiment_root / "retrieval" / "retrieval_top20.csv"),
        "input_summary": input_summary,
        "dsm_summary": dsm_summary,
        "pose_overall_summary": pose_summary,
        "validation_summary_path": as_manifest_path(validation_summary_path),
        "validation_pipeline_status": validation_summary.get("pipeline_status"),
        "validation_query_count": validation_summary.get("query_count"),
        "frame_sanity_summary_path": as_manifest_path(frame_summary_path),
        "frame_sanity_diagnosis_counts": frame_summary.get("diagnosis_counts", {}),
        "failure_bucket_count": len(failure_rows),
        "generated_at_utc": utc_now(),
    }
    return payload, failure_rows


def write_failure_buckets(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        rows = [{"query_id": "", "failure_bucket": "none", "detail": ""}]
    write_csv(path, rows, ["query_id", "failure_bucket", "detail"])


def faiss_mapping_count(path: Path) -> int:
    payload = load_json(path)
    for key in ("ids", "id_list", "items", "mapping", "index_to_id"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return len(value)
    return len(payload)


def main() -> None:
    args = parse_args()
    gate_root = resolve_runtime_path(args.gate_root)
    experiment_root = resolve_runtime_path(args.experiment_root)
    bundle_root = experiment_root / "pose_v1_formal"
    suite_root = bundle_root / "eval_pose_validation_suite_caiwangcun_truth"
    log_path = experiment_root / "logs" / "fullreplace_full.log"

    if experiment_root == gate_root:
        raise SystemExit("full run experiment root must not equal gate root")
    if experiment_root.exists() and args.overwrite and not args.skip_materialize:
        shutil.rmtree(experiment_root)

    preflight = check_required_gate_assets(gate_root)
    preflight["runtime_environment"] = check_runtime_environment()
    ensure_dir(experiment_root / "plan")

    if not args.skip_materialize:
        materialize = materialize_full_root(gate_root, experiment_root, args.overwrite)
        write_json(experiment_root / "plan" / "full_asset_reuse_audit.json", materialize)
    else:
        stale_hits = find_stale_root_references(experiment_root, gate_root)
        if stale_hits:
            raise SystemExit(f"stale gate-root references exist: {stale_hits[:10]}")
    write_json(experiment_root / "plan" / "full_preflight_audit.json", preflight)

    if not args.skip_pose:
        build_formal_inputs(args, bundle_root, experiment_root, log_path)
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "run_formal_pose_v1_pipeline.py"),
                "--bundle-root",
                str(bundle_root),
                "--phase",
                "full",
                "--sample-count",
                str(args.pose_sample_count),
                "--device",
                args.device,
                "--skip-dsm-build",
            ],
            log_path,
            args.dry_run,
        )

    if not args.skip_validation:
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "run_pose_validation_suite.py"),
                "--bundle-root",
                str(bundle_root),
                "--query-seed-csv",
                str(experiment_root / "query_truth" / "queries_truth_seed.csv"),
                "--phase",
                "full",
                "--target-resolution-m",
                str(args.target_resolution_m),
                "--crop-margin-m",
                str(args.crop_margin_m),
                "--block-size",
                str(args.block_size),
                "--flight-asset-manifest",
                str(experiment_root / "plan" / "caiwangcun_asset_manifest.csv"),
                "--output-root",
                str(suite_root),
                "--overwrite",
            ],
            log_path,
            args.dry_run,
        )
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "diagnose_pose_frame_sanity.py"),
                "--bundle-root",
                str(bundle_root),
                "--suite-root",
                str(suite_root),
                "--output-root",
                str(suite_root / "ortho_alignment" / "frame_sanity"),
            ],
            log_path,
            args.dry_run,
        )

    if not args.dry_run and not args.skip_pose:
        acceptance, failure_rows = summarize_acceptance(experiment_root, gate_root)
        write_json(experiment_root / "plan" / "full_acceptance_summary.json", acceptance)
        write_failure_buckets(experiment_root / "plan" / "full_failure_buckets.csv", failure_rows)

    if not args.skip_report:
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "generate_caiwangcun_fullreplace_full_report.py"),
                "--experiment-root",
                str(experiment_root),
                "--gate-root",
                str(gate_root),
            ],
            log_path,
            args.dry_run,
        )

    write_json(
        experiment_root / "plan" / "run_full_summary.json",
        {
            "experiment_root": as_manifest_path(experiment_root),
            "gate_root": as_manifest_path(gate_root),
            "bundle_root": as_manifest_path(bundle_root),
            "full_pose_summary": as_manifest_path(bundle_root / "summary" / "pose_overall_summary.json"),
            "full_validation_summary": as_manifest_path(suite_root / "full_run_summary.json"),
            "frame_sanity_summary": as_manifest_path(suite_root / "ortho_alignment" / "frame_sanity" / "overall_frame_sanity.json"),
            "acceptance_summary": as_manifest_path(experiment_root / "plan" / "full_acceptance_summary.json"),
            "generated_at_utc": utc_now(),
        },
    )


if __name__ == "__main__":
    main()

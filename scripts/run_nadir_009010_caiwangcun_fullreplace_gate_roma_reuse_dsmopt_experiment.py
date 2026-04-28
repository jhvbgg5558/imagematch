#!/usr/bin/env python3
"""Run the CaiWangCun gate with RoMa match reuse and parallel DSM sampling.

Purpose:
- start from the accepted CaiWangCun DOM/DSM full-replacement gate assets;
- rerun RoMa v2 rerank while saving point-level matches for pose-v1;
- skip the second formal-pose RoMa export and use parallel DSM sampling with
  detailed timing.

Main inputs:
- the completed CaiWangCun full-replacement gate root;
- CaiWangCun candidate library, query assets, retrieval inputs, and DOM/DSM
  mosaics from that gate;
- project scripts under `scripts/`.

Main outputs:
- an isolated optimized gate under
  `new3output/nadir_009010_caiwangcun_domdsm_fullreplace_gate_roma_reuse_parallel_dsm_timing_2026-04-27`;
- reusable RoMa point matches, formal pose gate outputs, validation outputs,
  and timing/audit JSON files.

Applicable task constraints:
- query images have no runtime geolocation metadata and are not guaranteed to
  be orthophotos;
- runtime retrieval and pose do not use truth to choose candidates;
- this experiment changes execution reuse/parallelism only, not RoMa ranking,
  DSM sampling rules, or PnP scoring.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
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
    write_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE_ROOT = (
    PROJECT_ROOT / "new3output" / "nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20"
)
DEFAULT_EXPERIMENT_ROOT = (
    PROJECT_ROOT
    / "new3output"
    / "nadir_009010_caiwangcun_domdsm_fullreplace_gate_roma_reuse_parallel_dsm_timing_2026-04-27"
)
DEFAULT_PYTHON_BIN = str(PROJECT_ROOT / ".conda" / "bin" / "python") if os.name != "nt" else sys.executable
GATE_QUERY_IDS = ("q_001", "q_021", "q_002", "q_003", "q_004")

COPY_DIRS = (
    "selected_queries",
    "query_inputs",
    "query_features",
    "query_truth",
    "source_mosaic",
    "candidate_library",
    "candidate_features",
    "faiss",
)

SCRIPT_SNAPSHOT_NAMES = (
    "run_nadir_009010_caiwangcun_fullreplace_gate_roma_reuse_dsmopt_experiment.py",
    "rerank_with_romav2_intersection.py",
    "run_romav2_rerank_intersection_round.py",
    "merge_romav2_pose_matches.py",
    "run_formal_pose_v1_pipeline.py",
    "sample_dsm_for_dom_points.py",
    "build_formal_query_manifest.py",
    "build_formal_candidate_manifest.py",
    "build_candidate_dsm_cache.py",
    "build_pose_manifest.py",
    "run_pose_validation_suite.py",
    "diagnose_pose_frame_sanity.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-root", default=str(DEFAULT_GATE_ROOT))
    parser.add_argument("--experiment-root", default=str(DEFAULT_EXPERIMENT_ROOT))
    parser.add_argument("--python-bin", default=DEFAULT_PYTHON_BIN)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--romav2-sample-count", type=int, default=5000)
    parser.add_argument("--pose-sample-count", type=int, default=5000)
    parser.add_argument("--dsm-workers", type=int, default=4)
    parser.add_argument("--target-crs", default="EPSG:32650")
    parser.add_argument("--target-resolution-m", type=float, default=0.14)
    parser.add_argument("--crop-margin-m", type=float, default=80.0)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-rerank", action="store_true")
    parser.add_argument("--skip-pose", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
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


def replace_text_in_file(path: Path, old_root: Path, new_root: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return False
    old_variants = {as_manifest_path(old_root), str(old_root).replace("/", "\\")}
    changed = False
    for old in old_variants:
        if old in text:
            text = text.replace(old, as_manifest_path(new_root))
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
                "source_path": as_manifest_path(src),
                "snapshot_path": as_manifest_path(dst),
                "sha256": sha256_file(src),
                "copied_at_utc": utc_now(),
            }
        )
    write_json(snapshot_root / "script_manifest.json", {"scripts": rows})


def materialize_experiment_root(gate_root: Path, experiment_root: Path, overwrite: bool) -> dict[str, Any]:
    ensure_dir(experiment_root / "plan")
    copied: list[dict[str, str]] = []
    for dirname in COPY_DIRS:
        src = gate_root / dirname
        dst = experiment_root / dirname
        copytree_replace(src, dst, overwrite)
        copied.append({"kind": "dir", "name": dirname, "src": as_manifest_path(src), "dst": as_manifest_path(dst)})

    src_romav2 = gate_root / "romav2_rerank"
    dst_romav2 = experiment_root / "romav2_rerank"
    for dirname in ("coarse", "input_round"):
        copytree_replace(src_romav2 / dirname, dst_romav2 / dirname, overwrite)
        copied.append(
            {
                "kind": "dir",
                "name": f"romav2_rerank/{dirname}",
                "src": as_manifest_path(src_romav2 / dirname),
                "dst": as_manifest_path(dst_romav2 / dirname),
            }
        )

    plan_src = gate_root / "plan"
    for name in ("caiwangcun_asset_manifest.csv", "caiwangcun_source_tile_manifest.csv", "retrieval_candidate_id_audit.json"):
        src = plan_src / name
        if src.exists():
            dst = experiment_root / "plan" / name
            ensure_dir(dst.parent)
            shutil.copy2(src, dst)
            copied.append({"kind": "file", "name": f"plan/{name}", "src": as_manifest_path(src), "dst": as_manifest_path(dst)})

    formal_query_src = gate_root / "pose_v1_formal" / "input" / "formal_query_manifest.csv"
    if formal_query_src.exists():
        formal_query_dst = experiment_root / "pose_v1_formal" / "input" / "formal_query_manifest.csv"
        ensure_dir(formal_query_dst.parent)
        shutil.copy2(formal_query_src, formal_query_dst)
        copied.append(
            {
                "kind": "file",
                "name": "pose_v1_formal/input/formal_query_manifest.csv",
                "src": as_manifest_path(formal_query_src),
                "dst": as_manifest_path(formal_query_dst),
            }
        )

    rewrite = rewrite_manifest_paths(experiment_root, gate_root, experiment_root)
    copy_script_snapshots(experiment_root)
    return {"copied": copied, "path_rewrite": rewrite, "generated_at_utc": utc_now()}


def run_timed(command: list[str], log_path: Path, dry_run: bool) -> dict[str, Any]:
    started = time.perf_counter()
    run_cmd(command, log_path, dry_run)
    return {"command": command, "elapsed_seconds": time.perf_counter() - started}


def build_formal_inputs(args: argparse.Namespace, bundle_root: Path, experiment_root: Path, log_path: Path) -> None:
    retrieval_top20 = experiment_root / "retrieval" / "retrieval_top20.csv"
    tiles_csv = experiment_root / "candidate_library" / "tiles.csv"
    query_truth_tiles_csv = experiment_root / "query_truth" / "query_truth_tiles.csv"
    dsm_mosaic = experiment_root / "source_mosaic" / "caiwangcun_dsm_0p14m_epsg32650.tif"
    formal_query_manifest = bundle_root / "input" / "formal_query_manifest.csv"
    if not formal_query_manifest.exists():
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


def summarize_gate(experiment_root: Path, timing_steps: list[dict[str, Any]]) -> dict[str, Any]:
    bundle_root = experiment_root / "pose_v1_formal"
    phase_summary_path = bundle_root / "summary" / "phase_gate_summary.json"
    sampling_summary_path = bundle_root / "sampling" / "sampling_summary.json"
    reuse_summary_path = bundle_root / "matches" / "roma_match_reuse_summary.json"
    pose_summary = load_json(phase_summary_path) if phase_summary_path.exists() else {}
    sampling_summary = load_json(sampling_summary_path) if sampling_summary_path.exists() else {}
    reuse_summary = load_json(reuse_summary_path) if reuse_summary_path.exists() else {}
    return {
        "experiment_root": as_manifest_path(experiment_root),
        "gate_root": as_manifest_path(DEFAULT_GATE_ROOT),
        "gate_query_ids": list(GATE_QUERY_IDS),
        "retrieval_top20_rows": count_csv_rows(experiment_root / "retrieval" / "retrieval_top20.csv"),
        "reused_match_rows": reuse_summary.get("row_count"),
        "pose_matches_rows": count_csv_rows(bundle_root / "matches" / "roma_matches.csv"),
        "correspondence_rows": count_csv_rows(bundle_root / "correspondences" / "pose_correspondences.csv"),
        "sampled_rows": count_csv_rows(bundle_root / "sampling" / "sampled_correspondences.csv"),
        "pnp_rows": count_csv_rows(bundle_root / "pnp" / "pnp_results.csv"),
        "sampling_status_counts": sampling_summary.get("status_counts", {}),
        "sampling_elapsed_seconds": sampling_summary.get("elapsed_seconds"),
        "sampling_rows_per_second": sampling_summary.get("rows_per_second"),
        "dsm_worker_count": sampling_summary.get("worker_count"),
        "pose_stage_names": [stage.get("stage") for stage in pose_summary.get("stages", [])],
        "timing_steps": timing_steps,
        "generated_at_utc": utc_now(),
    }


def main() -> None:
    args = parse_args()
    gate_root = resolve_runtime_path(args.gate_root)
    experiment_root = resolve_runtime_path(args.experiment_root)
    bundle_root = experiment_root / "pose_v1_formal"
    log_path = experiment_root / "logs" / "roma_reuse_parallel_dsm_gate.log"
    timing_steps: list[dict[str, Any]] = []

    if experiment_root == gate_root:
        raise SystemExit("optimized experiment root must not equal the source gate root")
    if experiment_root.exists() and args.overwrite:
        shutil.rmtree(experiment_root)
    ensure_dir(experiment_root / "plan")
    materialize = materialize_experiment_root(gate_root, experiment_root, args.overwrite)
    write_json(experiment_root / "plan" / "asset_reuse_audit.json", materialize)

    romav2_root = experiment_root / "romav2_rerank"
    retrieval_top20 = experiment_root / "retrieval" / "retrieval_top20.csv"
    if not args.skip_rerank:
        rerank_cmd = [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "run_romav2_rerank_intersection_round.py"),
            "--input-round-root",
            str(romav2_root / "input_round"),
            "--tiles-csv",
            str(experiment_root / "candidate_library" / "tiles.csv"),
            "--out-root",
            str(romav2_root),
            "--top-k",
            str(args.top_k),
            "--python-bin",
            args.python_bin,
            "--device",
            args.device,
            "--sample-count",
            str(args.romav2_sample_count),
            "--ranking-mode",
            "inlier_count_only",
            "--timing-json",
            str(romav2_root / "timing" / "romav2_rerank_internal.json"),
        ]
        for query_id in GATE_QUERY_IDS:
            rerank_cmd.extend(["--query-id", query_id])
        timing_steps.append(
            {"stage": "romav2_rerank_with_pose_matches"}
            | run_timed(rerank_cmd, log_path, args.dry_run)
        )
        timing_steps.append(
            {"stage": "export_reranked_for_pose"}
            | run_timed(
                [
                    args.python_bin,
                    str(PROJECT_ROOT / "scripts" / "export_romav2_reranked_for_pose.py"),
                    "--stage7-root",
                    str(romav2_root / "stage7"),
                    "--out-csv",
                    str(retrieval_top20),
                    "--top-k",
                    str(args.top_k),
                ],
                log_path,
                args.dry_run,
            )
        )

    if not args.skip_pose:
        if not retrieval_top20.exists() and not args.dry_run:
            raise SystemExit(f"missing retrieval top20 CSV: {retrieval_top20}")
        build_formal_inputs(args, bundle_root, experiment_root, log_path)
        merge_cmd = [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "merge_romav2_pose_matches.py"),
            "--stage7-root",
            str(romav2_root / "stage7"),
            "--out-csv",
            str(bundle_root / "matches" / "roma_matches.csv"),
            "--summary-json",
            str(bundle_root / "matches" / "roma_match_reuse_summary.json"),
            "--top-k",
            str(args.top_k),
        ]
        for query_id in GATE_QUERY_IDS:
            merge_cmd.extend(["--query-id", query_id])
        timing_steps.append({"stage": "merge_reused_pose_matches"} | run_timed(merge_cmd, log_path, args.dry_run))
        timing_steps.append(
            {"stage": "formal_pose_gate_reuse_matches_parallel_dsm"}
            | run_timed(
                [
                    args.python_bin,
                    str(PROJECT_ROOT / "scripts" / "run_formal_pose_v1_pipeline.py"),
                    "--bundle-root",
                    str(bundle_root),
                    "--phase",
                    "sample",
                    "--sample-query-count",
                    str(len(GATE_QUERY_IDS)),
                    "--sample-count",
                    str(args.pose_sample_count),
                    "--device",
                    args.device,
                    "--skip-dsm-build",
                    "--reuse-match-csv",
                    str(bundle_root / "matches" / "roma_matches.csv"),
                    "--dsm-workers",
                    str(args.dsm_workers),
                ],
                log_path,
                args.dry_run,
            )
        )

    suite_root = bundle_root / "eval_pose_validation_suite_caiwangcun_truth"
    if not args.skip_validation:
        timing_steps.append(
            {"stage": "validation_gate"}
            | run_timed(
                [
                    args.python_bin,
                    str(PROJECT_ROOT / "scripts" / "run_pose_validation_suite.py"),
                    "--bundle-root",
                    str(bundle_root),
                    "--query-seed-csv",
                    str(experiment_root / "query_truth" / "queries_truth_seed.csv"),
                    "--phase",
                    "gate",
                    "--gate-count",
                    str(len(GATE_QUERY_IDS)),
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
        )
        timing_steps.append(
            {"stage": "frame_sanity"}
            | run_timed(
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
        )

    if not args.dry_run:
        write_json(experiment_root / "plan" / "run_gate_summary.json", summarize_gate(experiment_root, timing_steps))
    else:
        write_json(
            experiment_root / "plan" / "run_gate_summary.json",
            {
                "experiment_root": as_manifest_path(experiment_root),
                "dry_run": True,
                "timing_steps": timing_steps,
                "generated_at_utc": utc_now(),
            },
        )


if __name__ == "__main__":
    main()

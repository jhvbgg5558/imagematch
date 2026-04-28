#!/usr/bin/env python3
"""Run the 009/010 nadir-query DINOv2+RoMa v2 pose experiment.

Purpose:
- orchestrate the new 009/010 near-nadir query experiment under one isolated
  `new2output` root;
- reuse the existing DINOv2 fixed satellite library and FAISS index while
  regenerating query-side assets, RoMa rerank outputs, DOM/DSM/PnP pose
  outputs, and the validation suite;
- copy the experiment-specific scripts into the experiment root for audit.

Main inputs:
- raw UAV flights 009 and 010 under `D:/数据/武汉影像/无人机0.1m`;
- existing DINOv2 fixed satellite library, FAISS index, and mapping assets.

Main outputs:
- all experiment assets under
  `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10`;
- script snapshots under `<experiment-root>/scripts`.

Applicable task constraints:
- no output is written to `new2output/pose_v1_formal`;
- query metadata is used only for offline selection and truth construction;
- runtime retrieval uses sanitized query images and fixed candidate DOM assets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT_ROOT = PROJECT_ROOT / "new2output" / "nadir_009010_dinov2_romav2_pose_2026-04-10"
DEFAULT_RAW_UAV_ROOT = Path("D:/数据/武汉影像/无人机0.1m")
DEFAULT_BASELINE_DIR = PROJECT_ROOT / "output" / "coverage_truth_200_300_500_700_dinov2_baseline"
DEFAULT_TILES_CSV = DEFAULT_BASELINE_DIR / "fixed_satellite_library" / "tiles.csv"
DEFAULT_FAISS_INDEX = DEFAULT_BASELINE_DIR / "faiss" / "satellite_tiles_ip.index"
DEFAULT_MAPPING_JSON = DEFAULT_BASELINE_DIR / "faiss" / "satellite_tiles_ip_mapping.json"
DEFAULT_SOURCE_HGT = PROJECT_ROOT / "new2output" / "N30E114.hgt"

NEW_SCRIPT_NAMES = (
    "select_nadir_uav_queries.py",
    "export_romav2_reranked_for_pose.py",
    "run_nadir_009010_pose_experiment.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-root", default=str(DEFAULT_EXPERIMENT_ROOT))
    parser.add_argument("--raw-uav-root", default=str(DEFAULT_RAW_UAV_ROOT))
    parser.add_argument("--phase", choices=("gate", "full"), default="gate")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-query-prep", action="store_true")
    parser.add_argument("--skip-retrieval", action="store_true")
    parser.add_argument("--skip-pose", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--romav2-sample-count", type=int, default=5000)
    parser.add_argument("--pose-sample-count", type=int, default=2000)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def resolve_runtime_path(path: str | Path) -> Path:
    text = str(path)
    if os.name != "nt" and len(text) >= 3 and text[1:3] in {":\\", ":/"}:
        drive = text[0].lower()
        rest = text[3:].replace("\\", "/")
        return Path(f"/mnt/{drive}/{rest}")
    if os.name == "nt" and text.startswith("/mnt/") and len(text) > 6:
        drive = text[5].upper()
        rest = text[7:].replace("/", "\\")
        return Path(f"{drive}:\\{rest}")
    return Path(text)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def run_cmd(cmd: list[str], log_path: Path, dry_run: bool) -> None:
    ensure_dir(log_path.parent)
    line = " ".join(cmd)
    print("+", line)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n[{utc_now()}] + {line}\n")
    if dry_run:
        return
    with log_path.open("a", encoding="utf-8") as log:
        subprocess.run(cmd, cwd=PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT, text=True, check=True)


def copy_script_snapshots(experiment_root: Path) -> None:
    scripts_root = experiment_root / "scripts"
    ensure_dir(scripts_root)
    rows: list[dict[str, object]] = []
    for name in NEW_SCRIPT_NAMES:
        src = PROJECT_ROOT / "scripts" / name
        dst = scripts_root / name
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
    write_json(scripts_root / "script_manifest.json", {"scripts": rows})


def validate_query_gate(selected_csv: Path, manifest_csv: Path) -> dict[str, object]:
    with selected_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        selected = list(csv.DictReader(handle))
    with manifest_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        manifest = list(csv.DictReader(handle))
    flight_counts: dict[str, int] = {}
    for row in selected:
        flight_counts[row["flight_id"]] = flight_counts.get(row["flight_id"], 0) + 1
    pitch_bad = [row for row in selected if float(row["gimbal_pitch_degree"]) > -85.0]
    if len(selected) != 40:
        raise SystemExit(f"selected query count must be 40, got {len(selected)}")
    if sorted(flight_counts.values()) != [20, 20]:
        raise SystemExit(f"expected two flights with 20 rows each, got {flight_counts}")
    if pitch_bad:
        raise SystemExit(f"found selected rows with pitch > -85: {len(pitch_bad)}")
    if len(manifest) != 40:
        raise SystemExit(f"query manifest count must be 40, got {len(manifest)}")
    return {"selected_count": len(selected), "manifest_count": len(manifest), "flight_counts": flight_counts}


def main() -> None:
    args = parse_args()
    experiment_root = resolve_runtime_path(args.experiment_root)
    raw_uav_root = resolve_runtime_path(args.raw_uav_root)
    forbidden_root = (PROJECT_ROOT / "new2output" / "pose_v1_formal").resolve()
    if is_relative_to(experiment_root, forbidden_root):
        raise SystemExit(f"refusing to write into existing formal root: {forbidden_root}")
    pose_root = experiment_root / "pose_v1_formal"
    logs_root = experiment_root / "logs"
    ensure_dir(experiment_root)
    for name in [
        "selected_queries",
        "query_inputs",
        "query_truth",
        "query_features",
        "retrieval",
        "romav2_rerank",
        "reports",
        "plan",
        "logs",
    ]:
        ensure_dir(experiment_root / name)
    copy_script_snapshots(experiment_root)
    write_json(
        experiment_root / "plan" / "experiment_contract.json",
        {
            "experiment_root": str(experiment_root),
            "formal_query_policy": {
                "flight_ids": [
                    "DJI_202510311347_009_新建面状航线1",
                    "DJI_202510311413_010_新建面状航线1",
                ],
                "per_flight_count": 20,
                "pitch_rule": "gimbal_pitch_degree <= -85.0",
                "query_id_order": "009 rows become q_001..q_020; 010 rows become q_021..q_040",
            },
            "runtime_candidate_policy": {
                "coarse_retrieval": "DINOv2 query features searched against the reused fixed satellite FAISS index",
                "rerank": "RoMa v2 inlier_count_only over DINOv2 Top-20",
                "truth_usage": "query truth CSVs are passed to RoMa/evaluation scripts only for labels, summaries, and reports; they are not used to construct runtime FAISS candidates",
                "pose_score_source": "RoMa reranked fused_score exported as build_formal_candidate_manifest score",
            },
            "path_isolation": {
                "forbidden_write_root": str(forbidden_root),
                "allowed_experiment_root": str(experiment_root),
                "read_only_reused_assets": [
                    str(DEFAULT_TILES_CSV),
                    str(DEFAULT_FAISS_INDEX),
                    str(DEFAULT_MAPPING_JSON),
                    str(DEFAULT_SOURCE_HGT),
                ],
            },
            "generated_at_utc": utc_now(),
        },
    )

    run_log = logs_root / f"run_{args.phase}.log"
    py = args.python_bin
    selected_csv = experiment_root / "selected_queries" / "selected_images_summary.csv"
    query_manifest = experiment_root / "query_inputs" / "query_manifest.csv"
    query_seed = experiment_root / "query_truth" / "queries_truth_seed.csv"
    query_truth_tiles = experiment_root / "query_truth" / "query_truth_tiles.csv"
    query_features = experiment_root / "query_features" / "query_dinov2_pooler.npz"
    query_features_status = experiment_root / "query_features" / "query_dinov2_pooler_status.csv"
    romav2_root = experiment_root / "romav2_rerank"
    retrieval_top20 = experiment_root / "retrieval" / "retrieval_top20.csv"

    if not args.skip_query_prep:
        select_cmd = [
            py,
            "scripts/select_nadir_uav_queries.py",
            "--input-root",
            str(raw_uav_root),
            "--output-root",
            str(experiment_root),
            "--per-flight-count",
            "20",
            "--pitch-max",
            "-85",
        ]
        if args.overwrite:
            select_cmd.append("--overwrite")
        run_cmd(select_cmd, run_log, args.dry_run)
        run_cmd(
            [
                py,
                "scripts/sanitize_query_images.py",
                "--selected-query-csv",
                str(selected_csv),
                "--out-dir",
                str(experiment_root / "query_inputs" / "images"),
                "--manifest-csv",
                str(query_manifest),
            ],
            run_log,
            args.dry_run,
        )
        run_cmd(
            [
                py,
                "scripts/generate_query_truth_from_coverage_v2.py",
                "--selected-query-csv",
                str(selected_csv),
                "--tile-metadata-csv",
                str(DEFAULT_TILES_CSV),
                "--out-dir",
                str(experiment_root / "query_truth"),
            ],
            run_log,
            args.dry_run,
        )
        if not args.dry_run:
            gate = validate_query_gate(selected_csv, query_manifest)
            write_json(experiment_root / "plan" / "query_gate_summary.json", gate)

    if not args.skip_retrieval:
        run_cmd(
            [
                py,
                "scripts/extract_dino_features.py",
                "--input-csv",
                str(query_manifest),
                "--id-column",
                "query_id",
                "--image-column",
                "sanitized_query_path",
                "--output-npz",
                str(query_features),
                "--output-csv",
                str(query_features_status),
                "--model-name",
                "facebook/dinov2-base",
                "--device",
                args.device,
            ],
            run_log,
            args.dry_run,
        )
        run_cmd(
            [
                py,
                "scripts/run_romav2_intersection_pipeline.py",
                "--baseline-result-dir",
                str(experiment_root),
                "--query-features-npz",
                str(query_features),
                "--query-seed-csv",
                str(query_seed),
                "--query-truth-tiles-csv",
                str(query_truth_tiles),
                "--faiss-index",
                str(DEFAULT_FAISS_INDEX),
                "--mapping-json",
                str(DEFAULT_MAPPING_JSON),
                "--query-manifest-csv",
                str(query_manifest),
                "--tiles-csv",
                str(DEFAULT_TILES_CSV),
                "--out-root",
                str(romav2_root),
                "--top-k",
                str(args.top_k),
                "--python-bin",
                py,
                "--device",
                args.device,
                "--sample-count",
                str(args.romav2_sample_count),
                "--ranking-mode",
                "inlier_count_only",
                "--coarse-model-label",
                "DINOv2",
            ],
            run_log,
            args.dry_run,
        )
        run_cmd(
            [
                py,
                "scripts/export_romav2_reranked_for_pose.py",
                "--stage7-root",
                str(romav2_root / "stage7"),
                "--out-csv",
                str(retrieval_top20),
                "--top-k",
                str(args.top_k),
            ],
            run_log,
            args.dry_run,
        )

    if not args.skip_pose:
        run_cmd(
            [
                py,
                "scripts/build_formal_query_manifest.py",
                "--bundle-root",
                str(pose_root),
                "--query-manifest-csv",
                str(query_manifest),
                "--selected-summary-csv",
                str(selected_csv),
            ],
            run_log,
            args.dry_run,
        )
        run_cmd(
            [
                py,
                "scripts/build_formal_candidate_manifest.py",
                "--bundle-root",
                str(pose_root),
                "--retrieval-top20-csv",
                str(retrieval_top20),
                "--tiles-csv",
                str(DEFAULT_TILES_CSV),
                "--query-truth-tiles-csv",
                str(query_truth_tiles),
                "--query-truth-csv",
                str(experiment_root / "query_truth" / "query_truth.csv"),
            ],
            run_log,
            args.dry_run,
        )
        run_cmd([py, "scripts/build_candidate_dsm_cache.py", "--bundle-root", str(pose_root)], run_log, args.dry_run)
        run_cmd(
            [
                py,
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
                py,
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
        run_cmd([py, "scripts/validate_pose_assets.py", "--bundle-root", str(pose_root)], run_log, args.dry_run)
        formal_args = [
            py,
            "scripts/run_formal_pose_v1_pipeline.py",
            "--bundle-root",
            str(pose_root),
            "--phase",
            "full" if args.phase == "full" else "sample",
            "--device",
            args.device,
            "--skip-dsm-build",
            "--sample-count",
            str(args.pose_sample_count),
            "--python-exe",
            py,
        ]
        if args.phase == "gate":
            formal_args.extend(["--sample-query-count", "5"])
        run_cmd(formal_args, run_log, args.dry_run)

    if not args.skip_validation:
        suite_root = pose_root / "eval_pose_validation_suite"
        validation_cmd = [
            py,
            "scripts/run_pose_validation_suite.py",
            "--bundle-root",
            str(pose_root),
            "--query-seed-csv",
            str(query_seed),
            "--phase",
            args.phase,
            "--output-root",
            str(suite_root),
        ]
        if args.overwrite:
            validation_cmd.append("--overwrite")
        run_cmd(validation_cmd, run_log, args.dry_run)
        run_cmd(
            [py, "scripts/render_pose_vs_at_figures.py", "--pose-root", str(suite_root / "pose_vs_at")],
            run_log,
            args.dry_run,
        )
        run_cmd(
            [
                py,
                "scripts/generate_pose_validation_suite_word_report.py",
                "--suite-root",
                str(suite_root),
            ],
            run_log,
            args.dry_run,
        )

    write_json(
        experiment_root / "plan" / f"run_{args.phase}_command_summary.json",
        {
            "phase": args.phase,
            "experiment_root": str(experiment_root),
            "dry_run": args.dry_run,
            "completed_at_utc": utc_now(),
            "path_isolation": "all generated outputs are under experiment_root except read-only reused baseline assets",
        },
    )
    print(experiment_root)


if __name__ == "__main__":
    main()

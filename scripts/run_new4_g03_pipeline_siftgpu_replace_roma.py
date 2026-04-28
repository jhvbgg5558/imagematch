#!/usr/bin/env python3
"""Run new4 G03 SIFTGPU replacement gate experiment.

Purpose:
- create the G03 experiment directory and plan;
- verify that true GPU SIFT/SIFTGPU matching is usable before the formal run;
- if available, run the CaiWangCun 5-query gate with SIFTGPU replacing RoMa v2
  while keeping G02 DOM+Z reuse, PnP, scoring, and validation logic.

Main inputs:
- G02 engineering pipeline outputs for comparison and environment probing;
- existing 009/010 query assets and CaiWangCun DOM/DSM source mosaics.

Main outputs:
- `new4output/.../G03_pipeline_siftgpu_replace_roma`;
- `实验计划.md`, `plan/siftgpu_env_check.json`, and summary JSON files.

Applicable task constraints:
- query images have no runtime geolocation metadata and are not assumed to be
  orthophotos;
- CPU SIFT is not accepted as a formal substitute for SIFTGPU in this group.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MATRIX_ROOT = PROJECT_ROOT / "new4output" / "nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27"
DEFAULT_EXPERIMENT_ROOT = MATRIX_ROOT / "G03_pipeline_siftgpu_replace_roma"
DEFAULT_G02_ROOT = MATRIX_ROOT / "G02_pipeline_engineering_reuse_domz_parallel_sampling"
DEFAULT_GATE_SCRIPT = PROJECT_ROOT / "scripts" / "run_nadir_009010_caiwangcun_fullreplace_gate_experiment.py"
DEFAULT_SEED_MOSAIC_ROOT = (
    PROJECT_ROOT
    / "new3output"
    / "nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20"
    / "source_mosaic"
)
GATE_QUERY_IDS = ["q_001", "q_021", "q_002", "q_003", "q_004"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-root", default=str(DEFAULT_EXPERIMENT_ROOT))
    parser.add_argument("--g02-root", default=str(DEFAULT_G02_ROOT))
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed-mosaic-root", default=str(DEFAULT_SEED_MOSAIC_ROOT))
    parser.add_argument("--domz-workers", type=int, default=4)
    parser.add_argument("--colmap-bin", default="colmap")
    parser.add_argument(
        "--siftgpu-bin",
        default=str(PROJECT_ROOT / "third_party" / "SiftGPU" / "bin" / "siftgpu_pair_match"),
    )
    parser.add_argument("--siftgpu-max-num-features", type=int, default=8192)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-run", action="store_true")
    parser.add_argument("--allow-env-failure", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def status_counts(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(Counter(row.get(field, "") for row in rows))


def write_plan_md(experiment_root: Path, g02_root: Path) -> None:
    plan = f"""# 第 3 组实验计划：第 2 组 + SIFTGPU 替代 RoMa v2

## Summary

- 实验组名：`G03_pipeline_siftgpu_replace_roma`
- 输出目录：`{experiment_root.as_posix()}`
- 对照组：`G02_pipeline_engineering_reuse_domz_parallel_sampling`
- Gate query：`{" / ".join(GATE_QUERY_IDS)}`
- 目标：在 G02 工程优化管线基础上，将 RoMa v2 几何匹配与重排全部替换为 SIFTGPU，直接比较速度、匹配质量和定位精度。

## Pipeline

- DINOv2 + FAISS 粗检索仍输出 Top-20。
- `prepare_romav2_intersection_inputs.py` 继续只作为通用 query/candidate shard 准备器。
- SIFTGPU rerank 输出 `siftgpu_rerank/stage7/<flight>/reranked_top20.csv`。
- SIFTGPU 同步输出 pose 点级匹配：`siftgpu_rerank/stage7/<flight>/siftgpu_matches_for_pose.csv`。
- Pose 阶段复用 SIFTGPU 点级匹配，不再执行 RoMa export。
- DOM+Z point cache、cache-based sampling、PnP、score、validation 继续沿用 G02。

## Environment Gate

- 正式 G03 必须通过 `plan/siftgpu_env_check.json`。
- 可接受后端：可执行 SiftGPU，或 COLMAP 的 GPU SIFT/SiftGPU 路径能完成两图 probe。
- CPU SIFT 只能作为诊断，不计入正式 G03。
- 如果环境失败，本组记录为环境阻断，不生成伪正式精度结论。

## Outputs

- `siftgpu_rerank/`
- `retrieval/`
- `pose_v1_formal/`
- `logs/`
- `plan/`
- `timing_summary.json`
- `accuracy_summary.json`
- `acceptance_summary.json`
- `compare_against_G02_summary.json`

## Acceptance

- 环境检查通过。
- best pose 输出 `5/5 ok`。
- retrieval Top-20 输出 `100` 行。
- PnP 输出 `100` 个 candidate 结果。
- validation pipeline 状态为 `ok`。
- 与 G02 对比 Layer-2、Layer-3 精度和关键耗时，明确回答 SIFTGPU 是否可以替代 RoMa v2。

## Current Baseline

- G02 根目录：`{g02_root.as_posix()}`
- 本组不引入降分辨率、Top-20 精简或打分口径变化。
"""
    (experiment_root / "实验计划.md").write_text(plan, encoding="utf-8")


def seed_source_mosaic(experiment_root: Path, seed_mosaic_root: Path) -> None:
    source_root = experiment_root / "source_mosaic"
    ensure_dir(source_root)
    for name in ("caiwangcun_ortho_0p14m_epsg32650.tif", "caiwangcun_dsm_0p14m_epsg32650.tif"):
        src = seed_mosaic_root / name
        dst = source_root / name
        if not src.exists():
            raise SystemExit(f"missing seed mosaic asset: {src}")
        if not dst.exists():
            shutil.copy2(src, dst)


def seed_source_tile_links(experiment_root: Path) -> Path:
    source_root = experiment_root / "source_mosaic"
    tile_root = experiment_root / "plan" / "seed_source_tiles"
    ensure_dir(tile_root)
    links = {
        "CaiWangCun-DOM_ortho_part_000_000.tif": source_root / "caiwangcun_ortho_0p14m_epsg32650.tif",
        "CaiWangCun-DOM_DSM_part_000_000.tif": source_root / "caiwangcun_dsm_0p14m_epsg32650.tif",
    }
    for name, target in links.items():
        link_path = tile_root / name
        if link_path.exists():
            continue
        try:
            link_path.symlink_to(target)
        except OSError:
            try:
                link_path.hardlink_to(target)
            except OSError:
                shutil.copy2(target, link_path)
    return tile_root


def first_probe_pair(g02_root: Path) -> tuple[str | None, str | None]:
    query_rows = load_csv(g02_root / "query_inputs" / "query_manifest.csv")
    retrieval_rows = load_csv(g02_root / "retrieval" / "retrieval_top20.csv")
    tile_rows = load_csv(g02_root / "candidate_library" / "tiles.csv")
    if not query_rows or not retrieval_rows or not tile_rows:
        return None, None
    query_by_id = {row["query_id"]: row for row in query_rows}
    tile_by_id = {row["tile_id"]: row for row in tile_rows}
    row = retrieval_rows[0]
    query = query_by_id.get(row["query_id"])
    tile = tile_by_id.get(row["candidate_tile_id"])
    if not query or not tile:
        return None, None
    return query.get("sanitized_query_path"), tile.get("image_path")


def run_env_check(args: argparse.Namespace, experiment_root: Path, g02_root: Path) -> dict[str, Any]:
    query_image, candidate_image = first_probe_pair(g02_root)
    out_json = experiment_root / "plan" / "siftgpu_env_check.json"
    cmd = [
        args.python_bin,
        str(PROJECT_ROOT / "scripts" / "check_siftgpu_environment.py"),
        "--out-json",
        str(out_json),
        "--colmap-bin",
        args.colmap_bin,
        "--siftgpu-bin",
        args.siftgpu_bin,
        "--max-num-features",
        str(args.siftgpu_max_num_features),
    ]
    if query_image and candidate_image:
        cmd.extend(["--query-image", query_image, "--candidate-image", candidate_image])
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)
    return load_json(out_json)


def write_env_blocked_outputs(experiment_root: Path, g02_root: Path, env: dict[str, Any]) -> None:
    payload = {
        "experiment_root": str(experiment_root),
        "g02_root": str(g02_root),
        "generated_at_utc": utc_now(),
        "accepted": False,
        "blocked_stage": "siftgpu_environment_check",
        "reason": "true SIFTGPU/COLMAP GPU SIFT is not usable in the current runtime",
        "siftgpu_env_check": "plan/siftgpu_env_check.json",
        "formal_cpu_fallback_allowed": False,
    }
    write_json(experiment_root / "acceptance_summary.json", payload)
    write_json(
        experiment_root / "timing_summary.json",
        {
            "experiment_root": str(experiment_root),
            "g02_root": str(g02_root),
            "generated_at_utc": utc_now(),
            "siftgpu_env_available": bool(env.get("available")),
            "formal_run_started": False,
        },
    )
    write_json(
        experiment_root / "accuracy_summary.json",
        {
            "experiment_root": str(experiment_root),
            "g02_root": str(g02_root),
            "generated_at_utc": utc_now(),
            "formal_accuracy_available": False,
            "reason": payload["reason"],
        },
    )
    write_json(
        experiment_root / "compare_against_G02_summary.json",
        {
            "experiment_root": str(experiment_root),
            "g02_root": str(g02_root),
            "generated_at_utc": utc_now(),
            "comparison_available": False,
            "reason": payload["reason"],
        },
    )


def run_g03(args: argparse.Namespace, experiment_root: Path) -> dict[str, Any]:
    seed_tile_root = seed_source_tile_links(experiment_root)
    command = [
        args.python_bin,
        str(DEFAULT_GATE_SCRIPT),
        "--experiment-root",
        str(experiment_root),
        "--caiwangcun-root",
        str(seed_tile_root),
        "--device",
        args.device,
        "--skip-mosaic",
        "--geometry-matcher",
        "siftgpu",
        "--colmap-bin",
        args.colmap_bin,
        "--siftgpu-bin",
        args.siftgpu_bin,
        "--siftgpu-max-num-features",
        str(args.siftgpu_max_num_features),
        "--romav2-export-pose-matches",
        "--reuse-rerank-pose-matches",
        "--domz-sampling",
        "--domz-workers",
        str(args.domz_workers),
    ]
    for query_id in GATE_QUERY_IDS:
        command.extend(["--rerank-query-id", query_id])
    if args.dry_run:
        command.append("--dry-run")
    log_path = experiment_root.parent / "G03_pipeline_siftgpu_replace_roma_wrapper.log"
    started = time.time()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_now()}] + {' '.join(command)}\n")
        completed = subprocess.run(command, cwd=PROJECT_ROOT, stdout=handle, stderr=subprocess.STDOUT, text=True)
    return {"command": command, "returncode": completed.returncode, "elapsed_seconds": time.time() - started, "log_path": str(log_path)}


def summarize_if_ran(experiment_root: Path, g02_root: Path, wrapper_run: dict[str, Any]) -> None:
    pose_root = experiment_root / "pose_v1_formal"
    validation_summary = load_json(pose_root / "eval_pose_validation_suite_caiwangcun_truth" / "phase_gate_summary.json")
    pnp_rows = load_csv(pose_root / "pnp" / "pnp_results.csv")
    best_rows = load_csv(pose_root / "summary" / "per_query_best_pose.csv")
    sampled_rows = load_csv(pose_root / "sampling" / "sampled_correspondences.csv")
    matches_rows = load_csv(pose_root / "matches" / "roma_matches.csv")
    pose_vs_at = validation_summary.get("overall_pose_vs_at", {})
    tiepoint = validation_summary.get("overall_tiepoint_ground_error", {})
    timing = load_json(experiment_root / "siftgpu_rerank" / "timing" / "siftgpu_rerank_internal.json")
    accuracy = {
        "experiment_root": str(experiment_root),
        "g02_root": str(g02_root),
        "generated_at_utc": utc_now(),
        "retrieval_top20_rows": len(load_csv(experiment_root / "retrieval" / "retrieval_top20.csv")),
        "matches_row_count": len(matches_rows),
        "sampling_row_count": len(sampled_rows),
        "sampling_status_counts": status_counts(sampled_rows, "sample_status"),
        "pnp_row_count": len(pnp_rows),
        "pnp_status_counts": status_counts(pnp_rows, "status"),
        "best_pose_status_counts": status_counts(best_rows, "best_status"),
        "validation_pipeline_status": validation_summary.get("pipeline_status"),
        "layer2_horizontal_error_m_mean": pose_vs_at.get("horizontal_error_m", {}).get("mean") or pose_vs_at.get("numeric_summaries", {}).get("horizontal_error_m", {}).get("mean"),
        "layer3_tiepoint_xy_error_rmse_m": tiepoint.get("tiepoint_xy_error_rmse_m"),
    }
    write_json(experiment_root / "accuracy_summary.json", accuracy)
    write_json(
        experiment_root / "timing_summary.json",
        {
            "experiment_root": str(experiment_root),
            "g02_root": str(g02_root),
            "generated_at_utc": utc_now(),
            "wrapper_elapsed_seconds": wrapper_run.get("elapsed_seconds"),
            "siftgpu_rerank_elapsed_seconds": timing.get("elapsed_seconds"),
            "pose_export_romav2_matches_seconds": 0.0,
            "siftgpu_rerank_timing": timing,
        },
    )
    g02_accuracy = load_json(g02_root / "accuracy_summary.json")
    write_json(
        experiment_root / "compare_against_G02_summary.json",
        {
            "experiment_root": str(experiment_root),
            "g02_root": str(g02_root),
            "generated_at_utc": utc_now(),
            "g03_accuracy": accuracy,
            "g02_accuracy": g02_accuracy,
        },
    )
    checks = {
        "wrapper_returncode_zero": wrapper_run.get("returncode") == 0,
        "retrieval_top20_rows_100": accuracy["retrieval_top20_rows"] == 100,
        "pnp_row_count_100": accuracy["pnp_row_count"] == 100,
        "best_pose_5_of_5_ok": accuracy["best_pose_status_counts"].get("ok") == 5,
        "validation_pipeline_ok": accuracy["validation_pipeline_status"] == "ok",
    }
    write_json(
        experiment_root / "acceptance_summary.json",
        {
            "experiment_root": str(experiment_root),
            "g02_root": str(g02_root),
            "generated_at_utc": utc_now(),
            "checks": checks,
            "accepted": all(checks.values()),
        },
    )


def main() -> None:
    args = parse_args()
    experiment_root = Path(args.experiment_root)
    g02_root = Path(args.g02_root)
    if args.overwrite and experiment_root.exists():
        shutil.rmtree(experiment_root)
    ensure_dir(experiment_root)
    write_plan_md(experiment_root, g02_root)
    seed_source_mosaic(experiment_root, Path(args.seed_mosaic_root))
    env = run_env_check(args, experiment_root, g02_root)
    if not env.get("available") and not args.allow_env_failure:
        write_env_blocked_outputs(experiment_root, g02_root, env)
        print(experiment_root)
        return
    wrapper_run = None
    if not args.skip_run:
        wrapper_run = run_g03(args, experiment_root)
        if int(wrapper_run["returncode"]) != 0:
            write_json(experiment_root / "wrapper_failed_summary.json", wrapper_run)
            raise SystemExit(int(wrapper_run["returncode"]))
    if wrapper_run is not None and not args.dry_run:
        summarize_if_ran(experiment_root, g02_root, wrapper_run)
    print(experiment_root)


if __name__ == "__main__":
    main()

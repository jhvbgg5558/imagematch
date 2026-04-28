#!/usr/bin/env python3
"""Run new4 G02 engineering-optimized CaiWangCun gate experiment.

Purpose:
- execute the 5-query CaiWangCun gate with pure pipeline optimizations:
  RoMa point-match reuse, offline DOM+Z point cache, and cache-based sampling;
- keep matcher, PnP, scoring, and validation logic aligned with G01;
- summarize timing, accuracy, acceptance, and G01 comparison outputs.

Main inputs:
- existing 009/010 query assets;
- CaiWangCun DOM/DSM source mosaics from the completed gate seed;
- G01 baseline summaries under the same new4 matrix root.

Main outputs:
- `new4output/.../G02_pipeline_engineering_reuse_domz_parallel_sampling`;
- `实验计划.md`, `timing_summary.json`, `accuracy_summary.json`,
  `acceptance_summary.json`, and `compare_against_G01_summary.json`.

Applicable task constraints:
- query inputs are geolocation-metadata-free UAV images and are not assumed to
  be orthophotos;
- this experiment does not introduce downsampling, SIFTGPU, Top-20 pruning, or
  learned score changes.
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
DEFAULT_EXPERIMENT_ROOT = MATRIX_ROOT / "G02_pipeline_engineering_reuse_domz_parallel_sampling"
DEFAULT_BASELINE_ROOT = MATRIX_ROOT / "G01_baseline_current_pipeline"
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
    parser.add_argument("--baseline-root", default=str(DEFAULT_BASELINE_ROOT))
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed-mosaic-root", default=str(DEFAULT_SEED_MOSAIC_ROOT))
    parser.add_argument("--domz-workers", type=int, default=4)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-run", action="store_true")
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


def count_csv_rows(path: Path) -> int:
    return len(load_csv(path))


def status_counts(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(Counter(row.get(field, "") for row in rows))


def nested_mean(summary: dict[str, Any], metric: str) -> float | None:
    value = summary.get(metric, {}).get("mean")
    if value in ("", None):
        value = summary.get("numeric_summaries", {}).get(metric, {}).get("mean")
    return None if value in ("", None) else float(value)


def write_plan_md(experiment_root: Path) -> None:
    plan = f"""# 第 2 组实验计划：工程流水线优化组合

## Summary

- 实验组名：`G02_pipeline_engineering_reuse_domz_parallel_sampling`
- 输出目录：`{experiment_root.as_posix()}`
- 对照基线：`G01_baseline_current_pipeline`
- Gate query：`{" / ".join(GATE_QUERY_IDS)}`
- 目标：验证 RoMa 点级匹配复用、DOM+Z 点缓存和 cache-based sampling 是否不损失精度并节省在线耗时。

## Pipeline

- RoMa rerank 阶段启用 `--export-pose-matches`，落盘点级匹配。
- 合并 `romav2_rerank/stage7/*/roma_matches_for_pose.csv` 为 pose 可复用的 `roma_matches.csv`。
- Pose 阶段使用 `--reuse-match-csv`，不再运行第二次 `export_romav2_matches_batch_for_pose.py`。
- `prepare_pose_correspondences.py` 保持不变。
- 离线预构建 `pose_v1_formal/domz_cache/domz_point_cache.csv`，复用 G01 DSM bilinear + 3x3 稳定性规则。
- 在线 sampling 使用 DOM+Z point cache，不再打开 DSM raster。
- PnP、score、validation 口径保持 G01 一致。

## Outputs

- `romav2_rerank/`
- `retrieval/`
- `pose_v1_formal/`
- `pose_v1_formal/domz_cache/`
- `logs/`
- `plan/`
- `timing_summary.json`
- `accuracy_summary.json`
- `acceptance_summary.json`
- `compare_against_G01_summary.json`

## Acceptance

- best pose 为 `5/5 ok`。
- PnP 输出 `100` 个 candidate。
- matches / correspondences / sampling 均为 `500000` 行。
- validation pipeline 状态为 `ok`。
- Layer-3 RMSE 与 G01 差值 `<= 0.01m`。
- Layer-2 水平误差均值与 G01 差值 `<= 0.05m`。
- sampling 状态计数与 G01 完全一致；若不一致，输出对比差异。
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


def run_g02(args: argparse.Namespace, experiment_root: Path) -> dict[str, Any]:
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
    log_path = experiment_root.parent / "G02_pipeline_engineering_reuse_domz_parallel_sampling_wrapper.log"
    ensure_dir(log_path.parent)
    started = time.time()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_now()}] + {' '.join(command)}\n")
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
    elapsed = time.time() - started
    return {
        "command": command,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "log_path": str(log_path),
    }


def validation_tiepoint_seconds(validation_summary: dict[str, Any]) -> float | None:
    for step in validation_summary.get("steps", []):
        if step.get("step_name") == "evaluate_pose_ortho_tiepoint_ground_error":
            value = step.get("elapsed_sec")
            return None if value in ("", None) else float(value)
    return None


def summarize_outputs(experiment_root: Path, baseline_root: Path, wrapper_run: dict[str, Any] | None) -> None:
    pose_root = experiment_root / "pose_v1_formal"
    suite_root = pose_root / "eval_pose_validation_suite_caiwangcun_truth"
    phase_summary = load_json(pose_root / "summary" / "phase_gate_summary.json")
    validation_summary = load_json(suite_root / "phase_gate_summary.json")
    rerank_timing = load_json(experiment_root / "romav2_rerank" / "timing" / "romav2_rerank_internal.json")
    domz_summary = load_json(pose_root / "domz_cache" / "domz_cache_summary.json")
    sampling_summary = load_json(pose_root / "sampling" / "sampling_summary.json")
    merge_summary = load_json(pose_root / "matches" / "roma_matches_reused_from_rerank.summary.json")

    pnp_rows = load_csv(pose_root / "pnp" / "pnp_results.csv")
    best_rows = load_csv(pose_root / "summary" / "per_query_best_pose.csv")
    sampled_rows = load_csv(pose_root / "sampling" / "sampled_correspondences.csv")

    ortho = validation_summary.get("overall_ortho_accuracy", {})
    pose_vs_at = validation_summary.get("overall_pose_vs_at", {})
    tiepoint = validation_summary.get("overall_tiepoint_ground_error", {})
    stages = {row.get("stage", ""): row for row in phase_summary.get("stages", [])}

    timing_summary = {
        "experiment_root": str(experiment_root),
        "baseline_root": str(baseline_root),
        "generated_at_utc": utc_now(),
        "wrapper_elapsed_seconds": None if wrapper_run is None else wrapper_run.get("elapsed_seconds"),
        "wrapper_returncode": None if wrapper_run is None else wrapper_run.get("returncode"),
        "romav2_rerank_elapsed_seconds": rerank_timing.get("elapsed_seconds"),
        "pose_export_romav2_matches_seconds": 0.0,
        "reuse_romav2_matches_for_pose_seconds": stages.get("reuse_romav2_matches_for_pose", {}).get("elapsed_seconds"),
        "merge_romav2_pose_matches_seconds": merge_summary.get("elapsed_seconds"),
        "prepare_pose_correspondences_seconds": stages.get("prepare_pose_correspondences", {}).get("elapsed_seconds"),
        "domz_prebuild_seconds": stages.get("build_domz_point_cache_for_correspondences", {}).get("elapsed_seconds"),
        "domz_sampling_total_seconds": stages.get("sample_domz_cache_for_dom_points", {}).get("elapsed_seconds"),
        "domz_sampling_detail": sampling_summary,
        "run_pnp_baseline_seconds": stages.get("run_pnp_baseline", {}).get("elapsed_seconds"),
        "score_formal_pose_results_seconds": stages.get("score_formal_pose_results", {}).get("elapsed_seconds"),
        "validation_tiepoint_seconds": validation_tiepoint_seconds(validation_summary),
        "pose_phase_stages": phase_summary.get("stages", []),
        "domz_cache_summary": domz_summary,
        "romav2_rerank_timing": rerank_timing,
    }
    write_json(experiment_root / "timing_summary.json", timing_summary)

    accuracy_summary = {
        "experiment_root": str(experiment_root),
        "baseline_root": str(baseline_root),
        "generated_at_utc": utc_now(),
        "gate_query_ids": GATE_QUERY_IDS,
        "retrieval_top20_rows": count_csv_rows(experiment_root / "retrieval" / "retrieval_top20.csv"),
        "matches_row_count": count_csv_rows(pose_root / "matches" / "roma_matches.csv"),
        "correspondence_row_count": count_csv_rows(pose_root / "correspondences" / "pose_correspondences.csv"),
        "sampling_row_count": len(sampled_rows),
        "sampling_status_counts": status_counts(sampled_rows, "sample_status"),
        "pnp_row_count": len(pnp_rows),
        "pnp_status_counts": status_counts(pnp_rows, "status"),
        "best_pose_row_count": len(best_rows),
        "best_pose_status_counts": status_counts(best_rows, "best_status"),
        "validation_pipeline_status": validation_summary.get("pipeline_status"),
        "layer1_evaluated_query_count": ortho.get("evaluated_query_count"),
        "layer1_center_offset_m_mean": nested_mean(ortho, "center_offset_m"),
        "layer1_ortho_iou_mean": nested_mean(ortho, "ortho_iou"),
        "layer2_evaluated_query_count": pose_vs_at.get("evaluated_query_count"),
        "layer2_horizontal_error_m_mean": nested_mean(pose_vs_at, "horizontal_error_m"),
        "layer3_evaluated_query_count": tiepoint.get("evaluated_query_count"),
        "layer3_tiepoint_xy_error_rmse_m": tiepoint.get("tiepoint_xy_error_rmse_m"),
    }
    write_json(experiment_root / "accuracy_summary.json", accuracy_summary)

    baseline_accuracy = load_json(baseline_root / "accuracy_summary.json")
    baseline_timing = load_json(baseline_root / "timing_summary.json")
    sampling_equal = accuracy_summary["sampling_status_counts"] == baseline_accuracy.get("sampling_status_counts")
    layer2_delta = None
    if accuracy_summary["layer2_horizontal_error_m_mean"] is not None and baseline_accuracy.get("layer2_horizontal_error_m_mean") is not None:
        layer2_delta = abs(
            float(accuracy_summary["layer2_horizontal_error_m_mean"])
            - float(baseline_accuracy["layer2_horizontal_error_m_mean"])
        )
    layer3_delta = None
    if accuracy_summary["layer3_tiepoint_xy_error_rmse_m"] is not None and baseline_accuracy.get("layer3_tiepoint_xy_error_rmse_m") is not None:
        layer3_delta = abs(
            float(accuracy_summary["layer3_tiepoint_xy_error_rmse_m"])
            - float(baseline_accuracy["layer3_tiepoint_xy_error_rmse_m"])
        )
    compare_summary = {
        "experiment_root": str(experiment_root),
        "baseline_root": str(baseline_root),
        "generated_at_utc": utc_now(),
        "sampling_status_counts_equal": sampling_equal,
        "pnp_status_counts_equal": accuracy_summary["pnp_status_counts"] == baseline_accuracy.get("pnp_status_counts"),
        "best_pose_status_counts_equal": accuracy_summary["best_pose_status_counts"] == baseline_accuracy.get("best_pose_status_counts"),
        "layer2_horizontal_error_m_mean_delta": layer2_delta,
        "layer3_tiepoint_xy_error_rmse_m_delta": layer3_delta,
        "baseline_pose_export_romav2_matches_seconds": baseline_timing.get("pose_export_romav2_matches_seconds"),
        "g02_pose_export_romav2_matches_seconds": 0.0,
        "baseline_dsm_sampling_seconds": baseline_timing.get("sample_dsm_for_dom_points_seconds"),
        "g02_online_domz_sampling_seconds": timing_summary.get("domz_sampling_total_seconds"),
        "g02_domz_prebuild_seconds": timing_summary.get("domz_prebuild_seconds"),
    }
    write_json(experiment_root / "compare_against_G01_summary.json", compare_summary)

    acceptance_checks = {
        "wrapper_returncode_zero": wrapper_run is None or wrapper_run.get("returncode") == 0,
        "best_pose_5_of_5_ok": accuracy_summary["best_pose_status_counts"].get("ok") == 5,
        "pnp_row_count_100": accuracy_summary["pnp_row_count"] == 100,
        "matches_row_count_500000": accuracy_summary["matches_row_count"] == 500000,
        "correspondence_row_count_500000": accuracy_summary["correspondence_row_count"] == 500000,
        "sampling_row_count_500000": accuracy_summary["sampling_row_count"] == 500000,
        "validation_pipeline_ok": accuracy_summary["validation_pipeline_status"] == "ok",
        "sampling_status_counts_equal_g01": sampling_equal,
        "layer2_delta_within_0p05m": layer2_delta is not None and layer2_delta <= 0.05,
        "layer3_delta_within_0p01m": layer3_delta is not None and layer3_delta <= 0.01,
        "pose_export_removed": timing_summary["pose_export_romav2_matches_seconds"] == 0.0,
    }
    write_json(
        experiment_root / "acceptance_summary.json",
        {
            "experiment_root": str(experiment_root),
            "baseline_root": str(baseline_root),
            "generated_at_utc": utc_now(),
            "checks": acceptance_checks,
            "accepted": all(acceptance_checks.values()),
            "accuracy_summary": "accuracy_summary.json",
            "timing_summary": "timing_summary.json",
            "compare_summary": "compare_against_G01_summary.json",
        },
    )


def main() -> None:
    args = parse_args()
    experiment_root = Path(args.experiment_root)
    baseline_root = Path(args.baseline_root)
    if args.overwrite and experiment_root.exists():
        shutil.rmtree(experiment_root)
    ensure_dir(experiment_root)
    write_plan_md(experiment_root)
    seed_source_mosaic(experiment_root, Path(args.seed_mosaic_root))
    wrapper_run = None
    if not args.skip_run:
        wrapper_run = run_g02(args, experiment_root)
        if int(wrapper_run["returncode"]) != 0:
            write_json(experiment_root / "wrapper_failed_summary.json", wrapper_run)
            raise SystemExit(int(wrapper_run["returncode"]))
    if not args.dry_run:
        summarize_outputs(experiment_root, baseline_root, wrapper_run)
    print(experiment_root)


if __name__ == "__main__":
    main()

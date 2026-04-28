#!/usr/bin/env python3
"""Run new4 G04 downsample resolution sweep on the G02 pipeline.

Purpose:
- execute two controlled query/candidate image-resolution variants on top of
  the G02 engineering pipeline;
- keep RoMa v2, DOM+Z sampling, PnP, scoring, and validation logic unchanged;
- compare speed, match density, pose success, and validation accuracy against
  the G02 same-environment control.

Main inputs:
- CaiWangCun DOM/DSM source mosaics from the completed gate seed;
- G02 summaries under the same new4 matrix root;
- the fixed five gate queries `q_001/q_021/q_002/q_003/q_004`.

Main outputs:
- `new4output/.../G04_downsample_resolution_sweep/G04A_downsample_0p5m`;
- `new4output/.../G04_downsample_resolution_sweep/G04B_downsample_1p0m`;
- per-subgroup timing, accuracy, acceptance, and G02 comparison summaries;
- sweep-level aggregate JSON and CSV.

Applicable task constraints:
- query images remain metadata-free and are not assumed to be orthophotos;
- external resolution normalization is introduced only as this named G04
  experiment variable, not as the default formal task protocol.
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
DEFAULT_EXPERIMENT_ROOT = MATRIX_ROOT / "G04_downsample_resolution_sweep"
DEFAULT_G02_ROOT = MATRIX_ROOT / "G02_pipeline_engineering_reuse_domz_parallel_sampling"
DEFAULT_GATE_SCRIPT = PROJECT_ROOT / "scripts" / "run_nadir_009010_caiwangcun_fullreplace_gate_experiment.py"
DEFAULT_SEED_MOSAIC_ROOT = (
    PROJECT_ROOT
    / "new3output"
    / "nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20"
    / "source_mosaic"
)
GATE_QUERY_IDS = ["q_001", "q_021", "q_002", "q_003", "q_004"]
SWEEP_CONFIGS = [
    ("G04A_downsample_0p5m", 0.5),
    ("G04B_downsample_1p0m", 1.0),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-root", default=str(DEFAULT_EXPERIMENT_ROOT))
    parser.add_argument("--g02-root", default=str(DEFAULT_G02_ROOT))
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


def ratio_delta(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline in (None, 0):
        return None
    return (float(current) - float(baseline)) / float(baseline)


def write_plan_md(root: Path) -> None:
    plan = f"""# 第 4 组实验计划：G02 + 影像降分辨率 Sweep

## Summary

- 实验组名：`G04_downsample_resolution_sweep`
- 输出根目录：`{root.as_posix()}`
- 子组：
  - `G04A_downsample_0p5m`
  - `G04B_downsample_1p0m`
- 对照组：`G02_pipeline_engineering_reuse_domz_parallel_sampling`
- Gate query：`{" / ".join(GATE_QUERY_IDS)}`

## Pipeline

- 基于 G02 工程优化管线：RoMa 点级匹配复用、DOM+Z cache sampling、PnP 与 validation 口径不变。
- 候选 DOM tile 在构建 candidate library 时输出为目标 GSD，但保持原 tile 地理范围、中心、bbox 与 tile_id 规则。
- Query 图按 `relative_altitude / calibrated_focal_length_px` 估算原始近似 GSD，并缩小到目标 GSD。
- formal query manifest 同步缩放 `width/height/fx/fy/cx/cy`。
- DSM 与 DOM+Z 仍按原 DSM 采样规则构建，不测试高程降分辨率。

## 子组

- G04A：query 与 candidate 同时降到 `0.5 m/pix`。
- G04B：query 与 candidate 同时降到 `1.0 m/pix`。

## 验收与对比

- 每个子组跑完整 5 query Top-20。
- 最低验收：retrieval `100` 行、PnP `100` candidate、best pose `5/5 ok`、validation pipeline `ok`。
- 对比 G02：RoMa rerank 耗时、match/sampling 行数、PnP 状态、Layer-2 均值、Layer-3 RMSE、总耗时变化。
"""
    (root / "实验计划.md").write_text(plan, encoding="utf-8")


def write_subplan_md(subroot: Path, target_gsd: float) -> None:
    text = f"""# G04 子组实验计划

- 子组目录：`{subroot.as_posix()}`
- 目标图像 GSD：`{target_gsd:.1f} m/pix`
- 基线：G02 工程优化管线。
- 改动：仅对 query 图和 candidate DOM tile 同时降分辨率；RoMa、DOM+Z、PnP、scoring、validation 不变。
- 输出：`timing_summary.json`、`accuracy_summary.json`、`acceptance_summary.json`、`compare_against_G02_summary.json`。
"""
    (subroot / "实验计划.md").write_text(text, encoding="utf-8")


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


def run_subgroup(args: argparse.Namespace, subroot: Path, target_gsd: float) -> dict[str, Any]:
    seed_tile_root = seed_source_tile_links(subroot)
    command = [
        args.python_bin,
        str(DEFAULT_GATE_SCRIPT),
        "--experiment-root",
        str(subroot),
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
        "--candidate-output-gsd-m",
        str(target_gsd),
        "--query-output-gsd-m",
        str(target_gsd),
    ]
    for query_id in GATE_QUERY_IDS:
        command.extend(["--rerank-query-id", query_id])
    if args.dry_run:
        command.append("--dry-run")
    log_path = subroot / "logs" / "g04_wrapper.log"
    ensure_dir(log_path.parent)
    started = time.time()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_now()}] + {' '.join(command)}\n")
        completed = subprocess.run(command, cwd=PROJECT_ROOT, stdout=handle, stderr=subprocess.STDOUT, text=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "elapsed_seconds": time.time() - started,
        "log_path": str(log_path),
    }


def validation_tiepoint_seconds(validation_summary: dict[str, Any]) -> float | None:
    for step in validation_summary.get("steps", []):
        if step.get("step_name") == "evaluate_pose_ortho_tiepoint_ground_error":
            value = step.get("elapsed_sec")
            return None if value in ("", None) else float(value)
    return None


def summarize_subgroup(
    subroot: Path,
    g02_root: Path,
    target_gsd: float,
    wrapper_run: dict[str, Any] | None,
) -> dict[str, Any]:
    pose_root = subroot / "pose_v1_formal"
    suite_root = pose_root / "eval_pose_validation_suite_caiwangcun_truth"
    phase_summary = load_json(pose_root / "summary" / "phase_gate_summary.json")
    validation_summary = load_json(suite_root / "phase_gate_summary.json")
    rerank_timing = load_json(subroot / "romav2_rerank" / "timing" / "romav2_rerank_internal.json")
    sampling_summary = load_json(pose_root / "sampling" / "sampling_summary.json")
    domz_summary = load_json(pose_root / "domz_cache" / "domz_cache_summary.json")
    merge_summary = load_json(pose_root / "matches" / "roma_matches_reused_from_rerank.summary.json")
    query_downsample = next((subroot / "query_inputs").glob("query_downsample_*_summary.json"), None)

    pnp_rows = load_csv(pose_root / "pnp" / "pnp_results.csv")
    best_rows = load_csv(pose_root / "summary" / "per_query_best_pose.csv")
    sampled_rows = load_csv(pose_root / "sampling" / "sampled_correspondences.csv")
    match_rows = count_csv_rows(pose_root / "matches" / "roma_matches.csv")
    corr_rows = count_csv_rows(pose_root / "correspondences" / "pose_correspondences.csv")
    stages = {row.get("stage", ""): row for row in phase_summary.get("stages", [])}
    ortho = validation_summary.get("overall_ortho_accuracy", {})
    pose_vs_at = validation_summary.get("overall_pose_vs_at", {})
    tiepoint = validation_summary.get("overall_tiepoint_ground_error", {})

    timing_summary = {
        "experiment_root": str(subroot),
        "g02_root": str(g02_root),
        "target_gsd_m": target_gsd,
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
    write_json(subroot / "timing_summary.json", timing_summary)

    accuracy_summary = {
        "experiment_root": str(subroot),
        "g02_root": str(g02_root),
        "target_gsd_m": target_gsd,
        "generated_at_utc": utc_now(),
        "gate_query_ids": GATE_QUERY_IDS,
        "retrieval_top20_rows": count_csv_rows(subroot / "retrieval" / "retrieval_top20.csv"),
        "matches_row_count": match_rows,
        "correspondence_row_count": corr_rows,
        "sampling_row_count": len(sampled_rows),
        "sampling_status_counts": status_counts(sampled_rows, "sample_status"),
        "pnp_row_count": len(pnp_rows),
        "pnp_status_counts": status_counts(pnp_rows, "status"),
        "best_pose_row_count": len(best_rows),
        "best_pose_status_counts": status_counts(best_rows, "best_status"),
        "validation_pipeline_status": validation_summary.get("pipeline_status"),
        "layer1_center_offset_m_mean": nested_mean(ortho, "center_offset_m"),
        "layer1_ortho_iou_mean": nested_mean(ortho, "ortho_iou"),
        "layer2_horizontal_error_m_mean": nested_mean(pose_vs_at, "horizontal_error_m"),
        "layer3_tiepoint_xy_error_rmse_m": tiepoint.get("tiepoint_xy_error_rmse_m"),
        "query_downsample_summary": str(query_downsample) if query_downsample else None,
    }
    write_json(subroot / "accuracy_summary.json", accuracy_summary)

    g02_accuracy = load_json(g02_root / "accuracy_summary.json")
    g02_timing = load_json(g02_root / "timing_summary.json")
    current_rerank = timing_summary.get("romav2_rerank_elapsed_seconds")
    g02_rerank = g02_timing.get("romav2_rerank_elapsed_seconds")
    current_total = timing_summary.get("wrapper_elapsed_seconds")
    g02_total = g02_timing.get("wrapper_elapsed_seconds")
    compare_summary = {
        "experiment_root": str(subroot),
        "g02_root": str(g02_root),
        "target_gsd_m": target_gsd,
        "generated_at_utc": utc_now(),
        "romav2_rerank_seconds_delta_ratio_vs_g02": ratio_delta(current_rerank, g02_rerank),
        "wrapper_elapsed_seconds_delta_ratio_vs_g02": ratio_delta(current_total, g02_total),
        "matches_row_count_delta_vs_g02": accuracy_summary["matches_row_count"] - int(g02_accuracy.get("matches_row_count", 0)),
        "sampling_row_count_delta_vs_g02": accuracy_summary["sampling_row_count"] - int(g02_accuracy.get("sampling_row_count", 0)),
        "pnp_status_counts_g02": g02_accuracy.get("pnp_status_counts"),
        "pnp_status_counts_current": accuracy_summary["pnp_status_counts"],
        "best_pose_status_counts_g02": g02_accuracy.get("best_pose_status_counts"),
        "best_pose_status_counts_current": accuracy_summary["best_pose_status_counts"],
        "layer2_horizontal_error_m_mean_g02": g02_accuracy.get("layer2_horizontal_error_m_mean"),
        "layer2_horizontal_error_m_mean_current": accuracy_summary["layer2_horizontal_error_m_mean"],
        "layer3_tiepoint_xy_error_rmse_m_g02": g02_accuracy.get("layer3_tiepoint_xy_error_rmse_m"),
        "layer3_tiepoint_xy_error_rmse_m_current": accuracy_summary["layer3_tiepoint_xy_error_rmse_m"],
    }
    write_json(subroot / "compare_against_G02_summary.json", compare_summary)

    acceptance_checks = {
        "wrapper_returncode_zero": wrapper_run is None or wrapper_run.get("returncode") == 0,
        "retrieval_top20_rows_100": accuracy_summary["retrieval_top20_rows"] == 100,
        "pnp_row_count_100": accuracy_summary["pnp_row_count"] == 100,
        "best_pose_5_of_5_ok": accuracy_summary["best_pose_status_counts"].get("ok") == 5,
        "validation_pipeline_ok": accuracy_summary["validation_pipeline_status"] == "ok",
        "sampling_matches_correspondences_consistent": (
            accuracy_summary["matches_row_count"]
            == accuracy_summary["correspondence_row_count"]
            == accuracy_summary["sampling_row_count"]
        ),
        "pose_export_removed": timing_summary["pose_export_romav2_matches_seconds"] == 0.0,
    }
    write_json(
        subroot / "acceptance_summary.json",
        {
            "experiment_root": str(subroot),
            "g02_root": str(g02_root),
            "target_gsd_m": target_gsd,
            "generated_at_utc": utc_now(),
            "checks": acceptance_checks,
            "accepted": all(acceptance_checks.values()),
            "accuracy_summary": "accuracy_summary.json",
            "timing_summary": "timing_summary.json",
            "compare_summary": "compare_against_G02_summary.json",
        },
    )
    return {
        "subgroup": subroot.name,
        "target_gsd_m": target_gsd,
        "accepted": all(acceptance_checks.values()),
        **accuracy_summary,
        "romav2_rerank_elapsed_seconds": timing_summary.get("romav2_rerank_elapsed_seconds"),
        "wrapper_elapsed_seconds": timing_summary.get("wrapper_elapsed_seconds"),
        "domz_sampling_total_seconds": timing_summary.get("domz_sampling_total_seconds"),
    }


def write_aggregate(root: Path, rows: list[dict[str, Any]]) -> None:
    write_json(
        root / "aggregate_resolution_sweep_summary.json",
        {"generated_at_utc": utc_now(), "subgroup_count": len(rows), "rows": rows},
    )
    if not rows:
        return
    fields = [
        "subgroup",
        "target_gsd_m",
        "accepted",
        "retrieval_top20_rows",
        "matches_row_count",
        "sampling_row_count",
        "pnp_status_counts",
        "best_pose_status_counts",
        "validation_pipeline_status",
        "layer2_horizontal_error_m_mean",
        "layer3_tiepoint_xy_error_rmse_m",
        "romav2_rerank_elapsed_seconds",
        "domz_sampling_total_seconds",
        "wrapper_elapsed_seconds",
    ]
    with (root / "aggregate_resolution_sweep_summary.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: json.dumps(row.get(field), ensure_ascii=False) if isinstance(row.get(field), (dict, list)) else row.get(field) for field in fields})


def main() -> None:
    args = parse_args()
    root = Path(args.experiment_root)
    g02_root = Path(args.g02_root)
    if args.overwrite and root.exists():
        shutil.rmtree(root)
    ensure_dir(root)
    write_plan_md(root)
    aggregate_rows: list[dict[str, Any]] = []
    for subgroup, target_gsd in SWEEP_CONFIGS:
        subroot = root / subgroup
        ensure_dir(subroot)
        write_subplan_md(subroot, target_gsd)
        seed_source_mosaic(subroot, Path(args.seed_mosaic_root))
        wrapper_run = None
        if not args.skip_run:
            wrapper_run = run_subgroup(args, subroot, target_gsd)
            if int(wrapper_run["returncode"]) != 0:
                write_json(subroot / "wrapper_failed_summary.json", wrapper_run)
                raise SystemExit(int(wrapper_run["returncode"]))
        if not args.dry_run:
            aggregate_rows.append(summarize_subgroup(subroot, g02_root, target_gsd, wrapper_run))
    if not args.dry_run:
        write_aggregate(root, aggregate_rows)
    print(root)


if __name__ == "__main__":
    main()

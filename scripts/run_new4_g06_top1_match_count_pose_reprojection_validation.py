#!/usr/bin/env python3
"""Run G06 Top-1 matched-candidate pose and reprojection validation.

Purpose:
- validate whether one candidate per query, selected by the largest matched
  point support from existing G02/G03 rerank outputs, can directly support PnP
  and reprojection validation;
- reuse existing sampled 2D-3D correspondences instead of rerunning retrieval,
  RoMa, SIFTGPU, DSM sampling, or DOM+Z cache construction;
- compare reduced Top-1 downstream time and accuracy against the full Top-20
  G02/G03 gate runs.

Main inputs:
- G02 and G03 rerank Top-20 CSVs;
- G02 and G03 sampled correspondences;
- G02 and G03 formal pose manifests and CaiWangCun validation assets.

Main outputs:
- `new4output/.../G06_top1_match_count_pose_reprojection_validation`;
- one reduced pose bundle per Top-1 strategy;
- root CSV/JSON/Markdown summaries comparing candidate choice, PnP,
  validation accuracy, and timing.

Applicable task constraints:
- query images are metadata-free UAV images and are not assumed orthophotos;
- this experiment does not prove that geometric rerank can be skipped, because
  Top-1 matched-point support is computed from existing geometry matching.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MATRIX_ROOT = PROJECT_ROOT / "new4output" / "nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27"
DEFAULT_G02_ROOT = MATRIX_ROOT / "G02_pipeline_engineering_reuse_domz_parallel_sampling"
DEFAULT_G03_ROOT = MATRIX_ROOT / "G03_pipeline_siftgpu_replace_roma"
DEFAULT_OUT_ROOT = MATRIX_ROOT / "G06_top1_match_count_pose_reprojection_validation"
GATE_QUERY_IDS = ["q_001", "q_021", "q_002", "q_003", "q_004"]


SUBGROUPS = [
    {
        "name": "G06A_g02_roma_inlier_top1",
        "source_group": "g02_roma",
        "base_key": "g02",
        "matcher": "RoMa v2",
        "rerank_rel": ("romav2_rerank", "stage7"),
        "sort_strategy": "inlier_count",
        "primary_metric": "inlier_count",
        "comparison_group": "G02",
    },
    {
        "name": "G06B_g03_siftgpu_inlier_top1",
        "source_group": "g03_siftgpu",
        "base_key": "g03",
        "matcher": "SIFTGPU",
        "rerank_rel": ("siftgpu_rerank", "stage7"),
        "sort_strategy": "inlier_count",
        "primary_metric": "inlier_count",
        "comparison_group": "G03",
    },
    {
        "name": "G06C_g03_siftgpu_match_top1",
        "source_group": "g03_siftgpu",
        "base_key": "g03",
        "matcher": "SIFTGPU",
        "rerank_rel": ("siftgpu_rerank", "stage7"),
        "sort_strategy": "match_count",
        "primary_metric": "match_count",
        "comparison_group": "G03",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--g02-root", default=str(DEFAULT_G02_ROOT))
    parser.add_argument("--g03-root", default=str(DEFAULT_G03_ROOT))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument(
        "--validation-timeout-seconds",
        type=int,
        default=900,
        help="Maximum wall time for each subgroup validation suite. Timeout is recorded as a failed validation.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    ensure_dir(path.parent)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def as_float(value: str | int | float | None, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: str | int | float | None, default: int = 0) -> int:
    return int(round(as_float(value, float(default))))


def is_true(value: str | int | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def count_csv_rows(path: Path) -> int:
    return len(load_csv(path))


def status_counts(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(Counter(row.get(field, "") for row in rows))


def nested_mean(summary: dict[str, Any], metric: str) -> float | None:
    value = summary.get(metric, {}).get("mean")
    if value in ("", None):
        value = summary.get("numeric_summaries", {}).get(metric, {}).get("mean")
    return None if value in ("", None) else float(value)


def select_top1_candidates(base_root: Path, subgroup: dict[str, str]) -> list[dict[str, Any]]:
    rerank_root = base_root.joinpath(*subgroup["rerank_rel"])
    rows: list[dict[str, str]] = []
    for path in sorted(rerank_root.glob("*/reranked_top20.csv")):
        rows.extend(load_csv(path))
    by_query: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("query_id") in GATE_QUERY_IDS:
            by_query[row["query_id"]].append(row)

    selected: list[dict[str, Any]] = []
    for query_id in GATE_QUERY_IDS:
        qrows = by_query.get(query_id, [])
        if not qrows:
            raise SystemExit(f"{subgroup['name']}: no rerank rows for {query_id}")
        if subgroup["sort_strategy"] == "match_count":
            qrows = sorted(
                qrows,
                key=lambda row: (
                    -as_int(row.get("match_count")),
                    -as_int(row.get("inlier_count")),
                    as_int(row.get("raw_rank")),
                    as_int(row.get("rank")),
                ),
            )
        else:
            qrows = sorted(
                qrows,
                key=lambda row: (
                    -as_int(row.get("inlier_count")),
                    as_int(row.get("raw_rank")),
                    as_int(row.get("rank")),
                ),
            )
        row = qrows[0]
        selected.append(
            {
                "subgroup": subgroup["name"],
                "source_group": subgroup["source_group"],
                "matcher": subgroup["matcher"],
                "strategy": f"{subgroup['primary_metric']}_top1",
                "query_id": query_id,
                "candidate_id": row["candidate_tile_id"],
                "raw_rank": as_int(row.get("raw_rank")),
                "rerank_rank": as_int(row.get("rank")),
                "match_count": as_int(row.get("match_count")),
                "inlier_count": as_int(row.get("inlier_count")),
                "inlier_ratio": as_float(row.get("inlier_ratio")),
                "fused_score": as_float(row.get("fused_score")),
                "geom_valid": as_int(row.get("geom_valid")),
                "is_truth_hit": int(is_true(row.get("is_intersection_truth_hit"))),
            }
        )
    return selected


def prepare_reduced_bundle(base_root: Path, subgroup_root: Path, overwrite: bool) -> Path:
    pose_root = subgroup_root / "pose_v1_formal"
    if overwrite and subgroup_root.exists():
        resolved = subgroup_root.resolve()
        expected = DEFAULT_OUT_ROOT.resolve()
        if expected not in resolved.parents and resolved != expected:
            raise SystemExit(f"refusing to delete unexpected path: {resolved}")
        shutil.rmtree(subgroup_root)
    ensure_dir(pose_root)
    base_pose = base_root / "pose_v1_formal"
    for dirname in ("manifest", "input"):
        src = base_pose / dirname
        dst = pose_root / dirname
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    ensure_dir(pose_root / "sampling")
    ensure_dir(pose_root / "pnp")
    ensure_dir(pose_root / "scores")
    ensure_dir(pose_root / "summary")
    ensure_dir(pose_root / "logs")
    return pose_root


def filter_sampled_correspondences(base_root: Path, pose_root: Path, selected: list[dict[str, Any]]) -> dict[str, Any]:
    selected_pairs = {(row["query_id"], row["candidate_id"]) for row in selected}
    src = base_root / "pose_v1_formal" / "sampling" / "sampled_correspondences.csv"
    dst = pose_root / "sampling" / "sampled_correspondences.csv"
    started = time.perf_counter()
    total_read = 0
    kept = 0
    per_pair_counts: Counter[tuple[str, str]] = Counter()
    status_counter: Counter[str] = Counter()
    with src.open("r", newline="", encoding="utf-8-sig") as in_handle, dst.open("w", newline="", encoding="utf-8-sig") as out_handle:
        reader = csv.DictReader(in_handle)
        if reader.fieldnames is None:
            raise SystemExit(f"empty sampled correspondences: {src}")
        writer = csv.DictWriter(out_handle, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            total_read += 1
            key = (row["query_id"], row["candidate_id"])
            if key not in selected_pairs:
                continue
            kept += 1
            per_pair_counts[key] += 1
            status_counter[row.get("sample_status", "")] += 1
            writer.writerow(row)
    elapsed = time.perf_counter() - started
    summary = {
        "source_csv": str(src),
        "output_csv": str(dst),
        "source_rows_read": total_read,
        "row_count": kept,
        "selected_pair_count": len(selected_pairs),
        "status_counts": dict(status_counter),
        "elapsed_seconds": elapsed,
        "per_pair_counts": [
            {"query_id": query_id, "candidate_id": candidate_id, "row_count": count}
            for (query_id, candidate_id), count in sorted(per_pair_counts.items())
        ],
    }
    write_json(pose_root / "sampling" / "sampling_summary.json", summary)
    return summary


def run_step(
    name: str,
    command: list[str],
    log_path: Path,
    dry_run: bool,
    timeout_seconds: int | None = None,
    allow_failure: bool = False,
) -> dict[str, Any]:
    ensure_dir(log_path.parent)
    started = time.time()
    if dry_run:
        result = {"step_name": name, "command": command, "returncode": 0, "elapsed_sec": 0.0, "dry_run": True}
    else:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{utc_now()}] + {' '.join(command)}\n")
            process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            timed_out = False
            try:
                returncode = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    returncode = process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    returncode = process.wait()
                handle.write(f"[{utc_now()}] ! timeout after {timeout_seconds}s; process group terminated\n")
        result = {
            "step_name": name,
            "command": command,
            "returncode": returncode,
            "elapsed_sec": time.time() - started,
            "dry_run": False,
            "timed_out": timed_out,
            "timeout_seconds": timeout_seconds,
        }
    if int(result["returncode"]) != 0 and not allow_failure:
        raise SystemExit(f"{name} failed with returncode {result['returncode']}; see {log_path}")
    return result


def run_reduced_pose_and_validation(
    python_bin: str,
    base_root: Path,
    subgroup_root: Path,
    pose_root: Path,
    selected: list[dict[str, Any]],
    skip_validation: bool,
    validation_timeout_seconds: int,
    dry_run: bool,
) -> list[dict[str, Any]]:
    log_path = subgroup_root / "logs" / "g06_run.log"
    steps: list[dict[str, Any]] = []
    manifest_json = pose_root / "manifest" / "pose_manifest.json"
    sampled_csv = pose_root / "sampling" / "sampled_correspondences.csv"
    steps.append(
        run_step(
            "run_pnp_baseline",
            [
                python_bin,
                str(PROJECT_ROOT / "scripts" / "run_pnp_baseline.py"),
                "--bundle-root",
                str(pose_root),
                "--manifest-json",
                str(manifest_json),
                "--sampled-correspondences-csv",
                str(sampled_csv),
                "--out-dir",
                str(pose_root / "pnp"),
            ],
            log_path,
            dry_run,
        )
    )
    steps.append(
        run_step(
            "run_pose_v1_formal_scoring_summary",
            [
                python_bin,
                str(PROJECT_ROOT / "scripts" / "run_pose_v1_formal_scoring_summary.py"),
                "--bundle-root",
                str(pose_root),
                "--manifest-json",
                str(manifest_json),
                "--pnp-results-csv",
                str(pose_root / "pnp" / "pnp_results.csv"),
                "--scores-dir",
                str(pose_root / "scores"),
                "--summary-dir",
                str(pose_root / "summary"),
            ],
            log_path,
            dry_run,
        )
    )
    if not skip_validation:
        validation_cmd = [
            python_bin,
            str(PROJECT_ROOT / "scripts" / "run_pose_validation_suite.py"),
            "--bundle-root",
            str(pose_root),
            "--query-seed-csv",
            str(base_root / "query_truth" / "queries_truth_seed.csv"),
            "--phase",
            "gate",
            "--gate-count",
            "5",
            "--target-resolution-m",
            "0.14",
            "--crop-margin-m",
            "80.0",
            "--block-size",
            "256",
            "--flight-asset-manifest",
            str(base_root / "plan" / "caiwangcun_asset_manifest.csv"),
            "--output-root",
            str(pose_root / "eval_pose_validation_suite_caiwangcun_truth"),
            "--overwrite",
        ]
        for query_id in GATE_QUERY_IDS:
            validation_cmd.extend(["--query-id", query_id])
        steps.append(
            run_step(
                "run_pose_validation_suite",
                validation_cmd,
                log_path,
                dry_run,
                timeout_seconds=validation_timeout_seconds,
                allow_failure=True,
            )
        )
    write_json(subgroup_root / "plan" / "reduced_run_steps.json", {"steps": steps, "selected_candidates": selected})
    return steps


def validation_tiepoint_seconds(validation_summary: dict[str, Any]) -> float | None:
    for step in validation_summary.get("steps", []):
        if step.get("step_name") == "evaluate_pose_ortho_tiepoint_ground_error":
            value = step.get("elapsed_sec")
            return None if value in ("", None) else float(value)
    return None


def summarize_subgroup(
    subgroup: dict[str, str],
    subgroup_root: Path,
    base_root: Path,
    selected: list[dict[str, Any]],
    sampling_summary: dict[str, Any],
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    pose_root = subgroup_root / "pose_v1_formal"
    validation_summary = load_json(pose_root / "eval_pose_validation_suite_caiwangcun_truth" / "phase_gate_summary.json")
    validation_root = pose_root / "eval_pose_validation_suite_caiwangcun_truth"
    pnp_rows = load_csv(pose_root / "pnp" / "pnp_results.csv")
    best_rows = load_csv(pose_root / "summary" / "per_query_best_pose.csv")
    base_accuracy = load_json(base_root / "accuracy_summary.json")
    base_timing = load_json(base_root / "timing_summary.json")

    ortho = validation_summary.get("overall_ortho_accuracy", {}) or load_json(
        validation_root / "ortho_alignment" / "overall_ortho_accuracy.json"
    )
    pose_vs_at = validation_summary.get("overall_pose_vs_at", {}) or load_json(
        validation_root / "pose_vs_at" / "overall_pose_vs_at.json"
    )
    tiepoint = validation_summary.get("overall_tiepoint_ground_error", {}) or load_json(
        validation_root / "tiepoint_ground_error" / "overall_tiepoint_ground_error.json"
    )
    pnp_status = status_counts(pnp_rows, "status")
    best_gate_rows = [row for row in best_rows if row.get("query_id") in GATE_QUERY_IDS]
    best_status = status_counts(best_gate_rows, "best_status")
    step_times = {row["step_name"]: row.get("elapsed_sec", 0.0) for row in steps}
    validation_step = next((row for row in steps if row["step_name"] == "run_pose_validation_suite"), {})
    validation_status = validation_summary.get("pipeline_status")
    if not validation_status and validation_step.get("timed_out"):
        validation_status = "timeout"
    elif not validation_status and validation_step:
        validation_status = "failed" if int(validation_step.get("returncode", 0)) != 0 else "missing_summary"

    actual_reduced_downstream_time = (
        float(sampling_summary.get("elapsed_seconds", 0.0))
        + float(step_times.get("run_pnp_baseline", 0.0))
        + float(step_times.get("run_pose_v1_formal_scoring_summary", 0.0))
        + float(step_times.get("run_pose_validation_suite", 0.0))
    )
    retrieval_time = float(base_timing.get("retrieval_elapsed_seconds") or 0.0)
    rerank_time = float(
        base_timing.get("romav2_rerank_elapsed_seconds")
        or base_timing.get("siftgpu_rerank_elapsed_seconds")
        or 0.0
    )
    estimated_end_to_end_time = retrieval_time + rerank_time + actual_reduced_downstream_time
    layer2_mean = nested_mean(pose_vs_at, "horizontal_error_m")
    layer3_rmse = tiepoint.get("tiepoint_xy_error_rmse_m")
    if layer3_rmse not in ("", None):
        layer3_rmse = float(layer3_rmse)
    else:
        layer3_rmse = None
    base_layer2 = base_accuracy.get("layer2_horizontal_error_m_mean")
    base_layer3 = base_accuracy.get("layer3_tiepoint_xy_error_rmSE_m") or base_accuracy.get("layer3_tiepoint_xy_error_rmse_m")

    accepted = (
        len(selected) == 5
        and len(pnp_rows) == 5
        and best_status.get("ok", 0) == 5
        and validation_status == "ok"
        and layer2_mean is not None
        and base_layer2 is not None
        and abs(float(layer2_mean) - float(base_layer2)) <= 0.5
        and layer3_rmse is not None
        and base_layer3 is not None
        and abs(float(layer3_rmse) - float(base_layer3)) <= 0.1
    )
    summary = {
        "subgroup": subgroup["name"],
        "source_group": subgroup["source_group"],
        "matcher": subgroup["matcher"],
        "strategy": f"{subgroup['primary_metric']}_top1",
        "comparison_group": subgroup["comparison_group"],
        "subgroup_root": str(subgroup_root),
        "base_root": str(base_root),
        "selected_candidate_count": len(selected),
        "sampling_row_count": int(sampling_summary.get("row_count", 0)),
        "sampling_status_counts": sampling_summary.get("status_counts", {}),
        "pnp_row_count": len(pnp_rows),
        "pnp_status_counts": pnp_status,
        "best_pose_status_counts": best_status,
        "validation_pipeline_status": validation_status,
        "validation_returncode": validation_step.get("returncode"),
        "validation_timed_out": bool(validation_step.get("timed_out", False)),
        "layer1_center_offset_m_mean": nested_mean(ortho, "center_offset_m"),
        "layer2_horizontal_error_m_mean": layer2_mean,
        "layer3_tiepoint_xy_error_rmse_m": layer3_rmse,
        "base_layer2_horizontal_error_m_mean": base_layer2,
        "base_layer3_tiepoint_xy_error_rmse_m": base_layer3,
        "layer2_delta_m": None if layer2_mean is None or base_layer2 is None else float(layer2_mean) - float(base_layer2),
        "layer3_delta_m": None if layer3_rmse is None or base_layer3 is None else float(layer3_rmse) - float(base_layer3),
        "actual_reduced_downstream_time_seconds": actual_reduced_downstream_time,
        "estimated_end_to_end_time_seconds": estimated_end_to_end_time,
        "retrieval_time_from_base_seconds": retrieval_time,
        "rerank_time_from_base_seconds": rerank_time,
        "step_times": step_times,
        "validation_tiepoint_seconds": validation_tiepoint_seconds(validation_summary),
        "base_sampling_row_count": base_accuracy.get("sampling_row_count"),
        "base_pnp_row_count": base_accuracy.get("pnp_row_count"),
        "candidate_reduction_ratio": 1.0 - (5.0 / max(1.0, float(base_accuracy.get("pnp_row_count") or 100))),
        "accepted": accepted,
    }
    write_json(subgroup_root / "timing_summary.json", {k: v for k, v in summary.items() if "time" in k or k in {"subgroup", "step_times", "validation_tiepoint_seconds"}})
    write_json(subgroup_root / "accuracy_summary.json", summary)
    write_json(
        subgroup_root / "acceptance_summary.json",
        {
            "accepted": accepted,
            "criteria": {
                "selected_candidate_count_is_5": len(selected) == 5,
                "pnp_row_count_is_5": len(pnp_rows) == 5,
                "best_pose_5_of_5_ok": best_status.get("ok", 0) == 5,
                "validation_pipeline_ok": summary["validation_pipeline_status"] == "ok",
                "layer2_delta_abs_le_0p5m": summary["layer2_delta_m"] is not None and abs(summary["layer2_delta_m"]) <= 0.5,
                "layer3_delta_abs_le_0p1m": summary["layer3_delta_m"] is not None and abs(summary["layer3_delta_m"]) <= 0.1,
            },
            "summary": summary,
        },
    )
    return summary


def write_plan_md(out_root: Path) -> None:
    lines = [
        "# 第 6 组实验计划：同名点最多 Top-1 候选位姿解算与重投影验证",
        "",
        "## Summary",
        "",
        f"- 实验组名：`G06_top1_match_count_pose_reprojection_validation`",
        f"- 输出目录：`{out_root.as_posix()}`",
        "- 输入对照：G02 RoMa 工程优化管线、G03 SIFTGPU 替换管线",
        "- Gate query：`q_001/q_021/q_002/q_003/q_004`",
        "- 性质：不重跑 retrieval、RoMa、SIFTGPU 或 DSM sampling，只复用已有 sampled correspondences 做 Top-1 reduced pose。",
        "",
        "## Subgroups",
        "",
        "- `G06A_g02_roma_inlier_top1`：G02 RoMa，按 `inlier_count` 最大选 1 个候选。",
        "- `G06B_g03_siftgpu_inlier_top1`：G03 SIFTGPU，按 `inlier_count` 最大选 1 个候选。",
        "- `G06C_g03_siftgpu_match_top1`：G03 SIFTGPU，按 `match_count` 最大选 1 个候选。",
        "",
        "## Metrics",
        "",
        "- 每组重新输出 5 行 PnP、5 个 gate query 的 best pose 与 CaiWangCun truth validation。",
        "- 重点比较 Layer-2 horizontal error mean、Layer-3 tiepoint XY RMSE、PnP ok 数和 reduced downstream 耗时。",
        "- 本组不能单独证明可跳过几何重排，因为 Top-1 的同名点数量来自已有几何匹配结果。",
    ]
    (out_root / "实验计划.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(out_root: Path, summaries: list[dict[str, Any]]) -> None:
    lines = [
        "# G06 Top-1 位姿解算与重投影验证报告",
        "",
        "## 结论摘要",
        "",
    ]
    accepted = [row for row in summaries if row.get("accepted")]
    if accepted:
        lines.append("- 通过 acceptance 的 Top-1 策略：" + ", ".join(row["subgroup"] for row in accepted))
    else:
        lines.append("- 没有 Top-1 策略同时满足 PnP、Layer-2 和 Layer-3 精度阈值。")
    lines.extend(
        [
            "- 该实验验证的是“已有几何匹配之后只拿 1 个候选做位姿”，不证明可以跳过重排。",
            "",
            "## 子组汇总",
            "",
            "| subgroup | accepted | PnP ok | best ok | Layer-2 mean m | Layer-2 delta m | Layer-3 RMSE m | Layer-3 delta m | reduced downstream s |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summaries:
        lines.append(
            "| {subgroup} | {accepted} | {pnp_ok} | {best_ok} | {l2} | {l2d} | {l3} | {l3d} | {time} |".format(
                subgroup=row["subgroup"],
                accepted=row["accepted"],
                pnp_ok=row["pnp_status_counts"].get("ok", 0),
                best_ok=row["best_pose_status_counts"].get("ok", 0),
                l2=format_optional(row.get("layer2_horizontal_error_m_mean")),
                l2d=format_optional(row.get("layer2_delta_m")),
                l3=format_optional(row.get("layer3_tiepoint_xy_error_rmse_m")),
                l3d=format_optional(row.get("layer3_delta_m")),
                time=format_optional(row.get("actual_reduced_downstream_time_seconds")),
            )
        )
    (out_root / "top1_pose_validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_optional(value: Any) -> str:
    if value in ("", None):
        return ""
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value)


def main() -> None:
    args = parse_args()
    g02_root = Path(args.g02_root)
    g03_root = Path(args.g03_root)
    out_root = Path(args.out_root)
    if args.overwrite and out_root.exists():
        resolved = out_root.resolve()
        expected_parent = MATRIX_ROOT.resolve()
        if expected_parent not in resolved.parents:
            raise SystemExit(f"refusing to delete unexpected output root: {resolved}")
        shutil.rmtree(out_root)
    ensure_dir(out_root)
    write_plan_md(out_root)

    base_roots = {"g02": g02_root, "g03": g03_root}
    all_selected: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for subgroup in SUBGROUPS:
        base_root = base_roots[subgroup["base_key"]]
        subgroup_root = out_root / subgroup["name"]
        selected = select_top1_candidates(base_root, subgroup)
        all_selected.extend(selected)
        ensure_dir(subgroup_root / "plan")
        write_csv(subgroup_root / "selected_candidates.csv", selected)
        pose_root = prepare_reduced_bundle(base_root, subgroup_root, overwrite=False)
        sampling_summary = filter_sampled_correspondences(base_root, pose_root, selected)
        steps = run_reduced_pose_and_validation(
            args.python_bin,
            base_root,
            subgroup_root,
            pose_root,
            selected,
            args.skip_validation,
            args.validation_timeout_seconds,
            args.dry_run,
        )
        summaries.append(summarize_subgroup(subgroup, subgroup_root, base_root, selected, sampling_summary, steps))

    write_csv(out_root / "top1_candidate_selection.csv", all_selected)
    write_csv(out_root / "top1_pose_validation_summary.csv", summaries)
    write_json(
        out_root / "top1_pose_validation_summary.json",
        {
            "generated_at_utc": utc_now(),
            "out_root": str(out_root),
            "gate_query_ids": GATE_QUERY_IDS,
            "subgroup_count": len(summaries),
            "summaries": summaries,
        },
    )
    write_json(
        out_root / "compare_against_g02_g03_summary.json",
        {
            "generated_at_utc": utc_now(),
            "g02_root": str(g02_root),
            "g03_root": str(g03_root),
            "summaries": summaries,
        },
    )
    write_report(out_root, summaries)
    print(out_root / "top1_pose_validation_summary.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run the new4 G01 CaiWangCun gate baseline without algorithm changes.

Purpose:
- create the new4 baseline experiment directory and plan document;
- call the existing CaiWangCun DOM+DSM full-replacement gate runner unchanged;
- summarize timing, accuracy, and acceptance files for later speed-optimization
  comparisons.

Main inputs:
- existing 009/010 query assets and CaiWangCun DOM/DSM source assets consumed
  by `run_nadir_009010_caiwangcun_fullreplace_gate_experiment.py`;
- the current project-local Ubuntu `.conda` Python environment.

Main outputs:
- `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/`
  `G01_baseline_current_pipeline`;
- `实验计划.md`, `timing_summary.json`, `accuracy_summary.json`,
  and `acceptance_summary.json`.

Applicable task constraints:
- query inputs are geolocation-metadata-free UAV images and are not assumed to
  be orthophotos;
- this baseline intentionally performs no RoMa reuse, no DOM+Z cache, no DSM
  parallelization, no resolution reduction, and no matcher replacement.
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
DEFAULT_EXPERIMENT_ROOT = (
    PROJECT_ROOT
    / "new4output"
    / "nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27"
    / "G01_baseline_current_pipeline"
)
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
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed-mosaic-root", default=str(DEFAULT_SEED_MOSAIC_ROOT))
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
    plan = f"""# ? 1 ??????????

## Summary

- ?????`G01_baseline_current_pipeline`
- ?????`{experiment_root.as_posix()}`
- ????????????????? CaiWangCun DOM+DSM ???? gate ???????????????????????
- ?????Ubuntu?????? `.conda/bin/python`
- Gate query?`{" / ".join(GATE_QUERY_IDS)}`

## Pipeline

- ?????? CaiWangCun DOM+DSM ???? gate ??????
- ????????????
  - ??? RoMa ?????
  - Pose ???????? `export_romav2_matches_batch_for_pose.py`?
  - DSM sampling ??????????????
  - ??? DOM+Z cache?
  - ??? DSM sampling?
  - ??????
  - ??? SIFTGPU?
- ???????`new3output/nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20`

## Outputs

- `romav2_rerank/`
- `retrieval/`
- `pose_v1_formal/`
- `logs/`
- `plan/`
- `timing_summary.json`
- `accuracy_summary.json`
- `acceptance_summary.json`

## Metrics

- ?????DINOv2 retrieval?RoMa v2 rerank?Pose ?? RoMa matches export?correspondence preparation?DSM sampling?PnP?scoring / summary?gate ????
- ?????best pose ok ??PnP candidate `ok / pnp_failed` ??DSM sampling ?????Layer-1 / Layer-2 / Layer-3 ???

## Acceptance

- gate ???????
- best pose ? `5/5 ok`?
- PnP ?? `100` ? candidate ???
- sampling ?? `500000` ??
- validation pipeline ??? `ok`?
- ???????????????????????????????????
"""
    (experiment_root / "????.md").write_text(plan, encoding="utf-8")


def seed_source_mosaic(experiment_root: Path, seed_mosaic_root: Path) -> None:
    source_root = experiment_root / "source_mosaic"
    ensure_dir(source_root)
    required = (
        "caiwangcun_ortho_0p14m_epsg32650.tif",
        "caiwangcun_dsm_0p14m_epsg32650.tif",
    )
    for name in required:
        src = seed_mosaic_root / name
        dst = source_root / name
        if not src.exists():
            raise SystemExit(f"missing seed mosaic asset: {src}")
        if not dst.exists():
            shutil.copy2(src, dst)


def seed_source_tile_links(experiment_root: Path) -> Path:
    """Create audit-only source tile links so the upstream gate preflight passes."""
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


def run_baseline(args: argparse.Namespace, experiment_root: Path) -> dict[str, Any]:
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
    ]
    for query_id in GATE_QUERY_IDS:
        command.extend(["--rerank-query-id", query_id])
    if args.dry_run:
        command.append("--dry-run")
    log_path = experiment_root.parent / "G01_baseline_current_pipeline_wrapper.log"
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


def summarize_outputs(experiment_root: Path, wrapper_run: dict[str, Any] | None) -> None:
    pose_root = experiment_root / "pose_v1_formal"
    suite_root = pose_root / "eval_pose_validation_suite_caiwangcun_truth"
    phase_summary = load_json(pose_root / "summary" / "phase_gate_summary.json")
    validation_summary = load_json(suite_root / "phase_gate_summary.json")
    rerank_timing = load_json(experiment_root / "romav2_rerank" / "timing" / "romav2_rerank_internal.json")

    pnp_rows = load_csv(pose_root / "pnp" / "pnp_results.csv")
    best_rows = load_csv(pose_root / "summary" / "per_query_best_pose.csv")
    sampled_rows = load_csv(pose_root / "sampling" / "sampled_correspondences.csv")

    ortho = validation_summary.get("overall_ortho_accuracy", {})
    pose_vs_at = validation_summary.get("overall_pose_vs_at", {})
    tiepoint = validation_summary.get("overall_tiepoint_ground_error", {})

    stages = {row.get("stage", ""): row for row in phase_summary.get("stages", [])}
    timing_summary = {
        "experiment_root": str(experiment_root),
        "generated_at_utc": utc_now(),
        "wrapper_elapsed_seconds": None if wrapper_run is None else wrapper_run.get("elapsed_seconds"),
        "wrapper_returncode": None if wrapper_run is None else wrapper_run.get("returncode"),
        "romav2_rerank_elapsed_seconds": rerank_timing.get("elapsed_seconds"),
        "pose_export_romav2_matches_seconds": stages.get("export_romav2_matches_batch_for_pose", {}).get("elapsed_seconds"),
        "prepare_pose_correspondences_seconds": stages.get("prepare_pose_correspondences", {}).get("elapsed_seconds"),
        "sample_dsm_for_dom_points_seconds": stages.get("sample_dsm_for_dom_points", {}).get("elapsed_seconds"),
        "run_pnp_baseline_seconds": stages.get("run_pnp_baseline", {}).get("elapsed_seconds"),
        "score_formal_pose_results_seconds": stages.get("score_formal_pose_results", {}).get("elapsed_seconds"),
        "pose_phase_stages": phase_summary.get("stages", []),
        "note": "DINOv2 feature/retrieval timing is retained in the existing gate logs when no structured timing JSON is emitted by that stage.",
    }
    write_json(experiment_root / "timing_summary.json", timing_summary)

    accuracy_summary = {
        "experiment_root": str(experiment_root),
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

    acceptance_checks = {
        "wrapper_returncode_zero": wrapper_run is None or wrapper_run.get("returncode") == 0,
        "best_pose_5_of_5_ok": accuracy_summary["best_pose_status_counts"].get("ok") == 5,
        "pnp_row_count_100": accuracy_summary["pnp_row_count"] == 100,
        "sampling_row_count_500000": accuracy_summary["sampling_row_count"] == 500000,
        "validation_pipeline_ok": accuracy_summary["validation_pipeline_status"] == "ok",
    }
    write_json(
        experiment_root / "acceptance_summary.json",
        {
            "experiment_root": str(experiment_root),
            "generated_at_utc": utc_now(),
            "checks": acceptance_checks,
            "accepted": all(acceptance_checks.values()),
            "accuracy_summary": "accuracy_summary.json",
            "timing_summary": "timing_summary.json",
        },
    )


def main() -> None:
    args = parse_args()
    experiment_root = Path(args.experiment_root)
    if args.overwrite and experiment_root.exists():
        shutil.rmtree(experiment_root)
    ensure_dir(experiment_root)
    write_plan_md(experiment_root)
    seed_source_mosaic(experiment_root, Path(args.seed_mosaic_root))
    wrapper_run = None
    if not args.skip_run:
        wrapper_run = run_baseline(args, experiment_root)
        if int(wrapper_run["returncode"]) != 0:
            write_json(experiment_root / "wrapper_failed_summary.json", wrapper_run)
            raise SystemExit(int(wrapper_run["returncode"]))
    if not args.dry_run:
        summarize_outputs(experiment_root, wrapper_run)
    print(experiment_root)


if __name__ == "__main__":
    main()

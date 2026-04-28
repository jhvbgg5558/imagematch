#!/usr/bin/env python3
"""Run the 009/010 ODM-truth gate at multiple ODM DSM resolutions.

Purpose:
- keep the locked 009/010 runtime retrieval task unchanged while rerunning the
  ODM-truth-only gate with several ODM DSM raster resolutions;
- compare `5 m`, `3 m`, and `2 m` ODM DSM settings under the same `0.1 m`
  DOM-truth validation grid;
- decide the highest practical ODM DSM precision that still supports the
  current formal pose gate on the available ODM LAZ assets.

Main inputs:
- `scripts/run_nadir_009010_odmrefresh_and_sattruth_experiment.py`;
- reused retrieval assets from
  `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/`;
- ODM flight assets resolved by the override-manifest builder.

Main outputs:
- three isolated gate roots under `new3output/`;
- an aggregate sweep summary JSON and CSV under
  `new3output/odm_dsm_gate_resolution_sweep_2026-04-17/`.

Applicable task constraints:
- DOM truth stays fixed at `0.1 m`;
- only ODM DSM resolution changes across runs;
- only the `gate` phase is executed;
- no suite Word reports or cross-suite comparison reports are generated.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REUSE_ROOT = PROJECT_ROOT / "new2output" / "nadir_009010_dinov2_romav2_pose_2026-04-10"
DEFAULT_SWEEP_ROOT = PROJECT_ROOT / "new3output" / "odm_dsm_gate_resolution_sweep_2026-04-17"
ORCHESTRATOR = PROJECT_ROOT / "scripts" / "run_nadir_009010_odmrefresh_and_sattruth_experiment.py"
DEFAULT_RESOLUTIONS = (5.0, 3.0, 2.0)


@dataclass(frozen=True)
class SweepCase:
    dsm_resolution_m: float
    experiment_root: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--reuse-retrieval-root", default=str(DEFAULT_REUSE_ROOT))
    parser.add_argument("--target-resolution-m", type=float, default=0.1)
    parser.add_argument("--resolutions-m", nargs="+", type=float, default=list(DEFAULT_RESOLUTIONS))
    parser.add_argument("--sweep-root", default=str(DEFAULT_SWEEP_ROOT))
    parser.add_argument("--root-date-tag", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json_if_exists(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_root_date_tag(args: argparse.Namespace) -> str:
    if args.root_date_tag:
        return args.root_date_tag
    return datetime.now().strftime("%Y-%m-%d")


def root_name_for_resolution(resolution_m: float, root_date_tag: str) -> str:
    if float(resolution_m).is_integer():
        value = str(int(resolution_m))
    else:
        value = str(resolution_m).replace(".", "p")
    return f"nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_{value}m_gate_{root_date_tag}"


def build_cases(args: argparse.Namespace) -> list[SweepCase]:
    root_date_tag = resolve_root_date_tag(args)
    seen: set[float] = set()
    cases: list[SweepCase] = []
    for resolution_m in args.resolutions_m:
        if resolution_m <= 0:
            raise SystemExit(f"invalid resolution: {resolution_m}")
        if resolution_m in seen:
            continue
        seen.add(resolution_m)
        cases.append(
            SweepCase(
                dsm_resolution_m=resolution_m,
                experiment_root=PROJECT_ROOT / "new3output" / root_name_for_resolution(resolution_m, root_date_tag),
            )
        )
    cases.sort(key=lambda item: item.dsm_resolution_m, reverse=True)
    return cases


def run_case(args: argparse.Namespace, case: SweepCase, sweep_log: Path) -> None:
    command = [
        args.python_bin,
        str(ORCHESTRATOR),
        "--phase",
        "odm_truth_only",
        "--validation-phase",
        "gate",
        "--experiment-root",
        str(case.experiment_root),
        "--reuse-retrieval-root",
        str(Path(args.reuse_retrieval_root)),
        "--target-resolution-m",
        str(args.target_resolution_m),
        "--dsm-target-resolution-m",
        str(case.dsm_resolution_m),
        "--skip-reports",
        "--device",
        args.device,
    ]
    if args.overwrite:
        command.append("--overwrite")
    rendered = " ".join(command)
    print("+", rendered)
    with sweep_log.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_now()}] + {rendered}\n")
    if args.dry_run:
        return
    with sweep_log.open("a", encoding="utf-8") as handle:
        subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )


def summarize_case(case: SweepCase) -> dict[str, object]:
    pose_root = case.experiment_root / "pose_v1_formal"
    dsm_summary_path = pose_root / "dsm_cache" / "rasters" / "_summary.json"
    sampling_summary_path = pose_root / "sampling" / "sampling_summary.json"
    pose_summary_path = pose_root / "summary" / "pose_overall_summary.json"
    per_query_best_pose_path = pose_root / "summary" / "per_query_best_pose.csv"
    suite_summary_path = pose_root / "eval_pose_validation_suite_odm_truth" / "phase_gate_summary.json"

    dsm_summary = load_json_if_exists(dsm_summary_path)
    sampling_summary = load_json_if_exists(sampling_summary_path)
    pose_summary = load_json_if_exists(pose_summary_path)
    suite_summary = load_json_if_exists(suite_summary_path)

    dsm_planned = int(dsm_summary.get("planned_count", 0) or 0)
    dsm_built = int(dsm_summary.get("built_count", 0) or 0)
    dsm_failed = int(dsm_summary.get("failed_count", 0) or 0)

    sampling_status_counts = sampling_summary.get("status_counts", {}) or {}
    sampling_row_count = int(sampling_summary.get("row_count", 0) or 0)
    sampling_nodata = int(sampling_status_counts.get("nodata", 0) or 0)
    sampling_ok = int(sampling_status_counts.get("ok", 0) or 0)
    sampling_unstable = int(sampling_status_counts.get("unstable_local_height", 0) or 0)
    sampling_nodata_ratio = (sampling_nodata / sampling_row_count) if sampling_row_count else None

    best_status_counts = pose_summary.get("best_status_counts", {}) or {}
    score_status_counts = pose_summary.get("score_status_counts", {}) or {}
    gate_ok_count = int(best_status_counts.get("ok", 0) or 0)
    gate_dsm_nodata_best = int(best_status_counts.get("dsm_nodata_too_high", 0) or 0)
    score_dsm_nodata = int(score_status_counts.get("dsm_nodata_too_high", 0) or 0)
    score_row_count = int(pose_summary.get("score_row_count", 0) or 0)

    flow_runnable = (
        dsm_planned > 0
        and dsm_built == dsm_planned
        and dsm_failed == 0
        and per_query_best_pose_path.exists()
        and bool(pose_summary)
        and bool(suite_summary)
    )
    pose_gate_valid = (
        gate_ok_count > 0
        and gate_dsm_nodata_best < sum(int(v or 0) for v in best_status_counts.values())
        and (score_row_count == 0 or score_dsm_nodata < score_row_count)
        and (sampling_nodata_ratio is None or sampling_nodata_ratio < 0.95)
    )
    supported = flow_runnable and pose_gate_valid

    return {
        "dsm_resolution_m": case.dsm_resolution_m,
        "experiment_root": str(case.experiment_root),
        "artifacts": {
            "dsm_summary_json": str(dsm_summary_path),
            "sampling_summary_json": str(sampling_summary_path),
            "pose_overall_summary_json": str(pose_summary_path),
            "per_query_best_pose_csv": str(per_query_best_pose_path),
            "validation_phase_gate_summary_json": str(suite_summary_path),
        },
        "flow_runnable": flow_runnable,
        "pose_gate_valid": pose_gate_valid,
        "supported": supported,
        "dsm": {
            "planned_count": dsm_planned,
            "built_count": dsm_built,
            "failed_count": dsm_failed,
            "target_resolution_m": dsm_summary.get("target_resolution_m"),
            "filled_cell_count": dsm_summary.get("filled_cell_count"),
        },
        "sampling": {
            "row_count": sampling_row_count,
            "nodata_count": sampling_nodata,
            "ok_count": sampling_ok,
            "unstable_local_height_count": sampling_unstable,
            "nodata_ratio": sampling_nodata_ratio,
        },
        "pose": {
            "query_count": pose_summary.get("query_count"),
            "score_row_count": score_row_count,
            "best_status_counts": best_status_counts,
            "score_status_counts": score_status_counts,
        },
        "validation": {
            "pipeline_status": suite_summary.get("pipeline_status"),
            "query_count": suite_summary.get("query_count"),
            "overall_ortho_accuracy": suite_summary.get("overall_ortho_accuracy"),
            "overall_pose_vs_at": suite_summary.get("overall_pose_vs_at"),
            "overall_tiepoint_ground_error": suite_summary.get("overall_tiepoint_ground_error"),
        },
        "judgement": "supported" if supported else "not_supported",
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    fieldnames = [
        "dsm_resolution_m",
        "flow_runnable",
        "pose_gate_valid",
        "supported",
        "dsm_planned_count",
        "dsm_built_count",
        "dsm_failed_count",
        "sampling_row_count",
        "sampling_nodata_count",
        "sampling_ok_count",
        "sampling_nodata_ratio",
        "pose_best_status_counts",
        "pose_score_status_counts",
        "validation_pipeline_status",
        "judgement",
        "experiment_root",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "dsm_resolution_m": row["dsm_resolution_m"],
                    "flow_runnable": row["flow_runnable"],
                    "pose_gate_valid": row["pose_gate_valid"],
                    "supported": row["supported"],
                    "dsm_planned_count": row["dsm"]["planned_count"],
                    "dsm_built_count": row["dsm"]["built_count"],
                    "dsm_failed_count": row["dsm"]["failed_count"],
                    "sampling_row_count": row["sampling"]["row_count"],
                    "sampling_nodata_count": row["sampling"]["nodata_count"],
                    "sampling_ok_count": row["sampling"]["ok_count"],
                    "sampling_nodata_ratio": row["sampling"]["nodata_ratio"],
                    "pose_best_status_counts": json.dumps(row["pose"]["best_status_counts"], ensure_ascii=False),
                    "pose_score_status_counts": json.dumps(row["pose"]["score_status_counts"], ensure_ascii=False),
                    "validation_pipeline_status": row["validation"]["pipeline_status"],
                    "judgement": row["judgement"],
                    "experiment_root": row["experiment_root"],
                }
            )


def main() -> None:
    args = parse_args()
    sweep_root = Path(args.sweep_root)
    ensure_dir(sweep_root / "logs")
    sweep_log = sweep_root / "logs" / "run_odm_dsm_gate_resolution_sweep.log"
    cases = build_cases(args)

    all_rows: list[dict[str, object]] = []
    for case in cases:
        run_case(args, case, sweep_log)
        all_rows.append(summarize_case(case))

    supported_rows = [row for row in all_rows if row["supported"]]
    highest_supported = min(supported_rows, key=lambda row: float(row["dsm_resolution_m"])) if supported_rows else None

    aggregate = {
        "sweep_root": str(sweep_root),
        "reuse_retrieval_root": str(Path(args.reuse_retrieval_root)),
        "target_resolution_m": float(args.target_resolution_m),
        "resolutions_m": [case.dsm_resolution_m for case in cases],
        "completed_at_utc": utc_now(),
        "cases": all_rows,
        "highest_supported_dsm_resolution_m": highest_supported["dsm_resolution_m"] if highest_supported else None,
        "highest_supported_experiment_root": highest_supported["experiment_root"] if highest_supported else None,
        "overall_judgement": (
            f"highest practical supported ODM DSM resolution is about {highest_supported['dsm_resolution_m']} m"
            if highest_supported
            else "no stable gate support was observed at 5 m, 3 m, or 2 m"
        ),
    }

    aggregate_json = sweep_root / "aggregate_summary.json"
    ensure_dir(aggregate_json.parent)
    aggregate_json.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(sweep_root / "aggregate_summary.csv", all_rows)
    print(aggregate_json)


if __name__ == "__main__":
    main()

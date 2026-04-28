#!/usr/bin/env python3
"""Run the formal pose-v1 phase gate on a small query subset.

Purpose:
- build the formal candidate DSM rasters if needed;
- run the locked formal pose chain on 3-5 representative queries before
  expanding to the full 40-query formal set;
- write a compact gate summary with stage-level counts and failures.

Main inputs:
- `manifest/pose_manifest.json`
- `input/formal_query_manifest.csv`
- `new2output/N30E114.hgt`

Main outputs:
- stage outputs under the active formal bundle root
- `summary/phase_gate_summary.json`

Applicable task constraints:
- phase gate must use runtime assets only;
- query truth is offline evaluation only and is not used to select candidates;
- default query selection should cover multiple flights before filling to 5.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"
DEFAULT_SOURCE_HGT = PROJECT_ROOT / "new2output" / "N30E114.hgt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--source-hgt", default=str(DEFAULT_SOURCE_HGT))
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--max-query-count", type=int, default=5)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--setting", default="satast")
    parser.add_argument("--sample-count", type=int, default=5000)
    parser.add_argument("--max-rank", type=int, default=20)
    parser.add_argument("--skip-dsm-build", action="store_true")
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def choose_gate_queries(query_manifest_csv: Path, explicit_query_ids: list[str], max_query_count: int) -> list[str]:
    if explicit_query_ids:
        return explicit_query_ids[:max_query_count]
    rows = load_csv(query_manifest_csv)
    per_flight: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        per_flight[row.get("flight_id", "")].append(row["query_id"])
    selected: list[str] = []
    for flight_id in sorted(per_flight):
        if per_flight[flight_id]:
            selected.append(per_flight[flight_id][0])
        if len(selected) >= max_query_count:
            return selected[:max_query_count]
    for row in rows:
        if row["query_id"] not in selected:
            selected.append(row["query_id"])
        if len(selected) >= max_query_count:
            break
    return selected[:max_query_count]


def run_stage(command: list[str], stage_name: str) -> dict[str, object]:
    started = time.time()
    completed = subprocess.run(command, cwd=str(PROJECT_ROOT), check=True, capture_output=True, text=True)
    return {
        "stage": stage_name,
        "elapsed_seconds": round(time.time() - started, 6),
        "stdout_tail": completed.stdout.strip().splitlines()[-5:],
        "stderr_tail": completed.stderr.strip().splitlines()[-5:],
        "command": command,
    }


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    summary_dir = bundle_root / "summary"
    logs_dir = bundle_root / "logs"
    ensure_dir(summary_dir)
    ensure_dir(logs_dir)

    query_manifest_csv = bundle_root / "input" / "formal_query_manifest.csv"
    gate_query_ids = choose_gate_queries(query_manifest_csv, args.query_id, args.max_query_count)
    if not gate_query_ids:
        raise SystemExit("no gate queries selected")

    stages: list[dict[str, object]] = []
    base_cmd = [sys.executable]

    if not args.skip_dsm_build:
        stages.append(
            run_stage(
                base_cmd
                + [
                    str(PROJECT_ROOT / "scripts" / "build_formal_dsm_rasters_from_hgt.py"),
                    "--bundle-root",
                    str(bundle_root),
                    "--source-hgt",
                    str(Path(args.source_hgt)),
                ],
                "build_formal_dsm_rasters_from_hgt",
            )
        )

    match_cmd = base_cmd + [
        str(PROJECT_ROOT / "scripts" / "export_romav2_matches_batch_for_pose.py"),
        "--bundle-root",
        str(bundle_root),
        "--device",
        args.device,
        "--setting",
        args.setting,
        "--sample-count",
        str(args.sample_count),
        "--max-rank",
        str(args.max_rank),
    ]
    for query_id in gate_query_ids:
        match_cmd.extend(["--query-id", query_id])
    stages.append(run_stage(match_cmd, "export_romav2_matches_batch_for_pose"))

    stages.append(
        run_stage(
            base_cmd
            + [
                str(PROJECT_ROOT / "scripts" / "prepare_pose_correspondences.py"),
                "--bundle-root",
                str(bundle_root),
                "--match-csv",
                str(bundle_root / "matches" / "roma_matches.csv"),
            ],
            "prepare_pose_correspondences",
        )
    )
    stages.append(
        run_stage(
            base_cmd
            + [
                str(PROJECT_ROOT / "scripts" / "sample_dsm_for_dom_points.py"),
                "--bundle-root",
                str(bundle_root),
            ],
            "sample_dsm_for_dom_points",
        )
    )
    stages.append(
        run_stage(
            base_cmd
            + [
                str(PROJECT_ROOT / "scripts" / "run_pnp_baseline.py"),
                "--bundle-root",
                str(bundle_root),
            ],
            "run_pnp_baseline",
        )
    )
    stages.append(
        run_stage(
            base_cmd
            + [
                str(PROJECT_ROOT / "scripts" / "score_pose_candidates.py"),
                "--bundle-root",
                str(bundle_root),
            ],
            "score_pose_candidates",
        )
    )
    stages.append(
        run_stage(
            base_cmd
            + [
                str(PROJECT_ROOT / "scripts" / "summarize_pose_results.py"),
                "--bundle-root",
                str(bundle_root),
            ],
            "summarize_pose_results",
        )
    )

    phase_gate_summary = {
        "bundle_root": str(bundle_root),
        "gate_query_ids": gate_query_ids,
        "stage_count": len(stages),
        "stages": stages,
        "artifacts": {
            "matches_summary": str(bundle_root / "matches" / "roma_match_summary.json"),
            "prepare_summary": str(bundle_root / "correspondences" / "prepare_summary.json"),
            "sampling_summary": str(bundle_root / "sampling" / "sampling_summary.json"),
            "pnp_summary": str(bundle_root / "pnp" / "pnp_summary.json"),
            "score_summary": str(bundle_root / "scores" / "score_summary.json"),
            "overall_summary": str(bundle_root / "summary" / "pose_overall_summary.json"),
        },
        "generated_at_unix": time.time(),
    }
    write_json(summary_dir / "phase_gate_summary.json", phase_gate_summary)
    (logs_dir / "run_formal_pose_phase_gate.log").write_text(
        "\n".join(
            [
                "stage=run_formal_pose_phase_gate",
                f"gate_query_ids={gate_query_ids}",
                f"stage_count={len(stages)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(summary_dir / "phase_gate_summary.json")


if __name__ == "__main__":
    main()

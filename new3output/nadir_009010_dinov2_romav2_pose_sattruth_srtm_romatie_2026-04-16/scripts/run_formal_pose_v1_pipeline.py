#!/usr/bin/env python3
"""Run the formal pose-v1 pipeline for a sample gate or full formal pass.

Purpose:
- orchestrate the locked formal pose-v1 stages under `new2output/pose_v1_formal`;
- support a small-sample gate first, then a full formal run with the same
  stage order and output conventions.

Main inputs:
- `manifest/pose_manifest.json`;
- formal query/candidate/DSM preparation assets under `pose_v1_formal`;
- raw SRTM HGT source if DSM rasters still need materialization.

Main outputs:
- standard stage outputs under `matches/`, `correspondences/`, `sampling/`,
  `pnp/`, and `summary/`;
- `summary/phase_gate_summary.json`.

Applicable task constraints:
- sample mode uses only runtime query/candidate assets and does not use truth
  to choose runtime pairs;
- query selection for the gate is deterministic and flight-aware by default;
- the stage order is fixed as RoMa -> correspondence -> DSM sampling -> PnP.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--phase", choices=("sample", "full"), default="sample")
    parser.add_argument("--manifest-json", default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--sample-query-count", type=int, default=5)
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--min-rank", type=int, default=1)
    parser.add_argument("--max-rank", type=int, default=20)
    parser.add_argument("--max-pairs", type=int, default=0)
    parser.add_argument("--sample-count", type=int, default=5000)
    parser.add_argument("--skip-dsm-build", action="store_true")
    parser.add_argument("--source-hgt", default=None)
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--score-script", default=None)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def choose_sample_queries(queries: list[dict[str, object]], limit: int) -> list[str]:
    selected: list[str] = []
    seen_flights: set[str] = set()
    for row in queries:
        query_id = str(row["query_id"])
        flight_id = str(row.get("flight_id", ""))
        if flight_id and flight_id not in seen_flights:
            selected.append(query_id)
            seen_flights.add(flight_id)
        if len(selected) >= limit:
            return selected
    for row in queries:
        query_id = str(row["query_id"])
        if query_id not in selected:
            selected.append(query_id)
        if len(selected) >= limit:
            break
    return selected


def grouped_status_counts(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    return dict(Counter(str(row.get(key, "")) for row in rows))


def run_step(command: list[str], cwd: Path) -> dict[str, object]:
    started = time.time()
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "elapsed_seconds": time.time() - started,
    }


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    manifest_path = Path(args.manifest_json) if args.manifest_json else bundle_root / "manifest" / "pose_manifest.json"
    manifest = load_json(manifest_path)

    query_ids = list(args.query_id)
    if not query_ids:
        if args.phase == "sample":
            query_ids = choose_sample_queries(list(manifest.get("queries", [])), args.sample_query_count)
        else:
            query_ids = [str(row["query_id"]) for row in manifest.get("queries", [])]

    stage_runs: list[dict[str, object]] = []
    if not args.skip_dsm_build:
        source_hgt = Path(args.source_hgt) if args.source_hgt else PROJECT_ROOT / "new2output" / "N30E114.hgt"
        stage_runs.append(
            {
                "stage": "materialize_formal_dsm_rasters",
                **run_step(
                    [
                        args.python_exe,
                        str(PROJECT_ROOT / "scripts" / "materialize_formal_dsm_rasters.py"),
                        "--bundle-root",
                        str(bundle_root),
                        "--source-hgt",
                        str(source_hgt),
                    ],
                    PROJECT_ROOT,
                ),
            }
        )

    roma_cmd = [
        args.python_exe,
        str(PROJECT_ROOT / "scripts" / "export_romav2_matches_batch_for_pose.py"),
        "--bundle-root",
        str(bundle_root),
        "--device",
        args.device,
        "--sample-count",
        str(args.sample_count),
        "--min-rank",
        str(args.min_rank),
        "--max-rank",
        str(args.max_rank),
    ]
    if args.max_pairs > 0:
        roma_cmd.extend(["--max-pairs", str(args.max_pairs)])
    for query_id in query_ids:
        roma_cmd.extend(["--query-id", query_id])
    stage_runs.append({"stage": "export_romav2_matches_batch_for_pose", **run_step(roma_cmd, PROJECT_ROOT)})

    stage_runs.append(
        {
            "stage": "prepare_pose_correspondences",
            **run_step(
                [
                    args.python_exe,
                    str(PROJECT_ROOT / "scripts" / "prepare_pose_correspondences.py"),
                    "--bundle-root",
                    str(bundle_root),
                    "--manifest-json",
                    str(manifest_path),
                    "--match-csv",
                    str(bundle_root / "matches" / "roma_matches.csv"),
                ],
                PROJECT_ROOT,
            ),
        }
    )
    stage_runs.append(
        {
            "stage": "sample_dsm_for_dom_points",
            **run_step(
                [
                    args.python_exe,
                    str(PROJECT_ROOT / "scripts" / "sample_dsm_for_dom_points.py"),
                    "--bundle-root",
                    str(bundle_root),
                    "--manifest-json",
                    str(manifest_path),
                    "--correspondences-csv",
                    str(bundle_root / "correspondences" / "pose_correspondences.csv"),
                ],
                PROJECT_ROOT,
            ),
        }
    )
    stage_runs.append(
        {
            "stage": "run_pnp_baseline",
            **run_step(
                [
                    args.python_exe,
                    str(PROJECT_ROOT / "scripts" / "run_pnp_baseline.py"),
                    "--bundle-root",
                    str(bundle_root),
                    "--manifest-json",
                    str(manifest_path),
                    "--sampled-correspondences-csv",
                    str(bundle_root / "sampling" / "sampled_correspondences.csv"),
                ],
                PROJECT_ROOT,
            ),
        }
    )

    score_script = Path(args.score_script) if args.score_script else PROJECT_ROOT / "scripts" / "score_formal_pose_results.py"
    if score_script.exists():
        stage_runs.append(
            {
                "stage": "score_formal_pose_results",
                **run_step(
                    [
                        args.python_exe,
                        str(score_script),
                        "--bundle-root",
                        str(bundle_root),
                        "--pnp-results-csv",
                        str(bundle_root / "pnp" / "pnp_results.csv"),
                    ],
                    PROJECT_ROOT,
                ),
            }
        )

    matches_path = bundle_root / "matches" / "roma_matches.csv"
    corr_path = bundle_root / "correspondences" / "pose_correspondences.csv"
    sampling_path = bundle_root / "sampling" / "sampled_correspondences.csv"
    pnp_path = bundle_root / "pnp" / "pnp_results.csv"
    dsm_summary_path = bundle_root / "dsm_cache" / "rasters" / "_summary.json"

    matches_rows = load_csv(matches_path) if matches_path.exists() and matches_path.stat().st_size > 0 else []
    corr_rows = load_csv(corr_path) if corr_path.exists() and corr_path.stat().st_size > 0 else []
    sampling_rows = load_csv(sampling_path) if sampling_path.exists() and sampling_path.stat().st_size > 0 else []
    pnp_rows = load_csv(pnp_path) if pnp_path.exists() and pnp_path.stat().st_size > 0 else []

    payload = {
        "bundle_root": str(bundle_root),
        "phase": args.phase,
        "query_ids": query_ids,
        "query_count": len(query_ids),
        "matches": {"path": str(matches_path), "row_count": len(matches_rows)},
        "correspondences": {
            "path": str(corr_path),
            "row_count": len(corr_rows),
            "status_counts": grouped_status_counts(corr_rows, "match_status") if corr_rows else {},
        },
        "sampling": {
            "path": str(sampling_path),
            "row_count": len(sampling_rows),
            "status_counts": grouped_status_counts(sampling_rows, "sample_status") if sampling_rows else {},
        },
        "pnp": {
            "path": str(pnp_path),
            "row_count": len(pnp_rows),
            "status_counts": grouped_status_counts(pnp_rows, "status") if pnp_rows else {},
        },
        "dsm": load_json(dsm_summary_path) if dsm_summary_path.exists() else {},
        "stages": stage_runs,
        "generated_at_unix": time.time(),
    }
    write_json(bundle_root / "summary" / "phase_gate_summary.json", payload)
    print(bundle_root / "summary" / "phase_gate_summary.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Summarize Baseline v1 pose outputs into explicit success / failure buckets.

Purpose:
- aggregate the PnP and candidate-score outputs into per-query, per-flight, and
  overall summaries;
- keep the `applicable_success`, `applicable_failure`, and `not_applicable_v1`
  buckets explicit for later documentation and review.

Main inputs:
- `scores/pose_candidate_scores.csv`
- `pnp/pnp_results.csv`
- the canonical manifest JSON for query metadata

Main outputs:
- `summary/pose_overall_summary.json`
- `summary/pose_per_query.csv`
- `summary/pose_per_flight.csv`
- `summary/pose_failure_breakdown.csv`
- `logs/summarize_pose_results.log`

Applicable task constraints:
- query is a single arbitrary UAV image;
- query has no geographic metadata;
- query is not guaranteed to be orthophoto;
- summary rows must preserve the locked v1 failure classes instead of merging
  them into a single generic failure rate.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--manifest-json", default=None)
    parser.add_argument("--scores-csv", default=None)
    parser.add_argument("--pnp-results-csv", default=None)
    parser.add_argument("--out-dir", default=None)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def as_float(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    manifest_path = Path(args.manifest_json) if args.manifest_json else bundle_root / "manifest" / "pose_manifest.json"
    scores_path = Path(args.scores_csv) if args.scores_csv else bundle_root / "scores" / "pose_candidate_scores.csv"
    pnp_path = Path(args.pnp_results_csv) if args.pnp_results_csv else bundle_root / "pnp" / "pnp_results.csv"
    out_dir = Path(args.out_dir) if args.out_dir else bundle_root / "summary"
    logs_dir = bundle_root / "logs"
    ensure_dir(out_dir)
    ensure_dir(logs_dir)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    score_rows = load_csv(scores_path)
    pnp_rows = load_csv(pnp_path)
    if not score_rows:
        raise SystemExit(f"No candidate scores found: {scores_path}")
    if not pnp_rows:
        raise SystemExit(f"No PnP rows found: {pnp_path}")

    pnp_by_pair = {(row["query_id"], row["candidate_id"]): row for row in pnp_rows}
    queries = {row["query_id"]: row for row in manifest.get("queries", [])}
    score_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in score_rows:
        score_groups[row["query_id"]].append(row)

    per_query_rows: list[dict[str, object]] = []
    per_flight_rows: list[dict[str, object]] = []
    best_status_counts: Counter[str] = Counter()
    overall_counts: Counter[str] = Counter()
    success_reproj_errors: list[float] = []
    success_inlier_ratios: list[float] = []

    for query_id, rows in score_groups.items():
        rows = sorted(rows, key=lambda row: float(row["score"]), reverse=True)
        best = rows[0]
        pnp_row = pnp_by_pair.get((query_id, best["candidate_id"]))
        status = pnp_row["status"] if pnp_row else "missing_pnp_row"
        if status == "ok":
            bucket = "applicable_success"
            success_reproj_errors.append(as_float(pnp_row.get("reproj_error_refined_mean"), as_float(pnp_row.get("reproj_error_mean"), 0.0)))
            success_inlier_ratios.append(as_float(pnp_row.get("inlier_ratio")))
        elif status in {
            "intrinsics_missing",
            "insufficient_2d3d_points",
            "dsm_coverage_insufficient",
            "dsm_nodata_too_high",
        }:
            bucket = "not_applicable_v1"
        else:
            bucket = "applicable_failure"

        overall_counts[bucket] += 1
        best_status_counts[status] += 1
        query_meta = queries.get(query_id, {})
        per_query_rows.append(
            {
                "query_id": query_id,
                "flight_id": query_meta.get("flight_id", ""),
                "best_candidate_id": best["candidate_id"],
                "best_score": best["score"],
                "best_status": status,
                "bucket": bucket,
                "best_inlier_count": pnp_row.get("inlier_count", "") if pnp_row else "",
                "best_inlier_ratio": pnp_row.get("inlier_ratio", "") if pnp_row else "",
                "best_reproj_error": pnp_row.get("reproj_error_refined_mean", pnp_row.get("reproj_error_mean", "")) if pnp_row else "",
                "best_pose_penalty": pnp_row.get("pose_penalty", "") if pnp_row else "",
                "candidate_count": len(rows),
            }
        )

    by_flight: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in per_query_rows:
        by_flight[row["flight_id"]].append(row)
    for flight_id, rows in by_flight.items():
        flight_total = len(rows)
        flight_success = sum(1 for row in rows if row["bucket"] == "applicable_success")
        flight_failure = sum(1 for row in rows if row["bucket"] == "applicable_failure")
        flight_not_applicable = sum(1 for row in rows if row["bucket"] == "not_applicable_v1")
        per_flight_rows.append(
            {
                "flight_id": flight_id,
                "query_count": flight_total,
                "applicable_success": flight_success,
                "applicable_failure": flight_failure,
                "not_applicable_v1": flight_not_applicable,
                "success_rate_on_applicable": float(flight_success) / max(1, flight_success + flight_failure),
            }
        )

    status_breakdown_rows = [
        {"status": status, "count": count}
        for status, count in sorted(best_status_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    all_status_counts = Counter(row["status"] for row in pnp_rows)
    failure_breakdown_rows = [
        {
            "status": status,
            "count": count,
            "category": (
                "success"
                if status == "ok"
                else "not_applicable_v1"
                if status in {"intrinsics_missing", "insufficient_2d3d_points", "dsm_coverage_insufficient", "dsm_nodata_too_high"}
                else "failure"
            ),
        }
        for status, count in sorted(all_status_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    write_csv(out_dir / "pose_per_query.csv", per_query_rows)
    write_csv(out_dir / "per_query_best_pose.csv", per_query_rows)
    write_csv(out_dir / "pose_per_flight.csv", per_flight_rows)
    write_csv(out_dir / "pose_status_breakdown.csv", status_breakdown_rows)
    write_csv(out_dir / "pose_failure_breakdown.csv", failure_breakdown_rows)
    write_json(
        out_dir / "pose_overall_summary.json",
        {
            "bundle_root": str(bundle_root),
            "manifest_json": str(manifest_path.resolve()),
            "scores_csv": str(scores_path.resolve()),
            "pnp_results_csv": str(pnp_path.resolve()),
            "query_count": len(per_query_rows),
            "bucket_counts": dict(overall_counts),
            "best_status_counts": dict(best_status_counts),
            "all_status_counts": dict(all_status_counts),
            "success_reproj_error_mean": float(sum(success_reproj_errors) / len(success_reproj_errors)) if success_reproj_errors else None,
            "success_inlier_ratio_mean": float(sum(success_inlier_ratios) / len(success_inlier_ratios)) if success_inlier_ratios else None,
            "generated_at_unix": time.time(),
        },
    )
    (logs_dir / "summarize_pose_results.log").write_text(
        "\n".join(
            [
                "stage=summarize_pose_results",
                f"bundle_root={bundle_root}",
                f"query_count={len(per_query_rows)}",
                f"bucket_counts={dict(overall_counts)}",
                f"best_status_counts={dict(best_status_counts)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(out_dir / "pose_overall_summary.json")


if __name__ == "__main__":
    main()

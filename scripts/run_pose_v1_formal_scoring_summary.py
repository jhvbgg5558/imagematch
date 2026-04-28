#!/usr/bin/env python3
"""Score and summarize formal Pose v1 PnP outputs.

Purpose:
- convert `pnp/pnp_results.csv` into a deterministic per-query candidate score;
- derive the formal best-pose summary used by the pose-v1 workflow;
- keep the scoring rule explicit and inspectable for later review.

Main inputs:
- `manifest/pose_manifest.json` for query metadata and expected query IDs;
- `pnp/pnp_results.csv` from the formal PnP stage.

Main outputs:
- `scores/pose_scores.csv`
- `summary/per_query_best_pose.csv`
- `summary/pose_overall_summary.json`
- optional supporting summaries under `summary/`
- `logs/run_pose_v1_formal_scoring_summary.log`

Applicable task constraints:
- query is a single arbitrary UAV image;
- query has no geographic metadata;
- query is not guaranteed to be orthophoto;
- this script only consumes PnP outputs and must not change the formal DSM or
  correspondence stages.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"
DEFAULT_SCORE_FORMULA = (
    "0.30*inlier_ratio + 0.25*coverage_score + 0.20*inlier_count_norm + "
    "0.10*elevation_span_norm - 0.10*reproj_error_norm - 0.05*pose_penalty"
)

NOT_APPLICABLE_STATUSES = {
    "intrinsics_missing",
    "insufficient_2d3d_points",
    "dsm_coverage_insufficient",
    "dsm_nodata_too_high",
    "missing_dsm_raster",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--manifest-json", default=None)
    parser.add_argument("--pnp-results-csv", default=None)
    parser.add_argument("--scores-dir", default=None)
    parser.add_argument("--summary-dir", default=None)
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


def normalize_min_max(value: float, min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return 0.0
    return max(0.0, min(1.0, (value - min_value) / (max_value - min_value)))


def safe_mean(values: list[float]) -> float | None:
    return float(statistics.mean(values)) if values else None


def safe_pstdev(values: list[float]) -> float | None:
    return float(statistics.pstdev(values)) if len(values) > 1 else 0.0 if values else None


def bucket_for_status(status: str) -> str:
    if status == "ok":
        return "applicable_success"
    if status in NOT_APPLICABLE_STATUSES:
        return "not_applicable_v1"
    return "applicable_failure"


def query_order_from_manifest(manifest: dict[str, object], pnp_rows: list[dict[str, str]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in manifest.get("queries", []):
        query_id = row.get("query_id", "")
        if query_id and query_id not in seen:
            ordered.append(query_id)
            seen.add(query_id)
    for row in pnp_rows:
        query_id = row.get("query_id", "")
        if query_id and query_id not in seen:
            ordered.append(query_id)
            seen.add(query_id)
    return ordered


def score_row(row: dict[str, str], norms: dict[str, float]) -> dict[str, object]:
    status = row.get("status", "")
    inlier_count = as_float(row.get("inlier_count"))
    inlier_ratio = as_float(row.get("inlier_ratio"))
    coverage_area = as_float(row.get("coverage_bbox_area_px2"))
    elevation_span = as_float(row.get("elevation_span_m"))
    reproj_error = as_float(row.get("reproj_error_refined_mean"), as_float(row.get("reproj_error_mean"), 0.0))
    pose_penalty = as_float(row.get("pose_penalty"), 1.0)

    if status == "ok":
        coverage_score = normalize_min_max(coverage_area, 0.0, norms["max_coverage_area"])
        inlier_count_norm = normalize_min_max(inlier_count, 0.0, norms["max_inlier_count"])
        elevation_span_norm = normalize_min_max(elevation_span, 0.0, norms["max_elevation_span"])
        reproj_error_norm = normalize_min_max(reproj_error, norms["min_reproj_error"], norms["max_reproj_error"])
    else:
        coverage_score = 0.0
        inlier_count_norm = 0.0
        elevation_span_norm = 0.0
        reproj_error_norm = 1.0
        pose_penalty = max(pose_penalty, 1.0)

    score = (
        0.30 * inlier_ratio
        + 0.25 * coverage_score
        + 0.20 * inlier_count_norm
        + 0.10 * elevation_span_norm
        - 0.10 * reproj_error_norm
        - 0.05 * pose_penalty
    )

    return {
        "query_id": row["query_id"],
        "candidate_id": row["candidate_id"],
        "status": status,
        "status_detail": row.get("status_detail", ""),
        "bucket": bucket_for_status(status),
        "candidate_rank": row.get("candidate_rank", ""),
        "total_correspondences": row.get("total_correspondences", ""),
        "valid_correspondences": row.get("valid_correspondences", ""),
        "ok_ratio": row.get("ok_ratio", ""),
        "nodata_ratio": row.get("nodata_ratio", ""),
        "inlier_count": f"{inlier_count:.6f}",
        "inlier_ratio": f"{inlier_ratio:.6f}",
        "coverage_bbox_area_px2": f"{coverage_area:.6f}",
        "coverage_score": f"{coverage_score:.6f}",
        "inlier_count_norm": f"{inlier_count_norm:.6f}",
        "elevation_span_m": f"{elevation_span:.6f}",
        "elevation_span_norm": f"{elevation_span_norm:.6f}",
        "reproj_error_m": f"{reproj_error:.6f}",
        "reproj_error_norm": f"{reproj_error_norm:.6f}",
        "pose_penalty": f"{pose_penalty:.6f}",
        "rvec": row.get("rvec", ""),
        "tvec": row.get("tvec", ""),
        "camera_center_x": row.get("camera_center_x", ""),
        "camera_center_y": row.get("camera_center_y", ""),
        "camera_center_z": row.get("camera_center_z", ""),
        "sample_status_breakdown": row.get("sample_status_breakdown", ""),
        "score": f"{score:.6f}",
    }


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    manifest_path = Path(args.manifest_json) if args.manifest_json else bundle_root / "manifest" / "pose_manifest.json"
    pnp_path = Path(args.pnp_results_csv) if args.pnp_results_csv else bundle_root / "pnp" / "pnp_results.csv"
    scores_dir = Path(args.scores_dir) if args.scores_dir else bundle_root / "scores"
    summary_dir = Path(args.summary_dir) if args.summary_dir else bundle_root / "summary"
    logs_dir = bundle_root / "logs"
    ensure_dir(scores_dir)
    ensure_dir(summary_dir)
    ensure_dir(logs_dir)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    pnp_rows = load_csv(pnp_path)
    if not pnp_rows:
        raise SystemExit(f"No PnP rows found: {pnp_path}")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pnp_rows:
        grouped[row["query_id"]].append(row)

    query_ids = query_order_from_manifest(manifest, pnp_rows)
    if not query_ids:
        query_ids = sorted(grouped)

    scored_rows: list[dict[str, object]] = []
    per_query_rows: list[dict[str, object]] = []
    per_flight_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()
    best_status_counts: Counter[str] = Counter()
    best_bucket_counts: Counter[str] = Counter()
    success_reproj_errors: list[float] = []
    success_inlier_ratios: list[float] = []
    success_scores: list[float] = []
    best_scores: list[float] = []

    query_meta = {row["query_id"]: row for row in manifest.get("queries", [])}

    for query_id in query_ids:
        rows = grouped.get(query_id, [])
        if not rows:
            query = query_meta.get(query_id, {})
            per_query_rows.append(
                {
                    "query_id": query_id,
                    "flight_id": query.get("flight_id", ""),
                    "candidate_count": 0,
                    "scored_candidate_count": 0,
                    "best_candidate_id": "",
                    "best_score": "",
                    "best_score_rank": "",
                    "best_status": "missing_pnp_rows",
                    "best_bucket": "applicable_failure",
                    "best_inlier_count": "",
                    "best_inlier_ratio": "",
                    "best_reproj_error": "",
                    "best_pose_penalty": "",
                    "best_coverage_bbox_area_px2": "",
                    "best_elevation_span_m": "",
                    "best_rvec": "",
                    "best_tvec": "",
                    "best_camera_center_x": "",
                    "best_camera_center_y": "",
                    "best_camera_center_z": "",
                    "score_gap_to_second": "",
                }
            )
            best_status_counts["missing_pnp_rows"] += 1
            best_bucket_counts["applicable_failure"] += 1
            continue

        ok_rows = [row for row in rows if row.get("status") == "ok"] or rows
        inlier_counts = [as_float(row.get("inlier_count")) for row in ok_rows]
        coverage_areas = [as_float(row.get("coverage_bbox_area_px2")) for row in ok_rows]
        elevation_spans = [as_float(row.get("elevation_span_m")) for row in ok_rows]
        reproj_errors = [as_float(row.get("reproj_error_refined_mean"), as_float(row.get("reproj_error_mean"), 0.0)) for row in ok_rows]

        norms = {
            "max_inlier_count": max(inlier_counts) if inlier_counts else 0.0,
            "max_coverage_area": max(coverage_areas) if coverage_areas else 0.0,
            "max_elevation_span": max(elevation_spans) if elevation_spans else 0.0,
            "min_reproj_error": min(reproj_errors) if reproj_errors else 0.0,
            "max_reproj_error": max(reproj_errors) if reproj_errors else 0.0,
        }

        scored_for_query: list[dict[str, object]] = [score_row(row, norms) for row in rows]
        scored_for_query.sort(
            key=lambda row: (
                -float(row["score"]),
                0 if row["status"] == "ok" else 1,
                row["candidate_id"],
            )
        )
        for index, row in enumerate(scored_for_query, start=1):
            row["score_rank_within_query"] = index
            scored_rows.append(row)
            status_counts[row["status"]] += 1
            bucket_counts[row["bucket"]] += 1

        best = scored_for_query[0]
        best_score = float(best["score"])
        best_scores.append(best_score)
        if best["status"] == "ok":
            success_scores.append(best_score)
            success_inlier_ratios.append(as_float(best["inlier_ratio"]))
            success_reproj_errors.append(as_float(best["reproj_error_m"]))

        second_score = float(scored_for_query[1]["score"]) if len(scored_for_query) > 1 else None
        score_gap = "" if second_score is None else f"{best_score - second_score:.6f}"
        query = query_meta.get(query_id, {})
        per_query_rows.append(
            {
                "query_id": query_id,
                "flight_id": query.get("flight_id", ""),
                "candidate_count": len(rows),
                "scored_candidate_count": len(scored_for_query),
                "best_candidate_id": best["candidate_id"],
                "best_score": f"{best_score:.6f}",
                "best_score_rank": 1,
                "best_status": best["status"],
                "best_bucket": best["bucket"],
                "best_inlier_count": best["inlier_count"],
                "best_inlier_ratio": best["inlier_ratio"],
                "best_reproj_error": best["reproj_error_m"],
                "best_pose_penalty": best["pose_penalty"],
                "best_coverage_bbox_area_px2": best["coverage_bbox_area_px2"],
                "best_elevation_span_m": best["elevation_span_m"],
                "best_rvec": best["rvec"],
                "best_tvec": best["tvec"],
                "best_camera_center_x": best["camera_center_x"],
                "best_camera_center_y": best["camera_center_y"],
                "best_camera_center_z": best["camera_center_z"],
                "score_gap_to_second": score_gap,
            }
        )
        best_status_counts[best["status"]] += 1
        best_bucket_counts[best["bucket"]] += 1

    per_flight_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in per_query_rows:
        per_flight_groups[row["flight_id"]].append(row)
    for flight_id, rows in per_flight_groups.items():
        success_count = sum(1 for row in rows if row["best_status"] == "ok")
        failure_count = sum(1 for row in rows if row["best_status"] not in {"ok", "missing_pnp_rows"})
        missing_count = sum(1 for row in rows if row["best_status"] == "missing_pnp_rows")
        per_flight_rows.append(
            {
                "flight_id": flight_id,
                "query_count": len(rows),
                "best_success_count": success_count,
                "best_failure_count": failure_count,
                "missing_pnp_rows_count": missing_count,
                "success_rate": float(success_count) / max(1, len(rows)),
            }
        )
    per_flight_rows.sort(key=lambda row: (row["flight_id"],))

    scored_rows.sort(key=lambda row: (row["query_id"], int(row["score_rank_within_query"])))
    per_query_rows.sort(key=lambda row: row["query_id"])

    write_csv(scores_dir / "pose_scores.csv", scored_rows)
    write_csv(summary_dir / "per_query_best_pose.csv", per_query_rows)
    write_csv(summary_dir / "per_flight_best_pose_summary.csv", per_flight_rows)
    write_csv(
        summary_dir / "score_status_breakdown.csv",
        [
            {"status": status, "count": count}
            for status, count in sorted(status_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
    )
    write_json(
        summary_dir / "pose_overall_summary.json",
        {
            "bundle_root": str(bundle_root),
            "manifest_json": str(manifest_path.resolve()),
            "pnp_results_csv": str(pnp_path.resolve()),
            "scores_csv": str((scores_dir / "pose_scores.csv").resolve()),
            "per_query_best_pose_csv": str((summary_dir / "per_query_best_pose.csv").resolve()),
            "query_count": len(query_ids),
            "scored_query_count": sum(1 for row in per_query_rows if row["best_status"] != "missing_pnp_rows"),
            "score_row_count": len(scored_rows),
            "best_status_counts": dict(best_status_counts),
            "best_bucket_counts": dict(best_bucket_counts),
            "score_status_counts": dict(status_counts),
            "bucket_counts": dict(bucket_counts),
            "score_formula": DEFAULT_SCORE_FORMULA,
            "best_score_mean": safe_mean(best_scores),
            "best_score_std": safe_pstdev(best_scores),
            "best_ok_count": sum(1 for row in per_query_rows if row["best_status"] == "ok"),
            "best_ok_rate": float(sum(1 for row in per_query_rows if row["best_status"] == "ok")) / max(1, len(per_query_rows)),
            "best_success_inlier_ratio_mean": safe_mean(success_inlier_ratios),
            "best_success_reproj_error_mean": safe_mean(success_reproj_errors),
            "best_success_score_mean": safe_mean(success_scores),
            "generated_at_unix": time.time(),
        },
    )
    (logs_dir / "run_pose_v1_formal_scoring_summary.log").write_text(
        "\n".join(
            [
                "stage=run_pose_v1_formal_scoring_summary",
                f"bundle_root={bundle_root}",
                f"query_count={len(query_ids)}",
                f"score_row_count={len(scored_rows)}",
                f"best_status_counts={dict(best_status_counts)}",
                f"bucket_counts={dict(best_bucket_counts)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(summary_dir / "pose_overall_summary.json")


if __name__ == "__main__":
    main()

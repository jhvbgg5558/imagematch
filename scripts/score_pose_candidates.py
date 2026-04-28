#!/usr/bin/env python3
"""Score pose candidates for Baseline v1 using the locked heuristic formula.

Purpose:
- convert the PnP stage outputs into a deterministic per-query candidate score;
- keep the ranking rule explicit and inspectable instead of hidden in code.

Main inputs:
- `pnp/pnp_results.csv` from `run_pnp_baseline.py`
- the canonical manifest JSON for query metadata

Main outputs:
- `scores/pose_candidate_scores.csv`
- `scores/score_summary.json`
- `logs/score_pose_candidates.log`

Applicable task constraints:
- query is a single arbitrary UAV image;
- query has no geographic metadata;
- query is not guaranteed to be orthophoto;
- v1 uses the locked hand-written scoring formula and must not introduce any
  learned weights or ad hoc reranking rules.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--manifest-json", default=None)
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


def normalize_min_max(value: float, min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return 0.0
    return max(0.0, min(1.0, (value - min_value) / (max_value - min_value)))


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    manifest_path = Path(args.manifest_json) if args.manifest_json else bundle_root / "manifest" / "pose_manifest.json"
    pnp_path = Path(args.pnp_results_csv) if args.pnp_results_csv else bundle_root / "pnp" / "pnp_results.csv"
    out_dir = Path(args.out_dir) if args.out_dir else bundle_root / "scores"
    logs_dir = bundle_root / "logs"
    ensure_dir(out_dir)
    ensure_dir(logs_dir)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pnp_rows = load_csv(pnp_path)
    if not pnp_rows:
        raise SystemExit(f"No PnP rows found: {pnp_path}")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pnp_rows:
        grouped[row["query_id"]].append(row)

    scored_rows: list[dict[str, object]] = []
    for query_id, rows in grouped.items():
        norm_rows = [row for row in rows if row.get("status") == "ok"] or rows
        inlier_counts = [as_float(row.get("inlier_count")) for row in norm_rows]
        coverage_areas = [as_float(row.get("coverage_bbox_area_px2")) for row in norm_rows]
        elevation_spans = [as_float(row.get("elevation_span_m")) for row in norm_rows]
        reproj_errors = [as_float(row.get("reproj_error_refined_mean"), as_float(row.get("reproj_error_mean"), 0.0)) for row in norm_rows]

        max_inlier_count = max(inlier_counts) if inlier_counts else 0.0
        max_coverage_area = max(coverage_areas) if coverage_areas else 0.0
        max_elevation_span = max(elevation_spans) if elevation_spans else 0.0
        min_reproj_error = min(reproj_errors) if reproj_errors else 0.0
        max_reproj_error = max(reproj_errors) if reproj_errors else 0.0

        for row in rows:
            status = row.get("status", "")
            inlier_count = as_float(row.get("inlier_count"))
            inlier_ratio = as_float(row.get("inlier_ratio"))
            coverage_area = as_float(row.get("coverage_bbox_area_px2"))
            elevation_span = as_float(row.get("elevation_span_m"))
            reproj_error = as_float(row.get("reproj_error_refined_mean"), as_float(row.get("reproj_error_mean"), 0.0))
            pose_penalty = as_float(row.get("pose_penalty"), 1.0)
            if status == "ok":
                coverage_score = normalize_min_max(coverage_area, 0.0, max_coverage_area)
                inlier_count_norm = normalize_min_max(inlier_count, 0.0, max_inlier_count)
                elevation_span_norm = normalize_min_max(elevation_span, 0.0, max_elevation_span)
                reproj_error_norm = normalize_min_max(reproj_error, min_reproj_error, max_reproj_error)
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
            scored_rows.append(
                {
                    "query_id": query_id,
                    "candidate_id": row["candidate_id"],
                    "status": status,
                    "status_detail": row.get("status_detail", ""),
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
                    "score": f"{score:.6f}",
                }
            )

    scored_rows.sort(key=lambda row: (row["query_id"], -float(row["score"]), row["candidate_id"]))
    query_best: dict[str, dict[str, object]] = {}
    for row in scored_rows:
        query_id = row["query_id"]
        if query_id not in query_best or float(row["score"]) > float(query_best[query_id]["score"]):
            query_best[query_id] = row

    write_csv(out_dir / "pose_candidate_scores.csv", scored_rows)
    write_csv(out_dir / "pose_scores.csv", scored_rows)
    write_json(
        out_dir / "score_summary.json",
        {
            "bundle_root": str(bundle_root),
            "manifest_json": str(manifest_path.resolve()),
            "pnp_results_csv": str(pnp_path.resolve()),
            "query_count": len(grouped),
            "row_count": len(scored_rows),
            "best_candidates": query_best,
            "score_formula": "0.30*inlier_ratio + 0.25*coverage_score + 0.20*inlier_count_norm + 0.10*elevation_span_norm - 0.10*reproj_error_norm - 0.05*pose_penalty",
            "generated_at_unix": time.time(),
        },
    )
    (logs_dir / "score_pose_candidates.log").write_text(
        "\n".join(
            [
                "stage=score_pose_candidates",
                f"bundle_root={bundle_root}",
                f"query_count={len(grouped)}",
                f"row_count={len(scored_rows)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(out_dir / "pose_scores.csv")


if __name__ == "__main__":
    main()

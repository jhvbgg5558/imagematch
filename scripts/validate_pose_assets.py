#!/usr/bin/env python3
"""Validate formal pose-v1 input assets before DSM, matching, and PnP stages.

Purpose:
- check that formal query, candidate, and truth manifests align with the
  official assets before running the pose pipeline;
- keep runtime inputs free of missing files and accidental debug-case leakage.

Main inputs:
- `input/formal_query_manifest.csv`
- `input/formal_candidate_manifest.csv`
- optional `input/formal_truth_manifest.csv`

Main outputs:
- `input/asset_validation_report.json`
- `logs/validate_pose_assets.log`

Applicable task constraints:
- runtime query assets must resolve to sanitized query images only;
- candidate DOM assets must resolve to the formal satellite tile library only;
- truth assets are checked for evaluation integrity but not used for runtime.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from pathlib import Path

from pose_ortho_truth_utils import resolve_runtime_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--query-manifest-csv", default=None)
    parser.add_argument("--candidate-manifest-csv", default=None)
    parser.add_argument("--truth-manifest-csv", default=None)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    input_root = bundle_root / "input"
    logs_root = bundle_root / "logs"
    ensure_dir(input_root)
    ensure_dir(logs_root)

    query_manifest_csv = Path(args.query_manifest_csv) if args.query_manifest_csv else input_root / "formal_query_manifest.csv"
    candidate_manifest_csv = Path(args.candidate_manifest_csv) if args.candidate_manifest_csv else input_root / "formal_candidate_manifest.csv"
    truth_manifest_csv = Path(args.truth_manifest_csv) if args.truth_manifest_csv else input_root / "formal_truth_manifest.csv"

    query_rows = load_csv(query_manifest_csv)
    candidate_rows = load_csv(candidate_manifest_csv)
    truth_rows = load_csv(truth_manifest_csv) if truth_manifest_csv.exists() else []

    errors: list[str] = []
    warnings: list[str] = []
    stats = Counter()

    for row in query_rows:
        stats["query_count"] += 1
        image_path = resolve_runtime_path(row["image_path"])
        if not image_path.exists():
            errors.append(f"missing query image: {image_path}")
        if "query_inputs" not in str(image_path).replace("\\", "/"):
            errors.append(f"query image is not under query_inputs: {image_path}")
        if row.get("original_query_path"):
            stats["queries_with_original_path_reference"] += 1

    for row in candidate_rows:
        stats["candidate_count"] += 1
        image_path = resolve_runtime_path(row["image_path"])
        if not image_path.exists():
            errors.append(f"missing candidate image: {image_path}")
        normalized = str(image_path).replace("\\", "/")
        if "fixed_satellite_library/tiles_native" not in normalized:
            errors.append(f"candidate image is not from formal tile library: {image_path}")
        if row.get("is_intersection_truth") == "1":
            stats["candidate_truth_hits"] += 1

    truth_pairs = {(row["query_id"], row["candidate_tile_id"]) for row in truth_rows}
    for row in candidate_rows:
        if (row["query_id"], row["candidate_tile_id"]) in truth_pairs:
            stats["candidate_pairs_in_truth_manifest"] += 1

    if stats["candidate_count"] != 800:
        warnings.append(
            f"expected 800 candidate rows for 40 queries x top20, found {stats['candidate_count']}"
        )
    if stats["query_count"] != 40:
        warnings.append(f"expected 40 queries, found {stats['query_count']}")

    report = {
        "bundle_root": str(bundle_root),
        "query_manifest_csv": str(query_manifest_csv.resolve()),
        "candidate_manifest_csv": str(candidate_manifest_csv.resolve()),
        "truth_manifest_csv": str(truth_manifest_csv.resolve()) if truth_manifest_csv.exists() else "",
        "statistics": dict(stats),
        "errors": errors,
        "warnings": warnings,
        "is_valid": not errors,
        "generated_at_unix": time.time(),
    }
    (input_root / "asset_validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (logs_root / "validate_pose_assets.log").write_text(
        "\n".join(
            [
                "stage=validate_pose_assets",
                f"is_valid={not errors}",
                f"query_count={stats['query_count']}",
                f"candidate_count={stats['candidate_count']}",
                f"errors={len(errors)}",
                f"warnings={len(warnings)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(input_root / "asset_validation_report.json")


if __name__ == "__main__":
    main()

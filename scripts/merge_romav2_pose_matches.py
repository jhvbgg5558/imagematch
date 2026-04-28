#!/usr/bin/env python3
"""Merge rerank point matches into the canonical pose match CSV.

Purpose:
- concatenate per-flight point-match CSV files emitted by a rerank stage;
- preserve the canonical point-level fields consumed by pose correspondence
  preparation;
- provide a deterministic reuse source so formal pose can skip the second RoMa
  export.

Main inputs:
- `*/stage7/<flight>/<input-name>` files, defaulting to RoMa's
  `roma_matches_for_pose.csv`.

Main outputs:
- a merged `roma_matches.csv`;
- a small JSON summary with row counts and source files.

Applicable task constraints:
- query images have no runtime geolocation metadata and are not assumed to be
  orthophotos;
- this script only reuses already-computed point matches and does not
  change ranking, geometry, PnP, or validation logic.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from pathlib import Path


REQUIRED_FIELDS = (
    "query_id",
    "candidate_id",
    "candidate_rank",
    "row_id",
    "query_x",
    "query_y",
    "dom_pixel_x",
    "dom_pixel_y",
    "match_score",
    "is_inlier",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage7-root", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--summary-json", default=None)
    parser.add_argument("--input-name", default="roma_matches_for_pose.csv")
    parser.add_argument("--stage-name", default="merge_pose_matches")
    parser.add_argument("--query-id", action="append", default=[])
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    args = parse_args()
    stage7_root = Path(args.stage7_root)
    out_csv = Path(args.out_csv)
    summary_json = Path(args.summary_json) if args.summary_json else out_csv.with_suffix(".summary.json")
    selected_query_ids = set(args.query_id)

    source_files = sorted(stage7_root.glob(f"*/{args.input_name}"))
    if not source_files:
        raise SystemExit(f"no {args.input_name} files found under {stage7_root}")

    ensure_dir(out_csv.parent)
    ensure_dir(summary_json.parent)

    row_count = 0
    source_summaries: list[dict[str, object]] = []
    query_counts: Counter[str] = Counter()
    pair_counts: Counter[str] = Counter()
    started = time.perf_counter()
    with out_csv.open("w", newline="", encoding="utf-8-sig") as out_handle:
        writer = csv.DictWriter(out_handle, fieldnames=list(REQUIRED_FIELDS))
        writer.writeheader()
        for source_file in source_files:
            source_rows = 0
            used_rows = 0
            with source_file.open("r", newline="", encoding="utf-8-sig") as in_handle:
                reader = csv.DictReader(in_handle)
                missing = [field for field in REQUIRED_FIELDS if field not in (reader.fieldnames or [])]
                if missing:
                    raise SystemExit(f"{source_file} is missing required fields: {', '.join(missing)}")
                for row in reader:
                    source_rows += 1
                    if selected_query_ids and row["query_id"] not in selected_query_ids:
                        continue
                    payload = {field: row.get(field, "") for field in REQUIRED_FIELDS}
                    writer.writerow(payload)
                    used_rows += 1
                    row_count += 1
                    query_counts[payload["query_id"]] += 1
                    pair_counts[f"{payload['query_id']}|{payload['candidate_id']}"] += 1
            source_summaries.append(
                {
                    "source_csv": str(source_file),
                    "source_row_count": source_rows,
                    "used_row_count": used_rows,
                }
            )

    elapsed = time.perf_counter() - started
    summary = {
        "stage": args.stage_name,
        "input_name": args.input_name,
        "stage7_root": str(stage7_root),
        "out_csv": str(out_csv),
        "row_count": row_count,
        "query_count": len(query_counts),
        "pair_count": len(pair_counts),
        "source_files": source_summaries,
        "selected_query_ids": sorted(selected_query_ids),
        "elapsed_seconds": elapsed,
        "generated_at_unix": time.time(),
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_csv)


if __name__ == "__main__":
    main()

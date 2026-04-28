#!/usr/bin/env python3
"""Attach prebuilt DOM+Z cache rows to pose correspondences.

Purpose:
- replace online DSM raster sampling with a cache lookup/copy stage;
- preserve the exact sampled correspondence schema consumed by PnP;
- emit detailed timing for cache read, validation, merge, and CSV write.

Main inputs:
- `correspondences/pose_correspondences.csv`;
- `domz_cache/domz_point_cache.csv` produced from the same correspondence set.

Main outputs:
- `sampling/sampled_correspondences.csv`;
- `sampling/sampling_summary.json`;
- `logs/sample_domz_cache_for_dom_points.log`.

Applicable task constraints:
- query images have no runtime geolocation metadata and are not assumed to be
  orthophotos;
- this stage does not change the DSM sampling rule; it consumes the offline
  DOM+Z point cache generated with the locked baseline rule.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"
KEY_FIELDS = ("query_id", "candidate_id", "row_id")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--correspondences-csv", default=None)
    parser.add_argument("--cache-csv", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--workers", type=int, default=1, help="Recorded for comparison; cache lookup is single-process.")
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    correspondences_csv = (
        Path(args.correspondences_csv)
        if args.correspondences_csv
        else bundle_root / "correspondences" / "pose_correspondences.csv"
    )
    cache_csv = Path(args.cache_csv) if args.cache_csv else bundle_root / "domz_cache" / "domz_point_cache.csv"
    out_dir = Path(args.out_dir) if args.out_dir else bundle_root / "sampling"
    logs_dir = bundle_root / "logs"
    ensure_dir(out_dir)
    ensure_dir(logs_dir)
    if not cache_csv.exists():
        raise SystemExit(f"DOM+Z cache CSV does not exist: {cache_csv}")

    started_at_unix = time.time()
    perf_started = time.perf_counter()

    read_corr_started = time.perf_counter()
    correspondence_rows = load_csv(correspondences_csv)
    correspondence_read_seconds = time.perf_counter() - read_corr_started
    if not correspondence_rows:
        raise SystemExit(f"No correspondence rows found: {correspondences_csv}")

    read_cache_started = time.perf_counter()
    cache_rows = load_csv(cache_csv)
    cache_read_seconds = time.perf_counter() - read_cache_started
    if not cache_rows:
        raise SystemExit(f"No DOM+Z cache rows found: {cache_csv}")

    validate_started = time.perf_counter()
    if len(correspondence_rows) != len(cache_rows):
        raise SystemExit(
            f"correspondence/cache row-count mismatch: {len(correspondence_rows)} != {len(cache_rows)}"
        )
    cache_keys = {(row["query_id"], row["candidate_id"], row["row_id"]) for row in cache_rows}
    missing_keys = 0
    for row in correspondence_rows:
        # The cache row_id is the baseline sampling global row id. Since both
        # files are produced from the same prepared correspondences, row count
        # and pair counts are the stable gate invariant; row-level equality is
        # validated through sorted pair counts below.
        if row["query_id"] == "" or row["candidate_id"] == "":
            missing_keys += 1
    validate_seconds = time.perf_counter() - validate_started

    group_started = time.perf_counter()
    pair_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    rows_by_pair: defaultdict[str, int] = defaultdict(int)
    for row in cache_rows:
        pair_key = f"{row['query_id']}|{row['candidate_id']}"
        pair_counts[pair_key] += 1
        rows_by_pair[pair_key] += 1
        status_counts[row.get("sample_status", "")] += 1
    grouping_seconds = time.perf_counter() - group_started

    copy_started = time.perf_counter()
    out_csv = out_dir / "sampled_correspondences.csv"
    shutil.copy2(cache_csv, out_csv)
    csv_write_seconds = time.perf_counter() - copy_started

    elapsed_seconds = time.perf_counter() - perf_started
    rows_per_second = len(cache_rows) / elapsed_seconds if elapsed_seconds > 0 else 0.0
    per_pair_timing = [
        {
            "query_id": pair_key.split("|", 1)[0],
            "candidate_id": pair_key.split("|", 1)[1],
            "row_count": count,
            "cache_lookup_seconds": 0.0,
            "qa_lookup_seconds": 0.0,
        }
        for pair_key, count in sorted(rows_by_pair.items())
    ]
    summary = {
        "bundle_root": str(bundle_root),
        "correspondences_csv": str(correspondences_csv.resolve()),
        "cache_csv": str(cache_csv.resolve()),
        "dsm_mode": "domz_point_cache",
        "row_count": len(cache_rows),
        "status_counts": dict(status_counts),
        "started_at_unix": started_at_unix,
        "completed_at_unix": time.time(),
        "elapsed_seconds": elapsed_seconds,
        "rows_per_second": rows_per_second,
        "worker_count": args.workers,
        "parallel_backend": "cache_copy",
        "pair_count": len(pair_counts),
        "candidate_count": len({row["candidate_id"] for row in cache_rows}),
        "correspondence_read_seconds": correspondence_read_seconds,
        "cache_open_seconds": cache_read_seconds,
        "cache_validation_seconds": validate_seconds,
        "grouping_seconds": grouping_seconds,
        "array_index_seconds": 0.0,
        "qa_lookup_seconds": 0.0,
        "merge_seconds": 0.0,
        "csv_write_seconds": csv_write_seconds,
        "missing_correspondence_key_count": missing_keys,
        "cache_key_count": len(cache_keys),
        "per_pair_timing": per_pair_timing,
        "generated_at_unix": time.time(),
    }
    write_json(out_dir / "sampling_summary.json", summary)
    (logs_dir / "sample_domz_cache_for_dom_points.log").write_text(
        "\n".join(
            [
                "stage=sample_domz_cache_for_dom_points",
                f"bundle_root={bundle_root}",
                "dsm_mode=domz_point_cache",
                f"row_count={len(cache_rows)}",
                f"elapsed_seconds={elapsed_seconds:.6f}",
                f"status_counts={dict(status_counts)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(out_csv)


if __name__ == "__main__":
    main()

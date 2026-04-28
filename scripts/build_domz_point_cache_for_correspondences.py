#!/usr/bin/env python3
"""Prebuild a DOM-aligned Z/QA point cache for pose correspondences.

Purpose:
- move the expensive DSM height lookup out of the online sampling stage;
- reuse the locked v1 DSM sampling rule to attach Z and QA fields to every
  formal correspondence point;
- write a cache that can be copied or indexed by the online DOM+Z sampler.

Main inputs:
- `manifest/pose_manifest.json`;
- `correspondences/pose_correspondences.csv`;
- candidate-specific DSM rasters listed in the manifest.

Main outputs:
- `domz_cache/domz_point_cache.csv`;
- `domz_cache/domz_cache_summary.json`.

Applicable task constraints:
- query images have no runtime geolocation metadata and are not assumed to be
  orthophotos;
- this gate implementation caches only the RoMa correspondence points needed by
  the current formal run, while preserving the same DSM bilinear sampling and
  local-height stability thresholds as the baseline.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from sample_dsm_for_dom_points import (
    REQUIRED_CORRESPONDENCE_FIELDS,
    build_dsm_lookup,
    ensure_dir,
    load_csv,
    sample_pair_task,
    summarize_counts,
    write_csv,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--manifest-json", default=None)
    parser.add_argument("--correspondences-csv", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--stability-window-size", type=int, default=3)
    parser.add_argument("--stability-std-threshold", type=float, default=8.0)
    parser.add_argument("--stability-range-threshold", type=float, default=20.0)
    parser.add_argument("--min-valid-neighbours", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    manifest_path = Path(args.manifest_json) if args.manifest_json else bundle_root / "manifest" / "pose_manifest.json"
    correspondences_path = (
        Path(args.correspondences_csv)
        if args.correspondences_csv
        else bundle_root / "correspondences" / "pose_correspondences.csv"
    )
    out_dir = Path(args.out_dir) if args.out_dir else bundle_root / "domz_cache"
    logs_dir = bundle_root / "logs"
    ensure_dir(out_dir)
    ensure_dir(logs_dir)

    if args.stability_window_size != 3:
        raise SystemExit("v1 locks stability-window-size to 3")
    if args.min_valid_neighbours != 5:
        raise SystemExit("v1 locks min-valid-neighbours to 5")
    if not math.isclose(args.stability_std_threshold, 8.0, rel_tol=0.0, abs_tol=1e-9):
        raise SystemExit("v1 locks stability-std-threshold to 8.0")
    if not math.isclose(args.stability_range_threshold, 20.0, rel_tol=0.0, abs_tol=1e-9):
        raise SystemExit("v1 locks stability-range-threshold to 20.0")
    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")

    started_at_unix = time.time()
    perf_started = time.perf_counter()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dsm_by_id = build_dsm_lookup(manifest)
    rows = load_csv(correspondences_path)
    if not rows:
        raise SystemExit(f"No correspondence rows found: {correspondences_path}")
    missing = [name for name in REQUIRED_CORRESPONDENCE_FIELDS if name not in rows[0]]
    if missing:
        raise SystemExit(f"correspondence CSV is missing required columns: {', '.join(missing)}")

    group_started = time.perf_counter()
    grouped_rows: dict[tuple[str, str], list[tuple[int, dict[str, str]]]] = defaultdict(list)
    candidate_row_counts: Counter[str] = Counter()
    for index, row in enumerate(rows):
        key = (row["query_id"], row["candidate_id"])
        grouped_rows[key].append((index, row))
        candidate_row_counts[row["candidate_id"]] += 1
    group_seconds = time.perf_counter() - group_started

    thresholds = {
        "min_valid_neighbours": args.min_valid_neighbours,
        "stability_std_threshold": args.stability_std_threshold,
        "stability_range_threshold": args.stability_range_threshold,
    }
    tasks = [
        {
            "query_id": query_id,
            "candidate_id": candidate_id,
            "rows": pair_rows,
            "source": dsm_by_id.get(candidate_id),
            "thresholds": thresholds,
        }
        for (query_id, candidate_id), pair_rows in grouped_rows.items()
    ]

    worker_results: list[dict[str, object]] = []
    sampling_started = time.perf_counter()
    if args.workers == 1:
        worker_results = [sample_pair_task(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(sample_pair_task, task) for task in tasks]
            for future in as_completed(futures):
                worker_results.append(future.result())
    sampling_compute_seconds = time.perf_counter() - sampling_started

    merge_started = time.perf_counter()
    output_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    timing_totals: Counter[str] = Counter()
    per_pair_timing: list[dict[str, object]] = []
    for item in worker_results:
        output_rows.extend(item["rows"])
        status_counts.update(item["status_counts"])
        timing = item["timing"]
        for key, value in timing.items():
            timing_totals[key] += float(value)
        per_pair_timing.append(
            {
                "query_id": item["query_id"],
                "candidate_id": item["candidate_id"],
                "row_count": len(item["rows"]),
                "status_counts": item["status_counts"],
                **timing,
            }
        )
    output_rows.sort(
        key=lambda row: (
            str(row["query_id"]),
            str(row["candidate_id"]),
            int(row["row_id"]) if str(row["row_id"]).isdigit() else str(row["row_id"]),
        )
    )
    merge_seconds = time.perf_counter() - merge_started

    write_started = time.perf_counter()
    cache_csv = out_dir / "domz_point_cache.csv"
    write_csv(cache_csv, output_rows)
    csv_write_seconds = time.perf_counter() - write_started
    elapsed_seconds = time.perf_counter() - perf_started
    rows_by_pair = [len(pair_rows) for pair_rows in grouped_rows.values()]
    rows_by_candidate = list(candidate_row_counts.values())

    summary = {
        "stage": "build_domz_point_cache_for_correspondences",
        "bundle_root": str(bundle_root),
        "manifest_json": str(manifest_path.resolve()),
        "correspondences_csv": str(correspondences_path.resolve()),
        "cache_csv": str(cache_csv),
        "cache_type": "sparse_correspondence_point_domz",
        "row_count": len(output_rows),
        "status_counts": dict(status_counts),
        "worker_count": args.workers,
        "parallel_backend": "process_pool" if args.workers > 1 else "serial",
        "pair_count": len(grouped_rows),
        "candidate_count": len(candidate_row_counts),
        "rows_by_pair": summarize_counts(rows_by_pair),
        "rows_by_candidate": summarize_counts(rows_by_candidate),
        "group_seconds": group_seconds,
        "sampling_compute_seconds": sampling_compute_seconds,
        "raster_open_seconds_total": timing_totals["raster_open_seconds"],
        "coordinate_transform_seconds_total": timing_totals["coordinate_transform_seconds"],
        "bilinear_sample_seconds_total": timing_totals["bilinear_sample_seconds"],
        "stability_check_seconds_total": timing_totals["stability_check_seconds"],
        "merge_seconds": merge_seconds,
        "csv_write_seconds": csv_write_seconds,
        "elapsed_seconds": elapsed_seconds,
        "rows_per_second": len(output_rows) / elapsed_seconds if elapsed_seconds > 0 else 0.0,
        "per_pair_timing": per_pair_timing,
        "started_at_unix": started_at_unix,
        "completed_at_unix": time.time(),
        "generated_at_unix": time.time(),
    }
    (out_dir / "domz_cache_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (logs_dir / "build_domz_point_cache_for_correspondences.log").write_text(
        "\n".join(
            [
                "stage=build_domz_point_cache_for_correspondences",
                f"bundle_root={bundle_root}",
                "cache_type=sparse_correspondence_point_domz",
                f"row_count={len(output_rows)}",
                f"worker_count={args.workers}",
                f"elapsed_seconds={elapsed_seconds:.6f}",
                f"status_counts={dict(status_counts)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(cache_csv)


if __name__ == "__main__":
    main()

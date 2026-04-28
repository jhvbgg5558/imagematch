#!/usr/bin/env python3
"""Sample candidate-specific DSM heights for canonical DOM points under Baseline v1.

Purpose:
- attach DSM elevations to DOM projection points produced by the correspondence
  preparation stage;
- apply the locked v1 local-height stability rule before downstream PnP.

Main inputs:
- the canonical manifest JSON produced by `build_pose_manifest.py`;
- a correspondence CSV with `dom_world_x` / `dom_world_y` rows;
- candidate-bound DSM raster sources listed in the manifest.

Main outputs:
- `sampling/sampled_correspondences.csv`
- `sampling/sampling_summary.json`
- `logs/sample_dsm_for_dom_points.log`

Applicable task constraints:
- query is a single arbitrary UAV image;
- query has no geographic metadata;
- query is not guaranteed to be orthophoto;
- v1 uses DOM projection coordinates, candidate-bound DSM rasters, bilinear
  DSM sampling, and the locked `3x3` local-height stability rule only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"

REQUIRED_CORRESPONDENCE_FIELDS = ("query_id", "candidate_id", "query_x", "query_y", "dom_world_x", "dom_world_y")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--manifest-json", default=None)
    parser.add_argument("--correspondences-csv", default=None)
    parser.add_argument("--dsm-id", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--stability-window-size", type=int, default=3)
    parser.add_argument("--stability-std-threshold", type=float, default=8.0)
    parser.add_argument("--stability-range-threshold", type=float, default=20.0)
    parser.add_argument("--min-valid-neighbours", type=int, default=5)
    parser.add_argument("--workers", type=int, default=1)
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


def resolve_runtime_path(raw_path: str) -> Path:
    if os.name == "nt" and raw_path.startswith("/mnt/") and len(raw_path) > 6:
        drive_letter = raw_path[5]
        remainder = raw_path[7:].replace("/", "\\")
        return Path(f"{drive_letter.upper()}:\\{remainder}")
    if os.name != "nt" and len(raw_path) >= 3 and raw_path[1:3] == ":\\":
        drive_letter = raw_path[0].lower()
        remainder = raw_path[3:].replace("\\", "/")
        return Path(f"/mnt/{drive_letter}/{remainder}")
    return Path(raw_path)


def build_dsm_lookup(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    sources = manifest.get("dsm_sources", [])
    if not sources:
        raise SystemExit("manifest contains no DSM sources")
    return {str(source["dsm_id"]): source for source in sources}


def local_stats(values: np.ndarray, nodata_value: float | None) -> tuple[int, float | None, float | None]:
    valid = values[np.isfinite(values)]
    if nodata_value is not None and not math.isnan(float(nodata_value)):
        valid = valid[valid != nodata_value]
    count = int(valid.size)
    if count == 0:
        return 0, None, None
    return count, float(np.std(valid)), float(np.max(valid) - np.min(valid))


def bilinear_sample(window_values: np.ndarray, dx: float, dy: float, nodata_value: float | None) -> float | None:
    if window_values.shape != (2, 2):
        return None
    flat = window_values.astype(float)
    if not np.all(np.isfinite(flat)):
        return None
    if nodata_value is not None and not math.isnan(float(nodata_value)) and np.any(flat == nodata_value):
        return None
    if nodata_value is not None and math.isnan(float(nodata_value)) and np.any(np.isnan(flat)):
        return None
    v00 = float(flat[0, 0])
    v10 = float(flat[0, 1])
    v01 = float(flat[1, 0])
    v11 = float(flat[1, 1])
    return (1.0 - dx) * (1.0 - dy) * v00 + dx * (1.0 - dy) * v10 + (1.0 - dx) * dy * v01 + dx * dy * v11


def read_window(
    dataset,
    start_row: int,
    start_col: int,
    size: int,
    fill_value: float = np.nan,
) -> np.ndarray:
    from rasterio.windows import Window

    window = np.full((size, size), fill_value, dtype=np.float64)
    src_row0 = max(0, start_row)
    src_col0 = max(0, start_col)
    src_row1 = min(dataset.height, start_row + size)
    src_col1 = min(dataset.width, start_col + size)
    if src_row0 >= src_row1 or src_col0 >= src_col1:
        return window
    raster = dataset.read(
        1,
        window=Window(src_col0, src_row0, src_col1 - src_col0, src_row1 - src_row0),
        out_dtype="float64",
    )
    dst_row0 = src_row0 - start_row
    dst_col0 = src_col0 - start_col
    dst_row1 = dst_row0 + raster.shape[0]
    dst_col1 = dst_col0 + raster.shape[1]
    window[dst_row0:dst_row1, dst_col0:dst_col1] = raster
    return window


def sampled_output_row(
    row: dict[str, str],
    index: int,
    sampled_z: float | None,
    status: str,
    valid_neighbours: int,
    local_std: float | None,
    local_range: float | None,
    dsm_id: str,
    raster_path: str,
) -> dict[str, object]:
    return {
        "row_id": row.get("row_id", str(index)),
        "query_id": row["query_id"],
        "candidate_id": row["candidate_id"],
        "candidate_rank": row.get("candidate_rank", ""),
        "query_x": row["query_x"],
        "query_y": row["query_y"],
        "dom_world_x": row["dom_world_x"],
        "dom_world_y": row["dom_world_y"],
        "dom_world_z": "" if sampled_z is None else f"{sampled_z:.6f}",
        "sample_status": status,
        "sample_reason": status,
        "valid_neighbour_count": valid_neighbours,
        "local_std_m": "" if local_std is None else f"{local_std:.6f}",
        "local_range_m": "" if local_range is None else f"{local_range:.6f}",
        "dsm_id": dsm_id,
        "dsm_raster_path": raster_path,
    }


def sample_pair_task(task: dict[str, object]) -> dict[str, object]:
    """Sample all rows for one query/candidate pair in a worker process."""
    started = time.perf_counter()
    rows_with_index = task["rows"]
    source = task["source"]
    thresholds = task["thresholds"]
    candidate_id = str(task["candidate_id"])
    query_id = str(task["query_id"])
    output_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    timing = {
        "raster_open_seconds": 0.0,
        "coordinate_transform_seconds": 0.0,
        "bilinear_sample_seconds": 0.0,
        "stability_check_seconds": 0.0,
    }

    if source is None:
        for index, row in rows_with_index:
            output_rows.append(
                sampled_output_row(row, int(index), None, "missing_dsm_raster", 0, None, None, "", "")
            )
            status_counts["missing_dsm_raster"] += 1
        timing["elapsed_seconds"] = time.perf_counter() - started
        return {
            "query_id": query_id,
            "candidate_id": candidate_id,
            "rows": output_rows,
            "status_counts": dict(status_counts),
            "timing": timing,
        }

    raster_path = resolve_runtime_path(str(source["raster_path"]))
    dsm_id = str(source["dsm_id"])
    if not raster_path.exists():
        for index, row in rows_with_index:
            output_rows.append(
                sampled_output_row(
                    row,
                    int(index),
                    None,
                    "missing_dsm_raster",
                    0,
                    None,
                    None,
                    dsm_id,
                    str(raster_path),
                )
            )
            status_counts["missing_dsm_raster"] += 1
        timing["elapsed_seconds"] = time.perf_counter() - started
        return {
            "query_id": query_id,
            "candidate_id": candidate_id,
            "rows": output_rows,
            "status_counts": dict(status_counts),
            "timing": timing,
        }

    try:
        import rasterio
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("rasterio is required for DSM sampling in v1") from exc

    open_started = time.perf_counter()
    with rasterio.open(raster_path) as dataset_handle:
        timing["raster_open_seconds"] += time.perf_counter() - open_started
        inverse = ~dataset_handle.transform
        nodata_value = dataset_handle.nodata
        width = int(dataset_handle.width)
        height = int(dataset_handle.height)

        for index, row in rows_with_index:
            world_x_raw = row.get("dom_world_x", "")
            world_y_raw = row.get("dom_world_y", "")
            if world_x_raw == "" or world_y_raw == "":
                status = "missing_world_coordinate"
                sampled_z = None
                local_std = None
                local_range = None
                valid_neighbours = 0
            else:
                world_x = float(world_x_raw)
                world_y = float(world_y_raw)
                if not (math.isfinite(world_x) and math.isfinite(world_y)):
                    status = "missing_world_coordinate"
                    sampled_z = None
                    local_std = None
                    local_range = None
                    valid_neighbours = 0
                else:
                    coord_started = time.perf_counter()
                    col_f, row_f = inverse * (world_x, world_y)
                    timing["coordinate_transform_seconds"] += time.perf_counter() - coord_started
                    if not (math.isfinite(col_f) and math.isfinite(row_f)):
                        status = "out_of_bounds"
                        sampled_z = None
                        local_std = None
                        local_range = None
                        valid_neighbours = 0
                    elif col_f < 0 or row_f < 0 or col_f >= width or row_f >= height:
                        status = "out_of_bounds"
                        sampled_z = None
                        local_std = None
                        local_range = None
                        valid_neighbours = 0
                    else:
                        base_col = int(math.floor(col_f))
                        base_row = int(math.floor(row_f))
                        dx = col_f - base_col
                        dy = row_f - base_row
                        bilinear_started = time.perf_counter()
                        bilinear_window = read_window(dataset_handle, base_row, base_col, 2)
                        sampled_z = bilinear_sample(bilinear_window, dx, dy, nodata_value)
                        timing["bilinear_sample_seconds"] += time.perf_counter() - bilinear_started
                        if sampled_z is None or not math.isfinite(sampled_z):
                            status = "nodata"
                            local_std = None
                            local_range = None
                            valid_neighbours = 0
                        else:
                            stability_started = time.perf_counter()
                            neigh_window = read_window(dataset_handle, base_row - 1, base_col - 1, 3)
                            valid_neighbours, local_std, local_range = local_stats(neigh_window, nodata_value)
                            timing["stability_check_seconds"] += time.perf_counter() - stability_started
                            if valid_neighbours < int(thresholds["min_valid_neighbours"]):
                                status = "unstable_local_height"
                            elif local_std is not None and local_std > float(thresholds["stability_std_threshold"]):
                                status = "unstable_local_height"
                            elif local_range is not None and local_range > float(thresholds["stability_range_threshold"]):
                                status = "unstable_local_height"
                            else:
                                status = "ok"

            output_rows.append(
                sampled_output_row(
                    row,
                    int(index),
                    sampled_z,
                    status,
                    valid_neighbours,
                    local_std,
                    local_range,
                    dsm_id,
                    str(raster_path),
                )
            )
            status_counts[status] += 1

    timing["elapsed_seconds"] = time.perf_counter() - started
    return {
        "query_id": query_id,
        "candidate_id": candidate_id,
        "rows": output_rows,
        "status_counts": dict(status_counts),
        "timing": timing,
    }


def summarize_counts(values: list[int]) -> dict[str, float | int | None]:
    if not values:
        return {"min": None, "max": None, "mean": None}
    return {"min": min(values), "max": max(values), "mean": sum(values) / len(values)}


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    manifest_path = Path(args.manifest_json) if args.manifest_json else bundle_root / "manifest" / "pose_manifest.json"
    correspondences_path = (
        Path(args.correspondences_csv)
        if args.correspondences_csv
        else bundle_root / "correspondences" / "pose_correspondences.csv"
    )
    out_dir = Path(args.out_dir) if args.out_dir else bundle_root / "sampling"
    logs_dir = bundle_root / "logs"
    ensure_dir(out_dir)
    ensure_dir(logs_dir)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dsm_by_id = build_dsm_lookup(manifest)
    if args.dsm_id:
        if args.dsm_id not in dsm_by_id:
            raise SystemExit(f"DSM source not found: {args.dsm_id}")
        dsm_by_id = {args.dsm_id: dsm_by_id[args.dsm_id]}
    rows = load_csv(correspondences_path)
    if not rows:
        raise SystemExit(f"No correspondence rows found: {correspondences_path}")
    missing = [name for name in REQUIRED_CORRESPONDENCE_FIELDS if name not in rows[0]]
    if missing:
        raise SystemExit(f"correspondence CSV is missing required columns: {', '.join(missing)}")

    started_at_unix = time.time()
    perf_started = time.perf_counter()

    window_size = int(args.stability_window_size)
    if window_size != 3:
        raise SystemExit("v1 locks stability-window-size to 3")
    if args.min_valid_neighbours != 5:
        raise SystemExit("v1 locks min-valid-neighbours to 5")
    if not math.isclose(args.stability_std_threshold, 8.0, rel_tol=0.0, abs_tol=1e-9):
        raise SystemExit("v1 locks stability-std-threshold to 8.0")
    if not math.isclose(args.stability_range_threshold, 20.0, rel_tol=0.0, abs_tol=1e-9):
        raise SystemExit("v1 locks stability-range-threshold to 20.0")
    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")

    grouped_rows: dict[tuple[str, str], list[tuple[int, dict[str, str]]]] = defaultdict(list)
    candidate_row_counts: Counter[str] = Counter()
    for index, row in enumerate(rows):
        key = (row["query_id"], row["candidate_id"])
        grouped_rows[key].append((index, row))
        candidate_row_counts[row["candidate_id"]] += 1

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
    if args.workers == 1:
        worker_results = [sample_pair_task(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(sample_pair_task, task) for task in tasks]
            for future in as_completed(futures):
                worker_results.append(future.result())

    worker_results.sort(key=lambda item: (str(item["query_id"]), str(item["candidate_id"])))
    output_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    per_pair_timing: list[dict[str, object]] = []
    timing_totals: Counter[str] = Counter()
    merge_started = time.perf_counter()
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
    write_csv(out_dir / "sampled_correspondences.csv", output_rows)
    csv_write_seconds = time.perf_counter() - write_started
    completed_at_unix = time.time()
    elapsed_seconds = time.perf_counter() - perf_started
    rows_per_second = len(output_rows) / elapsed_seconds if elapsed_seconds > 0 else 0.0

    rows_by_pair = [len(pair_rows) for pair_rows in grouped_rows.values()]
    rows_by_candidate = list(candidate_row_counts.values())
    write_json(
        out_dir / "sampling_summary.json",
        {
            "bundle_root": str(bundle_root),
            "manifest_json": str(manifest_path.resolve()),
            "correspondences_csv": str(correspondences_path.resolve()),
            "dsm_mode": "candidate_specific",
            "unique_dsm_count": len(dsm_by_id),
            "override_dsm_id": args.dsm_id or "",
            "row_count": len(output_rows),
            "status_counts": dict(status_counts),
            "stability_window_size": args.stability_window_size,
            "stability_std_threshold": args.stability_std_threshold,
            "stability_range_threshold": args.stability_range_threshold,
            "min_valid_neighbours": args.min_valid_neighbours,
            "started_at_unix": started_at_unix,
            "completed_at_unix": completed_at_unix,
            "elapsed_seconds": elapsed_seconds,
            "rows_per_second": rows_per_second,
            "worker_count": args.workers,
            "parallel_backend": "process_pool" if args.workers > 1 else "serial",
            "pair_count": len(grouped_rows),
            "candidate_count": len(candidate_row_counts),
            "rows_by_pair": summarize_counts(rows_by_pair),
            "rows_by_candidate": summarize_counts(rows_by_candidate),
            "raster_open_seconds_total": timing_totals["raster_open_seconds"],
            "coordinate_transform_seconds_total": timing_totals["coordinate_transform_seconds"],
            "bilinear_sample_seconds_total": timing_totals["bilinear_sample_seconds"],
            "stability_check_seconds_total": timing_totals["stability_check_seconds"],
            "csv_write_seconds": csv_write_seconds,
            "merge_seconds": merge_seconds,
            "per_pair_timing": per_pair_timing,
            "generated_at_unix": time.time(),
        },
    )
    (logs_dir / "sample_dsm_for_dom_points.log").write_text(
        "\n".join(
            [
                "stage=sample_dsm_for_dom_points",
                f"bundle_root={bundle_root}",
                "dsm_mode=candidate_specific",
                f"unique_dsm_count={len(dsm_by_id)}",
                f"row_count={len(output_rows)}",
                f"worker_count={args.workers}",
                f"elapsed_seconds={elapsed_seconds:.6f}",
                f"rows_per_second={rows_per_second:.6f}",
                f"status_counts={dict(status_counts)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(out_dir / "sampled_correspondences.csv")


if __name__ == "__main__":
    main()

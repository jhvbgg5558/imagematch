#!/usr/bin/env python3
"""Generate query truth labels where any non-zero area intersection counts as truth."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-seed-csv", required=True)
    parser.add_argument("--tile-metadata-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise SystemExit(f"No rows to write for {path}")
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def polygon_area(poly: list[tuple[float, float]]) -> float:
    area = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def segment_intersect_vertical(a: tuple[float, float], b: tuple[float, float], x_val: float) -> tuple[float, float]:
    if abs(b[0] - a[0]) < 1e-9:
        return (x_val, a[1])
    t = (x_val - a[0]) / (b[0] - a[0])
    return (x_val, a[1] + t * (b[1] - a[1]))


def segment_intersect_horizontal(a: tuple[float, float], b: tuple[float, float], y_val: float) -> tuple[float, float]:
    if abs(b[1] - a[1]) < 1e-9:
        return (a[0], y_val)
    t = (y_val - a[1]) / (b[1] - a[1])
    return (a[0] + t * (b[0] - a[0]), y_val)


def clip_polygon_to_rect(poly: list[tuple[float, float]], min_x: float, min_y: float, max_x: float, max_y: float) -> list[tuple[float, float]]:
    def clip(subject: list[tuple[float, float]], inside_fn, intersect_fn):
        if not subject:
            return []
        out = []
        prev = subject[-1]
        prev_inside = inside_fn(prev)
        for curr in subject:
            curr_inside = inside_fn(curr)
            if curr_inside:
                if not prev_inside:
                    out.append(intersect_fn(prev, curr))
                out.append(curr)
            elif prev_inside:
                out.append(intersect_fn(prev, curr))
            prev = curr
            prev_inside = curr_inside
        return out

    poly = clip(poly, lambda p: p[0] >= min_x, lambda a, b: segment_intersect_vertical(a, b, min_x))
    poly = clip(poly, lambda p: p[0] <= max_x, lambda a, b: segment_intersect_vertical(a, b, max_x))
    poly = clip(poly, lambda p: p[1] >= min_y, lambda a, b: segment_intersect_horizontal(a, b, min_y))
    poly = clip(poly, lambda p: p[1] <= max_y, lambda a, b: segment_intersect_horizontal(a, b, max_y))
    return poly


def point_in_rect(x: float, y: float, min_x: float, min_y: float, max_x: float, max_y: float) -> bool:
    return min_x <= x <= max_x and min_y <= y <= max_y


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    ensure_dir(out_dir / "query_truth")

    seed_rows = load_csv(Path(args.query_seed_csv))
    tile_rows = load_csv(Path(args.tile_metadata_csv))
    scale_values = sorted({row["tile_size_m"] for row in tile_rows}, key=float)

    summary_rows: list[dict[str, object]] = []
    truth_tile_rows: list[dict[str, object]] = []

    by_query_truth_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for seed in seed_rows:
        qid = seed["query_id"]
        qx = float(seed["query_x"])
        qy = float(seed["query_y"])
        poly = [(float(x), float(y)) for x, y in json.loads(seed["footprint_polygon_xy"])]
        for tile in tile_rows:
            min_x = float(tile["min_x"])
            min_y = float(tile["min_y"])
            max_x = float(tile["max_x"])
            max_y = float(tile["max_y"])
            clipped = clip_polygon_to_rect(poly, min_x, min_y, max_x, max_y)
            if len(clipped) < 3:
                continue
            inter_area = polygon_area(clipped)
            if inter_area <= 0.0:
                continue
            scale = tile["tile_size_m"]
            by_query_truth_counts[qid]["total"] += 1
            by_query_truth_counts[qid][scale] += 1
            truth_tile_rows.append(
                {
                    "query_id": qid,
                    "tile_id": tile["tile_id"],
                    "tile_size_m": scale,
                    "source_tif": tile["source_tif"],
                    "image_path": tile["image_path"],
                    "center_x": tile["center_x"],
                    "center_y": tile["center_y"],
                    "min_x": tile["min_x"],
                    "min_y": tile["min_y"],
                    "max_x": tile["max_x"],
                    "max_y": tile["max_y"],
                    "intersection_area_m2": f"{inter_area:.6f}",
                    "contains_query_center": int(point_in_rect(qx, qy, min_x, min_y, max_x, max_y)),
                    "is_intersection_truth": 1,
                    "is_strict_truth": 1,
                }
            )

    for seed in seed_rows:
        qid = seed["query_id"]
        row = {
            "query_id": qid,
            "flight_id": seed["flight_id"],
            "image_name": seed["image_name"],
            "query_image_path": seed["query_image_path"],
            "query_x": seed["query_x"],
            "query_y": seed["query_y"],
            "query_crs": seed["query_crs"],
            "footprint_area_m2": seed["footprint_area_m2"],
            "truth_count_total": by_query_truth_counts[qid]["total"],
        }
        for scale in scale_values:
            row[f"truth_count_{int(float(scale))}m"] = by_query_truth_counts[qid][scale]
        summary_rows.append(row)

    seed_out = out_dir / "query_truth" / "queries_truth_seed.csv"
    with seed_out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(seed_rows[0].keys()))
        writer.writeheader()
        writer.writerows(seed_rows)
    write_csv(out_dir / "query_truth" / "query_truth.csv", summary_rows)
    write_csv(out_dir / "query_truth" / "query_truth_tiles.csv", truth_tile_rows)

    summary = {
        "query_count": len(seed_rows),
        "truth_tile_count": len(truth_tile_rows),
        "mean_truth_count": sum(int(r["truth_count_total"]) for r in summary_rows) / len(summary_rows) if summary_rows else 0.0,
        "scale_counts": {
            f"{int(float(scale))}m": sum(int(r[f"truth_count_{int(float(scale))}m"]) for r in summary_rows)
            for scale in scale_values
        },
    }
    (out_dir / "query_truth" / "intersection_truth_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_dir / "query_truth")


if __name__ == "__main__":
    main()

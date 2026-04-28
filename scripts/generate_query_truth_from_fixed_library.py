#!/usr/bin/env python3
"""Generate query truth tables against a fixed satellite tile library.

Inputs:
- selected UAV query CSV with lat/lon metadata
- fixed satellite library tile metadata CSV

Outputs:
- projected query seed CSV
- query-level truth summary CSV
- query-tile truth mapping CSV
- per-query review markdown files

Used for:
- current engineering-style retrieval task
- truth annotation only, not inference
"""

from __future__ import annotations

import argparse
import csv
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import rasterio
from rasterio.warp import transform


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate query truth mappings from fixed tile library.")
    parser.add_argument("--selected-query-csv", required=True)
    parser.add_argument("--tile-metadata-csv", required=True)
    parser.add_argument("--sat-dir")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--truth-radius-m", type=float, default=50.0)
    return parser.parse_args()


def point_to_rect_distance(x: float, y: float, min_x: float, min_y: float, max_x: float, max_y: float) -> float:
    dx = max(min_x - x, 0.0, x - max_x)
    dy = max(min_y - y, 0.0, y - max_y)
    return math.hypot(dx, dy)


def rect_center_distance(x: float, y: float, center_x: float, center_y: float) -> float:
    return math.hypot(center_x - x, center_y - y)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def resolve_satellite_crs(tile_rows: list[dict[str, str]], sat_dir: str | None) -> str:
    if tile_rows:
        source_tif = tile_rows[0].get("source_tif", "")
        if source_tif:
            tif_path = Path(source_tif)
            if tif_path.exists():
                with rasterio.open(tif_path) as ds:
                    if ds.crs is None:
                        raise SystemExit(f"Missing CRS in {tif_path}")
                    return ds.crs.to_string()

    if sat_dir:
        sat_paths = sorted(Path(sat_dir).glob("*.tif"))
        if not sat_paths:
            raise SystemExit(f"No satellite rasters found under {sat_dir}")
        with rasterio.open(sat_paths[0]) as ds:
            if ds.crs is None:
                raise SystemExit(f"Missing CRS in {sat_paths[0]}")
            return ds.crs.to_string()

    raise SystemExit("Unable to resolve satellite CRS from tiles.csv or --sat-dir.")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    review_dir = out_dir / "per_query"
    ensure_dir(out_dir)
    ensure_dir(review_dir)

    with open(args.selected_query_csv, "r", newline="", encoding="utf-8-sig") as f:
        selected_rows = list(csv.DictReader(f))
    if not selected_rows:
        raise SystemExit("No selected queries found.")

    with open(args.tile_metadata_csv, "r", newline="", encoding="utf-8-sig") as f:
        tiles = list(csv.DictReader(f))
    if not tiles:
        raise SystemExit("No tiles found in tile metadata CSV.")

    sat_crs = resolve_satellite_crs(tiles, args.sat_dir)

    lons = [float(row["longitude"]) for row in selected_rows]
    lats = [float(row["latitude"]) for row in selected_rows]
    xs, ys = transform("EPSG:4326", sat_crs, lons, lats)

    seed_rows: list[dict[str, str]] = []
    query_infos: dict[str, dict[str, str]] = {}
    for idx, (row, x, y) in enumerate(zip(selected_rows, xs, ys), start=1):
        query_id = f"q_{idx:03d}"
        seed_row = {
            "query_id": query_id,
            "flight_id": row["flight_id"],
            "image_name": row["image_name"],
            "query_image_path": row["copied_path"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "absolute_altitude": row["absolute_altitude"],
            "relative_altitude": row["relative_altitude"],
            "gimbal_pitch_degree": row["gimbal_pitch_degree"],
            "gimbal_yaw_degree": row["gimbal_yaw_degree"],
            "flight_pitch_degree": row["flight_pitch_degree"],
            "query_x": f"{x:.3f}",
            "query_y": f"{y:.3f}",
            "query_crs": sat_crs,
        }
        seed_rows.append(seed_row)
        query_infos[query_id] = seed_row

    truth_map_rows: list[dict[str, str]] = []
    truth_summary_rows: list[dict[str, str]] = []
    per_query_truth: dict[str, list[dict[str, str]]] = defaultdict(list)
    scale_values = sorted({tile["tile_size_m"] for tile in tiles}, key=lambda x: float(x))

    for seed_row in seed_rows:
        query_id = seed_row["query_id"]
        qx = float(seed_row["query_x"])
        qy = float(seed_row["query_y"])
        scale_counter: Counter[str] = Counter()

        for tile in tiles:
            min_x = float(tile["min_x"])
            min_y = float(tile["min_y"])
            max_x = float(tile["max_x"])
            max_y = float(tile["max_y"])
            point_dist = point_to_rect_distance(qx, qy, min_x, min_y, max_x, max_y)
            if point_dist > args.truth_radius_m:
                continue

            center_dist = rect_center_distance(qx, qy, float(tile["center_x"]), float(tile["center_y"]))
            row = {
                "query_id": query_id,
                "tile_id": tile["tile_id"],
                "tile_size_m": tile["tile_size_m"],
                "source_tif": tile["source_tif"],
                "image_path": tile["image_path"],
                "center_x": tile["center_x"],
                "center_y": tile["center_y"],
                "min_x": tile["min_x"],
                "min_y": tile["min_y"],
                "max_x": tile["max_x"],
                "max_y": tile["max_y"],
                "intersects_truth_radius": "1",
                "distance_point_to_tile_m": f"{point_dist:.3f}",
                "distance_tile_center_to_query_m": f"{center_dist:.3f}",
                "contains_query_point": "1" if point_dist == 0.0 else "0",
            }
            truth_map_rows.append(row)
            per_query_truth[query_id].append(row)
            scale_counter[row["tile_size_m"]] += 1

        truth_summary_rows.append(
            {
                "query_id": query_id,
                "flight_id": seed_row["flight_id"],
                "image_name": seed_row["image_name"],
                "query_image_path": seed_row["query_image_path"],
                "query_x": seed_row["query_x"],
                "query_y": seed_row["query_y"],
                "query_crs": seed_row["query_crs"],
                "truth_radius_m": f"{args.truth_radius_m:.1f}",
                "truth_count_total": str(len(per_query_truth[query_id])),
                **{
                    f"truth_count_{int(float(scale))}m": str(scale_counter[scale])
                    for scale in scale_values
                },
            }
        )

    seed_csv = out_dir / "queries_truth_seed.csv"
    summary_csv = out_dir / "query_truth.csv"
    mapping_csv = out_dir / "query_truth_tiles.csv"

    def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
        if not rows:
            raise SystemExit(f"No rows to write for {path}")
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    write_csv(seed_csv, seed_rows)
    write_csv(summary_csv, truth_summary_rows)
    write_csv(mapping_csv, truth_map_rows)

    for query_id, rows in per_query_truth.items():
        rows_sorted = sorted(rows, key=lambda item: (float(item["distance_point_to_tile_m"]), float(item["tile_size_m"])))
        info = query_infos[query_id]
        query_dir = review_dir / query_id
        truth_tiles_dir = query_dir / "truth_tiles"
        ensure_dir(truth_tiles_dir)
        note_path = query_dir / "truth_summary.md"
        with note_path.open("w", encoding="utf-8") as f:
            f.write(f"# {query_id}\n\n")
            f.write(f"- Flight: {info['flight_id']}\n")
            f.write(f"- Image: {info['image_name']}\n")
            f.write(f"- Query image path: {info['query_image_path']}\n")
            f.write(f"- Query CRS: {info['query_crs']}\n")
            f.write(f"- Query projected point: ({info['query_x']}, {info['query_y']})\n")
            f.write(f"- Truth tile count: {len(rows_sorted)}\n\n")
            f.write("| tile_id | scale_m | point_dist_m | center_dist_m | contains_query_point | copied_truth_image |\n")
            f.write("| --- | --- | --- | --- | --- | --- |\n")
            for row in rows_sorted:
                src_image = Path(row["image_path"])
                dst_image = truth_tiles_dir / src_image.name
                if not dst_image.exists():
                    shutil.copy2(src_image, dst_image)
                f.write(
                    f"| {row['tile_id']} | {row['tile_size_m']} | {row['distance_point_to_tile_m']} | "
                    f"{row['distance_tile_center_to_query_m']} | {row['contains_query_point']} | {dst_image} |\n"
                )

    print(f"Satellite CRS: {sat_crs}")
    print(f"Queries: {len(seed_rows)}")
    print(f"Truth mappings: {len(truth_map_rows)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate coverage-based query truth tables against a fixed satellite tile library."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from collections import defaultdict
from pathlib import Path

from PIL import Image
import rasterio
from rasterio.warp import transform


GPS_LAT_RE = re.compile(rb'drone-dji:GpsLatitude="([+-]?[0-9.]+)"')
GPS_LON_RE = re.compile(rb'drone-dji:GpsLongitude="([+-]?[0-9.]+)"')
REL_ALT_RE = re.compile(rb'drone-dji:RelativeAltitude="([+-]?[0-9.]+)"')
ABS_ALT_RE = re.compile(rb'drone-dji:AbsoluteAltitude="([+-]?[0-9.]+)"')
GIMBAL_YAW_RE = re.compile(rb'drone-dji:GimbalYawDegree="([+-]?[0-9.]+)"')
GIMBAL_PITCH_RE = re.compile(rb'drone-dji:GimbalPitchDegree="([+-]?[0-9.]+)"')
GIMBAL_ROLL_RE = re.compile(rb'drone-dji:GimbalRollDegree="([+-]?[0-9.]+)"')
FLIGHT_PITCH_RE = re.compile(rb'drone-dji:FlightPitchDegree="([+-]?[0-9.]+)"')
CAL_FOCAL_RE = re.compile(rb'drone-dji:CalibratedFocalLength="([+-]?[0-9.]+)"')
OPT_CX_RE = re.compile(rb'drone-dji:CalibratedOpticalCenterX="([+-]?[0-9.]+)"')
OPT_CY_RE = re.compile(rb'drone-dji:CalibratedOpticalCenterY="([+-]?[0-9.]+)"')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate coverage-based truth from raw UAV metadata and fixed satellite tiles.")
    parser.add_argument("--selected-query-csv", required=True)
    parser.add_argument("--tile-metadata-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--coverage-threshold", type=float, default=0.4)
    parser.add_argument(
        "--footprint-core-ratio",
        type=float,
        default=0.6,
        help="Use the central ratio of the image to define the main-view coverage proxy.",
    )
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_binary_metadata(image_path: Path) -> dict[str, float]:
    data = image_path.read_bytes()[:400000]

    def grab(pattern: re.Pattern[bytes], key: str, default: float | None = None) -> float | None:
        match = pattern.search(data)
        if not match:
            return default
        return float(match.group(1))

    lat = grab(GPS_LAT_RE, "latitude")
    lon = grab(GPS_LON_RE, "longitude")
    if lat is None or lon is None:
        raise SystemExit(f"Missing GPS in {image_path}")
    return {
        "latitude": lat,
        "longitude": lon,
        "relative_altitude": grab(REL_ALT_RE, "relative_altitude", 0.0) or 0.0,
        "absolute_altitude": grab(ABS_ALT_RE, "absolute_altitude", 0.0) or 0.0,
        "gimbal_yaw_degree": grab(GIMBAL_YAW_RE, "gimbal_yaw_degree", 0.0) or 0.0,
        "gimbal_pitch_degree": grab(GIMBAL_PITCH_RE, "gimbal_pitch_degree", -90.0) or -90.0,
        "gimbal_roll_degree": grab(GIMBAL_ROLL_RE, "gimbal_roll_degree", 0.0) or 0.0,
        "flight_pitch_degree": grab(FLIGHT_PITCH_RE, "flight_pitch_degree", 0.0) or 0.0,
        "calibrated_focal_length_px": grab(CAL_FOCAL_RE, "calibrated_focal_length_px"),
        "optical_center_x": grab(OPT_CX_RE, "optical_center_x"),
        "optical_center_y": grab(OPT_CY_RE, "optical_center_y"),
    }


def resolve_satellite_crs(tile_rows: list[dict[str, str]]) -> str:
    source_tif = tile_rows[0].get("source_tif", "")
    if not source_tif:
        raise SystemExit("tiles.csv missing source_tif")
    with rasterio.open(source_tif) as ds:
        if ds.crs is None:
            raise SystemExit(f"Missing CRS in {source_tif}")
        return ds.crs.to_string()


def dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n = math.sqrt(dot(v, v))
    if n == 0:
        raise ValueError("Zero-length vector")
    return (v[0] / n, v[1] / n, v[2] / n)


def cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def center_direction(yaw_deg: float, pitch_deg: float) -> tuple[float, float, float]:
    yaw = math.radians(yaw_deg)
    elev = math.radians(pitch_deg)
    return norm((math.cos(elev) * math.sin(yaw), math.cos(elev) * math.cos(yaw), math.sin(elev)))


def camera_basis(yaw_deg: float, pitch_deg: float) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    forward = center_direction(yaw_deg, pitch_deg)
    yaw = math.radians(yaw_deg)
    right = norm((math.cos(yaw), -math.sin(yaw), 0.0))
    up = norm(cross(right, forward))
    return forward, right, up


def ray_from_pixel(
    u: float,
    v: float,
    width: int,
    height: int,
    focal_px: float,
    cx: float,
    cy: float,
    yaw_deg: float,
    pitch_deg: float,
) -> tuple[float, float, float]:
    forward, right, up = camera_basis(yaw_deg, pitch_deg)
    xn = (u - cx) / focal_px
    yn = (v - cy) / focal_px
    ray = (
        forward[0] + xn * right[0] - yn * up[0],
        forward[1] + xn * right[1] - yn * up[1],
        forward[2] + xn * right[2] - yn * up[2],
    )
    return norm(ray)


def intersect_ground(
    ray: tuple[float, float, float],
    height_m: float,
    query_x: float,
    query_y: float,
) -> tuple[float, float]:
    if ray[2] >= -1e-6:
        raise ValueError("Ray does not intersect ground plane")
    t = -height_m / ray[2]
    return query_x + t * ray[0], query_y + t * ray[1]


def polygon_area(poly: list[tuple[float, float]]) -> float:
    area = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def inside_left(p: tuple[float, float], x_min: float) -> bool:
    return p[0] >= x_min


def inside_right(p: tuple[float, float], x_max: float) -> bool:
    return p[0] <= x_max


def inside_bottom(p: tuple[float, float], y_min: float) -> bool:
    return p[1] >= y_min


def inside_top(p: tuple[float, float], y_max: float) -> bool:
    return p[1] <= y_max


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

    poly = clip(poly, lambda p: inside_left(p, min_x), lambda a, b: segment_intersect_vertical(a, b, min_x))
    poly = clip(poly, lambda p: inside_right(p, max_x), lambda a, b: segment_intersect_vertical(a, b, max_x))
    poly = clip(poly, lambda p: inside_bottom(p, min_y), lambda a, b: segment_intersect_horizontal(a, b, min_y))
    poly = clip(poly, lambda p: inside_top(p, max_y), lambda a, b: segment_intersect_horizontal(a, b, max_y))
    return poly


def point_in_rect(x: float, y: float, min_x: float, min_y: float, max_x: float, max_y: float) -> bool:
    return min_x <= x <= max_x and min_y <= y <= max_y


def footprint_polygon(
    image_path: Path,
    query_x: float,
    query_y: float,
    core_ratio: float,
) -> tuple[list[tuple[float, float]], dict[str, float]]:
    meta = read_binary_metadata(image_path)
    with Image.open(image_path) as img:
        width, height = img.size

    focal_px = meta["calibrated_focal_length_px"] or max(width, height)
    cx = meta["optical_center_x"] if meta["optical_center_x"] is not None else width / 2.0
    cy = meta["optical_center_y"] if meta["optical_center_y"] is not None else height / 2.0
    height_m = max(meta["relative_altitude"], 1.0)
    yaw_deg = meta["gimbal_yaw_degree"]
    pitch_deg = meta["gimbal_pitch_degree"]

    x_margin = (1.0 - core_ratio) * width * 0.5
    y_margin = (1.0 - core_ratio) * height * 0.5
    corners_px = [
        (x_margin, y_margin),
        (width - 1.0 - x_margin, y_margin),
        (width - 1.0 - x_margin, height - 1.0 - y_margin),
        (x_margin, height - 1.0 - y_margin),
    ]
    poly = []
    for u, v in corners_px:
        ray = ray_from_pixel(u, v, width, height, focal_px, cx, cy, yaw_deg, pitch_deg)
        poly.append(intersect_ground(ray, height_m, query_x, query_y))
    area = polygon_area(poly)
    info = {
        **meta,
        "image_width_px": float(width),
        "image_height_px": float(height),
        "footprint_core_ratio": core_ratio,
        "footprint_area_m2": area,
    }
    return poly, info


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    review_dir = out_dir / "per_query"
    ensure_dir(out_dir)
    ensure_dir(review_dir)

    selected_rows = load_csv(Path(args.selected_query_csv))
    if not selected_rows:
        raise SystemExit("No selected queries found.")

    tiles = load_csv(Path(args.tile_metadata_csv))
    if not tiles:
        raise SystemExit("No tiles found in tile metadata CSV.")
    sat_crs = resolve_satellite_crs(tiles)

    lons = [float(row["longitude"]) for row in selected_rows]
    lats = [float(row["latitude"]) for row in selected_rows]
    xs, ys = transform("EPSG:4326", sat_crs, lons, lats)

    seed_rows: list[dict[str, str]] = []
    truth_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, str]] = []
    per_query_truth: dict[str, list[dict[str, str]]] = defaultdict(list)

    scale_values = sorted({tile["tile_size_m"] for tile in tiles}, key=lambda x: float(x))

    for idx, (row, qx, qy) in enumerate(zip(selected_rows, xs, ys), start=1):
        query_id = f"q_{idx:03d}"
        query_image_path = Path(row["copied_path"])
        poly, info = footprint_polygon(query_image_path, qx, qy, args.footprint_core_ratio)
        if info["footprint_area_m2"] <= 0:
            raise SystemExit(f"Non-positive footprint area for {query_image_path}")

        seed = {
            "query_id": query_id,
            "flight_id": row["flight_id"],
            "image_name": row["image_name"],
            "query_image_path": str(query_image_path),
            "latitude": f"{info['latitude']:.9f}",
            "longitude": f"{info['longitude']:.9f}",
            "absolute_altitude": f"{info['absolute_altitude']:.3f}",
            "relative_altitude": f"{info['relative_altitude']:.3f}",
            "gimbal_yaw_degree": f"{info['gimbal_yaw_degree']:.2f}",
            "gimbal_pitch_degree": f"{info['gimbal_pitch_degree']:.2f}",
            "gimbal_roll_degree": f"{info['gimbal_roll_degree']:.2f}",
            "flight_pitch_degree": f"{info['flight_pitch_degree']:.2f}",
            "calibrated_focal_length_px": f"{(info['calibrated_focal_length_px'] or 0.0):.6f}",
            "optical_center_x": f"{(info['optical_center_x'] or 0.0):.3f}",
            "optical_center_y": f"{(info['optical_center_y'] or 0.0):.3f}",
            "image_width_px": f"{info['image_width_px']:.0f}",
            "image_height_px": f"{info['image_height_px']:.0f}",
            "query_x": f"{qx:.3f}",
            "query_y": f"{qy:.3f}",
            "query_crs": sat_crs,
            "footprint_area_m2": f"{info['footprint_area_m2']:.3f}",
            "footprint_core_ratio": f"{info['footprint_core_ratio']:.2f}",
            "footprint_polygon_xy": json.dumps([[round(x, 3), round(y, 3)] for x, y in poly], ensure_ascii=False),
        }
        seed_rows.append(seed)

        scale_counts = defaultdict(int)
        for tile in tiles:
            min_x = float(tile["min_x"])
            min_y = float(tile["min_y"])
            max_x = float(tile["max_x"])
            max_y = float(tile["max_y"])
            inter_poly = clip_polygon_to_rect(poly, min_x, min_y, max_x, max_y)
            if len(inter_poly) < 3:
                continue
            inter_area = polygon_area(inter_poly)
            if inter_area <= 0:
                continue
            coverage_ratio = inter_area / info["footprint_area_m2"]
            contains_center = point_in_rect(qx, qy, min_x, min_y, max_x, max_y)
            if coverage_ratio < args.coverage_threshold:
                continue

            truth_row = {
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
                "coverage_ratio": f"{coverage_ratio:.6f}",
                "intersection_area_m2": f"{inter_area:.3f}",
                "contains_query_center": "1" if contains_center else "0",
                "is_truth_cov_0_4": "1",
            }
            truth_rows.append(truth_row)
            per_query_truth[query_id].append(truth_row)
            scale_counts[tile["tile_size_m"]] += 1

        summary_row = {
            "query_id": query_id,
            "flight_id": row["flight_id"],
            "image_name": row["image_name"],
            "query_image_path": str(query_image_path),
            "query_x": f"{qx:.3f}",
            "query_y": f"{qy:.3f}",
            "query_crs": sat_crs,
            "coverage_threshold": f"{args.coverage_threshold:.2f}",
            "footprint_core_ratio": f"{args.footprint_core_ratio:.2f}",
            "footprint_area_m2": f"{info['footprint_area_m2']:.3f}",
            "truth_count_total": str(len(per_query_truth[query_id])),
            **{
                f"truth_count_{int(float(scale))}m": str(scale_counts[scale])
                for scale in scale_values
            },
        }
        summary_rows.append(summary_row)

    def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
        if not rows:
            raise SystemExit(f"No rows to write for {path}")
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    write_csv(out_dir / "queries_truth_seed.csv", seed_rows)
    write_csv(out_dir / "query_truth.csv", summary_rows)
    write_csv(out_dir / "query_truth_tiles.csv", truth_rows)

    for seed in seed_rows:
        query_id = seed["query_id"]
        rows = sorted(per_query_truth.get(query_id, []), key=lambda r: (-float(r["coverage_ratio"]), float(r["tile_size_m"])))
        qdir = review_dir / query_id
        tdir = qdir / "truth_tiles"
        ensure_dir(tdir)
        note = qdir / "truth_summary.md"
        with note.open("w", encoding="utf-8") as f:
            f.write(f"# {query_id}\n\n")
            f.write(f"- Flight: {seed['flight_id']}\n")
            f.write(f"- Image: {seed['image_name']}\n")
            f.write(f"- Query image path: {seed['query_image_path']}\n")
            f.write(f"- Coverage threshold: {args.coverage_threshold:.2f}\n")
            f.write(f"- Footprint core ratio: {args.footprint_core_ratio:.2f}\n")
            f.write(f"- Footprint area (m2): {seed['footprint_area_m2']}\n")
            f.write(f"- Truth tile count: {len(rows)}\n\n")
            f.write("| tile_id | scale_m | coverage_ratio | contains_center | copied_truth_image |\n")
            f.write("| --- | --- | --- | --- | --- |\n")
            for row in rows:
                src = Path(row["image_path"])
                dst = tdir / src.name
                if not dst.exists():
                    shutil.copy2(src, dst)
                f.write(
                    f"| {row['tile_id']} | {row['tile_size_m']} | {row['coverage_ratio']} | "
                    f"{row['contains_query_center']} | {dst} |\n"
                )

    zero_truth = sum(1 for row in summary_rows if int(row["truth_count_total"]) == 0)
    print(f"Satellite CRS: {sat_crs}")
    print(f"Queries: {len(seed_rows)}")
    print(f"Truth mappings: {len(truth_rows)}")
    print(f"Zero-truth queries: {zero_truth}")


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    main()

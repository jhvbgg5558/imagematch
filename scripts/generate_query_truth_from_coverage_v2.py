#!/usr/bin/env python3
"""Generate refined coverage truth with valid-content filtering and strict/soft labels."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
import rasterio
from rasterio.errors import CRSError
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
    parser = argparse.ArgumentParser(description="Generate refined coverage truth from UAV metadata and fixed satellite tiles.")
    parser.add_argument("--selected-query-csv", required=True)
    parser.add_argument("--tile-metadata-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--flight-id", default=None, help="Optional single-flight filter.")
    parser.add_argument("--coverage-threshold", type=float, default=0.4)
    parser.add_argument("--footprint-core-ratio", type=float, default=0.6)
    parser.add_argument("--min-valid-ratio", type=float, default=0.6)
    parser.add_argument("--black-threshold", type=int, default=8)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_binary_metadata(image_path: Path) -> dict[str, float]:
    data = image_path.read_bytes()[:400000]

    def grab(pattern: re.Pattern[bytes], default: float | None = None) -> float | None:
        match = pattern.search(data)
        if not match:
            return default
        return float(match.group(1))

    lat = grab(GPS_LAT_RE)
    lon = grab(GPS_LON_RE)
    if lat is None or lon is None:
        raise SystemExit(f"Missing GPS in {image_path}")
    return {
        "latitude": lat,
        "longitude": lon,
        "relative_altitude": grab(REL_ALT_RE, 0.0) or 0.0,
        "absolute_altitude": grab(ABS_ALT_RE, 0.0) or 0.0,
        "gimbal_yaw_degree": grab(GIMBAL_YAW_RE, 0.0) or 0.0,
        "gimbal_pitch_degree": grab(GIMBAL_PITCH_RE, -90.0) or -90.0,
        "gimbal_roll_degree": grab(GIMBAL_ROLL_RE, 0.0) or 0.0,
        "flight_pitch_degree": grab(FLIGHT_PITCH_RE, 0.0) or 0.0,
        "calibrated_focal_length_px": grab(CAL_FOCAL_RE),
        "optical_center_x": grab(OPT_CX_RE),
        "optical_center_y": grab(OPT_CY_RE),
    }


def resolve_satellite_crs(tile_rows: list[dict[str, str]]) -> str:
    with rasterio.open(tile_rows[0]["source_tif"]) as ds:
        if ds.crs is None:
            raise SystemExit("Missing CRS in source tif")
        return ds.crs.to_string()


def latlon_to_epsg32650(lat: float, lon: float) -> tuple[float, float]:
    # Pure-Python WGS84 -> UTM zone 50N fallback for environments with broken PROJ databases.
    a = 6378137.0
    f = 1 / 298.257223563
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    k0 = 0.9996
    lon0 = math.radians(117.0)

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    n = a / math.sqrt(1 - e2 * math.sin(lat_rad) ** 2)
    t = math.tan(lat_rad) ** 2
    c = ep2 * math.cos(lat_rad) ** 2
    a_term = math.cos(lat_rad) * (lon_rad - lon0)

    m = a * (
        (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * lat_rad
        - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * lat_rad)
        + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * lat_rad)
        - (35 * e2**3 / 3072) * math.sin(6 * lat_rad)
    )

    x = k0 * n * (
        a_term
        + (1 - t + c) * a_term**3 / 6
        + (5 - 18 * t + t**2 + 72 * c - 58 * ep2) * a_term**5 / 120
    ) + 500000.0
    y = k0 * (
        m
        + n
        * math.tan(lat_rad)
        * (
            a_term**2 / 2
            + (5 - t + 9 * c + 4 * c**2) * a_term**4 / 24
            + (61 - 58 * t + t**2 + 600 * c - 330 * ep2) * a_term**6 / 720
        )
    )
    return x, y


def project_query_points(lons: list[float], lats: list[float], sat_crs: str) -> tuple[list[float], list[float]]:
    try:
        xs, ys = transform("EPSG:4326", sat_crs, lons, lats)
        return list(xs), list(ys)
    except Exception:
        if sat_crs.upper() != "EPSG:32650":
            raise
        projected = [latlon_to_epsg32650(lat, lon) for lon, lat in zip(lons, lats)]
        return [x for x, _ in projected], [y for _, y in projected]


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


def intersect_ground(ray: tuple[float, float, float], height_m: float, query_x: float, query_y: float) -> tuple[float, float]:
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


def footprint_polygon(image_path: Path, query_x: float, query_y: float, core_ratio: float) -> tuple[list[tuple[float, float]], dict[str, float]]:
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
        ray = ray_from_pixel(u, v, width, focal_px, cx, cy, yaw_deg, pitch_deg)
        poly.append(intersect_ground(ray, height_m, query_x, query_y))
    info = {
        **meta,
        "image_width_px": float(width),
        "image_height_px": float(height),
        "footprint_core_ratio": core_ratio,
        "footprint_area_m2": polygon_area(poly),
    }
    return poly, info


def tile_content_metrics(image_path: Path, black_threshold: int) -> dict[str, float]:
    with Image.open(image_path) as img:
        arr = np.asarray(img.convert("RGB"))
    black_mask = np.all(arr <= black_threshold, axis=2)
    total = black_mask.size
    black_ratio = float(black_mask.sum()) / float(total)
    valid_ratio = 1.0 - black_ratio
    return {
        "black_pixel_ratio": black_ratio,
        "valid_pixel_ratio": valid_ratio,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise SystemExit(f"No rows to write for {path}")
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    ensure_dir(out_dir / "per_query")

    selected_rows = load_csv(Path(args.selected_query_csv))
    if args.flight_id:
        selected_rows = [row for row in selected_rows if row["flight_id"] == args.flight_id]
    if not selected_rows:
        raise SystemExit("No selected queries found after filtering.")

    tiles = load_csv(Path(args.tile_metadata_csv))
    sat_crs = resolve_satellite_crs(tiles)

    tile_metrics_cache: dict[str, dict[str, float]] = {}
    for tile in tiles:
        tile_metrics_cache[tile["tile_id"]] = tile_content_metrics(Path(tile["image_path"]), args.black_threshold)

    lons = [float(row["longitude"]) for row in selected_rows]
    lats = [float(row["latitude"]) for row in selected_rows]
    xs, ys = project_query_points(lons, lats, sat_crs)

    seed_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, str]] = []
    truth_rows: list[dict[str, str]] = []
    diagnostics_rows: list[dict[str, str]] = []
    per_query_truth: dict[str, list[dict[str, str]]] = defaultdict(list)
    scale_values = sorted({tile["tile_size_m"] for tile in tiles}, key=lambda x: float(x))

    for idx, (row, qx, qy) in enumerate(zip(selected_rows, xs, ys), start=1):
        query_id = f"q_{idx:03d}"
        query_image_path = Path(row["copied_path"])
        poly, info = footprint_polygon(query_image_path, qx, qy, args.footprint_core_ratio)

        seed_rows.append(
            {
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
        )

        strict_total = 0
        soft_total = 0
        scale_counts = defaultdict(int)
        strict_scale_counts = defaultdict(int)
        soft_scale_counts = defaultdict(int)

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
            if coverage_ratio < args.coverage_threshold:
                continue
            contains_center = point_in_rect(qx, qy, min_x, min_y, max_x, max_y)
            content = tile_metrics_cache[tile["tile_id"]]
            is_strict = int(content["valid_pixel_ratio"] >= args.min_valid_ratio)
            is_soft = int(not is_strict)
            truth_quality_score = coverage_ratio * content["valid_pixel_ratio"]

            out_row = {
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
                "valid_pixel_ratio": f"{content['valid_pixel_ratio']:.6f}",
                "black_pixel_ratio": f"{content['black_pixel_ratio']:.6f}",
                "truth_quality_score": f"{truth_quality_score:.6f}",
                "is_strict_truth": str(is_strict),
                "is_soft_truth": str(is_soft),
            }
            truth_rows.append(out_row)
            per_query_truth[query_id].append(out_row)
            scale_counts[tile["tile_size_m"]] += 1
            if is_strict:
                strict_total += 1
                strict_scale_counts[tile["tile_size_m"]] += 1
            else:
                soft_total += 1
                soft_scale_counts[tile["tile_size_m"]] += 1
                diagnostics_rows.append(
                    {
                        "query_id": query_id,
                        "flight_id": row["flight_id"],
                        "tile_id": tile["tile_id"],
                        "tile_size_m": tile["tile_size_m"],
                        "coverage_ratio": f"{coverage_ratio:.6f}",
                        "valid_pixel_ratio": f"{content['valid_pixel_ratio']:.6f}",
                        "black_pixel_ratio": f"{content['black_pixel_ratio']:.6f}",
                        "contains_query_center": "1" if contains_center else "0",
                        "soft_reason": "low_valid_pixel_ratio",
                    }
                )

        summary = {
            "query_id": query_id,
            "flight_id": row["flight_id"],
            "image_name": row["image_name"],
            "query_image_path": str(query_image_path),
            "query_x": f"{qx:.3f}",
            "query_y": f"{qy:.3f}",
            "query_crs": sat_crs,
            "coverage_threshold": f"{args.coverage_threshold:.2f}",
            "footprint_core_ratio": f"{args.footprint_core_ratio:.2f}",
            "min_valid_ratio": f"{args.min_valid_ratio:.2f}",
            "footprint_area_m2": f"{info['footprint_area_m2']:.3f}",
            "truth_count_total": str(sum(scale_counts.values())),
            "strict_truth_count_total": str(strict_total),
            "soft_truth_count_total": str(soft_total),
        }
        for scale in scale_values:
            scale_name = f"{int(float(scale))}m"
            summary[f"truth_count_{scale_name}"] = str(scale_counts[scale])
            summary[f"strict_truth_count_{scale_name}"] = str(strict_scale_counts[scale])
            summary[f"soft_truth_count_{scale_name}"] = str(soft_scale_counts[scale])
        summary_rows.append(summary)

    write_csv(out_dir / "queries_truth_seed.csv", seed_rows)
    write_csv(out_dir / "query_truth.csv", summary_rows)
    write_csv(out_dir / "query_truth_tiles.csv", truth_rows)
    if diagnostics_rows:
        write_csv(out_dir / "filtered_tiles_diagnostics.csv", diagnostics_rows)

    for seed in seed_rows:
        query_id = seed["query_id"]
        qdir = out_dir / "per_query" / query_id
        tdir = qdir / "truth_tiles"
        ensure_dir(tdir)
        rows = sorted(
            per_query_truth.get(query_id, []),
            key=lambda r: (
                -int(r["is_strict_truth"]),
                -float(r["coverage_ratio"]),
                -float(r["valid_pixel_ratio"]),
                float(r["tile_size_m"]),
            ),
        )
        with (qdir / "truth_summary.md").open("w", encoding="utf-8") as f:
            f.write(f"# {query_id}\n\n")
            f.write(f"- Flight: {seed['flight_id']}\n")
            f.write(f"- Image: {seed['image_name']}\n")
            f.write(f"- Query image path: {seed['query_image_path']}\n")
            f.write(f"- Coverage threshold: {args.coverage_threshold:.2f}\n")
            f.write(f"- Footprint core ratio: {args.footprint_core_ratio:.2f}\n")
            f.write(f"- Min valid ratio: {args.min_valid_ratio:.2f}\n")
            f.write(f"- Footprint area (m2): {seed['footprint_area_m2']}\n")
            f.write(f"- Strict truth count: {sum(int(r['is_strict_truth']) for r in rows)}\n")
            f.write(f"- Soft truth count: {sum(int(r['is_soft_truth']) for r in rows)}\n\n")
            f.write("| tile_id | scale_m | coverage_ratio | valid_pixel_ratio | black_pixel_ratio | contains_center | strict | copied_truth_image |\n")
            f.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")
            for row in rows:
                src = Path(row["image_path"])
                dst = tdir / src.name
                if not dst.exists():
                    shutil.copy2(src, dst)
                f.write(
                    f"| {row['tile_id']} | {row['tile_size_m']} | {row['coverage_ratio']} | {row['valid_pixel_ratio']} | "
                    f"{row['black_pixel_ratio']} | {row['contains_query_center']} | {row['is_strict_truth']} | {dst} |\n"
                )

    print(f"Satellite CRS: {sat_crs}")
    print(f"Queries: {len(seed_rows)}")
    print(f"Truth mappings: {len(truth_rows)}")
    print(f"Strict truth total: {sum(int(r['is_strict_truth']) for r in truth_rows)}")
    print(f"Soft truth total: {sum(int(r['is_soft_truth']) for r in truth_rows)}")


if __name__ == "__main__":
    main()

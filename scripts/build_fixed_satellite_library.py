#!/usr/bin/env python3
"""Build a fixed multi-scale satellite tile library for the current flight area.

Inputs:
- selected query CSV with flight identifiers
- raw UAV flight directories containing original JPG images with DJI XMP GPS
- satellite GeoTIFF directory

Outputs:
- fixed multi-scale satellite tile images at native crop resolution by default
- tile metadata CSV
- ROI summary JSON

Used for:
- current engineering-style retrieval task
- fixed candidate library construction independent of any single query image
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

import rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform
from rasterio.windows import from_bounds


GPS_LAT_RE = re.compile(rb'drone-dji:GpsLatitude="([+-]?[0-9.]+)"')
GPS_LON_RE = re.compile(rb'drone-dji:GpsLongitude="([+-]?[0-9.]+)"')
MRK_LAT_RE = re.compile(r"([+-]?[0-9.]+),Lat")
MRK_LON_RE = re.compile(r"([+-]?[0-9.]+),Lon")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fixed multi-scale satellite library for selected flights.")
    parser.add_argument("--selected-query-csv", required=True)
    parser.add_argument("--raw-flight-root", required=True)
    parser.add_argument("--sat-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--metadata-csv", required=True)
    parser.add_argument("--roi-summary-json", required=True)
    parser.add_argument("--tile-sizes", type=float, nargs="+", default=[80.0, 120.0, 200.0])
    parser.add_argument("--overlap", type=float, default=0.25)
    parser.add_argument(
        "--resize",
        type=int,
        default=0,
        help="Optional output size. Use 0 to keep native crop resolution.",
    )
    parser.add_argument("--roi-buffer-meters", type=float, default=250.0)
    return parser.parse_args()


def encode_affine(transform_obj: rasterio.Affine) -> str:
    return json.dumps([transform_obj.a, transform_obj.b, transform_obj.c, transform_obj.d, transform_obj.e, transform_obj.f])


def tile_id_for(center_x: float, center_y: float, tile_size: float) -> str:
    return f"s{int(round(tile_size))}_x{center_x:.3f}_y{center_y:.3f}"


def aligned_start(origin: float, start: float, step: float) -> float:
    return origin + math.floor((start - origin) / step) * step


def bounds_intersection(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> tuple[float, float, float, float] | None:
    left = max(a[0], b[0])
    bottom = max(a[1], b[1])
    right = min(a[2], b[2])
    top = min(a[3], b[3])
    if left >= right or bottom >= top:
        return None
    return left, bottom, right, top


def iter_rasters(src_dir: Path) -> list[Path]:
    return sorted(src_dir.glob("*.tif"))


def read_selected_flights(path: Path) -> list[str]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return sorted({row["flight_id"] for row in rows})


def extract_lat_lon(image_path: Path) -> tuple[float, float] | None:
    with image_path.open("rb") as f:
        data = f.read(262144)
    lat_match = GPS_LAT_RE.search(data)
    lon_match = GPS_LON_RE.search(data)
    if not lat_match or not lon_match:
        return None
    return float(lat_match.group(1)), float(lon_match.group(1))


def read_points_from_mrk(mrk_path: Path) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    with mrk_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            lat_match = MRK_LAT_RE.search(line)
            lon_match = MRK_LON_RE.search(line)
            if not lat_match or not lon_match:
                continue
            points.append((float(lat_match.group(1)), float(lon_match.group(1))))
    return points


def read_all_flight_points(raw_root: Path, flight_ids: list[str], dst_crs: str) -> list[tuple[float, float]]:
    lon_vals: list[float] = []
    lat_vals: list[float] = []
    for flight_id in flight_ids:
        flight_dir = raw_root / flight_id
        mrk_files = sorted(flight_dir.glob("*.MRK"))
        if mrk_files:
            for lat, lon in read_points_from_mrk(mrk_files[0]):
                lat_vals.append(lat)
                lon_vals.append(lon)
            continue

        for image_path in sorted(flight_dir.glob("*.JPG")):
            lat_lon = extract_lat_lon(image_path)
            if lat_lon is None:
                continue
            lat, lon = lat_lon
            lat_vals.append(lat)
            lon_vals.append(lon)

    xs, ys = transform("EPSG:4326", dst_crs, lon_vals, lat_vals)
    return list(zip(xs, ys))


def write_tile_image(out_path: Path, data) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "PNG",
        "width": data.shape[2],
        "height": data.shape[1],
        "count": data.shape[0],
        "dtype": data.dtype,
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data)


def main() -> None:
    args = parse_args()
    sat_dir = Path(args.sat_dir)
    out_dir = Path(args.out_dir)
    metadata_csv = Path(args.metadata_csv)
    roi_summary_json = Path(args.roi_summary_json)
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata_csv.parent.mkdir(parents=True, exist_ok=True)
    roi_summary_json.parent.mkdir(parents=True, exist_ok=True)

    sat_paths = iter_rasters(sat_dir)
    if not sat_paths:
        raise SystemExit(f"No satellite rasters found under {sat_dir}")

    with rasterio.open(sat_paths[0]) as sample_ds:
        if sample_ds.crs is None:
            raise SystemExit(f"Missing CRS in {sat_paths[0]}")
        sat_crs = sample_ds.crs.to_string()

    flight_ids = read_selected_flights(Path(args.selected_query_csv))
    points = read_all_flight_points(Path(args.raw_flight_root), flight_ids, sat_crs)
    if not points:
        raise SystemExit("No valid flight points found from raw JPG metadata.")

    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    roi_bounds = (
        min(xs) - args.roi_buffer_meters,
        min(ys) - args.roi_buffer_meters,
        max(xs) + args.roi_buffer_meters,
        max(ys) + args.roi_buffer_meters,
    )

    summary = {
        "flight_ids": flight_ids,
        "satellite_crs": sat_crs,
        "point_count": len(points),
        "roi_bounds": roi_bounds,
        "tile_sizes_m": args.tile_sizes,
        "overlap": args.overlap,
        "resize": args.resize,
        "image_resolution_mode": "native" if args.resize <= 0 else f"resized_{args.resize}",
    }
    roi_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    dedup: set[str] = set()
    written = 0
    skipped_bad_rasters: list[str] = []
    with metadata_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "tile_id",
                "scale_level_m",
                "tile_size_m",
                "image_path",
                "source_tif",
                "pixel_col_off",
                "pixel_row_off",
                "pixel_width",
                "pixel_height",
                "native_width",
                "native_height",
                "gsd_x_m_per_px",
                "gsd_y_m_per_px",
                "center_x",
                "center_y",
                "min_x",
                "min_y",
                "max_x",
                "max_y",
                "affine",
            ]
        )

        for sat_path in sat_paths:
            try:
                with rasterio.open(sat_path) as ds:
                    sat_bounds = (ds.bounds.left, ds.bounds.bottom, ds.bounds.right, ds.bounds.top)
                    overlap_bounds = bounds_intersection(sat_bounds, roi_bounds)
                    if overlap_bounds is None:
                        continue

                    usable_bands = min(3, ds.count)
                    if usable_bands < 1:
                        continue

                    for tile_size in sorted(args.tile_sizes):
                        step = tile_size * (1.0 - args.overlap)
                        x_start = aligned_start(ds.bounds.left, overlap_bounds[0], step)
                        y_start = aligned_start(ds.bounds.bottom, overlap_bounds[1], step)
                        x = x_start
                        while x < overlap_bounds[2]:
                            y = y_start
                            while y < overlap_bounds[3]:
                                min_x = x
                                min_y = y
                                max_x = x + tile_size
                                max_y = y + tile_size
                                candidate = (min_x, min_y, max_x, max_y)
                                if bounds_intersection(candidate, roi_bounds) is not None:
                                    center_x = min_x + tile_size / 2.0
                                    center_y = min_y + tile_size / 2.0
                                    tile_id = tile_id_for(center_x, center_y, tile_size)
                                    if tile_id not in dedup:
                                        dedup.add(tile_id)
                                        window = from_bounds(
                                            min_x, min_y, max_x, max_y, ds.transform
                                        ).round_offsets().round_lengths()
                                        native_width = int(window.width)
                                        native_height = int(window.height)
                                        if args.resize > 0:
                                            data = ds.read(
                                                indexes=list(range(1, usable_bands + 1)),
                                                window=window,
                                                out_shape=(usable_bands, args.resize, args.resize),
                                                resampling=Resampling.bilinear,
                                                boundless=True,
                                                fill_value=0,
                                            )
                                            out_width = args.resize
                                            out_height = args.resize
                                        else:
                                            data = ds.read(
                                                indexes=list(range(1, usable_bands + 1)),
                                                window=window,
                                                boundless=True,
                                                fill_value=0,
                                            )
                                            out_width = native_width
                                            out_height = native_height
                                        out_path = out_dir / f"{tile_id}.png"
                                        write_tile_image(out_path, data)
                                        affine = rasterio.Affine(
                                            (max_x - min_x) / out_width,
                                            0.0,
                                            min_x,
                                            0.0,
                                            -(max_y - min_y) / out_height,
                                            max_y,
                                        )
                                        writer.writerow(
                                            [
                                                tile_id,
                                                int(round(tile_size)),
                                                tile_size,
                                                str(out_path),
                                                str(sat_path),
                                                int(window.col_off),
                                                int(window.row_off),
                                                out_width,
                                                out_height,
                                                native_width,
                                                native_height,
                                                (max_x - min_x) / out_width,
                                                (max_y - min_y) / out_height,
                                                center_x,
                                                center_y,
                                                min_x,
                                                min_y,
                                                max_x,
                                                max_y,
                                                encode_affine(affine),
                                            ]
                                        )
                                        written += 1
                                y += step
                            x += step
            except Exception:
                skipped_bad_rasters.append(str(sat_path))
                continue

    print(f"Satellite CRS: {sat_crs}")
    print(f"ROI bounds: {tuple(round(v, 3) for v in roi_bounds)}")
    print(f"Written tiles: {written}")
    if skipped_bad_rasters:
        print(f"Skipped bad rasters: {len(skipped_bad_rasters)}")
        for item in skipped_bad_rasters[:10]:
            print(f"  - {item}")


if __name__ == "__main__":
    main()

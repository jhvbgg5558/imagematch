#!/usr/bin/env python3
"""Generate multi-scale satellite tiles over drone ortho coverage."""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
from pathlib import Path
from time import perf_counter

import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tile satellite rasters over the union extent of drone orthophotos."
    )
    parser.add_argument("--sat-dir", required=True, help="Directory with satellite GeoTIFF files.")
    parser.add_argument(
        "--drone-glob",
        required=True,
        help="Glob for drone orthophotos, e.g. '/path/*/odm_orthophoto/odm_orthophoto.tif'.",
    )
    parser.add_argument("--out-dir", required=True, help="Output directory for resized image tiles.")
    parser.add_argument(
        "--metadata-csv",
        required=True,
        help="CSV file that stores tile metadata.",
    )
    parser.add_argument(
        "--tile-sizes",
        type=float,
        nargs="+",
        default=[80.0, 120.0, 200.0],
        help="Ground window sizes in meters.",
    )
    parser.add_argument(
        "--overlap",
        type=float,
        default=0.25,
        help="Overlap ratio between adjacent windows, default 0.25.",
    )
    parser.add_argument(
        "--buffer-meters",
        type=float,
        default=0.0,
        help="Expand drone union extent by this many meters on each side.",
    )
    parser.add_argument(
        "--resize",
        type=int,
        default=512,
        help="Output tile size in pixels, default 512.",
    )
    parser.add_argument(
        "--image-format",
        default="png",
        choices=["png", "jpg"],
        help="Image format for resized tiles.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip writing image files that already exist.",
    )
    return parser.parse_args()


def iter_rasters(src_dir: Path) -> list[Path]:
    return sorted(src_dir.glob("*.tif"))


def read_union_bounds(paths: list[Path]) -> tuple[float, float, float, float, str]:
    if not paths:
        raise SystemExit("No drone orthophotos matched drone_glob")

    left = float("inf")
    bottom = float("inf")
    right = float("-inf")
    top = float("-inf")
    crs = None

    for path in paths:
        with rasterio.open(path) as ds:
            if ds.crs is None:
                raise SystemExit(f"Missing CRS: {path}")
            if crs is None:
                crs = ds.crs
            elif ds.crs != crs:
                raise SystemExit(f"CRS mismatch between drone orthophotos: {path}")

            bounds = ds.bounds
            left = min(left, bounds.left)
            bottom = min(bottom, bounds.bottom)
            right = max(right, bounds.right)
            top = max(top, bounds.top)

    return left, bottom, right, top, crs.to_string()


def expand_bounds(
    bounds: tuple[float, float, float, float], buffer_meters: float
) -> tuple[float, float, float, float]:
    left, bottom, right, top = bounds
    return (
        left - buffer_meters,
        bottom - buffer_meters,
        right + buffer_meters,
        top + buffer_meters,
    )


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


def aligned_start(origin: float, start: float, step: float) -> float:
    return origin + math.floor((start - origin) / step) * step


def encode_affine(transform: rasterio.Affine) -> str:
    return json.dumps([transform.a, transform.b, transform.c, transform.d, transform.e, transform.f])


def tile_id_for(center_x: float, center_y: float, tile_size: float) -> str:
    return f"s{int(round(tile_size))}_x{center_x:.3f}_y{center_y:.3f}"


def write_tile_image(
    out_path: Path,
    data,
    image_format: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "PNG" if image_format == "png" else "JPEG",
        "width": data.shape[2],
        "height": data.shape[1],
        "count": data.shape[0],
        "dtype": data.dtype,
    }
    if image_format == "jpg":
        profile["quality"] = 95

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data)


def main() -> None:
    args = parse_args()
    sat_dir = Path(args.sat_dir)
    out_dir = Path(args.out_dir)
    metadata_csv = Path(args.metadata_csv)
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata_csv.parent.mkdir(parents=True, exist_ok=True)

    sat_paths = iter_rasters(sat_dir)
    if not sat_paths:
        raise SystemExit(f"No satellite GeoTIFF files found under {sat_dir}")

    drone_paths = [Path(p) for p in sorted(glob.glob(args.drone_glob))]
    drone_bounds = read_union_bounds(drone_paths)
    roi_bounds = expand_bounds(drone_bounds[:4], args.buffer_meters)
    roi_crs = drone_bounds[4]

    print(f"Satellite tiles: {len(sat_paths)}")
    print(f"Drone orthos: {len(drone_paths)}")
    print(f"ROI CRS: {roi_crs}")
    print(f"ROI bounds: {tuple(round(v, 3) for v in roi_bounds)}")

    written = 0
    skipped = 0
    bad_sat = 0
    dedup = set()
    t0 = perf_counter()

    with metadata_csv.open("w", newline="", encoding="utf-8") as f:
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
                "center_x",
                "center_y",
                "min_x",
                "min_y",
                "max_x",
                "max_y",
                "affine",
            ]
        )

        for sat_idx, sat_path in enumerate(sat_paths, start=1):
            try:
                with rasterio.open(sat_path) as ds:
                    if ds.crs is None:
                        raise ValueError("missing CRS")
                    if ds.crs.to_string() != roi_crs:
                        raise ValueError(f"CRS mismatch: {ds.crs} != {roi_crs}")

                    sat_bounds = (ds.bounds.left, ds.bounds.bottom, ds.bounds.right, ds.bounds.top)
                    overlap_bounds = bounds_intersection(sat_bounds, roi_bounds)
                    if overlap_bounds is None:
                        continue

                    usable_bands = min(3, ds.count)
                    if usable_bands < 1:
                        raise ValueError("no readable bands")

                    for tile_size in sorted(args.tile_sizes):
                        step = tile_size * (1.0 - args.overlap)
                        if step <= 0:
                            raise SystemExit("Overlap must be smaller than 1.0")

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
                                            min_x,
                                            min_y,
                                            max_x,
                                            max_y,
                                            ds.transform,
                                        ).round_offsets().round_lengths()
                                        data = ds.read(
                                            indexes=list(range(1, usable_bands + 1)),
                                            window=window,
                                            out_shape=(usable_bands, args.resize, args.resize),
                                            boundless=True,
                                            resampling=Resampling.bilinear,
                                        )
                                        ext = "png" if args.image_format == "png" else "jpg"
                                        image_path = out_dir / f"{tile_id}.{ext}"
                                        if args.skip_existing and image_path.exists():
                                            skipped += 1
                                        else:
                                            write_tile_image(image_path, data, args.image_format)
                                            written += 1

                                        writer.writerow(
                                            [
                                                tile_id,
                                                int(round(tile_size)),
                                                tile_size,
                                                str(image_path),
                                                str(sat_path),
                                                int(window.col_off),
                                                int(window.row_off),
                                                int(window.width),
                                                int(window.height),
                                                center_x,
                                                center_y,
                                                min_x,
                                                min_y,
                                                max_x,
                                                max_y,
                                                encode_affine(ds.window_transform(window)),
                                            ]
                                        )
                                y += step
                            x += step
            except Exception as exc:  # pragma: no cover - depends on external files
                bad_sat += 1
                print(f"[WARN] skip {sat_path.name}: {exc}")

            if sat_idx % 200 == 0 or sat_idx == len(sat_paths):
                elapsed = perf_counter() - t0
                print(
                    f"[{sat_idx}/{len(sat_paths)}] written={written} skipped={skipped} "
                    f"bad_sat={bad_sat} elapsed={elapsed/60:.1f}min"
                )

    elapsed = perf_counter() - t0
    print(
        f"Finished. written={written} skipped={skipped} bad_sat={bad_sat} "
        f"elapsed={elapsed/60:.1f}min"
    )
    print(f"Metadata written to {metadata_csv}")


if __name__ == "__main__":
    main()

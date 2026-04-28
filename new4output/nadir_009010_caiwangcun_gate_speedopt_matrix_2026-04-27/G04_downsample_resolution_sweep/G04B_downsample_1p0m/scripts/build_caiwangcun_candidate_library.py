#!/usr/bin/env python3
"""Build a CaiWangCun DOM candidate tile library for the 009/010 gate.

Purpose:
- crop a fixed multi-scale candidate DOM library from a finished CaiWangCun
  orthophoto mosaic;
- keep candidate tile metadata compatible with the existing DINOv2, RoMa v2,
  and formal Pose v1 scripts;
- enforce CaiWangCun DOM/DSM coverage before any retrieval asset is built.

Main inputs:
- a CaiWangCun DOM mosaic in the target CRS;
- a CaiWangCun DSM mosaic in the same target CRS;
- 009/010 query truth seed metadata used only to define the offline ROI.

Main outputs:
- `candidate_library/tiles.csv`;
- `candidate_library/tiles_native/*.png`;
- `candidate_library/roi_summary.json`.

Applicable task constraints:
- query images remain arbitrary UAV images with no runtime geolocation;
- query coordinates are used here only to define this controlled gate ROI;
- no ODM LAZ or SRTM fallback is permitted.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-seed-csv", required=True)
    parser.add_argument("--ortho-mosaic", required=True)
    parser.add_argument("--dsm-mosaic", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--metadata-csv", required=True)
    parser.add_argument("--roi-summary-json", required=True)
    parser.add_argument("--tile-sizes", type=float, nargs="+", default=[200.0, 300.0, 500.0, 700.0])
    parser.add_argument("--overlap", type=float, default=0.25)
    parser.add_argument("--roi-buffer-meters", type=float, default=250.0)
    parser.add_argument(
        "--output-gsd-m",
        type=float,
        default=0.0,
        help="Optional DOM tile output GSD in meters/pixel. Values <=0 keep native mosaic sampling.",
    )
    parser.add_argument(
        "--dsm-expand-margin-m",
        type=float,
        default=250.0,
        help="Require the later candidate DSM request bbox to be covered too.",
    )
    return parser.parse_args()


def resolve_runtime_path(raw_path: str | Path) -> Path:
    text = str(raw_path)
    if os.name == "nt" and text.startswith("/mnt/") and len(text) > 6:
        drive_letter = text[5].upper()
        remainder = text[7:].replace("/", "\\")
        return Path(f"{drive_letter}:\\{remainder}")
    if os.name != "nt" and len(text) >= 3 and text[1:3] in {":\\", ":/"}:
        drive_letter = text[0].lower()
        remainder = text[3:].replace("\\", "/")
        return Path(f"/mnt/{drive_letter}/{remainder}")
    return Path(text)


def as_manifest_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def encode_affine(transform_obj) -> str:
    return json.dumps(
        [
            transform_obj.a,
            transform_obj.b,
            transform_obj.c,
            transform_obj.d,
            transform_obj.e,
            transform_obj.f,
        ],
        ensure_ascii=False,
    )


def aligned_start(origin: float, start: float, step: float) -> float:
    return origin + math.floor((start - origin) / step) * step


def intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def contains(bounds: tuple[float, float, float, float], candidate: tuple[float, float, float, float]) -> bool:
    return (
        candidate[0] >= bounds[0]
        and candidate[1] >= bounds[1]
        and candidate[2] <= bounds[2]
        and candidate[3] <= bounds[3]
    )


def intersect_bounds(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    return max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])


def query_roi(rows: list[dict[str, str]], buffer_m: float) -> tuple[float, float, float, float]:
    xs = [float(row["query_x"]) for row in rows]
    ys = [float(row["query_y"]) for row in rows]
    return min(xs) - buffer_m, min(ys) - buffer_m, max(xs) + buffer_m, max(ys) + buffer_m


def tile_id_for(center_x: float, center_y: float, tile_size: float) -> str:
    return f"cw_s{int(round(tile_size))}_x{center_x:.3f}_y{center_y:.3f}"


def main() -> None:
    args = parse_args()
    ortho_mosaic = resolve_runtime_path(args.ortho_mosaic)
    dsm_mosaic = resolve_runtime_path(args.dsm_mosaic)
    out_dir = resolve_runtime_path(args.out_dir)
    metadata_csv = resolve_runtime_path(args.metadata_csv)
    roi_summary_json = resolve_runtime_path(args.roi_summary_json)
    query_rows = load_csv(resolve_runtime_path(args.query_seed_csv))
    if not query_rows:
        raise SystemExit("query seed CSV is empty")

    try:
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.windows import from_bounds
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("rasterio is required to build the CaiWangCun candidate library") from exc

    ensure_dir(out_dir)
    ensure_dir(metadata_csv.parent)
    ensure_dir(roi_summary_json.parent)

    with rasterio.open(ortho_mosaic) as ortho_ds, rasterio.open(dsm_mosaic) as dsm_ds:
        if ortho_ds.crs is None or dsm_ds.crs is None:
            raise SystemExit("CaiWangCun DOM/DSM mosaics must both have CRS")
        if str(ortho_ds.crs) != str(dsm_ds.crs):
            raise SystemExit(f"DOM/DSM CRS mismatch: {ortho_ds.crs} vs {dsm_ds.crs}")
        if ortho_ds.count < 3:
            raise SystemExit(f"DOM mosaic must have at least 3 bands: {ortho_mosaic}")
        coverage_bounds = intersect_bounds(
            (ortho_ds.bounds.left, ortho_ds.bounds.bottom, ortho_ds.bounds.right, ortho_ds.bounds.top),
            (dsm_ds.bounds.left, dsm_ds.bounds.bottom, dsm_ds.bounds.right, dsm_ds.bounds.top),
        )
        roi_bounds = query_roi(query_rows, args.roi_buffer_meters)
        build_bounds = intersect_bounds(coverage_bounds, roi_bounds)
        if build_bounds[0] >= build_bounds[2] or build_bounds[1] >= build_bounds[3]:
            raise SystemExit("query ROI does not intersect the CaiWangCun DOM/DSM coverage")

        rows: list[dict[str, object]] = []
        skipped_counts = {"outside_roi": 0, "not_fully_covered": 0, "empty_window": 0}
        for tile_size in sorted(args.tile_sizes):
            step = tile_size * (1.0 - args.overlap)
            x_start = aligned_start(coverage_bounds[0], build_bounds[0] - tile_size, step)
            y_start = aligned_start(coverage_bounds[1], build_bounds[1] - tile_size, step)
            x = x_start
            while x <= build_bounds[2]:
                y = y_start
                while y <= build_bounds[3]:
                    min_x = x
                    min_y = y
                    max_x = x + tile_size
                    max_y = y + tile_size
                    tile_bounds = (min_x, min_y, max_x, max_y)
                    request_bounds = (
                        min_x - args.dsm_expand_margin_m,
                        min_y - args.dsm_expand_margin_m,
                        max_x + args.dsm_expand_margin_m,
                        max_y + args.dsm_expand_margin_m,
                    )
                    if not intersects(tile_bounds, roi_bounds):
                        skipped_counts["outside_roi"] += 1
                        y += step
                        continue
                    if not contains(coverage_bounds, tile_bounds) or not contains(coverage_bounds, request_bounds):
                        skipped_counts["not_fully_covered"] += 1
                        y += step
                        continue

                    window = from_bounds(min_x, min_y, max_x, max_y, ortho_ds.transform).round_offsets().round_lengths()
                    native_width = int(window.width)
                    native_height = int(window.height)
                    if native_width <= 0 or native_height <= 0:
                        skipped_counts["empty_window"] += 1
                        y += step
                        continue

                    if args.output_gsd_m > 0:
                        output_width = max(1, int(round(tile_size / args.output_gsd_m)))
                        output_height = max(1, int(round(tile_size / args.output_gsd_m)))
                        resampling = Resampling.average
                    else:
                        output_width = native_width
                        output_height = native_height
                        resampling = Resampling.nearest

                    data = ortho_ds.read(
                        indexes=[1, 2, 3],
                        window=window,
                        boundless=False,
                        out_shape=(3, output_height, output_width),
                        resampling=resampling,
                    )
                    center_x = min_x + tile_size / 2.0
                    center_y = min_y + tile_size / 2.0
                    tile_id = tile_id_for(center_x, center_y, tile_size)
                    out_path = out_dir / f"{tile_id}.png"
                    profile = {
                        "driver": "PNG",
                        "width": data.shape[2],
                        "height": data.shape[1],
                        "count": 3,
                        "dtype": data.dtype,
                    }
                    with rasterio.open(out_path, "w", **profile) as dst:
                        dst.write(data[:3])

                    affine = rasterio.Affine(
                        (max_x - min_x) / data.shape[2],
                        0.0,
                        min_x,
                        0.0,
                        -(max_y - min_y) / data.shape[1],
                        max_y,
                    )
                    rows.append(
                        {
                            "tile_id": tile_id,
                            "scale_level_m": int(round(tile_size)),
                            "tile_size_m": f"{tile_size:.3f}",
                            "image_path": as_manifest_path(out_path),
                            "source_tif": as_manifest_path(ortho_mosaic),
                            "pixel_col_off": int(window.col_off),
                            "pixel_row_off": int(window.row_off),
                            "pixel_width": int(data.shape[2]),
                            "pixel_height": int(data.shape[1]),
                            "native_width": native_width,
                            "native_height": native_height,
                            "output_gsd_m": "" if args.output_gsd_m <= 0 else f"{args.output_gsd_m:.12f}",
                            "gsd_x_m_per_px": f"{((max_x - min_x) / data.shape[2]):.12f}",
                            "gsd_y_m_per_px": f"{((max_y - min_y) / data.shape[1]):.12f}",
                            "center_x": f"{center_x:.12f}",
                            "center_y": f"{center_y:.12f}",
                            "min_x": f"{min_x:.12f}",
                            "min_y": f"{min_y:.12f}",
                            "max_x": f"{max_x:.12f}",
                            "max_y": f"{max_y:.12f}",
                            "affine": encode_affine(affine),
                        }
                    )
                    y += step
                x += step

        if not rows:
            raise SystemExit("no CaiWangCun candidate tiles were produced")

        fieldnames = list(rows[0].keys())
        with metadata_csv.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        write_json(
            roi_summary_json,
            {
                "source_ortho_mosaic": as_manifest_path(ortho_mosaic),
                "source_dsm_mosaic": as_manifest_path(dsm_mosaic),
                "target_crs": str(ortho_ds.crs),
                "query_count": len(query_rows),
                "roi_bounds": roi_bounds,
                "coverage_bounds": coverage_bounds,
                "build_bounds": build_bounds,
                "tile_sizes_m": args.tile_sizes,
                "overlap": args.overlap,
                "output_gsd_m": None if args.output_gsd_m <= 0 else args.output_gsd_m,
                "image_resolution_mode": "native" if args.output_gsd_m <= 0 else "fixed_output_gsd",
                "roi_buffer_meters": args.roi_buffer_meters,
                "dsm_expand_margin_m": args.dsm_expand_margin_m,
                "tile_count": len(rows),
                "skipped_counts": skipped_counts,
            },
        )

    print(metadata_csv)
    print(f"tile_count={len(rows)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Materialize per-candidate formal DSM rasters from the locked SRTM source.

Purpose:
- convert the active raw SRTM HGT tile into per-candidate DSM GeoTIFF rasters
  for `new2output/pose_v1_formal`;
- crop by the locked request bbox recorded in the formal DSM manifest and emit
  candidate-routed rasters for downstream DOM+DSM+PnP stages.

Main inputs:
- `new2output/N30E114.hgt`;
- `new2output/pose_v1_formal/input/formal_dsm_manifest.csv`.

Main outputs:
- per-candidate GeoTIFF rasters under `dsm_cache/rasters/`;
- `dsm_cache/rasters/_summary.json`;
- refreshed `formal_dsm_manifest.csv` and
  `dsm_cache/requests/srtm_download_requests.csv` statuses.

Applicable task constraints:
- runtime DSM preparation is candidate-oriented, not truth-oriented;
- crop bounds are taken directly from the formal DSM manifest request fields;
- no external resolution normalization is introduced beyond source-to-target
  reprojection.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"
DEFAULT_SOURCE_HGT = PROJECT_ROOT / "new2output" / "N30E114.hgt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--source-hgt", default=str(DEFAULT_SOURCE_HGT))
    parser.add_argument("--formal-dsm-manifest-csv", default=None)
    parser.add_argument("--requests-csv", default=None)
    parser.add_argument("--out-root", default=None)
    parser.add_argument("--target-crs", default="EPSG:32650")
    parser.add_argument("--resampling", choices=("nearest", "bilinear"), default="bilinear")
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


def choose_resampling(name: str):
    from rasterio.enums import Resampling

    return Resampling.bilinear if name == "bilinear" else Resampling.nearest


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    manifest_path = (
        Path(args.formal_dsm_manifest_csv)
        if args.formal_dsm_manifest_csv
        else bundle_root / "input" / "formal_dsm_manifest.csv"
    )
    requests_path = (
        Path(args.requests_csv)
        if args.requests_csv
        else bundle_root / "dsm_cache" / "requests" / "srtm_download_requests.csv"
    )
    out_root = Path(args.out_root) if args.out_root else bundle_root / "dsm_cache" / "rasters"
    source_hgt = Path(args.source_hgt)
    ensure_dir(out_root)

    if not source_hgt.exists():
        raise SystemExit(f"source HGT not found: {source_hgt}")

    dsm_rows = load_csv(manifest_path)
    if not dsm_rows:
        raise SystemExit(f"formal DSM manifest is empty: {manifest_path}")
    request_rows = load_csv(requests_path) if requests_path.exists() else []
    request_index = {row["download_request_id"]: row for row in request_rows if row.get("download_request_id")}

    try:
        import rasterio
        from rasterio.vrt import WarpedVRT
        from rasterio.windows import from_bounds
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("rasterio is required to materialize formal DSM rasters") from exc

    resampling_method = choose_resampling(args.resampling)
    status_counts: dict[str, int] = {}
    built_examples: list[dict[str, object]] = []
    source_bounds = {}

    with rasterio.open(source_hgt) as src:
        source_bounds = {
            "left": float(src.bounds.left),
            "bottom": float(src.bounds.bottom),
            "right": float(src.bounds.right),
            "top": float(src.bounds.top),
        }
        with WarpedVRT(src, crs=args.target_crs, resampling=resampling_method) as vrt:
            for row in dsm_rows:
                min_x = float(row["request_min_x"])
                min_y = float(row["request_min_y"])
                max_x = float(row["request_max_x"])
                max_y = float(row["request_max_y"])
                raster_path = resolve_runtime_path(str(row["raster_path"]))
                ensure_dir(raster_path.parent)
                try:
                    window = from_bounds(min_x, min_y, max_x, max_y, vrt.transform)
                    window = window.round_offsets().round_lengths()
                    width = max(1, int(window.width))
                    height = max(1, int(window.height))
                    data = vrt.read(1, window=window, out_shape=(height, width))
                    profile = {
                        "driver": "GTiff",
                        "width": width,
                        "height": height,
                        "count": 1,
                        "dtype": str(data.dtype),
                        "crs": args.target_crs,
                        "transform": vrt.window_transform(window),
                        "nodata": vrt.nodata,
                    }
                    with rasterio.open(raster_path, "w", **profile) as dst:
                        dst.write(data, 1)
                    row["status"] = "ready"
                    row["crs"] = args.target_crs
                    if len(built_examples) < 10:
                        built_examples.append(
                            {
                                "dsm_id": row["dsm_id"],
                                "raster_path": str(raster_path).replace("\\", "/"),
                                "width": width,
                                "height": height,
                            }
                        )
                except Exception as exc:  # pragma: no cover
                    message = str(exc).replace(",", ";").replace("\n", " ").strip()
                    if len(message) > 160:
                        message = message[:160]
                    row["status"] = f"failed:{type(exc).__name__}:{message}"

                request_id = row.get("download_request_id", "")
                if request_id in request_index:
                    request_index[request_id]["status"] = row["status"]
                status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

    write_csv(manifest_path, dsm_rows)
    if request_rows:
        write_csv(requests_path, request_rows)

    summary = {
        "bundle_root": str(bundle_root),
        "source_hgt": str(source_hgt.resolve()),
        "formal_dsm_manifest_csv": str(manifest_path.resolve()),
        "planned_count": len(dsm_rows),
        "built_count": sum(1 for row in dsm_rows if row.get("status") == "ready"),
        "missing_count": sum(1 for row in dsm_rows if row.get("status") == "missing"),
        "failed_count": sum(1 for row in dsm_rows if str(row.get("status", "")).startswith("failed:")),
        "crs": args.target_crs,
        "resampling": args.resampling,
        "source_bounds": source_bounds,
        "status_counts": status_counts,
        "built_examples": built_examples,
        "generated_at_unix": time.time(),
    }
    write_json(out_root / "_summary.json", summary)
    print(out_root / "_summary.json")


if __name__ == "__main__":
    main()

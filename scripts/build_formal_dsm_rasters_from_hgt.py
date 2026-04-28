#!/usr/bin/env python3
"""Build per-candidate formal DSM rasters from a raw SRTM HGT source.

Purpose:
- convert the locked raw SRTM source tile into per-candidate GeoTIFF rasters
  for the active formal pose-v1 run;
- keep DSM preparation aligned to the formal candidate bbox requests without
  introducing any external resolution normalization.

Main inputs:
- `new2output/N30E114.hgt`
- `new2output/pose_v1_formal/input/formal_dsm_manifest.csv`

Main outputs:
- `new2output/pose_v1_formal/dsm_cache/rasters/*.tif`
- `new2output/pose_v1_formal/dsm_cache/rasters/_summary.json`
- refreshed DSM/request manifest status values for built rasters

Applicable task constraints:
- each output raster is tied to one formal `dsm_id == candidate_id`;
- crop bounds are locked to `request_min_x/request_min_y/request_max_x/request_max_y`;
- the target CRS is the formal DOM projection CRS and is not inferred from truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"
DEFAULT_SOURCE_HGT = PROJECT_ROOT / "new2output" / "N30E114.hgt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--source-hgt", default=str(DEFAULT_SOURCE_HGT))
    parser.add_argument("--formal-dsm-manifest-csv", default=None)
    parser.add_argument("--out-root", default=None)
    parser.add_argument("--target-crs", default="EPSG:32650")
    parser.add_argument("--overwrite", action="store_true")
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


def estimate_target_resolution(dataset, target_crs: str) -> tuple[float, float]:
    from rasterio.warp import transform

    center_row = dataset.height // 2
    center_col = dataset.width // 2
    x0, y0 = dataset.xy(center_row, center_col)
    x1, y1 = dataset.xy(center_row, min(center_col + 1, dataset.width - 1))
    x2, y2 = dataset.xy(min(center_row + 1, dataset.height - 1), center_col)

    tx, ty = transform(dataset.crs, target_crs, [x0, x1, x2], [y0, y1, y2])
    res_x = abs(float(tx[1]) - float(tx[0]))
    res_y = abs(float(ty[2]) - float(ty[0]))
    if not math.isfinite(res_x) or res_x <= 0.0:
        raise SystemExit("failed to estimate projected x resolution from source HGT")
    if not math.isfinite(res_y) or res_y <= 0.0:
        raise SystemExit("failed to estimate projected y resolution from source HGT")
    return res_x, res_y


def refresh_status_files(
    dsm_manifest_csv: Path,
    dsm_manifest_json: Path,
    request_csv: Path,
) -> tuple[int, int]:
    dsm_rows = load_csv(dsm_manifest_csv)
    ready_count = 0
    missing_count = 0
    for row in dsm_rows:
        raster_path = Path(str(row["raster_path"]))
        if raster_path.exists():
            row["status"] = "ready"
            ready_count += 1
        else:
            row["status"] = "missing"
            missing_count += 1
    write_csv(dsm_manifest_csv, dsm_rows)

    if dsm_manifest_json.exists():
        payload = json.loads(dsm_manifest_json.read_text(encoding="utf-8"))
        payload["dsm_rows"] = dsm_rows
        payload["built_count"] = ready_count
        payload["missing_count"] = missing_count
        payload["generated_at_unix"] = time.time()
        write_json(dsm_manifest_json, payload)

    request_rows = load_csv(request_csv)
    for row in request_rows:
        raster_path = Path(str(row["raster_path"]))
        row["status"] = "ready" if raster_path.exists() else "missing"
    write_csv(request_csv, request_rows)
    return ready_count, missing_count


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    source_hgt = Path(args.source_hgt)
    dsm_manifest_csv = (
        Path(args.formal_dsm_manifest_csv)
        if args.formal_dsm_manifest_csv
        else bundle_root / "input" / "formal_dsm_manifest.csv"
    )
    dsm_manifest_json = bundle_root / "input" / "formal_dsm_manifest.json"
    request_csv = bundle_root / "dsm_cache" / "requests" / "srtm_download_requests.csv"
    out_root = Path(args.out_root) if args.out_root else bundle_root / "dsm_cache" / "rasters"
    logs_dir = bundle_root / "logs"
    ensure_dir(out_root)
    ensure_dir(logs_dir)

    if not source_hgt.exists():
        raise SystemExit(f"source HGT does not exist: {source_hgt}")
    rows = load_csv(dsm_manifest_csv)
    if not rows:
        raise SystemExit(f"formal DSM manifest is empty: {dsm_manifest_csv}")

    try:
        import rasterio
        from rasterio.transform import from_origin
        from rasterio.warp import reproject
        from rasterio.enums import Resampling
    except ImportError as exc:  # pragma: no cover - dependency blocker
        raise SystemExit("rasterio is required to build formal DSM rasters") from exc

    with rasterio.open(source_hgt) as source_ds:
        res_x, res_y = estimate_target_resolution(source_ds, args.target_crs)
        built_count = 0
        skipped_count = 0
        failed_rows: list[dict[str, object]] = []

        for row in rows:
            raster_path = Path(str(row["raster_path"]))
            ensure_dir(raster_path.parent)
            if raster_path.exists() and not args.overwrite:
                skipped_count += 1
                continue

            min_x = float(row["request_min_x"])
            min_y = float(row["request_min_y"])
            max_x = float(row["request_max_x"])
            max_y = float(row["request_max_y"])
            width = max(1, int(math.ceil((max_x - min_x) / res_x)))
            height = max(1, int(math.ceil((max_y - min_y) / res_y)))
            dst_transform = from_origin(min_x, max_y, res_x, res_y)
            destination = np.full((height, width), np.nan, dtype=np.float32)

            try:
                reproject(
                    source=rasterio.band(source_ds, 1),
                    destination=destination,
                    src_transform=source_ds.transform,
                    src_crs=source_ds.crs,
                    src_nodata=source_ds.nodata,
                    dst_transform=dst_transform,
                    dst_crs=args.target_crs,
                    dst_nodata=np.nan,
                    resampling=Resampling.bilinear,
                )
                profile = {
                    "driver": "GTiff",
                    "dtype": "float32",
                    "count": 1,
                    "height": height,
                    "width": width,
                    "crs": args.target_crs,
                    "transform": dst_transform,
                    "nodata": np.nan,
                    "compress": "deflate",
                }
                with rasterio.open(raster_path, "w", **profile) as dst:
                    dst.write(destination, 1)
                built_count += 1
            except Exception as exc:  # pragma: no cover - execution dependent
                failed_rows.append(
                    {
                        "dsm_id": row["dsm_id"],
                        "raster_path": str(raster_path),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    ready_count, missing_count = refresh_status_files(dsm_manifest_csv, dsm_manifest_json, request_csv)
    summary = {
        "bundle_root": str(bundle_root),
        "source_hgt": str(source_hgt.resolve()),
        "formal_dsm_manifest_csv": str(dsm_manifest_csv.resolve()),
        "planned_count": len(rows),
        "built_count": built_count,
        "skipped_existing_count": skipped_count,
        "ready_count": ready_count,
        "missing_count": missing_count,
        "failed_count": len(failed_rows),
        "crs": args.target_crs,
        "resolution_x_m": res_x,
        "resolution_y_m": res_y,
        "failed_rows": failed_rows,
        "generated_at_unix": time.time(),
    }
    write_json(out_root / "_summary.json", summary)
    (logs_dir / "build_formal_dsm_rasters_from_hgt.log").write_text(
        "\n".join(
            [
                "stage=build_formal_dsm_rasters_from_hgt",
                f"source_hgt={source_hgt}",
                f"planned_count={len(rows)}",
                f"built_count={built_count}",
                f"skipped_existing_count={skipped_count}",
                f"ready_count={ready_count}",
                f"missing_count={missing_count}",
                f"failed_count={len(failed_rows)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(out_root / "_summary.json")


if __name__ == "__main__":
    main()

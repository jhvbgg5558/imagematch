#!/usr/bin/env python3
"""Run the CaiWangCun DOM/DSM constrained gate experiment.

Purpose:
- reuse the locked 009/010 query, retrieval, and RoMa v2 rerank assets while
  replacing only the orthophoto truth and candidate DSM sources with the
  finished CaiWangCun 0.14 m DOM/DSM rasters;
- enforce a coverage-constrained gate so no candidate falls back to ODM LAZ or
  SRTM when the CaiWangCun DSM does not fully cover the requested DSM region.

Main inputs:
- `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10`;
- CaiWangCun 4x4 DOM/DSM GeoTIFF tiles under the supplied source directory.

Main outputs:
- `plan/caiwangcun_asset_manifest.csv`;
- `source_mosaic/caiwangcun_ortho_0p14m_epsg32650.tif`;
- `source_mosaic/caiwangcun_dsm_0p14m_epsg32650.tif`;
- coverage audits under `plan/`;
- a gate run under `pose_v1_formal/` using only fully covered candidates.

Applicable task constraints:
- runtime retrieval and rerank scores are reused unchanged;
- query intrinsics are reused from the existing per-flight cameras metadata;
- the query image has no runtime geolocation metadata;
- no ODM LAZ, SRTM, satellite-truth suite, or report-generation fallback is
  allowed in this branch.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REUSE_ROOT = PROJECT_ROOT / "new2output" / "nadir_009010_dinov2_romav2_pose_2026-04-10"
DEFAULT_EXPERIMENT_ROOT = (
    PROJECT_ROOT
    / "new3output"
    / "nadir_009010_dinov2_romav2_pose_caiwangcun_candidate_domdsm_0p14m_gate_2026-04-20"
)
DEFAULT_CAIWANGCUN_ROOT = (
    Path("/mnt/d") / "\u6570\u636e" / "\u6b66\u6c49\u5f71\u50cf" / "CaiWangCun-DOM"
    if os.name != "nt"
    else Path("D:/") / "\u6570\u636e" / "\u6b66\u6c49\u5f71\u50cf" / "CaiWangCun-DOM"
)

REUSED_DIRS = (
    "selected_queries",
    "query_inputs",
    "query_truth",
    "query_features",
    "retrieval",
    "romav2_rerank",
)

SCRIPT_SNAPSHOT_NAMES = (
    "run_nadir_009010_caiwangcun_domdsm_gate_experiment.py",
    "build_pose_manifest.py",
    "run_formal_pose_v1_pipeline.py",
    "run_pose_validation_suite.py",
    "build_query_ortho_truth_manifest.py",
    "crop_query_ortho_truth_tiles.py",
    "render_query_predicted_ortho_from_pose.py",
    "evaluate_pose_ortho_alignment.py",
    "evaluate_pose_ortho_tiepoint_ground_error.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-root", default=str(DEFAULT_EXPERIMENT_ROOT))
    parser.add_argument("--reuse-retrieval-root", default=str(DEFAULT_REUSE_ROOT))
    parser.add_argument("--caiwangcun-root", default=str(DEFAULT_CAIWANGCUN_ROOT))
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--target-resolution-m", type=float, default=0.14)
    parser.add_argument("--sample-query-count", type=int, default=5)
    parser.add_argument("--pose-sample-count", type=int, default=5000)
    parser.add_argument("--crop-margin-m", type=float, default=80.0)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--target-crs", default="EPSG:32650")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def resolve_runtime_path(raw_path: str | Path) -> Path:
    text = str(raw_path)
    if os.name == "nt" and text.startswith("/mnt/") and len(text) > 6:
        drive_letter = text[5]
        remainder = text[7:].replace("/", "\\")
        return Path(f"{drive_letter.upper()}:\\{remainder}")
    if os.name != "nt" and len(text) >= 3 and text[1:3] in (":\\", ":/"):
        drive_letter = text[0].lower()
        remainder = text[3:].replace("\\", "/")
        return Path(f"/mnt/{drive_letter}/{remainder}")
    return Path(text)


def as_manifest_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    ensure_dir(path.parent)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        if not fieldnames:
            handle.write("")
            return
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_cmd(command: list[str], log_path: Path, dry_run: bool) -> None:
    ensure_dir(log_path.parent)
    rendered = " ".join(command)
    print("+", rendered, flush=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_now()}] + {rendered}\n")
    if dry_run:
        return
    with log_path.open("a", encoding="utf-8") as handle:
        subprocess.run(command, cwd=PROJECT_ROOT, stdout=handle, stderr=subprocess.STDOUT, text=True, check=True)


def source_crs():
    from rasterio.crs import CRS

    return CRS.from_epsg(4547)


def sync_reused_assets(reuse_root: Path, experiment_root: Path, overwrite: bool) -> None:
    for dirname in REUSED_DIRS:
        src = reuse_root / dirname
        dst = experiment_root / dirname
        if not src.exists():
            raise SystemExit(f"missing reused asset directory: {src}")
        if dst.exists() and overwrite:
            shutil.rmtree(dst)
        if not dst.exists():
            shutil.copytree(src, dst)


def copy_script_snapshots(experiment_root: Path) -> None:
    snapshot_root = experiment_root / "scripts"
    ensure_dir(snapshot_root)
    rows: list[dict[str, object]] = []
    for name in SCRIPT_SNAPSHOT_NAMES:
        src = PROJECT_ROOT / "scripts" / name
        if not src.exists():
            continue
        dst = snapshot_root / name
        shutil.copy2(src, dst)
        rows.append(
            {
                "file": name,
                "source_path": as_manifest_path(src),
                "snapshot_path": as_manifest_path(dst),
                "sha256": sha256_file(src),
                "copied_at_utc": utc_now(),
            }
        )
    write_json(snapshot_root / "script_manifest.json", {"scripts": rows})


def find_source_tiles(caiwangcun_root: Path, kind: str) -> list[Path]:
    pattern = "CaiWangCun-DOM_ortho_part_*_*.tif" if kind == "ortho" else "CaiWangCun-DOM_DSM_part_*_*.tif"
    tiles = sorted(caiwangcun_root.glob(pattern))
    if not tiles:
        raise SystemExit(f"no CaiWangCun {kind} tiles found under {caiwangcun_root}")
    return tiles


def summarize_source_tiles(paths: Iterable[Path]) -> list[dict[str, object]]:
    import rasterio

    rows = []
    for path in paths:
        with rasterio.open(path) as ds:
            rows.append(
                {
                    "source_path": as_manifest_path(path),
                    "width": ds.width,
                    "height": ds.height,
                    "count": ds.count,
                    "dtype": ",".join(ds.dtypes),
                    "crs": str(ds.crs or source_crs()),
                    "bounds_left": float(ds.bounds.left),
                    "bounds_bottom": float(ds.bounds.bottom),
                    "bounds_right": float(ds.bounds.right),
                    "bounds_top": float(ds.bounds.top),
                    "resolution_x": float(abs(ds.transform.a)),
                    "resolution_y": float(abs(ds.transform.e)),
                    "nodata": ds.nodata,
                }
            )
    return rows


def mosaic_to_target(
    source_paths: list[Path],
    out_path: Path,
    target_crs: str,
    kind: str,
    overwrite: bool,
) -> dict[str, object]:
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.merge import merge
    from rasterio.vrt import WarpedVRT

    ensure_dir(out_path.parent)
    if out_path.exists() and not overwrite:
        with rasterio.open(out_path) as ds:
            return raster_summary(ds, out_path, kind, reused_existing=True)

    datasets = []
    vrts = []
    try:
        for path in source_paths:
            src = rasterio.open(path)
            datasets.append(src)
            vrts.append(
                WarpedVRT(
                    src,
                    src_crs=src.crs or source_crs(),
                    crs=target_crs,
                    resampling=Resampling.bilinear if kind == "dsm" else Resampling.nearest,
                )
            )
        data, transform = merge(vrts)
        first = vrts[0]
        profile = first.profile.copy()
        profile.update(
            driver="GTiff",
            height=data.shape[1],
            width=data.shape[2],
            count=data.shape[0],
            transform=transform,
            crs=target_crs,
            compress="lzw",
            tiled=True,
            bigtiff="if_safer",
        )
        if kind == "dsm":
            data = data[:1].astype("float32", copy=False)
            profile.update(count=1, dtype="float32", nodata=first.nodata)
        else:
            data = data[:3]
            profile.update(count=data.shape[0], dtype=str(data.dtype), photometric="rgb")
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(data)
    finally:
        for vrt in vrts:
            vrt.close()
        for src in datasets:
            src.close()

    with rasterio.open(out_path) as ds:
        return raster_summary(ds, out_path, kind, reused_existing=False)


def raster_summary(ds, path: Path, kind: str, reused_existing: bool) -> dict[str, object]:
    return {
        "path": as_manifest_path(path),
        "kind": kind,
        "crs": str(ds.crs),
        "bounds": {
            "left": float(ds.bounds.left),
            "bottom": float(ds.bounds.bottom),
            "right": float(ds.bounds.right),
            "top": float(ds.bounds.top),
        },
        "width": int(ds.width),
        "height": int(ds.height),
        "count": int(ds.count),
        "dtype": ",".join(ds.dtypes),
        "resolution": [float(abs(ds.transform.a)), float(abs(ds.transform.e))],
        "nodata": ds.nodata,
        "reused_existing": reused_existing,
    }


def classify_coverage(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    bounds: dict[str, float],
) -> tuple[str, float]:
    inter_min_x = max(min_x, bounds["left"])
    inter_min_y = max(min_y, bounds["bottom"])
    inter_max_x = min(max_x, bounds["right"])
    inter_max_y = min(max_y, bounds["top"])
    area = max(0.0, max_x - min_x) * max(0.0, max_y - min_y)
    inter_area = max(0.0, inter_max_x - inter_min_x) * max(0.0, inter_max_y - inter_min_y)
    ratio = inter_area / area if area > 0.0 else 0.0
    if ratio >= 0.999999:
        return "fully_covered", ratio
    if ratio > 0.0:
        return "partially_covered", ratio
    return "outside_caiwangcun", ratio


def choose_sample_queries(queries: list[dict[str, str]], limit: int) -> list[str]:
    selected: list[str] = []
    seen_flights: set[str] = set()
    for row in queries:
        query_id = row["query_id"]
        flight_id = row.get("flight_id", "")
        if flight_id and flight_id not in seen_flights:
            selected.append(query_id)
            seen_flights.add(flight_id)
        if len(selected) >= limit:
            return selected
    for row in queries:
        query_id = row["query_id"]
        if query_id not in selected:
            selected.append(query_id)
        if len(selected) >= limit:
            break
    return selected


def crop_candidate_dom_rasters(
    candidate_rows: list[dict[str, str]],
    ortho_mosaic_path: Path,
    out_root: Path,
    target_crs: str,
) -> dict[str, object]:
    import rasterio
    from rasterio.windows import from_bounds

    ensure_dir(out_root)
    built = 0
    failed = 0
    examples = []
    status_counts: Counter[str] = Counter()

    with rasterio.open(ortho_mosaic_path) as src:
        for row in candidate_rows:
            out_path = out_root / f"{row['candidate_id']}.tif"
            try:
                window = from_bounds(
                    float(row["min_x"]),
                    float(row["min_y"]),
                    float(row["max_x"]),
                    float(row["max_y"]),
                    src.transform,
                ).round_offsets().round_lengths()
                data = src.read(window=window, boundless=False)
                transform = src.window_transform(window)
                profile = src.profile.copy()
                profile.update(
                    driver="GTiff",
                    height=data.shape[1],
                    width=data.shape[2],
                    count=min(3, data.shape[0]),
                    dtype=str(data.dtype),
                    transform=transform,
                    crs=target_crs,
                    compress="lzw",
                    tiled=True,
                    bigtiff="if_safer",
                    photometric="rgb",
                )
                data = data[:3]
                with rasterio.open(out_path, "w", **profile) as dst:
                    dst.write(data)
                row["image_path"] = as_manifest_path(out_path)
                row["source_tif"] = as_manifest_path(ortho_mosaic_path)
                row["crs"] = target_crs
                row["geo_x0"] = f"{transform.c:.12f}"
                row["geo_x_col"] = f"{transform.a:.12f}"
                row["geo_x_row"] = f"{transform.b:.12f}"
                row["geo_y0"] = f"{transform.f:.12f}"
                row["geo_y_col"] = f"{transform.d:.12f}"
                row["geo_y_row"] = f"{transform.e:.12f}"
                row["affine"] = json.dumps(
                    [transform.a, transform.b, transform.c, transform.d, transform.e, transform.f],
                    ensure_ascii=False,
                )
                built += 1
                status_counts["ready"] += 1
                if len(examples) < 10:
                    examples.append(
                        {
                            "candidate_id": row["candidate_id"],
                            "path": as_manifest_path(out_path),
                            "width": int(profile["width"]),
                            "height": int(profile["height"]),
                        }
                    )
            except Exception as exc:
                failed += 1
                row["dom_crop_status"] = f"failed:{type(exc).__name__}:{str(exc)[:120]}"
                status_counts["failed"] += 1

    return {
        "source_ortho": as_manifest_path(ortho_mosaic_path),
        "out_root": as_manifest_path(out_root),
        "planned_count": len(candidate_rows),
        "built_count": built,
        "failed_count": failed,
        "status_counts": dict(status_counts),
        "built_examples": examples,
        "generated_at_utc": utc_now(),
    }


def write_asset_manifest(path: Path, query_rows: list[dict[str, str]], ortho_path: Path, dsm_path: Path) -> None:
    rows = []
    for flight_id in sorted({row["flight_id"] for row in query_rows if row.get("flight_id")}):
        rows.append(
            {
                "flight_id": flight_id,
                "asset_version_tag": "caiwangcun_domdsm_0p14m_epsg32650",
                "odm_orthophoto_path": as_manifest_path(ortho_path),
                "dsm_path": as_manifest_path(dsm_path),
                "asset_source": "CaiWangCun finished DOM/DSM",
            }
        )
    write_csv(path, rows)


def create_coverage_constrained_inputs(
    experiment_root: Path,
    reuse_root: Path,
    dsm_bounds: dict[str, float],
    dsm_mosaic_path: Path,
    ortho_mosaic_path: Path,
    sample_query_count: int,
    target_crs: str,
) -> dict[str, object]:
    src_input = reuse_root / "pose_v1_formal" / "input"
    dst_input = experiment_root / "pose_v1_formal" / "input"
    ensure_dir(dst_input)

    query_rows = load_csv(src_input / "formal_query_manifest.csv")
    candidate_rows = load_csv(src_input / "formal_candidate_manifest.csv")
    dsm_rows = load_csv(src_input / "formal_dsm_manifest.csv")
    truth_rows = load_csv(src_input / "formal_truth_manifest.csv")
    sample_query_ids = set(choose_sample_queries(query_rows, sample_query_count))

    dsm_audit = []
    dsm_status_by_tile: dict[str, str] = {}
    fully_covered_dsm_rows = []
    for row in dsm_rows:
        status, ratio = classify_coverage(
            float(row["request_min_x"]),
            float(row["request_min_y"]),
            float(row["request_max_x"]),
            float(row["request_max_y"]),
            dsm_bounds,
        )
        dsm_status_by_tile[row["candidate_tile_id"]] = status
        audit_row = dict(row)
        audit_row.update(
            {
                "coverage_status": status,
                "coverage_ratio": f"{ratio:.9f}",
                "exclusion_reason": "" if status == "fully_covered" else f"{status}; no ODM/SRTM fallback",
            }
        )
        dsm_audit.append(audit_row)
        if status == "fully_covered":
            new_row = dict(row)
            new_row["dsm_source_name"] = "caiwangcun_dsm_0p14m_epsg32650"
            new_row["raster_path"] = as_manifest_path(
                experiment_root / "pose_v1_formal" / "dsm_cache" / "rasters" / f"{row['dsm_id']}.tif"
            )
            new_row["status"] = "pending_caiwangcun_crop"
            fully_covered_dsm_rows.append(new_row)

    candidate_audit = []
    filtered_candidates = []
    filtered_topk_rows = []
    for row in candidate_rows:
        status = dsm_status_by_tile.get(row["candidate_tile_id"], "outside_caiwangcun")
        tile_status, tile_ratio = classify_coverage(
            float(row["min_x"]),
            float(row["min_y"]),
            float(row["max_x"]),
            float(row["max_y"]),
            dsm_bounds,
        )
        audit_row = dict(row)
        audit_row.update(
            {
                "candidate_tile_coverage_status": tile_status,
                "candidate_tile_coverage_ratio": f"{tile_ratio:.9f}",
                "dsm_request_coverage_status": status,
                "allowed_in_gate": str(status == "fully_covered").lower(),
                "exclusion_reason": "" if status == "fully_covered" else f"{status}; no ODM/SRTM fallback",
            }
        )
        candidate_audit.append(audit_row)
        if status == "fully_covered" and row["query_id"] in sample_query_ids:
            filtered_candidates.append(dict(row))
            filtered_topk_rows.append(
                {
                    "query_id": row["query_id"],
                    "candidate_id": row["candidate_id"],
                    "rank": row["candidate_rank"],
                    "score": row["candidate_score"],
                }
            )

    dom_crop_summary = crop_candidate_dom_rasters(
        filtered_candidates,
        ortho_mosaic_path,
        experiment_root / "pose_v1_formal" / "dom_cache" / "rasters",
        target_crs,
    )
    write_json(experiment_root / "pose_v1_formal" / "dom_cache" / "rasters" / "_summary.json", dom_crop_summary)

    write_csv(dst_input / "formal_query_manifest.csv", query_rows)
    write_json(dst_input / "formal_query_manifest.json", {"rows": query_rows})
    write_csv(dst_input / "formal_candidate_manifest.csv", filtered_candidates)
    write_json(dst_input / "formal_candidate_manifest.json", {"rows": filtered_candidates})
    write_csv(dst_input / "formal_dsm_manifest.csv", fully_covered_dsm_rows)
    write_json(dst_input / "formal_dsm_manifest.json", {"rows": fully_covered_dsm_rows})
    for row in truth_rows:
        row["source_tif"] = as_manifest_path(experiment_root / "source_mosaic" / "caiwangcun_ortho_0p14m_epsg32650.tif")
        row["query_crs"] = "EPSG:32650"
    write_csv(dst_input / "formal_truth_manifest.csv", truth_rows)
    write_json(dst_input / "formal_truth_manifest.json", {"rows": truth_rows})

    plan_root = experiment_root / "plan"
    write_csv(plan_root / "caiwangcun_candidate_coverage_audit.csv", candidate_audit)
    write_csv(plan_root / "caiwangcun_dsm_request_coverage_audit.csv", dsm_audit)
    filtered_topk_csv = plan_root / "caiwangcun_filtered_retrieval_top20.csv"
    write_csv(filtered_topk_csv, filtered_topk_rows)

    cache_source = experiment_root / "pose_v1_formal" / "dsm_cache" / "source"
    ensure_dir(cache_source)
    shutil.copy2(dsm_mosaic_path, cache_source / "caiwangcun_dsm_0p14m_epsg32650.tif")

    return {
        "query_rows": query_rows,
        "filtered_topk_csv": filtered_topk_csv,
        "dsm_manifest_csv": dst_input / "formal_dsm_manifest.csv",
        "sample_query_ids": sorted(sample_query_ids),
        "candidate_count_before": len(candidate_rows),
        "candidate_count_after": len(filtered_candidates),
        "dsm_count_before": len(dsm_rows),
        "dsm_count_after": len(fully_covered_dsm_rows),
        "candidate_status_counts": dict(Counter(row["dsm_request_coverage_status"] for row in candidate_audit)),
        "dsm_status_counts": dict(Counter(row["coverage_status"] for row in dsm_audit)),
        "dom_crop_summary": dom_crop_summary,
    }


def materialize_dsm_from_mosaic(bundle_root: Path, dsm_manifest_csv: Path, source_dsm: Path, target_crs: str) -> None:
    import rasterio
    from rasterio.windows import from_bounds

    rows = load_csv(dsm_manifest_csv)
    out_root = bundle_root / "dsm_cache" / "rasters"
    ensure_dir(out_root)
    built_examples = []
    status_counts: Counter[str] = Counter()
    with rasterio.open(source_dsm) as src:
        for row in rows:
            out_path = resolve_runtime_path(row["raster_path"])
            ensure_dir(out_path.parent)
            try:
                window = from_bounds(
                    float(row["request_min_x"]),
                    float(row["request_min_y"]),
                    float(row["request_max_x"]),
                    float(row["request_max_y"]),
                    src.transform,
                ).round_offsets().round_lengths()
                data = src.read(1, window=window, boundless=False).astype("float32", copy=False)
                profile = src.profile.copy()
                profile.update(
                    driver="GTiff",
                    height=data.shape[0],
                    width=data.shape[1],
                    count=1,
                    dtype="float32",
                    transform=src.window_transform(window),
                    crs=target_crs,
                    compress="lzw",
                    tiled=True,
                    bigtiff="if_safer",
                )
                with rasterio.open(out_path, "w", **profile) as dst:
                    dst.write(data, 1)
                row["status"] = "ready"
                status_counts["ready"] += 1
                if len(built_examples) < 10:
                    built_examples.append({"dsm_id": row["dsm_id"], "raster_path": as_manifest_path(out_path)})
            except Exception as exc:
                row["status"] = f"failed:{type(exc).__name__}:{str(exc)[:140]}"
                status_counts[row["status"]] += 1
    write_csv(dsm_manifest_csv, rows)
    write_json(
        out_root / "_summary.json",
        {
            "source_dsm": as_manifest_path(source_dsm),
            "formal_dsm_manifest_csv": as_manifest_path(dsm_manifest_csv),
            "planned_count": len(rows),
            "built_count": sum(1 for row in rows if row.get("status") == "ready"),
            "failed_count": sum(1 for row in rows if str(row.get("status", "")).startswith("failed:")),
            "status_counts": dict(status_counts),
            "built_examples": built_examples,
            "generated_at_utc": utc_now(),
        },
    )


def audit_query_centers(query_seed_csv: Path, query_ids: set[str], bounds: dict[str, float]) -> dict[str, object]:
    rows = load_csv(query_seed_csv)
    audited = []
    for row in rows:
        if row["query_id"] not in query_ids:
            continue
        x = float(row["query_x"])
        y = float(row["query_y"])
        covered = bounds["left"] <= x <= bounds["right"] and bounds["bottom"] <= y <= bounds["top"]
        audited.append(
            {"query_id": row["query_id"], "flight_id": row["flight_id"], "query_x": x, "query_y": y, "covered": covered}
        )
    return {
        "query_center_count": len(audited),
        "query_centers_covered_count": sum(1 for row in audited if row["covered"]),
        "query_centers": audited,
    }


def query_seed_rows_for_manifest(query_seed_csv: Path, query_ids: set[str]) -> list[dict[str, str]]:
    return [row for row in load_csv(query_seed_csv) if row["query_id"] in query_ids]


def main() -> None:
    args = parse_args()
    experiment_root = resolve_runtime_path(args.experiment_root)
    reuse_root = resolve_runtime_path(args.reuse_retrieval_root)
    caiwangcun_root = resolve_runtime_path(args.caiwangcun_root)
    bundle_root = experiment_root / "pose_v1_formal"
    log_path = experiment_root / "logs" / "caiwangcun_gate_experiment.log"

    if experiment_root.exists() and args.overwrite:
        shutil.rmtree(experiment_root)
    ensure_dir(experiment_root / "plan")
    ensure_dir(experiment_root / "source_mosaic")
    ensure_dir(bundle_root)

    sync_reused_assets(reuse_root, experiment_root, overwrite=args.overwrite)
    copy_script_snapshots(experiment_root)

    ortho_tiles = find_source_tiles(caiwangcun_root, "ortho")
    dsm_tiles = find_source_tiles(caiwangcun_root, "dsm")
    ortho_mosaic = experiment_root / "source_mosaic" / "caiwangcun_ortho_0p14m_epsg32650.tif"
    dsm_mosaic = experiment_root / "source_mosaic" / "caiwangcun_dsm_0p14m_epsg32650.tif"

    write_csv(experiment_root / "plan" / "caiwangcun_source_tile_manifest.csv", summarize_source_tiles([*ortho_tiles, *dsm_tiles]))
    ortho_summary = mosaic_to_target(ortho_tiles, ortho_mosaic, args.target_crs, "ortho", args.overwrite)
    dsm_summary = mosaic_to_target(dsm_tiles, dsm_mosaic, args.target_crs, "dsm", args.overwrite)
    write_json(
        experiment_root / "source_mosaic" / "caiwangcun_mosaic_summary.json",
        {
            "ortho": ortho_summary,
            "dsm": dsm_summary,
            "target_crs": args.target_crs,
            "source_crs": "CGCS2000 / 3-degree Gauss-Kruger CM 114E (EPSG:4547)",
            "generated_at_utc": utc_now(),
        },
    )

    coverage_info = create_coverage_constrained_inputs(
        experiment_root,
        reuse_root,
        dsm_summary["bounds"],
        dsm_mosaic,
        ortho_mosaic,
        args.sample_query_count,
        args.target_crs,
    )
    query_seed_csv = PROJECT_ROOT / "new1output" / "query_reselect_2026-03-26_v2" / "query_truth" / "queries_truth_seed.csv"
    query_ids = {row["query_id"] for row in coverage_info["query_rows"]}
    query_center_audit = audit_query_centers(query_seed_csv, query_ids, dsm_summary["bounds"])
    asset_rows = [*coverage_info["query_rows"], *query_seed_rows_for_manifest(query_seed_csv, query_ids)]
    write_asset_manifest(experiment_root / "plan" / "caiwangcun_asset_manifest.csv", asset_rows, ortho_mosaic, dsm_mosaic)
    write_json(
        experiment_root / "plan" / "caiwangcun_coverage_summary.json",
        {
            **{key: value for key, value in coverage_info.items() if key not in {"query_rows", "filtered_topk_csv", "dsm_manifest_csv"}},
            **query_center_audit,
            "dsm_mosaic_bounds_epsg32650": dsm_summary["bounds"],
            "fallback_policy": "excluded candidates only; no ODM LAZ or SRTM fallback",
            "generated_at_utc": utc_now(),
        },
    )

    materialize_dsm_from_mosaic(bundle_root, coverage_info["dsm_manifest_csv"], dsm_mosaic, args.target_crs)

    run_cmd(
        [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "build_pose_manifest.py"),
            "--bundle-root",
            str(bundle_root),
            "--query-manifest-csv",
            str(bundle_root / "input" / "formal_query_manifest.csv"),
            "--dom-manifest-csv",
            str(bundle_root / "input" / "formal_candidate_manifest.csv"),
            "--dsm-manifest-csv",
            str(bundle_root / "input" / "formal_dsm_manifest.csv"),
            "--coarse-topk-csv",
            str(coverage_info["filtered_topk_csv"]),
        ],
        log_path,
        args.dry_run,
    )
    run_cmd(
        [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "run_formal_pose_v1_pipeline.py"),
            "--bundle-root",
            str(bundle_root),
            "--phase",
            "sample",
            "--sample-query-count",
            str(args.sample_query_count),
            "--sample-count",
            str(args.pose_sample_count),
            "--device",
            args.device,
            "--skip-dsm-build",
        ],
        log_path,
        args.dry_run,
    )
    run_cmd(
        [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "run_pose_validation_suite.py"),
            "--bundle-root",
            str(bundle_root),
            "--phase",
            "gate",
            "--gate-count",
            str(args.sample_query_count),
            "--target-resolution-m",
            str(args.target_resolution_m),
            "--crop-margin-m",
            str(args.crop_margin_m),
            "--block-size",
            str(args.block_size),
            "--flight-asset-manifest",
            str(experiment_root / "plan" / "caiwangcun_asset_manifest.csv"),
            "--output-root",
            str(bundle_root / "eval_pose_validation_suite_caiwangcun_truth"),
            "--overwrite",
            *sum((["--query-id", query_id] for query_id in coverage_info["sample_query_ids"]), []),
        ],
        log_path,
        args.dry_run,
    )

    write_json(
        experiment_root / "plan" / "run_gate_summary.json",
        {
            "experiment_root": as_manifest_path(experiment_root),
            "reuse_retrieval_root": as_manifest_path(reuse_root),
            "caiwangcun_root": as_manifest_path(caiwangcun_root),
            "ortho_mosaic": as_manifest_path(ortho_mosaic),
            "dsm_mosaic": as_manifest_path(dsm_mosaic),
            "bundle_root": as_manifest_path(bundle_root),
            "coverage_summary": as_manifest_path(experiment_root / "plan" / "caiwangcun_coverage_summary.json"),
            "pose_gate_summary": as_manifest_path(bundle_root / "summary" / "phase_gate_summary.json"),
            "validation_gate_summary": as_manifest_path(
                bundle_root / "eval_pose_validation_suite_caiwangcun_truth" / "phase_gate_summary.json"
            ),
            "generated_at_utc": utc_now(),
        },
    )


if __name__ == "__main__":
    main()

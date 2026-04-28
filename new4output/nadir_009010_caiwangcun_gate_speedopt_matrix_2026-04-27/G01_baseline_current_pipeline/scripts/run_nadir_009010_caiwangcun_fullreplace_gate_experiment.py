#!/usr/bin/env python3
"""Run the CaiWangCun DOM/DSM full-replacement 009/010 gate.

Purpose:
- replace the old fixed satellite candidate library with a CaiWangCun DOM
  candidate library while keeping the query set, DINOv2, RoMa v2, and Pose v1
  algorithms unchanged;
- rebuild every candidate-bound artifact, including candidate features, FAISS,
  retrieval, rerank, formal manifests, DSM cache, pose outputs, and validation;
- keep the run gate-only and report-free.

Main inputs:
- the completed 009/010 query assets under
  `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10`;
- CaiWangCun finished DOM/DSM GeoTIFF tiles under the supplied source root.

Main outputs:
- a fully isolated experiment under
  `new3output/nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20`;
- CaiWangCun candidate library, retrieval/rerank outputs, pose gate outputs,
  CaiWangCun DOM-truth validation, and frame-sanity diagnostics.

Applicable task constraints:
- query images have no runtime geolocation metadata and are not guaranteed to
  be orthophotos;
- query metadata is used only for controlled offline ROI/truth generation;
- no ODM LAZ, SRTM, satellite-truth suite, comparison report, or docx report is
  used in this branch.
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

from run_nadir_009010_caiwangcun_domdsm_gate_experiment import (
    find_source_tiles,
    mosaic_to_target,
    summarize_source_tiles,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REUSE_ROOT = PROJECT_ROOT / "new2output" / "nadir_009010_dinov2_romav2_pose_2026-04-10"
DEFAULT_EXPERIMENT_ROOT = (
    PROJECT_ROOT / "new3output" / "nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20"
)
DEFAULT_CAIWANGCUN_ROOT = (
    Path("/mnt/d") / "\u6570\u636e" / "\u6b66\u6c49\u5f71\u50cf" / "CaiWangCun-DOM"
    if os.name != "nt"
    else Path("D:/") / "\u6570\u636e" / "\u6b66\u6c49\u5f71\u50cf" / "CaiWangCun-DOM"
)

REUSED_DIRS = (
    "selected_queries",
    "query_inputs",
    "query_features",
)

SCRIPT_SNAPSHOT_NAMES = (
    "run_nadir_009010_caiwangcun_fullreplace_gate_experiment.py",
    "build_caiwangcun_candidate_library.py",
    "diagnose_pose_frame_sanity.py",
    "build_formal_query_manifest.py",
    "build_formal_candidate_manifest.py",
    "build_candidate_dsm_cache.py",
    "build_pose_manifest.py",
    "run_formal_pose_v1_pipeline.py",
    "run_pose_validation_suite.py",
    "render_query_predicted_ortho_from_pose.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-root", default=str(DEFAULT_EXPERIMENT_ROOT))
    parser.add_argument("--reuse-root", default=str(DEFAULT_REUSE_ROOT))
    parser.add_argument("--caiwangcun-root", default=str(DEFAULT_CAIWANGCUN_ROOT))
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--target-crs", default="EPSG:32650")
    parser.add_argument("--target-resolution-m", type=float, default=0.14)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--sample-query-count", type=int, default=5)
    parser.add_argument("--romav2-sample-count", type=int, default=5000)
    parser.add_argument("--pose-sample-count", type=int, default=5000)
    parser.add_argument("--crop-margin-m", type=float, default=80.0)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-mosaic", action="store_true")
    parser.add_argument("--skip-retrieval", action="store_true")
    parser.add_argument("--skip-pose", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument(
        "--rerank-query-id",
        action="append",
        default=[],
        help="Optional query IDs to pass to RoMa rerank. Used for true small gate reruns.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


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


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


def sync_reused_assets(reuse_root: Path, experiment_root: Path, overwrite: bool) -> None:
    for dirname in REUSED_DIRS:
        src = reuse_root / dirname
        dst = experiment_root / dirname
        if not src.exists():
            raise SystemExit(f"missing reusable asset directory: {src}")
        if dst.exists() and overwrite:
            shutil.rmtree(dst)
        if not dst.exists():
            shutil.copytree(src, dst)


def rewrite_path_prefix(value: str, old_root: Path, new_root: Path) -> str:
    normalized = value.replace("\\", "/")
    old_norm = as_manifest_path(old_root)
    new_norm = as_manifest_path(new_root)
    if normalized.startswith(old_norm):
        return new_norm + normalized[len(old_norm) :]
    return value


def rewrite_reused_manifests(reuse_root: Path, experiment_root: Path) -> None:
    selected_csv = experiment_root / "selected_queries" / "selected_images_summary.csv"
    if selected_csv.exists():
        rows = load_csv(selected_csv)
        for row in rows:
            if "copied_path" in row:
                row["copied_path"] = rewrite_path_prefix(row["copied_path"], reuse_root, experiment_root)
        write_csv(selected_csv, rows)

    query_manifest_csv = experiment_root / "query_inputs" / "query_manifest.csv"
    if query_manifest_csv.exists():
        rows = load_csv(query_manifest_csv)
        for row in rows:
            for key in ("original_query_path", "sanitized_query_path"):
                if key in row:
                    row[key] = rewrite_path_prefix(row[key], reuse_root, experiment_root)
        write_csv(query_manifest_csv, rows)


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


def write_asset_manifest(path: Path, query_seed_csv: Path, ortho_mosaic: Path, dsm_mosaic: Path) -> None:
    rows = []
    for flight_id in sorted({row["flight_id"] for row in load_csv(query_seed_csv)}):
        rows.append(
            {
                "flight_id": flight_id,
                "asset_version_tag": "caiwangcun_fullreplace_domdsm_0p14m_epsg32650",
                "odm_orthophoto_path": as_manifest_path(ortho_mosaic),
                "dsm_path": as_manifest_path(dsm_mosaic),
                "asset_source": "CaiWangCun finished DOM/DSM full-replacement branch",
            }
        )
    write_csv(path, rows)


def materialize_dsm_from_mosaic(bundle_root: Path, dsm_manifest_csv: Path, source_dsm: Path, target_crs: str) -> None:
    try:
        import rasterio
        from rasterio.windows import from_bounds
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("rasterio is required to crop CaiWangCun DSM rasters") from exc

    rows = load_csv(dsm_manifest_csv)
    out_root = bundle_root / "dsm_cache" / "rasters"
    ensure_dir(out_root)
    status_counts: Counter[str] = Counter()
    built_examples = []
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


def validate_candidate_ids(retrieval_csv: Path, tiles_csv: Path) -> dict[str, object]:
    tile_ids = {row["tile_id"] for row in load_csv(tiles_csv)}
    retrieval_rows = load_csv(retrieval_csv)
    missing = sorted({row["candidate_tile_id"] for row in retrieval_rows if row["candidate_tile_id"] not in tile_ids})
    if missing:
        raise SystemExit(f"retrieval contains candidate IDs outside CaiWangCun tiles.csv: {missing[:5]}")
    return {"retrieval_row_count": len(retrieval_rows), "candidate_tile_count": len(tile_ids), "missing_count": len(missing)}


def main() -> None:
    args = parse_args()
    experiment_root = resolve_runtime_path(args.experiment_root)
    reuse_root = resolve_runtime_path(args.reuse_root)
    caiwangcun_root = resolve_runtime_path(args.caiwangcun_root)
    bundle_root = experiment_root / "pose_v1_formal"
    log_path = experiment_root / "logs" / "fullreplace_gate.log"

    if experiment_root.exists() and args.overwrite:
        shutil.rmtree(experiment_root)
    ensure_dir(experiment_root / "plan")
    ensure_dir(experiment_root / "source_mosaic")
    ensure_dir(bundle_root)

    sync_reused_assets(reuse_root, experiment_root, args.overwrite)
    rewrite_reused_manifests(reuse_root, experiment_root)
    copy_script_snapshots(experiment_root)

    ortho_tiles = find_source_tiles(caiwangcun_root, "ortho")
    dsm_tiles = find_source_tiles(caiwangcun_root, "dsm")
    write_csv(experiment_root / "plan" / "caiwangcun_source_tile_manifest.csv", summarize_source_tiles([*ortho_tiles, *dsm_tiles]))

    ortho_mosaic = experiment_root / "source_mosaic" / "caiwangcun_ortho_0p14m_epsg32650.tif"
    dsm_mosaic = experiment_root / "source_mosaic" / "caiwangcun_dsm_0p14m_epsg32650.tif"
    if args.skip_mosaic and (not ortho_mosaic.exists() or not dsm_mosaic.exists()):
        raise SystemExit("--skip-mosaic was supplied but CaiWangCun mosaics are missing")
    if args.skip_mosaic:
        ortho_summary = {"path": as_manifest_path(ortho_mosaic)}
        dsm_summary = {"path": as_manifest_path(dsm_mosaic)}
    else:
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

    candidate_root = experiment_root / "candidate_library"
    tiles_csv = candidate_root / "tiles.csv"
    run_cmd(
        [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "build_caiwangcun_candidate_library.py"),
            "--query-seed-csv",
            str(reuse_root / "query_truth" / "queries_truth_seed.csv"),
            "--ortho-mosaic",
            str(ortho_mosaic),
            "--dsm-mosaic",
            str(dsm_mosaic),
            "--out-dir",
            str(candidate_root / "tiles_native"),
            "--metadata-csv",
            str(tiles_csv),
            "--roi-summary-json",
            str(candidate_root / "roi_summary.json"),
            "--tile-sizes",
            "200",
            "300",
            "500",
            "700",
            "--overlap",
            "0.25",
            "--roi-buffer-meters",
            "250",
            "--dsm-expand-margin-m",
            "250",
        ],
        log_path,
        args.dry_run,
    )

    run_cmd(
        [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "generate_query_truth_from_coverage_v2.py"),
            "--selected-query-csv",
            str(experiment_root / "selected_queries" / "selected_images_summary.csv"),
            "--tile-metadata-csv",
            str(tiles_csv),
            "--out-dir",
            str(experiment_root / "query_truth"),
        ],
        log_path,
        args.dry_run,
    )
    query_seed_csv = experiment_root / "query_truth" / "queries_truth_seed.csv"
    query_truth_tiles_csv = experiment_root / "query_truth" / "query_truth_tiles.csv"
    write_asset_manifest(experiment_root / "plan" / "caiwangcun_asset_manifest.csv", query_seed_csv, ortho_mosaic, dsm_mosaic)

    retrieval_top20 = experiment_root / "retrieval" / "retrieval_top20.csv"
    romav2_root = experiment_root / "romav2_rerank"
    if not args.skip_retrieval:
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "extract_dino_features.py"),
                "--input-csv",
                str(tiles_csv),
                "--id-column",
                "tile_id",
                "--image-column",
                "image_path",
                "--output-npz",
                str(experiment_root / "candidate_features" / "caiwangcun_tile_dinov2_pooler.npz"),
                "--output-csv",
                str(experiment_root / "candidate_features" / "caiwangcun_tile_dinov2_status.csv"),
                "--model-name",
                "facebook/dinov2-base",
                "--device",
                args.device,
            ],
            log_path,
            args.dry_run,
        )
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "build_faiss_index.py"),
                "--features-npz",
                str(experiment_root / "candidate_features" / "caiwangcun_tile_dinov2_pooler.npz"),
                "--metadata-csv",
                str(tiles_csv),
                "--id-column",
                "tile_id",
                "--index-type",
                "ip",
                "--output-index",
                str(experiment_root / "faiss" / "caiwangcun_tiles_ip.index"),
                "--output-mapping-json",
                str(experiment_root / "faiss" / "caiwangcun_tiles_ip_mapping.json"),
            ],
            log_path,
            args.dry_run,
        )
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "evaluate_retrieval_against_intersection_truth.py"),
                "--query-features-npz",
                str(experiment_root / "query_features" / "query_dinov2_pooler.npz"),
                "--query-seed-csv",
                str(query_seed_csv),
                "--query-truth-tiles-csv",
                str(query_truth_tiles_csv),
                "--faiss-index",
                str(experiment_root / "faiss" / "caiwangcun_tiles_ip.index"),
                "--mapping-json",
                str(experiment_root / "faiss" / "caiwangcun_tiles_ip_mapping.json"),
                "--top-k",
                str(args.top_k),
                "--output-csv",
                str(romav2_root / "coarse" / f"retrieval_top{args.top_k}.csv"),
                "--summary-json",
                str(romav2_root / "coarse" / f"summary_top{args.top_k}.json"),
                "--curve-csv",
                str(romav2_root / "coarse" / f"topk_truth_curve_top{args.top_k}.csv"),
            ],
            log_path,
            args.dry_run,
        )
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "prepare_romav2_intersection_inputs.py"),
                "--query-manifest-csv",
                str(experiment_root / "query_inputs" / "query_manifest.csv"),
                "--query-seed-csv",
                str(query_seed_csv),
                "--query-truth-tiles-csv",
                str(query_truth_tiles_csv),
                "--coarse-retrieval-csv",
                str(romav2_root / "coarse" / f"retrieval_top{args.top_k}.csv"),
                "--top-k",
                str(args.top_k),
                "--out-root",
                str(romav2_root / "input_round"),
            ],
            log_path,
            args.dry_run,
        )
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "run_romav2_rerank_intersection_round.py"),
                "--input-round-root",
                str(romav2_root / "input_round"),
                "--tiles-csv",
                str(tiles_csv),
                "--out-root",
                str(romav2_root),
                "--top-k",
                str(args.top_k),
                "--python-bin",
                args.python_bin,
                "--device",
                args.device,
                "--sample-count",
                str(args.romav2_sample_count),
                "--ranking-mode",
                "inlier_count_only",
                "--timing-json",
                str(romav2_root / "timing" / "romav2_rerank_internal.json"),
            ]
            + [item for query_id in args.rerank_query_id for item in ("--query-id", query_id)],
            log_path,
            args.dry_run,
        )
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "export_romav2_reranked_for_pose.py"),
                "--stage7-root",
                str(romav2_root / "stage7"),
                "--out-csv",
                str(retrieval_top20),
                "--top-k",
                str(args.top_k),
            ],
            log_path,
            args.dry_run,
        )
        if not args.dry_run:
            write_json(experiment_root / "plan" / "retrieval_candidate_id_audit.json", validate_candidate_ids(retrieval_top20, tiles_csv))

    if not args.skip_pose:
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "build_formal_query_manifest.py"),
                "--bundle-root",
                str(bundle_root),
                "--query-manifest-csv",
                str(experiment_root / "query_inputs" / "query_manifest.csv"),
                "--selected-summary-csv",
                str(experiment_root / "selected_queries" / "selected_images_summary.csv"),
            ],
            log_path,
            args.dry_run,
        )
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "build_formal_candidate_manifest.py"),
                "--bundle-root",
                str(bundle_root),
                "--retrieval-top20-csv",
                str(retrieval_top20),
                "--tiles-csv",
                str(tiles_csv),
                "--query-truth-tiles-csv",
                str(query_truth_tiles_csv),
                "--query-truth-csv",
                str(experiment_root / "query_truth" / "query_truth.csv"),
            ],
            log_path,
            args.dry_run,
        )
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "build_candidate_dsm_cache.py"),
                "--bundle-root",
                str(bundle_root),
                "--dsm-source-name",
                "caiwangcun_dsm_0p14m_epsg32650",
                "--dsm-source-type",
                "finished_caiwangcun_dsm",
                "--dsm-asset-version-tag",
                "caiwangcun_fullreplace_domdsm_0p14m_epsg32650",
                "--upstream-dsm-path",
                str(dsm_mosaic),
                "--expand-margin-m",
                "250",
            ],
            log_path,
            args.dry_run,
        )
        if not args.dry_run:
            source_root = bundle_root / "dsm_cache" / "source"
            ensure_dir(source_root)
            shutil.copy2(dsm_mosaic, source_root / "caiwangcun_dsm_0p14m_epsg32650.tif")
            materialize_dsm_from_mosaic(
                bundle_root,
                bundle_root / "input" / "formal_dsm_manifest.csv",
                dsm_mosaic,
                args.target_crs,
            )
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
                str(retrieval_top20),
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

    suite_root = bundle_root / "eval_pose_validation_suite_caiwangcun_truth"
    if not args.skip_validation:
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "run_pose_validation_suite.py"),
                "--bundle-root",
                str(bundle_root),
                "--query-seed-csv",
                str(query_seed_csv),
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
                str(suite_root),
                "--overwrite",
            ],
            log_path,
            args.dry_run,
        )
        run_cmd(
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts" / "diagnose_pose_frame_sanity.py"),
                "--bundle-root",
                str(bundle_root),
                "--suite-root",
                str(suite_root),
                "--output-root",
                str(suite_root / "ortho_alignment" / "frame_sanity"),
            ],
            log_path,
            args.dry_run,
        )

    write_json(
        experiment_root / "plan" / "run_gate_summary.json",
        {
            "experiment_root": as_manifest_path(experiment_root),
            "reuse_root": as_manifest_path(reuse_root),
            "caiwangcun_root": as_manifest_path(caiwangcun_root),
            "candidate_tiles_csv": as_manifest_path(tiles_csv),
            "retrieval_top20_csv": as_manifest_path(retrieval_top20),
            "bundle_root": as_manifest_path(bundle_root),
            "pose_gate_summary": as_manifest_path(bundle_root / "summary" / "phase_gate_summary.json"),
            "validation_gate_summary": as_manifest_path(suite_root / "phase_gate_summary.json"),
            "frame_sanity_summary": as_manifest_path(suite_root / "ortho_alignment" / "frame_sanity" / "overall_frame_sanity.json"),
            "generated_at_utc": utc_now(),
        },
    )


if __name__ == "__main__":
    main()

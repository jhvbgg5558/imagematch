#!/usr/bin/env python3
"""Render orthophoto-truth evaluation visualizations for formal pose results.

Purpose:
- export quick-look PNGs for predicted orthophotos, truth orthophotos, and
  their overlays on a shared grid;
- render a diagnostic DOM overlay for the best candidate without using it as
  the primary evaluation target;
- keep visualization outputs aligned with the same truth-grid products used by
  the quantitative evaluation stage.

Main inputs:
- `<output_root>/query_ortho_truth_manifest.csv`;
- `<output_root>/pred_tiles/pred_tile_manifest.csv`;
- `summary/per_query_best_pose.csv`;
- `input/formal_candidate_manifest.csv`;
- truth / predicted orthophoto GeoTIFF tiles.

Main outputs:
- `<output_root>/viz_overlay_truth/*.png`;
- `<output_root>/viz_overlay_dom/*.png`;
- `<output_root>/viz_overlay_truth/_summary.json`;
- `<output_root>/viz_overlay_dom/_summary.json`.

Applicable task constraints:
- truth overlay is the primary accuracy visualization;
- DOM overlay is diagnostic-only and must not replace truth-based validation.
"""

from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

import numpy as np

from pose_ortho_truth_utils import (
    DEFAULT_FORMAL_BUNDLE_ROOT,
    ensure_dir,
    load_csv,
    resolve_runtime_path,
    resolve_output_root,
    valid_mask_from_image,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_FORMAL_BUNDLE_ROOT))
    parser.add_argument("--truth-manifest-csv", default=None)
    parser.add_argument("--pred-manifest-csv", default=None)
    parser.add_argument("--best-pose-csv", default=None)
    parser.add_argument("--candidate-manifest-csv", default=None)
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--output-root", default=None)
    return parser.parse_args()


def save_png(path: Path, rgb: np.ndarray) -> None:
    import cv2

    ensure_dir(path.parent)
    ok, encoded = cv2.imencode(".png", rgb[:, :, ::-1])
    if not ok:
        raise RuntimeError(f"Failed to encode PNG: {path}")
    encoded.tofile(str(path))


def read_raster(path: Path) -> tuple[np.ndarray, object]:
    import rasterio

    with rasterio.open(path) as ds:
        return ds.read(), ds.profile.copy()


def to_rgb(data: np.ndarray) -> np.ndarray:
    if data.ndim != 3:
        raise ValueError("expected (bands, rows, cols) raster layout")
    if data.shape[0] >= 3:
        rgb = np.moveaxis(data[:3], 0, -1)
    elif data.shape[0] == 1:
        rgb = np.repeat(np.moveaxis(data[:1], 0, -1), 3, axis=2)
    else:
        rgb = np.repeat(np.mean(np.moveaxis(data, 0, -1), axis=2, keepdims=True), 3, axis=2)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def draw_mask_outline(rgb: np.ndarray, mask: np.ndarray, color_bgr: tuple[int, int, int]) -> np.ndarray:
    import cv2

    out = rgb[:, :, ::-1].copy()
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        cv2.drawContours(out, contours, -1, color_bgr, 2)
    return out[:, :, ::-1]


def alpha_overlay(base_rgb: np.ndarray, top_rgb: np.ndarray, top_mask: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    out = base_rgb.astype(np.float32)
    top = top_rgb.astype(np.float32)
    mask = top_mask[:, :, None].astype(np.float32)
    blended = (1.0 - alpha) * out + alpha * top
    return np.clip(np.where(mask > 0.0, blended, out), 0, 255).astype(np.uint8)


def crop_dom_to_truth_grid(source_tif: Path, truth_path: Path) -> tuple[str, str, np.ndarray | None]:
    try:
        import rasterio
        from rasterio.warp import reproject, Resampling
    except Exception as exc:  # pragma: no cover - dependency guard
        raise SystemExit("rasterio is required for DOM overlay rendering") from exc

    if not source_tif.exists():
        return "missing_dom_source", f"DOM source not found: {source_tif}", None
    with rasterio.open(truth_path) as truth_ds, rasterio.open(source_tif) as src_ds:
        if truth_ds.crs is None or src_ds.crs is None:
            return "missing_dom_crs", "truth or DOM source has no CRS", None
        dst = np.zeros((min(3, src_ds.count), truth_ds.height, truth_ds.width), dtype=np.uint8)
        for band_idx in range(dst.shape[0]):
            reproject(
                source=rasterio.band(src_ds, band_idx + 1),
                destination=dst[band_idx],
                src_transform=src_ds.transform,
                src_crs=src_ds.crs,
                dst_transform=truth_ds.transform,
                dst_crs=truth_ds.crs,
                dst_nodata=0,
                resampling=Resampling.bilinear,
            )
        return "ok", "", dst


def render_truth_bundle(query_id: str, truth_path: Path, pred_path: Path, out_root: Path) -> tuple[str, str]:
    truth_data, _ = read_raster(truth_path)
    pred_data, _ = read_raster(pred_path)
    truth_rgb = to_rgb(truth_data)
    pred_rgb = to_rgb(pred_data)
    truth_mask = valid_mask_from_image(truth_data)
    pred_mask = valid_mask_from_image(pred_data)

    save_png(out_root / f"{query_id}_truth.png", truth_rgb)
    save_png(out_root / f"{query_id}_pred.png", pred_rgb)
    save_png(out_root / f"{query_id}_overlay.png", alpha_overlay(truth_rgb, pred_rgb, pred_mask))
    save_png(
        out_root / f"{query_id}_outline.png",
        draw_mask_outline(draw_mask_outline(truth_rgb, truth_mask, (0, 255, 0)), pred_mask, (255, 0, 0)),
    )
    return "ok", ""


def render_dom_bundle(
    query_id: str,
    truth_path: Path,
    pred_path: Path,
    source_tif: Path,
    out_root: Path,
) -> tuple[str, str]:
    truth_data, _ = read_raster(truth_path)
    pred_data, _ = read_raster(pred_path)
    pred_rgb = to_rgb(pred_data)
    pred_mask = valid_mask_from_image(pred_data)
    dom_status, dom_detail, dom_data = crop_dom_to_truth_grid(source_tif, truth_path)
    if dom_status != "ok" or dom_data is None:
        return dom_status, dom_detail
    dom_rgb = to_rgb(dom_data)
    dom_mask = valid_mask_from_image(dom_data)
    save_png(out_root / f"{query_id}_dom.png", dom_rgb)
    save_png(out_root / f"{query_id}_pred_vs_dom_overlay.png", alpha_overlay(dom_rgb, pred_rgb, pred_mask))
    save_png(
        out_root / f"{query_id}_pred_vs_dom_outline.png",
        draw_mask_outline(draw_mask_outline(dom_rgb, dom_mask, (0, 255, 0)), pred_mask, (255, 0, 0)),
    )
    return "ok", ""


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    eval_root = resolve_output_root(bundle_root, args.output_root)
    truth_manifest_csv = Path(args.truth_manifest_csv) if args.truth_manifest_csv else eval_root / "query_ortho_truth_manifest.csv"
    pred_manifest_csv = Path(args.pred_manifest_csv) if args.pred_manifest_csv else eval_root / "pred_tiles" / "pred_tile_manifest.csv"
    best_pose_csv = Path(args.best_pose_csv) if args.best_pose_csv else bundle_root / "summary" / "per_query_best_pose.csv"
    candidate_manifest_csv = Path(args.candidate_manifest_csv) if args.candidate_manifest_csv else bundle_root / "input" / "formal_candidate_manifest.csv"

    truth_rows = load_csv(resolve_runtime_path(truth_manifest_csv))
    pred_rows = load_csv(resolve_runtime_path(pred_manifest_csv))
    best_rows = load_csv(resolve_runtime_path(best_pose_csv))
    candidate_rows = load_csv(resolve_runtime_path(candidate_manifest_csv))
    selected_query_ids = set(args.query_id)

    truth_by_query = {row["query_id"]: row for row in truth_rows if not selected_query_ids or row["query_id"] in selected_query_ids}
    pred_by_query = {row["query_id"]: row for row in pred_rows if not selected_query_ids or row["query_id"] in selected_query_ids}
    best_by_query = {row["query_id"]: row for row in best_rows if not selected_query_ids or row["query_id"] in selected_query_ids}
    candidate_by_key = {(row["query_id"], row["candidate_id"]): row for row in candidate_rows}

    truth_out_root = eval_root / "viz_overlay_truth"
    dom_out_root = eval_root / "viz_overlay_dom"
    ensure_dir(truth_out_root)
    ensure_dir(dom_out_root)

    truth_status_counts: Counter[str] = Counter()
    dom_status_counts: Counter[str] = Counter()

    for query_id in sorted(set(truth_by_query) | set(pred_by_query) | set(best_by_query)):
        truth_row = truth_by_query.get(query_id)
        pred_row = pred_by_query.get(query_id)
        best_row = best_by_query.get(query_id)
        if truth_row is None or pred_row is None or best_row is None:
            truth_status_counts["missing_inputs"] += 1
            dom_status_counts["missing_inputs"] += 1
            continue
        if pred_row.get("status") not in {"ok", "exists"}:
            truth_status_counts[pred_row.get("status", "pred_ortho_failed")] += 1
            dom_status_counts[pred_row.get("status", "pred_ortho_failed")] += 1
            continue

        truth_path = resolve_runtime_path(truth_row["truth_crop_path"])
        pred_path = resolve_runtime_path(pred_row["pred_crop_path"])
        if (truth_out_root / f"{query_id}_overlay.png").exists() and not args.overwrite:
            truth_status = "exists"
            truth_detail = ""
        else:
            truth_status, truth_detail = render_truth_bundle(query_id, truth_path, pred_path, truth_out_root)
        truth_status_counts[truth_status] += 1

        candidate_row = candidate_by_key.get((query_id, best_row["best_candidate_id"]))
        if candidate_row is None:
            dom_status_counts["missing_candidate_manifest"] += 1
            continue
        source_tif = resolve_runtime_path(candidate_row["source_tif"])
        if (dom_out_root / f"{query_id}_pred_vs_dom_overlay.png").exists() and not args.overwrite:
            dom_status = "exists"
            dom_detail = ""
        else:
            dom_status, dom_detail = render_dom_bundle(query_id, truth_path, pred_path, source_tif, dom_out_root)
        dom_status_counts[dom_status] += 1

    write_json(
        truth_out_root / "_summary.json",
        {
            "bundle_root": str(bundle_root),
            "truth_manifest_csv": str(resolve_runtime_path(truth_manifest_csv)),
            "pred_manifest_csv": str(resolve_runtime_path(pred_manifest_csv)),
            "row_count": len(truth_by_query),
            "status_counts": dict(truth_status_counts),
            "generated_at_unix": time.time(),
        },
    )
    write_json(
        dom_out_root / "_summary.json",
        {
            "bundle_root": str(bundle_root),
            "candidate_manifest_csv": str(resolve_runtime_path(candidate_manifest_csv)),
            "best_pose_csv": str(resolve_runtime_path(best_pose_csv)),
            "row_count": len(best_by_query),
            "status_counts": dict(dom_status_counts),
            "generated_at_unix": time.time(),
        },
    )
    print(truth_out_root / "_summary.json")


if __name__ == "__main__":
    main()

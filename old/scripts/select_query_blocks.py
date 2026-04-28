#!/usr/bin/env python3
"""Select representative drone query blocks and export query metadata."""

from __future__ import annotations

import argparse
import ast
import csv
import math
from pathlib import Path
from time import perf_counter

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window, bounds as window_bounds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select representative drone query blocks.")
    parser.add_argument("--ortho-tif", required=True, help="Drone orthophoto GeoTIFF.")
    parser.add_argument(
        "--stage1-tiles-csv",
        required=True,
        help="Stage1 satellite metadata CSV for truth lookup.",
    )
    parser.add_argument("--out-dir", required=True, help="Directory for resized query images.")
    parser.add_argument("--metadata-csv", required=True, help="Output CSV for selected query metadata.")
    parser.add_argument(
        "--scales",
        type=float,
        nargs="+",
        default=[120.0, 200.0],
        help="Ground window sizes in meters.",
    )
    parser.add_argument(
        "--count-per-scale",
        type=int,
        default=5,
        help="How many query blocks to keep per scale.",
    )
    parser.add_argument(
        "--candidate-stride-ratio",
        type=float,
        default=0.4,
        help="Stride as a fraction of window size for candidate generation.",
    )
    parser.add_argument(
        "--min-separation-ratio",
        type=float,
        default=0.8,
        help="Minimum center distance between kept blocks, as a fraction of scale.",
    )
    parser.add_argument(
        "--alpha-threshold",
        type=int,
        default=8,
        help="Alpha threshold below which pixels are treated as invalid.",
    )
    parser.add_argument(
        "--max-invalid-ratio",
        type=float,
        default=0.3,
        help="Reject candidate if invalid pixels exceed this ratio.",
    )
    parser.add_argument("--resize", type=int, default=512, help="Output image size.")
    parser.add_argument(
        "--min-gradient-mean",
        type=float,
        default=0.0,
        help="Reject candidate if mean gradient magnitude is below this threshold.",
    )
    parser.add_argument(
        "--min-texture-std",
        type=float,
        default=0.0,
        help="Reject candidate if grayscale texture std is below this threshold.",
    )
    return parser.parse_args()


def load_stage1_tiles(path: Path) -> list[dict[str, object]]:
    tiles = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tiles.append(
                {
                    "tile_id": row["tile_id"],
                    "scale_level_m": int(float(row["scale_level_m"])),
                    "min_x": float(row["min_x"]),
                    "min_y": float(row["min_y"]),
                    "max_x": float(row["max_x"]),
                    "max_y": float(row["max_y"]),
                }
            )
    return tiles


def find_truth_tiles(tiles: list[dict[str, object]], center_x: float, center_y: float) -> list[str]:
    hits = []
    for tile in tiles:
        if tile["min_x"] <= center_x <= tile["max_x"] and tile["min_y"] <= center_y <= tile["max_y"]:
            hits.append(str(tile["tile_id"]))
    return hits


def compute_score(
    rgb: np.ndarray,
    alpha: np.ndarray | None,
    alpha_threshold: int,
    max_invalid_ratio: float,
    min_gradient_mean: float,
    min_texture_std: float,
):
    if alpha is None:
        valid_mask = np.ones(rgb.shape[1:], dtype=bool)
    else:
        valid_mask = alpha > alpha_threshold
    invalid_ratio = 1.0 - float(valid_mask.mean())
    if invalid_ratio > max_invalid_ratio:
        return None

    gray = rgb.mean(axis=0).astype(np.float32)
    gray_valid = gray[valid_mask]
    if gray_valid.size == 0:
        return None

    std = float(gray_valid.std())
    gy, gx = np.gradient(gray)
    grad_mag = np.sqrt(gx * gx + gy * gy)
    grad_mean = float(grad_mag[valid_mask].mean())
    if grad_mean < min_gradient_mean or std < min_texture_std:
        return None

    score = std + 0.7 * grad_mean
    return score, invalid_ratio, std, grad_mean


def window_to_dict(
    ds,
    window: Window,
    scale_m: float,
    score: float,
    invalid_ratio: float,
    texture_std: float,
    gradient_mean: float,
    stage1_tiles: list[dict[str, object]],
):
    b = window_bounds(window, ds.transform)
    center_x = (b[0] + b[2]) / 2.0
    center_y = (b[1] + b[3]) / 2.0
    truth_tile_ids = find_truth_tiles(stage1_tiles, center_x, center_y)
    return {
        "scale_m": scale_m,
        "window": window,
        "pixel_col_off": int(window.col_off),
        "pixel_row_off": int(window.row_off),
        "pixel_width": int(window.width),
        "pixel_height": int(window.height),
        "min_x": b[0],
        "min_y": b[1],
        "max_x": b[2],
        "max_y": b[3],
        "center_x": center_x,
        "center_y": center_y,
        "score": score,
        "invalid_ratio": invalid_ratio,
        "texture_std": texture_std,
        "gradient_mean": gradient_mean,
        "truth_tile_ids": truth_tile_ids,
    }


def distance(a: dict[str, object], b: dict[str, object]) -> float:
    dx = float(a["center_x"]) - float(b["center_x"])
    dy = float(a["center_y"]) - float(b["center_y"])
    return math.hypot(dx, dy)


def select_candidates(ds, scale_m: float, args, stage1_tiles):
    res_x = abs(ds.res[0])
    res_y = abs(ds.res[1])
    win_w = max(1, int(round(scale_m / res_x)))
    win_h = max(1, int(round(scale_m / res_y)))
    stride = max(1, int(round(min(win_w, win_h) * args.candidate_stride_ratio)))

    candidates = []
    max_row = ds.height - win_h
    max_col = ds.width - win_w
    for row_off in range(0, max_row + 1, stride):
        for col_off in range(0, max_col + 1, stride):
            window = Window(col_off, row_off, win_w, win_h)
            data = ds.read(
                indexes=[1, 2, 3, 4] if ds.count >= 4 else [1, 2, 3],
                window=window,
                out_dtype="uint8",
            )
            rgb = data[:3]
            alpha = data[3] if data.shape[0] >= 4 else None
            result = compute_score(
                rgb,
                alpha,
                args.alpha_threshold,
                args.max_invalid_ratio,
                args.min_gradient_mean,
                args.min_texture_std,
            )
            if result is None:
                continue
            score, invalid_ratio, texture_std, gradient_mean = result
            candidates.append(
                window_to_dict(
                    ds,
                    window,
                    scale_m,
                    score,
                    invalid_ratio,
                    texture_std,
                    gradient_mean,
                    stage1_tiles,
                )
            )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected = []
    min_sep = scale_m * args.min_separation_ratio
    for cand in candidates:
        if all(distance(cand, kept) >= min_sep for kept in selected):
            selected.append(cand)
        if len(selected) >= args.count_per_scale:
            break
    return selected


def save_query_image(ds, item: dict[str, object], out_path: Path, resize: int) -> None:
    window = item["window"]
    indexes = [1, 2, 3] if ds.count >= 3 else [1]
    data = ds.read(
        indexes=indexes,
        window=window,
        out_shape=(len(indexes), resize, resize),
        boundless=False,
        resampling=Resampling.bilinear,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "PNG",
        "width": resize,
        "height": resize,
        "count": len(indexes),
        "dtype": data.dtype,
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data)


def main() -> None:
    args = parse_args()
    ortho_tif = Path(args.ortho_tif)
    out_dir = Path(args.out_dir)
    metadata_csv = Path(args.metadata_csv)
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata_csv.parent.mkdir(parents=True, exist_ok=True)

    stage1_tiles = load_stage1_tiles(Path(args.stage1_tiles_csv))
    t0 = perf_counter()

    with rasterio.open(ortho_tif) as ds, metadata_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "query_id",
                "scale_m",
                "image_path",
                "ortho_tif",
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
                "score",
                "invalid_ratio",
                "texture_std",
                "gradient_mean",
                "truth_tile_ids",
            ]
        )

        total = 0
        for scale_m in args.scales:
            selected = select_candidates(ds, scale_m, args, stage1_tiles)
            print(f"scale={scale_m}m selected={len(selected)}")
            for idx, item in enumerate(selected, start=1):
                query_id = f"q_{int(round(scale_m))}m_{idx:02d}"
                image_path = out_dir / f"{query_id}.png"
                save_query_image(ds, item, image_path, args.resize)
                writer.writerow(
                    [
                        query_id,
                        scale_m,
                        str(image_path),
                        str(ortho_tif),
                        item["pixel_col_off"],
                        item["pixel_row_off"],
                        item["pixel_width"],
                        item["pixel_height"],
                        item["center_x"],
                        item["center_y"],
                        item["min_x"],
                        item["min_y"],
                        item["max_x"],
                        item["max_y"],
                        item["score"],
                        item["invalid_ratio"],
                        item["texture_std"],
                        item["gradient_mean"],
                        "|".join(item["truth_tile_ids"]),
                    ]
                )
                total += 1

    elapsed = perf_counter() - t0
    print(f"Metadata written to {metadata_csv}")
    print(f"Finished. total_queries={total} elapsed={elapsed/60:.1f}min")


if __name__ == "__main__":
    main()

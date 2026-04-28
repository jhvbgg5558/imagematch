#!/usr/bin/env python3
"""Shared helpers for UAV orthophoto-truth pose evaluation.

Purpose:
- centralize CSV/JSON/path/grid helpers used by the orthophoto-truth
  evaluation scripts;
- keep CRS/grid parsing consistent across truth-crop, predicted-ortho,
  metric, and visualization stages.

Main inputs:
- manifest CSV/JSON files under `new1output/query_reselect_2026-03-26_v2`
  and `new2output/pose_v1_formal`;
- orthophoto / DSM raster metadata and affine transforms.

Main outputs:
- helper return values only; this module does not write evaluation products.

Applicable task constraints:
- query is a single arbitrary UAV image;
- query is not guaranteed to be orthophoto;
- runtime pose outputs must remain separate from offline evaluation truth.
"""

from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
from typing import Iterable

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FORMAL_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"
DEFAULT_QUERY_ROOT = PROJECT_ROOT / "new1output" / "query_reselect_2026-03-26_v2"
DEFAULT_RAW_UAV_ROOT = Path(r"D:\数据\武汉影像\无人机0.1m")
DEFAULT_ORTHO_EVAL_DIRNAME = "eval_ortho_truth"
DEFAULT_VALIDATION_SUITE_DIRNAME = "eval_pose_validation_suite"


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


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_runtime_path(raw_path: str | Path) -> Path:
    text = str(raw_path)
    if os.name == "nt" and text.startswith("/mnt/") and len(text) > 6:
        drive_letter = text[5]
        remainder = text[7:].replace("/", "\\")
        return Path(f"{drive_letter.upper()}:\\{remainder}")
    if os.name != "nt" and len(text) >= 3 and text[1:3] == ":\\":
        drive_letter = text[0].lower()
        remainder = text[3:].replace("\\", "/")
        return Path(f"/mnt/{drive_letter}/{remainder}")
    return Path(text)


def resolve_output_root(
    bundle_root: Path,
    output_root: str | Path | None,
    default_dirname: str = DEFAULT_ORTHO_EVAL_DIRNAME,
) -> Path:
    if output_root is None or str(output_root) == "":
        return bundle_root / default_dirname
    return resolve_runtime_path(output_root)


def normalize_angle_deg(angle_deg: float) -> float:
    wrapped = (float(angle_deg) + 180.0) % 360.0 - 180.0
    if wrapped == -180.0:
        return 180.0
    return wrapped


def angle_diff_deg(first_deg: float, second_deg: float) -> float:
    return abs(normalize_angle_deg(float(first_deg) - float(second_deg)))


def unit_vector(vector: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(vector), dtype=np.float64)
    norm = float(np.linalg.norm(arr))
    if norm <= 0.0:
        return np.zeros(arr.shape, dtype=np.float64)
    return arr / norm


def parse_json_list(text: str | None) -> list[object]:
    if text is None or text == "":
        return []
    return json.loads(text)


def parse_float_list(text: str | None) -> list[float]:
    return [float(item) for item in parse_json_list(text)]


def parse_footprint_polygon_xy(text: str) -> list[tuple[float, float]]:
    coords = parse_json_list(text)
    return [(float(item[0]), float(item[1])) for item in coords]


def rotation_matrix_from_rvec(rvec_values: Iterable[float]) -> np.ndarray:
    rvec = np.asarray(list(rvec_values), dtype=np.float64).reshape(3)
    theta = float(np.linalg.norm(rvec))
    if theta <= 1e-12:
        return np.eye(3, dtype=np.float64)

    axis = rvec / theta
    axis_x, axis_y, axis_z = float(axis[0]), float(axis[1]), float(axis[2])
    skew = np.array(
        [
            [0.0, -axis_z, axis_y],
            [axis_z, 0.0, -axis_x],
            [-axis_y, axis_x, 0.0],
        ],
        dtype=np.float64,
    )
    identity = np.eye(3, dtype=np.float64)
    return identity + math.sin(theta) * skew + (1.0 - math.cos(theta)) * (skew @ skew)


def view_direction_from_yaw_pitch(yaw_deg: float, pitch_deg: float) -> np.ndarray:
    yaw_rad = math.radians(float(yaw_deg))
    pitch_rad = math.radians(float(pitch_deg))
    return unit_vector(
        (
            math.cos(pitch_rad) * math.sin(yaw_rad),
            math.cos(pitch_rad) * math.cos(yaw_rad),
            math.sin(pitch_rad),
        )
    )


def orientation_from_world_to_camera_rvec(rvec_values: Iterable[float]) -> dict[str, float]:
    rotation_matrix = rotation_matrix_from_rvec(rvec_values)
    axes_world = rotation_matrix.T
    right_world = unit_vector(axes_world[:, 0])
    down_world = unit_vector(axes_world[:, 1])
    forward_world = unit_vector(axes_world[:, 2])

    horizontal_norm = math.hypot(float(forward_world[0]), float(forward_world[1]))
    yaw_deg = normalize_angle_deg(math.degrees(math.atan2(float(forward_world[0]), float(forward_world[1]))))
    pitch_deg = math.degrees(math.atan2(float(forward_world[2]), horizontal_norm))

    world_up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    ref_right = np.cross(forward_world, world_up)
    if float(np.linalg.norm(ref_right)) <= 1e-8:
        roll_deg = math.nan
    else:
        ref_right = unit_vector(ref_right)
        ref_down = unit_vector(np.cross(forward_world, ref_right))
        roll_deg = math.degrees(
            math.atan2(
                float(np.dot(np.cross(ref_down, down_world), forward_world)),
                float(np.dot(ref_down, down_world)),
            )
        )

    return {
        "yaw_deg": yaw_deg,
        "pitch_deg": pitch_deg,
        "roll_deg": normalize_angle_deg(roll_deg) if math.isfinite(roll_deg) else math.nan,
        "view_dir_x": float(forward_world[0]),
        "view_dir_y": float(forward_world[1]),
        "view_dir_z": float(forward_world[2]),
        "right_dir_x": float(right_world[0]),
        "right_dir_y": float(right_world[1]),
        "right_dir_z": float(right_world[2]),
        "down_dir_x": float(down_world[0]),
        "down_dir_y": float(down_world[1]),
        "down_dir_z": float(down_world[2]),
    }


def orientation_from_yaw_pitch_roll(
    yaw_deg: float,
    pitch_deg: float,
    roll_deg: float,
) -> dict[str, float]:
    forward_world = view_direction_from_yaw_pitch(yaw_deg, pitch_deg)
    world_up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    ref_right = np.cross(forward_world, world_up)
    if float(np.linalg.norm(ref_right)) <= 1e-8:
        ref_right = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    ref_right = unit_vector(ref_right)
    ref_down = unit_vector(np.cross(forward_world, ref_right))

    roll_rad = math.radians(float(roll_deg))
    down_world = unit_vector(
        ref_down * math.cos(roll_rad) + np.cross(forward_world, ref_down) * math.sin(roll_rad)
    )
    right_world = unit_vector(np.cross(down_world, forward_world))

    return {
        "yaw_deg": normalize_angle_deg(float(yaw_deg)),
        "pitch_deg": float(pitch_deg),
        "roll_deg": normalize_angle_deg(float(roll_deg)),
        "view_dir_x": float(forward_world[0]),
        "view_dir_y": float(forward_world[1]),
        "view_dir_z": float(forward_world[2]),
        "right_dir_x": float(right_world[0]),
        "right_dir_y": float(right_world[1]),
        "right_dir_z": float(right_world[2]),
        "down_dir_x": float(down_world[0]),
        "down_dir_y": float(down_world[1]),
        "down_dir_z": float(down_world[2]),
    }


def view_dir_angle_error_deg(first_vector: Iterable[float], second_vector: Iterable[float]) -> float | None:
    first = unit_vector(first_vector)
    second = unit_vector(second_vector)
    if float(np.linalg.norm(first)) <= 0.0 or float(np.linalg.norm(second)) <= 0.0:
        return None
    cosine = float(np.clip(np.dot(first, second), -1.0, 1.0))
    return math.degrees(math.acos(cosine))


def bounds_from_polygon(points: Iterable[tuple[float, float]]) -> tuple[float, float, float, float]:
    pts = list(points)
    if not pts:
        raise ValueError("empty polygon")
    xs = [pt[0] for pt in pts]
    ys = [pt[1] for pt in pts]
    return min(xs), min(ys), max(xs), max(ys)


def clamp_bounds(
    left: float,
    bottom: float,
    right: float,
    top: float,
    ds_bounds,
) -> tuple[float, float, float, float]:
    return (
        max(float(ds_bounds.left), left),
        max(float(ds_bounds.bottom), bottom),
        min(float(ds_bounds.right), right),
        min(float(ds_bounds.top), top),
    )


def valid_mask_from_image(data: np.ndarray, nodata_value: float | int | None = None) -> np.ndarray:
    if data.ndim != 3:
        raise ValueError("expected raster array in (bands, rows, cols) layout")
    if data.shape[0] >= 4:
        alpha = data[3]
        return alpha > 0
    rgb = data[: min(3, data.shape[0])]
    if nodata_value is not None:
        return np.any(rgb != nodata_value, axis=0)
    return np.any(rgb > 0, axis=0)


def grayscale_from_image(data: np.ndarray) -> np.ndarray:
    if data.ndim != 3:
        raise ValueError("expected raster array in (bands, rows, cols) layout")
    rgb = data[: min(3, data.shape[0])].astype(np.float32)
    if rgb.shape[0] == 1:
        return rgb[0]
    if rgb.shape[0] == 2:
        return np.mean(rgb, axis=0)
    return 0.114 * rgb[0] + 0.587 * rgb[1] + 0.299 * rgb[2]


def centroid_from_mask(mask: np.ndarray, transform) -> tuple[float, float] | None:
    rows, cols = np.nonzero(mask)
    if rows.size == 0:
        return None
    xs, ys = transform * (cols + 0.5, rows + 0.5)
    return float(np.mean(xs)), float(np.mean(ys))


def mask_iou(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    intersection = float(np.count_nonzero(mask_a & mask_b))
    union = float(np.count_nonzero(mask_a | mask_b))
    if union <= 0.0:
        return 0.0
    return intersection / union


def overlap_ratio(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    denom = float(np.count_nonzero(mask_b))
    if denom <= 0.0:
        return 0.0
    return float(np.count_nonzero(mask_a & mask_b)) / denom


def ncc(gray_a: np.ndarray, gray_b: np.ndarray, mask: np.ndarray) -> float:
    a = gray_a[mask].astype(np.float64)
    b = gray_b[mask].astype(np.float64)
    if a.size < 2 or b.size < 2:
        return 0.0
    a -= np.mean(a)
    b -= np.mean(b)
    denom = math.sqrt(float(np.dot(a, a)) * float(np.dot(b, b)))
    if denom <= 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def global_ssim(gray_a: np.ndarray, gray_b: np.ndarray, mask: np.ndarray) -> float:
    a = gray_a[mask].astype(np.float64)
    b = gray_b[mask].astype(np.float64)
    if a.size < 2 or b.size < 2:
        return 0.0
    mu_a = float(np.mean(a))
    mu_b = float(np.mean(b))
    sigma_a = float(np.var(a))
    sigma_b = float(np.var(b))
    sigma_ab = float(np.mean((a - mu_a) * (b - mu_b)))
    dynamic_range = 255.0
    c1 = (0.01 * dynamic_range) ** 2
    c2 = (0.03 * dynamic_range) ** 2
    denom = (mu_a * mu_a + mu_b * mu_b + c1) * (sigma_a + sigma_b + c2)
    if denom <= 0.0:
        return 0.0
    return float(((2.0 * mu_a * mu_b + c1) * (2.0 * sigma_ab + c2)) / denom)


def summarize_numeric(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "median": None, "p90": None}
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p90": float(np.percentile(values, 90)),
    }


def summarize_numeric_extended(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "median": None, "rmse": None, "p90": None, "max": None}
    arr = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "rmse": float(np.sqrt(np.mean(np.square(arr)))),
        "p90": float(np.percentile(arr, 90)),
        "max": float(np.max(arr)),
    }

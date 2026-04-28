#!/usr/bin/env python3
"""Shared helpers for the satellite-truth validation subchain.

Purpose:
- keep satellite truth manifest selection, root resolution, and reporting
  conventions consistent across the new satellite-truth-only scripts;
- isolate the satellite-truth experiment from the existing UAV orthophoto
  truth pipeline;
- provide small deterministic helpers without mutating the older formal
  validation chain.

Main inputs:
- query seed CSVs under the active experiment root;
- the coverage-truth table exported from the fixed satellite library.

Main outputs:
- helper return values only; this module does not write evaluation products.

Applicable task constraints:
- satellite truth must come from source GeoTIFF crops, not from fixed tiles
  copied as final truth patches;
- top-k candidate stitching must not be used as truth;
- outputs for the new subchain must live under
  `pose_v1_formal/eval_pose_validation_suite_satellite_truth`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from pose_ortho_truth_utils import (
    DEFAULT_FORMAL_BUNDLE_ROOT,
    ensure_dir,
    load_csv,
    resolve_output_root,
    resolve_runtime_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT_ROOT = PROJECT_ROOT / "new3output" / "nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16"
DEFAULT_BUNDLE_ROOT = DEFAULT_EXPERIMENT_ROOT / "pose_v1_formal"
DEFAULT_SUITE_DIRNAME = "eval_pose_validation_suite_satellite_truth"
DEFAULT_QUERY_SEED_CSV = DEFAULT_BUNDLE_ROOT / "query_truth" / "queries_truth_seed.csv"
DEFAULT_QUERY_TRUTH_TILES_CSV = (
    PROJECT_ROOT
    / "output"
    / "coverage_truth_200_300_500_700_refined_truth_all40_valid06"
    / "query_truth_tiles.csv"
)
DEFAULT_QUERY_TRUTH_CSV = (
    PROJECT_ROOT
    / "output"
    / "coverage_truth_200_300_500_700_refined_truth_all40_valid06"
    / "query_truth.csv"
)


def resolve_satellite_suite_root(bundle_root: Path, output_root: str | Path | None) -> Path:
    """Resolve the satellite-truth suite root from the pose bundle root."""
    return resolve_output_root(bundle_root, output_root, DEFAULT_SUITE_DIRNAME)


def load_rows(path: str | Path) -> list[dict[str, str]]:
    return load_csv(resolve_runtime_path(path))


def choose_truth_row(rows: list[dict[str, str]]) -> dict[str, str]:
    """Pick a canonical truth source row for one query.

    The sort order is intentionally conservative:
    - strict truth rows first;
    - higher coverage first;
    - higher valid pixel ratio first;
    - lower black pixel ratio first;
    - smaller tiles first;
    - stable lexical tie-break on `tile_id`.
    """

    if not rows:
        raise ValueError("no truth rows available for query")

    def key(row: dict[str, str]) -> tuple[float, float, float, float, float, str]:
        strict = 1.0 if row.get("is_strict_truth", "0") in {"1", "true", "True"} else 0.0
        coverage = float(row.get("coverage_ratio", 0.0) or 0.0)
        valid_ratio = float(row.get("valid_pixel_ratio", 0.0) or 0.0)
        black_ratio = float(row.get("black_pixel_ratio", 1.0) or 1.0)
        tile_size = float(row.get("tile_size_m", 0.0) or 0.0)
        tile_id = row.get("tile_id", "")
        return (-strict, -coverage, -valid_ratio, black_ratio, tile_size, tile_id)

    return sorted(rows, key=key)[0]


def group_by_query(rows: Iterable[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        query_id = row["query_id"]
        grouped.setdefault(query_id, []).append(row)
    return grouped


def shorten_flight_id(flight_id: str) -> str:
    parts = flight_id.split("_")
    if len(parts) >= 3:
        return parts[2]
    return flight_id


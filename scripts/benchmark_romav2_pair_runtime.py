#!/usr/bin/env python3
"""Benchmark one RoMa v2 query-tile pair under the current UAV task setup.

Purpose:
- measure the actual runtime of the same RoMa v2 matching path used by the
  Top-20 visualization script;
- keep the benchmark comparable across different coarse baselines by reusing
  the exact `build_model()` and `match_pair()` helpers.

Main inputs:
- one query image path;
- one satellite tile image path;
- RoMa v2 settings and geometry thresholds matching the visualization round.

Main outputs:
- a compact JSON record printed to stdout with timing, image sizes, and match
  statistics for the tested pair.

Applicable task constraints:
- the query is a single arbitrary UAV image;
- the query has no geographic metadata;
- the query is not guaranteed to be orthophoto;
- no external resolution normalization is applied before matching unless it is
  already part of the reused model pipeline.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from PIL import Image

from visualize_romav2_top20_match_points import build_model, match_pair


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-path", required=True)
    parser.add_argument("--tile-path", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--setting", default="satast")
    parser.add_argument("--sample-count", type=int, default=5000)
    parser.add_argument("--ransac-reproj-thresh", type=float, default=4.0)
    parser.add_argument("--min-inliers", type=int, default=20)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.01)
    parser.add_argument("--label", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    query_path = Path(args.query_path)
    tile_path = Path(args.tile_path)
    query_size = Image.open(query_path).size
    tile_size = Image.open(tile_path).size

    model = build_model(args.setting, args.device)
    start = time.perf_counter()
    result = match_pair(
        model=model,
        query_path=query_path,
        tile_path=tile_path,
        sample_count=args.sample_count,
        ransac_reproj_thresh=args.ransac_reproj_thresh,
        min_inliers=args.min_inliers,
        min_inlier_ratio=args.min_inlier_ratio,
    )
    elapsed = time.perf_counter() - start

    payload = {
        "label": args.label,
        "query_path": str(query_path),
        "tile_path": str(tile_path),
        "query_size": query_size,
        "tile_size": tile_size,
        "elapsed_seconds": elapsed,
        "status": result["status"],
        "match_count": int(result["match_count"]),
        "inlier_count": int(result["inlier_count"]),
        "inlier_ratio": float(result["inlier_ratio"]),
        "geom_valid": bool(result["geom_valid"]),
        "romav2_match_score": float(result["romav2_match_score"]),
        "reproj_error_mean": None if result["reproj_error_mean"] is None else float(result["reproj_error_mean"]),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

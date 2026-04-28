#!/usr/bin/env python3
"""Build the formal pose-v1 candidate and truth manifests from official assets.

Purpose:
- convert the official DINOv2 top-20 retrieval output into a pose candidate
  manifest that points at the formal satellite tile library;
- export an aligned truth manifest for offline pose evaluation only.

Main inputs:
- `new1output/query_reselect_2026-03-26_v2/retrieval/retrieval_top20.csv`;
- `output/coverage_truth_200_300_500_700_dinov2_baseline/fixed_satellite_library/tiles.csv`;
- `new1output/query_reselect_2026-03-26_v2/query_truth/query_truth_tiles.csv`.

Main outputs:
- `input/formal_candidate_manifest.csv`
- `input/formal_candidate_manifest.json`
- `input/formal_truth_manifest.csv`
- `input/formal_truth_manifest.json`

Applicable task constraints:
- candidate DOM tiles must come from the formal fixed satellite library
  metadata table `tiles.csv`;
- truth rows are exported for offline evaluation only;
- this script must not inject truth rows into runtime candidate selection.
- newer coverage truth tables may omit the legacy `is_intersection_truth`
  column; rows present in `query_truth_tiles.csv` are then treated as broad
  coverage/intersection truth hits for offline audit fields only.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"
DEFAULT_RETRIEVAL_TOP20 = (
    PROJECT_ROOT
    / "new1output"
    / "query_reselect_2026-03-26_v2"
    / "retrieval"
    / "retrieval_top20.csv"
)
DEFAULT_TILES_CSV = (
    PROJECT_ROOT
    / "output"
    / "coverage_truth_200_300_500_700_dinov2_baseline"
    / "fixed_satellite_library"
    / "tiles.csv"
)
DEFAULT_QUERY_TRUTH_TILES = (
    PROJECT_ROOT
    / "new1output"
    / "query_reselect_2026-03-26_v2"
    / "query_truth"
    / "query_truth_tiles.csv"
)
DEFAULT_QUERY_TRUTH = (
    PROJECT_ROOT
    / "new1output"
    / "query_reselect_2026-03-26_v2"
    / "query_truth"
    / "query_truth.csv"
)

REQUIRED_RETRIEVAL_FIELDS = (
    "query_id",
    "rank",
    "candidate_tile_id",
    "score",
    "candidate_scale_level_m",
    "candidate_center_x",
    "candidate_center_y",
)
REQUIRED_TILE_FIELDS = (
    "tile_id",
    "scale_level_m",
    "tile_size_m",
    "image_path",
    "source_tif",
    "center_x",
    "center_y",
    "min_x",
    "min_y",
    "max_x",
    "max_y",
    "affine",
)
REQUIRED_TRUTH_TILE_FIELDS = (
    "query_id",
    "tile_id",
    "tile_size_m",
    "source_tif",
    "image_path",
    "center_x",
    "center_y",
    "min_x",
    "min_y",
    "max_x",
    "max_y",
    "is_strict_truth",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--retrieval-top20-csv", default=str(DEFAULT_RETRIEVAL_TOP20))
    parser.add_argument("--tiles-csv", default=str(DEFAULT_TILES_CSV))
    parser.add_argument("--query-truth-tiles-csv", default=str(DEFAULT_QUERY_TRUTH_TILES))
    parser.add_argument("--query-truth-csv", default=str(DEFAULT_QUERY_TRUTH))
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def require_columns(rows: list[dict[str, str]], required: tuple[str, ...], label: str) -> None:
    if not rows:
        raise SystemExit(f"{label} is empty")
    missing = [name for name in required if name not in rows[0]]
    if missing:
        raise SystemExit(f"{label} is missing required columns: {', '.join(missing)}")


def parse_affine(raw: str) -> dict[str, float]:
    values = ast.literal_eval(raw)
    if not isinstance(values, list) or len(values) != 6:
        raise SystemExit(f"invalid affine payload: {raw}")
    return {
        "geo_x_col": float(values[0]),
        "geo_x_row": float(values[1]),
        "geo_x0": float(values[2]),
        "geo_y_col": float(values[3]),
        "geo_y_row": float(values[4]),
        "geo_y0": float(values[5]),
    }


def truth_hit_flag(row: dict[str, str]) -> int:
    """Return the broad coverage/intersection truth flag for a truth row."""
    raw = row.get("is_intersection_truth")
    if raw is None or raw == "":
        return 1
    return int(float(raw))


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    input_root = bundle_root / "input"
    logs_root = bundle_root / "logs"
    ensure_dir(input_root)
    ensure_dir(logs_root)

    retrieval_rows = load_csv(Path(args.retrieval_top20_csv))
    tile_rows = load_csv(Path(args.tiles_csv))
    truth_tile_rows = load_csv(Path(args.query_truth_tiles_csv))
    truth_rows = load_csv(Path(args.query_truth_csv))
    require_columns(retrieval_rows, REQUIRED_RETRIEVAL_FIELDS, "retrieval_top20")
    require_columns(tile_rows, REQUIRED_TILE_FIELDS, "tiles.csv")
    require_columns(truth_tile_rows, REQUIRED_TRUTH_TILE_FIELDS, "query_truth_tiles")

    tiles_by_id = {row["tile_id"]: row for row in tile_rows}
    truth_by_pair = {(row["query_id"], row["tile_id"]): row for row in truth_tile_rows}
    truth_summary_by_query = {row["query_id"]: row for row in truth_rows}

    candidate_rows: list[dict[str, object]] = []
    for row in retrieval_rows:
        tile = tiles_by_id.get(row["candidate_tile_id"])
        if tile is None:
            raise SystemExit(
                "retrieval candidate is missing a corresponding tile asset in tiles.csv: "
                f"{row['candidate_tile_id']}"
            )
        pair_truth = truth_by_pair.get((row["query_id"], row["candidate_tile_id"]))
        affine = parse_affine(tile["affine"])
        candidate_rows.append(
            {
                "query_id": row["query_id"],
                "candidate_id": row["candidate_tile_id"],
                "candidate_tile_id": row["candidate_tile_id"],
                "candidate_rank": int(float(row["rank"])),
                "candidate_score": float(row["score"]),
                "candidate_scale_level_m": float(row["candidate_scale_level_m"]),
                "tile_size_m": float(tile["tile_size_m"]),
                "center_x": float(tile["center_x"]),
                "center_y": float(tile["center_y"]),
                "image_path": tile["image_path"],
                "source_tif": tile["source_tif"],
                "crs": "EPSG:32650",
                "min_x": float(tile["min_x"]),
                "min_y": float(tile["min_y"]),
                "max_x": float(tile["max_x"]),
                "max_y": float(tile["max_y"]),
                "geo_x0": affine["geo_x0"],
                "geo_x_col": affine["geo_x_col"],
                "geo_x_row": affine["geo_x_row"],
                "geo_y0": affine["geo_y0"],
                "geo_y_col": affine["geo_y_col"],
                "geo_y_row": affine["geo_y_row"],
                "affine": tile["affine"],
                "is_intersection_truth": truth_hit_flag(pair_truth) if pair_truth else 0,
                "is_strict_truth": int(pair_truth["is_strict_truth"]) if pair_truth else 0,
            }
        )

    truth_manifest_rows: list[dict[str, object]] = []
    for row in truth_tile_rows:
        truth_summary = truth_summary_by_query.get(row["query_id"], {})
        truth_manifest_rows.append(
            {
                "query_id": row["query_id"],
                "candidate_tile_id": row["tile_id"],
                "tile_size_m": float(row["tile_size_m"]),
                "source_tif": row["source_tif"],
                "image_path": row["image_path"],
                "center_x": float(row["center_x"]),
                "center_y": float(row["center_y"]),
                "min_x": float(row["min_x"]),
                "min_y": float(row["min_y"]),
                "max_x": float(row["max_x"]),
                "max_y": float(row["max_y"]),
                "is_intersection_truth": truth_hit_flag(row),
                "is_strict_truth": int(row["is_strict_truth"]),
                "intersection_area_m2": float(row.get("intersection_area_m2", 0.0)),
                "contains_query_center": int(row.get("contains_query_center", 0)),
                "query_crs": truth_summary.get("query_crs", "EPSG:32650"),
            }
        )

    write_csv(input_root / "formal_candidate_manifest.csv", candidate_rows)
    write_csv(input_root / "formal_truth_manifest.csv", truth_manifest_rows)
    write_json(
        input_root / "formal_candidate_manifest.json",
        {
            "bundle_root": str(bundle_root),
            "source_retrieval_top20_csv": str(Path(args.retrieval_top20_csv).resolve()),
            "source_tiles_csv": str(Path(args.tiles_csv).resolve()),
            "candidate_count": len(candidate_rows),
            "candidates": candidate_rows,
            "generated_at_unix": time.time(),
        },
    )
    write_json(
        input_root / "formal_truth_manifest.json",
        {
            "bundle_root": str(bundle_root),
            "source_query_truth_tiles_csv": str(Path(args.query_truth_tiles_csv).resolve()),
            "truth_row_count": len(truth_manifest_rows),
            "truth_rows": truth_manifest_rows,
            "generated_at_unix": time.time(),
        },
    )
    (logs_root / "build_formal_candidate_manifest.log").write_text(
        "\n".join(
            [
                "stage=build_formal_candidate_manifest",
                f"candidate_count={len(candidate_rows)}",
                f"truth_row_count={len(truth_manifest_rows)}",
                f"source_retrieval_top20_csv={Path(args.retrieval_top20_csv).resolve()}",
                f"source_tiles_csv={Path(args.tiles_csv).resolve()}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(input_root / "formal_candidate_manifest.csv")


if __name__ == "__main__":
    main()

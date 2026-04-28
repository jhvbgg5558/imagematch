#!/usr/bin/env python3
"""Assemble the canonical manifest for DOM+DSM+PnP Baseline v1.

Purpose:
- consolidate query, DOM, DSM, and coarse retrieval inputs into one manifest;
- normalize the pose-baseline metadata schema for downstream correspondence,
  DSM sampling, PnP, scoring, and summary scripts.

Main inputs:
- a query manifest CSV with query IDs, image paths, and approximate intrinsics;
- a DOM tile manifest CSV with candidate tile IDs and pixel-to-world affines;
- a DSM source manifest CSV with raster paths and CRS metadata;
- a coarse retrieval top-k CSV with query/candidate/rank/score rows.

Main outputs:
- `manifest/pose_manifest.json`
- `manifest/pose_manifest.csv`
- `manifest/input_summary.json`
- `manifest/run_config.json`

Applicable task constraints:
- query is a single arbitrary UAV image;
- query has no geographic metadata at runtime;
- query is not guaranteed to be orthophoto;
- v1 uses DOM projection coordinates and approximate intrinsics only;
- this script must not silently introduce any new resolution normalization or
  geometry assumption beyond the locked v1 plan.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_baseline_v1"

REQUIRED_QUERY_FIELDS = ("query_id", "image_path")
REQUIRED_DOM_FIELDS = (
    "candidate_id",
    "image_path",
    "crs",
    "geo_x0",
    "geo_x_col",
    "geo_x_row",
    "geo_y0",
    "geo_y_col",
    "geo_y_row",
)
REQUIRED_DSM_FIELDS = ("dsm_id", "raster_path", "crs")
REQUIRED_COARSE_FIELDS = ("query_id", "rank", "score")
OPTIONAL_INTRINSIC_FIELDS = ("fx_px", "fy_px", "cx_px", "cy_px", "k1", "k2", "p1", "p2")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--query-manifest-csv", required=True)
    parser.add_argument("--dom-manifest-csv", required=True)
    parser.add_argument("--dsm-manifest-csv", required=True)
    parser.add_argument("--coarse-topk-csv", required=True)
    parser.add_argument("--manifest-name", default="pose_manifest")
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


def require_columns(rows: list[dict[str, str]], required: tuple[str, ...], label: str) -> None:
    if not rows:
        raise SystemExit(f"{label} is empty")
    missing = [name for name in required if name not in rows[0]]
    if missing:
        raise SystemExit(f"{label} is missing required columns: {', '.join(missing)}")


def to_float(value: str | None, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    return float(value)


def affine_from_row(row: dict[str, str]) -> dict[str, float]:
    return {
        "geo_x0": float(row["geo_x0"]),
        "geo_x_col": float(row["geo_x_col"]),
        "geo_x_row": float(row["geo_x_row"]),
        "geo_y0": float(row["geo_y0"]),
        "geo_y_col": float(row["geo_y_col"]),
        "geo_y_row": float(row["geo_y_row"]),
    }


def summarize_intrinsics(row: dict[str, str]) -> dict[str, object]:
    intrinsics = {name: to_float(row.get(name)) for name in OPTIONAL_INTRINSIC_FIELDS if row.get(name) not in (None, "")}
    status = "ready" if {"fx_px", "fy_px", "cx_px", "cy_px"}.issubset(intrinsics) else "missing"
    return {"status": status, "values": intrinsics}


def canonical_query_row(row: dict[str, str]) -> dict[str, object]:
    canonical = {
        "query_id": row["query_id"],
        "flight_id": row.get("flight_id", ""),
        "image_path": row["image_path"],
        "width_px": row.get("width_px", ""),
        "height_px": row.get("height_px", ""),
        "intrinsics": summarize_intrinsics(row),
    }
    return canonical


def canonical_dom_row(row: dict[str, str]) -> dict[str, object]:
    canonical = {
        "candidate_id": row["candidate_id"],
        "image_path": row["image_path"],
        "crs": row["crs"],
        "affine": affine_from_row(row),
    }
    if row.get("dom_tile_id"):
        canonical["dom_tile_id"] = row["dom_tile_id"]
    return canonical


def canonical_dsm_row(row: dict[str, str]) -> dict[str, object]:
    canonical = {
        "dsm_id": row["dsm_id"],
        "raster_path": row["raster_path"],
        "crs": row["crs"],
        "nodata": row.get("nodata", ""),
    }
    if all(row.get(name) for name in ("geo_x0", "geo_x_col", "geo_x_row", "geo_y0", "geo_y_col", "geo_y_row")):
        canonical["affine"] = affine_from_row(row)
    return canonical


def canonical_coarse_row(row: dict[str, str]) -> dict[str, object]:
    candidate_id = row.get("candidate_id", row.get("candidate_tile_id", ""))
    if candidate_id == "":
        raise SystemExit("coarse top-k row is missing candidate_id/candidate_tile_id")
    return {
        "query_id": row["query_id"],
        "candidate_id": candidate_id,
        "rank": int(float(row["rank"])),
        "score": float(row["score"]),
    }


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    manifest_dir = bundle_root / "manifest"
    logs_dir = bundle_root / "logs"
    ensure_dir(manifest_dir)
    ensure_dir(logs_dir)

    query_rows = load_csv(Path(args.query_manifest_csv))
    dom_rows = load_csv(Path(args.dom_manifest_csv))
    dsm_rows = load_csv(Path(args.dsm_manifest_csv))
    coarse_rows = load_csv(Path(args.coarse_topk_csv))

    require_columns(query_rows, REQUIRED_QUERY_FIELDS, "query manifest")
    require_columns(dom_rows, REQUIRED_DOM_FIELDS, "DOM manifest")
    require_columns(dsm_rows, REQUIRED_DSM_FIELDS, "DSM manifest")
    require_columns(coarse_rows, REQUIRED_COARSE_FIELDS, "coarse top-k CSV")

    canonical_queries = [canonical_query_row(row) for row in query_rows]
    canonical_dom_tiles = [canonical_dom_row(row) for row in dom_rows]
    canonical_dsm_sources = [canonical_dsm_row(row) for row in dsm_rows]
    canonical_coarse = [canonical_coarse_row(row) for row in coarse_rows]

    query_by_id = {row["query_id"]: row for row in canonical_queries}
    dom_by_id = {row["candidate_id"]: row for row in canonical_dom_tiles}
    dsm_by_id = {row["dsm_id"]: row for row in canonical_dsm_sources}

    rows: list[dict[str, object]] = []
    per_query_counts: dict[str, int] = defaultdict(int)
    missing_dom = 0
    missing_query_intrinsics = 0
    for row in canonical_coarse:
        query_id = row["query_id"]
        candidate_id = row["candidate_id"]
        query_item = query_by_id.get(query_id)
        dom_item = dom_by_id.get(candidate_id)
        if query_item is None:
            raise SystemExit(f"Coarse CSV references unknown query_id: {query_id}")
        if query_item["intrinsics"]["status"] != "ready":
            missing_query_intrinsics += 1
        if dom_item is None:
            missing_dom += 1
        per_query_counts[query_id] += 1
        rows.append(
            {
                "query_id": query_id,
                "flight_id": query_item.get("flight_id", ""),
                "query_image_path": query_item["image_path"],
                "query_intrinsics_status": query_item["intrinsics"]["status"],
                "candidate_id": candidate_id,
                "candidate_rank": row["rank"],
                "candidate_score": f"{row['score']:.6f}",
                "candidate_image_path": dom_item["image_path"] if dom_item else "",
                "dom_crs": dom_item["crs"] if dom_item else "",
                "dsm_source_count": len(canonical_dsm_sources),
            }
        )

    payload = {
        "task_name": "pose_baseline_v1",
        "bundle_root": str(bundle_root),
        "generated_at_unix": time.time(),
        "query_manifest_csv": str(Path(args.query_manifest_csv).resolve()),
        "dom_manifest_csv": str(Path(args.dom_manifest_csv).resolve()),
        "dsm_manifest_csv": str(Path(args.dsm_manifest_csv).resolve()),
        "coarse_topk_csv": str(Path(args.coarse_topk_csv).resolve()),
        "defaults": {
            "world_coordinate_system": "dom_projection_crs",
            "intrinsics_model": "approx_intrinsics_v1",
            "pnp_mode": "solvePnPRansac_plus_refinement",
            "stability_window": "3x3",
        },
        "queries": canonical_queries,
        "dom_tiles": canonical_dom_tiles,
        "dsm_sources": canonical_dsm_sources,
        "coarse_candidates": canonical_coarse,
        "statistics": {
            "query_count": len(canonical_queries),
            "dom_tile_count": len(canonical_dom_tiles),
            "dsm_source_count": len(canonical_dsm_sources),
            "coarse_pair_count": len(canonical_coarse),
            "coarse_pairs_per_query_max": max(per_query_counts.values()) if per_query_counts else 0,
            "coarse_pairs_per_query_min": min(per_query_counts.values()) if per_query_counts else 0,
            "queries_missing_intrinsics": missing_query_intrinsics,
            "coarse_rows_with_missing_dom": missing_dom,
        },
    }

    write_json(manifest_dir / f"{args.manifest_name}.json", payload)
    write_csv(manifest_dir / f"{args.manifest_name}.csv", rows)
    write_json(
        manifest_dir / "input_summary.json",
        {
            "query_count": len(canonical_queries),
            "dom_tile_count": len(canonical_dom_tiles),
            "dsm_source_count": len(canonical_dsm_sources),
            "coarse_pair_count": len(canonical_coarse),
            "queries_missing_intrinsics": missing_query_intrinsics,
            "coarse_rows_with_missing_dom": missing_dom,
        },
    )
    write_json(
        manifest_dir / "run_config.json",
        {
            "bundle_root": str(bundle_root),
            "manifest_name": args.manifest_name,
            "inputs": {
                "query_manifest_csv": str(Path(args.query_manifest_csv).resolve()),
                "dom_manifest_csv": str(Path(args.dom_manifest_csv).resolve()),
                "dsm_manifest_csv": str(Path(args.dsm_manifest_csv).resolve()),
                "coarse_topk_csv": str(Path(args.coarse_topk_csv).resolve()),
            },
            "generated_at_unix": time.time(),
        },
    )
    (logs_dir / "build_pose_manifest.log").write_text(
        "\n".join(
            [
                "stage=build_pose_manifest",
                f"bundle_root={bundle_root}",
                f"query_count={len(canonical_queries)}",
                f"dom_tile_count={len(canonical_dom_tiles)}",
                f"dsm_source_count={len(canonical_dsm_sources)}",
                f"coarse_pair_count={len(canonical_coarse)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(manifest_dir / f"{args.manifest_name}.json")


if __name__ == "__main__":
    main()

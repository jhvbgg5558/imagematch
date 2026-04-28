#!/usr/bin/env python3
"""Normalize RoMa matches into canonical pose correspondences for Baseline v1.

Purpose:
- convert RoMa match rows into a canonical correspondence table for the pose
  baseline;
- recover DOM pixel coordinates into DOM projection coordinates using the
  locked per-tile affine transform stored in the manifest.

Main inputs:
- the canonical manifest JSON produced by `build_pose_manifest.py`;
- a RoMa match CSV with query pixel coordinates and DOM pixel coordinates;
- optional columns for match score, inlier flag, and candidate rank.

Main outputs:
- `correspondences/pose_correspondences.csv`
- `correspondences/prepare_summary.json`
- `logs/prepare_pose_correspondences.log`

Applicable task constraints:
- query is a single arbitrary UAV image;
- query has no geographic metadata;
- query is not guaranteed to be orthophoto;
- v1 must not change the locked world coordinate system or invent new
  normalization rules while preparing correspondences.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_baseline_v1"

REQUIRED_MATCH_FIELDS = ("query_id", "candidate_id", "query_x", "query_y", "dom_pixel_x", "dom_pixel_y")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--manifest-json", default=None)
    parser.add_argument("--match-csv", required=True)
    parser.add_argument("--out-dir", default=None)
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


def affine_from_manifest(entry: dict[str, object]) -> dict[str, float]:
    affine = entry.get("affine") or {}
    if not isinstance(affine, dict):
        return {}
    return {
        "geo_x0": float(affine.get("geo_x0", 0.0)),
        "geo_x_col": float(affine.get("geo_x_col", 0.0)),
        "geo_x_row": float(affine.get("geo_x_row", 0.0)),
        "geo_y0": float(affine.get("geo_y0", 0.0)),
        "geo_y_col": float(affine.get("geo_y_col", 0.0)),
        "geo_y_row": float(affine.get("geo_y_row", 0.0)),
    }


def pixel_to_world(x_px: float, y_px: float, affine: dict[str, float]) -> tuple[float, float]:
    x = affine["geo_x0"] + (x_px + 0.5) * affine["geo_x_col"] + (y_px + 0.5) * affine["geo_x_row"]
    y = affine["geo_y0"] + (x_px + 0.5) * affine["geo_y_col"] + (y_px + 0.5) * affine["geo_y_row"]
    return x, y


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    manifest_path = Path(args.manifest_json) if args.manifest_json else bundle_root / "manifest" / "pose_manifest.json"
    out_dir = Path(args.out_dir) if args.out_dir else bundle_root / "correspondences"
    ensure_dir(out_dir)
    logs_dir = bundle_root / "logs"
    ensure_dir(logs_dir)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dom_by_id = {row["candidate_id"]: row for row in manifest.get("dom_tiles", [])}

    match_rows = load_csv(Path(args.match_csv))
    if not match_rows:
        raise SystemExit(f"No match rows found: {args.match_csv}")
    missing = [name for name in REQUIRED_MATCH_FIELDS if name not in match_rows[0]]
    if missing:
        raise SystemExit(f"match CSV is missing required columns: {', '.join(missing)}")

    output_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    for index, row in enumerate(match_rows):
        candidate_id = row["candidate_id"]
        dom_entry = dom_by_id.get(candidate_id)
        if dom_entry is None:
            status = "missing_dom_metadata"
            dom_world_x = ""
            dom_world_y = ""
        else:
            affine = affine_from_manifest(dom_entry)
            if not affine:
                status = "missing_dom_affine"
                dom_world_x = ""
                dom_world_y = ""
            else:
                try:
                    dom_world_x, dom_world_y = pixel_to_world(float(row["dom_pixel_x"]), float(row["dom_pixel_y"]), affine)
                    status = "ok"
                except Exception:
                    dom_world_x = ""
                    dom_world_y = ""
                    status = "invalid_coordinate_transform"

        is_inlier = row.get("is_inlier", "")
        if is_inlier == "":
            is_inlier = "1"
        output_row = {
            "row_id": row.get("row_id", str(index)),
            "query_id": row["query_id"],
            "candidate_id": candidate_id,
            "candidate_rank": row.get("candidate_rank", ""),
            "query_x": row["query_x"],
            "query_y": row["query_y"],
            "dom_pixel_x": row["dom_pixel_x"],
            "dom_pixel_y": row["dom_pixel_y"],
            "dom_world_x": f"{dom_world_x:.6f}" if dom_world_x != "" else "",
            "dom_world_y": f"{dom_world_y:.6f}" if dom_world_y != "" else "",
            "match_score": row.get("match_score", row.get("score", "")),
            "is_inlier": is_inlier,
            "match_status": status,
            "dom_crs": dom_entry.get("crs", "") if dom_entry else "",
        }
        if row.get("query_flight_id"):
            output_row["query_flight_id"] = row["query_flight_id"]
        if row.get("match_id"):
            output_row["match_id"] = row["match_id"]
        output_rows.append(output_row)
        status_counts[status] += 1

    write_csv(out_dir / "pose_correspondences.csv", output_rows)
    write_json(
        out_dir / "prepare_summary.json",
        {
            "bundle_root": str(bundle_root),
            "manifest_json": str(manifest_path.resolve()),
            "match_csv": str(Path(args.match_csv).resolve()),
            "row_count": len(output_rows),
            "status_counts": dict(status_counts),
            "generated_at_unix": time.time(),
        },
    )
    (logs_dir / "prepare_pose_correspondences.log").write_text(
        "\n".join(
            [
                "stage=prepare_pose_correspondences",
                f"bundle_root={bundle_root}",
                f"row_count={len(output_rows)}",
                f"status_counts={dict(status_counts)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(out_dir / "pose_correspondences.csv")


if __name__ == "__main__":
    main()

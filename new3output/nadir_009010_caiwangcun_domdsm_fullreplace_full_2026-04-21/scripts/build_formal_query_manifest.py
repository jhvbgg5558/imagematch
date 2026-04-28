#!/usr/bin/env python3
"""Build the formal pose-v1 query manifest from sanitized query inputs.

Purpose:
- convert the official `query_inputs/query_manifest.csv` into a pose-specific
  query manifest under `new2output/pose_v1_formal/input/`;
- keep runtime inputs restricted to sanitized UAV query images while deriving
  approximate intrinsics from per-flight camera metadata.

Main inputs:
- `new1output/query_reselect_2026-03-26_v2/query_inputs/query_manifest.csv`;
- `new1output/query_reselect_2026-03-26_v2/selected_queries/selected_images_summary.csv`.

Main outputs:
- `input/formal_query_manifest.csv`
- `input/formal_query_manifest.json`

Applicable task constraints:
- runtime query images must come from `sanitized_query_path`;
- query truth and original GPS must not enter runtime manifests;
- intrinsics are approximate v1 values derived from flight camera metadata.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from pose_ortho_truth_utils import resolve_runtime_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"
DEFAULT_QUERY_MANIFEST = (
    PROJECT_ROOT
    / "new1output"
    / "query_reselect_2026-03-26_v2"
    / "query_inputs"
    / "query_manifest.csv"
)
DEFAULT_SELECTED_SUMMARY = (
    PROJECT_ROOT
    / "new1output"
    / "query_reselect_2026-03-26_v2"
    / "selected_queries"
    / "selected_images_summary.csv"
)

REQUIRED_FIELDS = (
    "query_id",
    "flight_id",
    "image_name",
    "original_query_path",
    "sanitized_query_path",
    "has_metadata_removed",
    "sanitization_method",
)
REQUIRED_SELECTED_FIELDS = ("flight_id", "image_name", "original_path")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--query-manifest-csv", default=str(DEFAULT_QUERY_MANIFEST))
    parser.add_argument("--selected-summary-csv", default=str(DEFAULT_SELECTED_SUMMARY))
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


def derive_intrinsics(cameras_json: Path) -> dict[str, object]:
    payload = json.loads(cameras_json.read_text(encoding="utf-8"))
    if not payload:
        raise SystemExit(f"camera payload is empty: {cameras_json}")
    model_name, camera = next(iter(payload.items()))
    width = float(camera["width"])
    height = float(camera["height"])
    scale = max(width, height)
    return {
        "intrinsics_model": model_name,
        "width_px": int(width),
        "height_px": int(height),
        "fx_px": float(camera["focal_x"]) * scale,
        "fy_px": float(camera["focal_y"]) * scale,
        "cx_px": width / 2.0 + float(camera.get("c_x", 0.0)) * scale,
        "cy_px": height / 2.0 + float(camera.get("c_y", 0.0)) * scale,
        "k1": float(camera.get("k1", 0.0)),
        "k2": float(camera.get("k2", 0.0)),
        "p1": float(camera.get("p1", 0.0)),
        "p2": float(camera.get("p2", 0.0)),
    }


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    input_root = bundle_root / "input"
    logs_root = bundle_root / "logs"
    ensure_dir(input_root)
    ensure_dir(logs_root)

    query_rows = load_csv(Path(args.query_manifest_csv))
    selected_rows = load_csv(Path(args.selected_summary_csv))
    require_columns(query_rows, REQUIRED_FIELDS, "query input manifest")
    require_columns(selected_rows, REQUIRED_SELECTED_FIELDS, "selected query summary")
    selected_by_pair = {
        (row["flight_id"], row["image_name"]): row for row in selected_rows
    }

    output_rows: list[dict[str, object]] = []
    manifest_payload_rows: list[dict[str, object]] = []
    for row in query_rows:
        key = (row["flight_id"], row["image_name"])
        selected = selected_by_pair.get(key)
        if selected is None:
            raise SystemExit(f"selected summary row not found for {key}")
        raw_image_path = resolve_runtime_path(selected["original_path"])
        cameras_json = raw_image_path.parent / "cameras.json"
        if not cameras_json.exists():
            raise SystemExit(f"cameras.json not found for query pair {key}: {cameras_json}")
        intr = derive_intrinsics(cameras_json)
        output_row = {
            "query_id": row["query_id"],
            "flight_id": row["flight_id"],
            "image_name": row["image_name"],
            "image_path": str(resolve_runtime_path(row["sanitized_query_path"])).replace("\\", "/"),
            "width_px": intr["width_px"],
            "height_px": intr["height_px"],
            "fx_px": f"{intr['fx_px']:.6f}",
            "fy_px": f"{intr['fy_px']:.6f}",
            "cx_px": f"{intr['cx_px']:.6f}",
            "cy_px": f"{intr['cy_px']:.6f}",
            "k1": f"{intr['k1']:.12f}",
            "k2": f"{intr['k2']:.12f}",
            "p1": f"{intr['p1']:.12f}",
            "p2": f"{intr['p2']:.12f}",
            "intrinsics_source": str(cameras_json).replace("\\", "/"),
            "intrinsics_model": intr["intrinsics_model"],
            "original_query_path": str(resolve_runtime_path(row["original_query_path"])).replace("\\", "/"),
            "selected_original_path": str(resolve_runtime_path(selected["original_path"])).replace("\\", "/"),
            "has_metadata_removed": row["has_metadata_removed"],
            "sanitization_method": row["sanitization_method"],
        }
        output_rows.append(output_row)
        manifest_payload_rows.append(
            {
                "query_id": output_row["query_id"],
                "flight_id": row["flight_id"],
                "image_name": output_row["image_name"],
                "image_path": output_row["image_path"],
                "width_px": intr["width_px"],
                "height_px": intr["height_px"],
                "intrinsics": {
                    "status": "ready",
                    "values": {
                        "fx_px": intr["fx_px"],
                        "fy_px": intr["fy_px"],
                        "cx_px": intr["cx_px"],
                        "cy_px": intr["cy_px"],
                        "k1": intr["k1"],
                        "k2": intr["k2"],
                        "p1": intr["p1"],
                        "p2": intr["p2"],
                    },
                    "source": str(cameras_json).replace("\\", "/"),
                    "model": intr["intrinsics_model"],
                },
            }
        )

    write_csv(input_root / "formal_query_manifest.csv", output_rows)
    write_json(
        input_root / "formal_query_manifest.json",
        {
            "bundle_root": str(bundle_root),
            "source_query_manifest_csv": str(Path(args.query_manifest_csv).resolve()),
            "source_selected_summary_csv": str(Path(args.selected_summary_csv).resolve()),
            "query_count": len(output_rows),
            "queries": manifest_payload_rows,
            "generated_at_unix": time.time(),
        },
    )
    (logs_root / "build_formal_query_manifest.log").write_text(
        "\n".join(
            [
                "stage=build_formal_query_manifest",
                f"query_count={len(output_rows)}",
                f"source_query_manifest_csv={Path(args.query_manifest_csv).resolve()}",
                f"source_selected_summary_csv={Path(args.selected_summary_csv).resolve()}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(input_root / "formal_query_manifest.csv")


if __name__ == "__main__":
    main()

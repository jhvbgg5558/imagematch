#!/usr/bin/env python3
"""Prepare a strict 200m-vs-200m retrieval experiment from existing assets."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

import faiss
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-tiles-csv", required=True)
    parser.add_argument("--source-features-npz", required=True)
    parser.add_argument("--source-mapping-json", required=True)
    parser.add_argument("--source-stage3-root", required=True)
    parser.add_argument("--source-stage4-root", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def filter_tiles_200m(source_tiles_csv: Path, out_csv: Path) -> dict[str, dict[str, str]]:
    rows = read_csv_rows(source_tiles_csv)
    rows_200 = [row for row in rows if int(float(row["scale_level_m"])) == 200]
    write_csv_rows(out_csv, rows_200, list(rows[0].keys()))
    return {row["tile_id"]: row for row in rows_200}


def build_200m_feature_assets(
    source_npz: Path,
    source_mapping_json: Path,
    tile_ids_200m: set[str],
    out_npz: Path,
    out_index: Path,
    out_mapping_json: Path,
) -> None:
    data = np.load(source_npz, allow_pickle=True)
    ids = data["ids"].astype(str)
    features = data["features"].astype("float32")

    keep_idx = [i for i, sample_id in enumerate(ids.tolist()) if str(sample_id) in tile_ids_200m]
    if not keep_idx:
        raise SystemExit("No 200m satellite features found.")

    ids_200 = ids[keep_idx]
    features_200 = features[keep_idx]
    out_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_npz, ids=ids_200, features=features_200)

    index = faiss.IndexFlatIP(features_200.shape[1])
    index.add(features_200)
    out_index.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(out_index))

    source_mapping = json.loads(source_mapping_json.read_text(encoding="utf-8"))
    items_by_id = {item["id"]: item for item in source_mapping["items"]}
    mapping_items = []
    for idx, sample_id in enumerate(ids_200.tolist()):
        sample_id = str(sample_id)
        item = items_by_id[sample_id]
        mapping_items.append({"faiss_row": idx, "id": sample_id, "metadata": item["metadata"]})

    out_mapping_json.write_text(
        json.dumps(
            {
                "index_type": source_mapping.get("index_type", "ip"),
                "dimension": int(features_200.shape[1]),
                "count": int(features_200.shape[0]),
                "missing_metadata": 0,
                "items": mapping_items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def rewrite_queries_to_200m_truth(
    source_stage3_root: Path,
    source_stage4_root: Path,
    out_stage3_root: Path,
    out_stage4_root: Path,
    tile_ids_200m: set[str],
) -> dict[str, int]:
    copied = {}
    for flight_dir in sorted(source_stage3_root.iterdir()):
        if not flight_dir.is_dir():
            continue
        queries_csv = flight_dir / "queries.csv"
        rows = read_csv_rows(queries_csv)
        out_rows = []
        out_flight_dir = out_stage3_root / flight_dir.name
        out_flight_dir.mkdir(parents=True, exist_ok=True)

        for row in rows:
            truth_ids = [x for x in row.get("truth_tile_ids", "").split("|") if x]
            truth_200 = [x for x in truth_ids if x in tile_ids_200m]
            if not truth_200:
                # Strict center-in-200m-tile experiment keeps only queries with 200m positive.
                continue
            src_img = Path(row["image_path"])
            dst_img = out_flight_dir / src_img.name
            shutil.copy2(src_img, dst_img)
            row = row.copy()
            row["image_path"] = str(dst_img)
            row["truth_tile_ids"] = "|".join(truth_200)
            out_rows.append(row)

        if not out_rows:
            continue

        write_csv_rows(out_flight_dir / "queries.csv", out_rows, list(out_rows[0].keys()))
        copied[flight_dir.name] = len(out_rows)

        # Reuse extracted DINO features because image content is unchanged.
        src_stage4 = source_stage4_root / flight_dir.name
        dst_stage4 = out_stage4_root / flight_dir.name
        dst_stage4.mkdir(parents=True, exist_ok=True)
        for name in ["query_features.npz", "query_feature_status.csv"]:
            src = src_stage4 / name
            if src.exists():
                shutil.copy2(src, dst_stage4 / name)

    return copied


def write_readme(out_root: Path, copied: dict[str, int]) -> None:
    lines = [
        "# Strict 200m Same-Scale Retrieval Experiment",
        "",
        "This experiment enforces a single evaluation protocol:",
        "",
        "- Query blocks: drone orthophoto patches with 200m ground coverage.",
        "- Satellite retrieval library: only 200m satellite tiles.",
        "- Input resolution: all patches and tiles remain resized to the unified network input size already used by the project.",
        "- Truth definition: a query is positive only if its center falls inside a 200m satellite tile.",
        "",
        "Purpose:",
        "",
        "To verify whether cross-view coarse retrieval can localize the drone image near the correct geographic area using only remote-sensing orthophotos, without relying on mixed satellite scales.",
        "",
        "Directory layout:",
        "",
        "- `stage1/tiles_200m.csv`: 200m-only satellite metadata.",
        "- `stage2/`: 200m-only DINOv2 feature subset, FAISS index, and mapping.",
        "- `stage3/<flight>/`: strict 200m query metadata and copied query PNGs.",
        "- `stage4/<flight>/`: reused query features plus strict retrieval outputs.",
        "- `stage7/<flight>/`: strict analysis outputs.",
        "",
        "Query counts kept after applying 200m-center truth:",
    ]
    for flight, count in copied.items():
        lines.append(f"- `{flight}`: {count}")
    (out_root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_root)
    stage1_dir = out_root / "stage1"
    stage2_dir = out_root / "stage2"
    stage3_dir = out_root / "stage3"
    stage4_dir = out_root / "stage4"
    stage7_dir = out_root / "stage7"
    for p in [stage1_dir, stage2_dir, stage3_dir, stage4_dir, stage7_dir]:
        p.mkdir(parents=True, exist_ok=True)

    tiles_200 = filter_tiles_200m(Path(args.source_tiles_csv), stage1_dir / "tiles_200m.csv")
    build_200m_feature_assets(
        source_npz=Path(args.source_features_npz),
        source_mapping_json=Path(args.source_mapping_json),
        tile_ids_200m=set(tiles_200.keys()),
        out_npz=stage2_dir / "satellite_dinov2_features_200m.npz",
        out_index=stage2_dir / "satellite_tiles_200m_ip.index",
        out_mapping_json=stage2_dir / "satellite_tiles_200m_mapping.json",
    )
    copied = rewrite_queries_to_200m_truth(
        source_stage3_root=Path(args.source_stage3_root),
        source_stage4_root=Path(args.source_stage4_root),
        out_stage3_root=stage3_dir,
        out_stage4_root=stage4_dir,
        tile_ids_200m=set(tiles_200.keys()),
    )

    manifest = {
        "experiment_name": "validation_200m_same_scale",
        "query_scale_m": 200,
        "satellite_scale_m": 200,
        "truth_rule": "query center falls inside 200m satellite tile",
        "top_k": args.top_k,
        "flight_query_counts": copied,
    }
    (out_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_readme(out_root, copied)
    print(f"Prepared strict same-scale experiment at {out_root}")


if __name__ == "__main__":
    main()

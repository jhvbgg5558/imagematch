#!/usr/bin/env python3
"""Export RoMa v2 reranked Top-K rows as formal pose retrieval input.

Purpose:
- convert `romav2_rerank/stage7/*/reranked_top20.csv` outputs into the
  `retrieval_top20.csv` schema consumed by `build_formal_candidate_manifest.py`;
- lock the pose candidate score to RoMa/DINOv2 rerank `fused_score`;
- preserve query/candidate/rank fields without introducing truth labels into
  runtime pose candidate selection.

Main inputs:
- one or more per-flight `reranked_top20.csv` files under a stage7 root.

Main outputs:
- `retrieval/retrieval_top20.csv`;
- `retrieval/retrieval_top20_export_summary.json`.

Applicable task constraints:
- `score` is always copied from `fused_score`; missing or non-numeric values are
  hard failures;
- output remains candidate-only and does not use `is_intersection_truth_hit`.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


REQUIRED_FIELDS = (
    "query_id",
    "rank",
    "candidate_tile_id",
    "candidate_scale_level_m",
    "candidate_center_x",
    "candidate_center_y",
    "fused_score",
)
OUTPUT_FIELDS = (
    "query_id",
    "rank",
    "candidate_tile_id",
    "score",
    "candidate_scale_level_m",
    "candidate_center_x",
    "candidate_center_y",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage7-root", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--top-k", type=int, default=20)
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def require_fields(rows: list[dict[str, str]], path: Path) -> None:
    if not rows:
        raise SystemExit(f"empty reranked csv: {path}")
    missing = [name for name in REQUIRED_FIELDS if name not in rows[0]]
    if missing:
        raise SystemExit(f"{path} missing required fields: {', '.join(missing)}")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise SystemExit(f"no rows to write: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(OUTPUT_FIELDS))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    stage7_root = Path(args.stage7_root)
    out_csv = Path(args.out_csv)
    files = sorted(stage7_root.glob("*/reranked_top20.csv"))
    if not files:
        raise SystemExit(f"no reranked_top20.csv files found under {stage7_root}")

    out_rows: list[dict[str, str]] = []
    source_files: list[str] = []
    for path in files:
        rows = load_csv(path)
        require_fields(rows, path)
        source_files.append(str(path))
        for row in rows:
            rank = int(row["rank"])
            if rank > args.top_k:
                continue
            fused_score = float(row["fused_score"])
            out_rows.append(
                {
                    "query_id": row["query_id"],
                    "rank": str(rank),
                    "candidate_tile_id": row["candidate_tile_id"],
                    "score": f"{fused_score:.12g}",
                    "candidate_scale_level_m": row["candidate_scale_level_m"],
                    "candidate_center_x": row["candidate_center_x"],
                    "candidate_center_y": row["candidate_center_y"],
                }
            )

    out_rows.sort(key=lambda row: (row["query_id"], int(row["rank"])))
    query_counts = Counter(row["query_id"] for row in out_rows)
    bad_counts = {qid: count for qid, count in query_counts.items() if count != args.top_k}
    if bad_counts:
        raise SystemExit(f"queries with row count != top_k={args.top_k}: {bad_counts}")

    write_csv(out_csv, out_rows)
    write_json(
        out_csv.with_name("retrieval_top20_export_summary.json"),
        {
            "stage7_root": str(stage7_root),
            "out_csv": str(out_csv),
            "top_k": args.top_k,
            "source_files": source_files,
            "query_count": len(query_counts),
            "row_count": len(out_rows),
            "score_source": "fused_score",
        },
    )
    print(out_csv)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run stage3-4-7 validation for multiple drone orthophotos."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-flight validation round.")
    parser.add_argument("--ortho-tifs", nargs="+", required=True, help="Drone orthophoto TIFF paths.")
    parser.add_argument("--stage1-tiles-csv", required=True)
    parser.add_argument("--faiss-index", required=True)
    parser.add_argument("--mapping-json", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--scales", nargs="+", type=float, default=[120.0, 200.0])
    parser.add_argument("--count-per-scale", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--max-invalid-ratio", type=float, default=0.3)
    parser.add_argument("--min-gradient-mean", type=float, default=0.0)
    parser.add_argument("--min-texture-std", type=float, default=0.0)
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def flight_id_from_path(path: Path) -> str:
    parts = path.parts
    for part in parts:
        if part.startswith("DJI_"):
            return part
    return path.stem


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    scripts_dir = Path(__file__).resolve().parent
    py = sys.executable

    aggregate = []
    for ortho in [Path(p) for p in args.ortho_tifs]:
        flight_id = flight_id_from_path(ortho)
        stage3_dir = out_root / "stage3" / flight_id
        stage4_dir = out_root / "stage4" / flight_id
        stage7_dir = out_root / "stage7" / flight_id
        stage3_dir.mkdir(parents=True, exist_ok=True)
        stage4_dir.mkdir(parents=True, exist_ok=True)
        stage7_dir.mkdir(parents=True, exist_ok=True)

        query_csv = stage3_dir / "queries.csv"
        query_npz = stage4_dir / "query_features.npz"
        query_status = stage4_dir / "query_feature_status.csv"
        retrieval_csv = stage4_dir / f"retrieval_top{args.top_k}.csv"
        retrieval_summary = stage4_dir / f"retrieval_top{args.top_k}.json"
        analysis_json = stage7_dir / "analysis.json"
        analysis_md = stage7_dir / "analysis.md"

        cmd = [
            py,
            str(scripts_dir / "select_query_blocks.py"),
            "--ortho-tif",
            str(ortho),
            "--stage1-tiles-csv",
            args.stage1_tiles_csv,
            "--out-dir",
            str(stage3_dir),
            "--metadata-csv",
            str(query_csv),
            "--scales",
            *[str(int(s)) if float(s).is_integer() else str(s) for s in args.scales],
            "--count-per-scale",
            str(args.count_per_scale),
            "--max-invalid-ratio",
            str(args.max_invalid_ratio),
            "--min-gradient-mean",
            str(args.min_gradient_mean),
            "--min-texture-std",
            str(args.min_texture_std),
            "--resize",
            "512",
        ]
        run(cmd)

        cmd = [
            py,
            str(scripts_dir / "extract_dino_features.py"),
            "--input-csv",
            str(query_csv),
            "--id-column",
            "query_id",
            "--image-column",
            "image_path",
            "--output-npz",
            str(query_npz),
            "--output-csv",
            str(query_status),
            "--batch-size",
            "10",
            "--device",
            args.device,
        ]
        if args.local_files_only:
            cmd.append("--local-files-only")
        run(cmd)

        cmd = [
            py,
            str(scripts_dir / "query_faiss_index.py"),
            "--query-features-npz",
            str(query_npz),
            "--query-metadata-csv",
            str(query_csv),
            "--faiss-index",
            args.faiss_index,
            "--mapping-json",
            args.mapping_json,
            "--query-id-column",
            "query_id",
            "--top-k",
            str(args.top_k),
            "--output-csv",
            str(retrieval_csv),
            "--summary-json",
            str(retrieval_summary),
        ]
        run(cmd)

        cmd = [
            py,
            str(scripts_dir / "analyze_retrieval_results.py"),
            "--query-metadata-csv",
            str(query_csv),
            "--retrieval-summary-json",
            str(retrieval_summary),
            "--output-json",
            str(analysis_json),
            "--output-md",
            str(analysis_md),
        ]
        run(cmd)

        with analysis_json.open("r", encoding="utf-8") as f:
            analysis = json.load(f)
        aggregate.append(
            {
                "flight_id": flight_id,
                "query_count": analysis["overall"]["query_count"],
                "recall@1": analysis["overall"]["recall@1"],
                "recall@5": analysis["overall"]["recall@5"],
                "recall@10": analysis["overall"]["recall@10"],
                "per_scale": analysis["per_scale"],
            }
        )

    agg_json = out_root / "aggregate_summary.json"
    agg_md = out_root / "aggregate_summary.md"
    with agg_json.open("w", encoding="utf-8") as f:
        json.dump({"flights": aggregate}, f, ensure_ascii=False, indent=2)

    lines = ["# Multi-Flight Validation Summary", ""]
    for item in aggregate:
        lines.extend(
            [
                f"## {item['flight_id']}",
                f"- Query count: {item['query_count']}",
                f"- Recall@1: {item['recall@1']:.3f}",
                f"- Recall@5: {item['recall@5']:.3f}",
                f"- Recall@10: {item['recall@10']:.3f}",
            ]
        )
        for scale, stats in item["per_scale"].items():
            lines.append(
                f"- {scale}m: queries={stats['query_count']} "
                f"R@1={stats['recall@1']:.3f} "
                f"R@5={stats['recall@5']:.3f} "
                f"R@10={stats['recall@10']:.3f}"
            )
        lines.append("")
    with agg_md.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Aggregate JSON saved to {agg_json}")
    print(f"Aggregate markdown saved to {agg_md}")


if __name__ == "__main__":
    main()

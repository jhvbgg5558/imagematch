#!/usr/bin/env python3
"""Run fair-query-set comparisons across multiple DINOv2 pooling variants."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare DINOv2 pooling variants on an existing query set.")
    parser.add_argument("--stage1-tiles-csv", required=True)
    parser.add_argument("--stage3-root", required=True, help="Directory containing per-flight queries.csv files.")
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--methods", nargs="+", default=["pooler", "cls", "mean", "gem"])
    parser.add_argument("--model-name", default="facebook/dinov2-base")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--input-size", type=int, default=518)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--gem-p", type=float, default=3.0)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--pooler-index", default="")
    parser.add_argument("--pooler-mapping-json", default="")
    parser.add_argument("--satellite-scale-m", type=float, default=0.0)
    parser.add_argument("--reuse-feature-root", default="")
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_timing_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def maybe_filter_tiles_csv(src_csv: Path, out_root: Path, satellite_scale_m: float) -> Path:
    if satellite_scale_m <= 0:
        return src_csv
    rows = load_rows(src_csv)
    if not rows:
        raise SystemExit(f"No rows loaded from {src_csv}")
    fieldnames = list(rows[0].keys())
    wanted = str(int(satellite_scale_m)) if float(satellite_scale_m).is_integer() else str(satellite_scale_m)
    filtered = [row for row in rows if row.get("scale_level_m") == wanted]
    if not filtered:
        raise SystemExit(f"No tiles matched scale_level_m={wanted} in {src_csv}")
    dst_csv = out_root / f"tiles_scale_{wanted}_only.csv"
    write_rows(dst_csv, filtered, fieldnames)
    print(f"Filtered tiles CSV saved to {dst_csv} count={len(filtered)}")
    return dst_csv


def tile_ids_from_csv(path: Path) -> set[str]:
    return {row["tile_id"] for row in load_rows(path)}


def subset_feature_npz(src_npz: Path, dst_npz: Path, keep_ids: set[str]) -> int:
    data = np.load(src_npz, allow_pickle=True)
    ids = [str(x) for x in data["ids"].tolist()]
    features = data["features"].astype("float32")
    keep_indices = [i for i, sample_id in enumerate(ids) if sample_id in keep_ids]
    if not keep_indices:
        raise SystemExit(f"No features from {src_npz} matched filtered tile IDs.")
    filtered_ids = np.array([ids[i] for i in keep_indices], dtype=object)
    filtered_features = features[keep_indices]
    dst_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dst_npz, ids=filtered_ids, features=filtered_features)
    return len(keep_indices)


def summarize_method(method: str, method_dir: Path, flight_rows: list[dict[str, object]]) -> dict[str, object]:
    total_queries = sum(int(row["query_count"]) for row in flight_rows)
    hit1 = sum(int(row["hit_count@1"]) for row in flight_rows)
    hit5 = sum(int(row["hit_count@5"]) for row in flight_rows)
    hit10 = sum(int(row["hit_count@10"]) for row in flight_rows)
    mrr_sum = sum(float(row["mrr_sum"]) for row in flight_rows)
    top1_errors = [float(v) for row in flight_rows for v in row["top1_errors"]]

    timing_rows = []
    for timing_csv in sorted((method_dir / "timing").glob("*_timing.csv")):
        timing_rows.extend(load_timing_rows(timing_csv))

    feature_vals = [float(row["feature_ms"]) for row in timing_rows]
    retrieval_vals = [float(row["retrieval_ms"]) for row in timing_rows]
    total_vals = [float(row["total_ms"]) for row in timing_rows]

    return {
        "method": method,
        "query_count": total_queries,
        "recall@1": hit1 / total_queries if total_queries else 0.0,
        "recall@5": hit5 / total_queries if total_queries else 0.0,
        "recall@10": hit10 / total_queries if total_queries else 0.0,
        "mrr": mrr_sum / total_queries if total_queries else 0.0,
        "top1_error_m_mean": sum(top1_errors) / len(top1_errors) if top1_errors else None,
        "feature_ms_mean": sum(feature_vals) / len(feature_vals) if feature_vals else None,
        "retrieval_ms_mean": sum(retrieval_vals) / len(retrieval_vals) if retrieval_vals else None,
        "total_ms_mean": sum(total_vals) / len(total_vals) if total_vals else None,
    }


def write_method_aggregate(method_dir: Path, flight_rows: list[dict[str, object]]) -> None:
    aggregate_json = method_dir / "aggregate_summary.json"
    aggregate_md = method_dir / "aggregate_summary.md"
    payload = {
        "flights": [
            {
                "flight_id": row["flight_id"],
                "query_count": row["query_count"],
                "recall@1": row["recall@1"],
                "recall@5": row["recall@5"],
                "recall@10": row["recall@10"],
                "mrr": row["mrr"],
                "top1_error_m_mean": row["top1_error_m_mean"],
            }
            for row in flight_rows
        ]
    }
    with aggregate_json.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    lines = ["# Pooling Aggregate Summary", ""]
    for row in flight_rows:
        lines.extend(
            [
                f"## {row['flight_id']}",
                f"- Query count: {row['query_count']}",
                f"- Recall@1: {row['recall@1']:.3f}",
                f"- Recall@5: {row['recall@5']:.3f}",
                f"- Recall@10: {row['recall@10']:.3f}",
                f"- MRR: {row['mrr']:.3f}",
                f"- Top-1 error mean (m): {row['top1_error_m_mean']:.3f}" if row["top1_error_m_mean"] is not None else "- Top-1 error mean (m): na",
                "",
            ]
        )
    aggregate_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Method aggregate summary saved to {aggregate_json}")


def main() -> None:
    args = parse_args()
    scripts_dir = Path(__file__).resolve().parent
    py = sys.executable
    stage1_tiles_csv = Path(args.stage1_tiles_csv)
    stage3_root = Path(args.stage3_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    stage1_tiles_csv = maybe_filter_tiles_csv(stage1_tiles_csv, out_root, args.satellite_scale_m)
    filtered_tile_ids = tile_ids_from_csv(stage1_tiles_csv)
    reuse_feature_root = Path(args.reuse_feature_root) if args.reuse_feature_root else None

    query_csvs = sorted(stage3_root.glob("*/queries.csv"))
    if not query_csvs:
        raise SystemExit(f"No queries.csv found under {stage3_root}")

    overall_rows: list[dict[str, object]] = []
    per_flight_rows: list[dict[str, object]] = []

    for method in args.methods:
        method_dir = out_root / method
        stage2_dir = method_dir / "stage2"
        stage4_dir = method_dir / "stage4"
        stage7_dir = method_dir / "stage7"
        timing_dir = method_dir / "timing"
        stage2_dir.mkdir(parents=True, exist_ok=True)
        stage4_dir.mkdir(parents=True, exist_ok=True)
        stage7_dir.mkdir(parents=True, exist_ok=True)
        timing_dir.mkdir(parents=True, exist_ok=True)

        satellite_npz = stage2_dir / f"satellite_dinov2_{method}.npz"
        satellite_status = stage2_dir / f"satellite_dinov2_{method}_status.csv"
        faiss_index = stage2_dir / f"satellite_tiles_ip_{method}.index"
        mapping_json = stage2_dir / f"satellite_tiles_ip_{method}_mapping.json"

        reuse_pooler = (
            args.satellite_scale_m <= 0
            and method == "pooler"
            and args.pooler_index
            and args.pooler_mapping_json
        )
        if reuse_pooler:
            faiss_index = Path(args.pooler_index)
            mapping_json = Path(args.pooler_mapping_json)
        else:
            reused = False
            if reuse_feature_root is not None:
                candidates = [reuse_feature_root / method / "stage2" / f"satellite_dinov2_{method}.npz"]
                if method == "pooler":
                    candidates.append(reuse_feature_root.parent.parent / "output" / "stage2" / "satellite_dinov2_features.npz")
                for src_npz in candidates:
                    if src_npz.exists():
                        count = subset_feature_npz(src_npz, satellite_npz, filtered_tile_ids)
                        print(f"Reused satellite features from {src_npz} -> {satellite_npz} count={count}")
                        reused = True
                        break
            if not reused:
                cmd = [
                    py,
                    str(scripts_dir / "extract_dino_features.py"),
                    "--input-csv",
                    str(stage1_tiles_csv),
                    "--id-column",
                    "tile_id",
                    "--image-column",
                    "image_path",
                    "--output-npz",
                    str(satellite_npz),
                    "--output-csv",
                    str(satellite_status),
                    "--model-name",
                    args.model_name,
                    "--batch-size",
                    str(args.batch_size),
                    "--device",
                    args.device,
                    "--input-size",
                    str(args.input_size),
                    "--pooling",
                    method,
                    "--gem-p",
                    str(args.gem_p),
                ]
                if args.local_files_only:
                    cmd.append("--local-files-only")
                run(cmd)

            cmd = [
                py,
                str(scripts_dir / "build_faiss_index.py"),
                "--features-npz",
                str(satellite_npz),
                "--metadata-csv",
                str(stage1_tiles_csv),
                "--id-column",
                "tile_id",
                "--index-type",
                "ip",
                "--output-index",
                str(faiss_index),
                "--output-mapping-json",
                str(mapping_json),
            ]
            run(cmd)

        flight_rows = []
        for query_csv in query_csvs:
            flight_id = query_csv.parent.name
            query_npz = stage4_dir / f"{flight_id}_query_features.npz"
            query_status = stage4_dir / f"{flight_id}_query_feature_status.csv"
            retrieval_csv = stage4_dir / f"{flight_id}_retrieval_top{args.top_k}.csv"
            retrieval_json = stage4_dir / f"{flight_id}_retrieval_top{args.top_k}.json"
            analysis_json = stage7_dir / f"{flight_id}_analysis.json"
            analysis_md = stage7_dir / f"{flight_id}_analysis.md"
            timing_csv = timing_dir / f"{flight_id}_timing.csv"
            timing_json = timing_dir / f"{flight_id}_timing_summary.json"

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
                "--model-name",
                args.model_name,
                "--batch-size",
                str(min(args.batch_size, 10)),
                "--device",
                args.device,
                "--input-size",
                str(args.input_size),
                "--pooling",
                method,
                "--gem-p",
                str(args.gem_p),
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
                str(faiss_index),
                "--mapping-json",
                str(mapping_json),
                "--query-id-column",
                "query_id",
                "--top-k",
                str(args.top_k),
                "--output-csv",
                str(retrieval_csv),
                "--summary-json",
                str(retrieval_json),
            ]
            run(cmd)

            cmd = [
                py,
                str(scripts_dir / "analyze_retrieval_results.py"),
                "--query-metadata-csv",
                str(query_csv),
                "--retrieval-summary-json",
                str(retrieval_json),
                "--output-json",
                str(analysis_json),
                "--output-md",
                str(analysis_md),
            ]
            run(cmd)

            cmd = [
                py,
                str(scripts_dir / "measure_query_timing.py"),
                "--query-csv",
                str(query_csv),
                "--faiss-index",
                str(faiss_index),
                "--model-name",
                args.model_name,
                "--device",
                args.device,
                "--input-size",
                str(args.input_size),
                "--warmup-runs",
                str(args.warmup_runs),
                "--output-csv",
                str(timing_csv),
                "--summary-json",
                str(timing_json),
                "--pooling",
                method,
                "--gem-p",
                str(args.gem_p),
            ]
            if args.local_files_only:
                cmd.append("--local-files-only")
            run(cmd)

            retrieval = load_json(retrieval_json)
            timing = load_json(timing_json)
            top1_errors = [
                float(item["top1_error_m"])
                for item in retrieval["per_query"]
                if item.get("top1_error_m") is not None
            ]
            flight_row = {
                "method": method,
                "flight_id": flight_id,
                "query_count": int(retrieval["query_count"]),
                "hit_count@1": int(retrieval["hit_count@1"]),
                "hit_count@5": int(retrieval["hit_count@5"]),
                "hit_count@10": int(retrieval["hit_count@10"]),
                "recall@1": float(retrieval["recall@1"]),
                "recall@5": float(retrieval["recall@5"]),
                "recall@10": float(retrieval["recall@10"]),
                "mrr": float(retrieval.get("mrr", 0.0)),
                "mrr_sum": float(retrieval.get("mrr", 0.0)) * int(retrieval["query_count"]),
                "top1_error_m_mean": sum(top1_errors) / len(top1_errors) if top1_errors else None,
                "top1_errors": top1_errors,
                "feature_ms_mean": float(timing["feature_timing"]["mean_ms"]),
                "retrieval_ms_mean": float(timing["retrieval_timing"]["mean_ms"]),
                "total_ms_mean": float(timing["total_timing"]["mean_ms"]),
            }
            flight_rows.append(flight_row)
            per_flight_rows.append({k: v for k, v in flight_row.items() if k not in {"mrr_sum", "top1_errors"}})

        overall = summarize_method(method, method_dir, flight_rows)
        overall_rows.append(overall)
        write_method_aggregate(method_dir, flight_rows)

    overall_csv = out_root / "overall_metrics.csv"
    per_flight_csv = out_root / "per_flight_metrics.csv"
    summary_json = out_root / "comparison_summary.json"
    summary_md = out_root / "comparison_summary.md"

    with overall_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "method",
                "query_count",
                "recall@1",
                "recall@5",
                "recall@10",
                "mrr",
                "top1_error_m_mean",
                "feature_ms_mean",
                "retrieval_ms_mean",
                "total_ms_mean",
            ],
        )
        writer.writeheader()
        writer.writerows(overall_rows)

    with per_flight_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "method",
                "flight_id",
                "query_count",
                "recall@1",
                "recall@5",
                "recall@10",
                "mrr",
                "top1_error_m_mean",
                "feature_ms_mean",
                "retrieval_ms_mean",
                "total_ms_mean",
            ],
        )
        writer.writeheader()
        writer.writerows(per_flight_rows)

    payload = {"overall": overall_rows, "per_flight": per_flight_rows}
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines = [
        "# Pooling Comparison Summary",
        "",
        "## Overall",
    ]
    for row in overall_rows:
        lines.append(
            f"- {row['method']}: queries={row['query_count']} "
            f"R@1={row['recall@1']:.3f} "
            f"R@5={row['recall@5']:.3f} "
            f"R@10={row['recall@10']:.3f} "
            f"MRR={row['mrr']:.3f} "
            f"Top1Err={row['top1_error_m_mean'] if row['top1_error_m_mean'] is not None else 'na'} "
            f"FeatMS={row['feature_ms_mean'] if row['feature_ms_mean'] is not None else 'na'} "
            f"RetMS={row['retrieval_ms_mean'] if row['retrieval_ms_mean'] is not None else 'na'} "
            f"TotalMS={row['total_ms_mean'] if row['total_ms_mean'] is not None else 'na'}"
        )
    lines.extend(["", "## Per Flight"])
    for row in per_flight_rows:
        lines.append(
            f"- {row['method']} / {row['flight_id']}: "
            f"R@1={row['recall@1']:.3f} "
            f"R@5={row['recall@5']:.3f} "
            f"R@10={row['recall@10']:.3f} "
            f"MRR={row['mrr']:.3f} "
            f"Top1Err={row['top1_error_m_mean'] if row['top1_error_m_mean'] is not None else 'na'}"
        )
    with summary_md.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Overall CSV saved to {overall_csv}")
    print(f"Per-flight CSV saved to {per_flight_csv}")
    print(f"Summary JSON saved to {summary_json}")
    print(f"Summary markdown saved to {summary_md}")


if __name__ == "__main__":
    main()

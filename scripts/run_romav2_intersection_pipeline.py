#!/usr/bin/env python3
"""Run RoMa v2 reranking pipeline under intersection-truth evaluation with timing."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-result-dir", required=True)
    parser.add_argument("--query-features-npz", required=True)
    parser.add_argument("--query-seed-csv", required=True)
    parser.add_argument("--query-truth-tiles-csv", required=True)
    parser.add_argument("--faiss-index", required=True)
    parser.add_argument("--mapping-json", required=True)
    parser.add_argument("--query-manifest-csv", required=True)
    parser.add_argument("--tiles-csv", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--setting", default="satast")
    parser.add_argument("--sample-count", type=int, default=5000)
    parser.add_argument("--ransac-reproj-thresh", type=float, default=4.0)
    parser.add_argument("--min-inliers", type=int, default=20)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.01)
    parser.add_argument("--promotion-rank-gate", type=int, default=5)
    parser.add_argument("--ranking-mode", choices=["gate_only", "fused", "inlier_count_only"], default="fused")
    parser.add_argument("--global-weight", type=float, default=0.4)
    parser.add_argument("--geom-weight", type=float, default=0.6)
    parser.add_argument("--valid-bonus", type=float, default=0.1)
    parser.add_argument("--promotion-bonus", type=float, default=0.05)
    parser.add_argument("--coarse-model-label", default="DINOv3")
    return parser.parse_args()


def run_timed(cmd: list[str]) -> float:
    print("+", " ".join(cmd))
    start = time.perf_counter()
    subprocess.run(cmd, check=True)
    return time.perf_counter() - start


def write_timing(out_root: Path, rows: list[dict[str, object]]) -> None:
    timing_dir = out_root / "timing"
    timing_dir.mkdir(parents=True, exist_ok=True)
    (timing_dir / "timing_summary.json").write_text(json.dumps({"stages": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    with (timing_dir / "timing_summary.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["stage", "elapsed_seconds"])
        writer.writeheader()
        writer.writerows([{"stage": row["stage"], "elapsed_seconds": f"{float(row['elapsed_seconds']):.6f}"} for row in rows])


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    coarse_dir = out_root / "coarse"
    input_round_dir = out_root / "input_round"
    reports_dir = out_root / "reports"

    stages: list[dict[str, object]] = []

    coarse_csv = coarse_dir / f"retrieval_top{args.top_k}.csv"
    coarse_summary = coarse_dir / f"summary_top{args.top_k}.json"
    coarse_curve = coarse_dir / f"topk_truth_curve_top{args.top_k}.csv"
    elapsed = run_timed(
        [
            args.python_bin,
            str(script_dir / "evaluate_retrieval_against_intersection_truth.py"),
            "--query-features-npz", args.query_features_npz,
            "--query-seed-csv", args.query_seed_csv,
            "--query-truth-tiles-csv", args.query_truth_tiles_csv,
            "--faiss-index", args.faiss_index,
            "--mapping-json", args.mapping_json,
            "--top-k", str(args.top_k),
            "--output-csv", str(coarse_csv),
            "--summary-json", str(coarse_summary),
            "--curve-csv", str(coarse_curve),
        ]
    )
    stages.append({"stage": "coarse_topk_export", "elapsed_seconds": elapsed})

    elapsed = run_timed(
        [
            args.python_bin,
            str(script_dir / "prepare_romav2_intersection_inputs.py"),
            "--query-manifest-csv", args.query_manifest_csv,
            "--query-seed-csv", args.query_seed_csv,
            "--query-truth-tiles-csv", args.query_truth_tiles_csv,
            "--coarse-retrieval-csv", str(coarse_csv),
            "--top-k", str(args.top_k),
            "--out-root", str(input_round_dir),
        ]
    )
    stages.append({"stage": "input_preparation", "elapsed_seconds": elapsed})

    rerank_timing_json = out_root / "timing" / "romav2_rerank_internal.json"
    elapsed = run_timed(
        [
            args.python_bin,
            str(script_dir / "run_romav2_rerank_intersection_round.py"),
            "--input-round-root", str(input_round_dir),
            "--tiles-csv", args.tiles_csv,
            "--out-root", str(out_root),
            "--top-k", str(args.top_k),
            "--python-bin", args.python_bin,
            "--device", args.device,
            "--setting", args.setting,
            "--sample-count", str(args.sample_count),
            "--ransac-reproj-thresh", str(args.ransac_reproj_thresh),
            "--min-inliers", str(args.min_inliers),
            "--min-inlier-ratio", str(args.min_inlier_ratio),
            "--promotion-rank-gate", str(args.promotion_rank_gate),
            "--ranking-mode", args.ranking_mode,
            "--global-weight", str(args.global_weight),
            "--geom-weight", str(args.geom_weight),
            "--valid-bonus", str(args.valid_bonus),
            "--promotion-bonus", str(args.promotion_bonus),
            "--timing-json", str(rerank_timing_json),
        ]
    )
    stages.append({"stage": "romav2_rerank", "elapsed_seconds": elapsed})

    elapsed = run_timed(
        [
            args.python_bin,
            str(script_dir / "summarize_romav2_intersection_results.py"),
            "--baseline-result-dir", args.baseline_result_dir,
            "--romav2-result-dir", str(out_root),
        ]
    )
    stages.append({"stage": "summary_aggregation", "elapsed_seconds": elapsed})

    elapsed = run_timed(
        [
            args.python_bin,
            str(script_dir / "visualize_romav2_intersection_results.py"),
            "--baseline-result-dir", args.baseline_result_dir,
            "--romav2-result-dir", str(out_root),
            "--tiles-csv", args.tiles_csv,
            "--query-manifest-csv", args.query_manifest_csv,
            "--top-k", "10",
            "--rerank-top-k", str(args.top_k),
        ]
    )
    stages.append({"stage": "visualization", "elapsed_seconds": elapsed})
    # Report generation reads timing_summary.json from the result directory.
    write_timing(out_root, stages)

    report_md = reports_dir / "RoMaV2_intersection_truth_top20_实验结果说明.md"
    report_docx = reports_dir / "RoMaV2_intersection_truth_top20_实验结果说明.docx"
    elapsed = run_timed(
        [
            args.python_bin,
            str(script_dir / "generate_romav2_intersection_report.py"),
            "--result-dir", str(out_root),
            "--out-md", str(report_md),
            "--out-docx", str(report_docx),
            "--coarse-model-label", args.coarse_model_label,
        ]
    )
    stages.append({"stage": "report_generation", "elapsed_seconds": elapsed})

    write_timing(out_root, stages)
    print(out_root)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run the locked DINOv2 coarse + RoMa v2 inlier-count-only round for the current UAV task.

Purpose:
- provide one thin entrypoint for the formal `query v2 + intersection truth`
  round that reuses the existing RoMa v2 intersection pipeline;
- lock the coarse stage to the current DINOv2 assets instead of the older
  DINOv3-based round;
- keep all new outputs inside
  `new2output/romav2_dinov2_inliercount_rerank_2026-04-02`.

Main inputs:
- locked query-v2 DINOv2 features, truth CSVs, FAISS index, and tile library;
- existing generic scripts for intersection retrieval, RoMa v2 reranking,
  reporting, and Top-20 match-point visualization.

Main outputs:
- evaluation assets under `<bundle_root>/eval`;
- Top-20 match-point visualizations under `<bundle_root>/viz_top20_match_points`;
- locked run configuration and command log under `<bundle_root>/plan` and
  `<bundle_root>/logs`.

Applicable task constraints:
- the query is a single arbitrary UAV image;
- the query has no geographic metadata;
- the query is not guaranteed to be orthophoto;
- no external resolution normalization is introduced beyond the model pipeline;
- this wrapper must not write into older formal result directories.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "romav2_dinov2_inliercount_rerank_2026-04-02"

LOCKED_PATHS = {
    "baseline_result_dir": PROJECT_ROOT / "new1output" / "query_reselect_2026-03-26_v2",
    "query_features_npz": PROJECT_ROOT / "new1output" / "query_reselect_2026-03-26_v2" / "query_features" / "query_dinov2_pooler.npz",
    "query_seed_csv": PROJECT_ROOT / "new1output" / "query_reselect_2026-03-26_v2" / "query_truth" / "queries_truth_seed.csv",
    "query_truth_tiles_csv": PROJECT_ROOT / "new1output" / "query_reselect_2026-03-26_v2" / "query_truth" / "query_truth_tiles.csv",
    "faiss_index": PROJECT_ROOT / "output" / "coverage_truth_200_300_500_700_dinov2_baseline" / "faiss" / "satellite_tiles_ip.index",
    "mapping_json": PROJECT_ROOT / "new1output" / "query_reselect_2026-03-26_v2" / "faiss" / "satellite_tiles_ip_mapping.json",
    "query_manifest_csv": PROJECT_ROOT / "new1output" / "query_reselect_2026-03-26_v2" / "query_inputs" / "query_manifest.csv",
    "tiles_csv": PROJECT_ROOT / "output" / "coverage_truth_200_300_500_700_dinov2_baseline" / "fixed_satellite_library" / "tiles.csv",
    "selected_summary_csv": PROJECT_ROOT / "new1output" / "query_reselect_2026-03-26_v2" / "selected_queries" / "selected_images_summary.csv",
    "query_input_root": PROJECT_ROOT / "new1output" / "query_reselect_2026-03-26_v2" / "query_inputs" / "images",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--setting", default="satast")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--sample-count", type=int, default=5000)
    parser.add_argument("--ransac-reproj-thresh", type=float, default=4.0)
    parser.add_argument("--min-inliers", type=int, default=20)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.01)
    parser.add_argument("--promotion-rank-gate", type=int, default=5)
    parser.add_argument("--ranking-mode", choices=["gate_only", "fused", "inlier_count_only"], default="inlier_count_only")
    parser.add_argument("--global-weight", type=float, default=0.4)
    parser.add_argument("--geom-weight", type=float, default=0.6)
    parser.add_argument("--valid-bonus", type=float, default=0.1)
    parser.add_argument("--promotion-bonus", type=float, default=0.05)
    parser.add_argument("--target-long-side", type=int, default=900)
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--skip-viz", action="store_true")
    parser.add_argument("--print-only", action="store_true")
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def command_to_text(cmd: list[str]) -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in cmd)


def append_log(log_path: Path, message: str) -> None:
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def run_command(cmd: list[str], log_path: Path, print_only: bool) -> None:
    text = command_to_text(cmd)
    print(text)
    append_log(log_path, text)
    if print_only:
        return
    subprocess.run(cmd, check=True)


def write_locked_config(config_path: Path, bundle_root: Path, args: argparse.Namespace, eval_root: Path, viz_root: Path) -> None:
    payload = {
        "bundle_root": str(bundle_root),
        "eval_root": str(eval_root),
        "viz_root": str(viz_root),
        "coarse_model_label": "DINOv2",
        "rank_score_name": "inlier_count" if args.ranking_mode == "inlier_count_only" else "fused_score",
        "top_k": args.top_k,
        "device": args.device,
        "setting": args.setting,
        "sample_count": args.sample_count,
        "ransac_reproj_thresh": args.ransac_reproj_thresh,
        "min_inliers": args.min_inliers,
        "min_inlier_ratio": args.min_inlier_ratio,
        "promotion_rank_gate": args.promotion_rank_gate,
        "ranking_mode": args.ranking_mode,
        "global_weight": args.global_weight,
        "geom_weight": args.geom_weight,
        "valid_bonus": args.valid_bonus,
        "promotion_bonus": args.promotion_bonus,
        "target_long_side": args.target_long_side,
        "locked_inputs": {key: str(value) for key, value in LOCKED_PATHS.items()},
        "generated_at_unix": time.time(),
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_eval_command(args: argparse.Namespace, eval_root: Path) -> list[str]:
    script_path = PROJECT_ROOT / "scripts" / "run_romav2_intersection_pipeline.py"
    return [
        args.python_bin,
        str(script_path),
        "--baseline-result-dir", str(LOCKED_PATHS["baseline_result_dir"]),
        "--query-features-npz", str(LOCKED_PATHS["query_features_npz"]),
        "--query-seed-csv", str(LOCKED_PATHS["query_seed_csv"]),
        "--query-truth-tiles-csv", str(LOCKED_PATHS["query_truth_tiles_csv"]),
        "--faiss-index", str(LOCKED_PATHS["faiss_index"]),
        "--mapping-json", str(LOCKED_PATHS["mapping_json"]),
        "--query-manifest-csv", str(LOCKED_PATHS["query_manifest_csv"]),
        "--tiles-csv", str(LOCKED_PATHS["tiles_csv"]),
        "--out-root", str(eval_root),
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
        "--coarse-model-label", "DINOv2",
    ]


def build_viz_command(args: argparse.Namespace, eval_root: Path, viz_root: Path) -> list[str]:
    script_path = PROJECT_ROOT / "scripts" / "visualize_romav2_top20_match_points.py"
    return [
        args.python_bin,
        str(script_path),
        "--romav2-result-dir", str(eval_root),
        "--tiles-csv", str(LOCKED_PATHS["tiles_csv"]),
        "--selected-summary-csv", str(LOCKED_PATHS["selected_summary_csv"]),
        "--query-input-root", str(LOCKED_PATHS["query_input_root"]),
        "--out-root", str(viz_root),
        "--device", args.device,
        "--setting", args.setting,
        "--sample-count", str(args.sample_count),
        "--ransac-reproj-thresh", str(args.ransac_reproj_thresh),
        "--min-inliers", str(args.min_inliers),
        "--min-inlier-ratio", str(args.min_inlier_ratio),
        "--top-k", str(args.top_k),
        "--target-long-side", str(args.target_long_side),
    ]


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    eval_root = bundle_root / "eval"
    viz_root = bundle_root / "viz_top20_match_points"
    plan_root = bundle_root / "plan"
    logs_root = bundle_root / "logs"

    ensure_dir(bundle_root)
    ensure_dir(plan_root)
    ensure_dir(logs_root)
    if not args.skip_eval:
        ensure_dir(eval_root)
    if not args.skip_viz:
        ensure_dir(viz_root)

    missing_inputs = [str(path) for path in LOCKED_PATHS.values() if not path.exists()]
    if missing_inputs:
        raise SystemExit("Missing locked inputs:\n- " + "\n- ".join(missing_inputs))

    config_path = plan_root / "locked_run_config.json"
    command_log = logs_root / "run_commands.log"
    write_locked_config(config_path, bundle_root, args, eval_root, viz_root)

    append_log(command_log, f"# run started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    append_log(command_log, f"# bundle_root={bundle_root}")

    if not args.skip_eval:
        run_command(build_eval_command(args, eval_root), command_log, args.print_only)
    if not args.skip_viz:
        run_command(build_viz_command(args, eval_root, viz_root), command_log, args.print_only)

    print(bundle_root)


if __name__ == "__main__":
    main()

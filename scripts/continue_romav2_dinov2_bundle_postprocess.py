#!/usr/bin/env python3
"""Continue the DINOv2 coarse + RoMa v2 bundle after rerank completion.

Purpose:
- resume the current formal bundle from post-rerank assets that already exist;
- backfill the timing summary needed by the report generator;
- generate the formal report and bundle-level Top-20 match-point visualization
  without rerunning coarse retrieval or RoMa v2 reranking.

Main inputs:
- existing `eval/` outputs under
  `new1output/romav2_dinov2_intersection_2026-04-01/eval`;
- `romav2_rerank_internal.json` if present;
- locked query and tile assets from the current task.

Main outputs:
- `eval/timing/timing_summary.json` and `timing_summary.csv`;
- formal report files under `eval/reports/`;
- Top-20 match-point visualization assets under `viz_top20_match_points/`.

Applicable task constraints:
- the query is a single arbitrary UAV image;
- the query has no geographic metadata;
- the query is not guaranteed to be orthophoto;
- no new resolution normalization is introduced beyond the model pipeline;
- this script must not touch older formal result directories.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new1output" / "romav2_dinov2_intersection_2026-04-01"
DEFAULT_EVAL_ROOT = DEFAULT_BUNDLE_ROOT / "eval"
DEFAULT_VIZ_ROOT = DEFAULT_BUNDLE_ROOT / "viz_top20_match_points"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--eval-root", default=str(DEFAULT_EVAL_ROOT))
    parser.add_argument("--viz-root", default=str(DEFAULT_VIZ_ROOT))
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--setting", default="satast")
    parser.add_argument("--sample-count", type=int, default=5000)
    parser.add_argument("--ransac-reproj-thresh", type=float, default=4.0)
    parser.add_argument("--min-inliers", type=int, default=20)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.01)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--target-long-side", type=int, default=900)
    parser.add_argument("--coarse-model-label", default="DINOv2")
    return parser.parse_args()


def write_timing_summary(eval_root: Path) -> None:
    timing_dir = eval_root / "timing"
    timing_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    internal_path = timing_dir / "romav2_rerank_internal.json"
    if internal_path.exists():
        payload = json.loads(internal_path.read_text(encoding="utf-8"))
        rows.append(
            {
                "stage": "romav2_rerank",
                "elapsed_seconds": float(payload.get("elapsed_seconds", 0.0)),
            }
        )
    (timing_dir / "timing_summary.json").write_text(
        json.dumps({"stages": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (timing_dir / "timing_summary.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stage", "elapsed_seconds"])
        writer.writeheader()
        writer.writerows(rows)


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    eval_root = Path(args.eval_root)
    viz_root = Path(args.viz_root)

    eval_root.mkdir(parents=True, exist_ok=True)
    viz_root.mkdir(parents=True, exist_ok=True)
    write_timing_summary(eval_root)

    run(
        [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "generate_romav2_intersection_report.py"),
            "--result-dir",
            str(eval_root),
            "--out-md",
            str(eval_root / "reports" / "RoMaV2_intersection_truth_top20_实验结果说明.md"),
            "--out-docx",
            str(eval_root / "reports" / "RoMaV2_intersection_truth_top20_实验结果说明.docx"),
            "--coarse-model-label",
            args.coarse_model_label,
        ]
    )

    run(
        [
            args.python_bin,
            str(PROJECT_ROOT / "scripts" / "visualize_romav2_top20_match_points.py"),
            "--romav2-result-dir",
            str(eval_root),
            "--tiles-csv",
            str(PROJECT_ROOT / "output" / "coverage_truth_200_300_500_700_dinov2_baseline" / "fixed_satellite_library" / "tiles.csv"),
            "--selected-summary-csv",
            str(PROJECT_ROOT / "new1output" / "query_reselect_2026-03-26_v2" / "selected_queries" / "selected_images_summary.csv"),
            "--query-input-root",
            str(PROJECT_ROOT / "new1output" / "query_reselect_2026-03-26_v2" / "query_inputs" / "images"),
            "--out-root",
            str(viz_root),
            "--device",
            args.device,
            "--setting",
            args.setting,
            "--sample-count",
            str(args.sample_count),
            "--ransac-reproj-thresh",
            str(args.ransac_reproj_thresh),
            "--min-inliers",
            str(args.min_inliers),
            "--min-inlier-ratio",
            str(args.min_inlier_ratio),
            "--top-k",
            str(args.top_k),
            "--target-long-side",
            str(args.target_long_side),
        ]
    )

    print(bundle_root)


if __name__ == "__main__":
    main()

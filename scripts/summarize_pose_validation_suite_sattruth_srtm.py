#!/usr/bin/env python3
"""Summarize the satellite-truth + SRTM validation suite."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from pose_ortho_truth_utils import ensure_dir, load_json, resolve_output_root, resolve_runtime_path, write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new3output" / "nadir_009010_dinov2_romav2_pose_sattruth_srtm_2026-04-16" / "pose_v1_formal"
DEFAULT_SUITE_DIRNAME = "eval_pose_validation_suite_sattruth_srtm"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--ortho-root", default=None)
    parser.add_argument("--pose-root", default=None)
    parser.add_argument("--tiepoint-root", default=None)
    parser.add_argument("--phase", choices=("gate", "full"), default="full")
    parser.add_argument("--query-id", action="append", default=[])
    return parser.parse_args()


def load_json_if_exists(path: Path) -> dict[str, object]:
    if path.exists():
        return load_json(path)
    return {}


def format_metric(summary: dict[str, object], key: str) -> str:
    payload = summary.get(key, {})
    if not isinstance(payload, dict):
        return "n/a"
    mean = payload.get("mean")
    median = payload.get("median")
    p90 = payload.get("p90")
    if mean is None and median is None and p90 is None:
        return "n/a"
    return f"mean={mean}, median={median}, p90={p90}"


def format_scalar_metric(summary: dict[str, object], key: str) -> str:
    value = summary.get(key)
    if value is None or value == "":
        return "n/a"
    return str(value)


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    suite_root = resolve_runtime_path(args.output_root) if args.output_root else resolve_output_root(bundle_root, None, DEFAULT_SUITE_DIRNAME)
    ortho_root = resolve_runtime_path(args.ortho_root) if args.ortho_root else suite_root / "ortho_alignment_satellite"
    pose_root = resolve_runtime_path(args.pose_root) if args.pose_root else suite_root / "pose_vs_at"
    tie_root = resolve_runtime_path(args.tiepoint_root) if args.tiepoint_root else suite_root / "tiepoint_ground_error"
    reports_root = suite_root / "reports"
    ensure_dir(reports_root)

    ortho_overall = load_json_if_exists(ortho_root / "overall_ortho_accuracy.json")
    pose_overall = load_json_if_exists(pose_root / "overall_pose_vs_at.json")
    tie_overall = load_json_if_exists(tie_root / "overall_tiepoint_ground_error.json")

    validation_manifest = {
        "bundle_root": str(bundle_root),
        "suite_root": str(suite_root),
        "phase": args.phase,
        "selected_query_ids": args.query_id,
        "ortho_root": str(ortho_root),
        "pose_vs_at_root": str(pose_root),
        "tiepoint_ground_error_root": str(tie_root),
        "outputs": {
            "ortho_overall": str(ortho_root / "overall_ortho_accuracy.json"),
            "pose_overall": str(pose_root / "overall_pose_vs_at.json"),
            "tiepoint_overall": str(tie_root / "overall_tiepoint_ground_error.json"),
        },
        "generated_at_unix": time.time(),
    }
    write_json(suite_root / "validation_manifest.json", validation_manifest)

    report_lines = [
        "# Validation Suite Summary",
        "",
        f"- phase: `{args.phase}`",
        f"- ortho_alignment_satellite: `{ortho_root}`",
        f"- pose_vs_at: `{pose_root}`",
        f"- tiepoint_ground_error: `{tie_root}`",
        "",
        "## Main Metrics",
        f"- phase_corr_error_m: {format_metric(ortho_overall, 'phase_corr_error_m')}",
        f"- center_offset_m: {format_metric(ortho_overall, 'center_offset_m')}",
        f"- ortho_iou: {format_metric(ortho_overall, 'ortho_iou')}",
        f"- ssim: {format_metric(ortho_overall, 'ssim')}",
        f"- horizontal_error_m: {format_metric(pose_overall, 'horizontal_error_m')}",
        f"- view_dir_angle_error_deg: {format_metric(pose_overall, 'view_dir_angle_error_deg')}",
        f"- tiepoint_xy_error_rmse_m: {format_scalar_metric(tie_overall, 'tiepoint_xy_error_rmse_m')}",
        f"- tiepoint_xy_error_p90_m: {format_scalar_metric(tie_overall, 'tiepoint_xy_error_p90_m')}",
        f"- tiepoint_match_count_mean: {format_scalar_metric(tie_overall, 'tiepoint_match_count_mean')}",
        "",
        "## Interpretation",
        "- layer-1 validates predicted orthophotos against satellite truth crops.",
        "- layer-2 compares the best pose against the ODM/AT reference pose.",
        "- layer-3 measures local ground XY consistency with RoMa v2 tie-points.",
        "",
        "## Raw Files",
        f"- `{suite_root / 'validation_manifest.json'}`",
    ]
    (reports_root / "validation_suite_summary.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(suite_root / "validation_manifest.json")


if __name__ == "__main__":
    main()

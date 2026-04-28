#!/usr/bin/env python3
"""Summarize the unified three-layer pose validation suite.

Purpose:
- merge orthophoto-alignment, pose-vs-AT, and tie-point ground-error outputs
  into one suite-level manifest and summary JSON;
- keep the three layers explicitly separated while presenting their main
  metrics side by side;
- emit a compact human-readable report stub under the suite report directory.

Main inputs:
- per-layer summary JSON files under the suite root.

Main outputs:
- `<output_root>/validation_manifest.json`;
- `<output_root>/reports/validation_suite_summary.md`.

Applicable task constraints:
- orthophoto alignment remains the primary validation layer;
- pose-vs-AT and tie-point ground error remain complementary layers;
- suite-level phase/full JSON summaries are written by the orchestration entry
  script so this summarizer only emits the manifest and Markdown report.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from pose_ortho_truth_utils import (
    DEFAULT_FORMAL_BUNDLE_ROOT,
    DEFAULT_VALIDATION_SUITE_DIRNAME,
    ensure_dir,
    load_json,
    resolve_runtime_path,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_FORMAL_BUNDLE_ROOT))
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
    suite_root = resolve_runtime_path(args.output_root) if args.output_root else bundle_root / DEFAULT_VALIDATION_SUITE_DIRNAME
    ortho_root = resolve_runtime_path(args.ortho_root) if args.ortho_root else suite_root / "ortho_alignment"
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
        f"- ortho_alignment: `{ortho_root}`",
        f"- pose_vs_at: `{pose_root}`",
        f"- tiepoint_ground_error: `{tie_root}`",
        "",
        "## Main Metrics",
        f"- phase_corr_error_m: {format_metric(ortho_overall, 'phase_corr_error_m')}",
        f"- horizontal_error_m: {format_metric(pose_overall, 'horizontal_error_m')}",
        f"- view_dir_angle_error_deg: {format_metric(pose_overall, 'view_dir_angle_error_deg')}",
        f"- tiepoint_xy_error_rmse_m: {format_scalar_metric(tie_overall, 'tiepoint_xy_error_rmse_m')}",
        f"- tiepoint_xy_error_p90_m: {format_scalar_metric(tie_overall, 'tiepoint_xy_error_p90_m')}",
        "",
        "## Interpretation",
        "- orthophoto alignment remains the primary validation layer.",
        "- pose_vs_at provides relative camera-parameter deltas to the ODM/AT reference.",
        "- tiepoint ground error measures local object-space XY consistency on truth vs pred orthophotos.",
        "",
        "## Raw Files",
        f"- `{suite_root / 'validation_manifest.json'}`",
    ]
    (reports_root / "validation_suite_summary.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(suite_root / "validation_manifest.json")


if __name__ == "__main__":
    main()

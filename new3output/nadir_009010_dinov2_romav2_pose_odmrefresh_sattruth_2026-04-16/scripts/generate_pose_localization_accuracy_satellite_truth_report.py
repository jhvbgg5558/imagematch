#!/usr/bin/env python3
"""Generate a localized accuracy Word report for the satellite-truth suite.

Purpose:
- provide a second report entrypoint with the same satellite-truth data scope
  but a tighter filename for localization-focused review;
- keep the report content driven by the satellite-truth suite outputs;
- avoid reusing the UAV orthophoto-truth reporting template.

Main inputs:
- satellite-truth suite outputs under `pose_v1_formal/eval_pose_validation_suite_satellite_truth/`.

Main outputs:
- `<suite-root>/reports/pose_localization_accuracy_satellite_truth_report.docx`
"""

from __future__ import annotations

import sys
from pathlib import Path

from generate_pose_validation_suite_satellite_truth_word_report import main as generate_report


def main() -> None:
    if "--out-docx" not in sys.argv:
        # Default to the localization-focused filename when the caller does
        # not specify an explicit output path.
        if "--suite-root" in sys.argv:
            suite_root = Path(sys.argv[sys.argv.index("--suite-root") + 1])
        else:
            suite_root = Path("new3output") / "nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16" / "pose_v1_formal" / "eval_pose_validation_suite_satellite_truth"
        sys.argv.extend(["--out-docx", str(suite_root / "reports" / "pose_localization_accuracy_satellite_truth_report.docx")])
    generate_report()


if __name__ == "__main__":
    main()

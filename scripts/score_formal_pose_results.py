#!/usr/bin/env python3
"""Formal Pose v1 scoring and summary entrypoint.

Purpose:
- provide the stable entrypoint for formal pose result scoring;
- forward to the shared implementation used by the formal summary pipeline.

Main inputs:
- `--bundle-root`
- `--pnp-results-csv`

Main outputs:
- `scores/pose_scores.csv`
- `summary/per_query_best_pose.csv`
- `summary/pose_overall_summary.json`
"""

from __future__ import annotations

from run_pose_v1_formal_scoring_summary import main


if __name__ == "__main__":
    main()

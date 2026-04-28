#!/usr/bin/env python3
"""Compatibility entrypoint for the locked DINOv2 coarse + RoMa v2 bundle.

Purpose:
- preserve the documented bundle-style launcher name for the current task;
- forward execution to `run_romav2_dinov2_intersection_round.py` without
  duplicating pipeline logic.

Main inputs:
- the same locked inputs consumed by
  `run_romav2_dinov2_intersection_round.py`.

Main outputs:
- the same bundle-root outputs under
  `new1output/romav2_dinov2_intersection_2026-04-01`.

Applicable task constraints:
- this wrapper is only a naming alias for the current formal task bundle;
- it must not introduce new path, geometry, or resolution assumptions.
"""

from run_romav2_dinov2_intersection_round import main


if __name__ == "__main__":
    main()

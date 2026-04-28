# Agent Assignments

This bundle uses a three-agent workflow for the locked
`query v2 + intersection truth` round.

## Agent 1: Coordinator

- freeze the task boundary to the locked DINOv2 inputs listed in
  `IMPLEMENTATION_PLAN.md`
- keep every new output under this bundle root only
- ensure every new report or log labels the coarse stage as `DINOv2`

## Agent 2: Implementer

- add or update thin wrapper scripts only
- reuse the existing intersection-truth RoMa v2 pipeline instead of copying
  large logic blocks
- keep evaluation outputs in `eval/`
- keep Top-20 match-point visualizations in `viz_top20_match_points/`

## Agent 3: Reviewer

- verify mapping consistency against the locked `query v2` assets
- check that no script writes back into the older
  `query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_gpu` result tree
- check that `DINOv3` wording is not reused for this round
- check that key thresholds and assumptions remain explicit

## Expected Flow

1. Coordinator freezes scope and output boundaries.
2. Implementer runs the thin wrapper for `DINOv2 coarse + RoMa v2 rerank`.
3. Reviewer inspects paths, naming, and configuration before full execution.

## Run Entry

- launcher script:
  `D:\aiproject\imagematch\scripts\run_romav2_dinov2_intersection_round.py`
- bundle root:
  `D:\aiproject\imagematch\new1output\romav2_dinov2_intersection_2026-04-01`

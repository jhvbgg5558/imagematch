# Agent Assignments

This bundle uses a three-agent workflow for the locked
`DINOv2 coarse + RoMa v2 inlier-count-only` round.

## Agent 1: Coordinator

- freeze the task boundary to the locked `new1output/query_reselect_2026-03-26_v2`
  inputs listed in `IMPLEMENTATION_PLAN.md`
- keep every new output under this bundle root only
- verify the final rank is consistent with `geom_valid`, `inlier_count`,
  `raw_rank`, and `reproj_error_mean`

## Agent 2: Implementer

- add or update thin wrapper scripts only
- reuse the existing intersection-truth RoMa v2 pipeline instead of copying
  large logic blocks
- keep evaluation outputs in `eval/`
- keep Top-20 match-point visualizations in `viz_top20_match_points/`

## Agent 3: Reviewer

- verify `fused_score` is not used for final ranking in this bundle
- check that no script writes back into `new1output`
- check that report and config metadata mark this run as
  `inlier_count_only`

## Run Entry

- launcher script:
  `D:\aiproject\imagematch\scripts\run_romav2_dinov2_inliercount_rerank_bundle.py`
- bundle root:
  `D:\aiproject\imagematch\new2output\romav2_dinov2_inliercount_rerank_2026-04-02`

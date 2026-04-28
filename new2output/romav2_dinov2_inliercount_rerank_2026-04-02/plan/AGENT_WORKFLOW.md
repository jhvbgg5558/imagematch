# Agent Workflow

This workflow keeps the current round inside the locked
`query v2 + intersection truth` boundary while changing only the final rerank
policy.

## Scope Freeze

- coarse stage must be labeled `DINOv2`
- locked inputs come from `new1output/query_reselect_2026-03-26_v2`
- final rerank mode must be `inlier_count_only`
- no result may be written back into older formal result directories

## Execution Order

1. Review `IMPLEMENTATION_PLAN.md`.
2. Run the launcher in `scripts/run_romav2_dinov2_inliercount_rerank_bundle.py`.
3. Inspect generated config and command logs under `plan/` and `logs/`.
4. Review outputs in `eval/`.
5. Review Top-20 visualizations in `viz_top20_match_points/`.

## Expected Output Roots

- `eval/` for formal rerank metrics, summaries, figures, and reports
- `viz_top20_match_points/` for recomputed Top-20 match-point visualizations
- `logs/` for command traces
- `plan/` for locked configuration and workflow notes

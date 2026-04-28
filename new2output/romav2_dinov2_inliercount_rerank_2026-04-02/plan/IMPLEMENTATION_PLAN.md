# Implementation Plan

This bundle reuses the locked `DINOv2` coarse Top-20 outputs from
`new1output/query_reselect_2026-03-26_v2` and reruns the existing `RoMa v2`
intersection pipeline with one policy change:

- final rerank mode is `inlier_count_only`
- the final rank is driven by `RANSAC` inlier count, not `fused_score`
- outputs stay under this bundle root only

## Locked Inputs

- `new1output/query_reselect_2026-03-26_v2/retrieval/retrieval_top20.csv`
- `new1output/query_reselect_2026-03-26_v2/selected_queries/selected_images_summary.csv`
- `new1output/query_reselect_2026-03-26_v2/query_inputs/images`
- `output/coverage_truth_200_300_500_700_dinov2_baseline/fixed_satellite_library/tiles.csv`

## Main Outputs

- `eval/` for rerank CSVs, summaries, figures, and reports
- `viz_top20_match_points/` for post-process Top-20 match-point visualizations
- `plan/` for locked notes and agent workflow
- `logs/` for command traces

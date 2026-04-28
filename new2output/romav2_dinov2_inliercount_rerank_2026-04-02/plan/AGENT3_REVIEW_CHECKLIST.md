# Agent 3 Review Checklist

Use this checklist before treating any new output in this bundle as valid.

## Path Safety

- confirm every new file stays under
  `D:\aiproject\imagematch\new2output\romav2_dinov2_inliercount_rerank_2026-04-02`
- confirm no script writes into
  `new1output/query_reselect_2026-03-26_v2`
- confirm no script writes into the older
  `new1output/romav2_dinov2_intersection_2026-04-01`

## Ranking Logic

- confirm `ranking_mode` is `inlier_count_only`
- confirm final rank is not sorted by `fused_score`
- confirm stable tie-breaking is:
  `geom_valid` then `inlier_count` then `raw_rank` then `reproj_error_mean`

## Metadata

- confirm `locked_run_config.json` writes `rank_score_name: inlier_count`
- confirm `rerank_top20.json` writes `ranking_mode: inlier_count_only`
- confirm visual summaries do not imply `fused_score` is the final rank source

## Inputs and Assumptions

- confirm the wrapper still uses the locked `query v2` DINOv2 feature NPZ
- confirm the FAISS index and `tiles.csv` come from the DINOv2 baseline assets
- confirm RoMa v2 thresholds stay explicit and unchanged

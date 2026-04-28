# RoMa v2 On DINOv2 Query-v2 Plan

## Summary
本轮目标是在 `query v2 + intersection truth` 口径下，复用既有 `DINOv2 coarse` 正式资产，新增一轮 `RoMa v2` 重排与同名点可视化。

所有新结果固定写入：

- `eval/`
- `viz_top20_match_points/`
- `plan/`

## Locked Inputs
- `baseline_result_dir`: `new1output/query_reselect_2026-03-26_v2`
- `query_features_npz`: `new1output/query_reselect_2026-03-26_v2/query_features/query_dinov2_pooler.npz`
- `query_seed_csv`: `new1output/query_reselect_2026-03-26_v2/query_truth/queries_truth_seed.csv`
- `query_truth_tiles_csv`: `new1output/query_reselect_2026-03-26_v2/query_truth/query_truth_tiles.csv`
- `faiss_index`: `output/coverage_truth_200_300_500_700_dinov2_baseline/faiss/satellite_tiles_ip.index`
- `mapping_json`: `new1output/query_reselect_2026-03-26_v2/faiss/satellite_tiles_ip_mapping.json`
- `query_manifest_csv`: `new1output/query_reselect_2026-03-26_v2/query_inputs/query_manifest.csv`
- `tiles_csv`: `output/coverage_truth_200_300_500_700_dinov2_baseline/fixed_satellite_library/tiles.csv`

## Notes
- 当前 `query v2` 本地 DINOv2 mapping 与旧 baseline mapping 已核对一致，可复用旧 index。
- 正式比较口径固定对照 `new1output/query_reselect_2026-03-26_v2/retrieval/summary_top20.json`。
- 报告文案必须显示 coarse 模型为 `DINOv2`，不得沿用 `DINOv3` 固定表述。

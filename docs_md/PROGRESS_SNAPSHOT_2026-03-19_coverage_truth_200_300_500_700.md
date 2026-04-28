# 当前进度快照

日期：2026-03-19

## 1. 当前正在做的主任务

当前项目的主任务是：

> 在更贴近工程实际的输入条件下，仅依赖遥感正射影像，验证是否能够对任意单张无人机图像进行初步地理定位（检索）。

当前 query 口径为：

- 单张原始无人机图像
- 不带地理信息参与检索
- 不保证为正射视角
- 不做外部人工统一分辨率预处理

## 2. 当前这轮实验的实施思路

本轮结果目录为：

- `D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_dinov2_baseline`

这轮实验相对上一轮的主要变化有两点：

1. 尺度调整

- 固定卫星库尺度改为 `200m / 300m / 500m / 700m`

2. 真值定义调整

- 不再沿用旧的中心点式真值口径
- 改为使用 query 的近似地面覆盖框与卫星瓦片地面覆盖框求交
- 当相交比例大于 `0.4` 时，定义该卫星瓦片为真值

## 3. 当前已经完成的内容

- 已完成 4 条航线共 40 张原始 query 的筛选
- 已完成 query 去元数据版本生成
- 已完成 `200/300/500/700m` 固定卫星库构建
- 已完成 coverage 真值重算
- 已完成 query 特征提取
- 已完成 satellite 特征提取
- 已完成 FAISS 建库
- 已完成 Top-10 检索结果输出
- 已完成结果汇总统计
- 已完成聚合图、分航线图和 40 个 query 的 Top-10 可视化
- 已完成当前进度文档、结果索引和作图规范更新
- 已完成当前实验的正式 Word 结果说明文档
- 已完成 refined truth 全量 `40` query 稳定性验证
- 已完成 DINOv2 baseline 在 strict truth 口径下的正式重评估

## 4. 当前结果摘要

本轮实验规模：

- query 数量：`40`
- satellite tiles 数量：`1029`
- truth tile 记录数：`427`

本轮主结果：

- `coverage Recall@1 = 0.200`
- `coverage Recall@5 = 0.400`
- `coverage Recall@10 = 0.475`
- `coverage MRR = 0.290`
- `Top-1 error mean = 759.071m`

辅助中心点口径结果：

- `center Recall@1 = 0.175`
- `center Recall@5 = 0.275`
- `center Recall@10 = 0.325`

refined truth 稳定性结果：

- 规则：`coverage_ratio >= 0.4` 且 `valid_pixel_ratio >= 0.6` 记为 `strict_truth`
- `40/40` 个 query 有 truth
- `40/40` 个 query 有 `strict_truth`
- `40/40` 个 query 满足 `strict_truth_count >= 2`
- 平均每个 query 的 truth 数为 `10.68`
- 平均每个 query 的 `strict_truth` 数为 `3.12`

strict truth 正式重评估结果：

- `strict Recall@1 = 0.175`
- `strict Recall@5 = 0.375`
- `strict Recall@10 = 0.425`
- `strict MRR = 0.262`
- `Top-1 error mean = 759.071m`
- 相较旧 coverage 结果，主指标小幅下降，但 Top-1 error 基本不变

## 5. 当前已生成的主要产物

文档：

- `docs_md/PROJECT_PROGRESS.md`
- `docs_md/RESULTS_INDEX.md`
- `docs_md/VISUALIZATION_STYLE.md`
- `docs_md/PROGRESS_SNAPSHOT_2026-03-19_coverage_truth_200_300_500_700.md`
- `output/coverage_truth_200_300_500_700_dinov2_baseline/DINOv2_coverage_truth_200_300_500_700_实验结果说明_2026-03-19.docx`

结果目录：

- `output/coverage_truth_200_300_500_700_dinov2_baseline/retrieval/summary.json`
- `output/coverage_truth_200_300_500_700_dinov2_baseline/retrieval/retrieval_top10.csv`
- `output/coverage_truth_200_300_500_700_dinov2_baseline/query_truth/query_truth.csv`
- `output/coverage_truth_200_300_500_700_dinov2_baseline/query_truth/query_truth_tiles.csv`

可视化：

- `output/coverage_truth_200_300_500_700_dinov2_baseline/figures/_aggregate`
- `output/coverage_truth_200_300_500_700_dinov2_baseline/figures/<flight_id>/metrics_bar.png`
- `output/coverage_truth_200_300_500_700_dinov2_baseline/figures/<flight_id>/query_selection_scores.png`
- `output/coverage_truth_200_300_500_700_dinov2_baseline/figures/<flight_id>/q_xxx_top10.png`

脚本：

- `scripts/visualize_coverage_retrieval_results.py`
- `scripts/generate_query_truth_from_coverage_v2.py`
- `scripts/summarize_refined_truth_stability.py`
- `scripts/evaluate_retrieval_against_strict_truth.py`
- `scripts/visualize_strict_truth_retrieval_results.py`
- `scripts/generate_strict_truth_report.py`

refined truth 结果：

- `output/coverage_truth_200_300_500_700_refined_truth_all40_valid06/query_truth.csv`
- `output/coverage_truth_200_300_500_700_refined_truth_all40_valid06/query_truth_tiles.csv`
- `output/coverage_truth_200_300_500_700_refined_truth_all40_valid06/stability_summary.md`
- `output/coverage_truth_200_300_500_700_refined_truth_all40_valid06/stability_figures`
- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/retrieval/summary.json`
- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/figures`
- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/DINOv2_strict_truth_200_300_500_700_实验结果说明_2026-03-20.docx`

## 6. 当前进度判断

当前已经不处于“搭链路”阶段，而处于：

> 新尺度口径 + 新真值定义下的基线实验已经完整跑通，当前进入结果分析、结论整理和下一轮方案判断阶段。

也就是说，当前已经完成：

- 数据口径建立
- 真值口径建立
- 基线实验执行
- 结果可视化归档
- 正式 Word 说明文档归档

当前尚未完成的重点是：

- 对比上一轮 `80/120/200/300m` 结果
- 分析 `500m/700m` 在 refined truth 下的保留比例与真实贡献
- 分析 strict truth 下从命中变成未命中的 query
- 归纳被降级为 `soft_truth` 的黑边 tile 模式
- 决定下一轮是继续调阈值，还是进入检索重评估阶段

## 7. 下一步建议

- 先做 strict truth 与原 coverage truth 的对照总结
- 统计 `strict_truth` 在不同尺度上的保留分布
- 抽查 `strict_truth` 数量最少和最多的 query，确认规则解释性
- 如需进一步提升排序质量，再进入局部几何验证或重排

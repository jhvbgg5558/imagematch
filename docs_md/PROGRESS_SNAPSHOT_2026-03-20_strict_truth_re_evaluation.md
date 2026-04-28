# 当前进度快照

日期：2026-03-20

## 1. 当前正在做的主任务

当前项目的主任务是：

> 在更贴近工程实际的输入条件下，仅依赖遥感正射影像，验证是否能够对任意单张无人机图像进行初步地理定位（检索）。

当前 query 口径为：

- 单张原始无人机图像
- 不带地理信息参与检索
- 不保证为正射视角
- 不做外部人工统一分辨率预处理

## 2. 当前这轮工作的实施思路

本轮新增结果目录为：

- `D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_dinov2_strict_truth_eval`

这轮工作不是重跑模型，而是在已有 `DINOv2 + FAISS` baseline 排序结果不变的前提下，把正式评估真值从 coverage truth 收紧到 strict truth。

strict truth 的定义是：

- 先根据无人机已有地理坐标、相对高度、云台朝向和相机内参近似生成 query 的地面 footprint
- 再计算 query footprint 与卫星瓦片地面覆盖框的相交比例
- 当 `coverage_ratio >= 0.4` 时，先进入 coverage 候选
- 再计算卫星瓦片的 `valid_pixel_ratio`
- 只有满足 `valid_pixel_ratio >= 0.6` 的 coverage 候选才进入 `strict_truth`
- 其余 coverage 命中但有效内容不足的候选记为 `soft_truth`

这轮工作的核心目标是：

- 在更干净、更适合视觉检索监督的真值口径下，重新评价当前 baseline 的真实性能

## 3. 当前已经完成的内容

- 已完成 refined truth 全量 `40` query 稳定性验证
- 已确认 `40/40` query 有 truth
- 已确认 `40/40` query 有 `strict_truth`
- 已确认 `40/40` query 满足 `strict_truth_count >= 2`
- 已新建 strict truth 正式评估目录
- 已复用原有 query features、FAISS index 和卫星候选库资产
- 已生成 `query_truth_strict_only.csv`
- 已完成 strict truth 口径下的 retrieval 重评估
- 已完成 strict truth 聚合图、分航线图和 40 个 query 的 Top-10 联系图
- 已完成 strict truth 正式 Word 结果说明文档
- 已同步更新项目进度文档、结果索引和协议说明

## 4. 当前结果摘要

这轮 strict truth 评估规模：

- query 数量：`40`
- strict truth 记录数：`125`
- 每个 query 平均 strict truth 数：`3.12`

strict truth 主结果：

- `strict Recall@1 = 0.175`
- `strict Recall@5 = 0.375`
- `strict Recall@10 = 0.425`
- `strict MRR = 0.262`
- `Top-1 error mean = 759.071m`

和旧 coverage truth 结果对比：

- 旧 `coverage Recall@1 = 0.200`
- 旧 `coverage Recall@5 = 0.400`
- 旧 `coverage Recall@10 = 0.475`
- 旧 `coverage MRR = 0.290`

当前判断：

- strict truth 下主指标出现小幅下降
- `Top-1 error mean` 基本不变
- 说明这次变化主要来自真值净化，而不是检索排序变化
- 说明旧 coverage truth 中确实包含一部分“几何上成立但不适合作为视觉正样本”的 tile

## 5. 当前已生成的主要产物

结果目录：

- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/query_truth/query_truth.csv`
- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/query_truth/query_truth_tiles.csv`
- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/query_truth/query_truth_strict_only.csv`
- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/retrieval/retrieval_top10.csv`
- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/retrieval/summary.json`

可视化：

- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/figures/_aggregate`
- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/figures/<flight_id>/metrics_bar.png`
- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/figures/<flight_id>/query_selection_scores.png`
- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/figures/<flight_id>/q_xxx_top10.png`

报告：

- `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval/DINOv2_strict_truth_200_300_500_700_实验结果说明_2026-03-20.docx`

脚本：

- `scripts/evaluate_retrieval_against_strict_truth.py`
- `scripts/visualize_strict_truth_retrieval_results.py`
- `scripts/generate_strict_truth_report.py`

文档：

- `docs_md/PROJECT_PROGRESS.md`
- `docs_md/RESULTS_INDEX.md`
- `docs_md/EXPERIMENT_PROTOCOL.md`
- `docs_md/PROGRESS_SNAPSHOT_2026-03-20_strict_truth_re_evaluation.md`

## 6. 当前进度判断

当前已经不在“真值能不能稳定生成”的阶段，而处于：

> strict truth 已经完成正式重评估，当前进入 coverage truth 与 strict truth 的差异分析阶段。

也就是说，当前已经完成：

- refined truth 规则落地
- 全量稳定性验证
- strict truth 正式评估
- 图表归档
- 报告归档
- 文档归档

当前尚未完成的重点是：

- 分析哪些 query 从 coverage 命中变成 strict 未命中
- 统计不同尺度在 strict truth 下的保留比例与命中贡献
- 归纳被降级为 `soft_truth` 的典型黑边或低有效内容模式
- 判断 `min_valid_ratio = 0.6` 是否已经足够稳健

## 7. 下一步建议

- 做 strict truth 与 coverage truth 的逐 query 对照
- 列出由 coverage 命中变为 strict 未命中的 query 清单
- 统计 `200/300/500/700m` 各尺度的 strict truth 保留数与命中数
- 抽查 strict truth 数量最少和最多的 query，确认当前阈值的解释性
- 如后续继续提升检索质量，再进入局部几何验证或重排阶段

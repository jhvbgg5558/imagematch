# 当前任务结果可视化规范

本规范用于当前工程化检索任务的结果图表与案例图输出，适用于：

- `output/coverage_truth_200_300_500_700_dinov2_baseline`
- 后续同类 single-run baseline 结果目录

参考来源：

- `old/output/validation_200m_same_scale_lightglue_superpoint_fused_top10_k256/figures`
- `old/docs_md/REPORT_STYLE_GUIDE.md`

## 1. 目标

- 图表用于支撑结果判断，不作为装饰性材料
- 图表应能直接服务阶段总结、实验报告和后续论文式材料
- 图表默认优先表达当前正式口径，不混入旧任务口径

## 2. 输出目录

- 聚合图输出到 `figures/_aggregate/`
- 分航线图输出到 `figures/<flight_id>/`
- 每个 query 的 Top-K 联系图输出到所属航线目录

推荐结构：

- `figures/_aggregate/overall_metrics_bar.png`
- `figures/_aggregate/multi_flight_recall.png`
- `figures/_aggregate/center_metrics_bar.png`
- `figures/_aggregate/top1_error_distribution.png`
- `figures/<flight_id>/metrics_bar.png`
- `figures/<flight_id>/query_selection_scores.png`
- `figures/<flight_id>/<query_id>_top10.png`

## 3. 聚合图要求

- 必备 overall 指标图：展示正式主口径指标
- 必备 multi-flight 图：展示各航线 Recall 对比
- 若存在辅助口径，如 `center_*`，应单独出图，不与主口径混画
- 柱状图应直接在柱顶标注数值
- 标题应直接、技术化，不使用口语表达

推荐主口径：

- `coverage Recall@1`
- `coverage Recall@5`
- `coverage Recall@10`
- `coverage MRR`
- `Top-1 error mean (m)`

## 4. 分航线图要求

- 每航线至少输出一张指标柱状图
- 每航线至少输出一张 query reciprocal rank 图
- query 顺序按 `query_id` 排序
- 数值标注保留两到三位小数，保持图内一致

## 5. Top-K 联系图要求

- 默认使用白底拼图
- query 图放在第一位
- 后续候选按检索 rank 从小到大排列
- 默认生成 `Top-10`
- 图块标题条使用深色底，文字使用浅色

边框语义固定为：

- query：灰色
- coverage 真值命中：绿色
- coverage 非真值：红色

每个候选图块标题至少包含：

- `rank`
- `tile_id`
- `scale_m`
- `score`

query 图块标题至少包含：

- `query_id`
- `flight_id`
- 当前口径标签，如 `coverage truth`

## 6. 视觉与命名风格

- 维持旧结果目录的直白、工程型风格
- 不做复杂主题化设计
- 使用稳定的 matplotlib 默认配色或少量固定色
- 文件名保持语义直接，不引入冗余日期或版本后缀

## 7. 使用规则

- 当前新任务默认以 `coverage_*` 指标为主结论口径
- 若引用旧任务图片，必须明确标注为历史结果
- 如需新增图型，优先保证其能回答一个明确问题，而不是只增加展示数量

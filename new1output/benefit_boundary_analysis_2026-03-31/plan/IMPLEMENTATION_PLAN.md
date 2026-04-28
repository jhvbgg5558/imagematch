# RoMa v2 收益边界分析实施计划

## Summary
本计划用于执行当前的“收益边界分析”任务，目标是回答 RoMa v2 的提升来自哪里、对哪类 query 最有效、失败边界在哪里，以及提升是否体现为真实几何一致性，而不是少数样本上的偶然排序修正。

本次分析的所有主结论只基于 `query v2 + intersection truth` 正式结果，不混入旧任务结果，不混入其它 truth 口径，不混入其它 coarse 来源。

## Work Directory
- 工作根目录：`new1output/benefit_boundary_analysis_2026-03-31`
- 固定子目录：
  - `plan/`
  - `tables/`
  - `figures/`
  - `cases/`
  - `review/`
  - `reports/`
  - `logs/`

## Source Of Truth
### Main analysis inputs
- `new1output/query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_gpu/coarse/retrieval_top20.csv`
- `new1output/query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_gpu/per_query_comparison.csv`
- `new1output/query_reselect_2026-03-26_v2/query_truth/query_truth.csv`
- `new1output/query_reselect_2026-03-26_v2/query_truth/queries_truth_seed.csv`
- `new1output/query_reselect_2026-03-26_v2/selected_queries/selected_images_summary.csv`

### Explicit rule
- `coarse` 的唯一主真源必须是 `romav2_eval_2026-03-30_gpu/coarse/retrieval_top20.csv`。
- 独立 DINOv3 baseline 的 `retrieval/retrieval_top20.csv` 只能作为附表对照输入，不得进入主分桶逻辑。
- 若需要对照 baseline，必须单独输出附表，不得和主分析混算。

## Definitions
### Missing value rules
- 若某个 query 在某一阶段的 Top-20 中没有 truth，则该阶段的 `first_truth_rank = NA`。
- 若 `first_truth_rank = NA`，则对应 `top20_hit = 0`。
- `top1_hit = 1` 仅当 `first_truth_rank == 1`。
- `rank_gain = coarse_first_truth_rank - romav2_first_truth_rank`，仅当 before/after 两个 rank 都存在时才计算。
- 对于 D 类样本，`rank_gain` 默认记为 `NA`，不参与均值统计、箱线图和 rank scatter。
- `delta_top1_error_m = romav2_top1_error_m - coarse_top1_error_m`，它只表示 Top-1 定位偏差的变化，不可单独作为“重排成功”的判据。

### Main buckets
- A 类：`coarse_top1_hit == 1` 且 `romav2_top1_hit == 1`
- B 类：`coarse_top1_hit == 0` 且 `coarse_top20_hit == 1` 且 `romav2_top1_hit == 1`
- C 类：`coarse_top20_hit == 1` 且 `romav2_top1_hit == 0`
- D 类：`coarse_top20_hit == 0`

### Bucket refinements
- C 类细分：
  - `C_retained`：`coarse_top20_hit == 1` 且 `romav2_top20_hit == 1` 且 `romav2_top1_hit == 0`
  - `C_drop_out`：`coarse_top20_hit == 1` 且 `romav2_top20_hit == 0`
  - `C_near_miss`：`C_retained == 1` 且 `romav2_first_truth_rank <= 3`
- B 类细分：
  - `B_core`：`promoted_to_top1 == 1` 且 `rank_gain >= 3`
  - `B_strong_rank`：`rank_gain >= 5`
  - `B_strong_error`：`delta_top1_error_m <= -200`
- A 类补充标记：
  - `A_shrink`：`delta_top1_error_m <= -100`

## Deliverables
### Tables
- `tables/per_query_boundary_analysis.csv`
- `tables/bucket_summary.csv`
- `tables/table_1_bucket_counts.csv`
- `tables/table_2_bucket_by_flight.csv`
- `tables/table_3_rank_error_summary.csv`
- `tables/table_4_truth_footprint_summary.csv`
- `tables/supp_table_A_r1_contribution.csv`
- `tables/supp_table_B_c_bucket_breakdown.csv`
- `tables/supp_table_C_pitch_group_bucket_ratio.csv`

### Figures
- `figures/figure_1_bucket_counts.png`
- `figures/figure_2_bucket_by_flight.png`
- `figures/figure_3_rank_scatter.png`
- `figures/figure_4_top1_error_delta_boxplot.png`
- `figures/figure_5_pitch_distribution.png`
- `figures/figure_6_truthcount_footprint_distribution.png`
- `figures/figure_7_b_rank_gain_distribution.png`

### Cases and review
- `cases/representative_cases.csv`
- `cases/cd_failure_labels.csv`
- `review/review_notes.md`

### Report
- `reports/benefit_boundary_analysis_report.md`
- If needed, a docx export may be added later, but Markdown is the primary report format.

## Agent Responsibilities
### agent1
- Maintain this implementation plan as the only planning source.
- Lock the analysis scope, source tables, bucket definitions, NA rules, and case selection rules.
- Do not implement analysis code or generate the final plots/report.

### agent2
- Implement the analysis code and produce all tables, figures, cases, and intermediate logs.
- Read only the approved sources listed above.
- Create deterministic outputs under the working directory.
- Do not write the review notes or final report.

### agent3
- Review agent2 outputs for consistency, completeness, and rule compliance.
- Verify bucket assignments, NA handling, and summary statistics.
- Write review notes and the final report only after checks pass.

## Analysis Workflow
### Stage 1: Plan and directory setup
- Create the work directory tree.
- Save this file as the locked implementation plan.
- Create `TASK_CHECKLIST.md`.

### Stage 2: Per-query base table
- Build the unified per-query analysis table with one row per query.
- Attach coarse ranks, RoMa ranks, hit flags, error values, rank gain, query metadata, and truth counts.
- Validate that all 40 queries are present and uniquely assigned to one main bucket.

### Stage 3: Summary tables and figures
- Produce the four main tables and the three supplementary tables.
- Produce the seven required figures.
- Keep the statistics consistent with the per-query table and the NA rules.

### Stage 4: Case and failure analysis
- Select representative cases with fixed selection priority.
- Generate `cd_failure_labels.csv` for C and D classes.
- Distinguish C retained cases from C drop-out cases.

### Stage 5: Review and report
- Agent3 must verify the outputs and record issues or confirmations in `review/review_notes.md`.
- After review passes, generate the final Markdown report in `reports/`.

## Case Selection Rules
- Representative cases must be chosen to cover all four main buckets.
- Default case counts:
  - A 类 2 个
  - B 类 4 个
  - C 类 3 个
  - D 类 2 个
- Selection priority:
  - Cover different flights first.
  - Then cover different `pitch_group` values.
  - For B 类, prefer `B_core` and `B_strong_rank`.
  - For C 类, ensure both `C_retained` and `C_drop_out` are represented.
  - For D 类, ensure both `truth_sparse_limited` and `representation_failure` are represented if present.

## Failure Labels
Use a fixed label set for C/D manual inspection:
- `large_viewpoint_gap`
- `non_ground_dominant`
- `limited_overlap`
- `repetitive_texture`
- `appearance_gap_ortho_vs_oblique`
- `hard_negative_dominance`

For D 类, also distinguish:
- `truth_sparse_limited`
- `representation_failure`

## Validation Criteria
- 40 个 query 必须全部且仅归入一个主桶。
- `C_retained + C_drop_out == C_total` 必须成立。
- `NA` 处理规则必须与本文件一致。
- `delta_top1_error_m` 只能作为辅助指标，不能替代 top-1 命中判据。
- 补表 A 中新增 Top-1 命中贡献的解释必须与整体 `delta R@1` 一致。
- 图表、表格、案例和报告必须来源于通过审查的结果文件。

## Assumptions
- 主分析固定使用 `query v2 + intersection truth`。
- 不新增额外的自动场景分类模型。
- 不修改既有正式结果目录中的原始输出。
- 所有新结果集中写入 `new1output/benefit_boundary_analysis_2026-03-31`。

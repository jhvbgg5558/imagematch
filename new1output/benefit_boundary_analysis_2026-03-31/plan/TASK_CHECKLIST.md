# RoMa v2 收益边界分析任务清单

## Stage 1: Plan And Directory Setup
- [ ] Create `new1output/benefit_boundary_analysis_2026-03-31/plan/`
- [ ] Save the locked implementation plan as `IMPLEMENTATION_PLAN.md`
- [ ] Create `TASK_CHECKLIST.md`
- [ ] Create the remaining working directories: `tables/`, `figures/`, `cases/`, `review/`, `reports/`, `logs/`
- Acceptance criteria:
  - [ ] The work directory exists and only contains files for this analysis.
  - [ ] The plan file reflects the final unique coarse source and bucket rules.

## Stage 2: Build Per-Query Base Table
- [ ] Read `romav2_eval_2026-03-30_gpu/coarse/retrieval_top20.csv` as the only coarse source.
- [ ] Read `romav2_eval_2026-03-30_gpu/per_query_comparison.csv`.
- [ ] Read `query_truth/query_truth.csv`, `query_truth/queries_truth_seed.csv`, and `selected_queries/selected_images_summary.csv`.
- [ ] Build `tables/per_query_boundary_analysis.csv`.
- [ ] Populate all required columns, including ranks, hit flags, error fields, `rank_gain`, bucket labels, metadata, and truth counts.
- [ ] Apply NA rules exactly as specified in the plan.
- Acceptance criteria:
  - [ ] All 40 queries are present exactly once.
  - [ ] Every query belongs to exactly one main bucket.
  - [ ] D bucket rows have `first_truth_rank = NA` and `rank_gain = NA`.

## Stage 3: Summary Tables
- [ ] Generate `tables/bucket_summary.csv`.
- [ ] Generate `tables/table_1_bucket_counts.csv`.
- [ ] Generate `tables/table_2_bucket_by_flight.csv`.
- [ ] Generate `tables/table_3_rank_error_summary.csv`.
- [ ] Generate `tables/table_4_truth_footprint_summary.csv`.
- [ ] Generate `tables/supp_table_A_r1_contribution.csv`.
- [ ] Generate `tables/supp_table_B_c_bucket_breakdown.csv`.
- [ ] Generate `tables/supp_table_C_pitch_group_bucket_ratio.csv`.
- Acceptance criteria:
  - [ ] Bucket counts sum to 40.
  - [ ] `C_retained + C_drop_out == C_total`.
  - [ ] Supplementary tables are internally consistent with the per-query base table.

## Stage 4: Figures
- [ ] Generate `figures/figure_1_bucket_counts.png`.
- [ ] Generate `figures/figure_2_bucket_by_flight.png`.
- [ ] Generate `figures/figure_3_rank_scatter.png`.
- [ ] Generate `figures/figure_4_top1_error_delta_boxplot.png`.
- [ ] Generate `figures/figure_5_pitch_distribution.png`.
- [ ] Generate `figures/figure_6_truthcount_footprint_distribution.png`.
- [ ] Generate `figures/figure_7_b_rank_gain_distribution.png`.
- Acceptance criteria:
  - [ ] Every figure matches the approved bucket definitions and NA handling rules.
  - [ ] Rank scatter excludes rows with missing before/after rank values.
  - [ ] The figure set covers bucket counts, flight distribution, rank changes, error changes, pitch, truth/footprint, and B-class gain strength.

## Stage 5: Cases And Failure Labels
- [ ] Create `cases/representative_cases.csv`.
- [ ] Create `cases/cd_failure_labels.csv`.
- [ ] Select representative cases with the fixed bucket counts and priority rules.
- [ ] Distinguish `C_retained`, `C_drop_out`, and `C_near_miss`.
- [ ] Record C/D failure labels from the fixed label set.
- Acceptance criteria:
  - [ ] All four main buckets are represented in the case list.
  - [ ] B cases include strong improvement examples when available.
  - [ ] C cases include both retained and drop-out patterns when available.

## Stage 6: Review And Report
- [ ] Write `review/review_notes.md` after checking outputs.
- [ ] Verify bucket exclusivity and completeness.
- [ ] Verify NA handling and supplementary tables.
- [ ] Verify the contribution of B-class cases to the overall R@1 gain.
- [ ] Write `reports/benefit_boundary_analysis_report.md`.
- Acceptance criteria:
  - [ ] Review notes explicitly confirm or flag each validation rule.
  - [ ] Final report uses only reviewed outputs.
  - [ ] Final report explains benefit boundary, success cases, and failure boundaries.

## Stage 7: Final Consistency Check
- [ ] Confirm that the work directory contains only analysis outputs for this task.
- [ ] Confirm that the locked implementation plan still matches the generated files.
- [ ] Confirm that no old-task outputs were used in the main bucket logic.
- Acceptance criteria:
  - [ ] The analysis is reproducible from the saved files.
  - [ ] The directory layout matches the plan.
  - [ ] The final report can be regenerated from the stored tables and figures.

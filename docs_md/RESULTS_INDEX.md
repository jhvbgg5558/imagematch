# 结果目录索引

当前新任务已生成首轮正式 DINOv2 检索结果目录，并追加了一轮 coverage 真值口径结果。

## 1. 当前状态

- 旧结果已归档到 `../old/output/`
- 当前任务已产生首轮正式实验输出
- 当前已生成外部数据目录 `D:\数据\武汉影像\挑选无人机0.1m`，用于后续真值构造前的 query 候选管理
- 当前已生成原始裁块固定卫星库：`D:\aiproject\imagematch\output\fixed_satellite_library_4flights_raw_multiscale`
- 当前已生成原始裁块真值目录：`D:\aiproject\imagematch\output\query_truth_fixed_library_40_raw`
- 当前已生成四尺度原始裁块固定卫星库：`D:\aiproject\imagematch\output\fixed_satellite_library_4flights_raw_multiscale_80_120_200_300`
- 当前已生成四尺度原始裁块真值目录：`D:\aiproject\imagematch\output\query_truth_fixed_library_40_raw_80_120_200_300`
- 当前已生成去元数据 query 目录：`D:\aiproject\imagematch\output\query_sanitized_40_v2`
- 当前已生成 DINOv2 query 特征目录：`D:\aiproject\imagematch\output\dinov2_baseline_raw_40_query`
- 当前已生成 DINOv2 三尺度 vs 四尺度对照目录：`D:\aiproject\imagematch\output\dinov2_retrieval_compare_3scale_vs_4scale`
- 当前已生成 `200/300/500/700m` coverage 真值基线目录：`D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_dinov2_baseline`
- 当前已生成 refined truth 全量稳定性目录：`D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_refined_truth_all40_valid06`
- 当前已生成 strict truth 正式重评估目录：`D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_dinov2_strict_truth_eval`
- 当前保留一套过渡版 `512` 资产：`D:\aiproject\imagematch\output\fixed_satellite_library_4flights_80_120_200` 与 `D:\aiproject\imagematch\output\query_truth_fixed_library_40`
- 当前新一轮 query 重选和后续检索/可视化结果将统一使用 `new1output/` 作为工作根目录
- 当前已生成 RoMa v2 收益边界分析目录：`D:\aiproject\imagematch\new1output\benefit_boundary_analysis_2026-03-31`
- 当前已生成收益边界分析 Word 报告：`D:\aiproject\imagematch\new1output\benefit_boundary_analysis_2026-03-31\reports\benefit_boundary_analysis_report.docx`
- 当前已新增收益边界分析 Word 导出脚本：`D:\aiproject\imagematch\scripts\generate_benefit_boundary_word_report.py`
- 当前已新增 `RoMa v2` Top-20 同名点可视化脚本：`D:\aiproject\imagematch\scripts\visualize_romav2_top20_match_points.py`
- 当前 `RoMa v2` Top-20 同名点可视化目标输出目录为：`D:\aiproject\imagematch\new1output\romav2_top20_match_viz_2026-04-01`
- 当前已新增 `DINOv2 coarse + RoMa v2` 任务级包装脚本：`D:\aiproject\imagematch\scripts\run_romav2_dinov2_intersection_bundle.py`
- 当前 `DINOv2 coarse + RoMa v2` 执行目录为：`D:\aiproject\imagematch\new1output\romav2_dinov2_intersection_2026-04-01`
- 当前该目录已包含 `plan/IMPLEMENTATION_PLAN.md`、`plan/AGENT_WORKFLOW.md`、`plan/AGENT3_REVIEW_CHECKLIST.md` 与 `logs/README.md`；正式运行后应在同目录下新增 `eval/`、`viz_top20_match_points/` 与 `run_manifest.json`
- 截至 `2026-04-01` 当前该目录已启动正式运行，并已生成 `eval/coarse/retrieval_top20.csv`、`eval/coarse/summary_top20.json`、`eval/coarse/topk_truth_curve_top20.csv`
- 截至 `2026-04-01` 当前该目录已生成 `eval/input_round/stage3/` 与 `eval/input_round/stage4/`；说明 `DINOv2 coarse` 导出与 `RoMa v2` 输入准备已完成
- 截至 `2026-04-01` 当前该目录已开始生成 `eval/stage7/` 下的首条航线 rerank 结果，但尚未完成全量汇总、正式报告与 `viz_top20_match_points/`
- 当前已完成 `DOM+DSM+PnP Baseline v1` 实施计划文档定稿，文档位于 `new2output/DOM+DSM+PnP 位姿恢复实施计划（Baseline v1）.docx`
- 当前 `DOM+DSM+PnP Baseline v1` 的正式结果目录尚未生成，后续若开始实施，建议统一使用 `new2output/pose_baseline_v1/` 作为工作根目录

## 2. 使用规则

- 默认不要引用 `../old/output/` 下的任何结果作为当前正式结论
- 默认优先使用 raw 固定库与 raw 真值目录，不要把过渡版 `512` 资产当作主输入
- 如需分析旧结果，必须明确标注为历史任务结果
- 当前首轮正式对照结果以 `dinov2_retrieval_compare_3scale_vs_4scale` 为准
- 当前最新单轮正式结果以 `coverage_truth_200_300_500_700_dinov2_baseline` 为准
- 当前最新 refined truth 稳定性资产以 `coverage_truth_200_300_500_700_refined_truth_all40_valid06` 为准
- 当前最新 strict truth 正式评估结果以 `coverage_truth_200_300_500_700_dinov2_strict_truth_eval` 为准
- 当前 RoMa v2 收益边界分析结果以 `new1output\benefit_boundary_analysis_2026-03-31` 为准，主分桶只允许使用 `new1output\query_reselect_2026-03-26_v2\romav2_eval_2026-03-30_gpu\coarse\retrieval_top20.csv` 作为 coarse 输入
- 当前收益边界分析 Word 报告沿用同一主口径，仅做排版与插图，不重算结果、不改写分桶规则
- 当前 `RoMa v2` 同名点可视化属于后处理复算产物，只复用正式 `reranked_top20.csv` 与图像资产，不改动正式评估结果
- 当前 `DOM+DSM+PnP Baseline v1` 仅有计划文档，不得当作正式结果目录引用

## 3. 首轮正式结果

- 目录：`D:\aiproject\imagematch\output\dinov2_retrieval_compare_3scale_vs_4scale`
- 方法：DINOv2 `pooler` 全局特征 + FAISS `IndexFlatIP`
- 输入约束：query 使用去元数据无人机图像；satellite 使用 raw 固定卫星库
- 对照方式：`80/120/200m` vs `80/120/200/300m`
- 真值定义：query 中心点半径 `50m` 内与真值圆相交的卫星瓦片
- 关键结果：
  - 三尺度：`R@1=0.050`，`R@5=0.275`，`R@10=0.350`，`MRR=0.142`
  - 四尺度：`R@1=0.125`，`R@5=0.275`，`R@10=0.375`，`MRR=0.193`
  - `300m` 带来 `3` 个新增 Top-1 命中

## 4. 当前最新单轮结果

- 目录：`D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_dinov2_baseline`
- 方法：DINOv2 `pooler` 全局特征 + FAISS `IndexFlatIP`
- 输入约束：query 使用去元数据无人机图像；satellite 使用 raw 固定卫星库
- 尺度：`200/300/500/700m`
- 真值定义：query 近似地面覆盖框与卫星瓦片地面覆盖框相交比例大于 `0.4` 记为 coverage 真值
- 数据规模：`40` 个 query、`1029` 个卫星 tiles、`427` 条 truth tile 记录
- 关键结果：
  - `coverage R@1=0.200`
  - `coverage R@5=0.400`
  - `coverage R@10=0.475`
  - `coverage MRR=0.290`
  - `center R@1=0.175`
  - `center R@5=0.275`
  - `center R@10=0.325`
  - `Top-1 error mean ≈ 759.071m`
  - 当前已生成聚合图、分航线图和 40 个 query 的 Top-10 联系图
## 5. 待补充内容

## 5. Refined Truth 稳定性结果

- 目录：`D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_refined_truth_all40_valid06`
- 用途：验证 refined truth 是否能在全量 `40` 个 query 上稳定提供主真值
- 规则：
  - `strict_truth`：`coverage_ratio >= 0.4` 且 `valid_pixel_ratio >= 0.6`
  - `soft_truth`：满足 coverage，但有效内容不足
- 关键结果：
  - `40/40` query 有 truth
  - `40/40` query 有 `strict_truth`
  - `40/40` query 满足 `strict_truth_count >= 2`
  - 平均每个 query：`truth_total=10.68`、`strict=3.12`、`soft=7.55`
- 主要资产：
  - `query_truth.csv`
  - `query_truth_tiles.csv`
  - `filtered_tiles_diagnostics.csv`
  - `stability_summary.md`
  - `stability_figures/*.png`

## 6. Strict Truth 正式重评估结果

- 目录：`D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_dinov2_strict_truth_eval`
- 用途：在不改变 DINOv2 特征、FAISS 索引和排序结果的前提下，用 `strict_truth` 作为正式主口径重新评估 baseline
- 真值输入：
  - 全量 refined truth 资产来自 `coverage_truth_200_300_500_700_refined_truth_all40_valid06`
  - 正式评估只使用 `query_truth_strict_only.csv`
- 关键结果：
  - `strict R@1=0.175`
  - `strict R@5=0.375`
  - `strict R@10=0.425`
  - `strict MRR=0.262`
  - `Top-1 error mean ≈ 759.071m`
- 主要资产：
  - `retrieval/retrieval_top10.csv`
  - `retrieval/summary.json`
  - `figures/_aggregate/*.png`
  - `figures/<flight_id>/q_xxx_top10.png`
  - `DINOv2_strict_truth_200_300_500_700_实验结果说明_2026-03-20.docx`

## 7. DOM+DSM+PnP Baseline v1 预留结果结构

这部分仅用于后续实施阶段的目录约定，不代表当前已经生成任何 pose 结果。

- 计划与执行说明：`new2output/pose_baseline_v1/plan/`
- 运行输入与中间产物：`new2output/pose_baseline_v1/eval/`
- 可视化结果：`new2output/pose_baseline_v1/viz/`
- 正式报告：`new2output/pose_baseline_v1/reports/`
- 若后续需要为不同阶段保留子目录，优先使用明确语义的层级命名，不沿用旧的检索阶段编号

后续新增结果时，补充：

- 目录路径
- 方法名称
- 输入约束
- 真值定义
- 适用场景

## 8. DOM+DSM+PnP Baseline v1 调试结果目录（2026-04-02）

这部分记录的是“真实输入小样本闭环调试产物”，不是正式 pose 评估结果。

- 工作根目录：`D:\aiproject\imagematch\new2output\pose_baseline_v1`
- 真实样本输入：`D:\aiproject\imagematch\new2output\pose_baseline_v1\real_sample_case\input`
- RoMa 匹配结果：`D:\aiproject\imagematch\new2output\pose_baseline_v1\matches\roma_matches.csv`
- 2D-3D 对应：`D:\aiproject\imagematch\new2output\pose_baseline_v1\sampling\sampled_correspondences.csv`
- PnP 结果：`D:\aiproject\imagematch\new2output\pose_baseline_v1\pnp\pnp_results.csv`
- 候选打分：`D:\aiproject\imagematch\new2output\pose_baseline_v1\scores\pose_candidate_scores.csv`
- 汇总结果：`D:\aiproject\imagematch\new2output\pose_baseline_v1\summary\pose_overall_summary.json`
- 当前用途：验证真实 query + DOM + DSM 输入下的脚本闭环与失败分型是否可运行
- 当前限制：该目录包含同航线局部 DOM/DSM debug case，不得当作正式 retrieval 或正式 pose 精度结果引用

## 2026-04-02 Formal Pose v1 Result Root
- Active formal pose workspace: `D:\aiproject\imagematch\new2output\pose_v1_formal`.
- Generated formal inputs:
  - `input/formal_query_manifest.csv`
  - `input/formal_candidate_manifest.csv`
  - `input/formal_truth_manifest.csv`
  - `input/formal_dsm_manifest.csv`
  - `input/asset_validation_report.json`
  - `manifest/pose_manifest.json`
- These files are preparation-stage assets only, not final pose evaluation results.
- Historical debug root `D:\aiproject\imagematch\new2output\pose_baseline_v1` is inactive and must not be cited as the formal result root.

## 2026-04-02 Formal Pose v1 Preparation Outputs
- Formal preparation outputs currently considered valid:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\input\formal_query_manifest.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\input\formal_candidate_manifest.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\input\formal_truth_manifest.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\input\formal_dsm_manifest.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\input\asset_validation_report.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\manifest\pose_manifest.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\dsm_cache\requests\srtm_download_requests.csv`
- Raw upstream SRTM source now present:
  - `D:\aiproject\imagematch\new2output\N30E114.hgt`
- These are still preparation-stage artifacts.
- No formal `matches/`, `correspondences/`, `sampling/`, `pnp/`, `scores/`, or `summary/` outputs are valid yet under `pose_v1_formal`.

## 2026-04-02 DINOv2 + RoMa v2 Inlier-Only Rerank
- New experiment entrypoints:
  - `D:\aiproject\imagematch\scripts\run_romav2_dinov2_inliercount_rerank_round.py`
  - `D:\aiproject\imagematch\scripts\run_romav2_dinov2_inliercount_rerank_bundle.py`
- New output root:
  - `D:\aiproject\imagematch\new2output\romav2_dinov2_inliercount_rerank_2026-04-02`
- Input assets are reused from:
  - `D:\aiproject\imagematch\new1output\query_reselect_2026-03-26_v2`
- Ranking mode for this line is `inlier_count_only`; `fused_score` remains available for analysis but must not drive the final rank in this bundle.
- Bundle workflow notes live under:
  - `D:\aiproject\imagematch\new2output\romav2_dinov2_inliercount_rerank_2026-04-02\plan`
## 2026-04-07 Formal Pose v1 Scoring/Summary
- Stable entrypoint:
  - `D:\aiproject\imagematch\scripts\score_formal_pose_results.py`
- Shared implementation:
  - `D:\aiproject\imagematch\scripts\run_pose_v1_formal_scoring_summary.py`
- Formal outputs:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\scores\pose_scores.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\summary\per_query_best_pose.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\summary\pose_overall_summary.json`
- These outputs are only valid after the formal `pnp` stage produces `pnp/pnp_results.csv`.
## 2026-04-07 Formal Pose v1 Planned / Active Outputs
- Active formal root: `D:\aiproject\imagematch\new2output\pose_v1_formal\`
- DSM build summary: `D:\aiproject\imagematch\new2output\pose_v1_formal\dsm_cache\rasters\_summary.json`
- Phase-gate summary: `D:\aiproject\imagematch\new2output\pose_v1_formal\summary\phase_gate_summary.json`
- Formal score table: `D:\aiproject\imagematch\new2output\pose_v1_formal\scores\pose_scores.csv`
- Formal best-pose table: `D:\aiproject\imagematch\new2output\pose_v1_formal\summary\per_query_best_pose.csv`
- Formal overall summary: `D:\aiproject\imagematch\new2output\pose_v1_formal\summary\pose_overall_summary.json`
- Formal orchestration entrypoint: `D:\aiproject\imagematch\scripts\run_formal_pose_v1_pipeline.py`
- Formal DSM materialization entrypoint: `D:\aiproject\imagematch\scripts\materialize_formal_dsm_rasters.py`
- Formal scoring entrypoint: `D:\aiproject\imagematch\scripts\score_formal_pose_results.py`
- Current validated runtime gate outputs are from the 3-query sample closure:
  - `query_ids = q_001, q_011, q_021`
  - `pair_count = 60`
  - `PnP ok = 59`
  - `PnP failed = 1`
## 2026-04-09 Formal Pose v1 Full-40 Valid Outputs
- Active formal result root:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\`
- Full-run stage outputs now considered valid:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\matches\roma_matches.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\matches\roma_match_summary.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\correspondences\pose_correspondences.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\correspondences\prepare_summary.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\sampling\sampled_correspondences.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\sampling\sampling_summary.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\pnp\pnp_results.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\pnp\pnp_summary.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\pnp\pnp_inliers.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\scores\pose_scores.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\summary\per_query_best_pose.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\summary\pose_overall_summary.json`
- Full-run summary highlights:
  - `query_count = 40`
  - `score_row_count = 800`
  - `PnP status_counts = {ok: 756, pnp_failed: 44}`
  - `best_status_counts = {ok: 40}`
  - `best_ok_rate = 1.0`
- The superseded pre-rerun `PnP` files are preserved for audit only:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\pnp_backup_2026-04-09_pre_full40_rerun\`
## 2026-04-09 Formal Pose v1 UAV Ortho-Truth Evaluation
- New evaluation entrypoints:
  - `D:\aiproject\imagematch\scripts\build_query_ortho_truth_manifest.py`
  - `D:\aiproject\imagematch\scripts\crop_query_ortho_truth_tiles.py`
  - `D:\aiproject\imagematch\scripts\render_query_predicted_ortho_from_pose.py`
  - `D:\aiproject\imagematch\scripts\evaluate_pose_ortho_alignment.py`
  - `D:\aiproject\imagematch\scripts\render_pose_ortho_overlay_viz.py`
  - `D:\aiproject\imagematch\scripts\run_pose_ortho_truth_eval_pipeline.py`
- Active evaluation result root:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\`
- Gate outputs:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\phase_gate_summary.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\query_ortho_truth_manifest.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\truth_tiles\_summary.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\pred_tiles\_summary.json`
- Full-run quantitative outputs:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\per_query_ortho_accuracy.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\overall_ortho_accuracy.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\per_flight_ortho_accuracy.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\failure_buckets.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\full_run_summary.json`
- Full-run visualization outputs:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\viz_overlay_truth\`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\viz_overlay_dom\`
- Formal interpretation report:
  - `D:\aiproject\imagematch\scripts\generate_pose_ortho_accuracy_word_report.py`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\reports\pose_ortho_accuracy_report.docx`
- Full-run summary highlights:
  - `query_count = 40`
  - `evaluated_query_count = 39`
  - `eval_status_counts = {ok: 39, dsm_intersection_failed: 1}`
  - `phase_corr_error_m mean = 0.2497`
  - `phase_corr_error_m median = 0.2468`
  - `phase_corr_error_m p90 = 0.4389`
  - `ortho_iou mean = 0.3798`
  - `ssim mean = 0.4782`
  - only failed query = `q_022`
## 2026-04-09 Formal Pose v1 Ortho Tie-Point Ground Error Evaluation
- New evaluation entrypoints:
  - `D:\aiproject\imagematch\scripts\evaluate_pose_ortho_tiepoint_ground_error.py`
  - `D:\aiproject\imagematch\scripts\render_pose_ortho_tiepoint_viz.py`
- Active output root:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\`
- Full-run quantitative outputs:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\per_query_tiepoint_ground_error.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\overall_tiepoint_ground_error.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\per_flight_tiepoint_ground_error.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\tiepoint_failure_buckets.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\tiepoints\per_query_matches\`
- Full-run visualization outputs:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_ortho_truth\viz_tiepoints\`
- Full-run summary highlights:
  - `query_count = 40`
  - `evaluated_query_count = 39`
  - `matchable_query_count = 39`
  - `eval_status_counts = {tiepoint_eval_ok: 39, upstream_eval_failed: 1}`
  - `tiepoint_xy_error_mean_m = 3.9425`
  - `tiepoint_xy_error_median_m = 2.9209`
  - `tiepoint_xy_error_rmse_m = 5.7002`
  - `tiepoint_xy_error_p90_m = 13.7098`
  - `tiepoint_match_count_mean = 1070.23`
  - `tiepoint_inlier_ratio_mean = 0.5526`
  - only failed query remains `q_022`

## 2026-04-09 Formal Pose v1 Unified Validation Suite
- Unified suite entrypoints:
  - `D:\aiproject\imagematch\scripts\run_pose_validation_suite.py`
  - `D:\aiproject\imagematch\scripts\summarize_pose_validation_suite.py`
  - `D:\aiproject\imagematch\scripts\build_query_reference_pose_manifest.py`
  - `D:\aiproject\imagematch\scripts\evaluate_pose_against_reference_pose.py`
  - `D:\aiproject\imagematch\scripts\generate_pose_validation_suite_word_report.py`
  - `D:\aiproject\imagematch\scripts\render_pose_vs_at_figures.py`
- Active full-run result root:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\`
- Suite-level outputs:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\validation_manifest.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\full_run_summary.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\reports\validation_suite_summary.md`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\reports\formal_pose_v1_validation_suite_report.docx`
- Layer-1 outputs:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\ortho_alignment\per_query_ortho_accuracy.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\ortho_alignment\overall_ortho_accuracy.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\ortho_alignment\per_flight_ortho_accuracy.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\ortho_alignment\failure_buckets.csv`
- Layer-2 outputs:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\query_reference_pose_manifest.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\query_reference_pose_manifest.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\per_query_pose_vs_at.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\overall_pose_vs_at.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\per_flight_pose_vs_at.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\pose_vs_at_failure_buckets.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\README.md`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_manifest.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_1_position_error_distribution.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_2_orientation_error_distribution.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_3_per_query_horizontal_error.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_4_per_query_view_dir_error.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_5_per_flight_pose_error.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_6_dx_dy_scatter.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_7_horizontal_vs_viewdir_scatter.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_8_reference_source_status.png`
- Layer-3 outputs:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\tiepoint_ground_error\per_query_tiepoint_ground_error.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\tiepoint_ground_error\overall_tiepoint_ground_error.json`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\tiepoint_ground_error\per_flight_tiepoint_ground_error.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\tiepoint_ground_error\tiepoint_failure_buckets.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\tiepoint_ground_error\tiepoints\per_query_matches\`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\tiepoint_ground_error\viz_tiepoints\`
- Full-run summary highlights:
  - layer-1: `query_count=40`, `evaluated_query_count=39`, `phase_corr_error_m mean=0.2497`, `p90=0.4389`, failed query=`q_022`
  - layer-2: `query_count=40`, `evaluated_query_count=40`, `horizontal_error_m mean=40.6718`, `median=4.6051`, `view_dir_angle_error_deg mean=2.0945`
  - layer-2 reference source audit: `reference_source_type_counts = {odm_report_shots_geojson: 40}`
  - layer-3: `query_count=40`, `evaluated_query_count=39`, `tiepoint_xy_error_rmse_m=5.4663`, `tiepoint_xy_error_p90_m=8.2290`, failed query=`q_022`

## 2026-04-10 Formal Pose v1 Layer-2 Figure Outputs
- Figure rendering entrypoint:
  - `D:\aiproject\imagematch\scripts\render_pose_vs_at_figures.py`
- Figure output root:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\`
- Figure documentation:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\README.md`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_manifest.json`
- Figure files:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_1_position_error_distribution.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_2_orientation_error_distribution.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_3_per_query_horizontal_error.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_4_per_query_view_dir_error.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_5_per_flight_pose_error.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_6_dx_dy_scatter.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_7_horizontal_vs_viewdir_scatter.png`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\figure_8_reference_source_status.png`
- Verification snapshot:
  - `figure_count = 8`
  - `query_count = 40`
  - `evaluated_query_count = 40`
  - `reference_source_type_counts = {odm_report_shots_geojson: 40}`
  - highlighted outlier: `q_022`, with `horizontal_error_m = 1357.953818` and `view_dir_angle_error_deg = 53.405885`

## 2026-04-10 009/010 Nadir DINOv2 + RoMa v2 + DOM/DSM/PnP Full Run
- Result root:
  - `D:\aiproject\imagematch\new2output\nadir_009010_dinov2_romav2_pose_2026-04-10\`
- Scope:
  - route `009`: `20` selected query images
  - route `010`: `20` selected query images
  - all selected query rows satisfy `gimbal_pitch_degree <= -85.0`
- Query and retrieval outputs:
  - `selected_queries\selected_images_summary.csv`: `40` rows
  - `query_inputs\query_manifest.csv`: `40` rows
  - `query_truth\query_truth_tiles.csv`: `553` rows
  - `query_features\query_dinov2_pooler.npz`: `40 x 768` query feature matrix
  - `romav2_rerank\coarse\retrieval_top20.csv`: `800` rows
  - `romav2_rerank\stage7\DJI_202510311347_009_新建面状航线1\reranked_top20.csv`: `400` rows
  - `romav2_rerank\stage7\DJI_202510311413_010_新建面状航线1\reranked_top20.csv`: `400` rows
  - `retrieval\retrieval_top20.csv`: `800` rows
- Formal pose outputs:
  - `pose_v1_formal\input\asset_validation_report.json`: `is_valid = true`
  - `pose_v1_formal\manifest\pose_manifest.json`: `800` query-candidate pairs
  - `pose_v1_formal\matches\roma_matches.csv`: `1,600,000` rows
  - `pose_v1_formal\correspondences\pose_correspondences.csv`: `1,600,000` rows
  - `pose_v1_formal\sampling\sampled_correspondences.csv`: `1,600,000` rows
  - `pose_v1_formal\pnp\pnp_results.csv`: `800` rows
  - `pose_v1_formal\scores\pose_scores.csv`: `800` rows
  - `pose_v1_formal\summary\per_query_best_pose.csv`: `40` rows
  - `pose_v1_formal\summary\pose_overall_summary.json`
- Pose summary:
  - `PnP status_counts = {ok: 734, pnp_failed: 66}`
  - `best_status_counts = {ok: 40}`
  - `best_ok_rate = 1.0`
- Unified validation suite outputs:
  - `pose_v1_formal\eval_pose_validation_suite\full_run_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite\ortho_alignment\per_query_ortho_accuracy.csv`: `40` rows
  - `pose_v1_formal\eval_pose_validation_suite\pose_vs_at\per_query_pose_vs_at.csv`: `40` rows
  - `pose_v1_formal\eval_pose_validation_suite\tiepoint_ground_error\per_query_tiepoint_ground_error.csv`: `40` rows
  - `pose_v1_formal\eval_pose_validation_suite\reports\formal_pose_v1_validation_suite_report.docx`
  - `pose_v1_formal\eval_pose_validation_suite\reports\pose_localization_accuracy_report.docx`
  - `pose_v1_formal\eval_pose_validation_suite\reports\nadir_009010_pose_experiment_detailed_report.md`
  - `pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\`: 8 PNG files plus `README.md` and `figure_manifest.json`
- Validation summary:
  - layer-1 ortho alignment: `evaluated_query_count = 40`, `phase_corr_error_m mean = 0.7672`, `center_offset_m mean = 13.1874`, `ortho_iou mean = 0.7289`, `ssim mean = 0.5958`
  - layer-2 pose-vs-AT: `evaluated_query_count = 40`, `horizontal_error_m mean = 9.1654`, `median = 7.6759`, `p90 = 16.2847`, `view_dir_angle_error_deg mean = 1.2706`
  - layer-3 tiepoint ground error: `evaluated_query_count = 40`, `tiepoint_xy_error_mean_m = 2.4473`, `median = 2.0942`, `rmse = 2.8552`, `p90 = 4.3476`
- Current dynamic layer-2 highlighted query in the figures:
  - `q_012`: `horizontal_error_m = 27.3721`, `view_dir_angle_error_deg = 3.9337`
- Path isolation:
  - this experiment's outputs are under `new2output\nadir_009010_dinov2_romav2_pose_2026-04-10\`
  - fixed satellite library, tiles metadata, and FAISS index were reused read-only from `output\coverage_truth_200_300_500_700_dinov2_baseline\`

## 2026-04-16 Satellite Truth Subchain Scaffold
- New satellite-truth helper scripts have been added for the isolated `new3output` branch:
  - `scripts\satellite_truth_utils.py`
  - `scripts\build_query_satellite_truth_manifest.py`
  - `scripts\crop_query_satellite_truth_patches.py`
  - `scripts\evaluate_pose_satellite_alignment.py`
  - `scripts\evaluate_pose_satellite_geometry.py`
  - `scripts\evaluate_pose_satellite_tiepoint_ground_error.py`
  - `scripts\run_pose_validation_suite_satellite_truth.py`
  - `scripts\generate_pose_validation_suite_satellite_truth_word_report.py`
  - `scripts\generate_pose_localization_accuracy_satellite_truth_report.py`
- The satellite-truth suite root is reserved as:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\pose_v1_formal\eval_pose_validation_suite_satellite_truth\`
- Current status:
  - the subchain has been scaffolded and syntax-checked
  - no formal `full_run_summary.json` has been recorded yet for this subchain
  - this index entry records the available code and intended output path, not a completed experimental result

## 2026-04-16 ODM Truth + ODM DSM New3output Scaffold
- New orchestrator and comparison scripts are now available:
  - `scripts\run_nadir_009010_odmrefresh_and_sattruth_experiment.py`
  - `scripts\build_odm_asset_override_manifest.py`
  - `scripts\materialize_formal_dsm_rasters_from_odm.py`
  - `scripts\generate_odm_truth_vs_satellite_truth_comparison_report.py`
- Intended experiment root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\`
- Intended new outputs:
  - `pose_v1_formal\eval_pose_validation_suite_odm_truth\`
  - `pose_v1_formal\eval_pose_validation_suite_satellite_truth\`
  - `reports\odm_truth_vs_satellite_truth_comparison.md`
  - `reports\odm_truth_vs_satellite_truth_comparison.docx`
- Current status:
  - scaffolding and orchestration are implemented
  - no completed new3output full-run result is indexed yet

## 2026-04-16 New3output Integrated Experiment Report
- A standalone integrated report for the completed new3output experiment now exists at:
  - `new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\reports\nadir_009010_odmrefresh_sattruth_full_experiment_report.docx`
- The integrated report covers:
  - query selection scope and runtime reuse assumptions
  - ODM truth + ODM DSM refreshed pose pipeline
  - ODM-truth validation
  - satellite-truth validation
  - baseline vs new3 key metric comparison
  - predicted-ortho partial-coverage / missing-area analysis
- Companion figure assets were generated under:
  - `new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\reports\full_experiment_report_assets\`
- Generated figure set includes:
  - `odm_truth_metrics.png`
  - `satellite_truth_metrics.png`
  - `baseline_vs_new3_key_metrics.png`
  - `predicted_ortho_missing_coverage_analysis.png`
  - multiple per-query truth/pred/mask/overlay sample panels
- This integrated report is additive:
  - it does not replace the suite-local ODM-truth or satellite-truth reports
  - it serves as the top-level human-readable summary for the completed new3output branch

## 2026-04-16 New3output Process-Focused Report
- A second Word report focused on experiment content and end-to-end process now exists at:
  - `new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\reports\nadir_009010_odmrefresh_sattruth_experiment_process_report.docx`
- This process-focused report emphasizes:
  - experiment objectives
  - query/data scope
  - input asset replacement relationships
  - end-to-end execution flow
  - per-stage outputs and gates
  - compact key-result summaries
  - predicted-ortho partial-coverage explanation
- Companion figure assets were generated under:
  - `new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\reports\process_report_assets\`
- The process-focused report is additive and coexists with:
  - the integrated full report
  - the suite-local ODM-truth and satellite-truth reports

## 2026-04-16 New3output Completed Branch Index
- Completed experiment root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\`
- Runtime pose outputs:
  - `pose_v1_formal\pnp\pnp_results.csv`
  - `pose_v1_formal\scores\pose_scores.csv`
  - `pose_v1_formal\summary\per_query_best_pose.csv`
  - `pose_v1_formal\summary\pose_overall_summary.json`
- ODM-truth suite outputs:
  - `pose_v1_formal\eval_pose_validation_suite_odm_truth\full_run_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_odm_truth\ortho_alignment\per_query_ortho_accuracy.csv`
  - `pose_v1_formal\eval_pose_validation_suite_odm_truth\pose_vs_at\per_query_pose_vs_at.csv`
  - `pose_v1_formal\eval_pose_validation_suite_odm_truth\tiepoint_ground_error\per_query_tiepoint_ground_error.csv`
- Satellite-truth suite outputs:
  - `pose_v1_formal\eval_pose_validation_suite_satellite_truth\full_run_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_satellite_truth\ortho_alignment_satellite\per_query_ortho_accuracy.csv`
  - `pose_v1_formal\eval_pose_validation_suite_satellite_truth\pose_vs_satellite_truth_geometry\per_query_pose_vs_satellite_truth_geometry.csv`
  - `pose_v1_formal\eval_pose_validation_suite_satellite_truth\tiepoint_ground_error_satellite\per_query_tiepoint_ground_error.csv`
- Cross-branch comparison outputs:
  - `reports\odm_truth_vs_satellite_truth_comparison.md`
  - `reports\odm_truth_vs_satellite_truth_comparison.docx`
- Top-level branch reports:
  - `reports\nadir_009010_odmrefresh_sattruth_full_experiment_report.docx`
  - `reports\full_experiment_report_assets\`
  - `reports\nadir_009010_odmrefresh_sattruth_experiment_process_report.docx`
  - `reports\process_report_assets\`
- Branch interpretation note:
  - runtime candidate retrieval remained fixed to the satellite library
  - ODM-truth changed only the truth orthophoto source and PnP DSM source
  - satellite-truth is an additive validation branch and must not be read as the runtime truth source

## 2026-04-16 Predicted-Ortho Hole Diagnosis Outputs
- Diagnosis script:
  - `scripts\diagnose_predicted_ortho_holes.py`
- Output root:
  - `new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\reports\predicted_ortho_hole_diagnosis\`
- Primary outputs:
  - `all_queries_hole_diagnosis.csv`
  - `all_queries_hole_diagnosis.json`
  - `q_003_diagnosis.json`
- Representative figures:
  - `figures\q_003_pred_rgb.png`
  - `figures\q_003_pred_alpha_mask.png`
  - `figures\q_003_dsm_valid_mask_on_pred_grid.png`
  - `figures\q_003_alpha_vs_dsm_overlap_overlay.png`
- Current classification summary:
  - `mixed_dsm_and_pose = 21`
  - `truth_grid_too_large = 19`
- Current q_003 conclusion:
  - not classified as purely `dsm_limited`
  - currently classified as `mixed_dsm_and_pose`
  - oversized truth context remains a documented contributing factor

## 2026-04-16 Satellite Truth + SRTM + RoMa-Tiepoint Gate Outputs
- New isolated branch root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16\`
- New route orchestrator and suite entrypoints:
  - `scripts\run_nadir_009010_sattruth_srtm_romatie_experiment.py`
  - `scripts\run_pose_validation_suite_sattruth_srtm.py`
  - `scripts\evaluate_pose_satellite_tiepoint_ground_error_romav2.py`
  - `scripts\generate_sattruth_srtm_romatie_vs_baseline_report.py`
- Branch contract and script snapshot outputs:
  - `plan\experiment_contract.json`
  - `scripts\script_manifest.json`
  - `logs\run_sattruth_srtm_romatie_gate.log`
- Pose gate outputs:
  - `pose_v1_formal\summary\phase_gate_summary.json`
  - `pose_v1_formal\summary\per_query_best_pose.csv`
  - `pose_v1_formal\pnp\pnp_results.csv`
  - `pose_v1_formal\dsm_cache\rasters\_summary.json`
- Satellite-truth validation gate outputs:
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\phase_gate_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\satellite_truth\query_satellite_truth_manifest.csv`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\satellite_truth\truth_patches\`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\pred_tiles\pred_tile_manifest.csv`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\ortho_alignment_satellite\per_query_ortho_accuracy.csv`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\pose_vs_at\per_query_pose_vs_at.csv`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\tiepoint_ground_error\per_query_tiepoint_ground_error.csv`
- Layer-3 RoMa gate evidence:
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\tiepoint_ground_error\overall_tiepoint_ground_error.json`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\tiepoint_ground_error\tiepoints\per_query_matches\`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\tiepoint_ground_error\viz_tiepoints\`
- Gate-stage report outputs:
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\reports\formal_pose_v1_validation_suite_sattruth_srtm_report.docx`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\reports\pose_localization_accuracy_sattruth_srtm_romatie_report.docx`
  - `reports\sattruth_srtm_romatie_vs_baseline.md`
  - `reports\sattruth_srtm_romatie_vs_baseline.docx`
- Interpretation note:
  - this index records a successful `5-query gate`
  - no `40-query full_run_summary.json` exists yet for this branch

## 2026-04-17 Satellite Truth + SRTM + RoMa-Tiepoint Full Outputs
- The same branch now also has a completed `40-query full` run:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16\`
- Full-run top-level summaries:
  - `plan\run_sattruth_srtm_romatie_full_summary.json`
  - `pose_v1_formal\summary\pose_overall_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\full_run_summary.json`
- Full-run pose outputs:
  - `pose_v1_formal\pnp\pnp_results.csv`
  - `pose_v1_formal\scores\pose_scores.csv`
  - `pose_v1_formal\summary\per_query_best_pose.csv`
  - `pose_v1_formal\summary\per_flight_best_pose_summary.csv`
- Full-run validation outputs:
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\ortho_alignment_satellite\overall_ortho_accuracy.json`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\pose_vs_at\overall_pose_vs_at.json`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\tiepoint_ground_error\overall_tiepoint_ground_error.json`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\tiepoint_ground_error\per_query_tiepoint_ground_error.csv`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\tiepoint_ground_error\tiepoints\per_query_matches\`
- Full-run report outputs:
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\reports\formal_pose_v1_validation_suite_sattruth_srtm_report.docx`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\reports\pose_localization_accuracy_sattruth_srtm_romatie_report.docx`
  - `reports\sattruth_srtm_romatie_vs_baseline.md`
  - `reports\sattruth_srtm_romatie_vs_baseline.docx`
  - `reports\final_experiment_report_sattruth_srtm_romatie.md`
  - `reports\final_experiment_report_sattruth_srtm_romatie.docx`
  - `reports\final_experiment_report_assets\overall_metrics_comparison.png`
  - `reports\final_experiment_report_assets\layer1_metrics_bar.png`
  - `reports\final_experiment_report_assets\layer2_metrics_bar.png`
  - `reports\final_experiment_report_assets\layer3_metrics_bar.png`
  - `reports\final_experiment_report_assets\low_match_queries_improvement.png`
  - `reports\final_experiment_report_assets\runtime_status_comparison.png`
  - `reports\final_experiment_report_assets\pipeline_overview.png`
  - `reports\final_experiment_report_assets\sample_cases\`
- Final-report sample-case assets currently include:
  - representative success cases: `q_015`, `q_022`
  - anomalous cases: `q_034`, `q_036`
- Final-report positioning note:
  - `final_experiment_report_sattruth_srtm_romatie.*` is the main narrative report for this branch
  - the suite-local Word reports remain valid supporting outputs, but they are no longer the preferred single-document summary
- Current interpretation note:
  - this branch is no longer gate-only
  - it now has a completed formal full run with satellite truth validation and RoMa-based layer-3 tiepoint evaluation

## 2026-04-17 ODM-Truth-Only 0.1m Re-Run Orchestrator Update
- The existing ODM-refresh orchestrator now also supports a report-free ODM-only rerun path:
  - `scripts\run_nadir_009010_odmrefresh_and_sattruth_experiment.py --phase odm_truth_only`
- New CLI controls now available:
  - `--target-resolution-m`
  - `--dsm-target-resolution-m`
  - `--skip-reports`
- Recommended isolated output root for this mode:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_0p1m_2026-04-17\`
- Expected non-report outputs for a successful gate/full run under this mode:
  - `plan\flight_asset_override_manifest.csv`
  - `plan\experiment_contract.json`
  - `plan\run_odm_truth_only_gate_summary.json`
  - `plan\run_odm_truth_only_full_summary.json`
  - `pose_v1_formal\dsm_cache\source\odm_dsm_merged.tif`
  - `pose_v1_formal\dsm_cache\rasters\_summary.json`
  - `pose_v1_formal\summary\pose_overall_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_odm_truth\phase_gate_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_odm_truth\full_run_summary.json`
- This mode is explicitly intended to avoid:
  - `pose_v1_formal\eval_pose_validation_suite_satellite_truth\`
  - suite-local `.docx` report outputs
  - cross-suite comparison report outputs

## 2026-04-17 ODM DSM Gate Resolution Sweep Outputs
- Sweep entrypoint:
  - `scripts\run_odm_dsm_gate_resolution_sweep.py`
- Sweep aggregate root:
  - `D:\aiproject\imagematch\new3output\odm_dsm_gate_resolution_sweep_2026-04-17\`
- Aggregate outputs:
  - `aggregate_summary.json`
  - `aggregate_summary.csv`
  - `logs\run_odm_dsm_gate_resolution_sweep.log`
- Per-resolution gate roots:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_5m_gate_2026-04-17\`
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_3m_gate_2026-04-17\`
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_2m_gate_2026-04-17\`
- Expected key outputs inside each per-resolution root:
  - `pose_v1_formal\dsm_cache\rasters\_summary.json`
  - `pose_v1_formal\sampling\sampling_summary.json`
  - `pose_v1_formal\summary\per_query_best_pose.csv`
  - `pose_v1_formal\summary\pose_overall_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_odm_truth\phase_gate_summary.json`
- Interpretation note:
  - this sweep exists only to estimate the highest practical ODM DSM resolution
    supported by the current LAZ assets while keeping DOM truth fixed at `0.1 m`
  - it is not a full-run branch and it intentionally generates no `.docx`
    report outputs

## 2026-04-18 ODM DSM Hi-Res Gate Sweep Outputs
- Sweep entrypoint:
  - `scripts\run_odm_dsm_gate_resolution_sweep.py`
- Hi-res sweep aggregate root:
  - `D:\aiproject\imagematch\new3output\odm_dsm_gate_resolution_sweep_hires_2026-04-18\`
- Aggregate outputs:
  - `aggregate_summary.json`
  - `aggregate_summary.csv`
  - `logs\run_odm_dsm_gate_resolution_sweep.log`
- Per-resolution gate roots:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_1m_gate_2026-04-18\`
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_0p5m_gate_2026-04-18\`
- Expected key outputs inside each per-resolution root:
  - `pose_v1_formal\dsm_cache\rasters\_summary.json`
  - `pose_v1_formal\sampling\sampling_summary.json`
  - `pose_v1_formal\summary\per_query_best_pose.csv`
  - `pose_v1_formal\summary\pose_overall_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_odm_truth\phase_gate_summary.json`
- Interpretation note:
  - this hi-res sweep is a follow-up to the completed `5 m / 3 m / 2 m` sweep
  - it exists only to test whether the highest supported ODM DSM resolution can
    be tightened from `2 m` to `1.0 m` or `0.5 m`

## 2026-04-18 ODM DSM Sweep Final Summary Outputs
- First-stage sweep final summary:
  - `D:\aiproject\imagematch\new3output\odm_dsm_gate_resolution_sweep_2026-04-17\aggregate_summary.json`
  - `D:\aiproject\imagematch\new3output\odm_dsm_gate_resolution_sweep_2026-04-17\aggregate_summary.csv`
- Hi-res sweep final summary:
  - `D:\aiproject\imagematch\new3output\odm_dsm_gate_resolution_sweep_hires_2026-04-18\aggregate_summary.json`
  - `D:\aiproject\imagematch\new3output\odm_dsm_gate_resolution_sweep_hires_2026-04-18\aggregate_summary.csv`
- Current formal interpretation:
  - highest validated supported ODM DSM resolution: `0.5 m`
  - recommended practical resolution for less distorted predicted-ortho output:
    `1.0 m`

## Predicted-Ortho Visualization Notes
- Validation predicted ortho renderer:
  - `scripts\render_query_predicted_ortho_from_pose.py`
- Truth-overlay visualization renderer:
  - `scripts\render_pose_ortho_overlay_viz.py`
- Historical smooth-reference branch:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16\pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\ortho_alignment\viz_overlay_truth\`
- Interpretation note:
  - files under `viz_overlay_truth\` are PNG visualizations derived from the
    same predicted-ortho reprojection products; they are not outputs of a
    different reconstruction method
## 2026-04-20 CaiWangCun Candidate-DOM + DSM Gate Outputs
- Branch root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_caiwangcun_candidate_domdsm_0p14m_gate_2026-04-20\`
- Key gate outputs:
  - `pose_v1_formal\dom_cache\rasters\_summary.json`
  - `pose_v1_formal\dsm_cache\rasters\_summary.json`
  - `pose_v1_formal\summary\phase_gate_summary.json`
  - `pose_v1_formal\summary\pose_overall_summary.json`
  - `pose_v1_formal\summary\per_query_best_pose.csv`
- Validation outputs:
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\phase_gate_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\ortho_alignment\overall_ortho_accuracy.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\pose_vs_at\overall_pose_vs_at.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\tiepoint_ground_error\overall_tiepoint_ground_error.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\ortho_alignment\viz_overlay_truth\`

## 2026-04-20 CaiWangCun DOM/DSM Coverage-Constrained Gate Outputs
- Branch root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_caiwangcun_domdsm_0p14m_gate_2026-04-20\`
- Entry script:
  - `scripts\run_nadir_009010_caiwangcun_domdsm_gate_experiment.py`
- Mosaic and planning outputs:
  - `source_mosaic\caiwangcun_ortho_0p14m_epsg32650.tif`
  - `source_mosaic\caiwangcun_dsm_0p14m_epsg32650.tif`
  - `source_mosaic\caiwangcun_mosaic_summary.json`
  - `plan\caiwangcun_asset_manifest.csv`
  - `plan\caiwangcun_candidate_coverage_audit.csv`
  - `plan\caiwangcun_dsm_request_coverage_audit.csv`
  - `plan\caiwangcun_coverage_summary.json`
  - `plan\run_gate_summary.json`
- Formal pose outputs:
  - `pose_v1_formal\dsm_cache\rasters\_summary.json`
  - `pose_v1_formal\summary\phase_gate_summary.json`
  - `pose_v1_formal\summary\pose_overall_summary.json`
  - `pose_v1_formal\summary\per_query_best_pose.csv`
- CaiWangCun DOM-truth validation outputs:
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\phase_gate_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\ortho_alignment\overall_ortho_accuracy.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\pose_vs_at\overall_pose_vs_at.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\tiepoint_ground_error\overall_tiepoint_ground_error.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\ortho_alignment\viz_overlay_truth\`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\tiepoint_ground_error\viz_tiepoints\`
- No report outputs were generated for this branch:
  - no satellite-truth suite
  - no comparison report
  - no `.docx` report

## 2026-04-21 CaiWangCun DOM/DSM Full-Replacement Gate Outputs
- Branch root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20\`
- Entry scripts:
  - `scripts\run_nadir_009010_caiwangcun_fullreplace_gate_experiment.py`
  - `scripts\generate_caiwangcun_fullreplace_gate_report.py`
- Source mosaic outputs:
  - `source_mosaic\caiwangcun_ortho_0p14m_epsg32650.tif`
  - `source_mosaic\caiwangcun_dsm_0p14m_epsg32650.tif`
  - `source_mosaic\caiwangcun_mosaic_summary.json`
- CaiWangCun candidate-library outputs:
  - `candidate_library\tiles.csv`
  - `candidate_features\caiwangcun_tile_dinov2_pooler.npz`
  - `candidate_features\caiwangcun_tile_dinov2_status.csv`
  - `faiss\caiwangcun_tiles_ip.index`
  - `faiss\caiwangcun_tiles_ip_mapping.json`
  - `romav2_rerank\coarse\retrieval_top20.csv`
  - `romav2_rerank\coarse\summary_top20.json`
  - `romav2_rerank\stage7\*\reranked_top20.csv`
  - `retrieval\retrieval_top20.csv`
- Formal pose outputs:
  - `pose_v1_formal\dsm_cache\rasters\_summary.json`
  - `pose_v1_formal\manifest\pose_manifest.json`
  - `pose_v1_formal\summary\phase_gate_summary.json`
  - `pose_v1_formal\summary\pose_overall_summary.json`
  - `pose_v1_formal\summary\per_query_best_pose.csv`
- CaiWangCun DOM-truth validation outputs:
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\phase_gate_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\ortho_alignment\overall_ortho_accuracy.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\pose_vs_at\overall_pose_vs_at.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\tiepoint_ground_error\overall_tiepoint_ground_error.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\ortho_alignment\frame_sanity\overall_frame_sanity.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\ortho_alignment\viz_overlay_truth\`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\ortho_alignment\viz_overlay_dom\`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\tiepoint_ground_error\viz_tiepoints\`
- Final report outputs:
  - `reports\caiwangcun_fullreplace_gate_report.docx`
  - `reports\caiwangcun_fullreplace_gate_report.md`
  - `reports\assets\`
- Key result snapshot:
  - `candidate tiles = 149`
  - retrieval Top-20 rows: `800`
  - `recall@1 = 0.675`, `recall@5 = 0.95`, `recall@10 = 0.975`,
    `recall@20 = 0.975`
  - DSM cache: `119/119` built, `failed_count = 0`
  - validation `pipeline_status = ok`
  - layer-1 `center_offset_m mean = 4.393887`,
    `ortho_iou mean = 0.746525`
  - layer-2 `horizontal_error_m mean = 1.8294804`
  - layer-3 `tiepoint_xy_error_rmse_m = 0.3236196`

## 2026-04-22 CaiWangCun DOM/DSM Full-Replacement Full Run Outputs
- Branch root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21\`
- Entry scripts:
  - `scripts\run_nadir_009010_caiwangcun_fullreplace_full_experiment.py`
  - `scripts\generate_caiwangcun_fullreplace_full_report.py`
- Planning and audit outputs:
  - `plan\full_preflight_audit.json`
  - `plan\full_asset_reuse_audit.json`
  - `plan\full_acceptance_summary.json`
  - `plan\full_failure_buckets.csv`
  - `plan\run_full_summary.json`
- Reused/revalidated full-root assets:
  - `source_mosaic\caiwangcun_ortho_0p14m_epsg32650.tif`
  - `source_mosaic\caiwangcun_dsm_0p14m_epsg32650.tif`
  - `candidate_library\tiles.csv`
  - `candidate_features\caiwangcun_tile_dinov2_pooler.npz`
  - `faiss\caiwangcun_tiles_ip.index`
  - `retrieval\retrieval_top20.csv`
  - `romav2_rerank\stage7\*\reranked_top20.csv`
- Full formal pose outputs:
  - `pose_v1_formal\dsm_cache\rasters\_summary.json`
  - `pose_v1_formal\manifest\pose_manifest.json`
  - `pose_v1_formal\matches\roma_matches.csv`
  - `pose_v1_formal\correspondences\pose_correspondences.csv`
  - `pose_v1_formal\sampling\sampled_correspondences.csv`
  - `pose_v1_formal\pnp\pnp_results.csv`
  - `pose_v1_formal\scores\pose_scores.csv`
  - `pose_v1_formal\summary\phase_gate_summary.json`
  - `pose_v1_formal\summary\pose_overall_summary.json`
  - `pose_v1_formal\summary\per_query_best_pose.csv`
- Full CaiWangCun DOM-truth validation outputs:
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\full_run_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\ortho_alignment\overall_ortho_accuracy.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\pose_vs_at\overall_pose_vs_at.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\tiepoint_ground_error\overall_tiepoint_ground_error.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\ortho_alignment\frame_sanity\overall_frame_sanity.json`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\ortho_alignment\viz_overlay_truth\`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\ortho_alignment\viz_overlay_dom\`
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\tiepoint_ground_error\viz_tiepoints\`
- Final report outputs:
  - `reports\caiwangcun_fullreplace_full_report.docx`
  - `reports\caiwangcun_fullreplace_full_report.md`
  - `reports\assets\`
- Key result snapshot:
  - candidate tiles/features/FAISS mapping: `149 / 149 / 149`
  - retrieval Top-20 rows: `800`
  - DSM cache: `119/119` built, `failed_count = 0`
  - full pose best query status: `{ok: 40}`
  - PnP status counts: `{ok: 781, pnp_failed: 19}`
  - validation `pipeline_status = ok`
  - layer-1 `center_offset_m mean = 5.657901`,
    `ortho_iou mean = 0.741115`, evaluated `39/40`
  - layer-2 `horizontal_error_m median = 1.4296165`,
    `p90 = 3.652963`; mean `22.964179` is dominated by `q_037`
  - frame sanity usable-query horizontal error mean: `1.778006` over `39` queries
  - layer-3 `tiepoint_xy_error_rmse_m = 0.413562`;
    status counts `{tiepoint_eval_ok: 39, upstream_eval_failed: 1}`

## 2026-04-22 Layer-3 Tiepoint Coordinate-Difference Details
- Formal layer-3 tiepoint detail output:
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\tiepoint_ground_error\tiepoints\per_query_matches\<query_id>_tiepoints.csv`
- CSV scope:
  - ratio-test matches retained by RANSAC as inliers
  - same point set used for `tiepoint_xy_error_*` metrics
- CSV fields:
  - `query_id`
  - `match_index`
  - `truth_col_px`, `truth_row_px`
  - `pred_col_px`, `pred_row_px`
  - `truth_x_m`, `truth_y_m`
  - `pred_x_m`, `pred_y_m`
  - `dx_m`, `dy_m`, `dxy_m`
- Difference convention:
  - `dx_m = pred_x_m - truth_x_m`
  - `dy_m = pred_y_m - truth_y_m`
  - `dxy_m = sqrt(dx_m^2 + dy_m^2)`
- Full-run audit under
  `D:\aiproject\imagematch\new3output\nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21\`:
  - detail CSV count: `39`
  - successful layer-3 query count: `39`
  - missing detail query: `q_037`
  - failure bucket: `upstream_eval_failed`
- Updated report outputs include this detail-output inventory:
  - `new3output\nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20\reports\caiwangcun_fullreplace_gate_report.docx`
  - `new3output\nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21\reports\caiwangcun_fullreplace_full_report.docx`

## 2026-04-24 009/010 Dual-Route Engineering Report
- Report scope:
  - satellite DOM + SRTM route:
    `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16\`
  - CaiWangCun DOM+DSM full-replacement full run:
    `D:\aiproject\imagematch\new3output\nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21\`
- Generator:
  - `scripts\generate_009010_engineering_word_report.py`
- Final engineering report outputs:
  - `D:\aiproject\imagematch\汇总\009010双线路工程汇报_卫星DOM_SRTM_vs_CaiWangCun_DOMDSM.docx`
  - `D:\aiproject\imagematch\汇总\009010双线路工程汇报_卫星DOM_SRTM_vs_CaiWangCun_DOMDSM.md`
- Report structure:
  - six requested chapters: goal, scheme introduction, data processing flow,
    localization accuracy evaluation methods and metrics, experiment results,
    and runtime statistics
  - representative visualizations embedded in the Word report
- Key result snapshot:
  - SRTM route: `best_status_counts = {ok: 40}`,
    layer-2 `horizontal_error_m mean = 9.723047`,
    layer-3 `tiepoint_xy_error_rmse_m = 2.771818`
  - CaiWangCun route: `best_status_counts = {ok: 40}`,
    layer-1 evaluated `39/40`,
    frame-sanity usable-set `horizontal_error_m mean = 1.778006`,
    layer-3 `tiepoint_xy_error_rmse_m = 0.413562`
- Runtime-scope revision:
  - chapter 6 has been regenerated using only the "including upstream
    retrieval/rerank assets" runtime scope
  - SRTM route total runtime is now reported as approximately `6h47m`, with a
    conservative log-boundary note of approximately `6h50m21s`; the 2026-04-16
    formal/full substage remains recorded as `3h40m05s`
  - CaiWangCun full-replacement route total runtime is now reported as
    approximately `19h18m47s`; the 2026-04-21 full formal/full substage remains
    recorded as `15h18m55s`
  - chapter 6 now includes the shared workstation environment table
- Chapter 7/8 extension:
  - report structure has been expanded to eight formal chapters
  - chapter 7 records the consolidated conclusion and engineering analysis
  - chapter 8 records follow-up ideas and next work directions
  - the chapter 6 runtime scope remains the "including upstream
    retrieval/rerank assets" scope

## 2026-04-24 009/010 Dual-Route Online Timing Report
- Output:
  - `D:\aiproject\imagematch\汇总\时间统计.md`
- Generator:
  - `scripts\generate_009010_timing_report.py`
- Source routes:
  - SRTM upstream DINOv2/RoMa assets:
    `D:\aiproject\imagematch\new2output\nadir_009010_dinov2_romav2_pose_2026-04-10\`
  - SRTM formal pose:
    `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16\`
  - CaiWangCun full-replacement gate assets:
    `D:\aiproject\imagematch\new3output\nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20\`
  - CaiWangCun full formal pose:
    `D:\aiproject\imagematch\new3output\nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21\`
- Contents:
  - online-localization timing for DINOv2 query feature extraction, Top-20
    retrieval, RoMa v2 rerank, pose matches export, PnP data preparation, DSM
    sampling, PnP solving, and best-pose scoring
  - current actual per-query timing and deduplicated per-query estimate
  - RoMa v2 model-loading behavior and repeated-computation analysis
- Key values:
  - SRTM RoMa rerank: `11156.613s`
  - CaiWangCun RoMa rerank: `13617.368s`
  - SRTM pose matches export: `8985.443s`
  - CaiWangCun pose matches export: `9898.979s`
  - SRTM DSM sampling: `3262.850s`
  - CaiWangCun DSM sampling: `9274.061s`
## 2026-04-27 new4 Gate Speed-Optimization Matrix G01 Baseline
- Output root:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G01_baseline_current_pipeline/`
- Experiment plan:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G01_baseline_current_pipeline/实验计划.md`
- Root summaries:
  - `timing_summary.json`
  - `accuracy_summary.json`
  - `acceptance_summary.json`
- Key run outputs:
  - `retrieval/retrieval_top20.csv`
  - `romav2_rerank/timing/romav2_rerank_internal.json`
  - `pose_v1_formal/matches/roma_matches.csv`
  - `pose_v1_formal/correspondences/pose_correspondences.csv`
  - `pose_v1_formal/sampling/sampled_correspondences.csv`
  - `pose_v1_formal/pnp/pnp_results.csv`
  - `pose_v1_formal/summary/phase_gate_summary.json`
  - `pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/phase_gate_summary.json`
- Acceptance:
  - `accepted = true`
  - best pose `5/5 ok`
  - PnP rows `100`
  - sampling rows `500000`
  - validation pipeline `ok`
- Baseline metrics:
  - RoMa rerank `1617.055s`
  - pose-stage RoMa matches export `1412.034s`
  - DSM sampling `162.278s`
  - Layer-2 horizontal error mean `2.642712m`
  - Layer-3 tiepoint XY RMSE `0.504878m`

## 2026-04-27 new4 Gate Speed-Optimization Matrix G02 Engineering Pipeline
- Output root:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G02_pipeline_engineering_reuse_domz_parallel_sampling/`
- Experiment plan:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G02_pipeline_engineering_reuse_domz_parallel_sampling/实验计划.md`
- Root summaries:
  - `timing_summary.json`
  - `accuracy_summary.json`
  - `acceptance_summary.json`
  - `compare_against_G01_summary.json`
- Key outputs:
  - `romav2_rerank/stage7/*/roma_matches_for_pose.csv`
  - `pose_v1_formal/matches/roma_matches_reused_from_rerank.csv`
  - `pose_v1_formal/domz_cache/domz_point_cache.csv`
  - `pose_v1_formal/sampling/sampling_summary.json`
- Result:
  - main pipeline completed and validation pipeline is `ok`
  - `accepted = false` under strict equivalence checks
  - best pose `5/5 ok`
  - PnP status `{ok: 98, pnp_failed: 2}`
  - sampling status `{ok: 499809, nodata: 65, unstable_local_height: 126}`
  - Layer-2 horizontal error mean `2.072707m`
  - Layer-3 tiepoint XY RMSE `0.498889m`
  - second RoMa export removed; DOM+Z online sampling reduced to `19.643s`

## 2026-04-27 new4 Gate Speed-Optimization Matrix G03 SIFTGPU Replacement
- Output root:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G03_pipeline_siftgpu_replace_roma/`
- Experiment plan:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G03_pipeline_siftgpu_replace_roma/实验计划.md`
- Environment check:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G03_pipeline_siftgpu_replace_roma/plan/siftgpu_env_check.json`
- Root summaries:
  - `timing_summary.json`
  - `accuracy_summary.json`
  - `acceptance_summary.json`
  - `compare_against_G02_summary.json`
- Result:
  - `accepted = true`
  - formal G03 gate completed after installing dependencies and building local
    SiftGPU.
  - local SiftGPU pair matcher:
    `third_party/SiftGPU/bin/siftgpu_pair_match`
  - COLMAP GPU SIFT remains unavailable in WSL, so it is not used for the
    formal G03 result.
- Key metrics:
  - retrieval Top-20 rows: `100`
  - SIFTGPU match rows / sampling rows: `21218`
  - sampling status `{ok: 21208, unstable_local_height: 1, nodata: 9}`
  - PnP status `{ok: 39, pnp_failed: 61}`
  - best pose `5/5 ok`
  - validation pipeline `ok`
  - SIFTGPU rerank `580.830s`
  - Layer-2 horizontal error mean `2.053060m`
  - Layer-3 tiepoint XY RMSE `0.417440m`
- Comparison note:
  - G03 is faster than G02 in geometry rerank, but candidate-level PnP
    robustness drops from G02 `{ok: 98, pnp_failed: 2}` to G03
    `{ok: 39, pnp_failed: 61}`.

## 2026-04-28 new4 Gate Speed-Optimization Matrix G04 Downsample Sweep
- Output root:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G04_downsample_resolution_sweep/`
- Experiment plan:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G04_downsample_resolution_sweep/实验计划.md`
- Subgroups:
  - `G04A_downsample_0p5m/`
  - `G04B_downsample_1p0m/`
- Aggregate outputs:
  - `aggregate_resolution_sweep_summary.json`
  - `aggregate_resolution_sweep_summary.csv`
- G04A root summaries:
  - `G04A_downsample_0p5m/timing_summary.json`
  - `G04A_downsample_0p5m/accuracy_summary.json`
  - `G04A_downsample_0p5m/acceptance_summary.json`
  - `G04A_downsample_0p5m/compare_against_G02_summary.json`
- G04B root summaries:
  - `G04B_downsample_1p0m/timing_summary.json`
  - `G04B_downsample_1p0m/accuracy_summary.json`
  - `G04B_downsample_1p0m/acceptance_summary.json`
  - `G04B_downsample_1p0m/compare_against_G02_summary.json`
- G04A result:
  - `accepted = true` under loose completion checks
  - retrieval Top-20 rows `100`
  - matches/sampling rows `500000`
  - PnP status `{ok: 100}`
  - best pose gate queries `5/5 ok`
  - validation pipeline `ok`
  - RoMa rerank `3720.388s`
  - Layer-2 horizontal error mean `6.039019m`
  - Layer-3 tiepoint XY RMSE `441.898506m`
- G04B result:
  - `accepted = false`
  - failure reason `romav2_rerank_timeout_or_cpu_fallback`
  - first-flight RoMa rerank was terminated after more than two hours with
    0-byte stage7 output CSVs and no visible GPU process
- Conclusion:
  - the G04 downsample variants do not beat G02: `0.5 m/pix` damages geometry
    accuracy badly and `1.0 m/pix` is not operationally usable in this run.

## 2026-04-28 new4 Gate Speed-Optimization Matrix G05 Top-20 Pruning Posthoc
- Output root:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G05_top20_pruning_posthoc_analysis/`
- Experiment plan:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G05_top20_pruning_posthoc_analysis/实验计划.md`
- Analysis script:
  `scripts/analyze_new4_g05_top20_pruning_posthoc.py`
- Inputs:
  - `G02_pipeline_engineering_reuse_domz_parallel_sampling/`
  - `G03_pipeline_siftgpu_replace_roma/`
- Outputs:
  - `candidate_match_distribution_g02.csv`
  - `candidate_match_distribution_g03.csv`
  - `pruning_simulation_per_query.csv`
  - `compare_g02_g03_topk_pruning.csv`
  - `pruning_simulation_summary.json`
  - `pruning_simulation_summary.md`
- Result:
  - G05 completed as a pure posthoc analysis with no rerun of matching, PnP,
    DSM sampling, or validation.
  - data quality warnings: none.
- Key findings:
  - G02 RoMa `inlier_count_top1/top3/top5` does not pass the strict pruning
    criteria; Top-5 retains truth for `5/5` queries but final best-pose
    candidate for only `1/5`.
  - G03 SIFTGPU `inlier_count_top5` passes the strict criteria; `top1` and
    `top3` do not.
  - G03 SIFTGPU `match_count_top1` passes in this gate analysis, but this is
    not transferable to G02 because RoMa match counts are not a discriminative
    candidate-quality signal in the same way.
  - coarse raw ranking needs Top-10, not Top-1/3/5, to satisfy all strict
    checks in both source groups.
- Conclusion:
  - universal Top-1 pruning is not supported.
  - skipping geometry rerank or Top-20 retrieval is not supported by G05.
  - a follow-up pruning experiment should be algorithm-specific rather than a
    shared G02/G03 rule.

## 2026-04-28 new4 Gate Speed-Optimization Matrix G06 Top-1 Pose Validation
- Output root:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G06_top1_match_count_pose_reprojection_validation/`
- Experiment plan:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G06_top1_match_count_pose_reprojection_validation/实验计划.md`
- Wrapper:
  `scripts/run_new4_g06_top1_match_count_pose_reprojection_validation.py`
- Root outputs:
  - `top1_candidate_selection.csv`
  - `top1_pose_validation_summary.csv`
  - `top1_pose_validation_summary.json`
  - `compare_against_g02_g03_summary.json`
  - `top1_pose_validation_report.md`
- Subgroups:
  - `G06A_g02_roma_inlier_top1/`
  - `G06B_g03_siftgpu_inlier_top1/`
  - `G06C_g03_siftgpu_match_top1/`
- Result:
  - G06A/G06B/G06C each produced `5` selected Top-1 candidates.
  - PnP status for all three subgroups: `{ok: 5}`.
  - best-pose status for all three subgroups: `{ok: 5}`.
  - Layer-2 horizontal error mean:
    - G06A `2.288524m`
    - G06B `3.073294m`
    - G06C `2.053060m`
  - Layer-3 tiepoint summaries were not produced because validation timed out
    during `evaluate_pose_ortho_tiepoint_ground_error`.
  - G06C was retried separately with a 3600s validation limit and still timed
    out in Layer-3.
- Conclusion:
  - reduced Top-1 PnP is runnable, but no Top-1 strategy is accepted as a full
    replacement because the required Layer-3 validation did not complete.
  - G06C is the strongest follow-up candidate because it preserves G03 Layer-2
    performance, but it still needs a bounded Layer-3 validation path before it
    can be treated as a usable speed optimization.

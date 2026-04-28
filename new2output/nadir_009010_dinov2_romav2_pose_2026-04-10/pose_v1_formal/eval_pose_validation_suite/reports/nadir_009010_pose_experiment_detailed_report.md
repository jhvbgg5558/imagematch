# 009/010 下视 Query DINOv2 + RoMa v2 + DOM/DSM/PnP 实验详细记录

## 1. 实验背景与目标

本次实验是在已有 `DINOv2 coarse + RoMa v2 + DOM/DSM/PnP` 主链路基础上，重新约束 query 选择范围后，对无人机图像初始地理定位能力做一次更严格、更聚焦的验证。

本次调整的核心点有三条：

1. 不再混用多条航线，只使用两条近下视/真下视航线：
   - `DJI_202510311347_009_新建面状航线1`
   - `DJI_202510311413_010_新建面状航线1`
2. query 选择固定为 `gimbal_pitch_degree <= -85.0`，即近下视/真下视条件。
3. 每条航线固定选择 `20` 张 query，总计 `40` 张，形成一个 isolated 的正式实验根目录。

实验的核心目标不是单看 retrieval 命中，而是完整验证：

- 下视 query 经过 `DINOv2 coarse` 和 `RoMa v2 rerank` 后，能否得到稳定的 Top-20 候选；
- 候选进入 `DOM/DSM/PnP` 后，能否为每个 query 解算出有效 `best pose`；
- 最终 `best pose` 在三层验证口径下是否一致地支持“定位精度可接受”这个结论。

本次实验根目录固定为：

- `D:\aiproject\imagematch\new2output\nadir_009010_dinov2_romav2_pose_2026-04-10\`


## 2. 实验范围与输入约束

### 2.1 query 范围

本次实验只使用两条航线：

- 009 航线：`DJI_202510311347_009_新建面状航线1`
- 010 航线：`DJI_202510311413_010_新建面状航线1`

query 选择约束：

- `gimbal_pitch_degree <= -85.0`
- 每条航线选 `20` 张
- 总计 `40` 张

query 编号规则固定：

- 009 航线：`q_001` 到 `q_020`
- 010 航线：`q_021` 到 `q_040`

对应选择结果文件：

- `selected_queries/selected_images_summary.csv`

本次实际统计结果：

- 总 query 数：`40`
- 009 count：`20`
- 010 count：`20`
- 所有 query 满足 `gimbal_pitch_degree <= -85.0`

### 2.2 runtime 与评估边界

本次实验严格区分 runtime 和 offline evaluation：

- runtime candidate 选择只由 `DINOv2 coarse -> RoMa v2 rerank` 决定；
- `query truth` 只用于离线评估和 manifest audit 字段；
- truth 不进入 runtime candidate 选择逻辑；
- RoMa 导出的 pose candidate `score` 固定等于 `fused_score`。

### 2.3 资产复用约束

本次不重建卫星库，只复用已有 DINOv2 固定卫星资产：

- 固定卫星库 `tiles.csv`
- 卫星特征
- FAISS index

复用来源：

- `output/coverage_truth_200_300_500_700_dinov2_baseline/`

本次只重建 query 侧资产和后续 pose / validation 资产。


## 3. 实验目录结构

本次实验根目录下的重要子目录如下：

- `selected_queries/`
- `query_inputs/`
- `query_truth/`
- `query_features/`
- `retrieval/`
- `romav2_rerank/`
- `pose_v1_formal/`
- `pose_v1_formal/eval_pose_validation_suite/`
- `reports/`
- `scripts/`
- `logs/`
- `plan/`

其中与最终定位精度结论最相关的是：

- `retrieval/retrieval_top20.csv`
- `pose_v1_formal/pnp/pnp_results.csv`
- `pose_v1_formal/summary/per_query_best_pose.csv`
- `pose_v1_formal/eval_pose_validation_suite/`


## 4. 实验流程

### 4.1 query 重新选择

本次首先按 DJI XMP 中的 `gimbal_pitch_degree` 重新筛选 query，只保留近下视/真下视图像。  
选择逻辑要求在满足 pitch 约束的前提下，优先选择更接近 `-90` 度的图像，同时保持 frame、GPS、yaw 的分散性。

对应脚本：

- `scripts/select_nadir_uav_queries.py`

输出：

- `selected_queries/selected_images_summary.csv`

这一步的目的是先把 query 条件缩小到更可控的近下视场景，避免混入大视角变化样本，从而更清楚地观察 pose 链路在 nadir 条件下的上限表现。

### 4.2 query 去元数据与 truth 构造

原始 query 在进入模型链路前先做去元数据处理，确保后续模型和 pose 求解不会依赖保留下来的 EXIF / XMP / GPS 信息。

输出：

- `query_inputs/query_manifest.csv`

随后构造 query truth：

- `query_truth/queries_truth_seed.csv`
- `query_truth/query_truth.csv`
- `query_truth/query_truth_tiles.csv`

这里的 truth 只用于后续评估，不参与 runtime 检索和 candidate 决策。

### 4.3 DINOv2 coarse retrieval

对新选出来的 40 张 query 提取 DINOv2 特征，只构建 query 侧特征，不重建卫星库。

输出：

- `query_features/query_dinov2_pooler.npz`

在固定卫星库和 FAISS index 上执行 coarse Top-20 检索，得到：

- `romav2_rerank/coarse/retrieval_top20.csv`

本次 coarse Top-20 总行数：

- `800`

也就是 `40 query x 20 candidates`。

### 4.4 RoMa v2 rerank

在 DINOv2 coarse Top-20 基础上，执行 RoMa v2 交叠/匹配能力驱动的 rerank。

输出位于：

- `romav2_rerank/stage7/<flight_id>/reranked_top20.csv`
- `romav2_rerank/stage7/<flight_id>/rerank_top20.json`

本次 rerank 结果：

- 009 航线：`400` 行
- 010 航线：`400` 行
- 合计：`800` 行

后续再将 rerank Top-20 导出为 pose 输入使用的统一 retrieval 文件：

- `retrieval/retrieval_top20.csv`

输出字段兼容 formal pose candidate manifest，且 `score` 固定取 `fused_score`。

### 4.5 DOM/DSM/PnP pose 求解

在 retrieval Top-20 基础上，构建 formal pose 输入：

- formal query manifest
- formal candidate manifest
- asset validation report
- pose manifest
- DSM cache request / raster

随后进入 formal pose 主链路：

1. RoMa matches
2. pose correspondences
3. sampled correspondences
4. PnP
5. score
6. per-query best pose summary

本次正式输出位于：

- `pose_v1_formal/matches/`
- `pose_v1_formal/correspondences/`
- `pose_v1_formal/sampling/`
- `pose_v1_formal/pnp/`
- `pose_v1_formal/scores/`
- `pose_v1_formal/summary/`

### 4.6 三层验证与报告

在 `best pose` 基础上执行统一三层验证：

1. layer-1：predicted ortho vs UAV truth ortho
2. layer-2：best pose vs ODM/AT reference pose
3. layer-3：predicted ortho vs truth ortho tiepoint XY ground error

统一输出根目录：

- `pose_v1_formal/eval_pose_validation_suite/`

并进一步生成：

- figures
- Word 报告
- 定位精度评估报告


## 5. 关键中间产物与规模

### 5.1 query / retrieval 规模

- selected query：`40`
- query manifest：`40`
- DINOv2 coarse Top-20：`800`
- RoMa rerank Top-20：`800`
- pose retrieval Top-20：`800`

### 5.2 pose 运行规模

formal pose 运行后得到：

- `matches/roma_matches.csv`：`1,600,000` 行
- `correspondences/pose_correspondences.csv`：`1,600,000` 行
- `sampling/sampled_correspondences.csv`：`1,600,000` 行
- `pnp/pnp_results.csv`：`800` 行
- `scores/pose_scores.csv`：`800` 行
- `summary/per_query_best_pose.csv`：`40` 行

### 5.3 PnP 状态

`pnp/pnp_summary.json` 给出的状态统计：

- `ok = 734`
- `pnp_failed = 66`

虽然不是全部 800 对都成功解出 PnP，但在 per-query 选择最佳候选后：

- `best_status_counts = {ok: 40}`
- `best_ok_rate = 1.0`

也就是 40 个 query 最终都得到了可用的 `best pose`。


## 6. 三层验证内容与结果

### 6.1 Layer-1：正射套合

这一层验证的是：

- `best pose` 投影到 truth ortho 之后，
- predicted ortho 与 UAV truth ortho 在平面上是否稳定套合。

核心指标：

- `phase_corr_error_m`
- `center_offset_m`
- `ortho_iou`
- `ssim`

本次结果：

- `query_count = 40`
- `evaluated_query_count = 40`
- `eval_status_counts = {ok: 40}`
- `phase_corr_error_m mean = 0.7672`
- `phase_corr_error_m median = 0.4317`
- `phase_corr_error_m p90 = 2.0462`
- `center_offset_m mean = 13.1874`
- `ortho_iou mean = 0.7289`
- `ssim mean = 0.5958`

解释：

- `phase_corr_error_m` 处于较低水平，说明在当前下视场景下，`best pose` 对应的整体平面定位已经比较稳定；
- `center_offset_m` 作为辅助指标保留，但不单独作为最终精度结论依据；
- `ortho_iou` 和 `ssim` 提供了重投影后的图像重叠与结构相似性支撑。

### 6.2 Layer-2：pose vs ODM/AT

这一层验证的是：

- `best pose` 相对 ODM/AT 参考外参的偏差；
- 这不是绝对真值，而是对外参与位置偏差的相对诊断。

核心指标：

- `horizontal_error_m`
- `spatial_error_m`
- `view_dir_angle_error_deg`
- `yaw_error_deg`
- `pitch_error_deg`
- `roll_error_deg`

本次结果：

- `query_count = 40`
- `evaluated_query_count = 40`
- `eval_status_counts = {ok: 40}`
- `horizontal_error_m mean = 9.1654`
- `horizontal_error_m median = 7.6759`
- `horizontal_error_m p90 = 16.2847`
- `view_dir_angle_error_deg mean = 1.2706`
- `view_dir_angle_error_deg median = 1.0893`
- `view_dir_angle_error_deg p90 = 2.3670`

### 6.3 layer-2 动态高亮异常 query

之前 figures 脚本里曾写死高亮 `q_022`，但这对本次 `009/010` 实验是不正确的。  
在修正脚本后，当前 figures 会动态选择 `horizontal_error_m` 最大的 query 作为高亮点。

当前 figure manifest 中记录的动态高亮 query 为：

- `q_012`
- `horizontal_error_m = 27.3721 m`
- `view_dir_angle_error_deg = 3.9337 deg`

这说明当前最显著的 layer-2 outlier 不是历史模板里的 `q_022`，而是本次真实结果中的 `q_012`。

### 6.4 Layer-3：tiepoint ground error

这一层验证的是：

- predicted ortho 与 truth ortho 的局部对应点，
- 在地面 XY 坐标系下的几何一致性。

核心指标：

- `tiepoint_xy_error_mean_m`
- `tiepoint_xy_error_median_m`
- `tiepoint_xy_error_rmse_m`
- `tiepoint_xy_error_p90_m`
- `tiepoint_match_count_mean`
- `tiepoint_inlier_ratio_mean`

本次结果：

- `query_count = 40`
- `evaluated_query_count = 40`
- `matchable_query_count = 40`
- `eval_status_counts = {tiepoint_eval_ok: 40}`
- `tiepoint_xy_error_mean_m = 2.4473`
- `tiepoint_xy_error_median_m = 2.0942`
- `tiepoint_xy_error_rmse_m = 2.8552`
- `tiepoint_xy_error_p90_m = 4.3476`
- `tiepoint_match_count_mean = 1393.6750`
- `tiepoint_inlier_ratio_mean = 0.8521`

解释：

- 这一层说明当前 pose 解算结果不只是全局位置近似正确，在局部几何层面也保持了较好的稳定性；
- `tiepoint_xy_error_rmse_m` 和 `p90` 为本次正式精度口径提供了重要支撑。


## 7. 分航线对比

本次 009 与 010 两条航线都进入了完整链路，但它们的误差分布并不完全相同。  
分航线 figures 和 per-flight CSV 提供了进一步的对比依据，主要包括：

- 每条航线的 `horizontal_error_m_mean`
- 每条航线的 `view_dir_angle_error_deg_mean`
- 每条航线的 `phase_corr_error_m_mean`
- 每条航线的 `tiepoint_xy_error_rmse_m`

这些结果已经在：

- `pose_vs_at/per_flight_pose_vs_at.csv`
- `ortho_alignment/per_flight_ortho_accuracy.csv`
- `tiepoint_ground_error/per_flight_tiepoint_ground_error.csv`
- `pose_vs_at/figures/figure_5_per_flight_pose_error.png`

中固定保存，可用于后续进一步分析哪条航线更稳定、哪条航线更容易出现局部 outlier。


## 8. 最终报告与图表产物

本次实验已经生成以下正式报告和说明材料：

### 8.1 Word 报告

- `formal_pose_v1_validation_suite_report.docx`
- `定位精度评估报告.docx`

### 8.2 Markdown 报告

- `validation_suite_summary.md`
- `nadir_009010_pose_experiment_detailed_report.md`（本文件）

### 8.3 图表输出

位于：

- `pose_vs_at/figures/`

包含：

- `figure_1_position_error_distribution.png`
- `figure_2_orientation_error_distribution.png`
- `figure_3_per_query_horizontal_error.png`
- `figure_4_per_query_view_dir_error.png`
- `figure_5_per_flight_pose_error.png`
- `figure_6_dx_dy_scatter.png`
- `figure_7_horizontal_vs_viewdir_scatter.png`
- `figure_8_reference_source_status.png`
- `README.md`
- `figure_manifest.json`


## 9. 本次实验结论

基于当前 `009/010` 近下视 query 子集，本次实验可以得出以下结论：

1. `DINOv2 coarse -> RoMa v2 rerank -> DOM/DSM/PnP` 这条链路在下视场景下可以形成稳定闭环。
2. 尽管 800 个 query-candidate 对中有部分 PnP 失败，但 40 个 query 最终都获得了可用的 `best pose`，说明候选排序和 best-pose 选择是有效的。
3. layer-1、layer-2、layer-3 三层指标没有出现明显相互冲突的信号，说明结论不是单一指标偶然支撑的。
4. 在本次严格限制为 `gimbal_pitch_degree <= -85.0` 的近下视条件下，定位精度表现明显优于之前混合航线、混合俯仰角时的历史异常情况。
5. 当前 layer-2 图表中的异常点已经改为按真实结果动态选择，不再受历史固定 `q_022` 模板影响。


## 10. 后续建议

后续如果要继续推进，应优先做三件事：

1. 继续分析 `q_012` 这类当前真实 outlier，定位其误差来源是纹理重复、DOM/DSM 局部高差还是视角几何问题；
2. 在保持当前 isolated 根目录不变的前提下，逐步放宽 `gimbal_pitch_degree`，形成按 pitch bucket 的对照实验；
3. 将当前这套对下视场景有效的流程，和“单张 arbitrary UAV image”主任务明确区分，不要直接把 nadir 结论外推到全场景。


## 11. 关键文件索引

- 实验根目录：
  - `D:\aiproject\imagematch\new2output\nadir_009010_dinov2_romav2_pose_2026-04-10\`
- validation suite 根目录：
  - `D:\aiproject\imagematch\new2output\nadir_009010_dinov2_romav2_pose_2026-04-10\pose_v1_formal\eval_pose_validation_suite\`
- 详细 figures 目录：
  - `D:\aiproject\imagematch\new2output\nadir_009010_dinov2_romav2_pose_2026-04-10\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures\`
- formal validation Word 报告：
  - `D:\aiproject\imagematch\new2output\nadir_009010_dinov2_romav2_pose_2026-04-10\pose_v1_formal\eval_pose_validation_suite\reports\formal_pose_v1_validation_suite_report.docx`
- 定位精度评估报告：
  - `D:\aiproject\imagematch\new2output\nadir_009010_dinov2_romav2_pose_2026-04-10\pose_v1_formal\eval_pose_validation_suite\reports\定位精度评估报告.docx`

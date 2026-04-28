# CaiWangCun DOM/DSM 完整替换 Gate 实验报告

## 1. 实验目的
本次实验验证：在 query、DINOv2、RoMa v2、PnP 和 validation 算法参数保持不变的前提下，将所有绑定旧候选库的资产完整替换为 CaiWangCun 0.14m DOM/DSM 资产后，predicted ortho 是否从前两个不完整替换分支中的大偏移、倾斜和大面积黑框现象恢复正常。

核心判断是区分 DSM 质量问题、单视角覆盖问题、pose 问题和候选库/坐标框架混用问题。本轮 gate 只验证 5 个 sample query，不扩大到 full run。

## 2. 评估方法和评估指标
- Retrieval：用 Top-1/5/10/20 intersection recall 和 MRR 评估 CaiWangCun candidate library 对 40 张 query 的粗检索覆盖能力。
- DSM/Pose gate：检查 DSM cache build 成功率、2D-3D sampling 状态、PnP 状态、best pose score、inlier ratio 和 reprojection error。
- Layer-1 Ortho alignment：将 predicted ortho 与 CaiWangCun DOM truth 在同一 truth grid 上比较，重点看 center_offset_m、ortho_iou、SSIM 和有效像素比例。
- Layer-2 Pose vs AT：将 best pose 与 AT/query reference pose 比较，重点看 horizontal_error_m 和 view_dir_angle_error_deg。
- Layer-3 Tiepoint：在 predicted ortho 与 truth ortho 之间做局部 tiepoint ground error，重点看 RMSE、match count 和 inlier ratio。
- Frame sanity：检查 DSM valid ratio、pred valid pixel ratio、camera/bbox offset 和 truth-to-footprint area ratio，用于解释黑框、偏移和单视角覆盖。

## 3. 实验流程与数据准备
本轮是完整替换：复用 009/010 的 40 张 query 与 query features，但 CaiWangCun DOM/DSM mosaic、candidate tile library、candidate DINOv2 features、FAISS index、retrieval Top20、RoMa v2 rerank、formal manifests、DSM cache、pose manifest、gate pose 和 validation 输出均重新生成。不使用 ODM LAZ 或 SRTM fallback。

### 3.1 数据资产
|资产|CRS|波段数|类型|分辨率/说明|
|---|---:|---:|---:|---:|
|DOM mosaic|EPSG:32650|3|uint8,uint8,uint8|0.140046|
|DSM mosaic|EPSG:32650|1|float32|0.140046|
|Candidate tiles|149|200/300/500/700m|fully-covered only|{'outside_roi': 77, 'not_fully_covered': 233, 'empty_window': 0}|

## 4. 实验结果
### 4.1 Retrieval
|指标|数值|
|---|---:|
|query_count|40|
|retrieval_top20_rows|800|
|intersection_recall@1|0.6750|
|intersection_recall@5|0.9500|
|intersection_recall@10|0.9750|
|intersection_recall@20|0.9750|
|intersection_mrr|0.7836|

![图 1. CaiWangCun candidate library 的 DINOv2 Top-K retrieval 指标。](assets/retrieval_recall.png)

*图 1. CaiWangCun candidate library 的 DINOv2 Top-K retrieval 指标。*

### 4.2 DSM 与 Pose Gate
|环节|规模|状态|质量|
|---|---:|---|---|
|DSM cache|planned=119|built=119|failed=0|
|2D-3D sampling|rows=500000|ok=499786, nodata=92, unstable_local_height=122||
|PnP|rows=100|ok=97, pnp_failed=3||
|Best pose|scored_query_count=5|ok=5, missing_pnp_rows=35||
|Best quality|score_mean=0.7358|inlier_ratio_mean=0.8548|reproj_error_mean=2.3614|

![图 2. 2D-3D sampling 状态分布。](assets/sampling_status.png)

*图 2. 2D-3D sampling 状态分布。*


![图 3. PnP candidate 状态分布。](assets/pnp_status.png)

*图 3. PnP candidate 状态分布。*

### 4.3 三层 validation 与 frame sanity
|评估层|规模/状态|核心结果 1|核心结果 2|
|---|---|---|---|
|pipeline_status|ok|||
|Layer-1 ortho|eval=5/5|center_offset_mean=4.394m|ortho_iou_mean=0.7465|
|Layer-2 pose|eval=5/5|horizontal_error_mean=1.829m|view_dir_error_mean=0.273deg|
|Layer-3 tiepoint|eval=5/5|RMSE=0.324m|inlier_ratio_mean=0.9539|
|Layer-3 tiepoint CSV|files=5/5|missing=-|scope=RANSAC inliers|
|Frame sanity|ok_or_manual_review=5|DSM valid=99.77%|Pred valid=74.65%|

![图 4. Layer-1/2/3 关键几何误差。](assets/layer_metrics.png)

*图 4. Layer-1/2/3 关键几何误差。*


![图 5. Frame sanity 的 DSM/predicted coverage 与 offset 指标。](assets/frame_sanity.png)

*图 5. Frame sanity 的 DSM/predicted coverage 与 offset 指标。*

Layer-1 center_offset_m mean 为 4.394 m，ortho_iou mean 为 0.7465；Layer-2 horizontal_error_m mean 为 1.829 m；Layer-3 tiepoint RMSE 为 0.324 m。
Frame sanity 中 DSM valid ratio mean 为 99.77%，pred valid pixel ratio mean 为 74.65%，说明黑框不是 DSM 大面积 nodata 引起，predicted ortho 的有效覆盖已回到正常范围。

### Layer-3 tiepoint detail CSV
- Per-query detail dir: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/tiepoint_ground_error/tiepoints/per_query_matches`
- Scope: ratio-test matches retained by RANSAC inliers only, same as formal tiepoint RMSE.
- File pattern: `<query_id>_tiepoints.csv`; generated files: `5/5` ok queries.
- Fields: `query_id, match_index, truth_col_px, truth_row_px, pred_col_px, pred_row_px, truth_x_m, truth_y_m, pred_x_m, pred_y_m, dx_m, dy_m, dxy_m`
- Queries without detail CSV: `-`

### 4.4 代表性可视化

![图 6. q_003 predicted ortho 与 truth ortho overlay。](assets/q_003_truth_overlay.jpg)

*图 6. q_003 predicted ortho 与 truth ortho overlay。*


![图 7. q_003 predicted ortho 与 CaiWangCun DOM overlay。](assets/q_003_dom_overlay.jpg)

*图 7. q_003 predicted ortho 与 CaiWangCun DOM overlay。*


![图 8. q_003 tiepoint overlay。](assets/q_003_tiepoints_overlay.jpg)

*图 8. q_003 tiepoint overlay。*


![图 9. q_003 frame sanity overlay。](assets/q_003_frame_overlay.png)

*图 9. q_003 frame sanity overlay。*


![图 10. q_003 frame sanity offset vectors。](assets/q_003_offset_vectors.png)

*图 10. q_003 frame sanity offset vectors。*


![图 11. q_003 DSM valid mask on truth grid。](assets/q_003_dsm_valid_mask_on_truth_grid.png)

*图 11. q_003 DSM valid mask on truth grid。*


### 4.5 与前两个 CaiWangCun 不完整替换分支对比

![图 12. 前两个不完整替换分支与完整替换 gate 的偏移指标对比。](assets/caiwangcun_branch_offset_comparison.png)

*图 12. 前两个不完整替换分支与完整替换 gate 的偏移指标对比。*

前两个 CaiWangCun 分支仍有约 515 m 的 center_offset 和约 648-652 m 的 horizontal_error。本轮完整替换后，center_offset_m mean 降至 4.39 m，horizontal_error_m mean 降至 1.83 m，说明主要问题来自旧 candidate/retrieval/rerank 资产与新 DOM/DSM 混用，而不是 CaiWangCun DSM 自身不可用。

## 5. 结论与结果分析
- 本轮 gate 通过：validation pipeline_status=ok，Layer-1/2/3 均完成 5/5 query，frame_sanity 诊断为 ok_or_manual_review=5。
- DSM 支撑正常：DSM cache failed_count=0，truth grid 上 DSM valid ratio mean=99.77%，sampling nodata 仅 92/500000。
- predicted ortho 恢复正常：有效像素比例约 74.65%，不再只落在整图小角落；几何偏移从 500m 级降到米级。
- 结果支持当前解释：前两个分支的倾斜和大面积黑框不是单纯 DSM nodata，而是候选库/检索/重排资产没有随 CaiWangCun DOM 完整重建，导致候选图像、DSM、truth grid 和 pose reference 框架不一致。

## 6. 后续想法
- 可以规划 full run，但应先把当前 gate 的 5 个 query 可视化做人工抽查，确认道路和建筑没有系统性扭曲。
- full run 前建议保留 frame_sanity 输出，并扩展到全部 40 张 query，用于识别边界覆盖不足和个别 query 的视觉异常。
- 若 full run 中个别 query 出现偏移，应优先检查该 query 的 retrieval rank、RoMa inlier ratio、candidate tile 尺度和 DSM footprint，而不是回退到 ODM LAZ/SRTM。
- 后续正式实验应将“完整替换候选库派生资产”写入协议，避免再次出现半替换导致的坐标框架混用。

## 附录
- 实验根目录：`/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20`
- Validation 根目录：`/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth`
- 本轮不生成 satellite truth suite，不生成 comparison report，不使用 ODM LAZ/SRTM fallback。
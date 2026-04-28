# CaiWangCun DOM/DSM 完整替换 Full Run 实验报告

## 1. 实验目的
本次 full run 将 gate 已验证的 CaiWangCun DOM/DSM 完整替换口径扩展到全部 40 张 009/010 query，验证该路线在全量 query 上是否仍保持米级定位误差和正常 predicted ortho 覆盖。

## 2. 实验流程
Full run 使用独立目录，不覆盖 gate。CaiWangCun mosaic、candidate library、candidate features、FAISS、retrieval 和 RoMa rerank 从 gate 复制并做路径重写与审计；formal input、DSM cache、pose manifest、full pose、full validation 和 frame sanity 在 full root 下重新生成。

## 3. Full Pose 结果
|指标|数值|
|---|---:|
|query_count|40|
|scored_query_count|40|
|best_status_counts|ok=40|
|score_status_counts|ok=781, pnp_failed=19|
|best_score_mean|0.7445|
|best_success_inlier_ratio_mean|0.8564|
|best_success_reproj_error_mean|2.4450|

![图 1. Full run best pose status。](assets/pose_best_status.png)

*图 1. Full run best pose status。*


## 4. Full Validation 结果
|指标|数值|
|---|---:|
|pipeline_status|ok|
|Layer-1 center_offset_m mean|5.658 m|
|Layer-1 ortho_iou mean|0.7411|
|Layer-2 horizontal_error_m mean|22.964 m|
|Layer-2 view_dir_angle_error_deg mean|2.028 deg|
|Layer-3 tiepoint RMSE|0.414 m|
|Layer-3 per-query tiepoint CSV|39/39 ok-query files|
|Layer-3 missing detail query|q_037|
|Frame DSM valid ratio mean|99.88%|
|Frame pred valid pixel ratio mean|74.11%|

![图 2. Full run Layer-1/2/3 几何指标。](assets/full_validation_metrics.png)

*图 2. Full run Layer-1/2/3 几何指标。*


![图 3. Full run frame sanity 指标。](assets/full_frame_sanity.png)

*图 3. Full run frame sanity 指标。*


![图 4. Gate 与 Full 关键指标对比。](assets/gate_vs_full_metrics.png)

*图 4. Gate 与 Full 关键指标对比。*


### Layer-3 tiepoint detail CSV
- Per-query detail dir: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/tiepoint_ground_error/tiepoints/per_query_matches`
- Scope: ratio-test matches retained by RANSAC inliers only, same as formal tiepoint RMSE.
- File pattern: `<query_id>_tiepoints.csv`; generated files: `39/39` ok queries.
- Fields: `query_id, match_index, truth_col_px, truth_row_px, pred_col_px, pred_row_px, truth_x_m, truth_y_m, pred_x_m, pred_y_m, dx_m, dy_m, dxy_m`
- Queries without detail CSV: `q_037`

## 5. 代表性可视化

![q_021 predicted ortho 与 truth ortho overlay。](assets/q_021_truth_overlay.jpg)

*q_021 predicted ortho 与 truth ortho overlay。*


![q_021 predicted ortho 与 CaiWangCun DOM overlay。](assets/q_021_dom_overlay.jpg)

*q_021 predicted ortho 与 CaiWangCun DOM overlay。*


![q_021 tiepoint overlay。](assets/q_021_tiepoints_overlay.jpg)

*q_021 tiepoint overlay。*


![q_020 predicted ortho 与 truth ortho overlay。](assets/q_020_truth_overlay.jpg)

*q_020 predicted ortho 与 truth ortho overlay。*


![q_020 predicted ortho 与 CaiWangCun DOM overlay。](assets/q_020_dom_overlay.jpg)

*q_020 predicted ortho 与 CaiWangCun DOM overlay。*


![q_020 tiepoint overlay。](assets/q_020_tiepoints_overlay.jpg)

*q_020 tiepoint overlay。*


![q_016 predicted ortho 与 truth ortho overlay。](assets/q_016_truth_overlay.jpg)

*q_016 predicted ortho 与 truth ortho overlay。*


![q_016 predicted ortho 与 CaiWangCun DOM overlay。](assets/q_016_dom_overlay.jpg)

*q_016 predicted ortho 与 CaiWangCun DOM overlay。*


![q_016 tiepoint overlay。](assets/q_016_tiepoints_overlay.jpg)

*q_016 tiepoint overlay。*


## 6. 结论
- 若 full run 的 center_offset_m 和 horizontal_error_m 仍保持米级，则 CaiWangCun 完整替换路线可扩展到全量 query。
- 异常 query 应按 retrieval rank、RoMa inlier ratio、candidate tile scale、DSM footprint 与 frame sanity 分桶定位原因。
- 本轮继续保持 no ODM LAZ / no SRTM / no old satellite candidate fallback 的约束。

## 附录
- Full root: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21`
- Gate root: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20`

### 缺失图片
- `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/ortho_alignment/frame_sanity/figures/q_021_frame_overlay.png`
- `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/ortho_alignment/frame_sanity/figures/q_021_offset_vectors.png`
- `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/ortho_alignment/frame_sanity/figures/q_021_dsm_valid_mask_on_truth_grid.png`
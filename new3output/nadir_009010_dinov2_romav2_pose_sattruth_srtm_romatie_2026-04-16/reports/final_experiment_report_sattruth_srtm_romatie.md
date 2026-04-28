# 最终实验报告：Satellite Truth + SRTM + RoMa v2 Tiepoints

## 1. 实验目的
本实验的目标是验证：在运行时仅提供单张不带地理元数据的 UAV 图像、并仅依赖固定遥感正射卫星影像库作为候选源的条件下，是否能够完成 UAV 图像的初始地理定位。当前路线保持 runtime 检索与位姿估计主链不变，仅将 validation truth 替换为 satellite truth patch，将 DSM 固定回 SRTM，并将 layer-3 的 tie-point matcher 替换为 RoMa v2。

## 2. 评估方法与评估指标
本实验沿用三层验证体系。layer-1 用于回答“预测正射结果与 satellite truth patch 的图像级几何对齐程度如何”；layer-2 用于回答“估计 pose 与参考航空三角测量/ODM pose 的相对一致性如何”；layer-3 用于回答“在同一地面区域内，局部 tie-point 的地面 XY 误差是否稳定”。
- layer-1 指标。`phase_corr_error_m` 越小越好，表示全局平移残差；`ortho_iou` 越大越好，表示预测正射与真值有效覆盖的重叠程度；`ssim` 越大越好，但在跨源影像条件下同时受到纹理、光照与成像外观差异影响。
- layer-2 指标。`horizontal_error_m` 越小越好，衡量估计相机中心与参考相机中心的平面误差；`view_dir_angle_error_deg` 越小越好，衡量相机视线方向差异。该层仍使用 `pose_vs_at` 语义，因此与 baseline 具有直接可比性。
- layer-3 指标。`tiepoint_match_count` 与 `tiepoint_inlier_count` 越大越好，表示可用于地面误差估计的 RoMa v2 对应点支持更充分；`tiepoint_inlier_ratio` 越大越好；`tiepoint_xy_error_rmse_m` 与 `tiepoint_xy_error_p90_m` 越小越好，分别反映整体误差能量与高误差尾部。

![pipeline overview](final_experiment_report_assets/pipeline_overview.png)

## 3. 实验流程与数据准备
本次 full-run 固定在 009/010 两条 nadir 航线的 40 张 query 上，每条航线 20 张。query 经过 metadata 去除后进入 runtime；当前 `query_count=40`，`metadata_removed_count=40`，`gimbal_pitch_degree` 范围为 -90.0 到 -90.0。
- 离线数据准备。复用 baseline 的 selected_queries、query_inputs、retrieval 与 RoMa v2 rerank 资产；validation truth 改为从 source satellite GeoTIFF 裁切出的 truth patch；PnP 使用 SRTM DSM；query reference pose 仍来自 `odm_report/shots.geojson`，缺失时才退回 seed。
- Runtime 主链。单张 UAV query 先经过 DINOv2 coarse retrieval，再由 RoMa v2 rerank 生成候选排序，随后在 SRTM 支持下完成对应关系、2D-3D 构建、PnP 与 best-pose 选优。
- Validation 主链。layer-1 对比 predicted ortho 与 satellite truth patch；layer-2 运行 `pose_vs_at`；layer-3 在 truth/pred common valid mask 内用 RoMa v2 重新做 dense/semi-dense matching，并计算地面 XY 误差。

## 4. 实验结果
### 4.1 Runtime 结果
当前 full-run `best_status_counts` 为 `{'ok': 40}`，`score_status_counts` 为 `{'ok': 730, 'pnp_failed': 70}`；baseline 分别为 `{'ok': 40}` 与 `{'ok': 734, 'pnp_failed': 66}`。这表明当前路线在保持 40/40 query 全部产出可用 best pose 的同时，runtime 主链定义并未变化。
![runtime status comparison](final_experiment_report_assets/runtime_status_comparison.png)

### 4.2 Layer-1 结果
当前 layer-1 平均 `phase_corr_error_m=0.1919`，`ortho_iou=0.7738`，`ssim=0.4250`。对比 baseline，对应值分别为 `0.7672`、`0.7289`、`0.5958`。
从几何一致性角度看，`phase_corr_error_m` 明显下降、`ortho_iou` 上升，说明以 satellite truth patch 为真值时，预测正射结果与最终 truth 的平移一致性和有效覆盖重叠更强；`ssim` 下降则主要反映跨源影像在纹理、色调与成像条件上的外观差异，不应直接解释为几何退化。
![layer1 metrics](final_experiment_report_assets/layer1_metrics_bar.png)

### 4.3 Layer-2 结果
当前 layer-2 平均 `horizontal_error_m=9.7230`，`view_dir_angle_error_deg=1.3471`；baseline 分别为 `9.1654` 与 `1.2706`。由于该层仍是 `pose_vs_at`，因此可以直接理解为估计 pose 与参考 pose 的一致性对比。
结果显示 layer-2 没有出现明显改善，整体上略有回退但幅度有限。这说明将 validation truth 切换为 satellite truth patch，并不会自动带来 camera pose 与参考 pose 的同步提升。
![layer2 metrics](final_experiment_report_assets/layer2_metrics_bar.png)

### 4.4 Layer-3 结果
当前 layer-3 `status_counts={'tiepoint_eval_ok': 40}`，`tiepoint_match_count_mean=4879.225`，`tiepoint_inlier_ratio_mean=0.8581`，`tiepoint_xy_error_rmse_m=2.7718`，`tiepoint_xy_error_p90_m=4.4149`。baseline 对应 `status_counts={'tiepoint_eval_ok': 40}`，`tiepoint_xy_error_rmse_m=2.8552`，`tiepoint_xy_error_p90_m=4.3476`。
若按中位数比较，`tiepoint_match_count` 从 baseline 的 `1373.5000` 提升到 `4890.0000`，`tiepoint_inlier_count` 从 `1145.0000` 提升到 `4238.5000`。这说明 RoMa v2 作为 layer-3 matcher 后，局部几何评估获得了显著更强的 tiepoint support。
![layer3 metrics](final_experiment_report_assets/layer3_metrics_bar.png)

### 4.5 baseline 低匹配 query 改善情况
以 baseline 的 layer-3 `tiepoint_match_count` 下四分位作为 low-match 集合，可以看到多数 query 的匹配支持数量显著提升，但这并不等价于所有 query 的几何误差都会同步下降。
![low match improvement](final_experiment_report_assets/low_match_queries_improvement.png)

| Query | Baseline Matches | Current Matches | Delta | Baseline RMSE | Current RMSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| q_040 | 698 | 4901 | 4203 | 3.1219 | 3.6042 |
| q_031 | 784 | 4889 | 4105 | 4.5669 | 5.0892 |
| q_038 | 796 | 4805 | 4009 | 1.9927 | 3.9100 |
| q_034 | 855 | 4734 | 3879 | 2.8297 | 5.5110 |
| q_039 | 882 | 4852 | 3970 | 3.0561 | 1.7263 |
| q_035 | 886 | 4873 | 3987 | 2.1863 | 3.4738 |
| q_001 | 968 | 4829 | 3861 | 2.5494 | 1.2762 |
| q_036 | 1178 | 4834 | 3656 | 3.4201 | 8.2668 |

## 5. 结论与结果分析
综合 full-run 结果，可以得出以下结论。第一，runtime 任务定义保持不变的前提下，当前路线仍然实现了 `best_status_counts={ok: 40}`，因此 satellite truth + SRTM + RoMa layer-3 方案不会破坏原有定位主链。
第二，主要收益集中在 layer-1 与 layer-3。layer-1 的 `phase_corr_error_m` 和 `ortho_iou` 均优于 baseline，说明以 satellite truth patch 作为 formal truth 时，预测正射与最终真值之间的图像级几何对齐更稳定；layer-3 的 tiepoint 数量和 inlier 数量显著增加，且 RMSE 从 baseline 的 `2.8552` 下降到 `2.7718`。
第三，layer-2 没有明显改善，`horizontal_error_m` 与 `view_dir_angle_error_deg` 基本持平或略有回退。这表明 validation truth 的更换主要改善的是 orthophoto-level alignment 与局部 tiepoint support，而不是直接改善相机 pose 与参考 pose 的差距。
第四，`ssim` 低于 baseline 不能直接解释为几何退化。由于当前 layer-1 属于跨源对比，外观差异会显著拉低 `ssim`，因此应将其与 `phase_corr_error_m`、`ortho_iou` 联合解释。
第五，tiepoint 数量大增并不意味着所有 query 的地面几何误差都同步改善。部分 query 虽然已经获得高密度匹配，但 `RMSE` 仍然偏高，说明后续仍需关注局部几何失真、遮挡、跨源外观差异以及 truth/pred 有效覆盖不完全一致等问题。

![overall metrics comparison](final_experiment_report_assets/overall_metrics_comparison.png)

## 6. 后续想法
- 扩展到更一般的非 nadir / arbitrary UAV query，验证当前路线是否能从受控 nadir 集迁移到更真实的任意视角输入。
- 继续研究 satellite truth 作为正式主验证口径的稳定性，尤其是其与 UAV DOM/ODM truth 在空间分辨率、外观域差异上的系统偏差。
- 分析“高匹配但 RMSE 仍偏高”的 query，区分是 RoMa 匹配分布问题、局部区域形变问题，还是 truth/pred 几何边界不一致。
- 在 layer-3 中加入更强几何约束与分区域评估，例如分块 RMSE、边界区域剔除、显式不确定性建模，以减少仅靠 match count 解读结果的偏差。
- 进一步比较 runtime 与 validation 的差异，明确哪些改动应当只停留在验证链，哪些改动有可能反向迁移到运行时主链。

## 7. 关键实验设置与变量说明
- 实验对象：`new3output/nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16`。
- baseline 对比对象：`new2output/nadir_009010_dinov2_romav2_pose_2026-04-10`。
- runtime 保持不变：DINOv2 coarse retrieval + RoMa v2 rerank + fixed satellite library + SRTM-backed pose/PnP。
- validation 变更点：truth 改为 satellite truth patch；layer-2 继续使用 `pose_vs_at`；layer-3 matcher 改为 RoMa v2。
- 当前 full-run runtime 状态：`best_status_counts={'ok': 40}`，`score_status_counts={'ok': 730, 'pnp_failed': 70}`。
- 当前 layer-3 状态：`status_counts={'tiepoint_eval_ok': 40}`。
- query 基本信息：航线分布 `DJI_202510311347_009_新建面状航线1=20, DJI_202510311413_010_新建面状航线1=20`，平均 absolute altitude `391.452`，平均 relative altitude `372.277`。

## 8. 典型样例与异常样例分析
成功样例优先选取 layer-3 RMSE 低且 layer-2 平面误差较低的 query；异常样例优先选取 baseline low-match 集合中当前 RMSE 仍偏高的 query。

### q_015 (代表性成功样例)
- `current_match_count=4929`，`baseline_match_count=1686`，`current_rmse_m=0.9221`，`current_horizontal_error_m=4.4184`。
- 该样例说明在 satellite truth patch 与 RoMa v2 tiepoints 支持下，truth/pred 的局部几何关系能够保持较高稳定性。
![q_015 case](final_experiment_report_assets/sample_cases/q_015_case_panel.png)

### q_022 (代表性成功样例)
- `current_match_count=4894`，`baseline_match_count=1585`，`current_rmse_m=0.9403`，`current_horizontal_error_m=4.4262`。
- 该样例说明在 satellite truth patch 与 RoMa v2 tiepoints 支持下，truth/pred 的局部几何关系能够保持较高稳定性。
![q_022 case](final_experiment_report_assets/sample_cases/q_022_case_panel.png)

### q_036 (异常样例)
- `current_match_count=4834`，`baseline_match_count=1178`，`current_rmse_m=8.2668`，`current_horizontal_error_m=18.0227`。
- 该样例说明即使匹配点数量已经显著增加，局部几何误差仍可能偏高，后续需要重点排查区域形变、边界覆盖与跨源差异。
![q_036 case](final_experiment_report_assets/sample_cases/q_036_case_panel.png)

### q_034 (异常样例)
- `current_match_count=4734`，`baseline_match_count=855`，`current_rmse_m=5.5110`，`current_horizontal_error_m=20.1941`。
- 该样例说明即使匹配点数量已经显著增加，局部几何误差仍可能偏高，后续需要重点排查区域形变、边界覆盖与跨源差异。
![q_034 case](final_experiment_report_assets/sample_cases/q_034_case_panel.png)

## 附加说明
- 本报告只基于已存在的 full-run 结果重组与可视化，不引入新的实验口径。
- `validation truth` 仅用于离线评估，不参与 runtime 候选选择或定位推理。

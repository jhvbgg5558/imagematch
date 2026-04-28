# Pose-vs-AT 核心指标图表说明

本目录可视化第二层 `pose_vs_at` 结果，即 `best pose vs ODM/AT reference pose` 的相对位姿偏差。
这些图只解释第二层外参偏差，不代表第一层正射套合精度，也不代表第三层局部地物点误差。

## 当前整体结果
- `query_count=40`, `evaluated_query_count=40`。
- `horizontal_error_m`: mean=40.6718 m, median=4.6051 m, p90=16.5854 m。
- `view_dir_angle_error_deg`: mean=2.0945 deg, median=0.5647 deg, p90=1.8028 deg。
- 参考位姿来源：{'odm_report_shots_geojson': 40}。
- `q_022` 是本层最明显异常点：`horizontal_error_m=1357.9538 m`, `view_dir_angle_error_deg=53.4059 deg`。

## 图表列表
- `figure_1_position_error_distribution.png`：位置误差分布图。看 `horizontal_error_m` 和 `spatial_error_m` 的整体分布；纵轴采用 symlog 以便同时显示普通样本和 `q_022` 异常点。
- `figure_2_orientation_error_distribution.png`：姿态误差分布图。看视线方向误差和 yaw/pitch/roll 辅助误差；主姿态指标优先看 `view_dir_angle_error_deg`。
- `figure_3_per_query_horizontal_error.png`：逐 query 平面误差柱状图。用于定位哪些 query 的平面位置偏差最大，`q_022` 被单独高亮。
- `figure_4_per_query_view_dir_error.png`：逐 query 视线方向误差柱状图。用于定位哪些 query 的相机朝向偏差最大，`q_022` 被单独高亮。
- `figure_5_per_flight_pose_error.png`：分航线误差对比图。蓝色为平面位置误差均值，橙色为视线方向误差均值；可见第 011 航线受 `q_022` 拉高明显。
- `figure_6_dx_dy_scatter.png`：相机中心平面偏移散点图。横轴为 dx，纵轴为 dy；离原点越远，平面偏差越大，方向表示偏移方向。
- `figure_7_horizontal_vs_viewdir_scatter.png`：位置误差与姿态误差关系图。用于看位置误差大的样本是否也伴随朝向误差变大。
- `figure_8_reference_source_status.png`：参考来源和评估状态统计图。本次应显示 `odm_report_shots_geojson=40` 且 `ok=40`。

## 输入文件
- `per_query_pose_vs_at.csv`
- `per_flight_pose_vs_at.csv`
- `overall_pose_vs_at.json`
- `query_reference_pose_manifest.json`

生成目录：`new2output\pose_v1_formal\eval_pose_validation_suite\pose_vs_at\figures`

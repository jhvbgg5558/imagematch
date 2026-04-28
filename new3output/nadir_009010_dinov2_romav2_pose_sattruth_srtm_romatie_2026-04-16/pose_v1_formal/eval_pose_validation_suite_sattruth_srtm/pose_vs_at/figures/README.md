# Pose-vs-AT 图表说明

这些图来自 `pose_vs_at` 结果，是对 `best pose vs ODM/AT reference pose` 的离线诊断可视化。
图中的高亮点不再写死为历史 query，而是根据当前 `per_query_pose_vs_at.csv` 自动选择 `horizontal_error_m` 最大的 query。

## 当前统计
- `query_count=40`，`evaluated_query_count=40`。
- `horizontal_error_m`: mean=9.7230 m, median=8.1840 m, p90=20.3671 m。
- `view_dir_angle_error_deg`: mean=1.3471 deg, median=1.0536 deg, p90=2.9162 deg。
- `reference_source_type_counts={'odm_report_shots_geojson': 40}`。
- 当前动态高亮 query 为 `q_012`：`horizontal_error_m=34.0660 m`，`view_dir_angle_error_deg=5.0226 deg`。

## 图表说明
- `figure_1_position_error_distribution.png`：位置误差分布图，使用 symlog 纵轴以同时显示主体样本和高误差样本。
- `figure_2_orientation_error_distribution.png`：姿态误差分布图。
- `figure_3_per_query_horizontal_error.png`：逐 query 水平误差柱状图，动态高亮当前最大 horizontal error 的 query。
- `figure_4_per_query_view_dir_error.png`：逐 query 视线方向误差柱状图，高亮同一 query 便于对照。
- `figure_5_per_flight_pose_error.png`：分航线位置与视向误差均值对比图。
- `figure_6_dx_dy_scatter.png`：best pose 相对 reference pose 的 dx/dy 平面偏移散点图。
- `figure_7_horizontal_vs_viewdir_scatter.png`：水平误差与视向误差耦合散点图。
- `figure_8_reference_source_status.png`：reference source 与 eval status 统计图。

## 输入文件
- `per_query_pose_vs_at.csv`
- `per_flight_pose_vs_at.csv`
- `overall_pose_vs_at.json`
- `query_reference_pose_manifest.json`

输出目录：`/mnt/d/aiproject/imagematch/new3output/nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16/pose_v1_formal/eval_pose_validation_suite_sattruth_srtm/pose_vs_at/figures`

# DOM+DSM+PnP Baseline v1 实施计划

## 目标

本计划用于把当前新工作流落成一条可执行的几何定位 baseline：

`去元数据 UAV query -> DINOv2 coarse retrieval -> RoMa v2 匹配 -> DOM+DSM 构造 2D-3D 对应 -> PnP 求位姿初值`

本版只验证链路可行性和几何自洽性，不把结果表述为高精度摄影测量外参恢复。

## 固定约定

### 1. Query 侧约定

- query 是任意单张 UAV 图像
- query 不带地理信息
- query 不保证为正射影像
- 不做外部分辨率统一处理，除非这是模型内部固有流程
- query 侧推理输入不得使用原始 GPS / 飞控位姿 / 其他可直接泄漏空间位置的信息

### 2. 相机模型约定

- v1 使用针孔相机近似
- 焦距优先使用 EXIF `FocalLength`
- 若只能拿到 `35mm` 等效焦距，则按相机规格表换算为像素焦距
- 若两者都不可用，则该样本记为 `intrinsics_missing` 并退出主实验
- 传感器尺寸优先来自机型规格表；若不可得，则使用项目内统一登记表
- 主点默认设为图像中心
- 畸变参数 v1 统一设为 `0`
- v1 默认不做去畸变；若后续补齐可靠畸变参数，单独作为 v2 实验

### 3. 世界坐标系约定

- v1 统一使用 DOM 当前投影坐标系作为世界坐标系
- 2D-3D 构造顺序固定为：
  - DOM 像素坐标
  - DOM 投影坐标
  - DSM 高程采样
  - 世界三维点 `(X, Y, Z)`
- DOM 和 DSM 若不在同一坐标系，必须先统一到 DOM 坐标系再进入主链
- 像素到地理坐标按像素中心进行映射

### 4. DSM 采样约定

- v1 默认使用双线性插值采样 DSM 高程
- 若采样点越界，则标记为 `out_of_bounds`
- 若采样点落入 `nodata`，则标记为 `nodata`
- 若局部高程不稳定，则标记为 `unstable_local_height`
- 采样状态必须写入中间产物和汇总结果

### 5. 局部高程不稳定判定

v1 固定使用以下规则：

- 邻域大小：`3x3`
- 统计量：标准差与极差同时判断
- 阈值：标准差 `> 8 m` 或极差 `> 20 m`
- 若邻域内有效像元少于 `5` 个，也视为不稳定
- 满足任一条件即剔除该点，并记录 `unstable_local_height`

### 6. PnP 求解约定

- v1 先执行 `solvePnPRansac`
- 再对 RANSAC 内点执行一次 `solvePnP` refinement
- 最小有效 2D-3D 点数：`6`
- RANSAC 重投影阈值：`8 px`
- 最大迭代次数：`1000`
- 置信度：`0.99`
- v1 不提供外部初值

### 7. 候选打分约定

coarse top-k 候选都做几何求解，再按固定 baseline score 排序。

默认分数采用：

`score = 0.30 * inlier_ratio + 0.25 * coverage_score + 0.20 * inlier_count_norm + 0.10 * elevation_span_norm - 0.10 * reproj_error_norm - 0.05 * pose_penalty`

其中：

- `coverage_score` 表示 2D 点在 query 图像中的覆盖面积
- `inlier_count_norm` 是同一 query 内的归一化内点数
- `elevation_span_norm` 是同一 query 内的高程跨度归一化值
- `reproj_error_norm` 是同一 query 内的重投影误差归一化值
- `pose_penalty` 用于惩罚明显不合理的位姿

v1 不引入学习式权重，也不在运行中动态改权。

### 8. 样本退出规则

样本若满足以下任一条件，则退出主实验，但仍保留日志和统计：

- `intrinsics_missing`
- `insufficient_2d3d_points`
- `dsm_coverage_insufficient`
- `dsm_nodata_too_high`

这些样本在统计中归入 `not_applicable_v1`，不计入方法失败，但必须单独报告占比。

## 执行阶段

### Phase A: 参考数据与坐标链路验证

- 统一 DOM 与 DSM 的 CRS、分辨率、仿射变换和 `nodata` 规则
- 验证 `DOM 像素 -> DOM 投影坐标 -> DSM 高程 -> 3D 点`
- 输出：
  - 坐标核对表
  - 叠加检查图
  - 采样状态日志

### Phase B: 最小可跑通样例

- 选少量代表性 query
- 固定 DINOv2 coarse top-k 候选
- 导出 RoMa v2 匹配点并恢复到原始像素坐标
- 构造 2D-3D 对应并做 DSM 采样
- 跑通 `solvePnPRansac + refinement`
- 输出：
  - 对应点表
  - PnP 结果表
  - 重投影误差
  - 失败日志

### Phase C: 几何可解性与候选区分验证

- 对 top-k 候选都做 PnP
- 记录内点数、内点率、覆盖度、高程变化、误差和位姿合理性
- 验证正确候选是否能在几何分数上压过错误候选
- 输出：
  - 候选对比表
  - 成功 / 失败 / 退出分类
  - 失败类型分桶

### Phase D: 小规模 baseline 实验

- 扩展到一批代表性 query
- 固定 DOM/DSM 数据源、top-k、内参策略、采样规则、稳定性阈值、PnP 参数与打分函数
- 输出：
  - 成功率
  - 非发散率
  - 误差分布
  - 退出样本占比

### Phase E: 全量评估与口径固化

- 仅在前 4 阶段规则固定后进入全量评估
- 输出正式结果目录、汇总表和失败案例集
- 再决定是否升级到 v2

## 结果分类

### 1. `applicable_success`

满足 v1 前提且成功完成 PnP。

### 2. `applicable_failure`

满足 v1 前提，但方法链路在 PnP 或候选判别上失败。

### 3. `not_applicable_v1`

因内参不足、2D-3D 点不足、DSM 覆盖不足或 `nodata` 过高而退出。

## 脚本与目录

默认 bundle root 设为：

`new2output/pose_baseline_v1`

计划中的脚本如下：

- `scripts/build_pose_manifest.py`
  - 汇总 query、DOM、DSM、近似内参和 coarse 候选
- `scripts/sample_dsm_for_dom_points.py`
  - DOM 投影点到 DSM 高程采样
- `scripts/prepare_pose_correspondences.py`
  - RoMa 匹配点回原图坐标并构造 2D-3D 对应
- `scripts/run_pnp_baseline.py`
  - 执行 `solvePnPRansac + refinement`
- `scripts/score_pose_candidates.py`
  - 按固定 baseline score 对 top-k 候选排序
- `scripts/summarize_pose_results.py`
  - 汇总成功 / 失败 / 退出、误差和案例

建议结果子目录如下：

- `manifest/`
- `correspondences/`
- `sampling/`
- `pnp/`
- `scores/`
- `summary/`
- `logs/`

## 当前状态

本文件只定义实施计划，不包含任何正式实验结论。

# Agent3 审查清单与测试要求

## 1. 目的

本文件用于固定 `DOM+DSM+PnP Baseline v1` 的脚本审查边界。

适用范围：

- `build_pose_manifest.py`
- `sample_dsm_for_dom_points.py`
- `prepare_pose_correspondences.py`
- `run_pnp_baseline.py`
- `score_pose_candidates.py`
- `summarize_pose_results.py`

审查目标不是评价代码风格本身，而是阻止以下问题进入主线：

- 几何口径漂移
- 推理链误用真值信息
- 坐标转换或采样逻辑错误
- 退出样本与失败样本混统
- 结果不可复查、不可复现

## 2. 总体审查原则

- 必须保持 `Baseline v1` 的固定口径，不允许脚本运行时临时切换核心规则。
- 检索与匹配阶段不得使用 query 原始地理信息参与推理。
- 离线真值只能用于评估与误差分析，不得参与候选筛选、点过滤或候选打分。
- 所有关键中间产物必须落盘，且文件内容足以支撑人工复核。
- 所有退出规则必须单独统计，不得混入方法失败率。

## 3. 模块级审查清单

### 3.1 `build_pose_manifest.py`

- 是否清楚区分运行输入、离线评估真值、诊断产物。
- 是否显式记录 DOM、DSM、query、coarse top-k 的来源路径。
- 是否记录相机模型来源，且只允许 `approx_intrinsics_v1`。
- 是否把世界坐标系固定为 DOM 当前投影坐标系。
- 是否保存样本级配置快照，避免后续口径不明。

### 3.2 `sample_dsm_for_dom_points.py`

- 是否按 DOM 投影坐标查询 DSM，而不是反向把 DOM 吸附到 DSM 网格。
- 是否默认使用双线性插值。
- 是否为每个采样点保存状态码：
  - `ok`
  - `out_of_bounds`
  - `nodata`
  - `unstable_local_height`
- 是否按固定规则判定局部高程不稳定：
  - `3x3` 邻域
  - 标准差阈值 `8 m`
  - 极差阈值 `20 m`
  - 有效像元数阈值 `5`
- 是否将越界、nodata 和高程不稳定的点分别统计。

### 3.3 `prepare_pose_correspondences.py`

- 是否明确恢复 RoMa 匹配点到原图坐标，而不是混用 resize 后坐标。
- 是否为每个点保留完整链路：
  - UAV 像素坐标
  - DOM 像素坐标
  - DOM 投影坐标
  - DSM 高程
  - 最终 3D 点
- 是否按固定退出规则判断：
  - `insufficient_2d3d_points`
  - `dsm_coverage_insufficient`
  - `dsm_nodata_too_high`
- 是否保留过滤前后点数对比，便于定位问题来自匹配、采样还是过滤。

### 3.4 `run_pnp_baseline.py`

- 是否执行固定的两阶段策略：
  - `solvePnPRansac`
  - `solvePnP refinement`
- refinement 是否只使用 RANSAC 内点。
- 是否固定参数：
  - 最小有效点数 `6`
  - RANSAC 阈值 `8 px`
  - 最大迭代 `1000`
  - 置信度 `0.99`
- 是否保存：
  - 原始 2D-3D 点数
  - RANSAC 内点数
  - RANSAC 内点索引
  - RANSAC 误差
  - refinement 误差
  - 最终位姿
  - 失败原因

### 3.5 `score_pose_candidates.py`

- 是否在 coarse top-k 候选上统一执行，而不是只取 top-1。
- 是否严格使用固定 baseline score，而不是运行时动态换权重。
- 是否保存 score 的分项明细：
  - `inlier_ratio`
  - `coverage_score`
  - `inlier_count_norm`
  - `elevation_span_norm`
  - `reproj_error_norm`
  - `pose_penalty`
- 是否对明显不合理位姿施加惩罚，而不是直接丢弃不记录。

### 3.6 `summarize_pose_results.py`

- 是否单独统计三类样本：
  - `applicable_success`
  - `applicable_failure`
  - `not_applicable_v1`
- 是否把退出原因逐类汇总。
- 是否区分：
  - coarse 未召回
  - 匹配不足
  - DSM 采样失败
  - PnP 发散
  - 位姿不合理
- 是否生成汇总配置文件，写明本轮参数口径。

## 4. 必须覆盖的测试点

### 4.1 单元测试

- DOM 像素到投影坐标转换测试
- DSM 双线性采样测试
- DSM 越界处理测试
- DSM `nodata` 处理测试
- `unstable_local_height` 判定测试
- RoMa resize 坐标回原图测试
- 最小 2D-3D 点数退出测试
- baseline score 可复现性测试

### 4.2 集成测试

- 小样本 query 的 DOM -> DSM -> 3D 点构造链路测试
- 小样本 query 的 `solvePnPRansac + refinement` 跑通测试
- 正确候选与错误候选的几何打分区分测试
- 退出样本不会被计入失败率测试
- 结果目录具备最小复核产物测试

## 5. 没有这些产物不得审查通过

- 运行配置快照
- 样本级 manifest
- DSM 采样明细或可追踪日志
- 2D-3D 对应点明细
- PnP 内点索引
- refinement 前后误差对比
- 候选打分分项明细
- 退出原因汇总表
- 小样本人工复核入口

## 6. 审查结论模板

审查结论必须至少包含：

- 是否符合 `Baseline v1`
- 是否发现真值泄漏风险
- 是否发现坐标系或采样口径漂移
- 是否存在退出样本与失败样本混统
- 是否满足最小测试覆盖
- 是否允许进入下一阶段

若不通过，必须明确指出阻塞项属于哪一类：

- `implementation_bug`
- `geometry_contract_violation`
- `missing_artifacts`
- `insufficient_tests`
- `unclear_failure_accounting`

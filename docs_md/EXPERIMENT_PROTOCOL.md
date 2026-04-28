# 当前任务协议说明

这份文档用于固定当前新任务的输入约束和实验边界，避免再次混入旧任务的同尺度假设。

## 1. 当前任务定义

目标是论证：

> 在跨视角条件下，仅依赖遥感正射影像，能否把任意单张无人机影像检索到正确地理区域附近。

这里的“初步地理定位”仍指区域级检索定位，不等同于高精度位姿估计。

## 2. 当前输入约束

- query 是任意单张无人机影像
- query 不带任何地理信息
- query 不保证为正射影像
- query 的分辨率、视角、尺度、裁切范围可能不稳定
- 不做额外的外部分辨率统一处理，除非这是模型推理流程内部固有操作

## 3. 当前明确禁止继承的旧假设

- 不再默认 query 是 200m 正射裁块
- 不再默认 satellite 与 query 同尺度
- 不再默认真值可由 query 中心点落入瓦片自动定义
- 不再默认旧阶段预处理产物可直接复用

## 4. 正式协议状态

当前正式协议尚未最终定稿，但已经形成首轮固定库与真值口径：

- 固定卫星候选库：`80m / 120m / 200m / 300m` 多尺度瓦片
- 候选库范围：4 条航线整体活动区域
- 固定库主资产：原始裁块分辨率卫星瓦片，不预先统一到单一输入尺寸
- 首轮真值规则：以 query 中心点为圆心，半径 `50m` 内与真值圆相交的卫星瓦片都算正确候选
- 当前实验版 query：必须使用去除 EXIF/XMP/GPS/DJI 元数据后的无地理信息副本

补充约束：

- 固定卫星库是离线预构建的统一候选库，不能根据单张 query 的大小或坐标在推理时临时裁库
- 如果某个模型需要固定输入尺寸，统一 resize 只能发生在模型预处理或模型缓存派生阶段
- 模型输入缓存不反向定义固定卫星库主资产

这套口径当前用于真值准备，不等同于最终正式评测口径。

在新方案确定前：

- 不得把旧同尺度实验结果作为当前正式结论
- 不得把旧 query 集、旧 truth 定义、旧输出目录当作当前对照基准
- 如需引用历史内容，必须显式标注为 `old/` 历史材料

## 5. 待补充内容

后续需要补充并固定：

- query 数据定义
- 卫星候选库定义
- 真值构造方式
- 正式指标
- 训练/验证/测试划分方式
- 工程部署假设

## 6. 当前正在验证的 refined truth 方向

针对 coverage 真值中出现的大面积黑边 tile 被误记为真值的问题，当前正在验证一套 refined truth 方向：

- 第一步仍使用无人机已有经纬度、相对高度、云台朝向和相机内参近似生成 query 地面覆盖 footprint
- 第二步仍以 footprint 与卫星 tile 的几何相交比例定义 coverage 候选
- 第三步不再把所有 `coverage_ratio >= 0.4` 的 tile 等价视为正式真值
- 新增 tile 有效内容约束，计算：
  - `valid_pixel_ratio`
  - `black_pixel_ratio`
- 形成两级真值：
  - `strict_truth`：`coverage_ratio >= 0.4` 且 `valid_pixel_ratio >= 0.6`
  - `soft_truth`：满足 coverage，但有效内容不足

当前验证目标不是立刻替代既有正式结果，而是先确认：

- 大面积黑边 tile 是否能被稳定降级出主真值集合
- 新真值是否更接近“可用于视觉检索监督”的正样本
- 后续正式指标是否应默认切换到 `strict_truth`

截至 `2026-03-20`，这套 refined truth 已完成全量 `40` 个 query 的稳定性验证：

- `40/40` query 有 truth
- `40/40` query 有 `strict_truth`
- `40/40` query 满足 `strict_truth_count >= 2`

因此它已经满足“每个 query 都有稳定主真值”的最低要求，可以进入下一步的正式检索重评估。

截至 `2026-03-20`，该重评估已经完成，当前推荐口径更新为：

- 主指标默认使用 `strict_truth`
- `soft_truth` 仅用于诊断与解释，不进入正式主指标
- 旧 `coverage_truth` 保留作历史对照口径，不再作为默认正式评估结果

## 7. DOM+DSM+PnP Baseline v1 约定

这部分口径用于当前新任务的 pose baseline v1，目标是把“检索后可定位”进一步推进到“粗位姿恢复 / 初值恢复”。v1 仍然只作为实施准备阶段的正式协议，不自动意味着已经得到结果。

### 7.1 相机模型约定

- 焦距优先使用 EXIF `FocalLength`
- 若只能拿到 `35mm` 等效焦距，则结合统一登记的传感器尺寸换算为像素焦距
- 若焦距与等效焦距都缺失，则该样本记为 `intrinsics_missing` 并退出主实验
- 传感器尺寸优先来自相机型号规格表；若规格表不可得，则使用项目内统一登记的机型参数表，不允许逐样本临时换口径
- 主点默认设为图像中心
- 畸变系数在 v1 中统一设为 `0`
- v1 默认不做图像去畸变；若后续存在可靠畸变参数，可作为 v2 单独实验
- 该近似内参口径统一标记为 `approx_intrinsics_v1`

### 7.2 世界坐标系约定

- v1 统一使用 DOM 当前投影坐标系作为世界坐标系
- 不直接在经纬度上做 PnP
- DOM 像素点先映射到 DOM 投影平面坐标，再结合 DSM 高程得到 `(X, Y, Z)` 三维点
- 若 DOM 与 DSM 原始坐标系不同，必须先重投影到 DOM 坐标系后再进入主链

### 7.3 DSM 采样规则

- v1 默认使用双线性插值采样 DSM 高程
- 以 DOM 投影坐标为查询基准，在 DSM 上做采样，不反向把 DOM 降采样到 DSM 网格
- 若采样点越界或落入 `nodata`，直接剔除并记录状态码
- 若采样点局部高程不稳定，也剔除并记录状态码
- 采样状态码统一记录为：`ok / out_of_bounds / nodata / unstable_local_height`

### 7.4 局部高程不稳定判定

- 邻域固定为以采样点为中心的 `3x3` 邻域
- 同时计算邻域高程标准差与极差
- 若标准差 `> 8m` 或极差 `> 20m`，记为不稳定
- 若 `3x3` 邻域内有效像元不足 `5` 个，也记为不稳定
- 满足任一条件即标记为 `unstable_local_height` 并剔除该点

### 7.5 样本退出规则

- `intrinsics_missing`：无法从 EXIF 或统一机型参数表构造近似内参
- `insufficient_2d3d_points`：经过 DSM 采样和过滤后，有效 2D-3D 点数少于 `6`
- `dsm_coverage_insufficient`：RoMa 候选匹配点中，DSM 可成功采样的比例低于 `0.5`
- `dsm_nodata_too_high`：DSM 采样失败中，由 `nodata` 或越界导致的比例高于 `0.5`

这些样本在统计中单独列为 `not_applicable_v1`，不计入方法成功求解失败，但必须单独报告占比。

### 7.6 PnP 求解策略

- v1 固定使用两阶段求解：`solvePnPRansac` 后接 `solvePnP` refinement
- 最小有效 2D-3D 点数为 `6`
- RANSAC 重投影阈值固定为 `8 px`
- 最大迭代次数固定为 `1000`
- 置信度固定为 `0.99`
- v1 默认不提供外部初值
- refinement 只使用 RANSAC 内点重新求解，并保存 refinement 前后误差

### 7.7 候选打分规则

- coarse top-k 候选都要做几何求解，再按固定 baseline score 排序
- baseline score 由以下项组成：
  - 内点数
  - 内点率
  - 重投影误差
  - 点覆盖度
  - 3D 点高程变化
  - 位姿合理性惩罚项
- 参考公式：
  - `score = 0.30 * inlier_ratio + 0.25 * coverage_score + 0.20 * inlier_count_norm + 0.10 * elevation_span_norm - 0.10 * reproj_error_norm - 0.05 * pose_penalty`
- 其中各项均需在结果目录中保留分项日志，不允许只保留总分
- v1 不引入学习式权重，不在运行中动态改权

## 2026-04-02 Formal Pose v1 Runtime Notes
- Active formal pose workspace is `new2output/pose_v1_formal/`.
- Formal runtime candidate mapping must come from `output/coverage_truth_200_300_500_700_dinov2_baseline/fixed_satellite_library/tiles.csv`.
- `query_truth` is offline evaluation only and must not be used to resolve runtime candidate DOM assets.
- In the unified validation suite layer-2 (`pose_vs_at`), the formal reference-pose priority is:
  - primary: per-flight `odm_report/shots.geojson`
  - fallback only when ODM is missing/incomplete: `new1output/query_reselect_2026-03-26_v2/query_truth/queries_truth_seed.csv`
- Formal DSM preparation is defined as candidate tile bbox expanded by 250 m, with cache requests recorded under `new2output/pose_v1_formal/dsm_cache/requests/`.
- Historical `pose_baseline_v1` debug runs are not part of the active formal protocol.

## 2026-04-02 Formal Pose v1 DSM Execution Note
- The active raw SRTM source for the current formal run is `new2output/N30E114.hgt`.
- This HGT file is treated as source data only, not as the final runtime DSM manifest target.
- Runtime DSM consumption remains candidate-oriented:
  - each active candidate tile uses its own bbox expanded by `250 m`
  - each cropped DSM output must be written under `new2output/pose_v1_formal/dsm_cache/rasters/`
- The current formal request set contains `199` unique candidate-tile DSM regions, derived from the active `800` query-candidate pairs after tile deduplication.
- The full satellite library size (`1029` tiles) must not be confused with the current DSM preparation scope.

## 2026-04-10 009/010 Nadir Experiment Protocol Note
- The 009/010 nadir experiment is isolated under:
  - `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/`
- Query scope is restricted to:
  - `DJI_202510311347_009_新建面状航线1`
  - `DJI_202510311413_010_新建面状航线1`
- Nadir selection is fixed as:
  - `gimbal_pitch_degree <= -85.0`
  - `20` selected query images per route
  - query IDs `q_001` through `q_020` for route 009 and `q_021` through `q_040` for route 010
- Runtime candidate selection remains truth-free:
  - DINOv2 coarse retrieval and RoMa v2 rerank determine the Top-20 candidate set
  - query truth is used only for offline evaluation and manifest audit fields
- Pose candidate score is locked to:
  - `score = fused_score` from RoMa rerank export
  - missing `fused_score` is a hard failure
- Compatibility note for formal candidate manifests:
  - newer coverage truth exports may not include the legacy `is_intersection_truth` column
  - when that column is absent, rows present in `query_truth_tiles.csv` are treated as broad coverage/intersection truth hits for offline evaluation fields only
  - `is_strict_truth` must still be read from the explicit truth column

## 2026-04-16 Satellite Truth Subchain Note
- A separate satellite-truth validation subchain is being introduced under the isolated new3output experiment root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\`
- This subchain does not change the runtime retrieval task:
  - the query set remains 009/010 with 20 nadir images per flight
  - DINOv2 coarse retrieval and RoMa v2 rerank remain the runtime candidate source
  - the fixed satellite library remains the runtime DOM/candidate source
- Satellite truth constraints for this subchain:
  - the final truth patch must be cropped from a source satellite GeoTIFF under the suite root
  - a fixed tile may be used only as a selection anchor, not as the final truth object
  - top-k stitching is not permitted as the formal truth definition
- The satellite-truth suite is intentionally a validation-only branch:
  - layer-1 remains orthophoto alignment against satellite truth patches
  - layer-2 becomes a geometry diagnostic branch, not a camera-pose truth branch
  - layer-3 remains the local tie-point ground-XY error branch
- All outputs from this subchain must be written under:
  - `pose_v1_formal/eval_pose_validation_suite_satellite_truth/`
- New helper scripts for this branch are treated as the current formal contract for satellite truth, but they do not replace the existing UAV orthophoto-truth suite.

## 2026-04-16 ODM Truth + ODM DSM Replacement Note
- The new3output branch adds an ODM-refresh path without changing the runtime localization task:
  - runtime candidate retrieval remains DINOv2 coarse + RoMa v2 rerank over the fixed satellite library
  - query selection remains the locked 009/010 nadir set
  - query intrinsics remain the existing per-flight `cameras.json` derivation and are not refreshed in this experiment
- Only the following upstream layers are intentionally replaced:
  - evaluation truth orthophoto: use the flight-asset override manifest to select the authoritative ODM orthophoto source
  - PnP DSM: use ODM DSM override assets instead of SRTM-derived candidate DSM rasters
- ODM DSM sourcing rule:
  - prefer a raster DSM if present in the override manifest
  - if no raster DSM exists, use `odm_georeferenced_model.laz` as the ODM DSM-equivalent source and rasterize from that point cloud
- The orthophoto-truth validation suite must use explicit asset override input:
  - `scripts/run_pose_validation_suite.py --flight-asset-manifest <csv>`
  - silent fallback to legacy flight-root orthophotos is not permitted when an override manifest is supplied
- The new3output orchestrator for this contract is:
  - `scripts/run_nadir_009010_odmrefresh_and_sattruth_experiment.py`

## 2026-04-17 ODM-Truth-Only 0.1m Re-Run Note
- A second ODM-refresh execution mode is now supported for the same 009/010 runtime task:
  - `scripts/run_nadir_009010_odmrefresh_and_sattruth_experiment.py --phase odm_truth_only`
- This mode keeps the runtime localization task fixed to:
  - the existing `40` nadir queries from the completed `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/` branch
  - DINOv2 coarse retrieval
  - RoMa v2 rerank
  - the fixed satellite DOM candidate library
  - existing per-flight `cameras.json` intrinsics
- This mode intentionally excludes:
  - satellite-truth validation
  - cross-suite comparison report generation
  - suite-local Word report generation when `--skip-reports` is supplied
- The new locked resampling contract for this rerun path is:
  - `run_pose_validation_suite.py --target-resolution-m 0.1`
  - `materialize_formal_dsm_rasters_from_odm.py --target-resolution-m 0.1`
  - both orthophoto-truth alignment grids and ODM-derived DSM rasters are treated as a uniform `0.1 m` experiment grid
- The recommended isolated root for this rerun path is:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_0p1m_2026-04-17\`

## 2026-04-17 ODM DSM Gate Resolution Sweep Note
- A dedicated gate-only sweep entrypoint is now available to estimate the
  highest practical ODM DSM resolution supported by the current 009/010 ODM LAZ
  assets:
  - `scripts/run_odm_dsm_gate_resolution_sweep.py`
- This sweep keeps the runtime localization task fixed to:
  - the locked 009/010 nadir `40`-query set reused from
    `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/`
  - DINOv2 coarse retrieval
  - RoMa v2 rerank
  - the fixed satellite DOM candidate library
  - existing per-flight `cameras.json` intrinsics
- This sweep also keeps the validation truth contract fixed to:
  - ODM DOM truth only
  - `run_pose_validation_suite.py --target-resolution-m 0.1`
- The only swept variable is ODM DSM raster resolution:
  - `5 m`
  - `3 m`
  - `2 m`
- Each sweep case is written to its own isolated gate root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_5m_gate_2026-04-17\`
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_3m_gate_2026-04-17\`
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_2m_gate_2026-04-17\`
- Sweep-level aggregate outputs are written under:
  - `D:\aiproject\imagematch\new3output\odm_dsm_gate_resolution_sweep_2026-04-17\`
- Gate support is judged from the combination of:
  - DSM build success (`planned_count == built_count`, `failed_count == 0`)
  - pose gate runtime completion (`summary/per_query_best_pose.csv`,
    `summary/pose_overall_summary.json`)
  - validation suite completion
    (`eval_pose_validation_suite_odm_truth/phase_gate_summary.json`)
  - at least partial pose success (`best_status_counts.ok > 0`)
  - rejection of the degenerate all-`dsm_nodata_too_high` case
- This sweep is the active diagnosis route for deciding whether the current ODM
  LAZ assets support `2 m`, `3 m`, or only `5 m` DSM in the formal gate.

## 2026-04-18 Predicted-Ortho Semantics Note
- The current validation `predicted ortho` products are not full orthophoto
  reconstructions.
- In both `gate` and `full`, they are rendered from:
  - the formal per-query best pose
  - the candidate-linked DSM raster actually used by the pose branch
  - the single original query image
  - the truth crop grid used by the validation suite
- The formal renderer must therefore be interpreted as:
  - a grid-aligned single-image pose-and-DSM reprojection product
  - not a multi-view DOM / orthomosaic reconstruction stage
- Consequence for interpretation:
  - visible warping in roads or building outlines can be caused by DSM support,
    pose residuals, or both
  - visual smoothness alone must not be treated as evidence of higher geometric
    fidelity

## 2026-04-18 ODM DSM Sweep Resolution Conclusion
- The completed two-stage ODM DSM gate sweeps now establish:
  - supported in the first sweep: `5 m`, `3 m`, `2 m`
  - supported in the hi-res sweep: `1.0 m`, `0.5 m`
- The current highest validated supported ODM DSM resolution under the formal
  gate is therefore:
  - `0.5 m`
- Practical interpretation of this result:
  - `0.5 m` passes the formal gate contract
  - `1.0 m` remains the more stable operational choice for predicted-ortho
    visual quality because `0.5 m` exhibits much higher nodata burden and
    stronger local distortion amplification

## 2026-04-18 SRTM Visual Smoothness Note
- The historical `sattruth_srtm_romatie` branch renders predicted orthophotos
  with the same best-pose reprojection logic, but keeps the runtime DSM source
  as `SRTM`.
- This branch may appear visually less distorted because:
  - the SRTM surface is much smoother and lower-frequency than the higher-detail
    ODM DSM rasters
  - smoother DSM relief suppresses local roof / road-edge warping, even when it
    is not the more physically faithful urban-surface model
- `viz_overlay_truth` under that branch is only a visualization export over the
  predicted ortho and truth crop; it is not produced by a different orthophoto
  reconstruction method.

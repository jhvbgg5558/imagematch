# 数据资产说明

这份文档描述当前新任务下哪些数据仍可视为有效，哪些旧数据已经失效。

## 1. 当前有效状态

截至 2026-03-19，当前项目已生成原始 query 候选集、原始裁块固定卫星库和对应真值资产。

- 当前已生成的数据资产：

  - `D:\数据\武汉影像\挑选无人机0.1m`
  - 内容：4 条航线各 10 张原始无人机图片，共 40 张
  - 附带文件：每航线 `selected_images.csv`、`selection_notes.md`，以及根目录 `selected_images_summary.csv`
  - 特点：保留原始 EXIF/XMP 地理信息，用于后续真值匹配
  - 备注：后续新一轮 query 重选会在 `new1output/` 下重新生成一套 40 张候选图、去元数据副本、真值表和可视化结果
  - `D:\aiproject\imagematch\output\fixed_satellite_library_4flights_raw_multiscale`
  - 内容：面向 4 条航线区域的固定多尺度卫星瓦片库主资产
  - 规模：`4682` 张卫星瓦片
  - 尺度：`80m / 120m / 200m`
  - 附带文件：`tiles.csv`、`roi_summary.json`、`tiles_native/`
  - 特点：卫星瓦片保存为原始裁块分辨率，不再强制统一到 `512x512`
  - `D:\aiproject\imagematch\output\query_truth_fixed_library_40_raw`
  - 内容：40 张 query 在固定卫星库上的真值主表与真值配对表
  - 附带文件：`queries_truth_seed.csv`、`query_truth.csv`、`query_truth_tiles.csv`、`per_query/`
  - 特点：每个 query 目录下复制的真值卫星图来自原始裁块固定库
  - `D:\aiproject\imagematch\output\fixed_satellite_library_4flights_raw_multiscale_80_120_200_300`
  - 内容：面向 4 条航线区域的四尺度固定卫星瓦片库主资产
  - 规模：`4935` 张卫星瓦片
  - 尺度：`80m / 120m / 200m / 300m`
  - 附带文件：`tiles.csv`、`roi_summary.json`、`tiles_native/`
  - 特点：作为后续 DINOv2 基线的主候选库
  - `D:\aiproject\imagematch\output\query_truth_fixed_library_40_raw_80_120_200_300`
  - 内容：40 张 query 在四尺度固定卫星库上的真值主表与真值配对表
  - 附带文件：`queries_truth_seed.csv`、`query_truth.csv`、`query_truth_tiles.csv`、`per_query/`
  - 特点：真值映射数提升到 `1092`，新增 `truth_count_300m`
  - `D:\aiproject\imagematch\output\query_sanitized_40_v2`
  - 内容：去除 EXIF/XMP/GPS/DJI 元数据后的 query 实验版
  - 附带文件：`images/`、`query_manifest.csv`
  - 特点：保留原文件名和航线目录，但模型只读取无元数据副本
  - `D:\aiproject\imagematch\output\dinov2_baseline_raw_40_query`
  - 内容：40 张去元数据 query 的 DINOv2 特征
  - 附带文件：`query_dinov2_pooler.npz`、`query_dinov2_pooler_status.csv`

- 当前保留但不再作为主资产的过渡产物：

  - `D:\aiproject\imagematch\output\fixed_satellite_library_4flights_80_120_200`
  - `D:\aiproject\imagematch\output\query_truth_fixed_library_40`
  - 说明：这两者是早期 `512x512` 版本，仅用于过渡参考，不再作为正式主资产

- 仍然无效或未完成的部分：

- query 输入定义已经根本变化
- 旧任务依赖正射 query 裁块和同尺度实验设计
- 旧预处理结果无法自动满足新的工程化输入约束
- 当前 40 张图还不是正式评测集，只是首轮原始 query 候选集

## 2. 当前视为失效的旧数据资产

以下内容不应直接作为当前正式实验输入：

- 旧 query 裁块
- 旧 query metadata
- 旧 query truth 定义
- 旧同尺度卫星瓦片库
- 旧特征库与 FAISS 索引
- 旧阶段性预处理结果

这些材料都已归档到 `../old/`，仅供历史参考，不视为当前已验证可用资产。

## 3. 当前可保留但未重新验证的原始来源

从项目历史材料看，仍可能相关但尚未在新任务下重新确认的数据来源包括：

- 无人机原始或原始近似输入影像
- 遥感正射影像底图

这些数据来源后续需要重新梳理，并按新任务重建资产说明。

## 4. 当前结论

- 当前已有可复用的原始 query 候选集
- 当前已有原始裁块固定卫星库与对应真值表
- 当前已有四尺度固定卫星库、四尺度真值表和去元数据 query 实验版
- 当前还没有正式检索结果和正式评测集
- 新任务仍需要继续建立完整数据链路

## 5. DOM+DSM+PnP Baseline v1 资产分层（实施准备）

这部分不是当前已落盘的数据资产，而是 pose baseline v1 实施准备阶段必须明确的资产分层口径。

- 运行输入
  - 去元数据 UAV query 图像
  - DOM 参考影像
  - DSM 栅格数据
  - query / DOM / DSM 的坐标系说明
  - coarse top-k 候选索引
  - `approx_intrinsics_v1` 配置
- 离线评估真值
  - 原始 EXIF/GPS/姿态信息副本
  - 飞控日志
  - 相机型号、焦距、传感器尺寸等可用于评估但不进入推理链路的元数据
- 仅辅助诊断
  - coarse 检索结果
  - RoMa 匹配点与置信度
  - DOM 像素到投影坐标的转换日志
  - DSM 采样日志与状态码
  - 2D-3D 对应点集
  - PnP 内点集、位姿参数、失败原因
- 结果目录建议
  - 新任务正式产物若生成，应统一落在 `new2output/pose_baseline_v1/` 下
  - 建议按 `plan/`、`eval/`、`viz/`、`reports/` 分层
  - 该目录当前仅为规划口径，不代表已生成结果

## 6. 后续需要补充

- 原始数据位置
- 数据权限与来源说明
- 新 query 样本定义
- 新卫星库定义
- 新 truth 或标注方案
- 新处理产物清单
- 模型专用输入缓存方案

## 2026-04-02 Formal Pose v1 Assets
- Active formal pose root: `new2output/pose_v1_formal/`.
- Runtime queries: `new1output/query_reselect_2026-03-26_v2/query_inputs/`.
- Runtime candidate registry: `output/coverage_truth_200_300_500_700_dinov2_baseline/fixed_satellite_library/tiles.csv`.
- Runtime candidate images: `output/coverage_truth_200_300_500_700_dinov2_baseline/fixed_satellite_library/tiles_native/`.
- Offline evaluation truth: `new1output/query_reselect_2026-03-26_v2/query_truth/`.
- Formal DSM cache manifest: `new2output/pose_v1_formal/input/formal_dsm_manifest.csv`.
- Formal DSM request list: `new2output/pose_v1_formal/dsm_cache/requests/srtm_download_requests.csv`.
- Historical debug pose root: `new2output/pose_baseline_v1/` is inactive and should not be used as formal evidence.

## 2026-04-02 Formal Pose v1 DSM Assets
- The current formal DSM source is one raw SRTM tile:
  - `new2output/N30E114.hgt`
- File check result:
  - exists
  - byte size matches `3601 x 3601 x 2`
  - usable as `SRTM 1 arc-second`
- Coverage check result:
  - required formal pose extent is fully inside `N30E114`
  - no additional SRTM tile is currently required for the active 40-query formal pose v1 run
- The raw HGT is an upstream source only; downstream formal DSM rasters still need to be materialized into:
  - `new2output/pose_v1_formal/dsm_cache/rasters/`
- The formal DSM request count is `199` because it is deduplicated from active `Top-20` runtime candidates, not from the full `1029`-tile satellite library.
## 2026-04-07 Formal Pose v1 Asset Execution Notes
- Raw DSM source remains `D:\aiproject\imagematch\new2output\N30E114.hgt`.
- Candidate-bound DSM outputs are expected under `D:\aiproject\imagematch\new2output\pose_v1_formal\dsm_cache\rasters\`.
- The authoritative candidate-to-DSM mapping remains `D:\aiproject\imagematch\new2output\pose_v1_formal\input\formal_dsm_manifest.csv`, where `dsm_id == candidate_tile_id == runtime candidate_id`.
- Formal DSM request status is tracked in:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\input\formal_dsm_manifest.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\dsm_cache\requests\srtm_download_requests.csv`

## 2026-04-10 009/010 Nadir Experiment Assets
- Isolated experiment root:
  - `D:\aiproject\imagematch\new2output\nadir_009010_dinov2_romav2_pose_2026-04-10\`
- Runtime query assets:
  - `selected_queries\selected_images_summary.csv`
  - `query_inputs\images\`
  - `query_inputs\query_manifest.csv`
- Offline truth assets:
  - `query_truth\queries_truth_seed.csv`
  - `query_truth\query_truth.csv`
  - `query_truth\query_truth_tiles.csv`
- Runtime retrieval and pose assets:
  - `retrieval\retrieval_top20.csv`
  - `pose_v1_formal\input\formal_query_manifest.csv`
  - `pose_v1_formal\input\formal_candidate_manifest.csv`
  - `pose_v1_formal\input\formal_dsm_manifest.csv`
  - `pose_v1_formal\manifest\pose_manifest.json`
- DSM source and cache:
  - upstream source remains `D:\aiproject\imagematch\new2output\N30E114.hgt`
  - materialized candidate DSM rasters are under `pose_v1_formal\dsm_cache\rasters\`
- Reused read-only assets:
  - fixed satellite library: `D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_dinov2_baseline\fixed_satellite_library\`
  - FAISS index: `D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_dinov2_baseline\faiss\satellite_tiles_ip.index`
  - tiles metadata: `D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_dinov2_baseline\fixed_satellite_library\tiles.csv`
- Script snapshot:
  - `D:\aiproject\imagematch\new2output\nadir_009010_dinov2_romav2_pose_2026-04-10\scripts\script_manifest.json`

## 2026-04-16 Satellite Truth Branch Inputs
- The satellite-truth subchain reuses the current 009/010 pose bundle as its starting point, but writes into the isolated new3output experiment root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\`
- Satellite truth source inputs are read from the refined truth coverage assets:
  - `output\coverage_truth_200_300_500_700_refined_truth_all40_valid06\query_truth.csv`
  - `output\coverage_truth_200_300_500_700_refined_truth_all40_valid06\query_truth_tiles.csv`
- These inputs are selection anchors only; the final satellite truth for each query is a cropped patch under the satellite-truth suite root.
- The satellite-truth branch does not replace the read-only runtime satellite library or FAISS assets used by the main pose chain.

## 2026-04-16 ODM Refresh Asset Overrides
- The new3output ODM-refresh branch introduces an explicit flight-level override manifest:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\plan\flight_asset_override_manifest.csv`
- This manifest is the authoritative asset indirection layer for the new branch and records, per flight:
  - `odm_orthophoto_path`
  - `odm_dsm_path`
  - `shots_geojson_path`
  - `cameras_json_path`
  - `asset_version_tag`
  - `status`
- Current ODM DSM source reality for flights 009/010:
  - an orthophoto and `shots.geojson` are present
  - a directly reusable raster DSM may be absent
  - when raster DSM is absent, `odm_georeferencing\odm_georeferenced_model.laz` is used as the ODM DSM-equivalent source for downstream rasterization
- The new ODM DSM cache branch is intended to write to:
  - `pose_v1_formal\dsm_cache\source\odm_dsm_merged.tif`
  - `pose_v1_formal\dsm_cache\rasters\`

## 2026-04-16 New3output Completed Asset State
- The completed new3output branch is rooted at:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\`
- Query-side assets were reused from the isolated 009/010 branch structure under the new root:
  - `selected_queries\selected_images_summary.csv`
  - `query_inputs\query_manifest.csv`
  - `query_truth\queries_truth_seed.csv`
  - `query_truth\query_truth.csv`
  - `query_truth\query_truth_tiles.csv`
- Runtime retrieval assets remained read-only reuse from the completed baseline branch:
  - `retrieval\retrieval_top20.csv`
  - `romav2_rerank\stage7\*`
  - fixed satellite library: `D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_dinov2_baseline\fixed_satellite_library\`
  - FAISS index: `D:\aiproject\imagematch\output\coverage_truth_200_300_500_700_dinov2_baseline\faiss\satellite_tiles_ip.index`
- New3output truth/DSM override assets were driven by:
  - `plan\flight_asset_override_manifest.csv`
- Actual new3output truth and DSM asset interpretation for the completed branch:
  - orthophoto truth came from the explicit ODM orthophoto override entries in the flight-asset manifest
  - PnP DSM came from ODM DSM-equivalent inputs
  - when a directly reusable raster DSM was absent, `odm_georeferencing\odm_georeferenced_model.laz` was rasterized into the branch-local DSM cache
- New branch-local DSM outputs are materialized under:
  - `pose_v1_formal\dsm_cache\source\`
  - `pose_v1_formal\dsm_cache\rasters\`
- New branch-local validation assets are split into two independent suites:
  - ODM truth suite:
    - `pose_v1_formal\eval_pose_validation_suite_odm_truth\`
  - satellite truth suite:
    - `pose_v1_formal\eval_pose_validation_suite_satellite_truth\`
- Satellite truth source inputs for the completed branch remained:
  - `output\coverage_truth_200_300_500_700_refined_truth_all40_valid06\query_truth.csv`
  - `output\coverage_truth_200_300_500_700_refined_truth_all40_valid06\query_truth_tiles.csv`
  - final truth objects are cropped truth patches under the satellite-truth suite root, not fixed library tiles

## 2026-04-16 Satellite Truth + SRTM + RoMa-Tiepoint Branch Assets
- A separate new3output branch for the `satellite truth + SRTM DSM + RoMa layer-3` route now exists at:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16\`
- Read-only reused assets are unchanged from the completed baseline pose branch:
  - `selected_queries\selected_images_summary.csv`
  - `query_inputs\query_manifest.csv`
  - `query_truth\queries_truth_seed.csv`
  - `query_truth\query_truth.csv`
  - `query_truth\query_truth_tiles.csv`
  - `retrieval\retrieval_top20.csv`
  - `romav2_rerank\stage7\*`
- Runtime DSM assets for this branch explicitly come from `SRTM`, not ODM overrides:
  - upstream source: `D:\aiproject\imagematch\new2output\N30E114.hgt`
  - request manifest: `pose_v1_formal\input\formal_dsm_manifest.csv`
  - materialized rasters: `pose_v1_formal\dsm_cache\rasters\`
  - gate snapshot: `planned_count = 195`, `built_count = 195`, `failed_count = 0`
- Satellite truth assets for this branch are generated under the suite root rather than borrowed from UAV orthophoto products:
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\satellite_truth\query_satellite_truth_manifest.csv`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\satellite_truth\truth_patches\`
- The current validation suite layout for this branch is:
  - layer-1 satellite alignment:
    - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\ortho_alignment_satellite\`
  - layer-2 pose-vs-reference:
    - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\pose_vs_at\`
  - layer-3 RoMa tie-point evaluation:
    - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\tiepoint_ground_error\`
- Current branch status is a `5-query gate` only:
  - gate pose summary: `pose_v1_formal\summary\phase_gate_summary.json`
  - gate suite summary: `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\phase_gate_summary.json`
  - no full-run `40-query` asset set is recorded yet for this branch

## 2026-04-17 Satellite Truth + SRTM + RoMa-Tiepoint Full Asset State
- The same branch now also contains a completed `40-query` full-run asset set:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16\`
- Full-run branch manifests and summaries:
  - `plan\run_sattruth_srtm_romatie_full_summary.json`
  - `pose_v1_formal\summary\pose_overall_summary.json`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\full_run_summary.json`
- Runtime pose assets now represent the full 40-query pass rather than only the gate subset:
  - `pose_v1_formal\pnp\pnp_results.csv`
  - `pose_v1_formal\scores\pose_scores.csv`
  - `pose_v1_formal\summary\per_query_best_pose.csv`
  - `pose_v1_formal\summary\per_flight_best_pose_summary.csv`
- Validation assets now represent the full 40-query pass:
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\satellite_truth\truth_patches\`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\pred_tiles\`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\ortho_alignment_satellite\`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\pose_vs_at\`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\tiepoint_ground_error\`
- Layer-3 RoMa detail assets for the full run include:
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\tiepoint_ground_error\per_query_tiepoint_ground_error.csv`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\tiepoint_ground_error\tiepoints\per_query_matches\`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\tiepoint_ground_error\viz_tiepoints\`
- Final reporting assets now exist for the full branch:
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\reports\formal_pose_v1_validation_suite_sattruth_srtm_report.docx`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\reports\pose_localization_accuracy_sattruth_srtm_romatie_report.docx`
  - `reports\sattruth_srtm_romatie_vs_baseline.md`
  - `reports\sattruth_srtm_romatie_vs_baseline.docx`
  - `reports\final_experiment_report_sattruth_srtm_romatie.md`
  - `reports\final_experiment_report_sattruth_srtm_romatie.docx`
  - `reports\final_experiment_report_assets\`
- Final report asset breakdown:
  - comparison charts: `overall_metrics_comparison.png`, `layer1_metrics_bar.png`, `layer2_metrics_bar.png`, `layer3_metrics_bar.png`
  - diagnostic charts: `low_match_queries_improvement.png`, `runtime_status_comparison.png`, `pipeline_overview.png`
  - per-case visualization panels and source images under `reports\final_experiment_report_assets\sample_cases\`
## 2026-04-20 CaiWangCun Candidate-DOM + DSM Gate Assets
- Branch root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_caiwangcun_candidate_domdsm_0p14m_gate_2026-04-20\`
- Candidate DOM cache:
  - `pose_v1_formal\dom_cache\rasters\*.tif`
  - `pose_v1_formal\dom_cache\rasters\_summary.json`
  - built from `source_mosaic\caiwangcun_ortho_0p14m_epsg32650.tif`
  - `planned_count = 50`, `built_count = 50`, `failed_count = 0`
- DSM cache:
  - `pose_v1_formal\dsm_cache\rasters\*.tif`
  - `pose_v1_formal\dsm_cache\rasters\_summary.json`
  - built from `source_mosaic\caiwangcun_dsm_0p14m_epsg32650.tif`
- Formal inputs:
  - `pose_v1_formal\input\formal_candidate_manifest.csv` now points gate
    candidate DOM image paths at CaiWangCun DOM crops and stores matching affine transforms
  - `pose_v1_formal\manifest\pose_manifest.json` was rebuilt from these branch-local inputs

## 2026-04-20 CaiWangCun DOM/DSM Gate Assets
- New branch root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_caiwangcun_domdsm_0p14m_gate_2026-04-20\`
- Source inputs:
  - `D:\数据\武汉影像\CaiWangCun-DOM\CaiWangCun-DOM_ortho_part_*_*.tif`
  - `D:\数据\武汉影像\CaiWangCun-DOM\CaiWangCun-DOM_DSM_part_*_*.tif`
  - source CRS: `CGCS2000 / 3-degree Gauss-Kruger CM 114E`
  - source resolution: `0.14 m`
- Branch-local mosaics:
  - `source_mosaic\caiwangcun_ortho_0p14m_epsg32650.tif`
  - `source_mosaic\caiwangcun_dsm_0p14m_epsg32650.tif`
  - `source_mosaic\caiwangcun_mosaic_summary.json`
- Branch-local planning manifests:
  - `plan\caiwangcun_asset_manifest.csv`
  - `plan\caiwangcun_source_tile_manifest.csv`
  - `plan\caiwangcun_candidate_coverage_audit.csv`
  - `plan\caiwangcun_dsm_request_coverage_audit.csv`
  - `plan\caiwangcun_coverage_summary.json`
- Formal pose inputs were rebuilt under:
  - `pose_v1_formal\input\formal_query_manifest.csv`
  - `pose_v1_formal\input\formal_candidate_manifest.csv`
  - `pose_v1_formal\input\formal_truth_manifest.csv`
  - `pose_v1_formal\input\formal_dsm_manifest.csv`
  - `pose_v1_formal\manifest\pose_manifest.json`
- DSM cache is CaiWangCun-only:
  - source copy: `pose_v1_formal\dsm_cache\source\caiwangcun_dsm_0p14m_epsg32650.tif`
  - rasters: `pose_v1_formal\dsm_cache\rasters\*.tif`
  - summary: `pose_v1_formal\dsm_cache\rasters\_summary.json`
- Reused read-only runtime assets remain from:
  - `D:\aiproject\imagematch\new2output\nadir_009010_dinov2_romav2_pose_2026-04-10\`
  - reused directories: `selected_queries`, `query_inputs`, `query_truth`,
    `query_features`, `retrieval`, `romav2_rerank`
- Excluded source rule:
  - no ODM LAZ, ODM-derived DSM raster, SRTM HGT, or satellite-truth patch was
    used as a fallback in this branch

## 2026-04-21 CaiWangCun DOM/DSM Full-Replacement Gate Assets
- Branch root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20\`
- CaiWangCun source mosaics:
  - DOM: `source_mosaic\caiwangcun_ortho_0p14m_epsg32650.tif`
  - DSM: `source_mosaic\caiwangcun_dsm_0p14m_epsg32650.tif`
  - CRS: `EPSG:32650`
  - source CRS recorded as `CGCS2000 / 3-degree Gauss-Kruger CM 114E`
  - DOM is RGB `uint8`; DSM is single-band `float32`
  - resolution is approximately `0.1400458 m`
- Candidate library was rebuilt from CaiWangCun DOM/DSM coverage:
  - `candidate_library\tiles.csv`
  - tile sizes: `200 m`, `300 m`, `500 m`, `700 m`
  - tile count: `149`
  - all retained tiles are within the CaiWangCun DOM/DSM fully-covered area
- Candidate retrieval assets were rebuilt:
  - `candidate_features\caiwangcun_tile_dinov2_pooler.npz`
  - `candidate_features\caiwangcun_tile_dinov2_status.csv`
  - `faiss\caiwangcun_tiles_ip.index`
  - `faiss\caiwangcun_tiles_ip_mapping.json`
  - `romav2_rerank\coarse\retrieval_top20.csv`
  - `romav2_rerank\stage7\*\reranked_top20.csv`
- Formal pose assets were rebuilt:
  - `pose_v1_formal\input\formal_candidate_manifest.csv`
  - `pose_v1_formal\input\formal_dsm_manifest.csv`
  - `pose_v1_formal\manifest\pose_manifest.json`
  - `pose_v1_formal\dsm_cache\rasters\*.tif`
  - DSM cache rasters all derive from the CaiWangCun DSM mosaic
- Reused assets are limited to:
  - `selected_queries`
  - `query_inputs`
  - `query_truth`
  - `query_features`
- Excluded source rule:
  - no old satellite candidate library, ODM LAZ/DSM, or SRTM HGT is used as a
    runtime fallback in this full-replacement gate branch

## 2026-04-22 CaiWangCun DOM/DSM Full-Replacement Full Assets
- Branch root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21\`
- Asset origin and migration note:
  - the full run used branch-local CaiWangCun source mosaics already copied into
    the full root, so it did not need to re-read the external raw tile folder
    during pose/validation/reporting
  - if raw CaiWangCun tiles need to be re-read in a later task, the source data
    may now reside under `E:\数据\武汉影像\` with the same content and directory
    structure as the earlier `D:\数据\武汉影像\` location
- Full-root source mosaics:
  - DOM: `source_mosaic\caiwangcun_ortho_0p14m_epsg32650.tif`
  - DSM: `source_mosaic\caiwangcun_dsm_0p14m_epsg32650.tif`
  - CRS: `EPSG:32650`
  - resolution remains approximately `0.14 m`
- Candidate and retrieval assets:
  - `candidate_library\tiles.csv`
  - tile count: `149`
  - `candidate_features\caiwangcun_tile_dinov2_pooler.npz`
  - `candidate_features\caiwangcun_tile_dinov2_status.csv`
  - `faiss\caiwangcun_tiles_ip.index`
  - `faiss\caiwangcun_tiles_ip_mapping.json`
  - `retrieval\retrieval_top20.csv`
  - `romav2_rerank\stage7\*\reranked_top20.csv`
- Formal pose assets:
  - `pose_v1_formal\input\formal_query_manifest.csv`
  - `pose_v1_formal\input\formal_candidate_manifest.csv`
  - `pose_v1_formal\input\formal_dsm_manifest.csv`
  - `pose_v1_formal\manifest\pose_manifest.json`
  - `pose_v1_formal\dsm_cache\rasters\*.tif`
  - DSM cache rasters all derive from the full-root CaiWangCun DSM mosaic;
    cache summary reports `planned_count = 119`, `built_count = 119`,
    `failed_count = 0`
- Reused assets remain limited to query-side products:
  - `selected_queries`
  - `query_inputs`
  - `query_truth`
  - `query_features`
- Excluded source rule:
  - no ODM LAZ/DSM, SRTM HGT, or old satellite candidate library fallback was
    used by the full-replacement full run

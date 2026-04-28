# 项目当前进度

最后更新：2026-04-09

## 1. 当前主任务

当前主任务是论证：

> 在更贴近工程实际的输入条件下，仅依赖遥感正射影像，能否实现对任意单张无人机影像的初步地理定位（检索）。

这里的 query 输入约束为：

- 没有地理信息
- 不保证为正射影像
- 不对输入分辨率做外部人工统一处理，除非该处理是模型内部固有流程

## 2. 当前状态

- 项目已从旧的严格同尺度任务切换到新的工程化任务
- 旧任务资料已归档到 `old/`
- 当前已经建立新的正式数据口径，并完成首轮到次轮基线验证
- 当前已建立固定卫星库上的首轮真值定义，并进一步切换到 coverage 真值定义
- 当前已完成首轮 DINOv2 基线检索结果，并完成一轮更大尺度覆盖真值实验
- 当前已完成原始无人机图像代表样本首轮挑选
- 当前已在 `D:\数据\武汉影像\挑选无人机0.1m` 生成 4 条航线共 40 张原始 query 候选图
- 当前正在启动新一轮 query 重选，倾角窗口收紧为 `-85 ~ -40`，并尽量让下视与倾斜样本各占约一半
- 当前新一轮过程文件与可视化结果将统一放入 `new1output/`
- 当前已在项目 `output/` 下生成 4 航线区域固定卫星库与对应真值表
- 当前固定卫星库主资产已经切换为原始裁块分辨率，不再把 `512x512` 视为正式主资产
- 当前已完成 `80/120/200/300m` 四尺度 raw 固定卫星库
- 当前已完成 40 张 query 的去元数据实验版
- 当前已完成 4 尺度真值重算
- 当前 DINOv2 基线已完成 query 特征提取、卫星特征提取、FAISS 建库和检索评估
- 当前已完成 `80/120/200m` vs `80/120/200/300m` 首轮对照
- 当前已完成 `200/300/500/700m` 四尺度固定卫星库、coverage 真值重算与 DINOv2 baseline 检索
- 当前已完成 refined truth 规则的全量 `40` query 稳定性验证
- 当前已完成 DINOv2 baseline 在 `strict_truth` 口径下的正式重评估
- 当前已完成 DINOv2 baseline 在 `intersection truth` 口径下的正式重评估，基线报告已归档
- 当前已完成 `query v2 + intersection truth` 口径下的 `DINOv3 + FAISS` 基线检索与正式报告
- 当前已完成 `DINOv3 vs DINOv2` 在 `query v2 + intersection truth` 口径下的正式对比，当前结论为 `DINOv2` 更强
- 当前已进入新口径结果分析、可视化与文档归档阶段
- 当前已完成 LightGlue `rank1` 候选的全量 `40` query inlier 连线可视化（SuperPoint + LightGlue + RANSAC）
- 当前该批次结果已核对：`40/40` 图生成完成，汇总文件已落盘
- 当前已完成 LightGlue 在 `intersection truth` 口径下的正式结果报告，`md` 和 `docx` 均已生成，且中文显示正常
- 当前已启动 LightGlue top10 同名点可视化批处理，输出目录为 `newoutput/lightglue_top10_inlier_viz_2026-03-26/figures`
- 当前 LightGlue top10 同名点可视化已开始落盘，目录按 `航线/query/rank` 分层组织
- 当前已完成 `RoMa v2` 在 `DINOv3 coarse Top-20` 基础上的 `intersection truth` 正式重排实验
- 当前已修复 WSL 环境下的 GPU 可用性，`RoMa v2` 已在 `cuda` 模式下完成全量 `40` query 正式运行
- 当前已完成 `RoMa v2 vs DINOv3 baseline` 的整体指标汇总、分航线结果导出与可视化落盘
- 当前已完成 `RoMa v2` 正式汇报文档，`md` 和 `docx` 均已生成
- 当前已完成 `DOM+DSM+PnP Baseline v1` 实施计划文档定稿，文档落盘到 `new2output/DOM+DSM+PnP 位姿恢复实施计划（Baseline v1）.docx`
- 当前新任务已切换到实施准备阶段，正在按 `Agent1 / Agent2 / Agent3` 编排推进文档、脚本与审查边界，尚未开始正式实验结果统计

## 3. 当前明确失效的旧基础

以下内容不再直接作为当前任务的正式依据：

- `200m query vs 200m satellite` 同尺度口径
- query 中心点落入卫星瓦片的旧真值定义
- 基于正射 query 裁块构建的旧验证集
- 旧任务中的卫星瓦片预处理与查询预处理结果
- 旧任务形成的正式结果链路与结论

## 4. 当前有效结论

- 旧任务结论不能直接外推到当前新任务
- 当前必须重新定义 query、candidate、truth、evaluation 和 deployment assumptions
- 在新方案确定前，不应引用旧结果作为当前正式性能结论
- 当前首轮真值定义已经从“单块真值”切换为“固定卫星库中的多候选真值集合”
- 当前首轮 DINOv2 基线结果显示：加入 `300m` 后，`Recall@1` 从 `0.050` 提升到 `0.125`，`MRR` 从 `0.142` 提升到 `0.193`
- 当前首轮 DINOv2 基线结果显示：`Recall@5` 保持 `0.275` 不变，`Recall@10` 从 `0.350` 小幅升到 `0.375`
- 当前首轮 DINOv2 基线结果显示：`300m` 带来了 `3` 个新增 Top-1 命中样本，但 `Top-1 error mean` 从约 `712.840m` 上升到约 `778.538m`
- 当前次轮实验已把尺度改为 `200/300/500/700m`
- 当前次轮实验已把真值定义改为“query 近似地面覆盖框与卫星瓦片地面覆盖框相交比例大于 `0.4` 视为真值”
- 当前次轮实验在 `40` 个 query、`1029` 个卫星 tiles 的口径下得到：`coverage R@1=0.200`、`R@5=0.400`、`R@10=0.475`、`MRR=0.290`
- 当前次轮实验的辅助中心点口径结果为：`center R@1=0.175`、`R@5=0.275`、`R@10=0.325`
- 当前次轮实验的 `Top-1 error mean` 约为 `759.071m`
- 当前 refined truth 规则定义为：`coverage_ratio >= 0.4` 且 `valid_pixel_ratio >= 0.6` 记为 `strict_truth`，其余 coverage 命中但有效内容不足的 tile 记为 `soft_truth`
- 当前 refined truth 已在全量 `40` 个 query 上验证：`40/40` query 有真值，`40/40` query 有 `strict_truth`，且 `40/40` query 满足 `strict_truth_count >= 2`
- 当前 refined truth 全量稳定性结果显示：平均每个 query 有 `10.68` 个 truth，其中 `3.12` 个为 `strict_truth`
- 当前新结果说明：更大尺度与 coverage 真值口径已经形成一条完整可复用的评估链路，但仍需要继续分析哪些 query 受益、哪些失败模式仍然稳定存在
- 当前新结果说明：refined truth 已满足“每个 query 稳定存在主真值”的最低要求，可以作为后续重评估基线的候选正式口径
- 当前 strict truth 正式重评估结果为：`strict R@1=0.175`、`R@5=0.375`、`R@10=0.425`、`MRR=0.262`
- 当前 strict truth 与旧 coverage 结果对比表明：主指标出现小幅下降，但 `Top-1 error mean` 基本不变，说明变化主要来自真值口径净化，而非检索排序变化
- 当前结果说明：`strict_truth` 已具备作为后续正式主评估口径的条件
- 当前 LightGlue rank1 inlier 汇总结果（40 query）为：`inlier=4` 有 `33` 个、`inlier=5` 有 `7` 个；其中 `strict_hit@1` 分别为 `6` 和 `0`
- 当前 DINOv2 baseline 在 `intersection truth` 口径下的正式结果为：`R@1=0.525`、`R@5=0.800`、`R@10=0.900`、`R@20=0.975`、`MRR=0.654`、`Top-1 error mean=759.071m`
- 当前 LightGlue 在 `intersection truth` 口径下的正式结果为：`R@1=0.525`、`R@5=0.775`、`R@10=0.925`、`R@20=0.975`、`R@50=1.000`、`MRR=0.649`、`Top-1 error mean=677.336m`
- 当前 LightGlue top10 同名点可视化已按 `flight_id/query_id/rank` 层级开始生成，单张图采用“左 query、右卫片、只画 inlier 连线”的格式
- 当前 `DINOv3 + FAISS` 在 `query v2 + intersection truth` 口径下的正式结果为：`R@1=0.775`、`R@5=0.950`、`R@10=1.000`、`R@20=1.000`、`MRR=0.850`、`Top-1 error mean=862.191m`
- 当前 `DINOv3 vs DINOv2` 对比结果表明：`DINOv3` 未优于 `DINOv2`，差距主要体现在前排排序判别力和 `Top-1 error mean`
- 当前 `RoMa v2` 在 `query v2 + intersection truth` 口径下的正式结果为：`R@1=0.925`、`R@5=1.000`、`R@10=1.000`、`R@20=1.000`、`MRR=0.958`、`Top-1 error mean=630.313m`
- 当前 `RoMa v2 vs DINOv3 baseline` 对比结果表明：`RoMa v2` 将 `R@1` 从 `0.775` 提升到 `0.925`，`MRR` 从 `0.850` 提升到 `0.958`，并将 `Top-1 error mean` 从 `862.191m` 降到 `630.313m`
- 当前 `RoMa v2` 分航线结果显示：四条航线的 `R@1` 分别为 `0.9 / 1.0 / 0.9 / 0.9`，说明提升不是单航线偶然收益

## 5. 当前目录状态

- 当前活动文档位于 `docs_md/`
- 历史材料位于 `old/`
- 新任务已新增原始图像挑选脚本
- 新一轮 query 重选将沿用 `select_raw_uav_images.py`，但使用新的倾角窗口与平衡规则
- 新任务的首轮 query 候选集已落盘到外部数据目录
- 新任务的原始裁块固定卫星库已落盘到 `output/fixed_satellite_library_4flights_raw_multiscale`
- 新任务的原始裁块真值表已落盘到 `output/query_truth_fixed_library_40_raw`
- 新任务的四尺度原始裁块固定卫星库已落盘到 `output/fixed_satellite_library_4flights_raw_multiscale_80_120_200_300`
- 新任务的四尺度原始裁块真值表已落盘到 `output/query_truth_fixed_library_40_raw_80_120_200_300`
- 新任务的去元数据 query 实验版已落盘到 `output/query_sanitized_40_v2`
- 新任务的 DINOv2 query 特征已落盘到 `output/dinov2_baseline_raw_40_query`
- 新任务的 DINOv2 三尺度 vs 四尺度对照结果已落盘到 `output/dinov2_retrieval_compare_3scale_vs_4scale`
- 新任务的 `200/300/500/700m` coverage 真值基线结果已落盘到 `output/coverage_truth_200_300_500_700_dinov2_baseline`
- 新任务的 `intersection truth` 基线结果已落盘到 `newoutput/dinov2_rerun_intersection_truth_250m_2026-03-24`
- 新任务的 `query v2 + intersection truth` DINOv2 正式结果已落盘到 `new1output/query_reselect_2026-03-26_v2`
- 新任务的 `query v2 + intersection truth` DINOv3 正式结果已落盘到 `new1output/query_reselect_2026-03-26_v2/dinov3_eval_2026-03-30`
- 新任务的 `DINOv3 vs DINOv2` 正式对比说明已落盘到 `new1output/query_reselect_2026-03-26_v2/dinov3_eval_2026-03-30/reports`
- 新任务的全量 refined truth 稳定性结果已落盘到 `output/coverage_truth_200_300_500_700_refined_truth_all40_valid06`
- 新任务的 strict truth 正式重评估结果已落盘到 `output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval`
- 新任务的 LightGlue rank1 inlier 连线可视化结果已落盘到 `newoutput/lightglue_rank1_inlier_viz_2026-03-24/figures_rank1_40`
- 新任务的 LightGlue rank1 inlier 汇总表已落盘到 `newoutput/lightglue_rank1_inlier_viz_2026-03-24/summary_rank1_inliers.csv`
- 新任务的 LightGlue rank1 inlier 汇总说明已落盘到 `newoutput/lightglue_rank1_inlier_viz_2026-03-24/summary_rank1_inliers.md`
- 新任务的 LightGlue intersection truth 正式报告已落盘到 `newoutput/lightglue_intersection_truth_top50_k256_2026-03-24/reports`
- 新任务的 LightGlue top10 同名点可视化工作目录已创建到 `newoutput/lightglue_top10_inlier_viz_2026-03-26`
- 新任务的 LightGlue top10 同名点可视化结果已开始落盘到 `newoutput/lightglue_top10_inlier_viz_2026-03-26/figures`
- 新任务的 `RoMa v2` GPU 正式结果已落盘到 `new1output/query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_gpu`
- 新任务的 `RoMa v2` GPU 汇总文件包括 `overall_summary.json`、`aggregate_summary.json`、`per_query_comparison.csv`、`per_flight_comparison.csv` 和 `figures/_aggregate`
- 新任务的 `RoMa v2` 正式汇报文档已落盘到 `new1output/query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_gpu/reports`
- 新任务的 `RoMa v2` CPU 目录 `new1output/query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_cpu` 仅保留为早期未完成尝试，不再作为正式结论依据
- 当前已新建 `new1output/benefit_boundary_analysis_2026-03-31`，用于集中落盘 RoMa v2 收益边界分析的计划、表格、图件、案例、审查记录与阶段报告
- 当前已完成收益边界分析首轮正式产物生成：`A=31`、`B=6`、`C=3`、`D=0`，新增 `Top-1` 命中全部来自 `B` 类，说明当前收益主要来自“coarse 已召回、RoMa 纠正前排排序”
- 当前收益边界分析显示：`C` 类均为 `C_retained + C_near_miss`，暂未观察到 `C_drop_out`；当前 coarse 源下 `D=0`，说明本轮瓶颈主要不在 coarse Top-20 recall
- 当前已新增 `scripts/generate_benefit_boundary_word_report.py`，用于把收益边界分析的正式 Markdown 报告、核心表格和图件导出为带图 `docx`
- 当前已生成收益边界分析 Word 报告：`new1output/benefit_boundary_analysis_2026-03-31/reports/benefit_boundary_analysis_report.docx`，其中已嵌入 7 张汇总图和 `B` 类 6 张 query 可视化图
- 当前已新增 `scripts/visualize_romav2_top20_match_points.py`，用于对 `RoMa v2` 正式 `Top-20` 重排结果复算匹配点并生成“左 query、右卫片、仅画 inlier 连线”的同名点可视化
- 当前 `RoMa v2` 同名点可视化计划输出目录固定为 `new1output/romav2_top20_match_viz_2026-04-01`，实际全量生成需在 Ubuntu/WSL 的 `romav2 + GPU` 环境中运行
- 当前已新增 `scripts/run_romav2_dinov2_intersection_bundle.py`，用于把 `DINOv2 coarse + RoMa v2` 这一轮计划包装成单一入口，并将结果固定写入 `new1output/romav2_dinov2_intersection_2026-04-01/eval` 与 `new1output/romav2_dinov2_intersection_2026-04-01/viz_top20_match_points`
- 当前已在 `new1output/romav2_dinov2_intersection_2026-04-01/plan` 下补充 agent 协作说明与 reviewer checklist；该目录目前属于执行准备状态，尚未形成新的正式指标结论
- 截至 `2026-04-01` 当前已在 WSL 的 `.conda` 环境中正式启动 `scripts/run_romav2_dinov2_intersection_bundle.py --device cuda`
- 当前 `new1output/romav2_dinov2_intersection_2026-04-01/eval/coarse` 已完成 `retrieval_top20.csv`、`summary_top20.json` 与 `topk_truth_curve_top20.csv` 落盘
- 当前 `new1output/romav2_dinov2_intersection_2026-04-01/eval/input_round` 已完成 `stage3/` 与 `stage4/` 输入准备
- 当前正式运行已进入 `eval/stage7` 的 `RoMa v2` 重排阶段，正在处理第一条航线 `DJI_202510311347_009_新建面状航线1`
- 当前 `new1output/romav2_dinov2_intersection_2026-04-01` 尚未完成 overall 汇总、正式报告与 `viz_top20_match_points` 可视化；在整轮运行结束前不得把该目录内容当作最终正式结论
- 新任务的 coverage 基线可视化规范文档位于 `docs_md/VISUALIZATION_STYLE.md`
- 当前 `DOM+DSM+PnP Baseline v1` 的计划文档已落盘到 `new2output/DOM+DSM+PnP 位姿恢复实施计划（Baseline v1）.docx`
- 当前 `DOM+DSM+PnP Baseline v1` 的预期结果根目录建议为 `new2output/pose_baseline_v1/`，并按 `plan/`、`eval/`、`viz/`、`reports/` 分层；该目录目前仅为规划口径，不代表已生成结果
- 旧的 `output/fixed_satellite_library_4flights_80_120_200` 和 `output/query_truth_fixed_library_40` 仅保留为过渡版 `512` 资产，不再作为正式主资产
- 新任务的首轮正式检索实验已完成
- 新任务的次轮 coverage 正式检索实验已完成，当前正在补全图表与文档归档

## 6. 下一步建议

- 对照原 coverage 真值结果，分析具体哪些 query 从命中变成未命中
- 分析 strict truth 下不同尺度的真值保留比例与命中贡献
- 分析 `500/700m` 在 `strict_truth` 口径下的保留比例与贡献
- 梳理 `soft_truth` 里被降级的黑边或低有效内容 tile，确认过滤规则是否还需微调
- 视需要继续尝试 coverage 阈值或 `min_valid_ratio` 的稳健性分析
- 基于 `summary_rank1_inliers.csv`，抽样复核低 inlier 样本，确认“少量几何约束导致重排收益有限”的结论边界
- 基于 `per_query_comparison.csv` 分析 `RoMa v2` 获益最大的 query 类型，确认几何重排主要纠正的是哪类前排误排
- 视需要进一步比较 `RoMa v2` 与 LightGlue 在同一 `intersection truth` 口径下的收益边界与时间成本
- 按 `DOM+DSM+PnP Baseline v1` 实施计划，先完成坐标链路验证、DSM 采样骨架和 2D-3D 对应构造脚本的最小闭环
- 先由 `Agent3` 审查新链路的退出规则、日志状态码与 PnP 参数口径，再进入小样本运行
- 新任务正式产物若生成，应统一沉淀到 `new2output/pose_baseline_v1/` 下，不混入旧的检索结果目录

## 7. 更新规则

后续更新本文件时，建议保持以下结构不变：

- 当前主任务
- 当前状态
- 当前明确失效的旧基础
- 当前有效结论
- 当前目录状态
- 下一步建议

## 8. DOM+DSM+PnP Baseline v1 真实小样本闭环进展（2026-04-02）

- 已在 `new2output/pose_baseline_v1/` 下完成 1 条真实输入小样本闭环调试链路：`query -> DOM patch -> local DSM -> RoMa v2 -> 2D-3D -> PnP -> score -> summary`
- 当前样本为 `DJI_202510311347_009_新建面状航线1 / DJI_20251031135154_0001_V.JPG`，用途仅为真实输入几何闭环调试，不是正式 retrieval 评估样本
- 当前 real sample case 输入位于 `new2output/pose_baseline_v1/real_sample_case/input/`
- 当前真实样本 RoMa 匹配输出位于 `new2output/pose_baseline_v1/matches/roma_matches.csv`
- 当前真实样本 DSM 采样汇总显示：`5000` 条匹配中 `ok=2802`、`nodata=2128`、`unstable_local_height=70`
- 当前真实样本 PnP 已跑通，结果位于 `new2output/pose_baseline_v1/pnp/pnp_results.csv`，当前记录为 `inlier_count=61`、`refined reproj error=5.185 px`
- 当前真实样本 summary 已落盘到 `new2output/pose_baseline_v1/summary/pose_overall_summary.json`
- 当前这条链路只能说明“脚本与数据接口已能在真实输入上跑通”，不能据此宣称 pose baseline 已达到可接受定位精度
- 当前观察到相机中心相对 debug patch 中心仍约有 `614m` 平面偏差，说明后续优先问题仍是 DSM 质量、匹配点质量与位姿合理性约束，而不是单纯的脚本可执行性

## 2026-04-02 Formal Pose v1 Update
- Active pose workspace switched to `new2output/pose_v1_formal/`.
- Formal runtime asset chain is now locked as `query_inputs -> retrieval_top20 -> fixed_satellite_library/tiles.csv -> candidate bbox + 250m SRTM cache -> pose_v1_formal`.
- `query_truth` remains offline evaluation only and is not used to resolve runtime candidate assets.
- `new2output/pose_baseline_v1/` debug work is historical only and must not be treated as the active formal root.
- Current implementation status: formal query manifest, candidate manifest, DSM cache manifest, asset validation report, and unified pose manifest have been generated successfully.
- Current next steps: download/populate SRTM cache, run formal RoMa v2 small-sample matching, then continue formal correspondence, DSM sampling, and PnP validation.

## 2026-04-02 Formal Pose v1 Input Status
- Formal input generation has completed under `new2output/pose_v1_formal/`.
- Generated formal manifests:
  - `input/formal_query_manifest.csv`
  - `input/formal_candidate_manifest.csv`
  - `input/formal_truth_manifest.csv`
  - `input/formal_dsm_manifest.csv`
  - `manifest/pose_manifest.json`
  - `input/asset_validation_report.json`
- Validation summary:
  - `query_count = 40`
  - `candidate_count = 800`
  - `candidate_pairs_in_truth_manifest = 473`
  - `dsm_source_count = 199`
  - `queries_missing_intrinsics = 0`
  - `coarse_rows_with_missing_dom = 0`
  - `is_valid = true`
- Formal DSM planning is now based on `199` unique candidate tiles deduplicated from the `40 x Top-20 = 800` query-candidate pairs, not on the full satellite library size.
- The downloaded raw SRTM tile `new2output/N30E114.hgt` has been checked and is valid as a standard `3601 x 3601` 1 arc-second HGT tile.
- Current blocker has shifted from asset discovery to raster preparation: the raw HGT still needs to be converted/cropped into per-candidate DSM rasters under `new2output/pose_v1_formal/dsm_cache/rasters/`.

## 2026-04-02 DINOv2 + RoMa v2 Inlier-Only Rerank
- New entrypoints added for the rerank experiment:
  - `scripts/run_romav2_dinov2_inliercount_rerank_round.py`
  - `scripts/run_romav2_dinov2_inliercount_rerank_bundle.py`
- The new bundle is locked to:
  - input assets from `new1output/query_reselect_2026-03-26_v2`
  - output root `new2output/romav2_dinov2_inliercount_rerank_2026-04-02`
- Rerank mode is `inlier_count_only`, meaning final rank is driven by RoMa v2 inlier count with stable geometric tie-breaking.
- Existing `new1output` DINOv2 + RoMa v2 results remain unchanged and are still the formal baseline for the earlier bundle.
- Bundle plan and review notes now live under:
  - `new2output/romav2_dinov2_inliercount_rerank_2026-04-02/plan/`
## 2026-04-07 Formal Pose v1 Scoring/Summary
- Stable formal scoring entrypoint:
  - `D:\aiproject\imagematch\scripts\score_formal_pose_results.py`
- Shared implementation:
  - `D:\aiproject\imagematch\scripts\run_pose_v1_formal_scoring_summary.py`
- Formal scoring chain inputs:
  - `--bundle-root`
  - `--pnp-results-csv`
- Formal scoring chain outputs:
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\scores\pose_scores.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\summary\per_query_best_pose.csv`
  - `D:\aiproject\imagematch\new2output\pose_v1_formal\summary\pose_overall_summary.json`
- This closes the scoring/summary half of the formal pose pipeline; DSM raster preparation and full formal execution remain the next active gate.
## 2026-04-07 Formal Pose v1 Implementation Update
- Added `scripts/materialize_formal_dsm_rasters.py` to convert the locked raw SRTM source `new2output/N30E114.hgt` into per-candidate DSM GeoTIFF rasters for `new2output/pose_v1_formal/dsm_cache/rasters/`.
- Updated `scripts/sample_dsm_for_dom_points.py` so formal DSM sampling is now routed by `candidate_id == dsm_id` instead of a single global DSM source, with explicit `missing_dsm_raster` handling.
- Formal scoring/summary outputs are now aligned to the active formal root `new2output/pose_v1_formal/`, with explicit outputs:
  - `scores/pose_scores.csv`
  - `summary/per_query_best_pose.csv`
  - `summary/pose_overall_summary.json`
- Added `scripts/run_formal_pose_v1_pipeline.py` for the 3-5 query phase-gate run before expanding to the full 40-query formal set.
- Added `scripts/score_formal_pose_results.py` as the stable formal scoring entrypoint.
- Added agent workflow/checklist docs under `new2output/pose_v1_formal/plan/` to preserve Agent1 / Agent2 / Agent3 responsibilities for supervision, implementation, and review.
## 2026-04-07 Formal Pose v1 Runtime Gate Status
- Formal DSM raster materialization has completed successfully:
  - `new2output/pose_v1_formal/dsm_cache/rasters/_summary.json`
  - `planned_count = 199`
  - `built_count = 199`
  - `failed_count = 0`
- A formal phase-gate sample run has completed under the active formal root with:
  - `query_ids = [q_001, q_011, q_021]`
  - `query_count = 3`
  - `pair_count = 60`
  - `RoMa rows = 120000`
  - `correspondence ok = 120000`
  - `DSM sampling ok = 120000`
  - `PnP status_counts = {ok: 59, pnp_failed: 1}`
- Runtime summaries now exist at:
  - `new2output/pose_v1_formal/summary/phase_gate_summary.json`
  - `new2output/pose_v1_formal/summary/pose_overall_summary.json`
  - `new2output/pose_v1_formal/summary/per_query_best_pose.csv`
- Current next step has shifted from the validated 3-query phase gate to the full 40-query formal run.
## 2026-04-07 Formal Pose v1 Full-40 GPU Run Status
- A full formal run for all `40` queries has been launched from the validated phase-gate chain in the WSL `.conda` environment with GPU enabled.
- Active command family:
  - `scripts/run_formal_pose_v1_pipeline.py --bundle-root new2output/pose_v1_formal --phase full --device cuda --skip-dsm-build --sample-count 2000`
- The active runtime root remains:
  - `new2output/pose_v1_formal/`
- The older conflicting full-run attempt with `sample_count = 5000` was terminated to avoid overwriting the active formal outputs.
- The active surviving process is the `sample_count = 2000` full run, which is now the only formal full-run process allowed to write under `new2output/pose_v1_formal/`.
- Runtime logs for the active launch are reserved at:
  - `new2output/pose_v1_formal/logs/full40_gpu_stdout.log`
  - `new2output/pose_v1_formal/logs/full40_gpu_stderr.log`
- As of `2026-04-07 23:25:31 +08:00`, the active stage is still the RoMa export stage for the full `40 x Top-20 = 800` query-candidate pairs, so final `sampling/`, `pnp/`, `scores/`, and `summary/` outputs should not yet be treated as full-run-complete until the active process exits.
## 2026-04-09 Formal Pose v1 Full-40 Completion Status
- The full `40-query` formal run has now completed through `matches -> correspondences -> sampling -> pnp -> scores -> summary` under `new2output/pose_v1_formal/`.
- Full-run runtime scale:
  - `query_count = 40`
  - `candidate_count = 800`
  - `RoMa rows = 1,600,000`
  - `correspondence ok = 1,600,000`
  - `DSM sampling ok = 1,600,000`
- The original full-run `PnP` attempt on `2026-04-08` failed at result write time with a `PermissionError` on `pnp/pnp_results.csv`, so that intermediate scoring/summary pass was invalid.
- On `2026-04-09`, the formal `PnP` stage was rerun successfully in the WSL `.conda` environment against the full sampled correspondences, followed immediately by a fresh formal scoring/summary rerun.
- Final full-run `PnP` status:
  - `pnp row_count = 800`
  - `status_counts = {ok: 756, pnp_failed: 44}`
- Final formal scoring/summary status:
  - `scored_query_count = 40`
  - `score_row_count = 800`
  - `best_status_counts = {ok: 40}`
  - `best_ok_rate = 1.0`
- Current active formal outputs now considered valid:
  - `new2output/pose_v1_formal/pnp/pnp_results.csv`
  - `new2output/pose_v1_formal/pnp/pnp_summary.json`
  - `new2output/pose_v1_formal/pnp/pnp_inliers.json`
  - `new2output/pose_v1_formal/scores/pose_scores.csv`
  - `new2output/pose_v1_formal/summary/per_query_best_pose.csv`
  - `new2output/pose_v1_formal/summary/pose_overall_summary.json`
- The superseded pre-rerun `PnP` files have been preserved at:
  - `new2output/pose_v1_formal/pnp_backup_2026-04-09_pre_full40_rerun/`
- Current next step has shifted from “DSM raster preparation” to “expand from the validated 3-query phase gate to the full 40-query formal run”.
## 2026-04-09 Formal Pose v1 UAV Ortho-Truth Evaluation
- The formal accuracy-validation path is now anchored on UAV orthophoto truth instead of the runtime DOM used during pose solving.
- New evaluation scripts added:
  - `scripts/pose_ortho_truth_utils.py`
  - `scripts/build_query_ortho_truth_manifest.py`
  - `scripts/crop_query_ortho_truth_tiles.py`
  - `scripts/render_query_predicted_ortho_from_pose.py`
  - `scripts/evaluate_pose_ortho_alignment.py`
  - `scripts/render_pose_ortho_overlay_viz.py`
  - `scripts/run_pose_ortho_truth_eval_pipeline.py`
- Truth sourcing is now locked as:
  - `query_truth/queries_truth_seed.csv`
  - per-flight `D:\数据\武汉影像\无人机0.1m\<flight_id>\odm_orthophoto\odm_orthophoto.tif`
- The truth-evaluation chain is now:
  - `best pose -> truth ortho manifest -> truth ortho crops -> predicted ortho on truth grid -> quantitative metrics + overlays`
- Gate run completed first with:
  - `query_ids = [q_010, q_015, q_022, q_002, q_039]`
  - `truth crops built = 5`
  - `predicted orthophotos ok = 4`
  - `failure = {dsm_intersection_failed: 1}`
- Full `40-query` orthophoto-truth evaluation has now completed under `new2output/pose_v1_formal/eval_ortho_truth/`.
- Full-run evaluation status:
  - `query_count = 40`
  - `evaluated_query_count = 39`
  - `eval_status_counts = {ok: 39, dsm_intersection_failed: 1}`
  - failed query = `q_022`
- Full-run orthophoto-truth metrics:
  - `phase_corr_error_m mean = 0.2497`
  - `phase_corr_error_m median = 0.2468`
  - `phase_corr_error_m p90 = 0.4389`
  - `center_offset_m mean = 282.02`
  - `ortho_iou mean = 0.3798`
  - `ssim mean = 0.4782`
- Per-flight mean `phase_corr_error_m`:
  - `DJI_202510311347_009_新建面状航线1 = 0.2500`
  - `DJI_202510311413_010_新建面状航线1 = 0.2422`
  - `DJI_202510311435_011_新建面状航线1 = 0.2906`
  - `DJI_202510311500_012_新建面状航线1 = 0.2199`
- Current validation interpretation:
  - truth-grid orthorectification is now closed end-to-end for the formal pose root;
  - `phase_corr_error_m` is currently the most stable quantitative alignment indicator in this chain;
  - `center_offset_m` is retained as an auxiliary footprint-support indicator and should not be used alone to judge final geometric quality;
  - DOM overlays remain diagnostic only and are not the primary accuracy conclusion.
- A dedicated Word interpretation report has now been generated for `per_query_ortho_accuracy.csv`:
  - `scripts/generate_pose_ortho_accuracy_word_report.py`
  - `new2output/pose_v1_formal/eval_ortho_truth/reports/pose_ortho_accuracy_report.docx`
- Current next step has shifted from pipeline implementation to result analysis:
  - inspect `q_022` DSM-intersection failure;
  - analyze the relationship between `best_score / inlier_count / reproj_error` and orthophoto-truth metrics;
  - decide the final reporting metric set for the formal pose conclusion.
## 2026-04-09 Formal Pose v1 Ortho Tie-Point Ground Error Evaluation
- A new local-geometry evaluation branch has been added on top of the existing `eval_ortho_truth` chain.
- New scripts added:
  - `scripts/evaluate_pose_ortho_tiepoint_ground_error.py`
  - `scripts/render_pose_ortho_tiepoint_viz.py`
- The new tie-point metric branch is locked to:
  - `truth_tiles` vs `pred_tiles` only
  - `common_valid_mask = truth_valid & pred_valid`
  - shared orthophoto geotransform for pixel-to-ground XY conversion
  - planar `XY` ground error only; `Z` is not part of the formal metric
- New outputs now considered valid under `new2output/pose_v1_formal/eval_ortho_truth/`:
  - `per_query_tiepoint_ground_error.csv`
  - `overall_tiepoint_ground_error.json`
  - `per_flight_tiepoint_ground_error.csv`
  - `tiepoint_failure_buckets.csv`
  - `tiepoints/per_query_matches/*.csv`
  - `viz_tiepoints/_summary.json`
  - `viz_tiepoints/*.png`
- Full-run tie-point status:
  - `query_count = 40`
  - `evaluated_query_count = 39`
  - `matchable_query_count = 39`
  - `eval_status_counts = {tiepoint_eval_ok: 39, upstream_eval_failed: 1}`
  - only failed query remains `q_022`, preserved as upstream failure from `dsm_intersection_failed`
- Full-run tie-point metrics:
  - `tiepoint_xy_error_mean_m = 3.9425`
  - `tiepoint_xy_error_median_m = 2.9209`
  - `tiepoint_xy_error_rmse_m = 5.7002`
  - `tiepoint_xy_error_p90_m = 13.7098`
  - `tiepoint_match_count_mean = 1070.23`
  - `tiepoint_inlier_ratio_mean = 0.5526`
- Current interpretation:
  - `phase_corr_error_m` remains the global alignment indicator
  - `tiepoint_xy_error_*` now provides the formal local pointwise ground-geometry check
  - the orthophoto-truth evaluation root now contains both global and local geometry metrics for the same `best pose` outputs
## 2026-04-09 Formal Pose v1 Unified Validation Suite
- A new unified three-layer validation suite has been added under:
  - `new2output/pose_v1_formal/eval_pose_validation_suite/`
- New orchestration and summary entrypoints:
  - `scripts/run_pose_validation_suite.py`
  - `scripts/summarize_pose_validation_suite.py`
- New reference-pose evaluation entrypoints:
  - `scripts/build_query_reference_pose_manifest.py`
  - `scripts/evaluate_pose_against_reference_pose.py`
- Existing orthophoto-truth and tie-point scripts have been parameterized with configurable output roots so they can run under the new suite root without overwriting the historical `eval_ortho_truth/` outputs.
- The unified suite is now structured as:
  - `ortho_alignment/`
  - `pose_vs_at/`
  - `tiepoint_ground_error/`
  - `reports/`
- A new `5-query gate` has completed successfully under the suite root with:
  - `query_ids = [q_010, q_015, q_022, q_002, q_039]`
  - all step return codes = `0`
  - `suite phase summary = new2output/pose_v1_formal/eval_pose_validation_suite/phase_gate_summary.json`
- Gate layer-1 status:
  - `query_count = 5`
  - `evaluated_query_count = 4`
  - `eval_status_counts = {ok: 4, dsm_intersection_failed: 1}`
  - `phase_corr_error_m mean = 0.2739`
  - `phase_corr_error_m p90 = 0.3864`
- Gate layer-2 status:
  - `query_count = 5`
  - `evaluated_query_count = 5`
  - `eval_status_counts = {ok: 5}`
  - `horizontal_error_m mean = 277.83`
  - `horizontal_error_m median = 5.18`
  - `view_dir_angle_error_deg mean = 11.26`
  - `view_dir_angle_error_deg median = 0.65`
- Gate layer-3 status:
  - `query_count = 5`
  - `evaluated_query_count = 4`
  - `matchable_query_count = 4`
  - `eval_status_counts = {tiepoint_eval_ok: 4, upstream_eval_failed: 1}`
  - `tiepoint_xy_error_rmse_m = 3.8514`
  - `tiepoint_xy_error_p90_m = 4.6114`
- Current interpretation:
  - the new unified suite is now closed end-to-end for gate execution;
  - layer-1 remains the primary truth-orthophoto validation;
  - layer-2 now adds relative `best pose vs AT` parameter deltas;
  - layer-3 now adds local tie-point ground XY error in the same suite root;
  - layer-2 reference poses are now formally locked to `odm_report/shots.geojson` first, with `queries_truth_seed.csv` fallback only when ODM is missing or incomplete.

## 2026-04-09 Formal Pose v1 Unified Validation Suite Full-40
- The unified three-layer validation suite has now completed for the full `40` query formal set under:
  - `new2output/pose_v1_formal/eval_pose_validation_suite/`
- The suite root now contains valid full-run outputs:
  - `ortho_alignment/`
  - `pose_vs_at/`
  - `tiepoint_ground_error/`
  - `reports/validation_suite_summary.md`
  - `reports/formal_pose_v1_validation_suite_report.docx`
  - `validation_manifest.json`
  - `full_run_summary.json`
- A dedicated Word report generator has now been added:
  - `scripts/generate_pose_validation_suite_word_report.py`
- The current formal Word report has now been generated at:
  - `new2output/pose_v1_formal/eval_pose_validation_suite/reports/formal_pose_v1_validation_suite_report.docx`
- Layer-2 core metric visualizations have now been generated without modifying the existing layer-2 CSV/JSON outputs:
  - script: `scripts/render_pose_vs_at_figures.py`
  - output directory: `new2output/pose_v1_formal/eval_pose_validation_suite/pose_vs_at/figures/`
  - outputs: 8 PNG figures, `README.md`, and `figure_manifest.json`
  - the figures cover position-error distribution, orientation-error distribution, per-query horizontal error, per-query view-direction error, per-flight comparison, `dx_m/dy_m` offset direction, position-vs-orientation coupling, and reference-source/status counts.
- Layer-1 full-run status:
  - `query_count = 40`
  - `evaluated_query_count = 39`
  - `eval_status_counts = {ok: 39, dsm_intersection_failed: 1}`
  - failed query remains `q_022`
  - `phase_corr_error_m mean = 0.2497`
  - `phase_corr_error_m median = 0.2468`
  - `phase_corr_error_m p90 = 0.4389`
- Layer-2 full-run status:
  - `query_count = 40`
  - `evaluated_query_count = 40`
  - `eval_status_counts = {ok: 40}`
  - `reference_source_type_counts = {odm_report_shots_geojson: 40}`
  - `horizontal_error_m mean = 40.6718`
  - `horizontal_error_m median = 4.6051`
  - `horizontal_error_m p90 = 16.5854`
  - `view_dir_angle_error_deg mean = 2.0945`
  - `view_dir_angle_error_deg median = 0.5647`
  - `view_dir_angle_error_deg p90 = 1.8028`
- Layer-3 full-run status:
  - `query_count = 40`
  - `evaluated_query_count = 39`
  - `matchable_query_count = 39`
  - `eval_status_counts = {tiepoint_eval_ok: 39, upstream_eval_failed: 1}`
  - failed query remains `q_022`
  - `tiepoint_xy_error_mean_m = 3.9392`
  - `tiepoint_xy_error_median_m = 2.7994`
  - `tiepoint_xy_error_rmse_m = 5.4663`
  - `tiepoint_xy_error_p90_m = 8.2290`
- Current interpretation:
  - the unified suite is now closed end-to-end for both gate and full-40 execution;
  - layer-1 remains the primary validation conclusion;
  - layer-2 is now an audited relative-AT/ODM pose comparison branch, not an absolute-truth branch;
  - layer-3 provides the formal local ground-geometry cross-check on `pred ortho vs truth ortho`;
  - current next step should shift from pipeline execution to analysis of `q_022`, layer consistency, and final reporting.

## 2026-04-10 Formal Pose v1 Layer-2 Visualization Snapshot
- Current saved state:
  - the second validation layer `pose_vs_at` now has a dedicated visualization script and output directory;
  - the existing layer-2 formal CSV/JSON metrics were not modified;
  - visualization outputs are derived from the current full-40 `pose_vs_at` results.
- Script:
  - `scripts/render_pose_vs_at_figures.py`
- Output directory:
  - `new2output/pose_v1_formal/eval_pose_validation_suite/pose_vs_at/figures/`
- Generated files:
  - 8 PNG figures;
  - `README.md`;
  - `figure_manifest.json`.
- Verification snapshot:
  - `figure_count = 8`
  - `query_count = 40`
  - `evaluated_query_count = 40`
  - `reference_source_type_counts = {odm_report_shots_geojson: 40}`
  - highlighted outlier: `q_022`
  - `q_022 horizontal_error_m = 1357.953818`
  - `q_022 view_dir_angle_error_deg = 53.405885`
- Figure coverage:
  - position-error distribution;
  - orientation-error distribution;
  - per-query horizontal error;
  - per-query view-direction error;
  - per-flight pose error comparison;
  - `dx_m` vs `dy_m` offset direction;
  - `horizontal_error_m` vs `view_dir_angle_error_deg`;
  - reference-source and eval-status counts.
- Current interpretation:
  - layer-2 is best read as a relative `best pose vs ODM/AT reference pose` diagnostic;
  - `q_022` is the dominant layer-2 outlier and should remain the first target for abnormal-case analysis;
  - figure 8 confirms the current formal full-40 layer-2 reference source is fully auditable as `odm_report_shots_geojson = 40`.

## 2026-04-10 009/010 Nadir DINOv2 + RoMa v2 + DOM/DSM/PnP Experiment
- New isolated experiment root:
  - `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/`
- Scope is locked to two near-nadir UAV routes:
  - `DJI_202510311347_009_新建面状航线1`
  - `DJI_202510311413_010_新建面状航线1`
- Query selection completed with:
  - `query_count = 40`
  - `009 count = 20`
  - `010 count = 20`
  - all selected rows satisfy `gimbal_pitch_degree <= -85.0`
- DINOv2 + RoMa v2 retrieval chain completed:
  - DINOv2 coarse Top-20 rows: `800`
  - RoMa rerank rows: `400 + 400 = 800`
  - exported pose retrieval rows: `800`
  - pose candidate `score` is copied from RoMa rerank `fused_score`
- Formal pose chain completed under the isolated root:
  - `matches/roma_matches.csv`: `1,600,000` rows
  - `correspondences/pose_correspondences.csv`: `1,600,000` rows
  - `sampling/sampled_correspondences.csv`: `1,600,000` rows
  - `pnp/pnp_results.csv`: `800` rows
  - `scores/pose_scores.csv`: `800` rows
  - `summary/per_query_best_pose.csv`: `40` rows
- Formal pose status:
  - `PnP status_counts = {ok: 734, pnp_failed: 66}`
  - `best_status_counts = {ok: 40}`
  - `best_ok_rate = 1.0`
- Unified validation suite completed under:
  - `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/pose_v1_formal/eval_pose_validation_suite/`
- Validation status:
  - layer-1 ortho alignment: `query_count = 40`, `evaluated_query_count = 40`, `eval_status_counts = {ok: 40}`
  - layer-2 pose-vs-AT: `query_count = 40`, `evaluated_query_count = 40`, `eval_status_counts = {ok: 40}`
  - layer-3 tiepoint ground error: `query_count = 40`, `evaluated_query_count = 40`, `eval_status_counts = {tiepoint_eval_ok: 40}`
- Validation metric snapshot:
  - layer-1 `phase_corr_error_m mean = 0.7672`, `median = 0.4317`, `p90 = 2.0462`
  - layer-1 `center_offset_m mean = 13.1874`, `median = 8.1716`, `p90 = 28.3168`
  - layer-2 `horizontal_error_m mean = 9.1654`, `median = 7.6759`, `p90 = 16.2847`
  - layer-2 `view_dir_angle_error_deg mean = 1.2706`, `median = 1.0893`, `p90 = 2.3670`
  - layer-3 `tiepoint_xy_error_mean_m = 2.4473`, `median = 2.0942`, `rmse = 2.8552`, `p90 = 4.3476`
- Report and figure outputs:
  - `pose_v1_formal/eval_pose_validation_suite/reports/formal_pose_v1_validation_suite_report.docx`
  - `pose_v1_formal/eval_pose_validation_suite/reports/pose_localization_accuracy_report.docx`
  - `pose_v1_formal/eval_pose_validation_suite/reports/nadir_009010_pose_experiment_detailed_report.md`
  - `pose_v1_formal/eval_pose_validation_suite/pose_vs_at/figures/`
  - figure output contains 8 PNG files, `README.md`, and `figure_manifest.json`
- A dedicated localization-accuracy report generator now exists at:
  - `scripts/generate_pose_localization_accuracy_word_report.py`
- The localization-accuracy report is generated from the current `009/010` suite outputs and uses the current dynamic layer-2 highlighted query from `pose_vs_at/figures/figure_manifest.json`.
- Path isolation status:
  - runtime outputs for this experiment were written under the isolated `nadir_009010_dinov2_romav2_pose_2026-04-10` root
  - the older `new2output/pose_v1_formal/` root was not used as this experiment's output root
- Implementation note:
  - `scripts/build_formal_candidate_manifest.py` now treats missing `is_intersection_truth` in new coverage truth tiles as a broad coverage-truth hit for rows present in `query_truth_tiles.csv`; `is_strict_truth` remains read from the explicit column.

## 2026-04-16 Satellite Truth Subchain Scaffold
- A minimal runnable satellite-truth subchain has been added for the isolated new3output experiment root:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\`
- The new subchain is intentionally separate from the existing UAV orthophoto-truth main suite and does not modify the ODM truth / DSM main-chain scripts.
- New scripts added for the satellite-truth path:
  - `scripts/satellite_truth_utils.py`
  - `scripts/build_query_satellite_truth_manifest.py`
  - `scripts/crop_query_satellite_truth_patches.py`
  - `scripts/evaluate_pose_satellite_alignment.py`
  - `scripts/evaluate_pose_satellite_geometry.py`
  - `scripts/evaluate_pose_satellite_tiepoint_ground_error.py`
  - `scripts/run_pose_validation_suite_satellite_truth.py`
  - `scripts/generate_pose_validation_suite_satellite_truth_word_report.py`
  - `scripts/generate_pose_localization_accuracy_satellite_truth_report.py`
- Satellite truth definition in this subchain is constrained to:
  - choose a canonical satellite source tile from the refined truth coverage assets as a source anchor only;
  - crop the final truth patch from the source GeoTIFF under the satellite-truth suite root;
  - never use a fixed tile directly as the final truth;
  - never use top-k stitching as the final truth.
- The new suite root is reserved for outputs under:
  - `pose_v1_formal/eval_pose_validation_suite_satellite_truth/`
- This subchain has been scaffolded and compiled, but it has not yet been promoted into a completed experimental result in the progress log.

## 2026-04-16 ODM Truth + ODM DSM Orchestrator Scaffold
- The new3output experiment now has a dedicated orchestrator script:
  - `scripts/run_nadir_009010_odmrefresh_and_sattruth_experiment.py`
- The orchestrator keeps the runtime task fixed as UAV-to-satellite localization while isolating two new result branches:
  - `pose_v1_formal/eval_pose_validation_suite_odm_truth/`
  - `pose_v1_formal/eval_pose_validation_suite_satellite_truth/`
- The ODM-refresh branch is wired to:
  - reuse the completed 009/010 retrieval assets from `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/`
  - rebuild truth orthophoto crops from an explicit flight-level ODM asset override manifest
  - rebuild candidate DSM rasters from ODM DSM override assets instead of SRTM
  - rerun formal pose, scoring, best-pose summaries, and the unified three-layer suite under the new3output root
- The satellite-truth branch is now wired into the same orchestrator and can run on the refreshed best-pose outputs without changing runtime candidate selection.
- New helper/report scripts added for this branch:
  - `scripts/build_odm_asset_override_manifest.py`
  - `scripts/materialize_formal_dsm_rasters_from_odm.py`
  - `scripts/generate_odm_truth_vs_satellite_truth_comparison_report.py`
- `scripts/run_pose_validation_suite.py` now accepts `--flight-asset-manifest` so the orthophoto-truth suite can explicitly use override ODM orthophoto assets instead of silently falling back to legacy flight roots.
- This is still scaffold status only:
  - the code path is now connected end-to-end
  - no completed new3output full experimental result has been recorded yet in the progress log

## 2026-04-16 New3output Integrated Report Completion
- A dedicated integrated report generator has been added:
  - `scripts/generate_new3_full_experiment_report.py`
- This generator reads the completed new3output experiment assets and produces:
  - `new3output/nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16/reports/nadir_009010_odmrefresh_sattruth_full_experiment_report.docx`
  - `new3output/nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16/reports/full_experiment_report_assets/`
- The integrated report is now the top-level summary for the completed new3output branch and includes:
  - end-to-end experiment flow
  - runtime / ODM-truth / satellite-truth quantitative summaries
  - baseline-vs-new3 comparison figures
  - per-query truth/pred/mask/overlay sample panels
  - an explicit explanation of why predicted orthophotos show partial coverage rather than full orthophoto fill
- The missing-area explanation is now documented as a formal conclusion:
  - predicted ortho tiles are valid projected coverage on the truth grid
  - they are not complete orthophoto reconstructions
  - no flat-ground fallback is used when DSM support or projection support is absent

## 2026-04-16 New3output Process Report Completion
- A second report generator has been added for a process-first document:
  - `scripts/generate_new3_process_report.py`
- This generator produced:
  - `new3output/nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16/reports/nadir_009010_odmrefresh_sattruth_experiment_process_report.docx`
  - `new3output/nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16/reports/process_report_assets/`
- The new document keeps the existing full report unchanged and adds a second top-level artifact whose main structure is:
  - experiment objective
  - data/query scope
  - input-asset replacement relationships
  - end-to-end execution flow
  - stage outputs and gates
  - compact result summary
  - predicted-ortho partial-coverage explanation
- This closes the reporting split for the completed new3output branch:
  - one report is result/figure heavy
  - one report is process/content heavy

## 2026-04-16 New3output Experiment Completion Record
- The isolated new3output branch is now recorded as a completed experiment under:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16\`
- Runtime scope remained fixed to the 009/010 nadir query set:
  - route `009`: `20` selected queries
  - route `010`: `20` selected queries
  - retrieval / RoMa rerank / runtime satellite candidate DOM library were reused from the completed `new2output` baseline branch
- The main branch-level variable changes were:
  - truth orthophoto source switched to the explicit ODM orthophoto override branch
  - PnP DSM source switched from `SRTM HGT` to `ODM DSM / odm_georeferenced_model.laz` rasterization
  - an additional satellite-truth validation suite was run in parallel on the same best-pose outputs
- Formal pose chain completed under the new3output root:
  - `query_count = 40`
  - `score_row_count = 800`
  - `best_status_counts = {ok: 40}`
  - `score_status_counts = {ok: 520, dsm_nodata_too_high: 217, pnp_failed: 61, dsm_coverage_insufficient: 2}`
- ODM-truth suite completed under:
  - `new3output/nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16/pose_v1_formal/eval_pose_validation_suite_odm_truth/`
- ODM-truth metric snapshot:
  - layer-1 `phase_corr_error_m mean = 0.2788`, `ortho_iou mean = 0.6519`, `ssim mean = 0.5955`
  - layer-2 `horizontal_error_m mean = 6.6689`, `view_dir_angle_error_deg mean = 0.8336`
  - layer-3 `tiepoint_xy_error_rmse_m = 2.3427`, `p90 = 3.2604`
- Satellite-truth suite completed under:
  - `new3output/nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16/pose_v1_formal/eval_pose_validation_suite_satellite_truth/`
- Satellite-truth metric snapshot:
  - layer-1 `phase_corr_error_m mean = 0.0838`, `ortho_iou mean = 0.6935`, `ssim mean = 0.4226`
  - layer-3 `tiepoint_xy_error_rmse_m = 181.3715`, `p90 = 320.9374`
  - `status_counts = {too_few_tiepoints: 8, tiepoint_eval_ok: 32}`
- Cross-branch comparison summary:
  - baseline `new2output` PnP status counts: `{ok: 734, pnp_failed: 66}`
  - current `new3output` PnP status counts: `{ok: 520, dsm_nodata_too_high: 217, pnp_failed: 61, dsm_coverage_insufficient: 2}`
  - ODM-truth layer-3 tiepoint RMSE improved relative to the baseline (`2.3427` vs `2.8552`)
  - satellite-truth remained an independent cross-check branch and did not replace the runtime task definition
- The predicted-ortho partial-coverage issue is now treated as a documented interpretation constraint, not a file-corruption issue:
  - the rendered prediction is valid projected coverage on the truth grid
  - it is not a complete orthophoto reconstruction
  - no flat-ground fallback is used where DSM support or valid back-projection is absent
- Top-level reporting outputs for this completed branch now include:
  - `reports/odm_truth_vs_satellite_truth_comparison.md`
  - `reports/odm_truth_vs_satellite_truth_comparison.docx`
  - `reports/nadir_009010_odmrefresh_sattruth_full_experiment_report.docx`
  - `reports/nadir_009010_odmrefresh_sattruth_experiment_process_report.docx`

## 2026-04-16 Predicted-Ortho Hole Diagnosis Pass
- A dedicated diagnosis script has been added for the completed new3output branch:
  - `scripts/diagnose_predicted_ortho_holes.py`
- The diagnosis pass uses the existing rendered predicted orthophotos, the candidate-linked DSM rasters, the ODM-truth orthophoto suite metrics, and the satellite-truth crop manifests to separate hole causes into:
  - `dsm_limited`
  - `pose_limited`
  - `truth_grid_too_large`
  - `mixed_dsm_and_pose`
  - `unclear_manual_review`
- Current output root:
  - `new3output/nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16/reports/predicted_ortho_hole_diagnosis/`
- Current output set:
  - `all_queries_hole_diagnosis.csv`
  - `all_queries_hole_diagnosis.json`
  - `q_003_diagnosis.json`
  - `figures/`
- q_003 diagnosis snapshot:
  - `best_candidate_id = s700_x253883.067_y3364778.442`
  - `pred_valid_ratio = 0.544946`
  - `dsm_valid_ratio_on_pred_grid = 0.808826`
  - `iou_alpha_vs_dsm_valid = 0.673750`
  - `alpha_outside_dsm_valid_ratio = 0.000000`
  - `truth_to_footprint_area_ratio = 3.834906`
  - `pose_is_geometrically_plausible = true`
  - `diagnosis_primary = mixed_dsm_and_pose`
- Current full-branch diagnosis counts:
  - `mixed_dsm_and_pose = 21`
  - `truth_grid_too_large = 19`
- Current interpretation:
  - the q_003 holes are not consistent with a pure DSM-nodata explanation
  - DSM validity constrains the result, but the oversized truth grid is also a strong factor
  - no query was classified as purely `dsm_limited` by the current threshold rule

## 2026-04-16 Satellite Truth + SRTM + RoMa-Tiepoint Gate
- A second isolated `new3output` route has now been implemented under:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16\`
- This branch keeps the runtime task definition fixed to the existing 009/010 nadir query experiment and changes only two formal validation variables:
  - truth orthophoto source switches from UAV/ODM orthophoto to cropped satellite truth patches
  - layer-3 tie-point matching switches from the older sparse matcher path to `RoMa v2`
- The runtime DSM path is explicitly reverted to `SRTM HGT`:
  - upstream source remains `new2output\N30E114.hgt`
  - branch-local candidate rasters are materialized under `pose_v1_formal\dsm_cache\rasters\`
  - gate-stage DSM materialization completed with `planned_count = built_count = 195`
- New branch-level scripts now in use:
  - `scripts/run_nadir_009010_sattruth_srtm_romatie_experiment.py`
  - `scripts/run_pose_validation_suite_sattruth_srtm.py`
  - `scripts/evaluate_pose_satellite_tiepoint_ground_error_romav2.py`
  - `scripts/generate_sattruth_srtm_romatie_vs_baseline_report.py`
- Current recorded status is a completed `5-query gate`, not a full `40-query` formal run:
  - pose gate query ids: `q_001`, `q_021`, `q_002`, `q_003`, `q_004`
  - validation gate query ids: `q_003`, `q_001`, `q_002`, `q_004`, `q_021`
  - formal pose gate summary is available under `pose_v1_formal\summary\phase_gate_summary.json`
  - validation gate summary is available under `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\phase_gate_summary.json`
- Gate-stage pose chain results:
  - `match row_count = 200000`
  - `sampling row_count = 200000`
  - `pnp row_count = 100`
  - `pnp status_counts = {ok: 95, pnp_failed: 5}`
  - sampled queries all produced `best_status = ok`
- Gate-stage satellite-truth validation snapshot:
  - layer-1 `phase_corr_error_m mean = 0.1665`, `ortho_iou mean = 0.7938`, `ssim mean = 0.4319`
  - layer-2 `horizontal_error_m mean = 3.2834`, `view_dir_angle_error_deg mean = 0.3722`
  - layer-3 `tiepoint_xy_error_rmse_m = 1.4130`, `p90 = 2.1936`
  - layer-3 `status_counts = {tiepoint_eval_ok: 5}`
  - layer-3 `tiepoint_match_count_mean = 4883.0`, `tiepoint_inlier_ratio_mean = 0.8787`
- This gate verifies the intended route change:
  - validation truth is satellite imagery rather than UAV/ODM orthophoto
  - `pose_vs_at` remains the layer-2 geometry reference
  - `RoMa v2` materially increases tie-point support relative to the earlier low-match satellite branch
- Remaining next step for this route:
  - run the same branch in full `40-query` mode and record the formal full-run metrics separately from this gate-only checkpoint

## 2026-04-17 Satellite Truth + SRTM + RoMa-Tiepoint Full Run
- The `40-query full` pass for the same branch has now completed under:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16\`
- Formal pose full-run summary:
  - `query_count = 40`
  - `score_row_count = 800`
  - `best_status_counts = {ok: 40}`
  - `score_status_counts = {ok: 730, pnp_failed: 70}`
  - `best_ok_rate = 1.0`
- The runtime task definition remains unchanged relative to the baseline:
  - retrieval / rerank / fixed satellite candidate DOM library were reused
  - DSM remained `SRTM`
  - only the offline validation truth source and layer-3 matcher were changed
- Full validation suite completed successfully with `pipeline_status = ok` under:
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\full_run_summary.json`
- Full-run metric snapshot:
  - layer-1 `phase_corr_error_m mean = 0.1919`, `ortho_iou mean = 0.7738`, `ssim mean = 0.4250`
  - layer-2 `horizontal_error_m mean = 9.7230`, `view_dir_angle_error_deg mean = 1.3471`
  - layer-3 `tiepoint_xy_error_rmse_m = 2.7718`, `p90 = 4.4149`
  - layer-3 `status_counts = {tiepoint_eval_ok: 40}`
  - layer-3 `tiepoint_match_count_mean = 4879.225`, `tiepoint_inlier_ratio_mean = 0.8581`
- Relative to the completed `new2output` baseline branch:
  - runtime `best_status_counts` stayed unchanged at `{ok: 40}`
  - runtime PnP candidate status remained close to baseline (`ok: 730` vs baseline `734`)
  - layer-1 alignment improved strongly (`phase_corr_error_m mean 0.1919` vs baseline `0.7672`)
  - layer-3 tie-point RMSE improved slightly (`2.7718` vs baseline `2.8552`)
  - layer-3 tie-point support increased sharply (`tiepoint_match_count median 4890.0` vs baseline `1373.5`)
- Low-match baseline queries now receive much denser RoMa support in the new route:
  - representative gains include `q_040: 698 -> 4901`, `q_031: 784 -> 4889`, `q_038: 796 -> 4805`, `q_034: 855 -> 4734`
- Final branch reporting outputs now include:
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\reports\formal_pose_v1_validation_suite_sattruth_srtm_report.docx`
  - `pose_v1_formal\eval_pose_validation_suite_sattruth_srtm\reports\pose_localization_accuracy_sattruth_srtm_romatie_report.docx`
  - `reports\sattruth_srtm_romatie_vs_baseline.md`
  - `reports\sattruth_srtm_romatie_vs_baseline.docx`
  - `reports\final_experiment_report_sattruth_srtm_romatie.md`
  - `reports\final_experiment_report_sattruth_srtm_romatie.docx`
  - `reports\final_experiment_report_assets\`
- A standalone final experiment report chain has now been added for this branch:
  - entrypoint: `scripts\generate_final_experiment_report_sattruth_srtm_romatie.py`
  - fixed section order: experiment objective, evaluation methods/metrics, workflow/data preparation, results, conclusion/analysis, future work, key settings, and representative/anomalous cases
  - report-specific assets now include cross-layer comparison charts, runtime status comparison, low-match improvement visualization, pipeline overview, and per-query sample-case panels
- The rewritten final report is now the recommended human-readable summary for this branch:
  - it restates the full experiment in Chinese academic-report form instead of the earlier metric-only summary style
  - chapter 4 is now aligned one-to-one with the evaluation definition in chapter 2 (`runtime`, layer-1, layer-2, layer-3, and low-match review)
  - chapter 5 explicitly records the main gains and limitations: layer-1 and layer-3 improved, layer-2 stayed roughly flat / slightly worse, and lower `ssim` is interpreted as cross-source appearance difference rather than direct geometric failure
  - chapter 8 now includes `2` representative success cases and `2` anomalous cases for direct visual inspection
- Current next step after documentation/report consolidation:
  - use the rewritten final report as the formal branch summary, then move analysis effort to the remaining high-RMSE queries such as `q_034` and `q_036`

## 2026-04-17 ODM-Truth-Only 0.1m Re-Run Implementation
- The ODM-refresh orchestrator now supports a report-free ODM-only rerun path for the locked 009/010 runtime experiment:
  - `scripts/run_nadir_009010_odmrefresh_and_sattruth_experiment.py --phase odm_truth_only`
- New execution controls added to this entrypoint:
  - `--target-resolution-m`
  - `--dsm-target-resolution-m`
  - `--skip-reports`
- The new default isolated root for this rerun path is:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_odmtruth_odmdsm_0p1m_2026-04-17\`
- The intended contract for this path is:
  - reuse the completed `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/` retrieval-side assets unchanged
  - keep DOM truth rather than satellite truth
  - replace only the PnP DSM path with ODM DSM / LAZ-derived rasters
  - force both orthophoto-truth alignment and ODM DSM materialization to `0.1 m`
  - suppress suite-local report generation and cross-suite comparison report generation when `--skip-reports` is used
- The orchestrator now records the new contract under:
  - `plan/experiment_contract.json`
  - `plan/run_<phase>_<validation_phase>_summary.json`
- The run summary now includes runtime-cost indicators for the ODM-only path, including:
  - merged DSM raster byte size
  - built DSM raster count
  - locked DSM target resolution
  - ODM-truth suite pipeline status
- This is an implementation-only progress update:
  - no new `0.1 m` ODM-only experiment outputs have been recorded yet
  - the gate/full rerun still needs to be executed under the new root

## 2026-04-17 ODM DSM Gate Resolution Sweep Implementation
- A dedicated sweep runner has now been added for the 009/010 ODM-truth gate:
  - `scripts/run_odm_dsm_gate_resolution_sweep.py`
- This runner keeps:
  - DOM truth fixed at `0.1 m`
  - the 009/010 query set fixed
  - DINOv2 retrieval and RoMa v2 rerank fixed
  - the fixed satellite candidate DOM library fixed
- It sweeps only ODM DSM raster resolution across:
  - `5 m`
  - `3 m`
  - `2 m`
- Each case is executed as an isolated `gate` run under a separate root:
  - `...pose_odmtruth_odmdsm_5m_gate_2026-04-17`
  - `...pose_odmtruth_odmdsm_3m_gate_2026-04-17`
  - `...pose_odmtruth_odmdsm_2m_gate_2026-04-17`
- The sweep writes an aggregate diagnosis summary under:
  - `new3output/odm_dsm_gate_resolution_sweep_2026-04-17/aggregate_summary.json`
  - `new3output/odm_dsm_gate_resolution_sweep_2026-04-17/aggregate_summary.csv`
- Current purpose of this route:
  - determine the highest practical ODM DSM precision that still supports the
    formal `gate` on the available ODM LAZ point clouds
  - replace the earlier single-resolution guesswork with an explicit
    `5 m / 3 m / 2 m` comparison
- Current next step:
  - execute the sweep and inspect whether `2 m`, `3 m`, or only `5 m` avoids
    the all-`dsm_nodata_too_high` failure mode seen in the `0.1 m` rerun

## 2026-04-18 ODM DSM Hi-Res Gate Sweep Extension
- A second high-resolution gate sweep is now being added on top of the
  completed `5 m / 3 m / 2 m` sweep:
  - resolutions: `1.0 m`, `0.5 m`
- This extension keeps the same formal gate contract:
  - DOM truth fixed at `0.1 m`
  - ODM-truth-only gate mode
  - locked 009/010 query set
  - unchanged DINOv2 retrieval and RoMa v2 rerank
- Output organization for this extension is isolated under:
  - aggregate root:
    `new3output/odm_dsm_gate_resolution_sweep_hires_2026-04-18/`
  - per-resolution roots:
    - `...pose_odmtruth_odmdsm_1m_gate_2026-04-18`
    - `...pose_odmtruth_odmdsm_0p5m_gate_2026-04-18`
- Execution order is intentionally serial:
  - run `1.0 m` first
  - then run `0.5 m`
- Current purpose of this extension:
  - determine whether the highest practical supported ODM DSM resolution can be
    tightened from the already-supported `2 m` result to `1.0 m` or `0.5 m`

## 2026-04-18 ODM DSM Gate Sweep Final Result
- The combined `5 m / 3 m / 2 m / 1.0 m / 0.5 m` gate sweeps have now completed.
- Final aggregate conclusions:
  - `new3output/odm_dsm_gate_resolution_sweep_2026-04-17/aggregate_summary.json`
    confirms that `5 m`, `3 m`, and `2 m` are all supported, with the
    first-stage highest supported resolution recorded as `2.0 m`
  - `new3output/odm_dsm_gate_resolution_sweep_hires_2026-04-18/aggregate_summary.json`
    confirms that `1.0 m` and `0.5 m` are both also supported, with the final
    highest supported resolution recorded as `0.5 m`
- Current formal resolution conclusion:
  - highest validated supported ODM DSM resolution under the current formal
    gate is `0.5 m`
  - the more stable practical operating point is still closer to `1.0 m`
- Evidence that `0.5 m` is near the current limit rather than a comfortable
  regime:
  - `0.5 m` still passes `supported = true`, but
    `sampling.nodata_ratio = 0.651005`
  - `0.5 m` score status distribution is much less healthy than `1.0 m`
    (`ok = 35`, `dsm_nodata_too_high = 62`) while `1.0 m` keeps
    (`ok = 60`, `dsm_nodata_too_high = 38`)
  - `0.5 m` layer-1 / layer-2 visual-geometric quality is visibly worse than
    `1.0 m` despite still clearing the formal gate
- Current interpretation:
  - `0.5 m` is the highest validated supported DSM resolution
  - `1.0 m` is the recommended practical DSM choice when a less distorted
    predicted orthophoto is preferred over maximum tested nominal detail

## 2026-04-18 Predicted Orthophoto Interpretation Note
- The current `predicted ortho` products in both gate and full validation are
  not full multi-view orthophoto reconstructions.
- They are generated by:
  - selecting the per-query best pose from the formal pose runtime
  - sampling the candidate-linked DSM on the truth grid
  - reprojecting the single query image onto that grid
- Therefore, `gate` and `full` differ only in query coverage:
  - `gate` renders a deterministic subset
  - `full` renders all selected queries
- This means local visual distortion in roads / buildings should be interpreted
  as a mixture of:
  - DSM shape / void / interpolation limitations
  - pose residual error
  - truth-grid cropping context
  rather than as a failure of a dedicated orthophoto reconstruction stage

## 2026-04-18 Why Lower-Resolution DSM Looks Less Distorted
- Lower-resolution DSM products such as `5 m` often look less warped than
  `1.0 m` or `0.5 m` predicted orthophotos even when they are not more
  geometrically faithful.
- Current working explanation for this project branch:
  - coarser DSMs smooth away high-frequency local height variation, so pose
    error is expressed more as broad displacement than as local shape twisting
  - finer DSMs preserve more roof / facade / road-edge structure, so any pose
    or DSM mismatch is amplified into visible bending or skew
  - higher-resolution ODM DSMs also expose more nodata / unstable support on
    the truth grid, which increases local projection irregularity
- This explains why the historical `SRTM` branch can look visually smoother:
  - that branch keeps a much smoother low-frequency DSM source
  - the smoother surface suppresses local geometric twisting, even if it does
    not necessarily provide a more truthful urban-surface model
## 2026-04-20 CaiWangCun Candidate-DOM + DSM Gate
- A follow-up gate branch has completed under:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_caiwangcun_candidate_domdsm_0p14m_gate_2026-04-20\`
- This branch replaces both formal candidate DOM and DSM with CaiWangCun data for the gate:
  - `50` gate candidate DOM rasters were cropped from `caiwangcun_ortho_0p14m_epsg32650.tif`
  - `99` DSM cache rasters were cropped from `caiwangcun_dsm_0p14m_epsg32650.tif`
  - no ODM LAZ/SRTM fallback was used
- Formal pose sample gate completed:
  - gate query ids: `q_001`, `q_021`, `q_002`, `q_003`, `q_004`
  - `score_status_counts = {ok: 50}`
  - sampling status counts: `{ok: 249900, nodata: 51, unstable_local_height: 49}`
  - best score and match quality improved relative to the previous CaiWangCun-DSM-only branch:
    `best_success_inlier_ratio_mean = 0.860464`, `best_success_reproj_error_mean = 1.9763154`
- CaiWangCun DOM-truth validation completed with `pipeline_status = ok`.
- Validation snapshot:
  - layer-1 evaluated `5/5`; `phase_corr_error_m mean = 0.00752`, `ortho_iou mean = 0.09195`,
    `center_offset_m mean = 515.6682`
  - layer-2 evaluated `5/5`; `horizontal_error_m mean = 648.5305`
  - layer-3 matchable `5/5`, evaluated `4/5`; status counts
    `{tiepoint_eval_ok: 4, too_few_tiepoints: 1}`, `tiepoint_xy_error_rmse_m = 181.8233`
- Current interpretation:
  - replacing candidate DOM with CaiWangCun DOM improves local RoMa/PnP match quality
  - it does not remove the large validation-frame offset or restore normal predicted-ortho alignment
  - the remaining issue is therefore likely a coordinate/reference-frame mismatch between CaiWangCun products and the current query truth / AT validation frame, not simply satellite-DOM vs CaiWangCun-DSM mixing

## 2026-04-20 CaiWangCun DOM/DSM Coverage-Constrained Gate
- A new isolated gate branch has completed under:
  - `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_caiwangcun_domdsm_0p14m_gate_2026-04-20\`
- Runtime scope remained fixed:
  - locked 009/010 formal query manifest from the completed `new2output` branch
  - DINOv2 retrieval and RoMa v2 rerank reused unchanged
  - no ODM LAZ, SRTM, satellite-truth suite, `.docx`, or comparison report was used
- CaiWangCun source assets were mosaicked and reprojected from
  `CGCS2000 / 3-degree Gauss-Kruger CM 114E` to `EPSG:32650`:
  - DOM: `source_mosaic\caiwangcun_ortho_0p14m_epsg32650.tif`
  - DSM: `source_mosaic\caiwangcun_dsm_0p14m_epsg32650.tif`
  - both mosaics have identical bounds, `15950 x 15619` pixels, and about
    `0.1400458 m` pixel size
  - DOM is RGB `uint8`; DSM is single-band `float32` with nodata `-9999`
- Coverage-constrained filtering produced:
  - candidates before/after: `800 -> 484`
  - DSM requests before/after: `195 -> 99`
  - candidate coverage counts: `{fully_covered: 484, partially_covered: 301, outside_caiwangcun: 15}`
  - DSM request coverage counts: `{fully_covered: 99, partially_covered: 90, outside_caiwangcun: 6}`
  - query-center coverage: `39/40`; `q_016` is outside the CaiWangCun mosaic bounds
- DSM cache was built entirely from the CaiWangCun DSM mosaic:
  - `planned_count = 99`
  - `built_count = 99`
  - `failed_count = 0`
- Formal pose sample gate completed for `5` selected queries:
  - gate query ids: `q_001`, `q_021`, `q_002`, `q_003`, `q_004`
  - PnP `score_status_counts = {ok: 50}`
  - `best_status_counts` among the sampled queries: `{ok: 5}`
  - 2D-3D sampling status counts: `{ok: 249869, nodata: 63, unstable_local_height: 68}`
  - sampling nodata ratio is approximately `0.000252`, much lower than the prior ODM DSM gate sweeps
- CaiWangCun DOM-truth validation completed with `pipeline_status = ok` under:
  - `pose_v1_formal\eval_pose_validation_suite_caiwangcun_truth\phase_gate_summary.json`
- Validation snapshot:
  - layer-1 evaluated `5/5`; `phase_corr_error_m mean = 0.00955`, `ortho_iou mean = 0.09201`,
    `center_offset_m mean = 515.3221`
  - layer-2 evaluated `5/5`; `horizontal_error_m mean = 652.1089`
  - layer-3 matchable `5/5`, evaluated `4/5`; status counts
    `{tiepoint_eval_ok: 4, too_few_tiepoints: 1}`, `tiepoint_xy_error_rmse_m = 176.3708`
- Current interpretation:
  - CaiWangCun DSM strongly reduces DSM nodata and removes the gate-level DSM failure mode
  - the very large layer-1/layer-2/layer-3 geometric errors indicate that the
    CaiWangCun DOM/DSM frame is not aligned with the current formal truth/reference
    frame in the same way as the ODM-truth branches
  - this branch should therefore be treated as a DSM-support diagnosis success
    but not as a localization-accuracy improvement until the CaiWangCun DOM
    frame alignment is independently reconciled

## 2026-04-21 CaiWangCun DOM/DSM Full-Replacement Gate Report
- A full-replacement gate branch has completed under:
  - `D:\aiproject\imagematch\new3output\nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20\`
- This branch differs from the two earlier CaiWangCun diagnosis branches:
  - query selection and query features were reused
  - CaiWangCun DOM/DSM mosaics were rebuilt in `EPSG:32650`
  - candidate tile library, candidate DINOv2 features, FAISS index,
    retrieval Top-20, RoMa v2 rerank, formal manifests, DSM cache, pose
    manifest, gate pose outputs, and CaiWangCun DOM-truth validation outputs
    were all rebuilt from CaiWangCun assets
  - no ODM LAZ or SRTM fallback was used
- Gate results:
  - candidate tiles: `149`
  - retrieval Top-20 rows: `800`
  - retrieval `recall@1 = 0.675`, `recall@5 = 0.95`,
    `recall@10 = 0.975`, `recall@20 = 0.975`, `MRR = 0.783571`
  - DSM cache: `planned_count = 119`, `built_count = 119`,
    `failed_count = 0`
  - 2D-3D sampling counts: `{ok: 499786, nodata: 92,
    unstable_local_height: 122}`
  - PnP counts: `{ok: 97, pnp_failed: 3}`
  - best sampled-query pose counts: `{ok: 5}`
- CaiWangCun DOM-truth validation completed with `pipeline_status = ok`:
  - layer-1 evaluated `5/5`; `center_offset_m mean = 4.393887`,
    `ortho_iou mean = 0.746525`
  - layer-2 evaluated `5/5`; `horizontal_error_m mean = 1.8294804`
  - layer-3 evaluated `5/5`; `tiepoint_xy_error_rmse_m = 0.3236196`
  - frame sanity: `{ok_or_manual_review: 5}`,
    `dsm_sample_valid_ratio_on_truth_grid mean = 0.9977259`,
    `pred_valid_pixel_ratio mean = 0.7465249`
- Current interpretation:
  - full replacement restores predicted-ortho alignment from the previous
    `~515 m` / `~648-652 m` offset regime to meter-level errors
  - the earlier tilted predicted orthos and large black-frame appearance were
    caused mainly by mixing old candidate/retrieval/rerank assets with new
    CaiWangCun DOM/DSM assets, not by CaiWangCun DSM nodata itself
  - full run can be planned next, but should keep frame-sanity diagnostics for
    all `40` queries
- A detailed Chinese Word and Markdown report has been generated:
  - `new3output\nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20\reports\caiwangcun_fullreplace_gate_report.docx`
  - `new3output\nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20\reports\caiwangcun_fullreplace_gate_report.md`

## 2026-04-22 CaiWangCun DOM/DSM Full-Replacement Full Run
- The 40-query full run has completed under:
  - `D:\aiproject\imagematch\new3output\nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21\`
- Scope:
  - independent full root; the gate branch was not overwritten
  - query, DINOv2, RoMa v2, PnP, and validation parameters followed the accepted gate口径
  - CaiWangCun DOM/DSM source mosaics, candidate library, features, FAISS,
    retrieval/rerank, formal manifests, DSM cache, pose manifest, validation,
    frame sanity, and report assets are branch-local or copied with path-audit
  - no ODM LAZ, SRTM, or old satellite candidate library fallback was used
- Asset and pose acceptance:
  - candidate tiles: `149`; candidate feature count: `149`; FAISS mapping count: `149`
  - retrieval Top-20 rows: `800`
  - formal inputs: `query_count = 40`, `coarse_pair_count = 800`
  - DSM cache: `planned_count = 119`, `built_count = 119`, `failed_count = 0`
  - full pose: `query_count = 40`, `score_row_count = 800`,
    `best_status_counts = {ok: 40}`
  - PnP candidate counts: `{ok: 781, pnp_failed: 19}`
  - 2D-3D sampling counts: `{ok: 3997663, nodata: 840,
    unstable_local_height: 1497}`
- CaiWangCun DOM-truth validation completed with `pipeline_status = ok`:
  - layer-1 evaluated `39/40`; `q_037` failed orthophoto evaluation with
    `dsm_intersection_failed`
  - layer-1 `center_offset_m mean = 5.657901`, `ortho_iou mean = 0.741115`
  - layer-2 evaluated `40/40`; `horizontal_error_m mean = 22.964179`,
    `median = 1.4296165`, `p90 = 3.652963`
  - the layer-2 mean is dominated by `q_037`
    (`horizontal_error_m = 849.224956`, `view_dir_angle_error_deg = 71.267561`)
  - excluding the `q_037` validation-missing case, frame sanity reports
    `horizontal_error_m mean = 1.778006` across `39` usable queries
  - layer-3 tiepoint evaluation: `tiepoint_eval_ok = 39`,
    `upstream_eval_failed = 1`, `tiepoint_xy_error_rmse_m = 0.413562`
  - frame sanity: `{ok_or_manual_review: 39, missing_inputs: 1}`,
    `dsm_sample_valid_ratio_on_truth_grid mean = 0.998752`,
    `pred_valid_pixel_ratio mean = 0.741114`
- Current interpretation:
  - the complete-replacement route scales from the gate to almost all full-run
    queries and remains in the meter-level alignment regime for the usable set
  - the earlier `~500 m` CaiWangCun offset failure does not reappear
  - `q_037` is the only full-run exception and should be inspected before any
    larger production run; its failure bucket is tied to DSM/truth-grid
    intersection and a very large AT-vs-pose discrepancy, not to a global
    CaiWangCun frame offset
- Reports:
  - `new3output\nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21\reports\caiwangcun_fullreplace_full_report.docx`
  - `new3output\nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21\reports\caiwangcun_fullreplace_full_report.md`

## 2026-04-22 Layer-3 Tiepoint Detail CSV Standardization
- Layer-3 orthophoto-truth tiepoint evaluation now treats per-query tiepoint
  coordinate-difference CSV files as a formal output:
  - directory: `tiepoint_ground_error\tiepoints\per_query_matches\`
  - file pattern: `<query_id>_tiepoints.csv`
  - scope: ratio-test matches retained as RANSAC inliers only
  - fields: `query_id`, `match_index`, `truth_col_px`, `truth_row_px`,
    `pred_col_px`, `pred_row_px`, `truth_x_m`, `truth_y_m`, `pred_x_m`,
    `pred_y_m`, `dx_m`, `dy_m`, `dxy_m`
- Coordinate-difference convention:
  - `dx_m = pred_x_m - truth_x_m`
  - `dy_m = pred_y_m - truth_y_m`
  - `dxy_m = sqrt(dx_m^2 + dy_m^2)`
- The layer-3 summary now records the detail CSV scope, directory, field list,
  generated CSV count, and query IDs that do not have a detail CSV.
- Failure query behavior remains unchanged:
  - no empty or fake tiepoint CSV is created
  - the reason is recorded in `tiepoint_failure_buckets.csv`
- Existing full-run validation audit:
  - full run has `39` per-query detail CSV files
  - `overall_tiepoint_ground_error.json` reports `tiepoint_eval_ok = 39`
  - `q_037` is recorded in `tiepoint_failure_buckets.csv` as
    `upstream_eval_failed`
- Gate and full Word/Markdown report scripts now include the per-query detail
  CSV directory, field list, generated count, and missing-query list.

## 2026-04-24 009/010 Dual-Route Engineering Report
- A formal six-chapter engineering report has been generated for the two
  strongest current 009/010 experiment routes:
  - satellite DOM + SRTM route:
    `D:\aiproject\imagematch\new3output\nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16\`
  - CaiWangCun DOM+DSM full-replacement route:
    `D:\aiproject\imagematch\new3output\nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21\`
- New generator script:
  - `scripts\generate_009010_engineering_word_report.py`
- New report outputs:
  - `D:\aiproject\imagematch\汇总\009010双线路工程汇报_卫星DOM_SRTM_vs_CaiWangCun_DOMDSM.docx`
  - `D:\aiproject\imagematch\汇总\009010双线路工程汇报_卫星DOM_SRTM_vs_CaiWangCun_DOMDSM.md`
- The report follows the requested six chapters:
  - goal
  - scheme introduction
  - data processing flow
  - localization accuracy evaluation methods and metrics
  - experiment results
  - runtime statistics
- Metric source policy:
  - formal JSON/CSV outputs are used as the primary source for reported
    numbers
  - draft Markdown files under `汇总\` are used only as narrative source
    material
- Key comparison recorded in the report:
  - SRTM route: `40/40` best pose, layer-2 horizontal error mean
    `9.723047 m`, layer-3 tiepoint XY RMSE `2.771818 m`
  - CaiWangCun full-replacement route: `40/40` best pose, layer-1
    evaluated `39/40`, frame-sanity usable-set horizontal error mean
    `1.778006 m`, layer-3 tiepoint XY RMSE `0.413562 m`
- Validation performed after report generation:
  - `.docx` and `.md` outputs exist and are non-empty
  - Word document can be parsed as OpenXML
  - the Word document contains the six requested chapter headings plus one
    representative-figure subsection
  - six representative images are embedded
  - the Markdown report contains no first-person `我` / `我们` wording

## 2026-04-24 Engineering Report Runtime-Scope Revision
- The dual-route engineering report has been regenerated with chapter 6
  runtime statistics unified to the "including upstream retrieval/rerank
  assets" scope.
- The report no longer uses the formal pose + validation stage alone as the
  main runtime statistic.
- SRTM route runtime scope now starts from the 2026-04-10 DINOv2 query
  feature / DINOv2 coarse retrieval / RoMa v2 rerank asset generation and then
  adds the 2026-04-16 SRTM formal pose, validation, and report run:
  - main total: approximately `6h47m`
  - conservative log-boundary note: approximately `6h50m21s`
  - formal/full substage retained as `3h40m05s`
- CaiWangCun full-replacement runtime scope now starts from the 2026-04-20
  candidate library / candidate feature / FAISS / DINOv2 retrieval / RoMa v2
  rerank asset generation and then adds the 2026-04-21 full formal pose,
  validation, frame sanity, and report run:
  - main total: approximately `19h18m47s`
  - full formal/full substage retained as `15h18m55s`
- Chapter 6 now includes the shared workstation environment:
  - Windows 10 Home 64-bit
  - WSL2 Linux `6.6.87.2-microsoft-standard-WSL2`
  - Intel Core i5-7500 CPU @ 3.40GHz, 4 cores / 4 threads
  - physical memory about `64GB`, WSL visible memory about `31GiB`
  - NVIDIA GeForce GTX 1080, `8192 MiB` VRAM
  - NVIDIA Driver `581.80`, CUDA Version `13.0`
- Updated report outputs remain:
  - `D:\aiproject\imagematch\汇总\009010双线路工程汇报_卫星DOM_SRTM_vs_CaiWangCun_DOMDSM.docx`
  - `D:\aiproject\imagematch\汇总\009010双线路工程汇报_卫星DOM_SRTM_vs_CaiWangCun_DOMDSM.md`
- Validation after regeneration:
  - generator script passes `py_compile`
  - Word OpenXML can be parsed
  - chapter 6 contains subsections `6.1` through `6.5`
  - six representative images remain embedded
  - Markdown report still contains no first-person `我` / `我们` wording

## 2026-04-24 Engineering Report Chapter 7/8 Extension
- The dual-route engineering report has been regenerated from the same
  generator script and expanded from six chapters to eight chapters.
- Newly added chapters:
  - chapter 7: conclusion and analysis
  - chapter 8: follow-up ideas / next work directions
- Chapter 7 consolidates the engineering conclusion:
  - both routes support end-to-end initial localization from a single
    geo-metadata-free UAV image under the current 009/010 nadir scope
  - CaiWangCun DOM+DSM full replacement is the current best-accuracy route
  - satellite DOM+SRTM remains the lower-cost, stable cross-source baseline
  - `q_037`, cross-source metric interpretation, DSM fidelity, runtime cost,
    and sample-scope limits are recorded as explicit risks
- Chapter 8 records next work directions:
  - `q_037` anomaly review
  - Layer-3 / RoMa / DSM sampling runtime optimization
  - data-asset consistency audit
  - broader generalization experiments
  - standardized engineering outputs for downstream localization consumers
- Updated report outputs remain:
  - `D:\aiproject\imagematch\汇总\009010双线路工程汇报_卫星DOM_SRTM_vs_CaiWangCun_DOMDSM.docx`
  - `D:\aiproject\imagematch\汇总\009010双线路工程汇报_卫星DOM_SRTM_vs_CaiWangCun_DOMDSM.md`

## 2026-04-24 009/010 Dual-Route Online Timing Report
- A dedicated online-localization timing report has been generated:
  - `D:\aiproject\imagematch\汇总\时间统计.md`
- Generator:
  - `scripts\generate_009010_timing_report.py`
- Report scope:
  - satellite DOM + SRTM route, using the 2026-04-10 DINOv2/RoMa upstream
    assets and the 2026-04-16 SRTM formal pose outputs
  - CaiWangCun DOM+DSM full-replacement route, using the 2026-04-20 gate
    upstream assets and the 2026-04-21 full formal pose outputs
- Timing scope:
  - DINOv2 query feature extraction
  - Top-20 retrieval
  - RoMa v2 rerank
  - RoMa v2 pose matches export
  - PnP correspondence preparation
  - DSM sampling
  - PnP pose solving
  - score / best-pose output
- Key audited timing values:
  - SRTM RoMa rerank: `11156.613s`
  - CaiWangCun RoMa rerank: `13617.368s`
  - SRTM pose matches export: `8985.443s`
  - CaiWangCun pose matches export: `9898.979s`
  - SRTM DSM sampling: `3262.850s`
  - CaiWangCun DSM sampling: `9274.061s`
- Main engineering conclusion:
  - RoMa v2 rerank is not reloading the model for every query-candidate
    pair; it loads once per flight subprocess.
  - Each route still contains repeated RoMa computation because rerank output
    does not preserve the point-level matches required by PnP, so the formal
    pose stage runs a second RoMa matches export.
  - The report therefore records both current actual per-query timing and a
    deduplicated estimate that removes the second RoMa matches export.
- Validation:
  - the generator passes Python compilation
  - `时间统计.md` exists and is non-empty
  - key SRTM and CaiWangCun timing values are present
  - the report explicitly marks per-query and per-pair values as batch-average
    estimates where logs do not contain per-sample timing fields
  - the report contains no first-person `我` / `我们` wording
## 2026-04-27 new4 Gate Speed-Optimization Matrix G01 Baseline
- Baseline experiment completed for the CaiWangCun DOM+DSM full-replacement
  gate subset:
  - output root:
    `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G01_baseline_current_pipeline/`
  - gate query IDs: `q_001`, `q_021`, `q_002`, `q_003`, `q_004`
  - runtime environment: Ubuntu/WSL with project `.conda/bin/python`
- This run intentionally keeps the current pipeline unchanged:
  - RoMa rerank point matches are not reused by pose
  - pose still runs the second `export_romav2_matches_batch_for_pose.py`
  - DSM sampling uses the current single-worker point/window sampler
  - no DOM+Z cache, no downsampling, and no SIFTGPU replacement
- Acceptance result:
  - `acceptance_summary.json` reports `accepted = true`
  - best pose: `5/5 ok`
  - retrieval top-20 rows: `100`
  - sampled correspondence rows: `500000`
  - PnP rows: `100`, with status counts `{ok: 98, pnp_failed: 2}`
  - validation pipeline status: `ok`
- Main baseline metrics:
  - RoMa v2 rerank elapsed: `1617.055s`
  - second pose-stage RoMa matches export elapsed: `1412.034s`
  - DSM sampling elapsed: `162.278s`
  - Layer-1 center offset mean: `4.131264m`
  - Layer-2 horizontal error mean: `2.642712m`
  - Layer-3 tiepoint XY RMSE: `0.504878m`
- Implementation notes:
  - added `scripts/run_new4_g01_baseline_current_pipeline.py` to reproduce
    the G01 baseline and emit `timing_summary.json`,
    `accuracy_summary.json`, and `acceptance_summary.json`
  - `build_query_reference_pose_manifest.py` now falls back cleanly to
    `queries_truth_seed.csv` when the raw UAV root is unavailable in WSL
  - `run_nadir_009010_caiwangcun_fullreplace_gate_experiment.py` and
    `run_romav2_rerank_intersection_round.py` were adjusted so the gate rerank
    can be constrained to the 5 query IDs without exporting pose matches from
    the rerank step

## 2026-04-27 new4 Gate Speed-Optimization Matrix G02 Engineering Pipeline
- G02 completed under:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G02_pipeline_engineering_reuse_domz_parallel_sampling/`
- Implemented engineering-only pipeline changes:
  - RoMa rerank exports point-level pose matches.
  - Pose reuses the rerank matches and skips the second RoMa export.
  - DOM+Z correspondence-point cache replaces online DSM raster sampling.
  - DOM+Z sampling is grouped/parallelized and emits detailed timing.
- Main run status:
  - best pose: `5/5 ok`
  - PnP rows: `100`, with `{ok: 98, pnp_failed: 2}`
  - matches/correspondences/sampling rows: `500000`
  - validation pipeline: `ok`
- Timing result:
  - second pose-stage RoMa export removed: `0s`
  - DOM+Z prebuild: `65.298s`
  - DOM+Z online sampling stage: `19.643s`
  - G01 DSM sampling reference: `162.278s`
- Strict acceptance result:
  - `acceptance_summary.json` reports `accepted = false`
  - Layer-3 RMSE delta is within the planned tolerance
  - Layer-2 horizontal error mean delta and sampling status counts do not meet
    strict equivalence, so G02 is useful as an engineering result but not yet a
    precision-equivalent replacement for G01.

## 2026-04-27 new4 Gate Speed-Optimization Matrix G03 SIFTGPU Replacement
- G03 directory and implementation entrypoints were created under:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G03_pipeline_siftgpu_replace_roma/`
- Added SIFTGPU replacement scaffolding:
  - `scripts/check_siftgpu_environment.py`
  - `scripts/rerank_with_siftgpu_intersection.py`
  - `scripts/run_siftgpu_rerank_intersection_round.py`
  - `scripts/run_new4_g03_pipeline_siftgpu_replace_roma.py`
  - `run_nadir_009010_caiwangcun_fullreplace_gate_experiment.py` now accepts
    `--geometry-matcher romav2|siftgpu`.
- Environment recovery:
  - installed OpenGL/GLEW/GLUT/DevIL development dependencies in Ubuntu/WSL.
  - built local SiftGPU under `third_party/SiftGPU`.
  - added `third_party/SiftGPU/src/TestWin/siftgpu_pair_match.cpp`, a thin
    local SiftGPU pair matcher used by the G03 rerank stage.
  - COLMAP GPU SIFT still fails with `Shader not supported by your hardware`,
    so G03 uses the local SiftGPU CLI, not COLMAP.
- Formal G03 completed successfully:
  - `acceptance_summary.json` reports `accepted = true`
  - retrieval Top-20 rows: `100`
  - SIFTGPU point matches / sampled rows: `21218`
  - PnP rows: `100`, with `{ok: 39, pnp_failed: 61}`
  - best pose: `5/5 ok`
  - validation pipeline: `ok`
  - SIFTGPU rerank elapsed: `580.830s`
  - Layer-2 horizontal error mean: `2.053060m`
  - Layer-3 tiepoint XY RMSE: `0.417440m`
- Interpretation:
  - SIFTGPU is much faster than G02 RoMa rerank (`580.830s` vs `1400.535s`)
    and can still recover a valid best pose for all five gate queries.
  - Candidate-level robustness is weaker than RoMa: only `39/100` PnP
    candidates succeed, versus G02's `98/100`.
  - The method is therefore promising for speed, but not yet a full RoMa
    replacement without additional match-density / coverage filtering work.

## 2026-04-28 new4 Gate Speed-Optimization Matrix G04 Downsample Sweep
- G04 was implemented and executed under:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G04_downsample_resolution_sweep/`
- Added resolution-sweep support:
  - `build_caiwangcun_candidate_library.py` now accepts optional
    `--output-gsd-m` and writes candidate DOM tiles at fixed output GSD while
    preserving tile bbox/affine metadata.
  - new `scripts/downsample_query_inputs_for_resolution_sweep.py` creates
    downsampled metadata-free query images and records intrinsics scale factors.
  - `build_formal_query_manifest.py` now applies query-manifest downsample
    overrides to `width/height/fx/fy/cx/cy`.
  - `run_nadir_009010_caiwangcun_fullreplace_gate_experiment.py` now accepts
    `--candidate-output-gsd-m` and `--query-output-gsd-m`; when query
    downsampling is enabled it recomputes query DINOv2 features instead of
    reusing the original-resolution features.
  - new wrapper:
    `scripts/run_new4_g04_downsample_resolution_sweep.py`
- G04A `0.5 m/pix` completed:
  - retrieval Top-20 rows: `100`
  - matches/sampling rows: `500000`
  - PnP status `{ok: 100}`
  - best pose for gate queries: `5/5 ok`
  - validation pipeline: `ok`
  - RoMa rerank elapsed: `3720.388s`
  - DOM+Z sampling elapsed: `21.741s`
  - Layer-2 horizontal error mean: `6.039019m`
  - Layer-3 tiepoint XY RMSE: `441.898506m`
- G04B `1.0 m/pix` was terminated and recorded as failed:
  - failure reason: `romav2_rerank_timeout_or_cpu_fallback`
  - first-flight RoMa rerank ran for more than two hours at high CPU usage,
    with no visible GPU process in `nvidia-smi`
  - stage7 CSV outputs remained 0 bytes, so pose/validation were not run
- Current interpretation:
  - naive external downsampling of query and candidate PNGs is not a useful
    speed optimization for the current RoMa pipeline.
  - `0.5 m/pix` satisfies only the loose gate completion checks but severely
    damages Layer-3 tiepoint accuracy, so it is not an acceptable G02
    replacement.
  - `1.0 m/pix` is operationally unusable in this implementation because RoMa
    rerank did not complete within the gate iteration window.

## 2026-04-28 new4 Gate Speed-Optimization Matrix G05 Top-20 Pruning Posthoc
- G05 was implemented as a posthoc analysis only; no retrieval, matching, PnP,
  DSM sampling, or validation stages were rerun.
- Output root:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G05_top20_pruning_posthoc_analysis/`
- Added script:
  `scripts/analyze_new4_g05_top20_pruning_posthoc.py`
- Inputs:
  - G02 RoMa engineering pipeline outputs
  - G03 SIFTGPU replacement pipeline outputs
- Generated outputs:
  - `candidate_match_distribution_g02.csv`
  - `candidate_match_distribution_g03.csv`
  - `pruning_simulation_per_query.csv`
  - `compare_g02_g03_topk_pruning.csv`
  - `pruning_simulation_summary.json`
  - `pruning_simulation_summary.md`
- Data quality checks passed for the expected five gate queries and 100
  candidate rows per source group.
- Main results:
  - G02 RoMa: `inlier_count_top1/top3/top5` is not sufficient under the strict
    checks. `inlier_count_top5` retains truth hits for `5/5` queries, but only
    retains the final best-pose candidate for `1/5`.
  - G03 SIFTGPU: `inlier_count_top5` passes the strict checks; `top1` and
    `top3` do not. `match_count_top1` also passes for G03, but this is
    SIFTGPU-specific and should not be generalized to RoMa.
  - Coarse raw ranking needs Top-10 in both G02 and G03 to retain truth,
    final best-pose candidate, and at least one PnP-ok candidate for all five
    queries.
- Current interpretation:
  - do not adopt universal Top-1 pruning.
  - do not claim that Top-20 retrieval can be skipped from this analysis alone.
  - if candidate pruning is pursued, G03 can justify a follow-up experiment for
    SIFTGPU `match_count_top1` or `inlier_count_top5`, while G02 RoMa does not
    support inlier-count pruning to Top-5 under final best-pose retention.

## 2026-04-28 new4 Gate Speed-Optimization Matrix G06 Top-1 Pose Validation
- G06 was implemented and executed under:
  `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G06_top1_match_count_pose_reprojection_validation/`
- Added script:
  `scripts/run_new4_g06_top1_match_count_pose_reprojection_validation.py`
- Experiment design:
  - no retrieval, RoMa, SIFTGPU, DSM sampling, or DOM+Z cache stages were
    rerun.
  - each query kept only one candidate selected from existing G02/G03 rerank
    outputs.
  - reduced sampled correspondences were passed through the existing PnP,
    scoring, and CaiWangCun truth validation entrypoints.
- Subgroups:
  - `G06A_g02_roma_inlier_top1`
  - `G06B_g03_siftgpu_inlier_top1`
  - `G06C_g03_siftgpu_match_top1`
- Main result:
  - all three subgroups produced `5/5` PnP `ok` results.
  - all three subgroups produced `5/5` best-pose `ok` summaries.
  - Layer-2 pose-vs-AT outputs were produced for all three subgroups:
    - G06A: horizontal error mean `2.288524m`
    - G06B: horizontal error mean `3.073294m`
    - G06C: horizontal error mean `2.053060m`
  - Layer-3 tiepoint evaluation did not complete under the 600s per-subgroup
    timeout for any subgroup.
  - G06C was retried separately with a 3600s validation limit and still timed
    out during `evaluate_pose_ortho_tiepoint_ground_error`.
- Current interpretation:
  - Top-1 downstream pose solving is technically runnable and can produce PnP
    `ok` for every gate query.
  - G06C SIFTGPU `match_count_top1` exactly preserves the G03 Layer-2 mean in
    this gate, but the Layer-3 validation timeout prevents accepting it as a
    complete replacement.
  - G06 does not prove that geometric rerank can be skipped, because the Top-1
    decision still depends on matched-point counts from the geometry matcher.
  - No Top-1 strategy is accepted as a full replacement until Layer-3 either
    completes or is replaced by a bounded validation proxy for this pruning
    experiment.

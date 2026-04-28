# 实验结果目录索引

这份文档用于快速区分 `output/` 下哪些目录是正式结果，哪些只是历史探索或中间产物。

## 1. 当前正式结果

### 1.1 严格同尺度基线

- 目录：`D:\aiproject\imagematch\output\validation_200m_same_scale`
- 方法：`DINOv2 + FAISS`
- 作用：正式基线

### 1.2 严格同尺度 SIFT 重排

- 目录：`D:\aiproject\imagematch\output\validation_200m_same_scale_sift_gate3`
- 方法：`SIFT + RANSAC` 保守门控重排
- 作用：传统局部几何验证对照

### 1.3 严格同尺度 LightGlue 融合重排

- 目录：`D:\aiproject\imagematch\output\validation_200m_same_scale_lightglue_superpoint_fused_top10_k256`
- 方法：`SuperPoint + LightGlue` 融合重排
- 作用：当前正式最优方案

## 2. 常看文件

对于每个正式结果目录，优先看：

- `aggregate_summary.md`
- `aggregate_summary.json`
- `figures/`
- `stage7/<flight_id>/analysis.md`
- `stage7/<flight_id>/reranked_top10.csv` 或 `retrieval_top10.csv`

## 3. 历史探索目录

以下目录保留，但默认不作为正式主对比入口：

- `validation_round2`
- `validation_round3_200m_fair`
- `validation_round3_200m_fair_geom_sift`
- `validation_round3_200m_fair_geom_sift_round2_gate3`
- `validation_round3_200m_strict`
- `validation_200m_same_scale_lightglue_superpoint_gate3_top5_k64`
- `lightglue_pilot_012_q05_top3`

## 4. 阶段性共享产物

以下目录更偏流程阶段产物：

- `stage1`
- `stage2`
- `stage3`
- `stage4`
- `stage7`

这些目录可能被多个实验复用，但它们本身不一定代表完整的正式实验结论。

## 5. 当前最重要的图与文档入口

- 正式三方法说明文档：
  - `D:\aiproject\imagematch\方案\粗检索 + 局部几何验证重排\严格同尺度三方法对比实验结果解读_2026-03-17.docx`
- LightGlue 融合重排汇总图目录：
  - `D:\aiproject\imagematch\output\validation_200m_same_scale_lightglue_superpoint_fused_top10_k256\figures\_aggregate`


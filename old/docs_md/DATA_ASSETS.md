# 数据资产说明索引

这份文档是当前项目的数据管理入口，用于快速定位“有什么数据、数据在哪里、哪些可以直接复用”。

详细档案型说明仍以 Word 文档为准：

- `D:\aiproject\imagematch\武汉GNSS拒止视觉定位_已处理数据资产说明_2026-03-11.docx`

本 Markdown 主要承担“快速查阅版”和“实验使用版索引”的作用。

## 1. 数据管理原则

- 原始数据、处理中间产物、正式实验产物要区分开
- 正式实验优先引用 `output/` 下已经固化的结果目录
- 数据口径要和正式实验口径一致，避免混用 mixed-scale 历史结果

## 2. 当前项目中最重要的数据/结果位置

### 2.1 正式实验使用的数据与结果

- 严格同尺度基线结果：
  - `D:\aiproject\imagematch\output\validation_200m_same_scale`
- 严格同尺度 SIFT 重排结果：
  - `D:\aiproject\imagematch\output\validation_200m_same_scale_sift_gate3`
- 严格同尺度 LightGlue 融合重排结果：
  - `D:\aiproject\imagematch\output\validation_200m_same_scale_lightglue_superpoint_fused_top10_k256`

### 2.2 共享中间资产

- 卫星瓦片与阶段性输出：
  - `D:\aiproject\imagematch\output\stage1`
  - `D:\aiproject\imagematch\output\stage2`
  - `D:\aiproject\imagematch\output\stage3`
  - `D:\aiproject\imagematch\output\stage4`
  - `D:\aiproject\imagematch\output\stage7`

这些目录更多是流程阶段产物，不一定都代表“正式结论”。

## 3. 当前正式实验直接复用的口径

正式结论只基于以下数据定义：

- query 固定为 200m 无人机瓦片
- satellite 固定为 200m 卫星瓦片
- 图像 resize 到统一输入分辨率
- 真值定义为：query 中心点落入的 200m 卫星瓦片

## 4. 历史探索结果

以下目录是历史探索或过渡结果，不作为当前正式对比主结论：

- `D:\aiproject\imagematch\output\validation_round2`
- `D:\aiproject\imagematch\output\validation_round3_200m_fair`
- `D:\aiproject\imagematch\output\validation_round3_200m_fair_geom_sift`
- `D:\aiproject\imagematch\output\validation_round3_200m_fair_geom_sift_round2_gate3`
- `D:\aiproject\imagematch\output\validation_round3_200m_strict`
- `D:\aiproject\imagematch\output\validation_200m_same_scale_lightglue_superpoint_gate3_top5_k64`
- `D:\aiproject\imagematch\output\lightglue_pilot_012_q05_top3`

这些结果保留用于追溯方法演进过程，但不应与当前严格同尺度正式结论混用。

## 5. 数据说明维护建议

后续更新这份文档时，优先补充：

- 原始数据来源与采集说明
- 各阶段数据命名规则
- 每类数据的用途说明
- 当前可直接复用的数据资产清单
- 失效或已废弃的数据目录说明


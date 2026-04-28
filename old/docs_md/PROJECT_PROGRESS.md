# 项目当前进度

最后更新：2026-03-18

## 1. 当前主任务

当前主任务是论证：

> 基于遥感正射影像，能否实现对无人机影像的初步地理定位（检索）。

当前正式主线已经固定为严格同尺度口径，不再把 mixed-scale 探索结果作为正式结论。

## 2. 当前正式实验口径

- `200m query vs 200m satellite`
- 图像统一 resize 到同一输入分辨率
- 真值定义：query 中心落入的 200m 卫星瓦片
- 正式指标：`Recall@1`、`Recall@5`、`Recall@10`、`MRR`、`Top-1 error mean (m)`

## 3. 当前最优方法

当前正式最优方法是：

- `DINOv2 + FAISS` 粗检索
- `SuperPoint + LightGlue` 融合重排

对应结果目录：

- `D:\aiproject\imagematch\output\validation_200m_same_scale_lightglue_superpoint_fused_top10_k256`

## 4. 当前正式结果摘要

### 4.1 基线：DINOv2 + FAISS

- 目录：`validation_200m_same_scale`
- overall：
  - `Recall@1 = 0.050`
  - `Recall@5 = 0.600`
  - `Recall@10 = 1.000`
  - `MRR = 0.333`
  - `Top-1 error mean ≈ 582.730 m`

### 4.2 SIFT + RANSAC 保守门控

- 目录：`validation_200m_same_scale_sift_gate3`
- overall：
  - `Recall@1 = 0.100`
  - `Recall@5 = 0.600`
  - `Recall@10 = 1.000`
  - `MRR = 0.357`
  - `Top-1 error mean ≈ 571.316 m`

### 4.3 SuperPoint + LightGlue 融合重排

- 目录：`validation_200m_same_scale_lightglue_superpoint_fused_top10_k256`
- overall：
  - `Recall@1 = 0.600`
  - `Recall@5 = 0.800`
  - `Recall@10 = 1.000`
  - `MRR = 0.691`
  - `Top-1 error mean ≈ 426.980 m`

说明：

- 以上 overall 为 4 条航线共 20 个 query 的统一口径结果
- 分航线精确数值请看各目录下的 `aggregate_summary.md/json`

## 5. 当前明确结论

- 仅靠 `DINOv2 + FAISS` 粗检索，在严格同尺度条件下已经可以把无人机图像检索到正确地理区域附近，说明区域级初步定位成立。
- `SIFT + RANSAC` 保守门控重排没有整体稳定优于基线。
- `SuperPoint + LightGlue` 如果采用“全局分数 + 几何分数融合”，则能显著提升前排排序质量，是当前最优正式方案。
- 当前最准确的结论表述是：
  - 遥感正射影像能够支撑无人机影像的区域级初步定位
  - 学习型局部几何重排可进一步提升 Top-1 排序质量

## 6. 当前最重要的文档

- 正式结果说明：
  - `D:\aiproject\imagematch\方案\粗检索 + 局部几何验证重排\严格同尺度三方法对比实验结果解读_2026-03-17.docx`
- 交接说明：
  - `D:\aiproject\imagematch\对话\严格同尺度跨视角定位实验进展与交接说明_2026-03-17.docx`

## 7. 当前最重要的结果目录

- 基线：
  - `D:\aiproject\imagematch\output\validation_200m_same_scale`
- SIFT：
  - `D:\aiproject\imagematch\output\validation_200m_same_scale_sift_gate3`
- LightGlue 融合：
  - `D:\aiproject\imagematch\output\validation_200m_same_scale_lightglue_superpoint_fused_top10_k256`

## 8. 下一步建议

- 如果继续优化，优先在 LightGlue 融合路线基础上做：
  - 融合权重调整
  - 几何质量构造优化
  - 失败样例分析
- 不建议再把 mixed-scale 历史结果与当前正式结果混写
- 如果有新方法要进入正式对比，必须保持当前严格同尺度口径一致

## 9. 更新规则

后续更新本文件时，建议保持以下结构不变：

- 当前主任务
- 正式实验口径
- 当前最优方法
- 当前正式结果摘要
- 当前明确结论
- 下一步建议

这样新智能体进入项目时，只看这一份 Markdown 就能快速理解当前状态。


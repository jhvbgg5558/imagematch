# 正式实验口径说明

这份文档用于固定当前项目的正式实验口径，避免后续方法迭代时混入口径不一致的数据或结论。

## 1. 当前正式任务定义

目标是论证：

> 在跨视角条件下，仅依赖遥感正射影像，能否把无人机影像检索到正确地理区域附近。

这里的“初步地理定位”指区域级检索定位，不等同于高精度位姿估计。

## 2. 正式实验口径

- query：固定为 `200m` 无人机瓦片
- satellite：固定为 `200m` 卫星瓦片
- 输入：统一 resize 到同一网络输入分辨率
- 真值：`query` 中心点落入的 `200m` 卫星瓦片为正样本

## 3. 正式对比指标

- `Recall@1`
- `Recall@5`
- `Recall@10`
- `MRR`
- `Top-1 error mean (m)`

## 4. 正式对比方法

- 基线：`DINOv2 + FAISS`
- 传统重排：`SIFT + RANSAC` 保守门控重排
- 当前最优：`SuperPoint + LightGlue` 融合重排

## 5. 当前正式结果目录

- `D:\aiproject\imagematch\output\validation_200m_same_scale`
- `D:\aiproject\imagematch\output\validation_200m_same_scale_sift_gate3`
- `D:\aiproject\imagematch\output\validation_200m_same_scale_lightglue_superpoint_fused_top10_k256`

## 6. 不纳入当前正式结论的结果

以下结果可作为历史探索参考，但不纳入当前正式主结论：

- mixed-scale 检索结果
- 早期 fair/strict 过渡版本
- LightGlue pilot 小规模试跑结果
- 与当前真值定义不一致的旧结果

## 7. 使用规则

后续新增方法时，如果要进入正式主对比，必须满足：

- 使用同一套 `200m query vs 200m satellite` 数据口径
- 使用同一套真值定义
- 输出同一组正式指标
- 明确和当前三种方法做可比对照


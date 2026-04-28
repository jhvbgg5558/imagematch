# 当前任务修正待办

最后更新：2026-03-23

## 当前优先顺序

1. 数据范围、坐标系、ROI 与预处理说明
2. ROI 外扩与多尺度卫片库统计可视化
3. 新真值定义：query footprint 与卫片 tile 非零面积交集即为真值
4. 基于新真值重评估 DINOv2 baseline
5. 基于新真值生成 Top-K 真值累计曲线
6. LightGlue inlier 连线可视化
7. DINOv2 特征提取 / FAISS 建库 / query 检索时间统计

## 待办清单

- [x] 生成 query 与卫片联合空间总览图
- [x] 生成 ROI 外扩前后对比图与面积统计
- [x] 整理当前预处理流程说明
- [x] 统计各尺度 tile 数、覆盖面积、query footprint 面积
- [x] 实现 intersection truth 生成脚本
- [x] 基于 intersection truth 重评估现有 DINOv2 检索结果
- [x] 生成全量平均 Top-K 真值累计曲线
- [x] 生成按航线平均 Top-K 真值累计曲线
- [x] 生成 LightGlue query-vs-tile inlier 连线图
- [ ] 实现时间统计脚本并确认是否已实际跑完

## 当前说明

- 现有固定卫片库来自 4 条航线整体活动区域的 ROI，再额外外扩固定 buffer。
- 当前正式 strict-truth 结果保留作历史对照；后续主分析切换到 intersection truth。
- 时间统计优先记录：
  - satellite DINOv2 feature extraction
  - FAISS index build
  - query DINOv2 feature extraction
  - query retrieval
- 当前已经生成时间统计脚本与占位输出；但尚未对完整流水线做一次带实测计时的正式执行。

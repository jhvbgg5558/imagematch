# 武汉GNSS拒止视觉定位 200m同尺度Pooling对比实验进度

日期：2026-03-17

## 1. 本轮工作的主要目标

本轮工作的核心任务是：

- 将原先 `DINOv2 + FAISS` 的 pooling 对比实验，从“无人机查询固定 200m、卫星候选为 80m/120m/200m 多尺度”改为“无人机查询 200m、卫星候选也固定 200m”的严格同尺度实验口径。
- 在相同评价指标下，重新对比 `pooler / cls / mean / gem` 四种全局特征聚合方式。
- 生成与现有参考目录风格一致的可视化结果。
- 基于这轮同尺度结果，生成一份偏论文式、技术报告风格的 Word 实验结果说明文档。

## 2. 与上一轮实验的主要差异

上一轮 pooling 对比实验的真实口径是：

- 无人机查询图：`200m-only`
- 卫星候选库：`tiles_80_120_200`，即同时包含 `80m / 120m / 200m`

本轮新口径改为：

- 无人机查询图：继续使用 `validation_round3_200m_fair`，即 `200m-only`
- 卫星候选库：从 `tiles_80_120_200/tiles.csv` 中筛出 `scale_level_m == 200` 的瓦片，仅保留 `200m` 候选

也就是说，本轮实验是严格的：

- `200m query vs 200m satellite tile`

## 3. 本轮修改的关键脚本

本轮主要修改/新增了以下脚本：

- `/mnt/d/aiproject/imagematch/scripts/compare_pooling_variants.py`
- `/mnt/d/aiproject/imagematch/scripts/visualize_pooling_same_scale_results.py`
- `/mnt/d/aiproject/imagematch/scripts/generate_pooling_same_scale_paper_report.py`

### 3.1 compare_pooling_variants.py 的改动

关键新增能力：

- 增加 `--satellite-scale-m` 参数，用于固定卫星候选尺度
- 在运行开始时自动从原始 `tiles.csv` 里筛出 `200m` 瓦片
- 生成过滤后的：
  - `tiles_scale_200_only.csv`
- 为每种 pooling 方法在新结果目录下写出：
  - `stage2`
  - `stage4`
  - `stage7`
  - `timing`
  - `aggregate_summary.json`
  - `aggregate_summary.md`

### 3.2 本轮做过的优化

为了避免重复跑卫星侧 DINO 特征提取，本轮对 `compare_pooling_variants.py` 做了复用优化：

- `pooler`：
  - 复用原始 PoC 的卫星特征：
    - `/mnt/d/aiproject/imagematch/output/stage2/satellite_dinov2_features.npz`
- `cls / mean / gem`：
  - 复用上一轮 pooling 对比目录中已经生成好的卫星特征：
    - `/mnt/d/aiproject/imagematch/方案/CLS token vs mean pooling vs GeM pooling/<method>/stage2/satellite_dinov2_<method>.npz`

然后在复用的基础上：

- 只保留 `200m tile_id`
- 重建新的 `200m` 索引

这样显著加快了本轮同尺度实验。

## 4. 本轮结果目录

### 4.1 同尺度主结果目录

Windows 路径：

- `D:\aiproject\imagematch\方案\CLS token vs mean pooling vs GeM pooling_200m同尺度`

WSL 路径：

- `/mnt/d/aiproject/imagematch/方案/CLS token vs mean pooling vs GeM pooling_200m同尺度`

### 4.2 关键产物

根目录下：

- `overall_metrics.csv`
- `per_flight_metrics.csv`
- `tiles_scale_200_only.csv`

各方法子目录下：

- `pooler\aggregate_summary.json`
- `cls\aggregate_summary.json`
- `mean\aggregate_summary.json`
- `gem\aggregate_summary.json`

## 5. 本轮严格同尺度实验结果

### 5.1 overall 结果

当前 `overall_metrics.csv` 的结果为：

- `pooler`
  - `Recall@1 = 0.05`
  - `Recall@5 = 0.60`
  - `Recall@10 = 1.00`
  - `MRR = 0.3326`
  - `Top-1误差均值 = 582.73 m`
- `cls`
  - `Recall@1 = 0.05`
  - `Recall@5 = 0.60`
  - `Recall@10 = 1.00`
  - `MRR = 0.3326`
  - `Top-1误差均值 = 582.73 m`
- `mean`
  - `Recall@1 = 0.25`
  - `Recall@5 = 0.50`
  - `Recall@10 = 0.85`
  - `MRR = 0.4057`
  - `Top-1误差均值 = 424.17 m`
- `gem`
  - `Recall@1 = 0.25`
  - `Recall@5 = 0.60`
  - `Recall@10 = 0.75`
  - `MRR = 0.3943`
  - `Top-1误差均值 = 526.43 m`

### 5.2 当前可直接得出的结论

与上一轮“多尺度卫星候选库”相比，本轮“严格同尺度 200m”下的结论有明显变化：

- `pooler` 与 `cls` 依旧完全一致，这一点在同尺度条件下再次得到验证。
- 但它们的 `Recall@1` 从上一轮的较高水平显著下降到 `0.05`，说明此前多尺度卫星候选库对前排命中率存在明显缓冲作用。
- `mean` 与 `gem` 在本轮同尺度条件下的 `Recall@1` 提升到 `0.25`，高于 `pooler/cls`。
- 但 `mean` 与 `gem` 并没有在所有指标上全面占优，尤其是：
  - `Recall@10`
  - 部分航线稳定性
  - 困难样本表现
  仍然不够稳定。

更谨慎的表述应为：

- 不同 pooling 在严格同尺度口径下确实会改变首位命中和误差分布；
- 但当前证据不足以证明某一种 pooling 在所有维度上全面优于其他方案。

## 6. 分航线观察到的现象

从各方法 `aggregate_summary.json` 可见：

- `pooler / cls`
  - 在 009 航线上尚能维持一定前排能力
  - 在 010/011/012 航线上 `Recall@1` 已接近或降为 `0`
- `mean`
  - 在 012 航线上反而表现较好
  - 在 011 航线上退化明显
- `gem`
  - 在 012 航线上也出现一定前排改善
  - 但在 011 航线上定位误差很大，且稳定性不足

这说明在同尺度条件下，不同 pooling 更像是在不同类型查询上出现偏好差异，而不是简单的全局优劣关系。

## 7. 本轮可视化结果

### 7.1 可视化脚本

新增脚本：

- `/mnt/d/aiproject/imagematch/scripts/visualize_pooling_same_scale_results.py`

作用：

- 为每种方法、每条航线生成：
  - `metrics_bar.png`
  - `query_selection_scores.png`
  - `q_200m_01_top10.png` 到 `q_200m_05_top10.png`
- 为整体生成 `_aggregate` 汇总图

### 7.2 可视化输出目录

Windows 路径：

- `D:\aiproject\imagematch\方案\CLS token vs mean pooling vs GeM pooling_200m同尺度\figures`

该目录包含：

- `figures\pooler\<flight_id>\...`
- `figures\cls\<flight_id>\...`
- `figures\mean\<flight_id>\...`
- `figures\gem\<flight_id>\...`
- `figures\_aggregate\...`

### 7.3 汇总图文件

`_aggregate` 下已有：

- `multi_flight_recall.png`
- `pooling_same_scale_recall1.png`
- `pooling_same_scale_recall5.png`
- `pooling_same_scale_recall10.png`
- `pooling_same_scale_mrr.png`
- `pooling_same_scale_top1_error.png`
- `pooling_same_scale_feature_ms.png`
- `pooling_same_scale_total_ms.png`

这些图已经生成完成。

## 8. 本轮论文式 Word 报告

### 8.1 新增文档生成脚本

- `/mnt/d/aiproject/imagematch/scripts/generate_pooling_same_scale_paper_report.py`

### 8.2 已生成的 Word 文档

Windows 路径：

- `D:\aiproject\imagematch\方案\CLS token vs mean pooling vs GeM pooling_200m同尺度\DINOv2不同Pooling策略_200m同尺度跨视角粗定位实验结果说明_2026-03-17.docx`

该文档已经按以下结构组织：

- 任务定义
- 实验设置
- 指标定义
- 方法说明
- 定量结果
- 汇总图解读
- 典型案例
- 结论

并且已经插入：

- overall 表格
- 分航线表格
- 汇总图
- 典型检索案例图

### 8.3 文风说明

本轮文档刻意采用了：

- 偏论文式、技术报告式的书写方式
- 正式、克制的结论表述
- 先交代实验口径，再进入表格和图，再给出谨慎结论

不是口语化汇报稿。

## 9. 当前状态总结

截至目前，本轮工作已经完成：

1. 严格同尺度 200m pooling 对比重跑
2. 四种方法的指标统计
3. 参考风格的可视化输出
4. 偏论文式的实验结果 Word 文档生成

也就是说，本轮实验闭环已经完成。

## 10. 下一个智能体接手时最值得做的事

如果下次新开一个智能体，建议优先做以下事情：

1. 先读取本文档，建立当前上下文。
2. 再读取：
   - `D:\aiproject\imagematch\方案\CLS token vs mean pooling vs GeM pooling_200m同尺度\overall_metrics.csv`
   - `D:\aiproject\imagematch\方案\CLS token vs mean pooling vs GeM pooling_200m同尺度\per_flight_metrics.csv`
   - `D:\aiproject\imagematch\方案\CLS token vs mean pooling vs GeM pooling_200m同尺度\DINOv2不同Pooling策略_200m同尺度跨视角粗定位实验结果说明_2026-03-17.docx`
3. 如果要继续推进，可以优先考虑：
   - 进一步解释为何同尺度下 `mean/gem` 的 `Recall@1` 高于 `pooler/cls`
   - 继续引入局部几何重排，对不同 pooling 的 Top-K 做融合验证
   - 把本轮同尺度结果与上一轮多尺度结果系统化对照整理成正式章节或汇报材料

## 11. 一句话交接结论

一句话给下一个智能体：

当前已经完成了 `200m query vs 200m satellite tile` 严格同尺度口径下的 `pooler / cls / mean / gem` 四种 DINOv2 pooling 对比实验，结果、可视化和偏论文式 Word 报告都已生成完毕，主结论是：同尺度条件下 pooling 会显著影响首位命中与误差分布，但尚无证据支持某一种 pooling 在所有维度上全面优于其他方案。

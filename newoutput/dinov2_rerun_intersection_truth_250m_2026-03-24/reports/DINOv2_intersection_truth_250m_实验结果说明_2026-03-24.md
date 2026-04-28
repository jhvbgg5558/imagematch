# DINOv2 + FAISS 在 Intersection Truth 口径下的基线实验结果说明

## 1. 任务定义与实验设置
本组实验用于回答：在新的 `intersection truth` 真值定义下，`DINOv2 + FAISS` 作为跨视角区域级粗定位基线，能够达到怎样的检索表现。

- 数据范围：4 条航线，共 `40` 个 query。
- 卫片候选库：`1029` 张卫片，来源于四条航线总体范围外扩 `250m` 后构建的固定库。
- 方法：`facebook/dinov2-base` pooler 特征 + FAISS `IndexFlatIP`。
- 主展示口径：`top_k=20`；辅助分析口径：`top_k=1029`（全库排序）。

## 2. Intersection Truth 定义
本轮正式真值定义为：只要 query 覆盖范围与卫片存在非零面积相交，该卫片就记为 `intersection truth`。
这一定义比原先的单点式真值更宽，也更贴近“只要检索到与查询范围有真实地理交集的区域即可视为有效候选”的任务目标。

## 3. 指标定义
- `Intersection Recall@1/5/10/20`：前 K 名中是否命中 intersection truth。
- `Intersection MRR`：首个 intersection truth 排名倒数的平均值。
- `Top-1 error mean (m)`：首位候选中心与 query 参考位置之间的平均距离。

## 4. 总体定量结果
| 口径 | R@1 | R@5 | R@10 | R@20 | MRR | Top-1误差均值(m) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Top-20 | 0.525 | 0.800 | 0.900 | 0.975 | 0.654 | 759.071 |
| 全库排序 | 0.525 | 0.800 | 0.900 | 0.975 | 0.655 | 759.071 |

主口径 `Top-20` 下，当前基线达到 `R@1=0.525`、`R@10=0.900`、`R@20=0.975`、`MRR=0.654`。
与全库排序相比，`Top-20` 结果几乎没有损失，说明大部分有效命中已经集中在前 20 名候选中。

## 5. 分航线结果（Top-20）
| 航线 | Query数 | R@1 | R@5 | R@10 | R@20 | MRR | Top-1误差均值(m) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 009 | 10 | 0.400 | 0.900 | 0.900 | 0.900 | 0.583 | 718.153 |
| 010 | 10 | 0.600 | 0.800 | 1.000 | 1.000 | 0.727 | 783.721 |
| 011 | 10 | 0.800 | 1.000 | 1.000 | 1.000 | 0.858 | 638.405 |
| 012 | 10 | 0.300 | 0.500 | 0.700 | 1.000 | 0.449 | 896.007 |

可以看到，四条航线之间存在明显差异，其中 `011` 航线表现最好，`012` 航线相对最难。

## 6. 时间开销统计
| 阶段 | 耗时 |
| --- | ---: |
| 卫片特征提取 | 3454.23s (57.57 min) |
| FAISS 建库 | 1.76s (0.03 min) |
| Query 特征提取 | 183.00s (3.05 min) |
| 检索评估（Top-20） | 1.59s (0.03 min) |

## 7. Top-K 曲线结果解读
- full-truth 曲线结果：`40/40` 个 query 都能达到真值饱和，整体 `mean=1023.775`、`median=1024`、`p95=1029`。
- unique-tile 曲线结果：全部唯一真值 tile 数为 `475`，而 `k_full_truth=1029`，等于候选总量 `1029`。
- 这说明当前基线在前排候选上的命中能力已经较强，但若目标是把所有真值 tile 全部覆盖到，则仍需要接近全库深度。

## 8. 关键图表
- `figures/_aggregate/overall_metrics_bar.png`：overall 指标图。
- `figures/_aggregate/multi_flight_recall.png`：分航线 Recall 对比。
- `figures/_aggregate/top1_error_distribution.png`：Top-1 误差分布。
- `figures_topk_fulltruth/_aggregate/overall_topk_truth_count_curve_all.png`：full-truth 曲线。
- `figures_topk_unique_tile/_aggregate/overall_topk_unique_truth_count_curve.png`：unique-tile 曲线。

## 9. 结论
- 在 `intersection truth` 口径下，`DINOv2 + FAISS` 已经具备较强的区域级初步地理定位能力，`Top-20` 下可达到 `R@20=0.975`。
- 当前方法的主要瓶颈不在于前 20 名候选覆盖不足，而在于若希望把所有真值 tile 全部找全，仍需要很深的检索深度。
- 后续若继续优化，应优先提升排序判别力，降低达到全真值覆盖所需的 `K`，而不是仅扩大候选窗口。

# SuperPoint + LightGlue 在 Intersection Truth 口径下的重排结果说明

## 1. 任务定义与实验设置
本组实验用于回答：在 `intersection truth` 新真值口径下，若先用 `DINOv2 + FAISS` 对全库粗检索，再对前 `Top-50` 候选使用 `SuperPoint + LightGlue` 做局部重排，是否能够进一步改善正式指标。

- 数据范围：4 条航线，共 `40` 个 query。
- 固定候选库：`1029` 张卫片，来源于四条航线总体范围外扩 `250m` 后构建的固定库。
- 粗检索：DINOv2 pooler 特征 + FAISS `IndexFlatIP`。
- 重排方法：SuperPoint 局部特征 + LightGlue 匹配 + RANSAC 几何一致性 + 融合分数排序。
- 重排窗口：每个 query 的 coarse `Top-50`。
- Top-K 曲线口径：`1..50` 使用 LightGlue 结果，`51..1029` 保持 baseline 原顺序。

## 2. Intersection Truth 定义
本轮正式真值定义为：只要 query 覆盖范围与卫片存在非零面积相交，该卫片就记为 `intersection truth`。

## 3. 指标定义
- `Intersection Recall@1/5/10/20/50`：前 K 名中是否命中 intersection truth。
- `Intersection MRR`：首个 intersection truth 排名倒数的平均值。
- `Top-1 error mean (m)`：首位候选中心与 query 参考位置之间的平均距离。

## 4. 总体定量结果

- Baseline：`R@1=0.525`，`R@5=0.800`，`R@10=0.900`，`R@20=0.975`，`MRR=0.654`
- Coarse Top50 上限：`R@50=1.000`
- LightGlue：`R@1=0.525`，`R@5=0.775`，`R@10=0.925`，`R@20=0.975`，`R@50=1.000`，`MRR=0.649`
- 指标变化：`ΔR@1=+0.000`，`ΔR@5=-0.025`，`ΔR@10=+0.025`，`ΔMRR=-0.005`
- Top-1 误差：`759.071m -> 677.336m`

## 5. 分航线结果

- `009`：Baseline `R@10=0.900`，LightGlue `R@10=0.900`，`Δ=+0.000`
- `010`：Baseline `R@10=1.000`，LightGlue `R@10=1.000`，`Δ=+0.000`
- `011`：Baseline `R@10=1.000`，LightGlue `R@10=1.000`，`Δ=+0.000`
- `012`：Baseline `R@10=0.700`，LightGlue `R@10=0.800`，`Δ=+0.100`

## 6. 时间开销统计

- coarse Top-50 导出：`2.71s (0.05 min)`
- 输入准备：`0.54s (0.01 min)`
- LightGlue 重排：`4330.36s (72.17 min)`
- 结果汇总：`0.42s (0.01 min)`
- 可视化：`69.53s (1.16 min)`

## 7. Top-K 曲线结果

- full-truth：`40/40` 个 query 都能达到真值饱和，`mean=1023.775`，`median=1024`，`p95=1029`。
- unique-tile：唯一真值 tile 数为 `475`，`k_full_truth=1029`，候选唯一 tile 总数为 `1029`。
- 这说明 LightGlue 虽然改变了前 50 名内部顺序，但如果目标是把全部真值 tile 找全，仍然需要接近全库深度。

## 8. 代表性样例

- `q_038` / `012`：从 11..50 拉回 Top-10 的改进样例；Baseline 首个真值 rank=`12`，Coarse Top50 rank=`12`，LightGlue rank=`8`。
- `q_033` / `012`：前排排名进一步提升样例；Baseline 首个真值 rank=`14`，Coarse Top50 rank=`14`，LightGlue rank=`12`。
- `q_031` / `012`：Top-50 内存在真值但仍未进入 Top-10 的样例；Baseline 首个真值 rank=`17`，Coarse Top50 rank=`17`，LightGlue rank=`17`。

## 9. 结论

- 本轮 `LightGlue` 没有提升 `Recall@1`，但把 `Recall@10` 从 `0.900` 提升到 `0.925`。
- `Recall@5` 与 `MRR` 略有下降，说明当前局部重排并未稳定改善最前排排序质量。
- `Top-1 error mean` 从 `759.071m` 降到 `677.336m`，说明首位候选的空间误差有一定改善。
- 更准确的结论是：当前 LightGlue 更像是在局部改善前十名覆盖，而不是已经稳定提升首位候选最优性。

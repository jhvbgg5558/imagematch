# RoMa v2 收益边界分析报告

## 1. 分析目标

本轮分析的目标不是再次证明 `RoMa v2` 优于 coarse baseline，而是回答四个更关键的问题：

- 它的收益主要来自哪里。
- 它对哪类 query 最有帮助。
- 它在什么情况下仍然失败。
- 当前瓶颈更偏向 coarse recall，还是 rerank 判别能力。

主分析固定建立在 `query v2 + intersection truth` 口径上，且 `coarse` 唯一真源固定为 `romav2_eval_2026-03-30_gpu/coarse/retrieval_top20.csv`。

## 2. 主桶结果

本轮 `40` 个 query 的主桶分布为：

- `A=31`：coarse Top-1 已命中，RoMa v2 保持 Top-1 命中。
- `B=6`：coarse Top-1 未命中，但 coarse Top-20 已召回 truth，RoMa v2 最终提升到 Top-1。
- `C=3`：coarse Top-20 已召回 truth，但 RoMa v2 仍未提升到 Top-1。
- `D=0`：本轮没有出现 coarse Top-20 完全未召回 truth 的 query。

这说明当前 `R@1` 的全部新增命中都来自 `B` 类，且数量正好为 `6`。补表 A 也验证了这一点：`B` 类贡献了 `100%` 的新增 Top-1 命中，`A` 类主要提供稳定性或误差收缩，`C` 类暴露的是 rerank 未吃满 coarse recall 的边界。

## 3. 收益解释

`B` 类是本轮最关键的证据。它们满足同一个模式：coarse stage 已经把真实区域召回进 Top-20，但前排排序仍然错误；RoMa v2 进一步利用局部几何一致性，把 truth 从 `rank 2/3` 推升到 `rank 1`。当前 `B` 类一共 `6` 个样本，覆盖下视和倾斜两类 query，也分布在多条航线上，说明收益不是单航线偶然现象。

从代表案例看，这种收益同时体现在命中层和误差层。比如 `q_002`、`q_013`、`q_022` 和 `q_037` 都从 coarse 的非 Top-1 truth 提升为最终 Top-1 truth，且 Top-1 地理误差显著下降。这支持一个更稳健的结论：在 coarse Top-20 已经召回正确区域的前提下，RoMa v2 的主要价值不是扩大召回窗口，而是纠正 coarse 前排误排。

`A` 类数量最多，说明 coarse retrieval 本身已经较强。RoMa v2 在这类样本上的作用主要是稳健化，而不是决定性纠正。部分 A 类样本存在明显误差收缩，例如 `q_034` 的 Top-1 误差下降接近 `1 km`，但这类收益不应被写成“主贡献”，因为 coarse 本身已经命中。

## 4. 失败边界

本轮没有出现 `D` 类，因此当前数据不支持把主要瓶颈归因到 coarse recall 上限。换句话说，在这 40 个 query 上，coarse Top-20 已经覆盖了全部 truth；问题没有卡在“召回不到”，而是卡在“召回到了但没有总能排到第一”。

失败边界主要集中在 `C` 类，共 `3` 个样本，且全部属于 `C_retained`，没有 `C_drop_out`。这意味着 RoMa v2 当前并没有明显破坏已有 coarse recall；它的问题更像是“还没把 truth 充分推到最前面”，而不是“把已有 truth 挤出 Top-20”。这 3 个样本里，`q_001`、`q_023`、`q_038` 的 truth rank 分别从 `7/5/6` 改善到 `3/2/2`，说明 rerank 有收益，但收益还不够完成最后一步纠正。

从初始化的失败标签看，当前 C 类更接近两种模式：

- `hard_negative_dominance`：truth 被保留，但更强的假匹配区域仍占据前排。
- `large_viewpoint_gap`：倾斜视角下，正射候选与 UAV 外观差异仍然限制了几何重排的最终判别力。

## 5. 结论

本轮收益边界分析给出的核心结论是：

1. `RoMa v2` 的新增 `R@1` 收益全部来自 `B` 类，即“coarse 已召回、rerank 成功纠正排序”的样本。
2. 当前 40 个 query 中没有出现 `D` 类，说明这一轮的主瓶颈不在 coarse Top-20 recall，而在 rerank 对 hard negatives 的最终判别能力。
3. `C` 类全部为 `C_retained`，没有 `C_drop_out`，表明 RoMa v2 在这轮结果中没有表现出明显的重排破坏风险。
4. 因此，这轮实验最能支撑的主张不是“RoMa v2 扩大了召回边界”，而是“在 coarse stage 已经把正确区域拉进候选集后，几何重排能够稳定提升区域级初步地理定位的前排排序质量”。

## 6. 当前局限与下一步

这轮分析仍有两个边界：

- `D=0`，所以还不能对 coarse recall 失效模式做实证分解。
- `C` 类数量只有 `3`，失败模式判断目前仍应视为小样本结论。

下一步最自然的延伸不是改桶规则，而是沿用同一套分析框架继续看：

- `B` 类的几何收益是否集中在特定俯仰角或场景类型。
- `C` 类为何只能把 truth 推到 `rank 2/3` 而不是 `rank 1`。
- 后续若出现 `D` 类，再用同一脚本直接补 coarse recall 上限分析，而不用重写整套框架。

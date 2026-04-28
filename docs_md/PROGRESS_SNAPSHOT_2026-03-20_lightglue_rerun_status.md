# 当前进度快照

日期：2026-03-20

## 1. 当前正在做的工作

当前正在执行：

> 基于 `DINOv2 + FAISS` 的 strict truth 基线，使用 `SuperPoint + LightGlue` 对 `Top-20` 粗候选做局部几何重排。

当前目标是验证：

- 在 strict truth 口径下
- 通过 `Top-20` 候选扩窗
- 再用 `SuperPoint + LightGlue` 做局部匹配重排

是否能把更多真值从 `11..20` 推回前 `Top-10`，从而提升正式主指标 `Recall@1/5/10`。

## 2. 当前已经确认的前提

strict truth 基线结果已经确认：

- `strict Recall@1 = 0.175`
- `strict Recall@5 = 0.375`
- `strict Recall@10 = 0.425`
- `strict MRR = 0.262`

同时已确认：

- `17/40` 个 query 的首个 strict truth 在 `Top-10`
- `11/40` 个 query 的首个 strict truth 在 `11..20`
- `12/40` 个 query 在 `Top-20` 外仍未命中

因此当前方案结论仍然成立：

- LightGlue 重排窗口必须用 `Top-20`
- `Recall@20` 只作为 coarse candidate 上限诊断
- 正式主指标仍然继续看 `Recall@1/5/10` 和 `MRR`

## 3. 当前已经完成的内容

已完成脚本准备：

- `scripts/prepare_lightglue_strict_inputs.py`
- `scripts/rerank_with_lightglue_strict.py`
- `scripts/run_lightglue_rerank_strict_round.py`

已完成数据准备：

- 已生成新目录：
  - `output/coverage_truth_200_300_500_700_lightglue_superpoint_fused_top20_k256_strict`
- 已生成 `Top-20` coarse retrieval：
  - `coarse/retrieval_top20.csv`
  - `coarse/summary_top20.json`
- 已生成 LightGlue 批量输入：
  - `input_round/stage3/<flight_id>/queries.csv`
  - `input_round/stage4/<flight_id>/retrieval_top20.csv`

## 4. 当前现场状态

本轮在执行过程中，曾出现过重复启动的残留 LightGlue 诊断进程，导致 CPU 异常升高。

当前已完成：

- 已清理所有残留的 `LightGlue` 相关 Python 进程
- 已确认清理后 CPU 恢复空闲
- 已删除上一轮失败遗留的 `stage7` 空文件
- 已重新启动一条干净的批量 LightGlue 重排任务

当前运行状态：

- 当前仅保留一条有效的 `rerank_with_lightglue_strict.py` 进程
- 当前正在跑 `009` 航线
- 当前使用参数：
  - `Top-20`
  - `SuperPoint k256`
  - `ranking_mode = fused`
  - `device = cpu`

## 5. 当前需要注意的现象

当前 `stage7/<flight_id>/reranked_top20.csv` 和 `per_query_geom_metrics.csv` 在航线计算期间可能保持 `0` 字节。

这不是异常，而是因为当前脚本实现会：

- 先在内存中完成一整条航线的计算
- 再统一把结果写入文件

因此只要：

- 批量总控进程还在
- 对应航线的 `rerank_top20.json` 还没落盘
- 系统里仍能看到 `rerank_with_lightglue_strict.py` 在持续吃 CPU

就应判断为“还在正常运行中”，而不是“已经挂掉”。

## 6. 当前尚未完成的内容

当前还没有完成以下内容：

- `009` 航线的 `rerank_top20.json` 结果落盘
- `010/011/012` 三条航线的批量重排
- `aggregate_summary.json`
- LightGlue 聚合图与分航线图
- LightGlue 正式报告
- strict baseline vs LightGlue rerank 的对照总结

## 7. 下一步建议

- 继续等待当前干净的批量 LightGlue 任务完成
- 第一优先关注 `009` 航线的 `rerank_top20.json` 是否落盘
- 一旦全量四条航线完成，立即汇总：
  - `strict Recall@1/5/10/20`
  - `strict MRR`
  - 各航线提升情况
- 再判断 `Top-20` 扩窗是否真正带来了前 `Top-10` 的可见收益

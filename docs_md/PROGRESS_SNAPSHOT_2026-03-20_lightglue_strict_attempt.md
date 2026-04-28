# 当前进度快照

日期：2026-03-20

## 1. 当前正在尝试的工作

当前正在把 `DINOv2 + FAISS` 的 strict truth 基线扩展为：

> DINOv2 coarse retrieval + SuperPoint + LightGlue rerank

目标是观察在 `Top-20` 粗候选窗口下，局部几何重排是否能把更多 strict truth 真值推回前 `Top-10`，从而提升正式主指标。

## 2. 当前已确认的前提结论

基于 strict truth 口径的 dry-run 结果已经确认：

- 当前 baseline 的 `strict Recall@10 = 0.425`
- 当前 baseline 的 `strict MRR = 0.262`
- `40` 个 query 中：
  - `17` 个 query 的首个 strict truth 在 `Top-10`
  - `11` 个 query 的首个 strict truth 在 `11..20`
  - `12` 个 query 在 `Top-20` 外仍未命中

因此当前方案判断是：

- LightGlue 不应只看 `Top-10`
- 当前应该采用 `Top-20` 作为重排窗口
- 正式主指标仍然继续看 `Recall@1/5/10`
- `Recall@20` 只作为 coarse candidate 上限诊断指标

## 3. 当前已经完成的内容

已完成脚本补充：

- `scripts/prepare_lightglue_strict_inputs.py`
- `scripts/rerank_with_lightglue_strict.py`
- `scripts/run_lightglue_rerank_strict_round.py`

已完成资产准备：

- 已生成新的结果目录：
  - `output/coverage_truth_200_300_500_700_lightglue_superpoint_fused_top20_k256_strict`
- 已生成 `Top-20` coarse retrieval：
  - `coarse/retrieval_top20.csv`
  - `coarse/summary_top20.json`
- 已生成 LightGlue 需要的 `stage3/stage4` 输入：
  - `input_round/stage3/<flight_id>/queries.csv`
  - `input_round/stage4/<flight_id>/retrieval_top20.csv`

## 4. 当前阻塞点

当前阻塞不在脚本逻辑，而在运行时环境：

- `.conda` 环境里 `cv2` 可以正常导入
- 但 `torch` 导入在 `20s` 内超时
- `lightglue` 导入在 `20s` 内也超时

已验证现象：

- `timeout 20 python -c "import cv2"` 正常返回
- `timeout 20 python -c "import torch"` 超时
- `timeout 20 python -c "import lightglue"` 超时

因此当前全量 LightGlue 重排没有真正开始执行，已有的 `stage7/009` 零字节文件只是本轮尝试中断时遗留的空文件，不代表有效结果。

## 5. 当前结论

当前可以确认两件事：

1. 方法路线是合理的

- 从当前 strict truth 基线看，采用 `Top-20` 作为 LightGlue 重排窗口是必要的
- 否则会直接错过 `11/40` 个本来仍有机会被局部匹配拉升的 query

2. 当前不能继续推进的原因是环境问题

- 不是数据格式问题
- 不是真值口径问题
- 不是脚本接口问题
- 而是 `.conda` 里的 `torch/lightglue` 运行时目前不可用

## 6. 下一步建议

- 优先修复 `.conda` 环境中的 `torch/lightglue` 导入问题
- 修复后先做单航线 `009` 的 LightGlue 烟雾测试
- 单航线成功后再跑全量 `40` query
- 全量跑完后再生成：
  - `aggregate_summary.json`
  - 聚合图与分航线图
  - strict baseline vs LightGlue rerank 对照报告

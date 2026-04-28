# 代码编写与可读性约定

这份文档记录当前项目推荐遵守的代码编写规则，重点是提升脚本可读性、实验复现性和后续接手效率。

## 1. 文件头说明要求

从现在开始，**每个新建或明显重构的代码文件都应在文件开头写简要说明注释**。

对于 Python 文件，建议使用模块级 docstring，至少写清 4 件事：

- 这个文件是做什么的
- 主要输入是什么
- 主要输出是什么
- 适用于哪类实验或流程

推荐格式示例：

```python
"""Run strict same-scale LightGlue reranking.

Inputs:
- query metadata CSV
- retrieval CSV
- tiles CSV

Outputs:
- reranked CSV
- per-query metrics CSV
- summary JSON

Used for:
- 200m query vs 200m satellite formal evaluation
"""
```

## 2. 脚本命名规则

脚本命名应尽量表达“动作 + 方法 + 口径”，例如：

- `prepare_200m_same_scale_experiment.py`
- `run_lightglue_rerank_round.py`
- `generate_same_scale_comparison_report.py`

避免使用过于泛化、无法看出用途的名字。

## 3. 结果目录命名规则

结果目录应尽量体现：

- query 尺度
- satellite 尺度
- 方法
- 关键变体

例如：

- `validation_200m_same_scale`
- `validation_200m_same_scale_sift_gate3`
- `validation_200m_same_scale_lightglue_superpoint_fused_top10_k256`

## 4. 正式口径与探索口径隔离

如果脚本只适用于历史探索结果，应在文件头说明中明确写出：

- 该脚本适用的实验口径
- 是否属于正式结果链路

如果脚本服务于正式实验，文件头应明确写出：

- 正式实验口径：`200m query vs 200m satellite`
- 真值定义：中心落入 200m 瓦片

## 5. 可读性要求

- 一个脚本尽量只负责一类清晰任务
- 输出文件命名尽量与方法一致
- 关键阈值和关键参数要显式写在参数区，不要埋在函数内部
- 对关键排序逻辑、重排逻辑、评估逻辑，必要时补简短注释

## 6. 更新建议

后续如果对现有脚本做较大修改，建议顺手补齐文件头说明，使脚本在脱离上下文时也能快速理解。


# 武汉GNSS拒止视觉定位 跨视角检索Pooling对比实验进度

日期：2026-03-11

## 1. 当前研究背景与任务位置

当前工作属于“GNSS拒止环境下无人机视觉定位与融合导航理论与方法研究”的全局定位模块可行性论证。

当前已经完成的第一阶段论证结论是：

- 基于遥感正射影像，可以对无人机影像进行初步地理定位，即跨视角粗检索定位是可行的。
- 已有 PoC 基线方法为 `DINOv2-base + FAISS(IndexFlatIP)`。
- 后续方法对比应尽量复用既有数据资产、查询集与真值定义，避免重新处理原始数据。

本轮工作的主题是：

- 在现有 PoC 基础上，对比 `pooler / CLS token / mean pooling / GeM pooling` 这几种 DINOv2 全局特征聚合方式。

## 2. 已读取并确认的关键文档

已读取以下两份文档，并据此建立后续实验约束：

- `D:\aiproject\imagematch\武汉GNSS拒止视觉定位_已处理数据资产说明_2026-03-11.docx`
- `D:\aiproject\imagematch\方案\DINOv2+FAISS\基于DINOv2与FAISS的无人机_卫星跨视角粗定位PoC报告_2026-03-10.docx`

对应 WSL 路径：

- `/mnt/d/aiproject/imagematch/武汉GNSS拒止视觉定位_已处理数据资产说明_2026-03-11.docx`
- `/mnt/d/aiproject/imagematch/方案/DINOv2+FAISS/基于DINOv2与FAISS的无人机_卫星跨视角粗定位PoC报告_2026-03-10.docx`

## 3. 已确认的数据资产与公平比较口径

后续对比实验默认沿用以下设置：

- 无人机正射数据：4 条航线 `odm_orthophoto.tif`
- 卫星数据：已重投影到 `EPSG:32650` 的卫星切片
- 卫星候选瓦片库：`/mnt/d/aiproject/imagematch/output/stage1/tiles_80_120_200`
- 卫星瓦片元数据：`/mnt/d/aiproject/imagematch/output/stage1/tiles_80_120_200/tiles.csv`
- 公平查询集：`/mnt/d/aiproject/imagematch/output/validation_round3_200m_fair/stage3`
- 主查询尺度：`200m-only`
- 真值规则：继续沿用 `truth_tile_ids`

这样做的目的是保证不同 pooling 方案之间是严格的单变量对比，只替换“DINOv2 输出如何聚合成全局向量”这一层。

## 4. 现有 PoC 基线结论

现有 `pooler` 基线对应原始 PoC 主链路，即：

- 卫星瓦片经过 `DINOv2-base`
- 无人机查询图经过 `DINOv2-base`
- 双方进入同一特征空间
- 经过 `L2 normalize`
- 使用 `FAISS IndexFlatIP` 检索

此前文档中确认的 fair 查询集基线召回结果为：

- `009`: `Recall@1=0.6, Recall@5=1.0, Recall@10=1.0`
- `010`: `Recall@1=0.4, Recall@5=0.8, Recall@10=1.0`
- `011`: `Recall@1=0.6, Recall@5=0.8, Recall@10=1.0`
- `012`: `Recall@1=0.4, Recall@5=0.6, Recall@10=0.6`

## 5. 本轮确定的对比指标

用户已明确对比指标固定为以下 6 项：

1. `Recall@1`
2. `Recall@5`
3. `Recall@10`
4. `MRR`
5. `Top-1定位误差（米）`
6. 单次检索耗时，并补充单次查询特征提取耗时、单次总耗时

## 6. 本轮对实验设计的修正

原始设想是对比：

- CLS
- mean pooling
- GeM pooling

核对现有脚本后发现，原 PoC 特征提取脚本优先使用的是 `outputs.pooler_output`，因此不能把“CLS”直接等同于“现有基线”，需要改成更严谨的 4 组：

- `pooler`
- `cls`
- `mean`
- `gem`

当前实验含义是：

- 每一种方法都是“卫星图像和无人机查询图都经过同一个 DINOv2 + 同一种 pooling 方式”，再进入同一 FAISS 检索空间。
- 不做“卫星一种 pooling、无人机另一种 pooling”的混搭。

## 7. 已完成的代码改动

本轮已经修改或新增了以下脚本：

- `/mnt/d/aiproject/imagematch/scripts/extract_dino_features.py`
- `/mnt/d/aiproject/imagematch/scripts/measure_query_timing.py`
- `/mnt/d/aiproject/imagematch/scripts/query_faiss_index.py`
- `/mnt/d/aiproject/imagematch/scripts/analyze_retrieval_results.py`
- `/mnt/d/aiproject/imagematch/scripts/compare_pooling_variants.py`

其中主要改动为：

- `extract_dino_features.py`
  - 新增 `--pooling {pooler, cls, mean, gem}`
  - 新增 `--gem-p`
  - 支持 patch token 上的 `mean` 和 `GeM`
- `measure_query_timing.py`
  - 同步支持多种 pooling
- `query_faiss_index.py`
  - 新增 `MRR`
  - 新增 `Top-1定位误差（米）`
- `analyze_retrieval_results.py`
  - 将 `MRR` 和 `Top-1误差` 纳入分析输出
- `compare_pooling_variants.py`
  - 新增完整总控脚本
  - 自动按 `pooler -> cls -> mean -> gem` 顺序串行跑完整流程
  - 支持直接复用已有 `pooler` 卫星索引，避免重复重建基线卫星特征库

## 8. 结果输出目录

本轮对比实验结果统一写入：

- `D:\aiproject\imagematch\方案\CLS token vs mean pooling vs GeM pooling`

对应 WSL 路径：

- `/mnt/d/aiproject/imagematch/方案/CLS token vs mean pooling vs GeM pooling`

预期最终输出包括：

- `comparison_summary.json`
- `comparison_summary.md`
- `overall_metrics.csv`
- `per_flight_metrics.csv`
- 各方法独立子目录：
  - `pooler`
  - `cls`
  - `mean`
  - `gem`

## 9. 当前执行状态

当前总控脚本已经启动，并按顺序自动执行各方案。

运行方式：

- 使用 CPU 运行
- 不使用 CUDA
- 模型：`facebook/dinov2-base`
- 检索索引：`FAISS IndexFlatIP`

重要说明：

- `cls` 目录下长时间没有结果文件，不代表卡死。
- 当前 `extract_dino_features.py` 的实现方式是：
  - 先把所有图像的特征在内存中累计
  - 全部处理完后再统一写出 `npz/csv`
- 因此在 `cls/stage2` 的“卫星特征提取”阶段，CPU 会持续高负载，但目录暂时没有产物是正常现象。

## 10. 当前已完成的结果

### 10.1 pooler 基线已完整跑完

`pooler` 已完成：

- 四条航线查询特征提取
- 检索
- `Recall@1/5/10`
- `MRR`
- `Top-1定位误差`
- 单次特征提取耗时
- 单次检索耗时
- 单次总耗时

`pooler` 总体结果如下：

- `query_count = 20`
- `Recall@1 = 0.500`
- `Recall@5 = 0.800`
- `Recall@10 = 0.900`
- `MRR = 0.601388888888889`
- `Top-1定位误差均值 = 370.2049917688713 m`

`pooler` 平均时延如下：

- 单次特征提取均值：`2570.166416000575 ms`
- 单次检索均值：`1.2378849554806948 ms`
- 单次总耗时均值：`2571.4072410133667 ms`

### 10.2 pooler 分航线结果

- `009`
  - `Recall@1=0.600`
  - `Recall@5=1.000`
  - `Recall@10=1.000`
  - `MRR=0.750`
  - `Top-1误差均值=353.16195126963123 m`
- `010`
  - `Recall@1=0.400`
  - `Recall@5=0.800`
  - `Recall@10=1.000`
  - `MRR=0.529`
  - `Top-1误差均值=654.2659450963899 m`
- `011`
  - `Recall@1=0.600`
  - `Recall@5=0.800`
  - `Recall@10=1.000`
  - `MRR=0.660`
  - `Top-1误差均值=237.06463003569493 m`
- `012`
  - `Recall@1=0.400`
  - `Recall@5=0.600`
  - `Recall@10=0.600`
  - `MRR=0.467`
  - `Top-1误差均值=236.32744067376916 m`

这些结果说明：

- 新接入的 `MRR` 和 `Top-1误差` 没有破坏原有召回评估口径。
- `pooler` 召回趋势与原有 fair 基线保持一致。

## 11. 当前正在运行的阶段

当前状态：

- `pooler` 已完成
- `cls` 正在执行 `stage2` 的卫星特征提取
- `mean` 尚未开始
- `gem` 尚未开始

已经确认总控脚本会自动顺序继续：

1. 完成 `cls`
2. 自动执行 `mean`
3. 自动执行 `gem`

不需要人工再次启动，除非进程被手动中断或异常退出。

## 12. 下一个智能体接手时应优先做什么

如果下次新开一个智能体，建议按以下顺序接手：

1. 先检查总控进程是否仍在运行：
   - `compare_pooling_variants.py`
   - `extract_dino_features.py`
2. 检查结果目录：
   - `/mnt/d/aiproject/imagematch/方案/CLS token vs mean pooling vs GeM pooling`
3. 如果 `comparison_summary.json` 已生成，直接汇总四组方法结果并进行解读。
4. 如果仍停在某一方法的 `stage2`，优先确认是否只是卫星特征尚未落盘，而不是报错中断。
5. 如果任务失败或被中断，再决定是否续跑或拆分执行。

## 13. 当前最关键的交接结论

一句话总结给下一个智能体：

当前已经完成了基于现有 fair 查询集的 pooling 对比实验框架改造，`pooler` 基线结果已完整产出，`cls` 正在进行卫星特征提取，之后会自动串行执行 `mean` 和 `gem`，最终总表会落在 `D:\aiproject\imagematch\方案\CLS token vs mean pooling vs GeM pooling`。

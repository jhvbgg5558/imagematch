# DINOv3 vs DINOv2 在 Intersection Truth v2 口径下的对比说明

## 1. 对比目标
本报告用于对比当前最新 `query v2` 数据口径下，`DINOv2 + FAISS` 与 `DINOv3 + FAISS` 两套全局特征基线在 `intersection truth` 口径下的区域级检索表现。

## 2. 对比前提与数据来源
- 对比口径统一为 `intersection truth`。
- 对比 query 统一为 `query_reselect_2026-03-26_v2` 这一批 4 航线共 `40` 张 query。
- DINOv2 来源目录：`/mnt/d/aiproject/imagematch/new1output/query_reselect_2026-03-26_v2`
- DINOv3 来源目录：`/mnt/d/aiproject/imagematch/new1output/query_reselect_2026-03-26_v2/dinov3_eval_2026-03-30`
- 当前结论只比较正式输出结果，不重新跑实验。

## 3. 总体指标对比
| 指标 | DINOv2 | DINOv3 | Delta (v3-v2) |
| --- | ---: | ---: | ---: |
| Top-20 R@1 | 0.825 | 0.775 | -0.050 (DINOv3更低) |
| Top-20 R@5 | 0.975 | 0.950 | -0.025 (DINOv3更低) |
| Top-20 R@10 | 1.000 | 1.000 | 0.000 (持平) |
| Top-20 R@20 | 1.000 | 1.000 | 0.000 (持平) |
| Top-20 MRR | 0.899 | 0.850 | -0.048 (DINOv3更低) |
| Top-20 Top-1误差均值(m) | 721.818 | 862.191 | +140.374 (DINOv3更高) |
| 全库 MRR | 0.899 | 0.850 | -0.048 (DINOv3更低) |

总体上，DINOv2 在当前 `query v2` 口径下优于 DINOv3：DINOv2 的 `R@1=0.825`，DINOv3 的 `R@1=0.775`，两者相差 `-0.050`；`MRR` 也从 DINOv2 的 `0.899` 降到 DINOv3 的 `0.850`。
误差方面，DINOv3 的 `Top-1 error mean` 为 `862.191m`，高于 DINOv2 的 `721.818m`，说明这次升级没有把首位候选的空间偏差压低。

## 4. 分航线总览对比（Top-20）
| 航线 | DINOv2 R@1 | DINOv3 R@1 | Delta | DINOv2 MRR | DINOv3 MRR | DINOv2误差(m) | DINOv3误差(m) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 009 | 0.800 | 0.700 | -0.100 | 0.900 | 0.798 | 657.772 | 945.379 |
| 010 | 0.900 | 0.900 | +0.000 | 0.950 | 0.950 | 760.124 | 671.929 |
| 011 | 0.900 | 0.700 | -0.200 | 0.950 | 0.803 | 656.425 | 901.809 |
| 012 | 0.700 | 0.800 | +0.100 | 0.794 | 0.850 | 812.951 | 929.648 |

- `009` 航线：DINOv2 `R@1=0.800`，DINOv3 `R@1=0.700`，DINOv3 更弱。
- `010` 航线：两者都较强，但 DINOv2 `R@1=0.900` 仍高于 DINOv3。
- `011` 航线：DINOv2 `R@1=0.900`，DINOv3 `R@1=0.700`，差距明显。
- `012` 航线：DINOv2 `R@1=0.700`，DINOv3 `R@1=0.800`，这是 DINOv3 唯一更强的一条航线。

## 5. 时间说明
当前 `query v2` 目录下未发现 DINOv2 同批次同口径的 timing 文件，因此本报告不做严格公平的 DINOv2 vs DINOv3 耗时横向结论。
目前能确认的只有 DINOv3 本轮实测时间：

| 阶段 | DINOv3耗时 |
| --- | ---: |
| 卫片特征提取 | 2587.00s (43.12 min) |
| FAISS 建库 | 2.00s (0.03 min) |
| Query 特征提取 | 125.00s (2.08 min) |
| 检索评估（Top-20） | 2.00s (0.03 min) |

补充说明：`new1output/query_reselect_2026-03-26_v2/timing/` 下的 3 个 json 文件名都显式标记为 `dinov3`，应视为 DINOv3 的前处理与建库时间，不属于 DINOv2。

## 6. 结论
- 在当前最新 `intersection truth v2` 口径下，DINOv2 是更强的全局特征基线。
- DINOv3 没有带来召回率、MRR 或 Top-1 平均误差的改善。
- DINOv3 的主要问题不是“Top-20 覆盖不够”，因为两者都已在 `R@10/R@20` 上接近饱和；问题在于前排排序判别力没有优于 DINOv2。
- 若后续还要比较速度，需要为 DINOv2 `query v2` 这套结果补齐同批次 timing，再做严格耗时对比。

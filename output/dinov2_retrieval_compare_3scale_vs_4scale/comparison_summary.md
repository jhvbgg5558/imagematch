# DINOv2 三尺度 vs 四尺度对比

| metric | three_scale | four_scale | delta |
| --- | --- | --- | --- |
| recall@1 | 0.05 | 0.125 | 0.075 |
| recall@5 | 0.275 | 0.275 | 0.0 |
| recall@10 | 0.35 | 0.375 | 0.025000000000000022 |
| mrr | 0.14215277777777777 | 0.1931547619047619 | 0.051001984126984146 |
| top1_error_m_mean | 712.8402938520987 | 778.537863555553 | 65.69756970345429 |

- improved queries: 5
- degraded queries: 4
- unchanged queries: 31
- new top1 hits with 300m: 3

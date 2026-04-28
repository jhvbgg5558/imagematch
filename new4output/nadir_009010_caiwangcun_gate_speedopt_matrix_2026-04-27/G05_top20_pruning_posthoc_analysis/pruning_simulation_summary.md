# G05 Top-20 精简验证后处理分析

## 结论

- Do not adopt universal Top-1 pruning yet; inspect the per-source minimum Top-K and failure rows.
- `g02_roma`: inlier_count 最小可行 Top-K = `None`；coarse raw 保留 truth 的最小 Top-K = `10`。
- `g03_siftgpu`: inlier_count 最小可行 Top-K = `5`；coarse raw 保留 truth 的最小 Top-K = `10`。

## 策略汇总

| source_group | strategy | truth | best_pose | pnp_ok | reduction | pass |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| g02_roma | coarse_raw_top1 | 3/5 | 0/5 | 5/5 | 0.950 | False |
| g02_roma | coarse_raw_top3 | 4/5 | 3/5 | 5/5 | 0.850 | False |
| g02_roma | coarse_raw_top5 | 4/5 | 4/5 | 5/5 | 0.750 | False |
| g02_roma | coarse_raw_top10 | 5/5 | 5/5 | 5/5 | 0.500 | True |
| g02_roma | coarse_raw_top20 | 5/5 | 5/5 | 5/5 | 0.000 | True |
| g02_roma | rerank_fused_top1 | 4/5 | 1/5 | 5/5 | 0.950 | False |
| g02_roma | rerank_fused_top3 | 4/5 | 1/5 | 5/5 | 0.850 | False |
| g02_roma | rerank_fused_top5 | 5/5 | 1/5 | 5/5 | 0.750 | False |
| g02_roma | inlier_count_top1 | 4/5 | 1/5 | 5/5 | 0.950 | False |
| g02_roma | inlier_count_top3 | 4/5 | 1/5 | 5/5 | 0.850 | False |
| g02_roma | inlier_count_top5 | 5/5 | 1/5 | 5/5 | 0.750 | False |
| g02_roma | match_count_top1 | 4/5 | 1/5 | 5/5 | 0.950 | False |
| g02_roma | match_count_top3 | 4/5 | 1/5 | 5/5 | 0.850 | False |
| g02_roma | match_count_top5 | 5/5 | 1/5 | 5/5 | 0.750 | False |
| g03_siftgpu | coarse_raw_top1 | 3/5 | 0/5 | 4/5 | 0.950 | False |
| g03_siftgpu | coarse_raw_top3 | 4/5 | 3/5 | 5/5 | 0.850 | False |
| g03_siftgpu | coarse_raw_top5 | 4/5 | 4/5 | 5/5 | 0.750 | False |
| g03_siftgpu | coarse_raw_top10 | 5/5 | 5/5 | 5/5 | 0.500 | True |
| g03_siftgpu | coarse_raw_top20 | 5/5 | 5/5 | 5/5 | 0.000 | True |
| g03_siftgpu | rerank_fused_top1 | 5/5 | 3/5 | 5/5 | 0.950 | False |
| g03_siftgpu | rerank_fused_top3 | 5/5 | 4/5 | 5/5 | 0.850 | False |
| g03_siftgpu | rerank_fused_top5 | 5/5 | 5/5 | 5/5 | 0.750 | True |
| g03_siftgpu | inlier_count_top1 | 5/5 | 3/5 | 5/5 | 0.950 | False |
| g03_siftgpu | inlier_count_top3 | 5/5 | 4/5 | 5/5 | 0.850 | False |
| g03_siftgpu | inlier_count_top5 | 5/5 | 5/5 | 5/5 | 0.750 | True |
| g03_siftgpu | match_count_top1 | 5/5 | 5/5 | 5/5 | 0.950 | True |
| g03_siftgpu | match_count_top3 | 5/5 | 5/5 | 5/5 | 0.850 | True |
| g03_siftgpu | match_count_top5 | 5/5 | 5/5 | 5/5 | 0.750 | True |

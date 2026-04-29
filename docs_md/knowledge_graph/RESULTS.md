# Results

This page is a compact index of current formal or decision-relevant results. For the authoritative full list, use [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

## Retrieval Baselines

[[DINOv2]] early four-scale result:

- `R@1=0.125`;
- `R@5=0.275`;
- `R@10=0.375`;
- `MRR=0.193`.

Source: [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

[[coverage truth]] `200/300/500/700m` baseline:

- `coverage R@1=0.200`;
- `coverage R@5=0.400`;
- `coverage R@10=0.475`;
- `coverage MRR=0.290`;
- `Top-1 error mean ~= 759.071m`.

Source: [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

[[strict truth]] re-evaluation:

- `strict R@1=0.175`;
- `strict R@5=0.375`;
- `strict R@10=0.425`;
- `strict MRR=0.262`;
- `Top-1 error mean ~= 759.071m`.

Source: [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

## Query-v2 Geometry Rerank

[[DINOv3]] plus [[FAISS]] on query-v2/intersection-truth route:

- `R@1=0.775`;
- `R@5=0.950`;
- `R@10=1.000`;
- `MRR=0.850`;
- `Top-1 error mean=862.191m`.

[[RoMa v2]] on the same route:

- `R@1=0.925`;
- `R@5=1.000`;
- `R@10=1.000`;
- `MRR=0.958`;
- `Top-1 error mean=630.313m`.

Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).

## Formal Pose and 009010

[[formal pose v1]] full-40:

- `score_row_count=800`;
- PnP status `{ok: 756, pnp_failed: 44}`;
- best pose `{ok: 40}`.

[[satellite DOM SRTM route]]:

- `40/40` best pose;
- layer-2 horizontal error mean `9.723047 m`;
- layer-3 tiepoint XY RMSE `2.771818 m`.

[[CaiWangCun DOM DSM full replacement]]:

- `40/40` best pose;
- PnP candidates `{ok: 781, pnp_failed: 19}`;
- usable-set layer-2 horizontal error mean `1.778006 m`;
- layer-3 tiepoint XY RMSE `0.413562 m`.

Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md), [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

## new4 Gate Matrix

[[G01 baseline]]:

- accepted;
- RoMa rerank `1617.055s`;
- second pose-stage RoMa export `1412.034s`;
- DSM sampling `162.278s`;
- layer-2 mean `2.642712m`;
- layer-3 RMSE `0.504878m`.

[[G02 engineering reuse]]:

- strict acceptance failed;
- second RoMa export removed;
- DOM+Z online sampling `19.643s`;
- precision-equivalence issues remain.

[[G03 SIFTGPU replacement]]:

- accepted on gate;
- SIFTGPU rerank `580.830s`;
- best pose `5/5 ok`;
- PnP candidates `{ok: 39, pnp_failed: 61}`;
- layer-2 mean `2.053060m`;
- layer-3 RMSE `0.417440m`.

[[G04 downsample sweep]]:

- `0.5 m/pix` completed but poor layer-3 RMSE;
- `1.0 m/pix` failed by RoMa timeout/CPU fallback;
- conclusion: naive external downsampling is not useful.

[[G05 pruning posthoc]]:

- no universal Top-1 pruning;
- G03 `match_count_top1` and `inlier_count_top5` deserve follow-up.

[[G06 top1 pose validation]]:

- all subgroups produced `5/5` PnP ok and layer-2 outputs;
- layer-3 validation timed out, so no complete replacement is accepted.

Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).


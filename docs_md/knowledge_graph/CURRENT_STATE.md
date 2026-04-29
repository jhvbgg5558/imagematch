# Current State

## Current Objective

[[current objective]]: verify whether remote-sensing orthophoto imagery can support initial geographic localization of UAV imagery by retrieval.

The active query definition is [[single arbitrary UAV image]]:

- no geographic metadata at runtime;
- not guaranteed to be orthophoto;
- no external resolution normalization unless it is intrinsic to a model pipeline.

Sources: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md), [../EXPERIMENT_PROTOCOL.md](../EXPERIMENT_PROTOCOL.md).

## Active Mainline

The project has moved beyond the initial retrieval-only baseline into a retrieval-plus-geometry localization chain:

- [[DINO retrieval]] provides coarse Top-K candidates.
- [[RoMa v2]] or [[SIFTGPU]] supplies geometric matching or reranking.
- [[DOM DSM PnP]] estimates a pose from 2D-3D correspondences.
- [[validation suite]] evaluates predicted orthophoto alignment, pose-vs-reference geometry, and tiepoint ground error.

The most recent emphasis is the [[new4 speed optimization matrix]], which compares runtime/accuracy tradeoffs on the CaiWangCun gate subset. Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).

## Current Strongest Evidence

- [[CaiWangCun DOM DSM full replacement]] completed a 40-query full run with `40/40` best poses, `781/800` PnP candidates ok, and usable-set layer-2 horizontal error mean `1.778006 m` after excluding `q_037`.
- [[satellite DOM SRTM route]] remains a complete comparison route with `40/40` best poses and layer-3 tiepoint XY RMSE `2.771818 m`.
- The dual-route engineering report records the current comparison: SRTM route layer-2 mean `9.723047 m`; CaiWangCun full replacement usable-set layer-2 mean `1.778006 m`; CaiWangCun layer-3 tiepoint XY RMSE `0.413562 m`.

Sources: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md), [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

## Invalidated Current-Task Assumptions

The following are invalid as current formal basis:

- old same-scale `200m query vs 200m satellite` framing;
- truth defined only by query center point falling in a satellite tile;
- old orthophoto query crops as the evaluation dataset;
- old preprocessing outputs, feature stores, FAISS indexes, and conclusions under `old/`.

Sources: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md), [../DATA_ASSETS.md](../DATA_ASSETS.md), [../EXPERIMENT_PROTOCOL.md](../EXPERIMENT_PROTOCOL.md).

## Latest new4 Status

[[new4 speed optimization matrix]] current branch status:

- [[G01 baseline]]: accepted reference gate run; RoMa rerank `1617.055s`, second pose-stage RoMa export `1412.034s`, DSM sampling `162.278s`, layer-2 mean `2.642712 m`, layer-3 RMSE `0.504878 m`.
- [[G02 engineering reuse]]: removes second RoMa export and uses DOM+Z cache; faster sampling, but strict precision equivalence failed.
- [[G03 SIFTGPU replacement]]: accepted on gate; SIFTGPU rerank `580.830s`, best pose `5/5 ok`, but only `39/100` PnP candidates ok.
- [[G04 downsample sweep]]: naive external downsampling is not useful for current RoMa; `1.0 m/pix` attempt failed by timeout/CPU fallback.
- [[G05 pruning posthoc]]: no universal Top-1 pruning; G03 can justify a follow-up with `match_count_top1` or `inlier_count_top5`.
- [[G06 top1 pose validation]]: Top-1 pose solving is runnable and layer-2 results are available, but layer-3 validation timed out, so it is not accepted as a complete replacement.

Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).


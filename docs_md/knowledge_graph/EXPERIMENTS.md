# Experiments

## new1 Retrieval and Rerank Era

The `new1output/` branches cover the query-v2 retrieval and geometry rerank phase:

- [[DINOv2]] and [[DINOv3]] baselines under `new1output/query_reselect_2026-03-26_v2/`.
- [[RoMa v2]] GPU rerank under `new1output/query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_gpu/`.
- Benefit-boundary analysis under `new1output/benefit_boundary_analysis_2026-03-31/`.

Key conclusion: RoMa v2 improved the DINOv3 baseline on the query-v2/intersection-truth route, with `R@1` rising from `0.775` to `0.925` and MRR from `0.850` to `0.958`. Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).

## new2 Formal Pose v1

[[formal pose v1]] moved the project from retrieval/rerank into pose recovery:

- active root: `new2output/pose_v1_formal/`;
- full `40 x Top-20 = 800` run completed;
- final PnP status `{ok: 756, pnp_failed: 44}`;
- best pose `40/40 ok`.

This branch established the formal `matches -> correspondences -> sampling -> pnp -> scores -> summary` chain. Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md), [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

## 009010 Nadir Route

[[009010 nadir route]] restricts query scope to flights 009 and 010:

- `20` nadir images per route;
- `gimbal_pitch_degree <= -85.0`;
- DINOv2 coarse retrieval plus RoMa v2 rerank determines runtime Top-20 candidates;
- query truth remains offline-only.

This route is the basis for later SRTM, satellite-truth, ODM-refresh, and CaiWangCun replacement comparisons. Source: [../EXPERIMENT_PROTOCOL.md](../EXPERIMENT_PROTOCOL.md).

## Satellite DOM SRTM Route

[[satellite DOM SRTM route]] uses satellite DOM candidates and SRTM DSM in the 009/010 pipeline family.

Recorded comparison metrics:

- `40/40` best pose;
- layer-2 horizontal error mean `9.723047 m`;
- layer-3 tiepoint XY RMSE `2.771818 m`.

Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).

## CaiWangCun DOM DSM Full Replacement

[[CaiWangCun DOM DSM full replacement]] replaces the candidate DOM/DSM source with CaiWangCun branch-local assets:

- full run root: `new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21/`;
- candidate tiles: `149`;
- retrieval Top-20 rows: `800`;
- DSM cache built `119/119`;
- best pose `40/40 ok`;
- PnP candidates `{ok: 781, pnp_failed: 19}`.

Validation highlights:

- layer-1 evaluated `39/40`; `q_037` failed with `dsm_intersection_failed`;
- usable-set frame sanity mean horizontal error `1.778006 m` across `39` queries;
- layer-3 tiepoint XY RMSE `0.413562 m`.

Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md), [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

## new4 Speed Optimization Matrix

[[new4 speed optimization matrix]] is rooted at `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/` and tests speed changes on five gate queries.

See [[CURRENT_STATE]] and [[PIPELINES]] for the current accepted/rejected status of [[G01 baseline]], [[G02 engineering reuse]], [[G03 SIFTGPU replacement]], [[G04 downsample sweep]], [[G05 pruning posthoc]], and [[G06 top1 pose validation]].

Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).


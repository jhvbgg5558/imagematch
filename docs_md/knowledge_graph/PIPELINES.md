# Pipelines

## DINO Retrieval

[[DINO retrieval]] performs coarse candidate recall:

1. Read [[metadata-free query]] images.
2. Extract [[DINOv2]] or [[DINOv3]] global features.
3. Search a [[fixed satellite library]] with [[FAISS]].
4. Export Top-K candidate tables for evaluation or downstream geometry.

Key relation triples:

- [[DINO retrieval]] `uses` [[metadata-free query]].
- [[DINO retrieval]] `uses` [[fixed satellite library]].
- [[DINO retrieval]] `produces` Top-K retrieval CSV outputs.
- [[DINO retrieval]] `evaluates_against` [[strict truth]] or [[intersection truth]] depending on the branch.

Sources: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md), [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

## Geometry Rerank

Geometry rerank takes coarse Top-K candidates and reranks or validates them with image correspondences.

Current geometry methods:

- [[RoMa v2]]: strongest accuracy-oriented matcher, high runtime cost.
- [[LightGlue]]: useful comparison route and visualization source.
- [[SIFTGPU]]: speed-oriented replacement tested in [[G03 SIFTGPU replacement]].

Key relation triples:

- [[RoMa v2]] `uses` DINO Top-K candidates.
- [[RoMa v2]] `produces` reranked candidates and point matches.
- [[SIFTGPU]] `supersedes` neither [[RoMa v2]] nor [[LightGlue]] yet; it is a candidate optimization branch.
- [[G05 pruning posthoc]] `needs_followup` candidate pruning validation.

Sources: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md), [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

## DOM DSM PnP

[[DOM DSM PnP]] turns retrieval candidates into approximate pose estimates:

1. Use query/candidate image matches.
2. Convert DOM pixels to projected planar coordinates.
3. Sample DSM height for 3D points.
4. Build 2D-3D correspondences.
5. Run PnP with RANSAC and refinement.
6. Score candidates and select best pose per query.

Important constraints:

- `query_truth` is offline evaluation only and must not resolve runtime candidate assets.
- v1 does not directly solve PnP on longitude/latitude coordinates.
- DSM sampling failures must be recorded with explicit status codes.

Sources: [../EXPERIMENT_PROTOCOL.md](../EXPERIMENT_PROTOCOL.md), [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).

## Validation Suite

[[validation suite]] checks whether the pose solution is meaningful beyond PnP status:

- layer-1: predicted orthophoto alignment against truth imagery;
- layer-2: pose-vs-reference or frame-sanity geometry;
- layer-3: local tiepoint ground-XY error.

The satellite-truth branch is validation-only and does not change runtime retrieval. ODM-refresh branches intentionally replace evaluation truth orthophoto and/or PnP DSM under isolated roots.

Sources: [../EXPERIMENT_PROTOCOL.md](../EXPERIMENT_PROTOCOL.md), [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

## Speed Optimization Matrix

[[new4 speed optimization matrix]] compares speed/accuracy alternatives on a five-query CaiWangCun gate:

- [[G01 baseline]]: unchanged reference pipeline.
- [[G02 engineering reuse]]: reuse RoMa point matches and DOM+Z cache.
- [[G03 SIFTGPU replacement]]: use SIFTGPU geometry instead of RoMa.
- [[G04 downsample sweep]]: test external downsampling.
- [[G05 pruning posthoc]]: simulate candidate pruning without rerunning pipeline stages.
- [[G06 top1 pose validation]]: run downstream pose from selected Top-1 candidates.

Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).


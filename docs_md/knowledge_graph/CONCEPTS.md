# Concepts

## Query Concepts

[[single arbitrary UAV image]] is the active runtime query unit. It is not assumed to be orthophoto, same-scale, geotagged, or resolution-normalized.

[[metadata-free query]] is the experimental copy used by retrieval pipelines after EXIF/XMP/GPS/DJI metadata removal. Metadata may still exist in offline truth-building inputs but must not enter runtime localization.

Source: [../EXPERIMENT_PROTOCOL.md](../EXPERIMENT_PROTOCOL.md).

## Candidate Concepts

[[fixed satellite library]] is an offline prebuilt candidate library. It must not be constructed per query at runtime from query size or query coordinates.

The current project has used several candidate-library scopes:

- early raw multi-scale libraries under `output/`;
- `200/300/500/700m` coverage-truth library;
- branch-local CaiWangCun DOM/DSM libraries for replacement experiments.

Source: [../DATA_ASSETS.md](../DATA_ASSETS.md).

## Truth Concepts

[[coverage truth]] uses geometric footprint overlap between an approximate query ground footprint and satellite tile footprint.

[[strict truth]] refines coverage truth with valid-content filtering: `coverage_ratio >= 0.4` and `valid_pixel_ratio >= 0.6`.

[[soft truth]] denotes coverage hits whose visual content is insufficient for the main strict truth set.

[[intersection truth]] is the later query-v2 evaluation route used for DINO and geometry-rerank comparisons. It is useful for retrieval evaluation but must remain separate from runtime candidate selection.

Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md), [../EXPERIMENT_PROTOCOL.md](../EXPERIMENT_PROTOCOL.md).

## Method Concepts

[[DINO retrieval]] is the global-feature retrieval stage, using [[DINOv2]] or [[DINOv3]] features and [[FAISS]] inner-product search.

[[RoMa v2]] is the strongest current dense geometric matching/reranking component for the main retrieval-plus-pose route, but runtime cost is high.

[[LightGlue]] is a SuperPoint/LightGlue/RANSAC reranking line used for comparison and visualization; it improved some top-k behavior but did not become the current strongest route.

[[SIFTGPU]] is the speed-oriented geometry replacement tested in [[G03 SIFTGPU replacement]]. It is faster than RoMa on the gate subset but has weaker candidate-level PnP robustness.

Sources: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md), [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

## Pose Concepts

[[DOM DSM PnP]] maps DOM pixels to projected world coordinates, samples DSM heights, builds 2D-3D correspondences, and solves PnP.

[[formal pose v1]] is the active formal pose pipeline family. Its v1 assumptions include approximate intrinsics, no lens distortion correction, bilinear DSM sampling, and fixed PnP/RANSAC settings.

[[validation suite]] includes orthophoto alignment, pose-vs-reference geometry, and local tiepoint ground-XY error branches.

Source: [../EXPERIMENT_PROTOCOL.md](../EXPERIMENT_PROTOCOL.md).


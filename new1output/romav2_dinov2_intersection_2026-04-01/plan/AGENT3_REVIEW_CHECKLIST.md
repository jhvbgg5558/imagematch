# Agent 3 Review Checklist

Use this checklist before treating any new output in this bundle as valid.

## Path Safety

- confirm every new file stays under
  `D:\aiproject\imagematch\new1output\romav2_dinov2_intersection_2026-04-01`
- confirm no script writes into
  `new1output/query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_gpu`

## Input Consistency

- confirm the wrapper still uses the locked `query v2` DINOv2 feature NPZ
- confirm the FAISS index and `tiles.csv` come from the DINOv2 baseline assets
- confirm the mapping JSON is the `query v2` mapping already checked against
  the baseline index

## Naming and Reporting

- confirm the coarse label is `DINOv2` in commands, reports, and configs
- confirm no report reuses `DINOv3` wording from the older RoMa v2 round

## Assumptions and Thresholds

- confirm RoMa v2 thresholds stay explicit in the launcher config
- confirm the wrapper does not add extra resolution normalization
- confirm visualization is described as post-processing only and does not alter
  the formal rerank CSV or JSON outputs

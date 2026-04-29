# Open Questions

## Retrieval and Rerank

- Determine whether [[SIFTGPU]] can become a complete replacement for [[RoMa v2]] after match-density or coverage filtering improves candidate-level PnP robustness.
- Validate whether G03 `match_count_top1` or `inlier_count_top5` can preserve full validation, including layer-3, not only layer-2.
- Avoid claiming that Top-20 retrieval can be skipped until pruning is tested with a complete rerun and full validation.

Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).

## Pose and Validation

- Investigate why [[G06 top1 pose validation]] times out during layer-3 tiepoint evaluation.
- Treat `q_037` in [[CaiWangCun DOM DSM full replacement]] as a validation-missing or DSM-intersection failure case, not as proof of general pose collapse.
- Continue separating runtime candidate selection from offline truth and audit fields.

Source: [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md), [../EXPERIMENT_PROTOCOL.md](../EXPERIMENT_PROTOCOL.md).

## Asset and Protocol Hygiene

- Keep `old/` as historical reference only.
- Keep branch-local CaiWangCun assets isolated from satellite DOM/SRTM branches.
- Document any future move from Markdown wiki to `nodes.csv` / `edges.csv` export in [[SCHEMA]] before introducing graph-database artifacts.

Source: [../DATA_ASSETS.md](../DATA_ASSETS.md).

## Knowledge Graph Maintenance

- Run a link/lint pass whenever new wiki links are added.
- Reconcile [[CURRENT_STATE]], [[RESULTS]], and [[EXPERIMENTS]] after each new formal result.
- Prefer adding source-backed facts over narrative summaries when updating this wiki.


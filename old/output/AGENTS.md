# output Agent Instructions

This directory stores both formal result sets and historical exploration outputs.

## Formal Result Chain

The current formal result directories are:

- `validation_200m_same_scale`
- `validation_200m_same_scale_sift_gate3`
- `validation_200m_same_scale_lightglue_superpoint_fused_top10_k256`

When discussing the current official conclusion, use these directories unless the user explicitly asks for historical comparisons.

## Historical Exploration

Directories such as the following are historical or exploratory by default:

- `validation_round2`
- `validation_round3_200m_fair`
- `validation_round3_200m_fair_geom_sift`
- `validation_round3_200m_fair_geom_sift_round2_gate3`
- `validation_round3_200m_strict`
- `validation_200m_same_scale_lightglue_superpoint_gate3_top5_k64`
- `lightglue_pilot_012_q05_top3`

Do not promote these to formal conclusions without explicit user intent.

## Naming Rule For New Results

New result directories should make method and protocol obvious. Include, where relevant:

- query scale
- satellite scale
- method
- key variant

Examples:

- `validation_200m_same_scale_sift_gate3`
- `validation_200m_same_scale_lightglue_superpoint_fused_top10_k256`

## Documentation Sync Rule

If you add a new formal result directory, also update:

- `../docs_md/RESULTS_INDEX.md`
- `../docs_md/PROJECT_PROGRESS.md`

If the new result changes the best known method, update:

- `../docs_md/PROJECT_PROGRESS.md`


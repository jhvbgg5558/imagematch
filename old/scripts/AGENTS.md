# scripts Agent Instructions

This directory contains the executable experiment pipeline and reporting scripts.

## Before Editing

Read:

- `../docs_md/PROJECT_PROGRESS.md`
- `../docs_md/EXPERIMENT_PROTOCOL.md`
- `../docs_md/CODE_STYLE.md`

Do not modify scripts under assumptions that conflict with the formal same-scale protocol unless the user explicitly asks for a new exploratory branch.

## File Header Requirement

For every new script, and for any script that is significantly refactored, add a short module-level description at the top of the file.

That description should state:

- what the file does
- main inputs
- main outputs
- whether it serves the formal strict same-scale workflow or only historical exploration

For formal-result scripts, explicitly say they apply to:

- `200m query vs 200m satellite`
- truth defined by query-center-in-tile

## Script Naming

Prefer names that reflect:

- action
- method
- protocol or scale context

Good pattern examples:

- `prepare_200m_same_scale_experiment.py`
- `run_lightglue_rerank_round.py`
- `generate_same_scale_comparison_report.py`

## Separation Rule

Avoid mixing formal-result logic and historical-exploration logic in one script unless there is a strong reason and the distinction is documented clearly at the file top.

If a script is historical only, say so explicitly in the file header.


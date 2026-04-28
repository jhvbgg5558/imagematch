# docs_md Agent Instructions

This directory stores the project's stable Markdown knowledge base plus the frequently updated progress file.

## Read Order

When your task depends on current project state, read in this order:

1. `README.md`
2. `PROJECT_PROGRESS.md`
3. `EXPERIMENT_PROTOCOL.md`
4. `DATA_ASSETS.md`
5. `RESULTS_INDEX.md`
6. `CODE_STYLE.md`

## Current-State Rule

`PROJECT_PROGRESS.md` is intentionally updated frequently.

Rules:

- Re-read `PROJECT_PROGRESS.md` at the start of each new task
- Do not assume a previously read copy is still current
- If your work changes project status, best method, or next actions, update `PROJECT_PROGRESS.md`

## File Roles

- `README.md`: top-level entry into the Markdown docs
- `PROJECT_PROGRESS.md`: current state and handoff status
- `DATA_ASSETS.md`: fast data reference and asset navigation
- `EXPERIMENT_PROTOCOL.md`: formal evaluation definition
- `RESULTS_INDEX.md`: output directory map
- `CODE_STYLE.md`: coding and readability rules

## Update Rules

If the formal experiment protocol changes:

- update `EXPERIMENT_PROTOCOL.md`
- update `PROJECT_PROGRESS.md`
- update `RESULTS_INDEX.md` if result entrypoints change

If a new formal result directory is introduced:

- update `RESULTS_INDEX.md`
- update `PROJECT_PROGRESS.md`

If the best current method changes:

- update `PROJECT_PROGRESS.md`
- ensure references in `README.md` still point to the right primary result chain


# imagematch Agent Instructions

## Start Here

When entering this project, read these files in order before doing substantive work:

1. `docs_md/README.md`
2. `docs_md/PROJECT_PROGRESS.md`
3. `docs_md/EXPERIMENT_PROTOCOL.md`

Do not assume earlier chat memory or earlier project conclusions still apply.

## Current Task Scope

The project has been reset to a new task definition:

- objective remains: verify whether remote-sensing orthophoto imagery can support initial geographic localization of UAV imagery by retrieval
- query input is now a single arbitrary UAV image
- the query image has no geographic metadata
- the query image is not guaranteed to be orthophoto
- do not apply external resolution normalization unless it is intrinsic to the model pipeline

## Old Material

All previous task assets have been archived under `old/`.

Rules:

- treat `old/` as historical reference only
- do not use previous scripts, outputs, preprocessing products, or conclusions as the current formal basis
- previous same-scale preprocessing results are considered invalid for the new task unless explicitly revalidated

## Mandatory Progress Refresh

`docs_md/PROJECT_PROGRESS.md` is the current-state source of truth.

Rules:

- at the start of every new task, re-read `docs_md/PROJECT_PROGRESS.md`
- if current status, assumptions, valid data assets, or next steps change, update the Markdown docs

## Documentation Rules

Use the Markdown docs under `docs_md/` as the active knowledge base:

- `README.md`: documentation entry
- `PROJECT_PROGRESS.md`: current status
- `DATA_ASSETS.md`: current valid data status
- `EXPERIMENT_PROTOCOL.md`: current task constraints and evaluation assumptions
- `RESULTS_INDEX.md`: current valid outputs
- `CODE_STYLE.md`: coding rules

If new scripts, datasets, outputs, or formal conclusions are introduced, update the relevant Markdown docs.

## Code Rules

Before editing or adding scripts, read `docs_md/CODE_STYLE.md`.

In particular:

- new or heavily modified code files should start with a short file-level description
- the description should explain purpose, main inputs, main outputs, and applicable task constraints
- if a script depends on assumptions about image geometry, metadata, or resolution handling, state them explicitly

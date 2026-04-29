# Knowledge Graph Schema

This schema constrains the Markdown knowledge graph. It is intentionally lightweight so the wiki remains readable in plain Markdown and usable in Obsidian-style graph views.

## Node Types

- `Objective`: the project-level question or sub-question being tested.
- `Constraint`: a rule that limits valid inputs, preprocessing, assets, or interpretation.
- `Asset`: a concrete data or model artifact.
- `Dataset`: a grouped data collection used by an experiment.
- `Protocol`: an evaluation or runtime contract.
- `Pipeline`: a multi-stage execution chain.
- `Method`: an algorithm or model component.
- `Experiment`: a bounded run or branch with fixed inputs and outputs.
- `Metric`: a reported measurement.
- `Result`: an output table, JSON, figure set, report, or summary.
- `Conclusion`: an interpretation supported by current formal evidence.
- `Risk`: a known failure mode, ambiguity, or unresolved boundary.
- `Script`: a project script used as an entrypoint or helper.
- `OutputRoot`: a directory that contains experiment outputs.

## Relation Types

- `uses`: node A consumes node B.
- `produces`: node A writes node B.
- `evaluates_against`: method or experiment A is evaluated against truth/protocol B.
- `supersedes`: node A replaces node B as the preferred current reference.
- `invalidates`: node A makes node B unsuitable as current evidence.
- `depends_on`: node A requires node B.
- `supports`: evidence A supports conclusion B.
- `contradicts`: evidence A conflicts with claim B.
- `stored_at`: node A is located at path B.
- `implemented_by`: pipeline or method A is implemented by script B.
- `needs_followup`: node A requires future analysis B.

## Naming Rules

- Use stable English names for wiki links, even when the surrounding prose is Chinese.
- Use exact casing for method links: [[DINOv2]], [[DINOv3]], [[RoMa v2]], [[LightGlue]], [[SIFTGPU]].
- Use compact branch names for experiments: [[009010 nadir route]], [[CaiWangCun DOM DSM full replacement]], [[new4 speed optimization matrix]].
- Use path literals for real directories and files, for example `new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21/`.
- Do not create a link for every script filename; link only scripts that define an entrypoint or contract.

## Evidence Rules

- Every metric must cite a source document or output root.
- Every active asset must cite [../DATA_ASSETS.md](../DATA_ASSETS.md) or [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).
- Every formal result must cite [../RESULTS_INDEX.md](../RESULTS_INDEX.md) or the result root recorded there.
- Every protocol constraint must cite [../EXPERIMENT_PROTOCOL.md](../EXPERIMENT_PROTOCOL.md).
- Claims based on `old/` are allowed only as historical context and must be marked invalidated for current use.

## Link Inventory

The following entity links are intentionally used across the wiki and should remain defined here or in the relevant page:

- [[current objective]]
- [[single arbitrary UAV image]]
- [[metadata-free query]]
- [[fixed satellite library]]
- [[coverage truth]]
- [[strict truth]]
- [[intersection truth]]
- [[soft truth]]
- [[DINO retrieval]]
- [[DINOv2]]
- [[DINOv3]]
- [[FAISS]]
- [[RoMa v2]]
- [[LightGlue]]
- [[SIFTGPU]]
- [[DOM DSM PnP]]
- [[formal pose v1]]
- [[validation suite]]
- [[009010 nadir route]]
- [[satellite DOM SRTM route]]
- [[CaiWangCun DOM DSM full replacement]]
- [[new4 speed optimization matrix]]
- [[G01 baseline]]
- [[G02 engineering reuse]]
- [[G03 SIFTGPU replacement]]
- [[G04 downsample sweep]]
- [[G05 pruning posthoc]]
- [[G06 top1 pose validation]]


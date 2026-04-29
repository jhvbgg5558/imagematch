# imagematch Knowledge Graph Wiki

This directory is the maintained knowledge layer for the imagematch project. It follows the Karpathy-style LLM Wiki pattern: source documents stay untouched, while this wiki compiles project knowledge into stable, linked Markdown pages.

Primary source-of-truth documents remain:

- [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md)
- [../EXPERIMENT_PROTOCOL.md](../EXPERIMENT_PROTOCOL.md)
- [../DATA_ASSETS.md](../DATA_ASSETS.md)
- [../RESULTS_INDEX.md](../RESULTS_INDEX.md)

This wiki is an index and synthesis layer, not a new experimental result source.

## Reading Path

1. Read [[CURRENT_STATE]] for the current project objective, active scope, invalidated assumptions, and latest status.
2. Read [[CONCEPTS]] for the vocabulary used across retrieval, truth construction, geometry reranking, and pose validation.
3. Read [[PIPELINES]] to understand how [[DINO retrieval]], [[RoMa v2]], [[DOM DSM PnP]], and validation stages connect.
4. Read [[EXPERIMENTS]] for the major experiment branches from `new1output/` through `new4output/`.
5. Read [[ASSETS]] and [[RESULTS]] before citing any dataset, output root, metric, or conclusion.
6. Read [[OPEN_QUESTIONS]] before starting a new experiment or optimization pass.

## Maintenance Rules

- Treat `docs_md/*.md` as the current source layer and this directory as the compiled working layer.
- Keep source citations on important claims, especially metrics, active roots, invalidated assets, and protocol constraints.
- Mark any historical material from `old/` as `historical` or `invalidated`; do not promote it into current evidence.
- Update this wiki after meaningful changes to project status, active assets, formal results, or experimental conclusions.
- Prefer explicit links such as [[strict truth]], [[CaiWangCun DOM DSM full replacement]], and [[new4 speed optimization matrix]] over repeating long explanations.

## Wiki Pages

- [[SCHEMA]] defines node types, relation types, naming, and evidence rules.
- [[CURRENT_STATE]] summarizes the active project state.
- [[CONCEPTS]] defines reusable entities.
- [[PIPELINES]] maps execution and evaluation flow.
- [[EXPERIMENTS]] organizes major experiment branches.
- [[ASSETS]] records valid, historical, and forbidden asset use.
- [[RESULTS]] records current formal metrics and output roots.
- [[OPEN_QUESTIONS]] tracks risks and next decisions.

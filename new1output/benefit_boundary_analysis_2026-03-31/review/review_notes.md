# Review Notes

## Scope
- Review target: `new1output/benefit_boundary_analysis_2026-03-31`
- Main data source locked to `new1output/query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_gpu/coarse/retrieval_top20.csv`
- Main analysis scope: `query v2 + intersection truth`

## Checks
- `40/40` queries are present in `tables/per_query_boundary_analysis.csv`.
- `40/40` query ids are unique; no duplicate rows were found.
- Main buckets are mutually exclusive and complete: `A=31`, `B=6`, `C=3`, `D=0`.
- `C_retained + C_drop_out == C_total` holds: `3 + 0 = 3`.
- All current C samples are `C_retained`; no `C_drop_out` samples were generated in this round.
- Supplementary table A is consistent with overall `delta R@1`: `B` contributes `6` direct new Top-1 hits, matching the observed total gain of `6`.
- `D=0`, so this round contains no coarse Top-20 miss cases; there is no D-sample NA path to validate in the generated table.
- Table and figure inventory matches the implementation plan.

## Findings
- The generated outputs are internally consistent with the locked bucket rules.
- The current batch does not expose the D boundary. This is a data/result fact, not a pipeline bug.
- The most important interpretation risk is overclaiming geometric success from error reduction alone. The current tables avoid that by tying success to truth-rank transitions, not error deltas.

## Follow-Up Notes
- `cases/cd_failure_labels.csv` is initialized only for the `C` bucket because `D` is absent in this round.
- `cases/representative_cases.csv` therefore contains A/B/C exemplars only. This is expected under the observed bucket distribution.
- If a later round produces `D > 0`, rerun the same script to populate D-case and D-label rows without changing the bucket logic.

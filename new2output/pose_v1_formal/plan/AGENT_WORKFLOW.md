# Formal Pose v1 Agent Workflow

## Agent1
- Role: progress supervision and gate inspection.
- Read-only scope: `D:\aiproject\imagematch\new2output\pose_v1_formal\`
- Check directories: `dsm_cache/rasters`, `matches`, `correspondences`, `sampling`, `pnp`, `scores`, `summary`
- Output focus: stage completeness, missing artifacts, failure distributions, gate recommendation.

## Agent2
- Role: implementation.
- Write scope: `D:\aiproject\imagematch\scripts\` and formal bundle documentation/output helpers.
- Current responsibilities:
  - build candidate DSM rasters from raw HGT
  - enforce `candidate_id -> dsm_id -> raster_path`
  - generate `scores/pose_scores.csv`
  - generate `summary/per_query_best_pose.csv`
  - maintain `summary/pose_overall_summary.json`

## Agent3
- Role: code review and protocol audit.
- Review focus:
  - candidate-to-DSM binding correctness
  - CRS / affine consistency
  - distinction between asset-missing failures and geometric failures
  - no runtime dependence on `query_truth`

## Phase Gate
- Run `D:\aiproject\imagematch\scripts\run_formal_pose_phase_gate.py`
- Default gate size: 5 queries, selected across flights first
- Gate artifact: `D:\aiproject\imagematch\new2output\pose_v1_formal\summary\phase_gate_summary.json`

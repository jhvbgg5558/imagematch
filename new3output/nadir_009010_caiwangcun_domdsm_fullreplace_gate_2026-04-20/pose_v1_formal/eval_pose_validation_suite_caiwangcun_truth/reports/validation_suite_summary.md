# Validation Suite Summary

- phase: `gate`
- ortho_alignment: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/ortho_alignment`
- pose_vs_at: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/pose_vs_at`
- tiepoint_ground_error: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/tiepoint_ground_error`

## Main Metrics
- phase_corr_error_m: mean=0.11067659999999999, median=0.115509, p90=0.1490784
- horizontal_error_m: mean=1.8294804, median=1.655618, p90=3.2771866000000003
- view_dir_angle_error_deg: mean=0.2725336, median=0.237585, p90=0.49501760000000006
- tiepoint_xy_error_rmse_m: 0.32361956895217237
- tiepoint_xy_error_p90_m: 0.491323

## Interpretation
- orthophoto alignment remains the primary validation layer.
- pose_vs_at provides relative camera-parameter deltas to the ODM/AT reference.
- tiepoint ground error measures local object-space XY consistency on truth vs pred orthophotos.

## Raw Files
- `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/validation_manifest.json`
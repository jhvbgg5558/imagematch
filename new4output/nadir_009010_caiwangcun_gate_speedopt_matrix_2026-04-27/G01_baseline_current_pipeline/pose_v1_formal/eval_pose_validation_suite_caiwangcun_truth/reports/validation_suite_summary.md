# Validation Suite Summary

- phase: `gate`
- ortho_alignment: `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G01_baseline_current_pipeline/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/ortho_alignment`
- pose_vs_at: `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G01_baseline_current_pipeline/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/pose_vs_at`
- tiepoint_ground_error: `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G01_baseline_current_pipeline/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/tiepoint_ground_error`

## Main Metrics
- phase_corr_error_m: mean=0.09283319999999999, median=0.087474, p90=0.1366214
- horizontal_error_m: mean=2.6427123999999997, median=1.869604, p90=4.4005612
- view_dir_angle_error_deg: mean=0.7632171999999999, median=0.692459, p90=1.1234190000000002
- tiepoint_xy_error_rmse_m: 0.504877910385769
- tiepoint_xy_error_p90_m: 0.878624

## Interpretation
- orthophoto alignment remains the primary validation layer.
- pose_vs_at provides relative camera-parameter deltas to the ODM/AT reference.
- tiepoint ground error measures local object-space XY consistency on truth vs pred orthophotos.

## Raw Files
- `new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G01_baseline_current_pipeline/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/validation_manifest.json`
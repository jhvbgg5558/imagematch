# Validation Suite Summary

- phase: `full`
- ortho_alignment: `new2output/pose_v1_formal/eval_pose_validation_suite/ortho_alignment`
- pose_vs_at: `new2output/pose_v1_formal/eval_pose_validation_suite/pose_vs_at`
- tiepoint_ground_error: `new2output/pose_v1_formal/eval_pose_validation_suite/tiepoint_ground_error`

## Main Metrics
- phase_corr_error_m: mean=0.24966253846153846, median=0.246769, p90=0.43891360000000007
- horizontal_error_m: mean=40.67180965, median=4.6051475, p90=16.585374200000004
- view_dir_angle_error_deg: mean=2.0945009, median=0.5647074999999999, p90=1.8028320000000002
- tiepoint_xy_error_rmse_m: 5.466257034089889
- tiepoint_xy_error_p90_m: 8.229046

## Interpretation
- orthophoto alignment remains the primary validation layer.
- pose_vs_at provides relative camera-parameter deltas to the ODM/AT reference.
- tiepoint ground error measures local object-space XY consistency on truth vs pred orthophotos.

## Raw Files
- `new2output/pose_v1_formal/eval_pose_validation_suite/validation_manifest.json`
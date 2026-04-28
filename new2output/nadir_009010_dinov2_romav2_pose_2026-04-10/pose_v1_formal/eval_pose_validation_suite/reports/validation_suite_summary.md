# Validation Suite Summary

- phase: `full`
- ortho_alignment: `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/pose_v1_formal/eval_pose_validation_suite/ortho_alignment`
- pose_vs_at: `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/pose_v1_formal/eval_pose_validation_suite/pose_vs_at`
- tiepoint_ground_error: `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/pose_v1_formal/eval_pose_validation_suite/tiepoint_ground_error`

## Main Metrics
- phase_corr_error_m: mean=0.76722425, median=0.431705, p90=2.0462238000000004
- horizontal_error_m: mean=9.165404375, median=7.675858, p90=16.2846947
- view_dir_angle_error_deg: mean=1.270628625, median=1.0893345, p90=2.3670427
- tiepoint_xy_error_rmse_m: 2.855162565766651
- tiepoint_xy_error_p90_m: 4.3476348

## Interpretation
- orthophoto alignment remains the primary validation layer.
- pose_vs_at provides relative camera-parameter deltas to the ODM/AT reference.
- tiepoint ground error measures local object-space XY consistency on truth vs pred orthophotos.

## Raw Files
- `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/pose_v1_formal/eval_pose_validation_suite/validation_manifest.json`
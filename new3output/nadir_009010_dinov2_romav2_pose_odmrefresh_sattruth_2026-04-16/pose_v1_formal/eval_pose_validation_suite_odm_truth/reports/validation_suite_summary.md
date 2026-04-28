# Validation Suite Summary

- phase: `full`
- ortho_alignment: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16/pose_v1_formal/eval_pose_validation_suite_odm_truth/ortho_alignment`
- pose_vs_at: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16/pose_v1_formal/eval_pose_validation_suite_odm_truth/pose_vs_at`
- tiepoint_ground_error: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16/pose_v1_formal/eval_pose_validation_suite_odm_truth/tiepoint_ground_error`

## Main Metrics
- phase_corr_error_m: mean=0.27883455, median=0.2657525, p90=0.3352692
- horizontal_error_m: mean=6.66892575, median=4.557033499999999, p90=13.857612300000001
- view_dir_angle_error_deg: mean=0.8335707750000001, median=0.5720354999999999, p90=1.5756065000000001
- tiepoint_xy_error_rmse_m: 2.3426778627448535
- tiepoint_xy_error_p90_m: 3.260369600000001

## Interpretation
- orthophoto alignment remains the primary validation layer.
- pose_vs_at provides relative camera-parameter deltas to the ODM/AT reference.
- tiepoint ground error measures local object-space XY consistency on truth vs pred orthophotos.

## Raw Files
- `/mnt/d/aiproject/imagematch/new3output/nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16/pose_v1_formal/eval_pose_validation_suite_odm_truth/validation_manifest.json`
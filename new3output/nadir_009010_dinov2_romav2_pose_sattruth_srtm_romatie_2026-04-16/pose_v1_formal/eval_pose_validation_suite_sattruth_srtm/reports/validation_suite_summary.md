# Validation Suite Summary

- phase: `full`
- ortho_alignment: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16/pose_v1_formal/eval_pose_validation_suite_sattruth_srtm/ortho_alignment`
- pose_vs_at: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16/pose_v1_formal/eval_pose_validation_suite_sattruth_srtm/pose_vs_at`
- tiepoint_ground_error: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16/pose_v1_formal/eval_pose_validation_suite_sattruth_srtm/tiepoint_ground_error`

## Main Metrics
- phase_corr_error_m: mean=0.19185705, median=0.1568705, p90=0.3324795000000001
- horizontal_error_m: mean=9.723047025, median=8.1839695, p90=20.3670903
- view_dir_angle_error_deg: mean=1.347146875, median=1.0536020000000001, p90=2.916163
- tiepoint_xy_error_rmse_m: 2.771817773524779
- tiepoint_xy_error_p90_m: 4.414854900000011

## Interpretation
- orthophoto alignment remains the primary validation layer.
- pose_vs_at provides relative camera-parameter deltas to the ODM/AT reference.
- tiepoint ground error measures local object-space XY consistency on truth vs pred orthophotos.

## Raw Files
- `/mnt/d/aiproject/imagematch/new3output/nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16/pose_v1_formal/eval_pose_validation_suite_sattruth_srtm/validation_manifest.json`
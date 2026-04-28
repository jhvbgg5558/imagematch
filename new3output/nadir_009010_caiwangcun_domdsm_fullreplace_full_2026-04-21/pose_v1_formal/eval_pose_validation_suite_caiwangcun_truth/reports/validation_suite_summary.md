# Validation Suite Summary

- phase: `full`
- ortho_alignment: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/ortho_alignment`
- pose_vs_at: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/pose_vs_at`
- tiepoint_ground_error: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/tiepoint_ground_error`

## Main Metrics
- phase_corr_error_m: mean=0.12022566666666666, median=0.125055, p90=0.17351980000000003
- horizontal_error_m: mean=22.964179425, median=1.4296164999999998, p90=3.6529626
- view_dir_angle_error_deg: mean=2.027666525, median=0.19312200000000002, p90=0.48959100000000005
- tiepoint_xy_error_rmse_m: 0.4135621201364927
- tiepoint_xy_error_p90_m: 0.5856026

## Interpretation
- orthophoto alignment remains the primary validation layer.
- pose_vs_at provides relative camera-parameter deltas to the ODM/AT reference.
- tiepoint ground error measures local object-space XY consistency on truth vs pred orthophotos.

## Raw Files
- `/mnt/d/aiproject/imagematch/new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/validation_manifest.json`
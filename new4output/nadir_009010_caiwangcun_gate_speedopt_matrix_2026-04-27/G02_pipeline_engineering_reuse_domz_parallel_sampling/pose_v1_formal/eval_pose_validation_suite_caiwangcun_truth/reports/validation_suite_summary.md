# Validation Suite Summary

- phase: `gate`
- ortho_alignment: `/mnt/d/aiproject/imagematch/new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G02_pipeline_engineering_reuse_domz_parallel_sampling/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/ortho_alignment`
- pose_vs_at: `/mnt/d/aiproject/imagematch/new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G02_pipeline_engineering_reuse_domz_parallel_sampling/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/pose_vs_at`
- tiepoint_ground_error: `/mnt/d/aiproject/imagematch/new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G02_pipeline_engineering_reuse_domz_parallel_sampling/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/tiepoint_ground_error`

## Main Metrics
- phase_corr_error_m: mean=0.0986224, median=0.128452, p90=0.138214
- horizontal_error_m: mean=2.0727066, median=1.519454, p90=3.1659574000000004
- view_dir_angle_error_deg: mean=0.783442, median=0.750498, p90=1.273301
- tiepoint_xy_error_rmse_m: 0.4988889635121927
- tiepoint_xy_error_p90_m: 0.63907

## Interpretation
- orthophoto alignment remains the primary validation layer.
- pose_vs_at provides relative camera-parameter deltas to the ODM/AT reference.
- tiepoint ground error measures local object-space XY consistency on truth vs pred orthophotos.

## Raw Files
- `/mnt/d/aiproject/imagematch/new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G02_pipeline_engineering_reuse_domz_parallel_sampling/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/validation_manifest.json`
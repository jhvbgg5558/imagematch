# Validation Suite Summary

- phase: `gate`
- ortho_alignment: `/mnt/d/aiproject/imagematch/new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G03_pipeline_siftgpu_replace_roma/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/ortho_alignment`
- pose_vs_at: `/mnt/d/aiproject/imagematch/new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G03_pipeline_siftgpu_replace_roma/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/pose_vs_at`
- tiepoint_ground_error: `/mnt/d/aiproject/imagematch/new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G03_pipeline_siftgpu_replace_roma/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/tiepoint_ground_error`

## Main Metrics
- phase_corr_error_m: mean=0.0971436, median=0.084981, p90=0.1429326
- horizontal_error_m: mean=2.0530604, median=2.029462, p90=3.5301476000000003
- view_dir_angle_error_deg: mean=0.7935589999999999, median=0.693453, p90=1.4031044000000001
- tiepoint_xy_error_rmse_m: 0.41744002475044845
- tiepoint_xy_error_p90_m: 0.6517212

## Interpretation
- orthophoto alignment remains the primary validation layer.
- pose_vs_at provides relative camera-parameter deltas to the ODM/AT reference.
- tiepoint ground error measures local object-space XY consistency on truth vs pred orthophotos.

## Raw Files
- `/mnt/d/aiproject/imagematch/new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G03_pipeline_siftgpu_replace_roma/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/validation_manifest.json`
# Validation Suite Summary

- phase: `gate`
- ortho_alignment: `/mnt/d/aiproject/imagematch/new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G04_downsample_resolution_sweep/G04A_downsample_0p5m/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/ortho_alignment`
- pose_vs_at: `/mnt/d/aiproject/imagematch/new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G04_downsample_resolution_sweep/G04A_downsample_0p5m/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/pose_vs_at`
- tiepoint_ground_error: `/mnt/d/aiproject/imagematch/new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G04_downsample_resolution_sweep/G04A_downsample_0p5m/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/tiepoint_ground_error`

## Main Metrics
- phase_corr_error_m: mean=0.0240582, median=0.021356, p90=0.0412304
- horizontal_error_m: mean=6.0390186, median=6.895263, p90=7.3485038000000005
- view_dir_angle_error_deg: mean=0.956213, median=0.908112, p90=1.2430568
- tiepoint_xy_error_rmse_m: 441.89850627736695
- tiepoint_xy_error_p90_m: 527.935476

## Interpretation
- orthophoto alignment remains the primary validation layer.
- pose_vs_at provides relative camera-parameter deltas to the ODM/AT reference.
- tiepoint ground error measures local object-space XY consistency on truth vs pred orthophotos.

## Raw Files
- `/mnt/d/aiproject/imagematch/new4output/nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27/G04_downsample_resolution_sweep/G04A_downsample_0p5m/pose_v1_formal/eval_pose_validation_suite_caiwangcun_truth/validation_manifest.json`
# Pose Validation Suite Summary

- phase: `gate`
- query_count: `5`
- selected_query_ids: `q_010, q_015, q_022, q_002, q_039`
- failed_steps: `crop_query_ortho_truth_tiles, render_query_predicted_ortho_from_pose, evaluate_pose_ortho_alignment, render_pose_ortho_overlay_viz, build_query_reference_pose_manifest, evaluate_pose_against_reference_pose, evaluate_pose_ortho_tiepoint_ground_error, render_pose_ortho_tiepoint_viz`

## Layer 1: Ortho Alignment
- phase_corr_error_m mean: `n/a`
- phase_corr_error_m p90: `n/a`
- ortho_iou mean: `n/a`
- ssim mean: `n/a`

## Layer 2: Pose vs AT
- horizontal_error_m mean: `n/a`
- spatial_error_m mean: `n/a`
- view_dir_angle_error_deg mean: `n/a`

## Layer 3: Tie-Point Ground Error
- tiepoint_xy_error_rmse_m mean: `n/a`
- tiepoint_xy_error_p90_m mean: `n/a`
- tiepoint_match_count_mean: `n/a`

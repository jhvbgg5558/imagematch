# ODM Truth vs Satellite Truth Comparison

## Scope

- Baseline root: `/mnt/d/aiproject/imagematch/new2output/nadir_009010_dinov2_romav2_pose_2026-04-10`
- Current experiment root: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_dinov2_romav2_pose_odmrefresh_sattruth_2026-04-16`
- Runtime retrieval and candidate DOM library remained fixed to the satellite library.
- Main variable changes were: ODM orthophoto truth replacement, ODM-derived DSM replacement, and an additional satellite-truth validation view.

## Pose Runtime

- Baseline PnP rows: `800`, status counts: `{'ok': 734, 'pnp_failed': 66}`
- Current PnP rows: `800`, status counts: `{'ok': 520, 'dsm_nodata_too_high': 217, 'pnp_failed': 61, 'dsm_coverage_insufficient': 2}`
- Baseline best-pose rows: `40`, status counts: `{'ok': 40}`
- Current best-pose rows: `40`, status counts: `{'ok': 40}`

## Validation Summary

| Suite | Metric | Value |
| --- | --- | --- |
| baseline_uav_truth | layer1 phase_corr_error_m mean | - |
| baseline_uav_truth | layer1 ortho_iou mean | - |
| baseline_uav_truth | layer1 ssim mean | - |
| baseline_uav_truth | layer2 horizontal_error_m mean | - |
| baseline_uav_truth | layer2 view_dir_angle_error_deg mean | - |
| baseline_uav_truth | layer3 tiepoint_xy_error_rmse_m | 2.8552 |
| baseline_uav_truth | layer3 tiepoint_xy_error_p90_m | 4.3476 |
| odm_truth_refresh | layer1 phase_corr_error_m mean | - |
| odm_truth_refresh | layer1 ortho_iou mean | - |
| odm_truth_refresh | layer1 ssim mean | - |
| odm_truth_refresh | layer2 horizontal_error_m mean | - |
| odm_truth_refresh | layer2 view_dir_angle_error_deg mean | - |
| odm_truth_refresh | layer3 tiepoint_xy_error_rmse_m | 2.3427 |
| odm_truth_refresh | layer3 tiepoint_xy_error_p90_m | 3.2604 |
| satellite_truth | layer1 phase_corr_error_m mean | - |
| satellite_truth | layer1 ssim mean | - |
| satellite_truth | layer2 truth_patch_center_offset_m mean | - |
| satellite_truth | layer2 truth_covering_tile_rank mean | - |
| satellite_truth | layer3 tiepoint_xy_error_rmse_m | 181.3715 |
| satellite_truth | layer3 tiepoint_xy_error_p90_m | 320.9374 |

## Interpretation

- `odm_truth_refresh` keeps the original three-layer suite semantics but swaps the truth orthophoto source and the runtime DSM source.
- `satellite_truth` is an independent cross-check. Its layer-2 result is a geometry diagnostic relative to the truth patch rather than a pose-vs-AT comparison.


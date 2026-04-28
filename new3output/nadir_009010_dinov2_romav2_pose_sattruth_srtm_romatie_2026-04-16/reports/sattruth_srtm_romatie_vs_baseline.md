# Satellite Truth + SRTM + RoMa Tiepoints vs Baseline

## Scope

- Baseline root: `/mnt/d/aiproject/imagematch/new2output/nadir_009010_dinov2_romav2_pose_2026-04-10`
- Current experiment root: `/mnt/d/aiproject/imagematch/new3output/nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16`
- Runtime retrieval / rerank / satellite candidate DOM library remained fixed.
- Main changes were: satellite truth patches replaced UAV truth orthophotos, DSM returned to SRTM, and layer-3 matching switched to RoMa v2.

## Pose Runtime

- Baseline PnP rows: `800`, status counts: `{'ok': 734, 'pnp_failed': 66}`
- Current PnP rows: `800`, status counts: `{'ok': 730, 'pnp_failed': 70}`
- Baseline best-pose rows: `40`, status counts: `{'ok': 40}`
- Current best-pose rows: `40`, status counts: `{'ok': 40}`

## Validation Summary

| Suite | Metric | Value |
| --- | --- | --- |
| baseline | layer1 phase_corr_error_m mean | 0.7672 |
| baseline | layer1 ortho_iou mean | 0.7289 |
| baseline | layer1 ssim mean | 0.5958 |
| baseline | layer2 horizontal_error_m mean | 9.1654 |
| baseline | layer2 view_dir_angle_error_deg mean | 1.2706 |
| baseline | layer3 tiepoint_match_count median | 1373.5000 |
| baseline | layer3 tiepoint_inlier_count median | 1145.0000 |
| baseline | layer3 tiepoint_xy_error_rmse_m | 2.8552 |
| baseline | layer3 tiepoint_xy_error_p90_m | 4.3476 |
| sattruth_srtm_romatie | layer1 phase_corr_error_m mean | 0.1919 |
| sattruth_srtm_romatie | layer1 ortho_iou mean | 0.7738 |
| sattruth_srtm_romatie | layer1 ssim mean | 0.4250 |
| sattruth_srtm_romatie | layer2 horizontal_error_m mean | 9.7230 |
| sattruth_srtm_romatie | layer2 view_dir_angle_error_deg mean | 1.3471 |
| sattruth_srtm_romatie | layer3 tiepoint_match_count median | 4890.0000 |
| sattruth_srtm_romatie | layer3 tiepoint_inlier_count median | 4238.5000 |
| sattruth_srtm_romatie | layer3 tiepoint_xy_error_rmse_m | 2.7718 |
| sattruth_srtm_romatie | layer3 tiepoint_xy_error_p90_m | 4.4149 |

## Low-Match Query Review

| Query | Baseline Matches | Current Matches | Delta | Baseline RMSE | Current RMSE |
| --- | --- | --- | --- | --- | --- |
| q_040 | 698 | 4901 | 4203 | 3.1219 | 3.6042 |
| q_031 | 784 | 4889 | 4105 | 4.5669 | 5.0892 |
| q_038 | 796 | 4805 | 4009 | 1.9927 | 3.9100 |
| q_034 | 855 | 4734 | 3879 | 2.8297 | 5.5110 |
| q_039 | 882 | 4852 | 3970 | 3.0561 | 1.7263 |
| q_035 | 886 | 4873 | 3987 | 2.1863 | 3.4738 |
| q_001 | 968 | 4829 | 3861 | 2.5494 | 1.2762 |
| q_036 | 1178 | 4834 | 3656 | 3.4201 | 8.2668 |

## Interpretation

- This route keeps the original runtime localization task unchanged and changes only the offline validation truth source plus the layer-3 matcher.
- Layer-2 remains `pose_vs_at`, so changes in layer-2 should be interpreted as pose consistency changes rather than a change in evaluation semantics.
- Low-match review is defined from the baseline layer-3 lower quartile of `tiepoint_match_count` and compares the same query IDs under the new route.


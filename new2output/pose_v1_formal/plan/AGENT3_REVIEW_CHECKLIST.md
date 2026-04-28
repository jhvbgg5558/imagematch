# Agent3 Review Checklist

- Verify `D:\aiproject\imagematch\scripts\sample_dsm_for_dom_points.py` routes DSM sampling by `candidate_id == dsm_id`.
- Verify missing raster assets are labeled `missing_dsm_raster` and not merged into `nodata`.
- Verify `D:\aiproject\imagematch\scripts\build_formal_dsm_rasters_from_hgt.py` uses manifest request bounds directly and does not add external scale normalization.
- Verify `D:\aiproject\imagematch\scripts\score_pose_candidates.py` and `D:\aiproject\imagematch\scripts\summarize_pose_results.py` default to `D:\aiproject\imagematch\new2output\pose_v1_formal\`.
- Verify no new script uses `query_truth` to select runtime candidates, DSM rasters, or PnP inputs.

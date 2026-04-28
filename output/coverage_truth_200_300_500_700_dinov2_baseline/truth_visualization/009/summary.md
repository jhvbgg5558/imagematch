# Flight 009 Truth Visualization Summary

- Flight: DJI_202510311347_009_新建面状航线1
- Query count: 10
- Mean truth count: 11.60
- Coverage threshold: 0.40
- Footprint core ratio: 0.60

## Quick Observations

- Most truth-rich query: `q_004` with `16` truth tiles.
- Most compact query: `q_001` with `8` truth tiles.
- Highest top truth overlap: `q_002` top tile `s700_x253880.070_y3364790.419` with coverage ratio `1.000`.
- This flight contains many 500m and 700m truth tiles, so the optimized truth set is often region-level similar rather than patch-level identical.
- Queries with only large-scale truth tiles are expected to look less visually identical than old center-point truth, but they better reflect shared ground coverage.

## Per Query

- `q_001`: truth_count=`8`, top_truth=`s700_x253880.070_y3364790.419`, top_scale=`700m`, top_coverage_ratio=`0.861`
- `q_002`: truth_count=`14`, top_truth=`s700_x253880.070_y3364790.419`, top_scale=`700m`, top_coverage_ratio=`1.000`
- `q_003`: truth_count=`12`, top_truth=`s500_x254283.525_y3363823.418`, top_scale=`500m`, top_coverage_ratio=`0.822`
- `q_004`: truth_count=`16`, top_truth=`s500_x254158.067_y3364678.442`, top_scale=`500m`, top_coverage_ratio=`1.000`
- `q_005`: truth_count=`10`, top_truth=`s700_x253880.070_y3364790.419`, top_scale=`700m`, top_coverage_ratio=`0.735`
- `q_006`: truth_count=`11`, top_truth=`s700_x254394.267_y3364169.404`, top_scale=`700m`, top_coverage_ratio=`1.000`
- `q_007`: truth_count=`11`, top_truth=`s700_x254397.293_y3364682.454`, top_scale=`700m`, top_coverage_ratio=`0.780`
- `q_008`: truth_count=`12`, top_truth=`s700_x254408.067_y3364778.442`, top_scale=`700m`, top_coverage_ratio=`0.731`
- `q_009`: truth_count=`12`, top_truth=`s500_x254825.317_y3364420.530`, top_scale=`500m`, top_coverage_ratio=`0.817`
- `q_010`: truth_count=`10`, top_truth=`s700_x254922.293_y3364157.454`, top_scale=`700m`, top_coverage_ratio=`1.000`
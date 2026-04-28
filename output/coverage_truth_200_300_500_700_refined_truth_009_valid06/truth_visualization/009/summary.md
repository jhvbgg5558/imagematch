# Flight 009 Truth Visualization Summary

- Flight: DJI_202510311347_009_新建面状航线1
- Query count: 10
- Mean truth count: 11.60
- Coverage threshold: 0.40
- Footprint core ratio: 0.60
- Min valid ratio: 0.60

## Quick Observations

- Most truth-rich query: `q_004` with `16` truth tiles.
- Most compact query: `q_001` with `8` truth tiles.
- Highest top truth overlap: `q_006` top tile `s700_x254397.293_y3364157.454` with coverage ratio `1.000`.
- This flight contains many 500m and 700m truth tiles, so the optimized truth set is often region-level similar rather than patch-level identical.
- Queries with only large-scale truth tiles are expected to look less visually identical than old center-point truth, but they better reflect shared ground coverage.

## Per Query

- `q_001`: truth_count=`8`, strict=`2`, soft=`6`, top_truth=`s700_x253883.067_y3364778.442`, top_scale=`700m`, top_coverage_ratio=`0.840`, top_valid_ratio=`0.657`
- `q_002`: truth_count=`14`, strict=`5`, soft=`9`, top_truth=`s700_x253883.067_y3364778.442`, top_scale=`700m`, top_coverage_ratio=`1.000`, top_valid_ratio=`0.657`
- `q_003`: truth_count=`12`, strict=`3`, soft=`9`, top_truth=`s700_x254383.525_y3363548.418`, top_scale=`700m`, top_coverage_ratio=`0.573`, top_valid_ratio=`0.657`
- `q_004`: truth_count=`16`, strict=`5`, soft=`11`, top_truth=`s700_x253883.067_y3364778.442`, top_scale=`700m`, top_coverage_ratio=`0.875`, top_valid_ratio=`0.657`
- `q_005`: truth_count=`10`, strict=`2`, soft=`8`, top_truth=`s700_x253883.067_y3364778.442`, top_scale=`700m`, top_coverage_ratio=`0.710`, top_valid_ratio=`0.657`
- `q_006`: truth_count=`11`, strict=`2`, soft=`9`, top_truth=`s700_x254397.293_y3364157.454`, top_scale=`700m`, top_coverage_ratio=`1.000`, top_valid_ratio=`0.657`
- `q_007`: truth_count=`11`, strict=`3`, soft=`8`, top_truth=`s700_x254411.063_y3364766.491`, top_scale=`700m`, top_coverage_ratio=`0.608`, top_valid_ratio=`0.657`
- `q_008`: truth_count=`12`, strict=`3`, soft=`9`, top_truth=`s700_x254411.063_y3364766.491`, top_scale=`700m`, top_coverage_ratio=`0.708`, top_valid_ratio=`0.657`
- `q_009`: truth_count=`12`, strict=`3`, soft=`9`, top_truth=`s700_x254925.317_y3364145.530`, top_scale=`700m`, top_coverage_ratio=`0.562`, top_valid_ratio=`0.657`
- `q_010`: truth_count=`10`, strict=`5`, soft=`5`, top_truth=`s700_x254925.317_y3364145.530`, top_scale=`700m`, top_coverage_ratio=`1.000`, top_valid_ratio=`0.657`
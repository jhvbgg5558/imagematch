# Overall Intersection Truth Summary

- Query count: 40
- Total truth tiles: 9563
- Mean truth count: 239.07
- Scales: 200m=4270, 300m=2292, 500m=1360, 700m=1641

## Highlighted Queries

- Most truth-rich: `q_022` with 265 tiles.
- Least truth-rich: `q_021` with 192 tiles.

## Notes

- True tiles are defined by any non-zero area intersection with the query footprint.
- Larger scales and overlap increase the number of truth tiles, which explains why some candidates now cover the query range without being strict-truth-level matches.
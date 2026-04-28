# Overall Intersection Truth Summary

- Query count: 40
- Total truth tiles: 3311
- Mean truth count: 82.78
- Scales: 200m=1252, 300m=751, 500m=535, 700m=773

## Highlighted Queries

- Most truth-rich: `q_027` with 100 tiles.
- Least truth-rich: `q_017` with 41 tiles.

## Notes

- True tiles are defined by any non-zero area intersection with the query footprint.
- Larger scales and overlap increase the number of truth tiles, which explains why some candidates now cover the query range without being strict-truth-level matches.
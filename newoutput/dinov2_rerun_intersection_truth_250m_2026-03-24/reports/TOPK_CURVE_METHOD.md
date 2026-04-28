# Top-K Curve Method (Unique Tile Version, Reusable)

## Goal

- Build a top-k curve where:
  - x-axis = number of retrieved satellite tiles (K)
  - y-axis = number of found truth tiles (unique tile count)
- Curve must become flat after all truth tiles are found.

## Truth definition used here

- Intersection truth: a tile is truth if it has non-zero area overlap with query footprint.
- For this curve, truth is deduplicated by `tile_id`:
  - per-flight truth set = union of all truth tile IDs from queries in that flight
  - overall truth set = union of all truth tile IDs from all flights

## Candidate ranking definition (unique tile ranking)

- Input retrieval table is `retrieval_all.csv` (full-library, `top_k=0`).
- A flight has multiple queries, each with a score for a tile.
- Convert to unique tile ranking by flight:
  - for each `tile_id`, keep max score over all queries in that flight
  - sort unique tiles by this max score descending
- Overall ranking:
  - for each `tile_id`, keep max score over all queries in all flights
  - sort descending

This ensures K means "K unique satellite tiles", not query-tile pairs.

## Commands

### 1) Generate full-library retrieval table

```bash
/mnt/d/aiproject/imagematch/.conda/bin/python /mnt/d/aiproject/imagematch/scripts/evaluate_retrieval_against_intersection_truth.py \
  --query-features-npz /mnt/d/aiproject/imagematch/newoutput/dinov2_rerun_intersection_truth_250m_2026-03-24/query_features/query_dinov2_pooler.npz \
  --query-seed-csv /mnt/d/aiproject/imagematch/output/coverage_truth_200_300_500_700_intersection_truth_eval/query_truth/queries_truth_seed.csv \
  --query-truth-tiles-csv /mnt/d/aiproject/imagematch/output/coverage_truth_200_300_500_700_intersection_truth_eval/query_truth/query_truth_tiles.csv \
  --faiss-index /mnt/d/aiproject/imagematch/newoutput/dinov2_rerun_intersection_truth_250m_2026-03-24/faiss/satellite_tiles_ip.index \
  --mapping-json /mnt/d/aiproject/imagematch/newoutput/dinov2_rerun_intersection_truth_250m_2026-03-24/faiss/satellite_tiles_ip_mapping.json \
  --top-k 0 \
  --output-csv /mnt/d/aiproject/imagematch/newoutput/dinov2_rerun_intersection_truth_250m_2026-03-24/retrieval/retrieval_all.csv \
  --summary-json /mnt/d/aiproject/imagematch/newoutput/dinov2_rerun_intersection_truth_250m_2026-03-24/retrieval/summary_all.json \
  --curve-csv /mnt/d/aiproject/imagematch/newoutput/dinov2_rerun_intersection_truth_250m_2026-03-24/retrieval/topk_truth_curve_all.csv
```

### 2) Plot unique-tile curves

```bash
/mnt/d/aiproject/imagematch/.conda/bin/python /mnt/d/aiproject/imagematch/scripts/plot_topk_unique_tile_curves.py \
  --retrieval-csv /mnt/d/aiproject/imagematch/newoutput/dinov2_rerun_intersection_truth_250m_2026-03-24/retrieval/retrieval_all.csv \
  --query-seed-csv /mnt/d/aiproject/imagematch/output/coverage_truth_200_300_500_700_intersection_truth_eval/query_truth/queries_truth_seed.csv \
  --query-truth-tiles-csv /mnt/d/aiproject/imagematch/output/coverage_truth_200_300_500_700_intersection_truth_eval/query_truth/query_truth_tiles.csv \
  --out-dir /mnt/d/aiproject/imagematch/newoutput/dinov2_rerun_intersection_truth_250m_2026-03-24/figures_topk_unique_tile
```

## Outputs

- Overall curve:
  - `figures_topk_unique_tile/_aggregate/overall_topk_unique_truth_count_curve.png`
- Per-flight curves:
  - `figures_topk_unique_tile/<flight_id>/topk_unique_truth_count_curve.png`
- Raw curve table:
  - `figures_topk_unique_tile/topk_unique_truth_curve.csv`
- Full-truth K stats:
  - `figures_topk_unique_tile/k_full_truth_unique_tile_summary.json`

## Key interpretation

- `k_full_truth` = smallest K where found unique truth tile count reaches total unique truth tile count.
- After `k_full_truth`, the curve should remain flat.

## Reuse on other methods

- Keep truth files unchanged if truth definition is unchanged.
- Replace only retrieval source (`retrieval_all.csv`) from another method.
- Run the same unique-tile curve script to get comparable curves and `k_full_truth`.

## Common pitfalls

- Do not use top-10/top-20 files; they cannot show full-truth flattening behavior.
- Do not mix per-query cumulative-hit curves with unique-tile curves.
- If satellite library size changes, K upper bound changes and old thresholds are not directly comparable.

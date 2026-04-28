# Flight 012 Failure Analysis

## Compared Flights
- Stronger references: `DJI_202510311347_009_新建面状航线1`, `DJI_202510311435_011_新建面状航线1`
- Weak target: `DJI_202510311500_012_新建面状航线1`

## Key Findings
- `012` is not a total failure, but its performance is unstable and highly scale-sensitive.
- The main collapse happens at `120m`: `R@1=0.0`, `R@5=0.0`, `R@10=0.0`.
- `200m` partially rescues retrieval on `012`: `R@1=0.4`, `R@5=0.6`, `R@10=0.6`.
- Compared with `009` and `011`, `012` has weaker local structural distinctiveness at small scale.

## Evidence
- `009`
  - `120m`: `R@1=0.4`, `R@5=1.0`, `R@10=1.0`
  - `200m`: `R@1=0.6`, `R@5=1.0`, `R@10=1.0`
- `011`
  - `120m`: `R@1=0.6`, `R@5=0.8`, `R@10=1.0`
  - `200m`: `R@1=0.6`, `R@5=0.8`, `R@10=1.0`
- `012`
  - `120m`: `R@1=0.0`, `R@5=0.0`, `R@10=0.0`
  - `200m`: `R@1=0.4`, `R@5=0.6`, `R@10=0.6`

## Likely Causes
- Small-scale ambiguity:
  - `012` 120m blocks have lower average gradient strength than `009`, and lower gradient/texture combination than both strong flights.
  - This means the selected blocks contain less distinctive local geometry for DINOv2 retrieval.
- Repetitive urban patterns:
  - Failed `012` queries often retrieve visually similar but spatially incorrect tiles from nearby urban regions.
  - The top candidates are not random noise; they are structurally similar distractors.
- Better context at 200m:
  - When moving from `120m` to `200m`, `012` starts to recover.
  - This suggests the weak point is insufficient contextual field-of-view rather than a complete domain mismatch.
- One noisy 200m block:
  - `q_200m_01` on `012` has `invalid_ratio=0.224`, which is much worse than the clean reference flights.
  - This likely weakens at least one of the failed 200m retrievals.

## Failure Pattern
- `012` failed queries at `Top-10`:
  - all `120m` queries: `q_120m_01` to `q_120m_05`
  - two `200m` queries: `q_200m_01`, `q_200m_02`
- The top-ranked wrong tiles are often close in appearance and sometimes even geographically nearby in the broader study area.
- This is consistent with local texture confusion, not with broken metadata or index wiring.

## Interpretation
- The current pipeline works best when query blocks contain strong layout cues such as road intersections, block boundaries, and dense man-made structure.
- `012` seems to have more locally repetitive or less discriminative patterns at 120m.
- The retrieval backbone is usable, but small query windows are not robust across all flights.

## Recommended Next Step
- Use `200m` as the primary query scale for the next validation round.
- Treat `120m` as a secondary diagnostic scale rather than the main operating scale.
- Add stricter query-block filtering:
  - penalize low gradient blocks
  - penalize repeated roof/road-only regions
  - reject blocks with higher invalid ratios
- For `012`, manually inspect failed query sheets to verify whether the wrong tiles are visually confusable or whether the selected query regions themselves are weak.

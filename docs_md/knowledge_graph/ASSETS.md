# Assets

## Source Policy

Current asset truth comes from [../DATA_ASSETS.md](../DATA_ASSETS.md), with status refinements from [../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md). This wiki must not promote unlisted outputs into active evidence.

## Active Asset Families

[[metadata-free query]] assets:

- `output/query_sanitized_40_v2/` for early retrieval experiments;
- `new1output/query_reselect_2026-03-26_v2/query_inputs/` for query-v2 experiments;
- 009/010 branch-local query inputs under `new2output/` and `new3output/`.

[[fixed satellite library]] assets:

- early raw multi-scale satellite libraries under `output/`;
- `output/coverage_truth_200_300_500_700_dinov2_baseline/fixed_satellite_library/` as the formal runtime candidate source for the SRTM route;
- CaiWangCun branch-local candidate DOM/DSM assets for the full-replacement route.

Pose assets:

- [[formal pose v1]] root: `new2output/pose_v1_formal/`;
- 009/010 route root: `new2output/nadir_009010_dinov2_romav2_pose_2026-04-10/`;
- CaiWangCun full replacement root: `new3output/nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21/`.

Sources: [../DATA_ASSETS.md](../DATA_ASSETS.md), [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

## Historical or Inactive Assets

The following are not current formal evidence:

- `old/` scripts, outputs, preprocessing products, and conclusions;
- old same-scale query/candidate assets;
- transition `512x512` satellite libraries such as `output/fixed_satellite_library_4flights_80_120_200`;
- `new2output/pose_baseline_v1/` debug runs when discussing formal pose v1 results;
- incomplete or superseded PnP write-attempt outputs preserved only for audit.

Sources: [../DATA_ASSETS.md](../DATA_ASSETS.md), [../RESULTS_INDEX.md](../RESULTS_INDEX.md).

## Asset Rules

- Runtime candidate selection must be truth-free.
- `query_truth` may be used for offline evaluation and manifest audit fields only.
- Branch-local replacement assets must remain isolated under their experiment roots.
- If an override manifest is supplied for ODM truth, silent fallback to legacy flight-root orthophotos is not permitted.
- Raw DSM sources such as `new2output/N30E114.hgt` are upstream sources, not final candidate DSM rasters.

Source: [../EXPERIMENT_PROTOCOL.md](../EXPERIMENT_PROTOCOL.md).


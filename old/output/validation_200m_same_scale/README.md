# Strict 200m Same-Scale Retrieval Experiment

This experiment enforces a single evaluation protocol:

- Query blocks: drone orthophoto patches with 200m ground coverage.
- Satellite retrieval library: only 200m satellite tiles.
- Input resolution: all patches and tiles remain resized to the unified network input size already used by the project.
- Truth definition: a query is positive only if its center falls inside a 200m satellite tile.

Purpose:

To verify whether cross-view coarse retrieval can localize the drone image near the correct geographic area using only remote-sensing orthophotos, without relying on mixed satellite scales.

Directory layout:

- `stage1/tiles_200m.csv`: 200m-only satellite metadata.
- `stage2/`: 200m-only DINOv2 feature subset, FAISS index, and mapping.
- `stage3/<flight>/`: strict 200m query metadata and copied query PNGs.
- `stage4/<flight>/`: reused query features plus strict retrieval outputs.
- `stage7/<flight>/`: strict analysis outputs.

Query counts kept after applying 200m-center truth:
- `DJI_202510311347_009_新建面状航线1`: 5
- `DJI_202510311413_010_新建面状航线1`: 5
- `DJI_202510311435_011_新建面状航线1`: 5
- `DJI_202510311500_012_新建面状航线1`: 5

# 当前输入数据与 ROI 说明

- Query 数量：`40`
- 航线数量：`4`
- Query 坐标系：`EPSG:32650`
- 卫片坐标系：`EPSG:32650`
- ROI buffer：`250.0m`
- 原始 flight bbox 面积：`5.446 km^2`
- 外扩后 ROI 面积：`8.030 km^2`
- 外扩增加面积：`2.584 km^2`
- 卫片 tile 总数：`1029`

## 各尺度 tile 数

- `200m`: `553`
- `300m`: `253`
- `500m`: `114`
- `700m`: `109`

## Query footprint 面积统计

- 平均：`22.40 ha`
- 最小：`7.50 ha`
- 最大：`26.48 ha`

## 当前预处理链路

- 先从 4 条航线中选取代表性原始无人机图像作为 query 候选。
- 再用 Pillow 重编码生成无 EXIF/XMP/GPS 的 query 副本，作为正式检索输入。
- 卫片库先依据 ROI + fixed buffer 切出多尺度 tile，再对这些 tile 提取 DINOv2 特征并建 FAISS 索引。
- 当前卫片库保留 native crop resolution，不在切片阶段统一缩放到固定像素尺寸。
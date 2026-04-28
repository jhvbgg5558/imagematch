# OpenDroneMap 进度记录（2026-03-09）

## 1. 目标与背景
- 目标：在 WSL2 Ubuntu 环境下使用 Docker 版 OpenDroneMap（ODM）对无人机影像进行正射化。
- 原始数据根目录：`D:\数据\武汉影像\无人机0.1m`
- WSL 对应路径：`/mnt/d/数据/武汉影像/无人机0.1m`

## 2. 环境状态
- 系统：WSL2 Ubuntu 20.04
- Docker Desktop：已安装并可用
- Docker 验证：
  - `docker --version` 正常
  - `docker run --rm hello-world` 正常
- 权限问题处理：已将用户 `farsee2` 加入 `docker` 组，解决 `permission denied /var/run/docker.sock`。

## 3. 当前项目目录（脚本目录）
- 路径：`/mnt/d/aiproject/imagematch/orthoejection`
- 已创建文件：
  - `run_odm.sh`：一键运行 ODM
  - `odm.conf`：默认配置（DATA_ROOT、默认参数）
  - `README_ODM.md`：使用说明

## 4. 脚本能力说明
- 支持两种数据组织：
  1) `project/images/*.jpg`
  2) `project/*.jpg`（当前实际情况）
- 对第 2 种情况，会自动创建 `images/` 目录并建立符号链接（不复制、不覆盖原图）。

## 5. 已识别到的数据航线
- `DJI_202510311347_009_新建面状航线1`
- `DJI_202510311413_010_新建面状航线1`
- `DJI_202510311435_011_新建面状航线1`
- `DJI_202510311500_012_新建面状航线1`

## 6. 已完成处理的项目
- 项目：`DJI_202510311347_009_新建面状航线1`
- 输入：413 张航片
- 结论：ODM 运行完成，正射成果已生成。

### 关键成果文件
- 正射主成果：
  - `D:\数据\武汉影像\无人机0.1m\DJI_202510311347_009_新建面状航线1\odm_orthophoto\odm_orthophoto.tif`（约 442MB）
- 原始分辨率版本：
  - `...\odm_orthophoto\odm_orthophoto.original.tif`（约 799MB）
- 其他：
  - `...\odm_report\report.pdf`
  - `...\odm_georeferencing\odm_georeferenced_model.laz`
  - `...\odm_georeferencing\odm_georeferenced_model.bounds.gpkg`

## 7. 已确认的流程认知
- `odm_orthophoto.tif` 是该项目全部输入航片融合后的正射镶嵌成果。
- 不会覆盖原始 JPG。
- ODM 的标准正射输出是拼接成果（通常一张主 TIF），不是“每张原图各自一张正射图”的默认模式。

## 8. 下一次可直接执行的命令
在 WSL 终端：

```bash
cd /mnt/d/aiproject/imagematch/orthoejection
./run_odm.sh DJI_202510311413_010_新建面状航线1
```

如需保存日志：

```bash
./run_odm.sh DJI_202510311413_010_新建面状航线1 2>&1 | tee odm_010.log
```

## 9. 备注
- 第一次拉取 ODM 镜像会比较慢，属于正常现象。
- 若新终端报 Docker 权限问题，重新打开 WSL 终端或执行 `newgrp docker`。

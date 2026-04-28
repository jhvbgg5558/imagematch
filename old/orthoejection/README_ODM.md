# OpenDroneMap (Docker) Quick Start

This folder is preconfigured for OpenDroneMap on WSL2.

## 1) Data layout

The script supports both layouts:

```text
/mnt/d/数据/武汉影像/无人机0.1m/
  ├─ mission_01/
  │   ├─ images/
  │   │  ├─ DJI_0001.JPG
  │   │  └─ ...
  │   # OR images directly in mission_01/
  │   ├─ DJI_0001.JPG
  │   └─ ...
  └─ mission_02/
      └─ images/
```

`odm.conf` default:
- `DATA_ROOT="/mnt/d/数据/武汉影像/无人机0.1m"`

## 2) List detectable projects

```bash
./run_odm.sh --list
```

## 3) Run orthophoto processing

```bash
./run_odm.sh mission_01
```

Output is written under each project folder, for example:

```text
/mnt/d/数据/武汉影像/无人机0.1m/mission_01/odm_orthophoto/
```

If your images are directly under `mission_01/`, the script auto-creates
`mission_01/images/` as symlinks (no image duplication).

## 4) Optional extra parameters

```bash
./run_odm.sh mission_01 --dsm --dtm
./run_odm.sh mission_01 --rerun-all
```

## 5) Tune defaults

Edit `odm.conf`:
- `ODM_DEFAULT_ARGS="--orthophoto-resolution 5 --fast-orthophoto"`

You can set more conservative quality options if needed.

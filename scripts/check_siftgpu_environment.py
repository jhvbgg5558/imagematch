#!/usr/bin/env python3
"""Check whether true SIFTGPU matching is usable for a gate experiment.

Purpose:
- detect command-line SiftGPU or COLMAP's SiftGPU/OpenGL path;
- optionally run a two-image GPU SIFT probe and capture failures;
- write a machine-readable environment report before G03 is treated as a
  formal experiment.

Main inputs:
- optional query and candidate image paths for a runtime probe.

Main outputs:
- `siftgpu_env_check.json` with executable discovery, GPU information, and
  probe status.

Applicable task constraints:
- query images have no runtime geolocation metadata and are not assumed to be
  orthophotos;
- CPU SIFT fallback is reported as diagnostic only and is not marked as formal
  SIFTGPU availability.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--query-image", default=None)
    parser.add_argument("--candidate-image", default=None)
    parser.add_argument("--colmap-bin", default="colmap")
    parser.add_argument("--siftgpu-bin", default=None)
    parser.add_argument("--max-num-features", type=int, default=8192)
    return parser.parse_args()


def run_capture(cmd: list[str], timeout: int = 120) -> dict[str, object]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return {
            "command": cmd,
            "returncode": completed.returncode,
            "elapsed_seconds": time.perf_counter() - started,
            "output_tail": completed.stdout[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": cmd,
            "returncode": None,
            "elapsed_seconds": time.perf_counter() - started,
            "timeout": True,
            "output_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
        }


def count_colmap_rows(database_path: Path) -> dict[str, int]:
    if not database_path.exists():
        return {}
    con = sqlite3.connect(str(database_path))
    try:
        return {
            table: int(con.execute(f"select count(*) from {table}").fetchone()[0])
            for table in ("images", "keypoints", "descriptors", "matches", "two_view_geometries")
        }
    finally:
        con.close()


def colmap_gpu_probe(args: argparse.Namespace) -> dict[str, object]:
    if not args.query_image or not args.candidate_image:
        return {"requested": False}
    colmap_path = shutil.which(args.colmap_bin)
    if not colmap_path:
        return {"requested": True, "available": False, "reason": "colmap_not_found"}

    with tempfile.TemporaryDirectory(prefix="siftgpu_env_probe_") as tmp_raw:
        tmp = Path(tmp_raw)
        image_dir = tmp / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.query_image, image_dir / "query.jpg")
        shutil.copy2(args.candidate_image, image_dir / "candidate.png")
        db_path = tmp / "database.db"
        feature = run_capture(
            [
                colmap_path,
                "feature_extractor",
                "--database_path",
                str(db_path),
                "--image_path",
                str(image_dir),
                "--ImageReader.single_camera",
                "0",
                "--SiftExtraction.use_gpu",
                "1",
                "--SiftExtraction.max_num_features",
                str(args.max_num_features),
            ]
        )
        if feature["returncode"] != 0:
            return {
                "requested": True,
                "available": False,
                "backend": "colmap_siftgpu",
                "feature_extractor": feature,
                "database_counts": count_colmap_rows(db_path),
            }
        matcher = run_capture(
            [
                colmap_path,
                "exhaustive_matcher",
                "--database_path",
                str(db_path),
                "--SiftMatching.use_gpu",
                "1",
            ]
        )
        counts = count_colmap_rows(db_path)
        return {
            "requested": True,
            "available": matcher["returncode"] == 0 and counts.get("two_view_geometries", 0) > 0,
            "backend": "colmap_siftgpu",
            "feature_extractor": feature,
            "matcher": matcher,
            "database_counts": counts,
        }


def siftgpu_cli_probe(args: argparse.Namespace) -> dict[str, object]:
    if not args.siftgpu_bin:
        return {"requested": False}
    siftgpu_bin = Path(args.siftgpu_bin)
    if not siftgpu_bin.exists():
        return {"requested": True, "available": False, "reason": "siftgpu_bin_not_found", "siftgpu_bin": str(siftgpu_bin)}
    if not args.query_image or not args.candidate_image:
        return {"requested": True, "available": False, "reason": "probe_images_not_provided", "siftgpu_bin": str(siftgpu_bin)}
    with tempfile.TemporaryDirectory(prefix="siftgpu_cli_probe_") as tmp_raw:
        out_csv = Path(tmp_raw) / "matches.csv"
        run = run_capture(
            [
                str(siftgpu_bin),
                str(args.query_image),
                str(args.candidate_image),
                str(out_csv),
                str(args.max_num_features),
            ],
            timeout=120,
        )
        row_count = 0
        if out_csv.exists():
            with out_csv.open("r", newline="", encoding="utf-8-sig") as handle:
                row_count = sum(1 for _ in csv.DictReader(handle))
        return {
            "requested": True,
            "available": run.get("returncode") == 0 and row_count > 0,
            "backend": "local_siftgpu_pair_match",
            "siftgpu_bin": str(siftgpu_bin),
            "run": run,
            "match_row_count": row_count,
        }


def main() -> None:
    args = parse_args()
    out_json = Path(args.out_json)
    executables = {
        name: shutil.which(name)
        for name in ("siftgpu", "SiftGPU", "sift_gpu", args.colmap_bin, "nvidia-smi", "cmake", "make", "g++")
    }
    nvidia = run_capture([executables["nvidia-smi"], "--query-gpu=name,driver_version", "--format=csv,noheader"], timeout=20) if executables["nvidia-smi"] else {}
    colmap_help = run_capture([executables[args.colmap_bin], "-h"], timeout=20) if executables[args.colmap_bin] else {}
    cli_probe = siftgpu_cli_probe(args)
    probe = colmap_gpu_probe(args)
    classic_siftgpu_available = any(executables[name] for name in ("siftgpu", "SiftGPU", "sift_gpu"))
    available = bool(classic_siftgpu_available or cli_probe.get("available") or probe.get("available"))

    payload = {
        "available": available,
        "classic_siftgpu_executable_available": classic_siftgpu_available,
        "local_siftgpu_pair_match_available": bool(cli_probe.get("available")),
        "colmap_siftgpu_probe_available": bool(probe.get("available")),
        "executables": executables,
        "nvidia_smi": nvidia,
        "colmap_help": colmap_help,
        "local_siftgpu_pair_match_probe": cli_probe,
        "probe": probe,
        "formal_cpu_fallback_allowed": False,
        "generated_at_unix": time.time(),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_json)


if __name__ == "__main__":
    main()

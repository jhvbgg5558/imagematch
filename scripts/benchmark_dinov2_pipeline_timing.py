#!/usr/bin/env python3
"""Run or document end-to-end DINOv2 pipeline timing checkpoints."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--satellite-feature-cmd", default="")
    parser.add_argument("--faiss-build-cmd", default="")
    parser.add_argument("--query-feature-cmd", default="")
    parser.add_argument("--retrieval-cmd", default="")
    parser.add_argument("--execute", action="store_true", help="Actually run the commands. Default: only record placeholders.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    stages = [
        ("satellite_feature_extraction", args.satellite_feature_cmd),
        ("faiss_index_build", args.faiss_build_cmd),
        ("query_feature_extraction", args.query_feature_cmd),
        ("query_retrieval", args.retrieval_cmd),
    ]

    rows = []
    for stage_name, cmd in stages:
        row = {"stage": stage_name, "command": cmd, "status": "not_run", "elapsed_seconds": None}
        if args.execute and cmd:
            t0 = time.perf_counter()
            proc = subprocess.run(cmd, shell=True)
            elapsed = time.perf_counter() - t0
            row["elapsed_seconds"] = elapsed
            row["status"] = "ok" if proc.returncode == 0 else f"failed({proc.returncode})"
        rows.append(row)

    with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["stage", "command", "status", "elapsed_seconds"])
        writer.writeheader()
        writer.writerows(rows)

    out_json.write_text(json.dumps({"stages": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_json)
    print(out_csv)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Export RoMa v2 matches for formal pose-v1 query/candidate pairs in batch.

Purpose:
- run RoMa v2 on formal sanitized queries against formal candidate DOM tiles;
- export one canonical match CSV row set across multiple query/candidate pairs
  for downstream correspondence, DSM, and PnP stages.

Main inputs:
- `manifest/pose_manifest.json` built from formal query/candidate/DSM assets;
- optional query or rank filters for small-sample runs.

Main outputs:
- `matches/roma_matches.csv`
- `matches/roma_match_summary.json`
- `logs/export_romav2_matches_batch_for_pose.log`

Applicable task constraints:
- runtime query images must be sanitized UAV inputs only;
- candidate DOM tiles must come from the formal tile library only;
- this stage must not use truth to choose which pairs are matched.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import torch
from romav2 import RoMaV2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_v1_formal"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--manifest-json", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--setting", default="satast")
    parser.add_argument("--sample-count", type=int, default=5000)
    parser.add_argument("--ransac-reproj-thresh", type=float, default=4.0)
    parser.add_argument("--min-rank", type=int, default=1)
    parser.add_argument("--max-rank", type=int, default=20)
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--max-pairs", type=int, default=0)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        fieldnames = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def resolve_runtime_path(raw_path: str) -> Path:
    if os.name == "nt" and raw_path.startswith("/mnt/") and len(raw_path) > 6:
        drive_letter = raw_path[5]
        remainder = raw_path[7:].replace("/", "\\")
        return Path(f"{drive_letter.upper()}:\\{remainder}")
    if os.name != "nt" and len(raw_path) >= 3 and raw_path[1:3] == ":\\":
        drive_letter = raw_path[0].lower()
        remainder = raw_path[3:].replace("\\", "/")
        return Path(f"/mnt/{drive_letter}/{remainder}")
    return Path(raw_path)


def build_model(setting: str, device_name: str) -> RoMaV2:
    if device_name == "auto":
        use_cuda = torch.cuda.is_available()
    else:
        use_cuda = device_name.startswith("cuda")
    if use_cuda:
        torch.set_default_device("cuda")
    torch.set_float32_matmul_precision("highest")
    cfg = RoMaV2.Cfg(setting=setting, compile=False, name=f"RoMaV2-{setting}")
    return RoMaV2(cfg)


@torch.inference_mode()
def run_match(
    model: RoMaV2,
    query_path: Path,
    dom_path: Path,
    sample_count: int,
    ransac_reproj_thresh: float,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    preds = model.match(query_path, dom_path)
    matches, overlap, _, _ = model.sample(preds, sample_count)

    query_img = cv2.imread(str(query_path))
    dom_img = cv2.imread(str(dom_path))
    if query_img is None or dom_img is None:
        raise FileNotFoundError(f"Failed to read pair: {query_path} / {dom_path}")

    qh, qw = query_img.shape[:2]
    dh, dw = dom_img.shape[:2]
    kpts_q, kpts_d = model.to_pixel_coordinates(matches, qh, qw, dh, dw)
    q_np = kpts_q.detach().cpu().numpy().astype(np.float32)
    d_np = kpts_d.detach().cpu().numpy().astype(np.float32)
    overlap_np = overlap.detach().cpu().numpy().astype(np.float32)

    inlier_mask = np.zeros((len(q_np),), dtype=bool)
    homography = None
    if len(q_np) >= 4:
        homography, mask = cv2.findHomography(
            d_np,
            q_np,
            method=cv2.USAC_MAGSAC,
            ransacReprojThreshold=ransac_reproj_thresh,
            confidence=0.999999,
            maxIters=10000,
        )
        if mask is not None:
            inlier_mask = mask.ravel().astype(bool)

    rows: list[dict[str, object]] = []
    for idx, (q_pt, d_pt) in enumerate(zip(q_np, d_np), start=1):
        rows.append(
            {
                "row_id": idx,
                "query_x": f"{float(q_pt[0]):.6f}",
                "query_y": f"{float(q_pt[1]):.6f}",
                "dom_pixel_x": f"{float(d_pt[0]):.6f}",
                "dom_pixel_y": f"{float(d_pt[1]):.6f}",
                "match_score": f"{float(overlap_np[idx - 1]):.6f}",
                "is_inlier": int(bool(inlier_mask[idx - 1])),
            }
        )

    inlier_count = int(inlier_mask.sum())
    inlier_ratio = float(inlier_count / len(rows)) if rows else 0.0
    summary = {
        "match_count": len(rows),
        "inlier_count": inlier_count,
        "inlier_ratio": inlier_ratio,
        "geom_valid": bool(homography is not None),
    }
    return rows, summary


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    manifest_path = Path(args.manifest_json) if args.manifest_json else bundle_root / "manifest" / "pose_manifest.json"
    out_dir = Path(args.out_dir) if args.out_dir else bundle_root / "matches"
    logs_dir = bundle_root / "logs"
    ensure_dir(out_dir)
    ensure_dir(logs_dir)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    query_by_id = {row["query_id"]: row for row in manifest.get("queries", [])}
    dom_by_id = {row["candidate_id"]: row for row in manifest.get("dom_tiles", [])}
    coarse_rows = manifest.get("coarse_candidates", [])
    selected_query_ids = set(args.query_id)

    pair_rows = []
    for row in coarse_rows:
        rank = int(row["rank"])
        if rank < args.min_rank or rank > args.max_rank:
            continue
        if selected_query_ids and row["query_id"] not in selected_query_ids:
            continue
        pair_rows.append(row)
    if args.max_pairs > 0:
        pair_rows = pair_rows[: args.max_pairs]
    if not pair_rows:
        raise SystemExit("no query/candidate pairs selected for RoMa export")

    model = build_model(args.setting, args.device)
    output_rows: list[dict[str, object]] = []
    pair_summaries: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()

    for pair in pair_rows:
        rank = int(pair["rank"])
        query = query_by_id.get(pair["query_id"])
        dom = dom_by_id.get(pair["candidate_id"])
        if query is None or dom is None:
            raise SystemExit(f"manifest missing pair assets: {pair}")
        try:
            rows, summary = run_match(
                model=model,
                query_path=resolve_runtime_path(str(query["image_path"])),
                dom_path=resolve_runtime_path(str(dom["image_path"])),
                sample_count=args.sample_count,
                ransac_reproj_thresh=args.ransac_reproj_thresh,
            )
            status = "ok"
        except Exception as exc:
            rows = []
            summary = {
                "match_count": 0,
                "inlier_count": 0,
                "inlier_ratio": 0.0,
                "geom_valid": False,
            }
            status = f"error:{type(exc).__name__}"
        for row in rows:
            output_rows.append(
                {
                    "query_id": pair["query_id"],
                    "candidate_id": pair["candidate_id"],
                    "candidate_rank": rank,
                    **row,
                }
            )
        pair_summaries.append(
            {
                "query_id": pair["query_id"],
                "candidate_id": pair["candidate_id"],
                "candidate_rank": rank,
                "status": status,
                **summary,
            }
        )
        status_counts[status] += 1

    write_csv(out_dir / "roma_matches.csv", output_rows)
    (out_dir / "roma_match_summary.json").write_text(
        json.dumps(
            {
                "bundle_root": str(bundle_root),
                "manifest_json": str(manifest_path.resolve()),
                "pair_count": len(pair_rows),
                "row_count": len(output_rows),
                "pair_status_counts": dict(status_counts),
                "pair_summaries": pair_summaries,
                "sample_count": args.sample_count,
                "ransac_reproj_thresh": args.ransac_reproj_thresh,
                "device": args.device,
                "setting": args.setting,
                "generated_at_unix": time.time(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (logs_dir / "export_romav2_matches_batch_for_pose.log").write_text(
        "\n".join(
            [
                "stage=export_romav2_matches_batch_for_pose",
                f"pair_count={len(pair_rows)}",
                f"row_count={len(output_rows)}",
                f"pair_status_counts={dict(status_counts)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(out_dir / "roma_matches.csv")


if __name__ == "__main__":
    main()

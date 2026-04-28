#!/usr/bin/env python3
"""Export RoMa v2 matches for one pose-baseline query/candidate pair.

Purpose:
- run RoMa v2 on one query image and one DOM patch;
- export canonical match rows for downstream pose correspondences.

Main inputs:
- `manifest/pose_manifest.json` from `build_pose_manifest.py`;
- one query ID and one candidate ID present in the manifest.

Main outputs:
- `matches/roma_matches.csv`
- `matches/roma_match_summary.json`
- `logs/export_romav2_matches_for_pose.log`

Applicable task constraints:
- this script is only for Baseline v1 pose matching;
- it must not change the world coordinate system or the downstream PnP rules;
- it may use RoMa resizing internally, but exported coordinates must be in the
  original query and DOM image pixel systems.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from romav2 import RoMaV2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_baseline_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--manifest-json", default=None)
    parser.add_argument("--query-id", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--setting", default="satast")
    parser.add_argument("--sample-count", type=int, default=5000)
    parser.add_argument("--ransac-reproj-thresh", type=float, default=4.0)
    parser.add_argument("--min-inliers", type=int, default=20)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.01)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


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

    rows = []
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
        "geom_valid": bool(inlier_count >= 20 and inlier_ratio >= 0.01),
        "homography_found": homography is not None,
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
    query = next((row for row in manifest.get("queries", []) if row["query_id"] == args.query_id), None)
    dom = next((row for row in manifest.get("dom_tiles", []) if row["candidate_id"] == args.candidate_id), None)
    if query is None:
        raise SystemExit(f"query_id not found in manifest: {args.query_id}")
    if dom is None:
        raise SystemExit(f"candidate_id not found in manifest: {args.candidate_id}")

    model = build_model(args.setting, args.device)
    rows, summary = run_match(
        model=model,
        query_path=Path(query["image_path"]),
        dom_path=Path(dom["image_path"]),
        sample_count=args.sample_count,
        ransac_reproj_thresh=args.ransac_reproj_thresh,
    )

    output_rows = []
    for row in rows:
        output_rows.append(
            {
                "query_id": args.query_id,
                "candidate_id": args.candidate_id,
                "candidate_rank": 1,
                **row,
            }
        )

    write_csv(out_dir / "roma_matches.csv", output_rows)
    (out_dir / "roma_match_summary.json").write_text(
        json.dumps(
            {
                "bundle_root": str(bundle_root),
                "manifest_json": str(manifest_path.resolve()),
                "query_id": args.query_id,
                "candidate_id": args.candidate_id,
                "sample_count": args.sample_count,
                "ransac_reproj_thresh": args.ransac_reproj_thresh,
                "device": args.device,
                "setting": args.setting,
                **summary,
                "generated_at_unix": time.time(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (logs_dir / "export_romav2_matches_for_pose.log").write_text(
        "\n".join(
            [
                "stage=export_romav2_matches_for_pose",
                f"query_id={args.query_id}",
                f"candidate_id={args.candidate_id}",
                f"match_count={summary['match_count']}",
                f"inlier_count={summary['inlier_count']}",
                f"inlier_ratio={summary['inlier_ratio']:.6f}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(out_dir / "roma_matches.csv")


if __name__ == "__main__":
    main()

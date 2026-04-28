#!/usr/bin/env python3
"""Recompute LightGlue matches for selected query/tile pairs and render inlier correspondences."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from lightglue import LightGlue, SuperPoint
from lightglue.utils import numpy_image_to_torch, rbd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-result-dir", required=True)
    parser.add_argument("--lightglue-result-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-num-keypoints", type=int, default=256)
    parser.add_argument("--query-ids", nargs="*", default=[])
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_rgb(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGB"))


def build_extractor(max_num_keypoints: int, device: str):
    extractor = SuperPoint(max_num_keypoints=max_num_keypoints)
    matcher = LightGlue(features="superpoint")
    return extractor.eval().to(device), matcher.eval().to(device)


@torch.inference_mode()
def extract(image: np.ndarray, extractor, device: str):
    tensor = numpy_image_to_torch(image).to(device)
    return extractor.extract(tensor)


@torch.inference_mode()
def match_pair(query_img: np.ndarray, tile_img: np.ndarray, extractor, matcher, device: str):
    feats_q = extract(query_img, extractor, device)
    feats_t = extract(tile_img, extractor, device)
    out = rbd(matcher({"image0": feats_t, "image1": feats_q}))
    matches = out["matches"].detach().cpu().numpy()
    kq = rbd(feats_q)["keypoints"].detach().cpu().numpy()
    kt = rbd(feats_t)["keypoints"].detach().cpu().numpy()
    if matches.shape[0] < 4:
        return kq, kt, np.zeros((0, 2), dtype=int), np.zeros((0,), dtype=bool)
    src_pts = kt[matches[:, 0]].astype(np.float32)
    dst_pts = kq[matches[:, 1]].astype(np.float32)
    _, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if mask is None:
        inlier_mask = np.zeros((matches.shape[0],), dtype=bool)
    else:
        inlier_mask = mask.ravel().astype(bool)
    return kq, kt, matches, inlier_mask


def choose_cases(comp_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = []
    degraded = next((r for r in comp_rows if r["baseline_first_strict_truth_rank"] == "1" and r["lightglue_first_strict_truth_rank"] != "1"), None)
    if degraded:
        degraded = dict(degraded)
        degraded["case_type"] = "degraded_top1"
        selected.append(degraded)
    promoted = [r for r in comp_rows if int(r["promoted_11_20_to_top10"]) == 1]
    promoted.sort(key=lambda r: r["query_id"])
    for idx, row in enumerate(promoted[:2], start=1):
        item = dict(row)
        item["case_type"] = f"promoted_{idx}"
        selected.append(item)
    unresolved = [r for r in comp_rows if int(r["coarse_strict_hit@20"]) == 1 and int(r["lightglue_strict_hit@10"]) == 0]
    unresolved.sort(key=lambda r: (r["coarse_first_strict_truth_rank"] or "999", r["query_id"]))
    if unresolved:
        item = dict(unresolved[0])
        item["case_type"] = "unresolved_top20"
        selected.append(item)
    dedup = {}
    for row in selected:
        dedup[row["query_id"]] = row
    return list(dedup.values())


def draw_inliers(query_img: np.ndarray, tile_img: np.ndarray, kq, kt, matches: np.ndarray, inlier_mask: np.ndarray, title: str, out_path: Path) -> None:
    h = max(query_img.shape[0], tile_img.shape[0])
    w = query_img.shape[1] + tile_img.shape[1]
    canvas = np.full((h + 40, w, 3), 245, dtype=np.uint8)
    canvas[40 : 40 + tile_img.shape[0], : tile_img.shape[1]] = tile_img
    canvas[40 : 40 + query_img.shape[0], tile_img.shape[1] : tile_img.shape[1] + query_img.shape[1]] = query_img
    cv2.rectangle(canvas, (0, 0), (w, 40), (20, 20, 20), -1)
    cv2.putText(canvas, title, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
    offset_x = tile_img.shape[1]
    for idx, (m, keep) in enumerate(zip(matches, inlier_mask)):
        if not keep:
            continue
        x1, y1 = kt[m[0]]
        x2, y2 = kq[m[1]]
        p1 = (int(round(x1)), int(round(y1 + 40)))
        p2 = (int(round(x2 + offset_x)), int(round(y2 + 40)))
        color = (46, 204, 113)
        cv2.line(canvas, p1, p2, color, 1, cv2.LINE_AA)
        cv2.circle(canvas, p1, 3, color, -1, cv2.LINE_AA)
        cv2.circle(canvas, p2, 3, color, -1, cv2.LINE_AA)
    Image.fromarray(canvas).save(out_path)


def main() -> None:
    args = parse_args()
    baseline_dir = Path(args.baseline_result_dir)
    lightglue_dir = Path(args.lightglue_result_dir)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

    comp_rows = load_csv(lightglue_dir / "per_query_comparison.csv")
    selected = choose_cases(comp_rows) if not args.query_ids else [r for r in comp_rows if r["query_id"] in set(args.query_ids)]

    manifest = {r["query_id"]: r for r in load_csv(baseline_dir / "query_inputs" / "query_manifest.csv")}
    tiles = {r["tile_id"]: r for r in load_csv(baseline_dir / "fixed_satellite_library" / "tiles.csv")}
    reranked = {}
    for csv_path in sorted((lightglue_dir / "stage7").glob("*/reranked_top20.csv")):
        for row in load_csv(csv_path):
            reranked.setdefault(row["query_id"], []).append(row)
    for rows in reranked.values():
        rows.sort(key=lambda x: int(x["rank"]))

    extractor, matcher = build_extractor(args.max_num_keypoints, args.device)

    for row in selected:
        qid = row["query_id"]
        qpath = Path(manifest[qid]["sanitized_query_path"])
        qimg = read_rgb(qpath)
        top1 = reranked[qid][0]
        tile_id = top1["candidate_tile_id"]
        tpath = Path(tiles[tile_id]["image_path"])
        timg = read_rgb(tpath)
        kq, kt, matches, inlier_mask = match_pair(qimg, timg, extractor, matcher, args.device)
        title = f"{qid} | rank1 {tile_id} | inliers={int(inlier_mask.sum())}/{len(inlier_mask)} | hit={top1['is_strict_truth_hit']}"
        draw_inliers(qimg, timg, kq, kt, matches, inlier_mask, title, out_dir / f"{row['case_type']}_{qid}_rank1_inliers.png")

        truth_rows = [r for r in reranked[qid] if r["is_strict_truth_hit"] == "1"]
        if truth_rows:
            truth_row = truth_rows[0]
            tile_id = truth_row["candidate_tile_id"]
            tpath = Path(tiles[tile_id]["image_path"])
            timg = read_rgb(tpath)
            kq, kt, matches, inlier_mask = match_pair(qimg, timg, extractor, matcher, args.device)
            title = f"{qid} | first truth {tile_id} rank={truth_row['rank']} | inliers={int(inlier_mask.sum())}/{len(inlier_mask)}"
            draw_inliers(qimg, timg, kq, kt, matches, inlier_mask, title, out_dir / f"{row['case_type']}_{qid}_truth_inliers.png")

    print(out_dir)


if __name__ == "__main__":
    main()

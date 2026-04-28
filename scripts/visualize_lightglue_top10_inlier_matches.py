#!/usr/bin/env python3
"""Render top-10 LightGlue query/tile pairs with inlier correspondences.

The output is organized by flight and query:

    <out-dir>/<flight_id>/<query_id>/rank01_<tile_id>.png
    <out-dir>/<flight_id>/<query_id>/rank02_<tile_id>.png
    ...

Each image shows the query on the left and the ranked satellite tile on the right,
with only RANSAC inlier correspondences drawn as lines.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from lightglue import LightGlue, SuperPoint
from lightglue.utils import numpy_image_to_torch, rbd


QUERY_BORDER = (31, 119, 180)
TILE_BORDER_HIT = (26, 127, 55)
TILE_BORDER_MISS = (180, 35, 24)
TITLE_BAR = (24, 24, 24)
BG = (245, 245, 245)
LINE_COLOR = (46, 204, 113)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lightglue-result-dir",
        default="/mnt/d/aiproject/imagematch/newoutput/lightglue_intersection_truth_top50_k256_2026-03-24",
    )
    parser.add_argument(
        "--baseline-result-dir",
        default="/mnt/d/aiproject/imagematch/output/coverage_truth_200_300_500_700_dinov2_strict_truth_eval",
    )
    parser.add_argument(
        "--out-dir",
        default="/mnt/d/aiproject/imagematch/newoutput/lightglue_top10_inlier_viz_2026-03-26/figures",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-num-keypoints", type=int, default=256)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--target-long-side", type=int, default=900)
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


def resize_with_scale(image: np.ndarray, target_long_side: int) -> tuple[np.ndarray, float]:
    h, w = image.shape[:2]
    long_side = max(h, w)
    if long_side <= target_long_side:
        return image, 1.0
    scale = target_long_side / float(long_side)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized, scale


def add_border(img: np.ndarray, color: tuple[int, int, int], width: int = 6) -> np.ndarray:
    h, w = img.shape[:2]
    canvas = np.full((h + 2 * width, w + 2 * width, 3), color, dtype=np.uint8)
    canvas[width : width + h, width : width + w] = img
    return canvas


def draw_pair(
    query_img: np.ndarray,
    tile_img: np.ndarray,
    query_kpts: np.ndarray,
    tile_kpts: np.ndarray,
    matches: np.ndarray,
    inlier_mask: np.ndarray,
    title: str,
    out_path: Path,
    tile_hit: bool,
    target_long_side: int,
) -> None:
    q_vis, q_scale = resize_with_scale(query_img, target_long_side)
    t_vis, t_scale = resize_with_scale(tile_img, target_long_side)
    q_kpts = query_kpts * q_scale
    t_kpts = tile_kpts * t_scale

    q_vis = add_border(q_vis, QUERY_BORDER)
    t_vis = add_border(t_vis, TILE_BORDER_HIT if tile_hit else TILE_BORDER_MISS)

    title_h = 44
    gap = 0
    h = max(q_vis.shape[0], t_vis.shape[0]) + title_h
    w = q_vis.shape[1] + t_vis.shape[1] + gap
    canvas = np.full((h, w, 3), BG, dtype=np.uint8)
    canvas[title_h : title_h + q_vis.shape[0], 0 : q_vis.shape[1]] = q_vis
    canvas[title_h : title_h + t_vis.shape[0], q_vis.shape[1] : q_vis.shape[1] + t_vis.shape[1]] = t_vis

    cv2.rectangle(canvas, (0, 0), (w, title_h), TITLE_BAR, -1)
    cv2.putText(canvas, title, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 1, cv2.LINE_AA)

    x_offset = q_vis.shape[1]
    q_pad = 6
    t_pad = 6
    q_origin_x = q_pad
    q_origin_y = title_h + q_pad
    t_origin_x = x_offset + t_pad
    t_origin_y = title_h + t_pad

    for m, keep in zip(matches, inlier_mask):
        if not keep:
            continue
        tile_idx, query_idx = int(m[0]), int(m[1])
        q_pt = query_kpts[query_idx] * q_scale
        t_pt = tile_kpts[tile_idx] * t_scale
        p1 = (int(round(t_pt[0])) + t_origin_x, int(round(t_pt[1])) + t_origin_y)
        p2 = (int(round(q_pt[0])) + q_origin_x, int(round(q_pt[1])) + q_origin_y)
        cv2.line(canvas, p1, p2, LINE_COLOR, 1, cv2.LINE_AA)
        cv2.circle(canvas, p1, 3, LINE_COLOR, -1, cv2.LINE_AA)
        cv2.circle(canvas, p2, 3, LINE_COLOR, -1, cv2.LINE_AA)

    Image.fromarray(canvas).save(out_path)


def short_flight_name(flight_id: str) -> str:
    parts = flight_id.split("_")
    return parts[2] if len(parts) >= 3 else flight_id


def safe_name(text: str) -> str:
    return (
        text.replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace(" ", "_")
        .replace("(", "_")
        .replace(")", "_")
    )


def main() -> None:
    args = parse_args()
    result_dir = Path(args.lightglue_result_dir)
    baseline_dir = Path(args.baseline_result_dir)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

    manifest_rows = load_csv(baseline_dir / "query_inputs" / "query_manifest.csv")
    manifest = {row["query_id"]: row for row in manifest_rows}
    tile_rows = load_csv(baseline_dir / "fixed_satellite_library" / "tiles.csv")
    tiles = {row["tile_id"]: row for row in tile_rows}

    per_query_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for flight_dir in sorted((result_dir / "stage7").iterdir()):
        rerank_csv = flight_dir / "reranked_top50.csv"
        if not rerank_csv.exists():
            continue
        for row in load_csv(rerank_csv):
            per_query_rows[row["query_id"]].append(row)

    for rows in per_query_rows.values():
        rows.sort(key=lambda r: int(r["rank"]))

    extractor, matcher = build_extractor(args.max_num_keypoints, args.device)

    summary_rows: list[dict[str, object]] = []
    for qid in sorted(per_query_rows.keys()):
        query_meta = manifest[qid]
        flight_id = query_meta["flight_id"]
        query_path = Path(query_meta["sanitized_query_path"])
        query_img = read_rgb(query_path)

        q_out_dir = out_dir / flight_id / qid
        ensure_dir(q_out_dir)

        for row in per_query_rows[qid][: args.top_k]:
            tile_id = row["candidate_tile_id"]
            tile_meta = tiles[tile_id]
            tile_path = Path(tile_meta["image_path"])
            tile_img = read_rgb(tile_path)
            qk, tk, matches, inlier_mask = match_pair(query_img, tile_img, extractor, matcher, args.device)
            inlier_count = int(inlier_mask.sum())
            match_count = int(matches.shape[0])
            title = (
                f"{qid} | {short_flight_name(flight_id)} | rank={int(row['rank'])} | "
                f"tile={tile_id} | inliers={inlier_count}/{match_count} | hit={row['is_intersection_truth_hit']}"
            )
            out_path = q_out_dir / f"rank{int(row['rank']):02d}_{safe_name(tile_id)}.png"
            draw_pair(
                query_img,
                tile_img,
                qk,
                tk,
                matches,
                inlier_mask,
                title,
                out_path,
                tile_hit=row["is_intersection_truth_hit"] == "1",
                target_long_side=args.target_long_side,
            )
            summary_rows.append(
                {
                    "flight_id": flight_id,
                    "flight_tag": short_flight_name(flight_id),
                    "query_id": qid,
                    "rank": int(row["rank"]),
                    "candidate_tile_id": tile_id,
                    "is_intersection_truth_hit": int(row["is_intersection_truth_hit"]),
                    "match_count": match_count,
                    "inlier_count": inlier_count,
                    "inlier_ratio": f"{(inlier_count / match_count if match_count else 0.0):.6f}",
                    "fused_score": row["fused_score"],
                    "global_score": row["global_score"],
                    "candidate_scale_level_m": row["candidate_scale_level_m"],
                    "query_path": str(query_path),
                    "tile_path": str(tile_path),
                    "out_path": str(out_path),
                }
            )

    summary_csv = out_dir.parent / "summary_top10_inliers.csv"
    with summary_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fieldnames = list(summary_rows[0].keys()) if summary_rows else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    summary_md = out_dir.parent / "summary_top10_inliers.md"
    lines = [
        "# LightGlue Top10 同名点可视化汇总",
        "",
        f"- query 数量: {len(per_query_rows)}",
        f"- 每个 query 候选数: {args.top_k}",
        f"- 输出目录: `{out_dir}`",
        f"- 汇总表: `{summary_csv}`",
        "",
        "## 目录结构",
        "",
        "每个 query 的 10 张图按 `flight_id/q_xxx/` 存放，文件名以 `rank01_...png` 到 `rank10_...png` 命名。",
    ]
    summary_md.write_text("\n".join(lines), encoding="utf-8")

    print(out_dir)
    print(summary_csv)
    print(summary_md)


if __name__ == "__main__":
    main()

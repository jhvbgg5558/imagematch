#!/usr/bin/env python3
"""Rerank coarse retrieval candidates with local geometric verification."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-metadata-csv", required=True)
    parser.add_argument("--retrieval-csv", required=True)
    parser.add_argument("--tiles-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--metrics-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--rerank-mode", choices=["full_geom", "conservative_gate"], default="full_geom")
    parser.add_argument("--promotion-rank-gate", type=int, default=3)
    parser.add_argument("--ratio-thresh", type=float, default=0.75)
    parser.add_argument("--ransac-reproj-thresh", type=float, default=5.0)
    parser.add_argument("--min-homography-matches", type=int, default=4)
    parser.add_argument("--min-inliers", type=int, default=5)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.4)
    return parser.parse_args()


def read_gray(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("L"))


def load_queries(path: Path) -> dict[str, dict[str, object]]:
    queries: dict[str, dict[str, object]] = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries[row["query_id"]] = {
                "image_path": row["image_path"],
                "truth_tile_ids": [x for x in row.get("truth_tile_ids", "").split("|") if x],
                "center_x": float(row.get("center_x", 0.0) or 0.0),
                "center_y": float(row.get("center_y", 0.0) or 0.0),
                "scale_m": float(row.get("scale_m", 0.0) or 0.0),
            }
    return queries


def load_tiles(path: Path) -> dict[str, dict[str, object]]:
    tiles: dict[str, dict[str, object]] = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tiles[row["tile_id"]] = {
                "image_path": row["image_path"],
                "scale_level_m": row.get("scale_level_m", ""),
                "center_x": float(row.get("center_x", 0.0) or 0.0),
                "center_y": float(row.get("center_y", 0.0) or 0.0),
            }
    return tiles


def load_retrieval(path: Path, top_k: int) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rank = int(row["rank"])
            if rank > top_k:
                continue
            grouped[row["query_id"]].append(
                {
                    "raw_rank": rank,
                    "candidate_tile_id": row["candidate_tile_id"],
                    "global_score": float(row["score"]),
                }
            )
    for items in grouped.values():
        items.sort(key=lambda x: int(x["raw_rank"]))
    return grouped


def compute_reproj_error(
    homography: np.ndarray,
    src_pts: np.ndarray,
    dst_pts: np.ndarray,
    inlier_mask: np.ndarray,
) -> float | None:
    if homography is None or inlier_mask is None:
        return None
    inlier_mask = inlier_mask.ravel().astype(bool)
    if not np.any(inlier_mask):
        return None
    src_in = src_pts[inlier_mask].reshape(-1, 1, 2)
    dst_in = dst_pts[inlier_mask].reshape(-1, 2)
    proj = cv2.perspectiveTransform(src_in, homography).reshape(-1, 2)
    errors = np.linalg.norm(proj - dst_in, axis=1)
    return float(np.mean(errors)) if len(errors) else None


def verify_pair(
    sift: cv2.SIFT,
    matcher: cv2.BFMatcher,
    query_image: np.ndarray,
    cand_image: np.ndarray,
    ratio_thresh: float,
    ransac_reproj_thresh: float,
    min_homography_matches: int,
    min_inliers: int,
    min_inlier_ratio: float,
) -> dict[str, object]:
    kp_q, desc_q = sift.detectAndCompute(query_image, None)
    kp_c, desc_c = sift.detectAndCompute(cand_image, None)
    if desc_q is None or desc_c is None or len(kp_q) < 2 or len(kp_c) < 2:
        return {
            "keypoints_query": len(kp_q),
            "keypoints_candidate": len(kp_c),
            "match_count": 0,
            "inlier_count": 0,
            "inlier_ratio": 0.0,
            "reproj_error_mean": None,
            "geom_valid": False,
            "geom_score": -1.0,
        }

    knn = matcher.knnMatch(desc_c, desc_q, k=2)
    good = []
    for pair in knn:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < ratio_thresh * n.distance:
            good.append(m)

    match_count = len(good)
    if match_count < min_homography_matches:
        return {
            "keypoints_query": len(kp_q),
            "keypoints_candidate": len(kp_c),
            "match_count": match_count,
            "inlier_count": 0,
            "inlier_ratio": 0.0,
            "reproj_error_mean": None,
            "geom_valid": False,
            "geom_score": -1.0,
        }

    src_pts = np.float32([kp_c[m.queryIdx].pt for m in good])
    dst_pts = np.float32([kp_q[m.trainIdx].pt for m in good])
    homography, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, ransac_reproj_thresh)
    if homography is None or mask is None:
        return {
            "keypoints_query": len(kp_q),
            "keypoints_candidate": len(kp_c),
            "match_count": match_count,
            "inlier_count": 0,
            "inlier_ratio": 0.0,
            "reproj_error_mean": None,
            "geom_valid": False,
            "geom_score": -1.0,
        }

    inlier_count = int(mask.sum())
    inlier_ratio = float(inlier_count / match_count) if match_count else 0.0
    reproj_error_mean = compute_reproj_error(homography, src_pts, dst_pts, mask)
    geom_valid = inlier_count >= min_inliers and inlier_ratio >= min_inlier_ratio
    geom_score = (
        float(inlier_count * 1000.0 + inlier_ratio * 100.0 - (reproj_error_mean or 999.0))
        if geom_valid
        else -1.0
    )
    return {
        "keypoints_query": len(kp_q),
        "keypoints_candidate": len(kp_c),
        "match_count": match_count,
        "inlier_count": inlier_count,
        "inlier_ratio": inlier_ratio,
        "reproj_error_mean": reproj_error_mean,
        "geom_valid": geom_valid,
        "geom_score": geom_score,
    }


def hit_at_k(pred_ids: list[str], truth_ids: list[str], k: int) -> bool:
    truth = set(truth_ids)
    return any(pid in truth for pid in pred_ids[:k])


def sort_candidates(candidates: list[dict[str, object]], args: argparse.Namespace) -> None:
    if args.rerank_mode == "conservative_gate":
        for cand in candidates:
            cand["promote_flag"] = bool(cand["geom_valid"]) and int(cand["raw_rank"]) <= args.promotion_rank_gate
        candidates.sort(key=lambda x: (0 if x["promote_flag"] else 1, int(x["raw_rank"])))
        return

    for cand in candidates:
        cand["promote_flag"] = bool(cand["geom_valid"])
    candidates.sort(
        key=lambda x: (
            0 if x["geom_valid"] else 1,
            int(x["raw_rank"]),
            -float(x["inlier_count"]),
            -float(x["inlier_ratio"]),
            float("inf") if x["reproj_error_mean"] is None else float(x["reproj_error_mean"]),
            int(x["raw_rank"]),
        )
    )


def main() -> None:
    args = parse_args()
    output_csv = Path(args.output_csv)
    metrics_csv = Path(args.metrics_csv)
    summary_json = Path(args.summary_json)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    metrics_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_json.parent.mkdir(parents=True, exist_ok=True)

    queries = load_queries(Path(args.query_metadata_csv))
    tiles = load_tiles(Path(args.tiles_csv))
    retrieval = load_retrieval(Path(args.retrieval_csv), args.top_k)

    sift = cv2.SIFT_create()
    matcher = cv2.BFMatcher(cv2.NORM_L2)

    query_image_cache: dict[str, np.ndarray] = {}
    tile_image_cache: dict[str, np.ndarray] = {}
    per_query = []
    top1_errors = []
    hit1 = hit5 = hit10 = 0
    reciprocal_rank_sum = 0.0

    with metrics_csv.open("w", newline="", encoding="utf-8") as mf, output_csv.open(
        "w", newline="", encoding="utf-8"
    ) as of:
        metrics_writer = csv.writer(mf)
        metrics_writer.writerow(
            [
                "query_id",
                "candidate_tile_id",
                "raw_rank",
                "global_score",
                "candidate_scale_level_m",
                "keypoints_query",
                "keypoints_candidate",
                "match_count",
                "inlier_count",
                "inlier_ratio",
                "reproj_error_mean",
                "geom_valid",
                "geom_score",
                "promote_flag",
                "is_truth_hit",
            ]
        )
        rerank_writer = csv.writer(of)
        rerank_writer.writerow(
            [
                "query_id",
                "rank",
                "raw_rank",
                "candidate_tile_id",
                "global_score",
                "candidate_scale_level_m",
                "candidate_center_x",
                "candidate_center_y",
                "match_count",
                "inlier_count",
                "inlier_ratio",
                "reproj_error_mean",
                "geom_valid",
                "geom_score",
                "is_truth_hit",
            ]
        )

        for query_id, query_meta in queries.items():
            query_path = Path(str(query_meta["image_path"]))
            if query_id not in query_image_cache:
                query_image_cache[query_id] = read_gray(query_path)
            query_image = query_image_cache[query_id]
            candidates = []
            for item in retrieval.get(query_id, []):
                tile_id = str(item["candidate_tile_id"])
                tile_meta = tiles[tile_id]
                tile_path = Path(str(tile_meta["image_path"]))
                if tile_id not in tile_image_cache:
                    tile_image_cache[tile_id] = read_gray(tile_path)
                metrics = verify_pair(
                    sift=sift,
                    matcher=matcher,
                    query_image=query_image,
                    cand_image=tile_image_cache[tile_id],
                    ratio_thresh=args.ratio_thresh,
                    ransac_reproj_thresh=args.ransac_reproj_thresh,
                    min_homography_matches=args.min_homography_matches,
                    min_inliers=args.min_inliers,
                    min_inlier_ratio=args.min_inlier_ratio,
                )
                is_truth_hit = tile_id in query_meta["truth_tile_ids"]
                metrics_writer.writerow(
                    [
                        query_id,
                        tile_id,
                        item["raw_rank"],
                        item["global_score"],
                        tile_meta["scale_level_m"],
                        metrics["keypoints_query"],
                        metrics["keypoints_candidate"],
                        metrics["match_count"],
                        metrics["inlier_count"],
                        metrics["inlier_ratio"],
                        metrics["reproj_error_mean"],
                        int(bool(metrics["geom_valid"])),
                        metrics["geom_score"],
                        int(is_truth_hit),
                    ]
                )
                candidates.append(
                    {
                        **item,
                        **metrics,
                        "promote_flag": False,
                        "candidate_tile_id": tile_id,
                        "candidate_scale_level_m": tile_meta["scale_level_m"],
                        "candidate_center_x": tile_meta["center_x"],
                        "candidate_center_y": tile_meta["center_y"],
                        "is_truth_hit": is_truth_hit,
                    }
                )

            sort_candidates(candidates, args)

            pred_ids = [str(x["candidate_tile_id"]) for x in candidates]
            first_hit_rank = None
            top1_error_m = None
            for rank, cand in enumerate(candidates, start=1):
                if first_hit_rank is None and cand["is_truth_hit"]:
                    first_hit_rank = rank
                if rank == 1:
                    dx = float(cand["candidate_center_x"]) - float(query_meta["center_x"])
                    dy = float(cand["candidate_center_y"]) - float(query_meta["center_y"])
                    top1_error_m = math.hypot(dx, dy)
                rerank_writer.writerow(
                    [
                        query_id,
                        rank,
                        cand["raw_rank"],
                        cand["candidate_tile_id"],
                        cand["global_score"],
                        cand["candidate_scale_level_m"],
                        cand["candidate_center_x"],
                        cand["candidate_center_y"],
                        cand["match_count"],
                        cand["inlier_count"],
                        cand["inlier_ratio"],
                        cand["reproj_error_mean"],
                        int(bool(cand["geom_valid"])),
                        cand["geom_score"],
                        int(bool(cand["promote_flag"])),
                        int(cand["is_truth_hit"]),
                    ]
                )

            q_hit1 = hit_at_k(pred_ids, query_meta["truth_tile_ids"], 1)
            q_hit5 = hit_at_k(pred_ids, query_meta["truth_tile_ids"], 5)
            q_hit10 = hit_at_k(pred_ids, query_meta["truth_tile_ids"], 10)
            hit1 += int(q_hit1)
            hit5 += int(q_hit5)
            hit10 += int(q_hit10)
            reciprocal_rank = 0.0 if first_hit_rank is None else 1.0 / first_hit_rank
            reciprocal_rank_sum += reciprocal_rank
            if top1_error_m is not None:
                top1_errors.append(top1_error_m)
            per_query.append(
                {
                    "query_id": query_id,
                    "truth_tile_ids": query_meta["truth_tile_ids"],
                    "topk_tile_ids": pred_ids,
                    "hit@1": q_hit1,
                    "hit@5": q_hit5,
                    "hit@10": q_hit10,
                    "reciprocal_rank": reciprocal_rank,
                    "top1_error_m": top1_error_m,
                }
            )

    total = len(per_query)
    summary = {
        "top_k": args.top_k,
        "query_count": total,
        "recall@1": hit1 / total if total else 0.0,
        "recall@5": hit5 / total if total else 0.0,
        "recall@10": hit10 / total if total else 0.0,
        "mrr": reciprocal_rank_sum / total if total else 0.0,
        "top1_error_m_mean": sum(top1_errors) / len(top1_errors) if top1_errors else None,
        "hit_count@1": hit1,
        "hit_count@5": hit5,
        "hit_count@10": hit10,
        "per_query": per_query,
        "config": {
            "rerank_mode": args.rerank_mode,
            "promotion_rank_gate": args.promotion_rank_gate,
            "ratio_thresh": args.ratio_thresh,
            "ransac_reproj_thresh": args.ransac_reproj_thresh,
            "min_homography_matches": args.min_homography_matches,
            "min_inliers": args.min_inliers,
            "min_inlier_ratio": args.min_inlier_ratio,
        },
    }
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Reranked results saved to {output_csv}")
    print(f"Metrics saved to {metrics_csv}")
    print(f"Summary saved to {summary_json}")
    print(
        f"Finished. queries={total} "
        f"recall@1={summary['recall@1']:.3f} "
        f"recall@5={summary['recall@5']:.3f} "
        f"recall@10={summary['recall@10']:.3f} "
        f"mrr={summary['mrr']:.3f} "
        f"top1_error_m_mean={summary['top1_error_m_mean'] if summary['top1_error_m_mean'] is not None else 'na'}"
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Rerank coarse retrieval candidates with SuperPoint + LightGlue under strict-truth evaluation."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from lightglue import LightGlue, SuperPoint
from lightglue.utils import numpy_image_to_torch, rbd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-metadata-csv", required=True)
    parser.add_argument("--retrieval-csv", required=True)
    parser.add_argument("--tiles-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--metrics-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--max-num-keypoints", type=int, default=256)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--ransac-reproj-thresh", type=float, default=5.0)
    parser.add_argument("--min-inliers", type=int, default=5)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.5)
    parser.add_argument("--promotion-rank-gate", type=int, default=5)
    parser.add_argument("--ranking-mode", choices=["gate_only", "fused"], default="fused")
    parser.add_argument("--global-weight", type=float, default=0.4)
    parser.add_argument("--geom-weight", type=float, default=0.6)
    parser.add_argument("--valid-bonus", type=float, default=0.1)
    parser.add_argument("--promotion-bonus", type=float, default=0.05)
    return parser.parse_args()


def read_rgb(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGB"))


def load_queries(path: Path) -> dict[str, dict[str, object]]:
    queries: dict[str, dict[str, object]] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries[row["query_id"]] = {
                "image_path": row["image_path"],
                "truth_tile_ids": [x for x in row.get("truth_tile_ids", "").split("|") if x],
                "center_x": float(row.get("center_x", 0.0) or 0.0),
                "center_y": float(row.get("center_y", 0.0) or 0.0),
                "flight_id": row.get("flight_id", ""),
            }
    return queries


def load_tiles(path: Path) -> dict[str, dict[str, object]]:
    tiles: dict[str, dict[str, object]] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tiles[row["tile_id"]] = {
                "image_path": row["image_path"],
                "scale_level_m": row.get("tile_size_m", row.get("scale_level_m", "")),
                "center_x": float(row.get("center_x", 0.0) or 0.0),
                "center_y": float(row.get("center_y", 0.0) or 0.0),
            }
    return tiles


def load_retrieval(path: Path, top_k: int) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    with path.open("r", newline="", encoding="utf-8-sig") as f:
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


def build_extractor(max_num_keypoints: int, device: str):
    extractor = SuperPoint(max_num_keypoints=max_num_keypoints)
    matcher = LightGlue(features="superpoint")
    return extractor.eval().to(device), matcher.eval().to(device)


def extract_features(image: np.ndarray, extractor, device: str) -> dict[str, torch.Tensor]:
    tensor = numpy_image_to_torch(image).to(device)
    return extractor.extract(tensor)


def compute_reproj_error(homography: np.ndarray, src_pts: np.ndarray, dst_pts: np.ndarray, inlier_mask: np.ndarray) -> float | None:
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


@torch.inference_mode()
def verify_pair(feats_q, feats_c, matcher, ransac_reproj_thresh: float, min_inliers: int, min_inlier_ratio: float) -> dict[str, object]:
    match_out = rbd(matcher({"image0": feats_c, "image1": feats_q}))
    matches = match_out["matches"].detach().cpu().numpy()
    keypoints_q = rbd(feats_q)["keypoints"].detach().cpu().numpy()
    keypoints_c = rbd(feats_c)["keypoints"].detach().cpu().numpy()

    match_count = int(matches.shape[0])
    if match_count < 4:
        return {
            "keypoints_query": int(keypoints_q.shape[0]),
            "keypoints_candidate": int(keypoints_c.shape[0]),
            "match_count": match_count,
            "inlier_count": 0,
            "inlier_ratio": 0.0,
            "reproj_error_mean": None,
            "geom_valid": False,
            "geom_score": -1.0,
        }

    src_pts = keypoints_c[matches[:, 0]].astype(np.float32)
    dst_pts = keypoints_q[matches[:, 1]].astype(np.float32)
    homography, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, ransac_reproj_thresh)
    if homography is None or mask is None:
        return {
            "keypoints_query": int(keypoints_q.shape[0]),
            "keypoints_candidate": int(keypoints_c.shape[0]),
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
    geom_score = float(inlier_count * 1000.0 + inlier_ratio * 100.0 - (reproj_error_mean or 999.0)) if geom_valid else -1.0
    return {
        "keypoints_query": int(keypoints_q.shape[0]),
        "keypoints_candidate": int(keypoints_c.shape[0]),
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


def minmax_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    vmin = min(values)
    vmax = max(values)
    if math.isclose(vmin, vmax):
        return [1.0 for _ in values]
    return [(v - vmin) / (vmax - vmin) for v in values]


def attach_fused_scores(candidates: list[dict[str, object]], args: argparse.Namespace) -> None:
    global_scores = [float(x["global_score"]) for x in candidates]
    inlier_counts = [float(x["inlier_count"]) for x in candidates]
    reproj_errors = [float(x["reproj_error_mean"]) for x in candidates if x["reproj_error_mean"] is not None]
    norm_global = minmax_normalize(global_scores)
    max_inliers = max(inlier_counts) if inlier_counts else 0.0
    max_reproj = max(reproj_errors) if reproj_errors else 1.0

    for cand, global_norm in zip(candidates, norm_global):
        norm_inliers = float(cand["inlier_count"]) / max_inliers if max_inliers > 0 else 0.0
        inlier_ratio = float(cand["inlier_ratio"])
        reproj = cand["reproj_error_mean"]
        reproj_quality = 0.0
        if reproj is not None and max_reproj > 0:
            reproj_quality = max(0.0, 1.0 - float(reproj) / max_reproj)
        geom_quality = 0.5 * norm_inliers + 0.35 * inlier_ratio + 0.15 * reproj_quality
        if not bool(cand["geom_valid"]):
            geom_quality *= 0.5
        fused_score = args.global_weight * global_norm + args.geom_weight * geom_quality
        if bool(cand["geom_valid"]):
            fused_score += args.valid_bonus
        if bool(cand["geom_valid"]) and int(cand["raw_rank"]) <= args.promotion_rank_gate:
            fused_score += args.promotion_bonus
        cand["global_score_norm"] = global_norm
        cand["geom_quality"] = geom_quality
        cand["fused_score"] = fused_score


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

    extractor, matcher = build_extractor(args.max_num_keypoints, args.device)
    query_feat_cache: dict[str, dict[str, torch.Tensor]] = {}
    tile_feat_cache: dict[str, dict[str, torch.Tensor]] = {}

    per_query = []
    top1_errors = []
    hit1 = hit5 = hit10 = hit20 = 0
    reciprocal_rank_sum = 0.0

    with metrics_csv.open("w", newline="", encoding="utf-8-sig") as mf, output_csv.open("w", newline="", encoding="utf-8-sig") as of:
        metrics_writer = csv.writer(mf)
        metrics_writer.writerow(
            [
                "query_id", "candidate_tile_id", "raw_rank", "global_score", "candidate_scale_level_m",
                "keypoints_query", "keypoints_candidate", "match_count", "inlier_count", "inlier_ratio",
                "reproj_error_mean", "geom_valid", "geom_score", "global_score_norm", "geom_quality",
                "fused_score", "promote_flag", "is_strict_truth_hit",
            ]
        )
        rerank_writer = csv.writer(of)
        rerank_writer.writerow(
            [
                "query_id", "rank", "raw_rank", "candidate_tile_id", "global_score", "candidate_scale_level_m",
                "candidate_center_x", "candidate_center_y", "match_count", "inlier_count", "inlier_ratio",
                "reproj_error_mean", "geom_valid", "geom_score", "global_score_norm", "geom_quality",
                "fused_score", "promote_flag", "is_strict_truth_hit",
            ]
        )

        for query_id, query_meta in queries.items():
            if query_id not in query_feat_cache:
                query_feat_cache[query_id] = extract_features(read_rgb(Path(str(query_meta["image_path"]))), extractor, args.device)
            feats_q = query_feat_cache[query_id]
            candidates = []
            for item in retrieval.get(query_id, []):
                tile_id = str(item["candidate_tile_id"])
                tile_meta = tiles[tile_id]
                if tile_id not in tile_feat_cache:
                    tile_feat_cache[tile_id] = extract_features(read_rgb(Path(str(tile_meta["image_path"]))), extractor, args.device)
                feats_c = tile_feat_cache[tile_id]
                metrics = verify_pair(
                    feats_q=feats_q,
                    feats_c=feats_c,
                    matcher=matcher,
                    ransac_reproj_thresh=args.ransac_reproj_thresh,
                    min_inliers=args.min_inliers,
                    min_inlier_ratio=args.min_inlier_ratio,
                )
                is_truth_hit = tile_id in query_meta["truth_tile_ids"]
                promote_flag = bool(metrics["geom_valid"]) and int(item["raw_rank"]) <= args.promotion_rank_gate
                candidates.append(
                    {
                        **item,
                        **metrics,
                        "promote_flag": promote_flag,
                        "candidate_tile_id": tile_id,
                        "candidate_scale_level_m": tile_meta["scale_level_m"],
                        "candidate_center_x": tile_meta["center_x"],
                        "candidate_center_y": tile_meta["center_y"],
                        "is_strict_truth_hit": is_truth_hit,
                    }
                )

            attach_fused_scores(candidates, args)
            for cand in candidates:
                metrics_writer.writerow(
                    [
                        query_id, cand["candidate_tile_id"], cand["raw_rank"], cand["global_score"], cand["candidate_scale_level_m"],
                        cand["keypoints_query"], cand["keypoints_candidate"], cand["match_count"], cand["inlier_count"],
                        cand["inlier_ratio"], cand["reproj_error_mean"], int(bool(cand["geom_valid"])), cand["geom_score"],
                        cand["global_score_norm"], cand["geom_quality"], cand["fused_score"], int(bool(cand["promote_flag"])),
                        int(cand["is_strict_truth_hit"]),
                    ]
                )
            if args.ranking_mode == "fused":
                candidates.sort(key=lambda x: (-float(x["fused_score"]), int(x["raw_rank"])))
            else:
                candidates.sort(key=lambda x: (0 if x["promote_flag"] else 1, int(x["raw_rank"])))
            pred_ids = [str(x["candidate_tile_id"]) for x in candidates]
            first_hit_rank = None
            top1_error_m = None
            for rank, cand in enumerate(candidates, start=1):
                if first_hit_rank is None and cand["is_strict_truth_hit"]:
                    first_hit_rank = rank
                if rank == 1:
                    dx = float(cand["candidate_center_x"]) - float(query_meta["center_x"])
                    dy = float(cand["candidate_center_y"]) - float(query_meta["center_y"])
                    top1_error_m = math.hypot(dx, dy)
                rerank_writer.writerow(
                    [
                        query_id, rank, cand["raw_rank"], cand["candidate_tile_id"], cand["global_score"], cand["candidate_scale_level_m"],
                        cand["candidate_center_x"], cand["candidate_center_y"], cand["match_count"], cand["inlier_count"],
                        cand["inlier_ratio"], cand["reproj_error_mean"], int(bool(cand["geom_valid"])), cand["geom_score"],
                        cand["global_score_norm"], cand["geom_quality"], cand["fused_score"], int(bool(cand["promote_flag"])),
                        int(cand["is_strict_truth_hit"]),
                    ]
                )

            q_hit1 = hit_at_k(pred_ids, query_meta["truth_tile_ids"], 1)
            q_hit5 = hit_at_k(pred_ids, query_meta["truth_tile_ids"], 5)
            q_hit10 = hit_at_k(pred_ids, query_meta["truth_tile_ids"], 10)
            q_hit20 = hit_at_k(pred_ids, query_meta["truth_tile_ids"], 20)
            hit1 += int(q_hit1)
            hit5 += int(q_hit5)
            hit10 += int(q_hit10)
            hit20 += int(q_hit20)
            reciprocal_rank = 0.0 if first_hit_rank is None else 1.0 / first_hit_rank
            reciprocal_rank_sum += reciprocal_rank
            if top1_error_m is not None:
                top1_errors.append(top1_error_m)
            per_query.append(
                {
                    "query_id": query_id,
                    "truth_tile_ids": query_meta["truth_tile_ids"],
                    "first_strict_truth_rank": first_hit_rank,
                    "strict_hit@1": q_hit1,
                    "strict_hit@5": q_hit5,
                    "strict_hit@10": q_hit10,
                    "strict_hit@20": q_hit20,
                    "strict_reciprocal_rank": reciprocal_rank,
                    "top1_error_m": top1_error_m,
                }
            )

    total = len(per_query)
    summary = {
        "top_k": args.top_k,
        "query_count": total,
        "strict_recall@1": hit1 / total if total else 0.0,
        "strict_recall@5": hit5 / total if total else 0.0,
        "strict_recall@10": hit10 / total if total else 0.0,
        "strict_recall@20": hit20 / total if total else 0.0,
        "strict_mrr": reciprocal_rank_sum / total if total else 0.0,
        "top1_error_m_mean": sum(top1_errors) / len(top1_errors) if top1_errors else None,
        "strict_hit_count@1": hit1,
        "strict_hit_count@5": hit5,
        "strict_hit_count@10": hit10,
        "strict_hit_count@20": hit20,
        "per_query": per_query,
        "config": {
            "feature_backend": "superpoint",
            "max_num_keypoints": args.max_num_keypoints,
            "device": args.device,
            "promotion_rank_gate": args.promotion_rank_gate,
            "ransac_reproj_thresh": args.ransac_reproj_thresh,
            "min_inliers": args.min_inliers,
            "min_inlier_ratio": args.min_inlier_ratio,
            "ranking_mode": args.ranking_mode,
            "global_weight": args.global_weight,
            "geom_weight": args.geom_weight,
            "valid_bonus": args.valid_bonus,
            "promotion_bonus": args.promotion_bonus,
        },
    }
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Reranked results saved to {output_csv}")
    print(f"Metrics saved to {metrics_csv}")
    print(f"Summary saved to {summary_json}")
    print(
        f"Finished. queries={total} strict_recall@1={summary['strict_recall@1']:.3f} "
        f"strict_recall@5={summary['strict_recall@5']:.3f} strict_recall@10={summary['strict_recall@10']:.3f} "
        f"strict_recall@20={summary['strict_recall@20']:.3f} strict_mrr={summary['strict_mrr']:.3f}"
    )


if __name__ == "__main__":
    main()

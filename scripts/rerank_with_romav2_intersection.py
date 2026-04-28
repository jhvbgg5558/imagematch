#!/usr/bin/env python3
"""Rerank coarse retrieval candidates with RoMa v2 under intersection-truth evaluation."""

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
from romav2 import RoMaV2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-metadata-csv", required=True)
    parser.add_argument("--retrieval-csv", required=True)
    parser.add_argument("--tiles-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--metrics-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--setting", default="satast")
    parser.add_argument("--sample-count", type=int, default=5000)
    parser.add_argument("--ransac-reproj-thresh", type=float, default=4.0)
    parser.add_argument("--min-inliers", type=int, default=20)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.01)
    parser.add_argument("--promotion-rank-gate", type=int, default=5)
    parser.add_argument("--ranking-mode", choices=["gate_only", "fused", "inlier_count_only"], default="fused")
    parser.add_argument("--global-weight", type=float, default=0.4)
    parser.add_argument("--geom-weight", type=float, default=0.6)
    parser.add_argument("--valid-bonus", type=float, default=0.1)
    parser.add_argument("--promotion-bonus", type=float, default=0.05)
    parser.add_argument("--query-id", action="append", default=[], help="Optional query IDs to process.")
    parser.add_argument(
        "--pose-matches-csv",
        default=None,
        help="Optional CSV path for point-level RoMa matches reusable by the formal pose pipeline.",
    )
    return parser.parse_args()


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


def build_pose_match_rows(
    kpts_q_np: np.ndarray,
    kpts_c_np: np.ndarray,
    overlap_np: np.ndarray,
    inlier_mask: np.ndarray,
) -> list[dict[str, object]]:
    """Build the point-level row payload consumed by pose-v1 correspondence prep."""
    rows: list[dict[str, object]] = []
    for idx, (q_pt, c_pt) in enumerate(zip(kpts_q_np, kpts_c_np), start=1):
        rows.append(
            {
                "row_id": idx,
                "query_x": f"{float(q_pt[0]):.6f}",
                "query_y": f"{float(q_pt[1]):.6f}",
                "dom_pixel_x": f"{float(c_pt[0]):.6f}",
                "dom_pixel_y": f"{float(c_pt[1]):.6f}",
                "match_score": f"{float(overlap_np[idx - 1]):.6f}" if idx - 1 < len(overlap_np) else "",
                "is_inlier": int(bool(inlier_mask[idx - 1])) if idx - 1 < len(inlier_mask) else 0,
            }
        )
    return rows


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
def verify_pair(
    model: RoMaV2,
    query_path: Path,
    candidate_path: Path,
    sample_count: int,
    ransac_reproj_thresh: float,
    min_inliers: int,
    min_inlier_ratio: float,
) -> dict[str, object]:
    preds = model.match(query_path, candidate_path)
    matches, overlap, precision_qc, precision_cq = model.sample(preds, sample_count)

    query_img = cv2.imread(str(query_path))
    cand_img = cv2.imread(str(candidate_path))
    if query_img is None or cand_img is None:
        raise FileNotFoundError(f"Failed to read query/candidate image: {query_path} / {candidate_path}")
    hq, wq = query_img.shape[:2]
    hc, wc = cand_img.shape[:2]

    kpts_q, kpts_c = model.to_pixel_coordinates(matches, hq, wq, hc, wc)
    kpts_q_np = kpts_q.detach().cpu().numpy().astype(np.float32)
    kpts_c_np = kpts_c.detach().cpu().numpy().astype(np.float32)
    overlap_np = overlap.detach().cpu().numpy().astype(np.float32)

    match_count = int(len(kpts_q_np))
    zero_inliers = np.zeros((match_count,), dtype=bool)
    if match_count < 4:
        return {
            "match_count": match_count,
            "romav2_match_score": float(overlap_np.mean()) if match_count else 0.0,
            "inlier_count": 0,
            "inlier_ratio": 0.0,
            "reproj_error_mean": None,
            "geom_valid": False,
            "geom_score": -1.0,
            "pose_match_rows": build_pose_match_rows(kpts_q_np, kpts_c_np, overlap_np, zero_inliers),
        }

    homography, mask = cv2.findHomography(
        kpts_c_np,
        kpts_q_np,
        method=cv2.USAC_MAGSAC,
        ransacReprojThreshold=ransac_reproj_thresh,
        confidence=0.999999,
        maxIters=10000,
    )
    if homography is None or mask is None:
        return {
            "match_count": match_count,
            "romav2_match_score": float(overlap_np.mean()),
            "inlier_count": 0,
            "inlier_ratio": 0.0,
            "reproj_error_mean": None,
            "geom_valid": False,
            "geom_score": -1.0,
            "pose_match_rows": build_pose_match_rows(kpts_q_np, kpts_c_np, overlap_np, zero_inliers),
        }

    inlier_count = int(mask.sum())
    inlier_ratio = float(inlier_count / match_count) if match_count else 0.0
    reproj_error_mean = compute_reproj_error(homography, kpts_c_np, kpts_q_np, mask)
    geom_valid = inlier_count >= min_inliers and inlier_ratio >= min_inlier_ratio
    overlap_mean = float(overlap_np.mean()) if len(overlap_np) else 0.0
    geom_score = float(inlier_count * 1000.0 + inlier_ratio * 100.0 + overlap_mean * 10.0 - (reproj_error_mean or 999.0)) if geom_valid else -1.0
    return {
        "match_count": match_count,
        "romav2_match_score": overlap_mean,
        "inlier_count": inlier_count,
        "inlier_ratio": inlier_ratio,
        "reproj_error_mean": reproj_error_mean,
        "geom_valid": geom_valid,
        "geom_score": geom_score,
        "pose_match_rows": build_pose_match_rows(kpts_q_np, kpts_c_np, overlap_np, mask.ravel().astype(bool)),
    }


def attach_fused_scores(candidates: list[dict[str, object]], args: argparse.Namespace) -> None:
    global_scores = [float(x["global_score"]) for x in candidates]
    roma_scores = [float(x["romav2_match_score"]) for x in candidates]
    inlier_counts = [float(x["inlier_count"]) for x in candidates]
    reproj_errors = [float(x["reproj_error_mean"]) for x in candidates if x["reproj_error_mean"] is not None]
    norm_global = minmax_normalize(global_scores)
    norm_roma = minmax_normalize(roma_scores)
    max_inliers = max(inlier_counts) if inlier_counts else 0.0
    max_reproj = max(reproj_errors) if reproj_errors else 1.0

    for cand, global_norm, roma_norm in zip(candidates, norm_global, norm_roma):
        norm_inliers = float(cand["inlier_count"]) / max_inliers if max_inliers > 0 else 0.0
        inlier_ratio = float(cand["inlier_ratio"])
        reproj = cand["reproj_error_mean"]
        reproj_quality = 0.0
        if reproj is not None and max_reproj > 0:
            reproj_quality = max(0.0, 1.0 - float(reproj) / max_reproj)
        geom_quality = 0.4 * norm_inliers + 0.25 * inlier_ratio + 0.2 * roma_norm + 0.15 * reproj_quality
        if not bool(cand["geom_valid"]):
            geom_quality *= 0.5
        fused_score = args.global_weight * global_norm + args.geom_weight * geom_quality
        if bool(cand["geom_valid"]):
            fused_score += args.valid_bonus
        if bool(cand["geom_valid"]) and int(cand["raw_rank"]) <= args.promotion_rank_gate:
            fused_score += args.promotion_bonus
        cand["global_score_norm"] = global_norm
        cand["romav2_score_norm"] = roma_norm
        cand["geom_quality"] = geom_quality
        cand["fused_score"] = fused_score


def ranking_sort_key(candidate: dict[str, object], ranking_mode: str) -> tuple[object, ...]:
    """Return a stable sort key for the requested reranking mode."""
    reproj = candidate["reproj_error_mean"]
    reproj_value = float(reproj) if reproj is not None else float("inf")
    raw_rank = int(candidate["raw_rank"])

    if ranking_mode == "fused":
        return (-float(candidate["fused_score"]), raw_rank)
    if ranking_mode == "inlier_count_only":
        return (
            0 if bool(candidate["geom_valid"]) else 1,
            -int(candidate["inlier_count"]),
            raw_rank,
            reproj_value,
        )
    return (0 if bool(candidate["promote_flag"]) else 1, raw_rank)


def main() -> None:
    args = parse_args()
    output_csv = Path(args.output_csv)
    metrics_csv = Path(args.metrics_csv)
    summary_json = Path(args.summary_json)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    metrics_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    pose_matches_csv = Path(args.pose_matches_csv) if args.pose_matches_csv else None
    if pose_matches_csv is not None:
        pose_matches_csv.parent.mkdir(parents=True, exist_ok=True)

    queries = load_queries(Path(args.query_metadata_csv))
    selected_query_ids = set(args.query_id)
    if selected_query_ids:
        queries = {query_id: row for query_id, row in queries.items() if query_id in selected_query_ids}
        if not queries:
            raise SystemExit(f"no requested query IDs found in {args.query_metadata_csv}: {sorted(selected_query_ids)}")
    tiles = load_tiles(Path(args.tiles_csv))
    retrieval = load_retrieval(Path(args.retrieval_csv), args.top_k)
    model = build_model(args.setting, args.device)

    per_query = []
    top1_errors = []
    hit_counts = {1: 0, 5: 0, 10: 0, 20: 0}
    reciprocal_rank_sum = 0.0

    pose_handle = pose_matches_csv.open("w", newline="", encoding="utf-8-sig") if pose_matches_csv is not None else None
    with metrics_csv.open("w", newline="", encoding="utf-8-sig") as mf, output_csv.open("w", newline="", encoding="utf-8-sig") as of:
        metrics_writer = csv.writer(mf)
        metrics_writer.writerow(
            [
                "query_id", "candidate_tile_id", "raw_rank", "global_score", "candidate_scale_level_m",
                "match_count", "romav2_match_score", "inlier_count", "inlier_ratio", "reproj_error_mean",
                "geom_valid", "geom_score", "global_score_norm", "romav2_score_norm", "geom_quality",
                "fused_score", "promote_flag", "is_intersection_truth_hit",
            ]
        )
        rerank_writer = csv.writer(of)
        rerank_writer.writerow(
            [
                "query_id", "rank", "raw_rank", "candidate_tile_id", "global_score", "candidate_scale_level_m",
                "candidate_center_x", "candidate_center_y", "match_count", "romav2_match_score", "inlier_count",
                "inlier_ratio", "reproj_error_mean", "geom_valid", "geom_score", "global_score_norm",
                "romav2_score_norm", "geom_quality", "fused_score", "promote_flag", "is_intersection_truth_hit",
            ]
        )
        pose_writer = None
        if pose_handle is not None:
            pose_writer = csv.writer(pose_handle)
            pose_writer.writerow(
                [
                    "query_id",
                    "candidate_id",
                    "candidate_rank",
                    "row_id",
                    "query_x",
                    "query_y",
                    "dom_pixel_x",
                    "dom_pixel_y",
                    "match_score",
                    "is_inlier",
                ]
            )

        for query_id, query_meta in queries.items():
            candidates = []
            for item in retrieval.get(query_id, []):
                tile_id = str(item["candidate_tile_id"])
                tile_meta = tiles[tile_id]
                metrics = verify_pair(
                    model=model,
                    query_path=Path(str(query_meta["image_path"])),
                    candidate_path=Path(str(tile_meta["image_path"])),
                    sample_count=args.sample_count,
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
                        "is_intersection_truth_hit": is_truth_hit,
                    }
                )

            attach_fused_scores(candidates, args)
            for cand in candidates:
                metrics_writer.writerow(
                    [
                        query_id, cand["candidate_tile_id"], cand["raw_rank"], cand["global_score"], cand["candidate_scale_level_m"],
                        cand["match_count"], cand["romav2_match_score"], cand["inlier_count"], cand["inlier_ratio"],
                        cand["reproj_error_mean"], int(bool(cand["geom_valid"])), cand["geom_score"], cand["global_score_norm"],
                        cand["romav2_score_norm"], cand["geom_quality"], cand["fused_score"], int(bool(cand["promote_flag"])),
                        int(cand["is_intersection_truth_hit"]),
                    ]
                )

            candidates.sort(key=lambda x: ranking_sort_key(x, args.ranking_mode))

            pred_ids = [str(x["candidate_tile_id"]) for x in candidates]
            first_hit_rank = None
            top1_error_m = None
            for rank, cand in enumerate(candidates, start=1):
                if first_hit_rank is None and cand["is_intersection_truth_hit"]:
                    first_hit_rank = rank
                if rank == 1:
                    dx = float(cand["candidate_center_x"]) - float(query_meta["center_x"])
                    dy = float(cand["candidate_center_y"]) - float(query_meta["center_y"])
                    top1_error_m = math.hypot(dx, dy)
                rerank_writer.writerow(
                    [
                        query_id, rank, cand["raw_rank"], cand["candidate_tile_id"], cand["global_score"], cand["candidate_scale_level_m"],
                        cand["candidate_center_x"], cand["candidate_center_y"], cand["match_count"], cand["romav2_match_score"],
                        cand["inlier_count"], cand["inlier_ratio"], cand["reproj_error_mean"], int(bool(cand["geom_valid"])),
                        cand["geom_score"], cand["global_score_norm"], cand["romav2_score_norm"], cand["geom_quality"],
                        cand["fused_score"], int(bool(cand["promote_flag"])), int(cand["is_intersection_truth_hit"]),
                    ]
                )
                if pose_writer is not None:
                    for match_row in cand.get("pose_match_rows", []):
                        pose_writer.writerow(
                            [
                                query_id,
                                cand["candidate_tile_id"],
                                rank,
                                match_row["row_id"],
                                match_row["query_x"],
                                match_row["query_y"],
                                match_row["dom_pixel_x"],
                                match_row["dom_pixel_y"],
                                match_row["match_score"],
                                match_row["is_inlier"],
                            ]
                        )

            q_hits = {k: hit_at_k(pred_ids, query_meta["truth_tile_ids"], k) for k in hit_counts}
            for k, hit in q_hits.items():
                hit_counts[k] += int(hit)
            reciprocal_rank = 0.0 if first_hit_rank is None else 1.0 / first_hit_rank
            reciprocal_rank_sum += reciprocal_rank
            if top1_error_m is not None:
                top1_errors.append(top1_error_m)
            per_query.append(
                {
                    "query_id": query_id,
                    "flight_id": query_meta["flight_id"],
                    "truth_count": len(query_meta["truth_tile_ids"]),
                    "first_truth_rank": first_hit_rank,
                    "intersection_hit@1": q_hits[1],
                    "intersection_hit@5": q_hits[5],
                    "intersection_hit@10": q_hits[10],
                    "intersection_hit@20": q_hits[20],
                    "intersection_reciprocal_rank": reciprocal_rank,
                    "top1_error_m": top1_error_m,
                }
            )

    total = len(per_query)
    summary = {
        "top_k": args.top_k,
        "query_count": total,
        "intersection_recall@1": hit_counts[1] / total if total else 0.0,
        "intersection_recall@5": hit_counts[5] / total if total else 0.0,
        "intersection_recall@10": hit_counts[10] / total if total else 0.0,
        "intersection_recall@20": hit_counts[20] / total if total else 0.0,
        "intersection_mrr": reciprocal_rank_sum / total if total else 0.0,
        "top1_error_m_mean": sum(top1_errors) / len(top1_errors) if top1_errors else None,
        "intersection_hit_count@1": hit_counts[1],
        "intersection_hit_count@5": hit_counts[5],
        "intersection_hit_count@10": hit_counts[10],
        "intersection_hit_count@20": hit_counts[20],
        "per_query": per_query,
        "config": {
            "matcher_backend": "romav2",
            "device": args.device,
            "setting": args.setting,
            "sample_count": args.sample_count,
            "promotion_rank_gate": args.promotion_rank_gate,
            "ransac_reproj_thresh": args.ransac_reproj_thresh,
            "min_inliers": args.min_inliers,
            "min_inlier_ratio": args.min_inlier_ratio,
            "ranking_mode": args.ranking_mode,
            "global_weight": args.global_weight,
            "geom_weight": args.geom_weight,
            "valid_bonus": args.valid_bonus,
            "promotion_bonus": args.promotion_bonus,
            "rank_score_name": "inlier_count" if args.ranking_mode == "inlier_count_only" else "fused_score",
        },
    }
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    if pose_handle is not None:
        pose_handle.close()

    print(f"Reranked results saved to {output_csv}")
    print(f"Metrics saved to {metrics_csv}")
    print(f"Summary saved to {summary_json}")
    if pose_matches_csv is not None:
        print(f"Pose matches saved to {pose_matches_csv}")


if __name__ == "__main__":
    main()

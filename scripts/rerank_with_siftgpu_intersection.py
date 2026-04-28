#!/usr/bin/env python3
"""Rerank coarse retrieval candidates with COLMAP SiftGPU matches.

Purpose:
- replace RoMa v2 geometry verification with SIFTGPU-style SIFT feature
  extraction and matching through COLMAP's GPU SIFT interface;
- export the same candidate-level rerank schema and point-level pose-match
  schema used by the formal pose pipeline.

Main inputs:
- query metadata CSV, coarse retrieval CSV, and candidate tile CSV.

Main outputs:
- reranked Top-K CSV, per-query geometry metrics CSV, summary JSON, and
  optional `siftgpu_matches_for_pose.csv`.

Applicable task constraints:
- query images have no runtime geolocation metadata and are not assumed to be
  orthophotos;
- this script requires GPU SIFT to run successfully and does not silently fall
  back to CPU SIFT for formal G03 results.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sqlite3
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np


PAIR_ID_MOD = 2147483647


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-metadata-csv", required=True)
    parser.add_argument("--retrieval-csv", required=True)
    parser.add_argument("--tiles-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--metrics-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--colmap-bin", default="colmap")
    parser.add_argument("--siftgpu-bin", default=None)
    parser.add_argument("--max-num-features", type=int, default=8192)
    parser.add_argument("--ransac-reproj-thresh", type=float, default=4.0)
    parser.add_argument("--min-inliers", type=int, default=20)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.01)
    parser.add_argument("--promotion-rank-gate", type=int, default=5)
    parser.add_argument("--ranking-mode", choices=["gate_only", "fused", "inlier_count_only"], default="inlier_count_only")
    parser.add_argument("--global-weight", type=float, default=0.4)
    parser.add_argument("--geom-weight", type=float, default=0.6)
    parser.add_argument("--valid-bonus", type=float, default=0.1)
    parser.add_argument("--promotion-bonus", type=float, default=0.05)
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--pose-matches-csv", default=None)
    return parser.parse_args()


def load_queries(path: Path) -> dict[str, dict[str, object]]:
    out = {}
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            out[row["query_id"]] = {
                "image_path": row["image_path"],
                "truth_tile_ids": [x for x in row.get("truth_tile_ids", "").split("|") if x],
                "center_x": float(row.get("center_x", 0.0) or 0.0),
                "center_y": float(row.get("center_y", 0.0) or 0.0),
                "flight_id": row.get("flight_id", ""),
            }
    return out


def load_tiles(path: Path) -> dict[str, dict[str, object]]:
    out = {}
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            out[row["tile_id"]] = {
                "image_path": row["image_path"],
                "scale_level_m": row.get("tile_size_m", row.get("scale_level_m", "")),
                "center_x": float(row.get("center_x", 0.0) or 0.0),
                "center_y": float(row.get("center_y", 0.0) or 0.0),
            }
    return out


def load_retrieval(path: Path, top_k: int) -> dict[str, list[dict[str, object]]]:
    grouped = defaultdict(list)
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            rank = int(row["rank"])
            if rank <= top_k:
                grouped[row["query_id"]].append(
                    {"raw_rank": rank, "candidate_tile_id": row["candidate_tile_id"], "global_score": float(row["score"])}
                )
    for items in grouped.values():
        items.sort(key=lambda item: int(item["raw_rank"]))
    return grouped


def hit_at_k(pred_ids: list[str], truth_ids: list[str], k: int) -> bool:
    truth = set(truth_ids)
    return any(pid in truth for pid in pred_ids[:k])


def minmax_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    vmin, vmax = min(values), max(values)
    if math.isclose(vmin, vmax):
        return [1.0 for _ in values]
    return [(value - vmin) / (vmax - vmin) for value in values]


def pair_id(image_id1: int, image_id2: int) -> int:
    a, b = sorted((int(image_id1), int(image_id2)))
    return PAIR_ID_MOD * a + b


def read_blob_array(blob: bytes, dtype: np.dtype, shape: tuple[int, int]) -> np.ndarray:
    if not blob:
        return np.empty((0, shape[1]), dtype=dtype)
    return np.frombuffer(blob, dtype=dtype).reshape(shape)


def run_siftgpu_cli_pair(siftgpu_bin: str, query_path: Path, candidate_path: Path, max_num_features: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with tempfile.TemporaryDirectory(prefix="siftgpu_cli_pair_") as tmp_raw:
        out_csv = Path(tmp_raw) / "matches.csv"
        cmd = [siftgpu_bin, str(query_path), str(candidate_path), str(out_csv), str(max_num_features)]
        completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if completed.returncode != 0:
            raise RuntimeError(f"SiftGPU pair matcher failed:\n{completed.stdout[-2000:]}")
        rows = []
        with out_csv.open("r", newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                rows.append(row)
        if not rows:
            return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32), np.empty((0,), bool)
        q_pts = np.array([[float(row["query_x"]), float(row["query_y"])] for row in rows], dtype=np.float32)
        c_pts = np.array([[float(row["dom_pixel_x"]), float(row["dom_pixel_y"])] for row in rows], dtype=np.float32)
        return q_pts, c_pts, np.ones((len(rows),), dtype=bool)


def run_colmap_pair(colmap_bin: str, query_path: Path, candidate_path: Path, max_num_features: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with tempfile.TemporaryDirectory(prefix="siftgpu_pair_") as tmp_raw:
        tmp = Path(tmp_raw)
        image_dir = tmp / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(query_path, image_dir / "query.jpg")
        shutil.copy2(candidate_path, image_dir / "candidate.png")
        db_path = tmp / "database.db"
        feature_cmd = [
            colmap_bin,
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
            str(max_num_features),
        ]
        match_cmd = [
            colmap_bin,
            "exhaustive_matcher",
            "--database_path",
            str(db_path),
            "--SiftMatching.use_gpu",
            "1",
        ]
        feature = subprocess.run(feature_cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if feature.returncode != 0:
            raise RuntimeError(f"COLMAP SiftGPU feature_extractor failed:\n{feature.stdout[-2000:]}")
        match = subprocess.run(match_cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if match.returncode != 0:
            raise RuntimeError(f"COLMAP SiftGPU exhaustive_matcher failed:\n{match.stdout[-2000:]}")

        con = sqlite3.connect(str(db_path))
        try:
            images = {name: image_id for image_id, name in con.execute("select image_id, name from images")}
            q_id = images["query.jpg"]
            c_id = images["candidate.png"]
            keypoints = {}
            for image_id, rows, cols, data in con.execute("select image_id, rows, cols, data from keypoints"):
                keypoints[image_id] = read_blob_array(data, np.float32, (rows, cols))[:, :2].astype(np.float32)
            pid = pair_id(q_id, c_id)
            geo_row = con.execute("select rows, cols, data from two_view_geometries where pair_id=?", (pid,)).fetchone()
            if geo_row is None or geo_row[0] == 0:
                return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32), np.empty((0,), bool)
            match_idx = read_blob_array(geo_row[2], np.uint32, (geo_row[0], geo_row[1]))
            q_idx = match_idx[:, 0] if q_id < c_id else match_idx[:, 1]
            c_idx = match_idx[:, 1] if q_id < c_id else match_idx[:, 0]
            q_pts = keypoints[q_id][q_idx]
            c_pts = keypoints[c_id][c_idx]
            return q_pts.astype(np.float32), c_pts.astype(np.float32), np.ones((len(q_pts),), dtype=bool)
        finally:
            con.close()


def compute_reproj_error(homography: np.ndarray, src_pts: np.ndarray, dst_pts: np.ndarray, inlier_mask: np.ndarray) -> float | None:
    if homography is None or inlier_mask is None or not np.any(inlier_mask):
        return None
    src_in = src_pts[inlier_mask].reshape(-1, 1, 2)
    dst_in = dst_pts[inlier_mask].reshape(-1, 2)
    proj = cv2.perspectiveTransform(src_in, homography).reshape(-1, 2)
    return float(np.mean(np.linalg.norm(proj - dst_in, axis=1)))


def pose_rows(q_pts: np.ndarray, c_pts: np.ndarray, inlier_mask: np.ndarray) -> list[dict[str, object]]:
    rows = []
    for idx, (q_pt, c_pt) in enumerate(zip(q_pts, c_pts), start=1):
        rows.append(
            {
                "row_id": idx,
                "query_x": f"{float(q_pt[0]):.6f}",
                "query_y": f"{float(q_pt[1]):.6f}",
                "dom_pixel_x": f"{float(c_pt[0]):.6f}",
                "dom_pixel_y": f"{float(c_pt[1]):.6f}",
                "match_score": "1.000000",
                "is_inlier": int(bool(inlier_mask[idx - 1])) if idx - 1 < len(inlier_mask) else 0,
            }
        )
    return rows


def verify_pair(args: argparse.Namespace, query_path: Path, candidate_path: Path) -> dict[str, object]:
    if args.siftgpu_bin:
        q_pts, c_pts, initial_inliers = run_siftgpu_cli_pair(args.siftgpu_bin, query_path, candidate_path, args.max_num_features)
    else:
        q_pts, c_pts, initial_inliers = run_colmap_pair(args.colmap_bin, query_path, candidate_path, args.max_num_features)
    match_count = int(len(q_pts))
    if match_count < 4:
        return {
            "match_count": match_count,
            "siftgpu_match_score": 0.0,
            "inlier_count": 0,
            "inlier_ratio": 0.0,
            "reproj_error_mean": None,
            "geom_valid": False,
            "geom_score": -1.0,
            "pose_match_rows": pose_rows(q_pts, c_pts, initial_inliers),
        }
    homography, mask = cv2.findHomography(
        c_pts,
        q_pts,
        method=cv2.USAC_MAGSAC,
        ransacReprojThreshold=args.ransac_reproj_thresh,
        confidence=0.999999,
        maxIters=10000,
    )
    if homography is None or mask is None:
        inliers = np.zeros((match_count,), dtype=bool)
    else:
        inliers = mask.ravel().astype(bool)
    inlier_count = int(inliers.sum())
    inlier_ratio = float(inlier_count / match_count) if match_count else 0.0
    reproj_error_mean = compute_reproj_error(homography, c_pts, q_pts, inliers) if homography is not None else None
    geom_valid = inlier_count >= args.min_inliers and inlier_ratio >= args.min_inlier_ratio
    score = inlier_ratio
    geom_score = float(inlier_count * 1000.0 + inlier_ratio * 100.0 + score * 10.0 - (reproj_error_mean or 999.0)) if geom_valid else -1.0
    return {
        "match_count": match_count,
        "siftgpu_match_score": score,
        "inlier_count": inlier_count,
        "inlier_ratio": inlier_ratio,
        "reproj_error_mean": reproj_error_mean,
        "geom_valid": geom_valid,
        "geom_score": geom_score,
        "pose_match_rows": pose_rows(q_pts, c_pts, inliers),
    }


def attach_fused_scores(candidates: list[dict[str, object]], args: argparse.Namespace) -> None:
    global_scores = [float(x["global_score"]) for x in candidates]
    sift_scores = [float(x["siftgpu_match_score"]) for x in candidates]
    inlier_counts = [float(x["inlier_count"]) for x in candidates]
    reproj_errors = [float(x["reproj_error_mean"]) for x in candidates if x["reproj_error_mean"] is not None]
    norm_global = minmax_normalize(global_scores)
    norm_sift = minmax_normalize(sift_scores)
    max_inliers = max(inlier_counts) if inlier_counts else 0.0
    max_reproj = max(reproj_errors) if reproj_errors else 1.0
    for cand, global_norm, sift_norm in zip(candidates, norm_global, norm_sift):
        norm_inliers = float(cand["inlier_count"]) / max_inliers if max_inliers > 0 else 0.0
        reproj = cand["reproj_error_mean"]
        reproj_quality = max(0.0, 1.0 - float(reproj) / max_reproj) if reproj is not None and max_reproj > 0 else 0.0
        geom_quality = 0.4 * norm_inliers + 0.25 * float(cand["inlier_ratio"]) + 0.2 * sift_norm + 0.15 * reproj_quality
        if not bool(cand["geom_valid"]):
            geom_quality *= 0.5
        fused = args.global_weight * global_norm + args.geom_weight * geom_quality
        if bool(cand["geom_valid"]):
            fused += args.valid_bonus
        if bool(cand["geom_valid"]) and int(cand["raw_rank"]) <= args.promotion_rank_gate:
            fused += args.promotion_bonus
        cand["global_score_norm"] = global_norm
        cand["siftgpu_score_norm"] = sift_norm
        cand["geom_quality"] = geom_quality
        cand["fused_score"] = fused


def ranking_sort_key(candidate: dict[str, object], ranking_mode: str) -> tuple[object, ...]:
    reproj = candidate["reproj_error_mean"]
    reproj_value = float(reproj) if reproj is not None else float("inf")
    raw_rank = int(candidate["raw_rank"])
    if ranking_mode == "fused":
        return (-float(candidate["fused_score"]), raw_rank)
    if ranking_mode == "inlier_count_only":
        return (0 if bool(candidate["geom_valid"]) else 1, -int(candidate["inlier_count"]), raw_rank, reproj_value)
    return (0 if bool(candidate["promote_flag"]) else 1, raw_rank)


def main() -> None:
    args = parse_args()
    if args.siftgpu_bin:
        if not Path(args.siftgpu_bin).exists():
            raise SystemExit(f"SiftGPU pair matcher not found: {args.siftgpu_bin}")
    elif not shutil.which(args.colmap_bin):
        raise SystemExit(f"COLMAP executable not found: {args.colmap_bin}")
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
    selected = set(args.query_id)
    if selected:
        queries = {qid: row for qid, row in queries.items() if qid in selected}
    tiles = load_tiles(Path(args.tiles_csv))
    retrieval = load_retrieval(Path(args.retrieval_csv), args.top_k)

    per_query = []
    top1_errors = []
    hit_counts = {1: 0, 5: 0, 10: 0, 20: 0}
    reciprocal_rank_sum = 0.0
    pose_handle = pose_matches_csv.open("w", newline="", encoding="utf-8-sig") if pose_matches_csv else None
    try:
        with metrics_csv.open("w", newline="", encoding="utf-8-sig") as mf, output_csv.open("w", newline="", encoding="utf-8-sig") as of:
            metrics_writer = csv.writer(mf)
            metrics_writer.writerow([
                "query_id", "candidate_tile_id", "raw_rank", "global_score", "candidate_scale_level_m",
                "match_count", "siftgpu_match_score", "inlier_count", "inlier_ratio", "reproj_error_mean",
                "geom_valid", "geom_score", "global_score_norm", "siftgpu_score_norm", "geom_quality",
                "fused_score", "promote_flag", "is_intersection_truth_hit",
            ])
            rerank_writer = csv.writer(of)
            rerank_writer.writerow([
                "query_id", "rank", "raw_rank", "candidate_tile_id", "global_score", "candidate_scale_level_m",
                "candidate_center_x", "candidate_center_y", "match_count", "siftgpu_match_score", "inlier_count",
                "inlier_ratio", "reproj_error_mean", "geom_valid", "geom_score", "global_score_norm",
                "siftgpu_score_norm", "geom_quality", "fused_score", "promote_flag", "is_intersection_truth_hit",
            ])
            pose_writer = None
            if pose_handle is not None:
                pose_writer = csv.writer(pose_handle)
                pose_writer.writerow([
                    "query_id", "candidate_id", "candidate_rank", "row_id", "query_x", "query_y",
                    "dom_pixel_x", "dom_pixel_y", "match_score", "is_inlier",
                ])

            for query_id, query_meta in queries.items():
                candidates = []
                for item in retrieval.get(query_id, []):
                    tile_id = str(item["candidate_tile_id"])
                    tile_meta = tiles[tile_id]
                    metrics = verify_pair(args, Path(str(query_meta["image_path"])), Path(str(tile_meta["image_path"])))
                    is_truth_hit = tile_id in query_meta["truth_tile_ids"]
                    candidates.append({
                        **item,
                        **metrics,
                        "promote_flag": bool(metrics["geom_valid"]) and int(item["raw_rank"]) <= args.promotion_rank_gate,
                        "candidate_tile_id": tile_id,
                        "candidate_scale_level_m": tile_meta["scale_level_m"],
                        "candidate_center_x": tile_meta["center_x"],
                        "candidate_center_y": tile_meta["center_y"],
                        "is_intersection_truth_hit": is_truth_hit,
                    })
                attach_fused_scores(candidates, args)
                for cand in candidates:
                    metrics_writer.writerow([
                        query_id, cand["candidate_tile_id"], cand["raw_rank"], cand["global_score"], cand["candidate_scale_level_m"],
                        cand["match_count"], cand["siftgpu_match_score"], cand["inlier_count"], cand["inlier_ratio"],
                        cand["reproj_error_mean"], int(bool(cand["geom_valid"])), cand["geom_score"], cand["global_score_norm"],
                        cand["siftgpu_score_norm"], cand["geom_quality"], cand["fused_score"], int(bool(cand["promote_flag"])),
                        int(cand["is_intersection_truth_hit"]),
                    ])
                candidates.sort(key=lambda x: ranking_sort_key(x, args.ranking_mode))
                pred_ids = [str(x["candidate_tile_id"]) for x in candidates]
                first_hit_rank = None
                top1_error_m = None
                for rank, cand in enumerate(candidates, start=1):
                    if first_hit_rank is None and cand["is_intersection_truth_hit"]:
                        first_hit_rank = rank
                    if rank == 1:
                        top1_error_m = math.hypot(float(cand["candidate_center_x"]) - float(query_meta["center_x"]), float(cand["candidate_center_y"]) - float(query_meta["center_y"]))
                    rerank_writer.writerow([
                        query_id, rank, cand["raw_rank"], cand["candidate_tile_id"], cand["global_score"], cand["candidate_scale_level_m"],
                        cand["candidate_center_x"], cand["candidate_center_y"], cand["match_count"], cand["siftgpu_match_score"],
                        cand["inlier_count"], cand["inlier_ratio"], cand["reproj_error_mean"], int(bool(cand["geom_valid"])),
                        cand["geom_score"], cand["global_score_norm"], cand["siftgpu_score_norm"], cand["geom_quality"],
                        cand["fused_score"], int(bool(cand["promote_flag"])), int(cand["is_intersection_truth_hit"]),
                    ])
                    if pose_writer is not None:
                        for match_row in cand.get("pose_match_rows", []):
                            pose_writer.writerow([
                                query_id, cand["candidate_tile_id"], rank, match_row["row_id"], match_row["query_x"],
                                match_row["query_y"], match_row["dom_pixel_x"], match_row["dom_pixel_y"],
                                match_row["match_score"], match_row["is_inlier"],
                            ])
                q_hits = {k: hit_at_k(pred_ids, query_meta["truth_tile_ids"], k) for k in hit_counts}
                for k, hit in q_hits.items():
                    hit_counts[k] += int(hit)
                reciprocal_rank = 0.0 if first_hit_rank is None else 1.0 / first_hit_rank
                reciprocal_rank_sum += reciprocal_rank
                if top1_error_m is not None:
                    top1_errors.append(top1_error_m)
                per_query.append({
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
                })
    finally:
        if pose_handle is not None:
            pose_handle.close()

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
            "matcher_backend": "colmap_siftgpu",
            "siftgpu_bin": args.siftgpu_bin or "",
            "max_num_features": args.max_num_features,
            "ranking_mode": args.ranking_mode,
            "cpu_fallback": False,
        },
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_csv)


if __name__ == "__main__":
    main()

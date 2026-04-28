#!/usr/bin/env python3
"""Render RoMa v2 Top-20 inlier correspondences for the current UAV retrieval task.

This script is a post-processing utility for the current task setting:
- the query is a single arbitrary UAV image,
- the query has no geographic metadata,
- the query is not guaranteed to be orthophoto,
- the visualization must reuse the locked `query v2 + intersection truth`
  formal rerank results without changing evaluation outputs.

Main inputs:
- existing RoMa v2 rerank results under `romav2_eval_2026-03-30_gpu/stage7`
- query image paths from `input_round/stage3/<flight_id>/queries.csv`
- satellite tile paths from the formal `tiles.csv`

Main outputs:
- per-pair visualization images under `new1output/romav2_top20_match_viz_2026-04-01/figures`
- `summary_top20_match_points.csv`
- `summary_top20_match_points.md`

Applicable constraints:
- recompute matches only for visualization; do not modify formal rerank CSV/JSON
- keep RoMa parameters aligned with the formal rerank round
- save a placeholder image and summary row when a pair cannot be visualized
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from romav2 import RoMaV2


QUERY_BORDER = (31, 119, 180)
TILE_BORDER_HIT = (26, 127, 55)
TILE_BORDER_MISS = (180, 35, 24)
TITLE_BAR = (24, 24, 24)
BG = (245, 245, 245)
LINE_COLOR = (46, 204, 113)
WARN_COLOR = (237, 137, 54)
TEXT_COLOR = (255, 255, 255)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--romav2-result-dir",
        default="/mnt/d/aiproject/imagematch/new1output/query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_gpu",
    )
    parser.add_argument(
        "--tiles-csv",
        default="/mnt/d/aiproject/imagematch/output/coverage_truth_200_300_500_700_dinov2_baseline/fixed_satellite_library/tiles.csv",
    )
    parser.add_argument(
        "--selected-summary-csv",
        default="/mnt/d/aiproject/imagematch/new1output/query_reselect_2026-03-26_v2/selected_queries/selected_images_summary.csv",
    )
    parser.add_argument(
        "--query-input-root",
        default="/mnt/d/aiproject/imagematch/new1output/query_reselect_2026-03-26_v2/query_inputs/images",
    )
    parser.add_argument(
        "--out-root",
        default="/mnt/d/aiproject/imagematch/new1output/romav2_top20_match_viz_2026-04-01",
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        help="overwrite any existing figures instead of reusing them",
    )
    parser.set_defaults(resume=True)
    parser.add_argument("--setting", default="satast")
    parser.add_argument("--sample-count", type=int, default=5000)
    parser.add_argument("--ransac-reproj-thresh", type=float, default=4.0)
    parser.add_argument("--min-inliers", type=int, default=20)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.01)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--target-long-side", type=int, default=900)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_rgb(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGB"))


def safe_name(text: str) -> str:
    return (
        text.replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace(" ", "_")
        .replace("(", "_")
        .replace(")", "_")
    )


def short_flight_name(flight_id: str) -> str:
    parts = flight_id.split("_")
    return parts[2] if len(parts) >= 3 else flight_id


def resize_with_scale(image: np.ndarray, target_long_side: int) -> tuple[np.ndarray, float]:
    height, width = image.shape[:2]
    long_side = max(height, width)
    if long_side <= target_long_side:
        return image, 1.0
    scale = target_long_side / float(long_side)
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    return resized, scale


def add_border(image: np.ndarray, color: tuple[int, int, int], width: int = 6) -> np.ndarray:
    height, width_img = image.shape[:2]
    canvas = np.full((height + 2 * width, width_img + 2 * width, 3), color, dtype=np.uint8)
    canvas[width : width + height, width : width + width_img] = image
    return canvas


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
def match_pair(
    model: RoMaV2,
    query_path: Path,
    tile_path: Path,
    sample_count: int,
    ransac_reproj_thresh: float,
    min_inliers: int,
    min_inlier_ratio: float,
) -> dict[str, object]:
    preds = model.match(query_path, tile_path)
    matches, overlap, _, _ = model.sample(preds, sample_count)

    query_img = cv2.imread(str(query_path))
    tile_img = cv2.imread(str(tile_path))
    if query_img is None or tile_img is None:
        raise FileNotFoundError(f"Failed to read image pair: {query_path} / {tile_path}")
    height_q, width_q = query_img.shape[:2]
    height_t, width_t = tile_img.shape[:2]

    kpts_q, kpts_t = model.to_pixel_coordinates(matches, height_q, width_q, height_t, width_t)
    kpts_q_np = kpts_q.detach().cpu().numpy().astype(np.float32)
    kpts_t_np = kpts_t.detach().cpu().numpy().astype(np.float32)
    overlap_np = overlap.detach().cpu().numpy().astype(np.float32)

    match_count = int(len(kpts_q_np))
    if match_count < 4:
        return {
            "query_keypoints": kpts_q_np,
            "tile_keypoints": kpts_t_np,
            "match_count": match_count,
            "inlier_mask": np.zeros((match_count,), dtype=bool),
            "inlier_count": 0,
            "inlier_ratio": 0.0,
            "reproj_error_mean": None,
            "geom_valid": False,
            "romav2_match_score": float(overlap_np.mean()) if match_count else 0.0,
            "status": "insufficient_matches",
        }

    homography, mask = cv2.findHomography(
        kpts_t_np,
        kpts_q_np,
        method=cv2.USAC_MAGSAC,
        ransacReprojThreshold=ransac_reproj_thresh,
        confidence=0.999999,
        maxIters=10000,
    )
    if homography is None or mask is None:
        inlier_mask = np.zeros((match_count,), dtype=bool)
    else:
        inlier_mask = mask.ravel().astype(bool)

    inlier_count = int(inlier_mask.sum())
    inlier_ratio = float(inlier_count / match_count) if match_count else 0.0
    reproj_error_mean = compute_reproj_error(homography, kpts_t_np, kpts_q_np, mask) if homography is not None and mask is not None else None
    geom_valid = inlier_count >= min_inliers and inlier_ratio >= min_inlier_ratio
    return {
        "query_keypoints": kpts_q_np,
        "tile_keypoints": kpts_t_np,
        "match_count": match_count,
        "inlier_mask": inlier_mask,
        "inlier_count": inlier_count,
        "inlier_ratio": inlier_ratio,
        "reproj_error_mean": reproj_error_mean,
        "geom_valid": geom_valid,
        "romav2_match_score": float(overlap_np.mean()) if match_count else 0.0,
        "status": "ok",
    }


def draw_pair(
    query_img: np.ndarray,
    tile_img: np.ndarray,
    query_keypoints: np.ndarray,
    tile_keypoints: np.ndarray,
    inlier_mask: np.ndarray,
    title: str,
    out_path: Path,
    tile_hit: bool,
    target_long_side: int,
) -> None:
    q_vis, q_scale = resize_with_scale(query_img, target_long_side)
    t_vis, t_scale = resize_with_scale(tile_img, target_long_side)

    q_vis = add_border(q_vis, QUERY_BORDER)
    t_vis = add_border(t_vis, TILE_BORDER_HIT if tile_hit else TILE_BORDER_MISS)

    title_h = 44
    gap = 0
    canvas_h = max(q_vis.shape[0], t_vis.shape[0]) + title_h
    canvas_w = q_vis.shape[1] + t_vis.shape[1] + gap
    canvas = np.full((canvas_h, canvas_w, 3), BG, dtype=np.uint8)
    canvas[title_h : title_h + q_vis.shape[0], 0 : q_vis.shape[1]] = q_vis
    canvas[title_h : title_h + t_vis.shape[0], q_vis.shape[1] : q_vis.shape[1] + t_vis.shape[1]] = t_vis

    cv2.rectangle(canvas, (0, 0), (canvas_w, title_h), TITLE_BAR, -1)
    cv2.putText(canvas, title, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.62, TEXT_COLOR, 1, cv2.LINE_AA)

    q_origin_x = 6
    q_origin_y = title_h + 6
    t_origin_x = q_vis.shape[1] + 6
    t_origin_y = title_h + 6

    for idx, keep in enumerate(inlier_mask):
        if not keep:
            continue
        q_pt = query_keypoints[idx] * q_scale
        t_pt = tile_keypoints[idx] * t_scale
        p_query = (int(round(q_pt[0])) + q_origin_x, int(round(q_pt[1])) + q_origin_y)
        p_tile = (int(round(t_pt[0])) + t_origin_x, int(round(t_pt[1])) + t_origin_y)
        cv2.line(canvas, p_tile, p_query, LINE_COLOR, 1, cv2.LINE_AA)
        cv2.circle(canvas, p_tile, 3, LINE_COLOR, -1, cv2.LINE_AA)
        cv2.circle(canvas, p_query, 3, LINE_COLOR, -1, cv2.LINE_AA)

    Image.fromarray(canvas).save(out_path)


def draw_placeholder(
    title: str,
    reason: str,
    out_path: Path,
    tile_hit: bool,
    width: int = 1400,
    height: int = 700,
) -> None:
    canvas = np.full((height, width, 3), BG, dtype=np.uint8)
    cv2.rectangle(canvas, (0, 0), (width, 52), TITLE_BAR, -1)
    cv2.putText(canvas, title, (16, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.7, TEXT_COLOR, 1, cv2.LINE_AA)
    cv2.rectangle(canvas, (40, 110), (width // 2 - 20, height - 60), QUERY_BORDER, 6)
    cv2.rectangle(canvas, (width // 2 + 20, 110), (width - 40, height - 60), TILE_BORDER_HIT if tile_hit else TILE_BORDER_MISS, 6)
    cv2.putText(canvas, "query", (80, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.9, QUERY_BORDER, 2, cv2.LINE_AA)
    cv2.putText(canvas, "candidate tile", (width // 2 + 60, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.9, TILE_BORDER_HIT if tile_hit else TILE_BORDER_MISS, 2, cv2.LINE_AA)
    cv2.putText(canvas, f"visualization unavailable: {reason}", (80, height // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, WARN_COLOR, 2, cv2.LINE_AA)
    Image.fromarray(canvas).save(out_path)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_query_rows(stage3_dir: Path) -> dict[str, dict[str, str]]:
    query_rows: dict[str, dict[str, str]] = {}
    for flight_dir in sorted(stage3_dir.iterdir()):
        if not flight_dir.is_dir():
            continue
        queries_csv = flight_dir / "queries.csv"
        if not queries_csv.exists():
            continue
        for row in load_csv(queries_csv):
            query_rows[row["query_id"]] = row
    return query_rows


def load_selected_lookup(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    for row in load_csv(path):
        lookup[(row["flight_id"], row["image_name"])] = row
    return lookup


def resolve_query_path(
    query_row: dict[str, str],
    selected_lookup: dict[tuple[str, str], dict[str, str]],
    query_input_root: Path,
) -> Path:
    image_path = Path(query_row["image_path"])
    if image_path.exists():
        return image_path
    image_name = image_path.name
    flight_id = query_row["flight_id"]
    fallback_1 = query_input_root / flight_id / image_name
    if fallback_1.exists():
        return fallback_1
    selected = selected_lookup.get((flight_id, image_name))
    if selected:
        copied_path = Path(selected["copied_path"])
        if copied_path.exists():
            return copied_path
        original_path = Path(selected["original_path"])
        if original_path.exists():
            return original_path
    return image_path


def build_summary_md(
    out_root: Path,
    summary_csv: Path,
    summary_rows: list[dict[str, object]],
    top_k: int,
) -> str:
    query_ids = sorted({str(row["query_id"]) for row in summary_rows})
    success_rows = [row for row in summary_rows if str(row["status"]) == "ok"]
    failed_rows = [row for row in summary_rows if str(row["status"]) != "ok"]
    flight_counts = Counter(str(row["flight_id"]) for row in summary_rows)
    truth_hit_count = sum(int(row["is_intersection_truth_hit"]) for row in summary_rows)
    inlier_values = [int(row["inlier_count"]) for row in summary_rows]
    if inlier_values:
        inlier_min = min(inlier_values)
        inlier_max = max(inlier_values)
        inlier_mean = sum(inlier_values) / len(inlier_values)
    else:
        inlier_min = inlier_max = inlier_mean = 0.0

    lines = [
        "# RoMa v2 Top-20 同名点可视化汇总",
        "",
        f"- 结果目录: `{out_root}`",
        f"- 汇总 CSV: `{summary_csv}`",
        f"- query 数量: `{len(query_ids)}`",
        f"- 每个 query 候选数: `{top_k}`",
        f"- 目标总图数: `{len(query_ids) * top_k}`",
        f"- 实际图数: `{len(summary_rows)}`",
        f"- 成功生成图数: `{len(success_rows)}`",
        f"- 失败/占位图数: `{len(failed_rows)}`",
        f"- intersection truth hit 候选图数: `{truth_hit_count}`",
        f"- inlier_count 统计: `min={inlier_min}` `mean={inlier_mean:.2f}` `max={inlier_max}`",
        "",
        "## 各航线图数",
        "",
    ]
    for flight_id, count in sorted(flight_counts.items()):
        lines.append(f"- `{flight_id}`: `{count}`")
    if failed_rows:
        lines.extend(
            [
                "",
                "## 失败记录",
                "",
            ]
        )
        for row in failed_rows[:40]:
            lines.append(
                f"- `{row['query_id']}` rank `{row['rank']}` tile `{row['candidate_tile_id']}`: `{row['status']}`"
            )
        if len(failed_rows) > 40:
            lines.append(f"- 其余失败记录见 `{summary_csv}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    romav2_result_dir = Path(args.romav2_result_dir)
    out_root = Path(args.out_root)
    figures_dir = out_root / "figures"
    ensure_dir(figures_dir)

    tiles = {row["tile_id"]: row for row in load_csv(Path(args.tiles_csv))}
    query_rows = load_query_rows(romav2_result_dir / "input_round" / "stage3")
    selected_lookup = load_selected_lookup(Path(args.selected_summary_csv))
    query_input_root = Path(args.query_input_root)

    model = build_model(args.setting, args.device)
    summary_rows: list[dict[str, object]] = []

    for flight_dir in sorted((romav2_result_dir / "stage7").iterdir()):
        if not flight_dir.is_dir():
            continue
        rerank_csv = flight_dir / f"reranked_top{args.top_k}.csv"
        if not rerank_csv.exists():
            continue
        rerank_rows = load_csv(rerank_csv)
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rerank_rows:
            grouped[row["query_id"]].append(row)
        for qid, rows in grouped.items():
            rows.sort(key=lambda row: int(row["rank"]))
            query_row = query_rows[qid]
            query_path = resolve_query_path(query_row, selected_lookup, query_input_root)
            query_output_dir = figures_dir / flight_dir.name / qid
            ensure_dir(query_output_dir)

            for row in rows[: args.top_k]:
                rank = int(row["rank"])
                tile_id = row["candidate_tile_id"]
                tile_row = tiles[tile_id]
                tile_path = Path(tile_row["image_path"])
                out_path = query_output_dir / f"rank{rank:02d}_{safe_name(tile_id)}.png"
                title = (
                    f"{qid} | {short_flight_name(flight_dir.name)} | rank={rank} | "
                    f"tile={tile_id} | hit={row['is_intersection_truth_hit']}"
                )
                print(
                    f"[{flight_dir.name}] {qid} rank {rank:02d}/{args.top_k} tile {tile_id}",
                    flush=True,
                )

                status = "ok"
                match_count = 0
                inlier_count = 0
                inlier_ratio = 0.0
                geom_valid = 0
                romav2_match_score = ""
                reproj_error_mean = ""

                try:
                    query_img = read_rgb(query_path)
                    tile_img = read_rgb(tile_path)
                    match_info = match_pair(
                        model=model,
                        query_path=query_path,
                        tile_path=tile_path,
                        sample_count=args.sample_count,
                        ransac_reproj_thresh=args.ransac_reproj_thresh,
                        min_inliers=args.min_inliers,
                        min_inlier_ratio=args.min_inlier_ratio,
                    )
                    match_count = int(match_info["match_count"])
                    inlier_count = int(match_info["inlier_count"])
                    inlier_ratio = float(match_info["inlier_ratio"])
                    geom_valid = int(bool(match_info["geom_valid"]))
                    romav2_match_score = f"{float(match_info['romav2_match_score']):.6f}"
                    reproj_error_mean = (
                        "" if match_info["reproj_error_mean"] is None else f"{float(match_info['reproj_error_mean']):.6f}"
                    )
                    status = str(match_info["status"])
                    title_full = f"{title} | inliers={inlier_count}/{match_count}"
                    if match_count >= 4 and not (args.resume and out_path.exists()):
                        draw_pair(
                            query_img=query_img,
                            tile_img=tile_img,
                            query_keypoints=np.asarray(match_info["query_keypoints"]),
                            tile_keypoints=np.asarray(match_info["tile_keypoints"]),
                            inlier_mask=np.asarray(match_info["inlier_mask"]),
                            title=title_full,
                            out_path=out_path,
                            tile_hit=row["is_intersection_truth_hit"] == "1",
                            target_long_side=args.target_long_side,
                        )
                    elif not (args.resume and out_path.exists()):
                        draw_placeholder(
                            title=title_full,
                            reason=status,
                            out_path=out_path,
                            tile_hit=row["is_intersection_truth_hit"] == "1",
                        )
                except Exception as exc:
                    status = f"error:{type(exc).__name__}"
                    if not (args.resume and out_path.exists()):
                        draw_placeholder(
                            title=title,
                            reason=status,
                            out_path=out_path,
                            tile_hit=row["is_intersection_truth_hit"] == "1",
                        )

                summary_rows.append(
                    {
                        "flight_id": flight_dir.name,
                        "flight_tag": short_flight_name(flight_dir.name),
                        "query_id": qid,
                        "rank": rank,
                        "candidate_tile_id": tile_id,
                        "is_intersection_truth_hit": int(row["is_intersection_truth_hit"]),
                        "match_count": match_count,
                        "inlier_count": inlier_count,
                        "inlier_ratio": f"{inlier_ratio:.6f}",
                        "geom_valid": geom_valid,
                        "romav2_match_score": romav2_match_score,
                        "reproj_error_mean": reproj_error_mean,
                        "status": status,
                        "query_path": str(query_path),
                        "tile_path": str(tile_path),
                        "output_path": str(out_path),
                    }
                )

    summary_csv = out_root / "summary_top20_match_points.csv"
    write_csv(summary_csv, summary_rows)
    summary_md = out_root / "summary_top20_match_points.md"
    summary_md.write_text(build_summary_md(out_root, summary_csv, summary_rows, args.top_k), encoding="utf-8")
    print(figures_dir)
    print(summary_csv)
    print(summary_md)


if __name__ == "__main__":
    main()

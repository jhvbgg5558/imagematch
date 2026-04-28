#!/usr/bin/env python3
"""Run the Baseline v1 PnP stage on sampled DOM-DSM correspondences.

Purpose:
- convert sampled 2D-3D correspondences into a pose estimate using a locked
  solvePnPRansac + refinement flow;
- emit explicit status codes for v1 exit conditions and PnP failures.

Main inputs:
- the canonical manifest JSON produced by `build_pose_manifest.py`;
- sampled correspondences with `dom_world_x`, `dom_world_y`, `dom_world_z`;
- query intrinsics stored in the manifest or provided as an override JSON.

Main outputs:
- `pnp/pnp_results.csv`
- `pnp/pnp_summary.json`
- `pnp/pnp_inliers.json`
- `logs/run_pnp_baseline.log`

Applicable task constraints:
- query is a single arbitrary UAV image;
- query has no geographic metadata;
- query is not guaranteed to be orthophoto;
- v1 must not reuse the older same-scale truth assumptions or silently alter
  the locked PnP parameters.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "new2output" / "pose_baseline_v1"

REQUIRED_FIELDS = (
    "query_id",
    "candidate_id",
    "query_x",
    "query_y",
    "dom_world_x",
    "dom_world_y",
    "dom_world_z",
    "sample_status",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", default=str(DEFAULT_BUNDLE_ROOT))
    parser.add_argument("--manifest-json", default=None)
    parser.add_argument("--sampled-correspondences-csv", default=None)
    parser.add_argument("--intrinsics-json", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--min-points", type=int, default=6)
    parser.add_argument("--ransac-reproj-thresh", type=float, default=8.0)
    parser.add_argument("--ransac-max-iters", type=int, default=1000)
    parser.add_argument("--ransac-confidence", type=float, default=0.99)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, object]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_intrinsics(manifest: dict[str, object], intrinsics_path: Path | None) -> dict[str, dict[str, float]]:
    if intrinsics_path is not None:
        payload = json.loads(intrinsics_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit("intrinsics JSON must be a mapping of query_id -> intrinsics")
        return {
            query_id: {
                "fx_px": float(values["fx_px"]),
                "fy_px": float(values["fy_px"]),
                "cx_px": float(values["cx_px"]),
                "cy_px": float(values["cy_px"]),
                "k1": float(values.get("k1", 0.0)),
                "k2": float(values.get("k2", 0.0)),
                "p1": float(values.get("p1", 0.0)),
                "p2": float(values.get("p2", 0.0)),
            }
            for query_id, values in payload.items()
        }

    intrinsics: dict[str, dict[str, float]] = {}
    for row in manifest.get("queries", []):
        query_id = row["query_id"]
        values = row.get("intrinsics", {}).get("values", {})
        if {"fx_px", "fy_px", "cx_px", "cy_px"}.issubset(values):
            intrinsics[query_id] = {
                "fx_px": float(values["fx_px"]),
                "fy_px": float(values["fy_px"]),
                "cx_px": float(values["cx_px"]),
                "cy_px": float(values["cy_px"]),
                "k1": float(values.get("k1", 0.0)),
                "k2": float(values.get("k2", 0.0)),
                "p1": float(values.get("p1", 0.0)),
                "p2": float(values.get("p2", 0.0)),
            }
    return intrinsics


def as_float(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def group_rows(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["query_id"], row["candidate_id"])].append(row)
    return grouped


def bounding_box_area(points: np.ndarray) -> float:
    if len(points) == 0:
        return 0.0
    min_xy = points.min(axis=0)
    max_xy = points.max(axis=0)
    span = np.maximum(max_xy - min_xy, 0.0)
    return float(span[0] * span[1])


def reprojection_error(
    object_points: np.ndarray,
    image_points: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    rvec: np.ndarray,
    tvec: np.ndarray,
) -> float:
    import cv2

    projected, _ = cv2.projectPoints(object_points, rvec, tvec, camera_matrix, dist_coeffs)
    projected = projected.reshape(-1, 2)
    errors = np.linalg.norm(projected - image_points, axis=1)
    return float(np.mean(errors)) if len(errors) else 0.0


def camera_center_from_pose(rvec: np.ndarray, tvec: np.ndarray) -> tuple[float, float, float]:
    import cv2

    rotation_matrix, _ = cv2.Rodrigues(rvec)
    center = -rotation_matrix.T @ tvec.reshape(3, 1)
    return float(center[0, 0]), float(center[1, 0]), float(center[2, 0])


def empty_result(query_id: str, candidate_id: str, status: str, detail: str, total_rows: int, ok_rows: int, ok_ratio: float, nodata_ratio: float, sample_status_counts: Counter[str]) -> dict[str, object]:
    return {
        "query_id": query_id,
        "candidate_id": candidate_id,
        "status": status,
        "status_detail": detail,
        "total_correspondences": total_rows,
        "valid_correspondences": ok_rows,
        "ok_ratio": f"{ok_ratio:.6f}",
        "nodata_ratio": f"{nodata_ratio:.6f}",
        "inlier_count": 0,
        "inlier_ratio": 0.0,
        "coverage_bbox_area_px2": 0.0,
        "elevation_span_m": 0.0,
        "reproj_error_mean": "",
        "reproj_error_refined_mean": "",
        "pose_penalty": 1.0,
        "rvec": "",
        "tvec": "",
        "camera_center_x": "",
        "camera_center_y": "",
        "camera_center_z": "",
        "sample_status_breakdown": json.dumps(dict(sample_status_counts), ensure_ascii=False),
    }


def main() -> None:
    args = parse_args()
    bundle_root = Path(args.bundle_root)
    manifest_path = Path(args.manifest_json) if args.manifest_json else bundle_root / "manifest" / "pose_manifest.json"
    sampled_path = (
        Path(args.sampled_correspondences_csv)
        if args.sampled_correspondences_csv
        else bundle_root / "sampling" / "sampled_correspondences.csv"
    )
    out_dir = Path(args.out_dir) if args.out_dir else bundle_root / "pnp"
    logs_dir = bundle_root / "logs"
    ensure_dir(out_dir)
    ensure_dir(logs_dir)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sampled_rows = load_csv(sampled_path)
    if not sampled_rows:
        raise SystemExit(f"No sampled correspondences found: {sampled_path}")
    missing = [name for name in REQUIRED_FIELDS if name not in sampled_rows[0]]
    if missing:
        raise SystemExit(f"sampled correspondences are missing required columns: {', '.join(missing)}")

    intrinsics_map = get_intrinsics(manifest, Path(args.intrinsics_json) if args.intrinsics_json else None)

    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - dependency blocker
        raise SystemExit("opencv-python is required for the Baseline v1 PnP stage") from exc

    grouped = group_rows(sampled_rows)
    results: list[dict[str, object]] = []
    inlier_dump: dict[str, list[int]] = {}
    status_counts: Counter[str] = Counter()

    for (query_id, candidate_id), rows in grouped.items():
        total_rows = len(rows)
        sample_status_counts = Counter(row["sample_status"] for row in rows)
        ok_rows = [row for row in rows if row["sample_status"] == "ok" and row.get("dom_world_z", "") != ""]
        ok_count = len(ok_rows)
        ok_ratio = ok_count / total_rows if total_rows else 0.0
        nodata_ratio = (sample_status_counts["nodata"] + sample_status_counts["out_of_bounds"]) / total_rows if total_rows else 0.0
        query_intrinsics = intrinsics_map.get(query_id)

        if query_intrinsics is None:
            status = "intrinsics_missing"
            status_counts[status] += 1
            results.append(empty_result(query_id, candidate_id, status, "no approx intrinsics available", total_rows, ok_count, ok_ratio, nodata_ratio, sample_status_counts))
            continue
        if nodata_ratio > 0.5:
            status = "dsm_nodata_too_high"
            status_counts[status] += 1
            results.append(empty_result(query_id, candidate_id, status, "nodata or out-of-bounds dominates the sample set", total_rows, ok_count, ok_ratio, nodata_ratio, sample_status_counts))
            continue
        if ok_ratio < 0.5:
            status = "dsm_coverage_insufficient"
            status_counts[status] += 1
            results.append(empty_result(query_id, candidate_id, status, "less than half of the correspondences survived DSM sampling", total_rows, ok_count, ok_ratio, nodata_ratio, sample_status_counts))
            continue
        if ok_count < args.min_points:
            status = "insufficient_2d3d_points"
            status_counts[status] += 1
            results.append(empty_result(query_id, candidate_id, status, f"need at least {args.min_points} valid correspondences", total_rows, ok_count, ok_ratio, nodata_ratio, sample_status_counts))
            continue

        object_points = np.array(
            [[float(row["dom_world_x"]), float(row["dom_world_y"]), float(row["dom_world_z"])] for row in ok_rows],
            dtype=np.float64,
        )
        image_points = np.array(
            [[float(row["query_x"]), float(row["query_y"])] for row in ok_rows],
            dtype=np.float64,
        )
        camera_matrix = np.array(
            [
                [query_intrinsics["fx_px"], 0.0, query_intrinsics["cx_px"]],
                [0.0, query_intrinsics["fy_px"], query_intrinsics["cy_px"]],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        dist_coeffs = np.array(
            [
                query_intrinsics.get("k1", 0.0),
                query_intrinsics.get("k2", 0.0),
                query_intrinsics.get("p1", 0.0),
                query_intrinsics.get("p2", 0.0),
                0.0,
            ],
            dtype=np.float64,
        )

        try:
            success, rvec, tvec, inliers = cv2.solvePnPRansac(
                object_points,
                image_points,
                camera_matrix,
                dist_coeffs,
                iterationsCount=args.ransac_max_iters,
                reprojectionError=args.ransac_reproj_thresh,
                confidence=args.ransac_confidence,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )
        except cv2.error as exc:
            status = "pnp_failed"
            status_counts[status] += 1
            result = empty_result(query_id, candidate_id, status, f"opencv error: {exc}", total_rows, ok_count, ok_ratio, nodata_ratio, sample_status_counts)
            result["coverage_bbox_area_px2"] = bounding_box_area(image_points)
            result["elevation_span_m"] = float(object_points[:, 2].max() - object_points[:, 2].min())
            results.append(result)
            continue

        if not success or inliers is None or len(inliers) == 0:
            status = "pnp_failed"
            status_counts[status] += 1
            result = empty_result(query_id, candidate_id, status, "solvePnPRansac did not converge", total_rows, ok_count, ok_ratio, nodata_ratio, sample_status_counts)
            result["coverage_bbox_area_px2"] = bounding_box_area(image_points)
            result["elevation_span_m"] = float(object_points[:, 2].max() - object_points[:, 2].min())
            results.append(result)
            continue

        inlier_idx = inliers.ravel().astype(int)
        inlier_object_points = object_points[inlier_idx]
        inlier_image_points = image_points[inlier_idx]
        inlier_ratio = float(len(inlier_idx) / len(ok_rows)) if ok_rows else 0.0

        try:
            refined_success, refined_rvec, refined_tvec = cv2.solvePnP(
                inlier_object_points,
                inlier_image_points,
                camera_matrix,
                dist_coeffs,
                rvec,
                tvec,
                useExtrinsicGuess=True,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )
        except cv2.error as exc:
            status = "refinement_failed"
            status_counts[status] += 1
            result = empty_result(query_id, candidate_id, status, f"refinement error: {exc}", total_rows, ok_count, ok_ratio, nodata_ratio, sample_status_counts)
            result["inlier_count"] = int(len(inlier_idx))
            result["inlier_ratio"] = f"{inlier_ratio:.6f}"
            result["coverage_bbox_area_px2"] = bounding_box_area(image_points)
            result["elevation_span_m"] = float(object_points[:, 2].max() - object_points[:, 2].min())
            result["reproj_error_mean"] = f"{reprojection_error(object_points, image_points, camera_matrix, dist_coeffs, rvec, tvec):.6f}"
            result["rvec"] = json.dumps(rvec.reshape(-1).tolist())
            result["tvec"] = json.dumps(tvec.reshape(-1).tolist())
            results.append(result)
            continue

        if not refined_success:
            status = "refinement_failed"
            status_counts[status] += 1
            result = empty_result(query_id, candidate_id, status, "solvePnP refinement returned false", total_rows, ok_count, ok_ratio, nodata_ratio, sample_status_counts)
            result["inlier_count"] = int(len(inlier_idx))
            result["inlier_ratio"] = f"{inlier_ratio:.6f}"
            result["coverage_bbox_area_px2"] = bounding_box_area(image_points)
            result["elevation_span_m"] = float(object_points[:, 2].max() - object_points[:, 2].min())
            result["reproj_error_mean"] = f"{reprojection_error(object_points, image_points, camera_matrix, dist_coeffs, rvec, tvec):.6f}"
            result["rvec"] = json.dumps(rvec.reshape(-1).tolist())
            result["tvec"] = json.dumps(tvec.reshape(-1).tolist())
            results.append(result)
            continue

        reproj_before = reprojection_error(object_points, image_points, camera_matrix, dist_coeffs, rvec, tvec)
        reproj_after = reprojection_error(inlier_object_points, inlier_image_points, camera_matrix, dist_coeffs, refined_rvec, refined_tvec)
        center_x, center_y, center_z = camera_center_from_pose(refined_rvec, refined_tvec)
        elevation_span = float(object_points[:, 2].max() - object_points[:, 2].min())
        pose_penalty = 0.0
        if not all(math.isfinite(value) for value in (center_x, center_y, center_z)):
            pose_penalty = 1.0
        elif center_z < object_points[:, 2].min() - 100.0:
            pose_penalty = 1.0
        elif center_z > object_points[:, 2].max() + 5000.0:
            pose_penalty = 1.0

        status = "ok"
        status_counts[status] += 1
        inlier_dump[f"{query_id}::{candidate_id}"] = inlier_idx.tolist()
        results.append(
            {
                "query_id": query_id,
                "candidate_id": candidate_id,
                "status": status,
                "status_detail": "",
                "total_correspondences": total_rows,
                "valid_correspondences": ok_count,
                "ok_ratio": f"{ok_ratio:.6f}",
                "nodata_ratio": f"{nodata_ratio:.6f}",
                "inlier_count": int(len(inlier_idx)),
                "inlier_ratio": f"{inlier_ratio:.6f}",
                "coverage_bbox_area_px2": f"{bounding_box_area(inlier_image_points):.6f}",
                "elevation_span_m": f"{elevation_span:.6f}",
                "reproj_error_mean": f"{reproj_before:.6f}",
                "reproj_error_refined_mean": f"{reproj_after:.6f}",
                "pose_penalty": f"{pose_penalty:.6f}",
                "rvec": json.dumps(refined_rvec.reshape(-1).tolist()),
                "tvec": json.dumps(refined_tvec.reshape(-1).tolist()),
                "camera_center_x": f"{center_x:.6f}",
                "camera_center_y": f"{center_y:.6f}",
                "camera_center_z": f"{center_z:.6f}",
                "sample_status_breakdown": json.dumps(dict(sample_status_counts), ensure_ascii=False),
            }
        )

    write_csv(out_dir / "pnp_results.csv", results)
    write_json(out_dir / "pnp_inliers.json", inlier_dump)
    write_json(
        out_dir / "pnp_summary.json",
        {
            "bundle_root": str(bundle_root),
            "manifest_json": str(manifest_path.resolve()),
            "sampled_correspondences_csv": str(sampled_path.resolve()),
            "row_count": len(results),
            "status_counts": dict(status_counts),
            "min_points": args.min_points,
            "ransac_reproj_thresh": args.ransac_reproj_thresh,
            "ransac_max_iters": args.ransac_max_iters,
            "ransac_confidence": args.ransac_confidence,
            "generated_at_unix": time.time(),
        },
    )
    (logs_dir / "run_pnp_baseline.log").write_text(
        "\n".join(
            [
                "stage=run_pnp_baseline",
                f"bundle_root={bundle_root}",
                f"row_count={len(results)}",
                f"status_counts={dict(status_counts)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(out_dir / "pnp_results.csv")


if __name__ == "__main__":
    main()

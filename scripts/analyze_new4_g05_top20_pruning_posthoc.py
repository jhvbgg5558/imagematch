#!/usr/bin/env python3
"""Analyze Top-20 pruning from existing new4 G02/G03 gate outputs.

Purpose:
- run a pure posthoc analysis over the existing G02 RoMa and G03 SIFTGPU
  candidate-level outputs;
- simulate whether Top-20 candidates can be reduced to Top-1/3/5 by coarse
  rank, fused rerank, inlier count, or match count;
- report whether truth candidates, final best-pose candidates, and any PnP-ok
  candidates would remain available.

Main inputs:
- G02 and G03 rerank Top-20 CSVs;
- G02 and G03 query truth tiles;
- G02 and G03 PnP and best-pose outputs.

Main outputs:
- candidate match distribution CSVs;
- per-query pruning simulation CSV;
- JSON/CSV/Markdown summary under the G05 output root.

Applicable task constraints:
- query images are metadata-free UAV images and are not assumed orthophotos;
- this script does not run retrieval, matching, DSM sampling, PnP, or
  validation; it only reads existing experiment outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MATRIX_ROOT = PROJECT_ROOT / "new4output" / "nadir_009010_caiwangcun_gate_speedopt_matrix_2026-04-27"
DEFAULT_G02_ROOT = MATRIX_ROOT / "G02_pipeline_engineering_reuse_domz_parallel_sampling"
DEFAULT_G03_ROOT = MATRIX_ROOT / "G03_pipeline_siftgpu_replace_roma"
DEFAULT_OUT_ROOT = MATRIX_ROOT / "G05_top20_pruning_posthoc_analysis"
EXPECTED_QUERY_IDS = ["q_001", "q_021", "q_002", "q_003", "q_004"]
STRATEGIES = [
    ("coarse_raw", [1, 3, 5, 10, 20]),
    ("rerank_fused", [1, 3, 5]),
    ("inlier_count", [1, 3, 5]),
    ("match_count", [1, 3, 5]),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--g02-root", default=str(DEFAULT_G02_ROOT))
    parser.add_argument("--g03-root", default=str(DEFAULT_G03_ROOT))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    ensure_dir(path.parent)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def as_float(value: str | None, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def as_int(value: str | None, default: int = 0) -> int:
    return int(round(as_float(value, float(default))))


def is_true(value: str | int | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def source_config(root: Path, source_group: str) -> dict[str, Any]:
    if source_group == "g02_roma":
        return {
            "source_group": source_group,
            "method": "RoMa v2",
            "rerank_root": root / "romav2_rerank" / "stage7",
            "matcher_score_field": "romav2_match_score",
            "distribution_name": "candidate_match_distribution_g02.csv",
        }
    return {
        "source_group": source_group,
        "method": "SIFTGPU",
        "rerank_root": root / "siftgpu_rerank" / "stage7",
        "matcher_score_field": "siftgpu_match_score",
        "distribution_name": "candidate_match_distribution_g03.csv",
    }


def load_truth_hits(root: Path) -> set[tuple[str, str]]:
    rows = load_csv(root / "query_truth" / "query_truth_tiles.csv")
    return {
        (row["query_id"], row["tile_id"])
        for row in rows
        if is_true(row.get("is_strict_truth"))
    }


def load_pnp_status(root: Path) -> dict[tuple[str, str], str]:
    rows = load_csv(root / "pose_v1_formal" / "pnp" / "pnp_results.csv")
    return {(row["query_id"], row["candidate_id"]): row.get("status", "") for row in rows}


def load_best_candidates(root: Path) -> dict[str, str]:
    rows = load_csv(root / "pose_v1_formal" / "summary" / "per_query_best_pose.csv")
    return {row["query_id"]: row.get("best_candidate_id", "") for row in rows}


def load_reranked_rows(root: Path, source_group: str) -> list[dict[str, str]]:
    cfg = source_config(root, source_group)
    rows: list[dict[str, str]] = []
    for path in sorted(cfg["rerank_root"].glob("*/reranked_top20.csv")):
        for row in load_csv(path):
            row["_source_file"] = str(path)
            rows.append(row)
    return rows


def normalize_candidate_rows(root: Path, source_group: str) -> tuple[list[dict[str, Any]], list[str]]:
    cfg = source_config(root, source_group)
    truth_hits = load_truth_hits(root)
    pnp_status = load_pnp_status(root)
    best_candidates = load_best_candidates(root)
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    for row in load_reranked_rows(root, source_group):
        query_id = row["query_id"]
        candidate_id = row["candidate_tile_id"]
        truth_from_field = is_true(row.get("is_intersection_truth_hit"))
        truth_from_fallback = (query_id, candidate_id) in truth_hits
        best_candidate_id = best_candidates.get(query_id, "")
        out = {
            "source_group": source_group,
            "query_id": query_id,
            "candidate_id": candidate_id,
            "raw_rank": as_int(row.get("raw_rank")),
            "rerank_rank": as_int(row.get("rank")),
            "match_count": as_int(row.get("match_count")),
            "inlier_count": as_int(row.get("inlier_count")),
            "inlier_ratio": as_float(row.get("inlier_ratio")),
            "geom_valid": as_int(row.get("geom_valid")),
            "is_truth_hit": int(truth_from_field or truth_from_fallback),
            "truth_hit_source": "rerank_field" if truth_from_field else ("strict_truth_fallback" if truth_from_fallback else ""),
            "pnp_status": pnp_status.get((query_id, candidate_id), "missing"),
            "is_best_pose_candidate": int(best_candidate_id == candidate_id),
            "best_candidate_id": best_candidate_id,
            "global_score": as_float(row.get("global_score")),
            "fused_score": as_float(row.get("fused_score")),
            "candidate_scale_level_m": as_float(row.get("candidate_scale_level_m")),
            "matcher_score": as_float(row.get(cfg["matcher_score_field"])),
            "method": cfg["method"],
        }
        rows.append(out)

    query_ids = sorted({row["query_id"] for row in rows})
    if query_ids != sorted(EXPECTED_QUERY_IDS):
        warnings.append(f"{source_group}: query set mismatch: {query_ids}")
    for query_id in query_ids:
        qrows = [row for row in rows if row["query_id"] == query_id]
        if len(qrows) != 20:
            warnings.append(f"{source_group}: {query_id} has {len(qrows)} candidates, expected 20")
        if not any(row["is_truth_hit"] for row in qrows):
            warnings.append(f"{source_group}: {query_id} has no truth-hit candidate in Top-20")
    return rows, warnings


def sort_candidates(rows: list[dict[str, Any]], strategy: str) -> list[dict[str, Any]]:
    if strategy == "coarse_raw":
        return sorted(rows, key=lambda row: (row["raw_rank"], row["rerank_rank"]))
    if strategy == "rerank_fused":
        return sorted(rows, key=lambda row: (row["rerank_rank"], row["raw_rank"]))
    if strategy == "inlier_count":
        return sorted(rows, key=lambda row: (-row["inlier_count"], row["raw_rank"], row["rerank_rank"]))
    if strategy == "match_count":
        return sorted(rows, key=lambda row: (-row["match_count"], -row["inlier_count"], row["raw_rank"], row["rerank_rank"]))
    raise ValueError(strategy)


def simulate(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_source_query: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_source_query[(row["source_group"], row["query_id"])].append(row)

    per_query_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    source_groups = sorted({row["source_group"] for row in rows})
    for source_group in source_groups:
        source_query_ids = sorted({query_id for group, query_id in by_source_query if group == source_group})
        for strategy, ks in STRATEGIES:
            for k in ks:
                strategy_name = f"{strategy}_top{k}"
                truth_retained = 0
                best_retained = 0
                pnp_ok_available = 0
                retained_counts: list[int] = []
                for query_id in source_query_ids:
                    qrows = by_source_query[(source_group, query_id)]
                    selected = sort_candidates(qrows, strategy)[:k]
                    selected_ids = {row["candidate_id"] for row in selected}
                    query_truth_retained = any(row["is_truth_hit"] for row in selected)
                    query_best_retained = any(row["is_best_pose_candidate"] for row in selected)
                    query_pnp_ok = any(row["pnp_status"] == "ok" for row in selected)
                    truth_retained += int(query_truth_retained)
                    best_retained += int(query_best_retained)
                    pnp_ok_available += int(query_pnp_ok)
                    retained_counts.append(len(selected))
                    per_query_rows.append(
                        {
                            "source_group": source_group,
                            "query_id": query_id,
                            "strategy": strategy_name,
                            "k": k,
                            "retained_candidate_ids": "|".join(row["candidate_id"] for row in selected),
                            "retained_raw_ranks": "|".join(str(row["raw_rank"]) for row in selected),
                            "retained_rerank_ranks": "|".join(str(row["rerank_rank"]) for row in selected),
                            "retained_inlier_counts": "|".join(str(row["inlier_count"]) for row in selected),
                            "retained_match_counts": "|".join(str(row["match_count"]) for row in selected),
                            "truth_retained": int(query_truth_retained),
                            "best_pose_candidate_retained": int(query_best_retained),
                            "pnp_ok_available": int(query_pnp_ok),
                            "truth_candidate_ids_in_top20": "|".join(row["candidate_id"] for row in qrows if row["is_truth_hit"]),
                            "best_candidate_id": next((row["best_candidate_id"] for row in qrows if row["best_candidate_id"]), ""),
                        }
                    )
                query_count = len(source_query_ids)
                avg_kept = sum(retained_counts) / query_count if query_count else math.nan
                summary_rows.append(
                    {
                        "source_group": source_group,
                        "strategy": strategy_name,
                        "query_count": query_count,
                        "retained_per_query": k,
                        "truth_retained_query_count": truth_retained,
                        "truth_retained_ratio": truth_retained / query_count if query_count else None,
                        "best_pose_candidate_retained_query_count": best_retained,
                        "best_pose_candidate_retained_ratio": best_retained / query_count if query_count else None,
                        "pnp_ok_available_query_count": pnp_ok_available,
                        "pnp_ok_available_ratio": pnp_ok_available / query_count if query_count else None,
                        "average_retained_candidate_count": avg_kept,
                        "candidate_reduction_vs_top20_ratio": 1.0 - (avg_kept / 20.0) if query_count else None,
                        "passes_strict_topk_gate": truth_retained == query_count
                        and best_retained == query_count
                        and pnp_ok_available == query_count,
                    }
                )
    return per_query_rows, summary_rows


def decision_summary(summary_rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"by_source_group": {}, "overall_conclusion": ""}
    for group in sorted({row["source_group"] for row in summary_rows}):
        group_rows = [row for row in summary_rows if row["source_group"] == group]
        passed_inlier = [
            row for row in group_rows
            if row["strategy"].startswith("inlier_count_top") and row["passes_strict_topk_gate"]
        ]
        best_inlier = min(passed_inlier, key=lambda row: row["retained_per_query"], default=None)
        coarse_passed = [
            row for row in group_rows
            if row["strategy"].startswith("coarse_raw_top") and row["truth_retained_query_count"] == row["query_count"]
        ]
        best_coarse = min(coarse_passed, key=lambda row: row["retained_per_query"], default=None)
        out["by_source_group"][group] = {
            "minimum_inlier_count_topk_passing_all_checks": None if best_inlier is None else best_inlier["retained_per_query"],
            "minimum_coarse_raw_topk_retaining_truth": None if best_coarse is None else best_coarse["retained_per_query"],
            "inlier_count_top1_passes_all_checks": any(
                row["strategy"] == "inlier_count_top1" and row["passes_strict_topk_gate"]
                for row in group_rows
            ),
        }
    both_top1 = all(
        item["inlier_count_top1_passes_all_checks"]
        for item in out["by_source_group"].values()
    )
    if both_top1:
        out["overall_conclusion"] = "G02 and G03 both support inlier_count Top-1 pruning under the strict posthoc checks."
    else:
        out["overall_conclusion"] = (
            "Do not adopt universal Top-1 pruning yet; inspect the per-source minimum Top-K and failure rows."
        )
    return out


def write_plan(out_root: Path, g02_root: Path, g03_root: Path) -> None:
    text = f"""# 第 5 组实验计划：Top-20 精简验证后处理分析

## Summary

- 实验组名：`G05_top20_pruning_posthoc_analysis`
- 输出目录：`{out_root.as_posix()}`
- G02 输入：`{g02_root.as_posix()}`
- G03 输入：`{g03_root.as_posix()}`
- 性质：只做已有结果后处理，不重跑 RoMa、SIFTGPU、PnP、DSM sampling 或 validation。

## 分析口径

- 正确候选：优先使用 `is_intersection_truth_hit == 1`，必要时用 `query_truth_tiles.csv` 中的 strict truth 兜底。
- 同名点数量主指标：`inlier_count`。
- 辅助指标：`match_count`；G02 RoMa 的 `match_count` 基本固定，不作为主结论。
- 策略：coarse raw Top-1/3/5/10/20，rerank fused Top-1/3/5，inlier count Top-1/3/5，match count Top-1/3/5。

## 验收

- 每组读取 5 query × 20 candidate。
- 输出候选分布、逐 query 模拟表、策略汇总 JSON/CSV/Markdown。
- 明确给出 Top-1 是否可行；若不可行，给出 Top-3/Top-5 是否可行。
"""
    (out_root / "实验计划.md").write_text(text, encoding="utf-8")


def write_markdown_summary(
    path: Path,
    summary_rows: list[dict[str, Any]],
    decisions: dict[str, Any],
    warnings: list[str],
) -> None:
    lines = [
        "# G05 Top-20 精简验证后处理分析",
        "",
        "## 结论",
        "",
        f"- {decisions['overall_conclusion']}",
    ]
    for group, decision in decisions["by_source_group"].items():
        lines.append(
            f"- `{group}`: inlier_count 最小可行 Top-K = "
            f"`{decision['minimum_inlier_count_topk_passing_all_checks']}`；"
            f"coarse raw 保留 truth 的最小 Top-K = "
            f"`{decision['minimum_coarse_raw_topk_retaining_truth']}`。"
        )
    lines.extend(["", "## 策略汇总", ""])
    lines.append("| source_group | strategy | truth | best_pose | pnp_ok | reduction | pass |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | --- |")
    for row in summary_rows:
        lines.append(
            f"| {row['source_group']} | {row['strategy']} | "
            f"{row['truth_retained_query_count']}/{row['query_count']} | "
            f"{row['best_pose_candidate_retained_query_count']}/{row['query_count']} | "
            f"{row['pnp_ok_available_query_count']}/{row['query_count']} | "
            f"{row['candidate_reduction_vs_top20_ratio']:.3f} | "
            f"{row['passes_strict_topk_gate']} |"
        )
    if warnings:
        lines.extend(["", "## Data Quality Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    g02_root = Path(args.g02_root)
    g03_root = Path(args.g03_root)
    out_root = Path(args.out_root)
    if args.overwrite and out_root.exists():
        shutil.rmtree(out_root)
    ensure_dir(out_root)
    write_plan(out_root, g02_root, g03_root)

    all_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for root, group in ((g02_root, "g02_roma"), (g03_root, "g03_siftgpu")):
        rows, group_warnings = normalize_candidate_rows(root, group)
        all_rows.extend(rows)
        warnings.extend(group_warnings)
        cfg = source_config(root, group)
        write_csv(out_root / cfg["distribution_name"], rows)

    per_query_rows, summary_rows = simulate(all_rows)
    decisions = decision_summary(summary_rows)
    write_csv(out_root / "pruning_simulation_per_query.csv", per_query_rows)
    write_csv(out_root / "compare_g02_g03_topk_pruning.csv", summary_rows)
    write_json(
        out_root / "pruning_simulation_summary.json",
        {
            "generated_at_utc": utc_now(),
            "g02_root": str(g02_root),
            "g03_root": str(g03_root),
            "out_root": str(out_root),
            "expected_query_ids": EXPECTED_QUERY_IDS,
            "candidate_row_count": len(all_rows),
            "data_quality_warnings": warnings,
            "decision_summary": decisions,
            "strategy_summary": summary_rows,
        },
    )
    write_markdown_summary(out_root / "pruning_simulation_summary.md", summary_rows, decisions, warnings)
    print(out_root)


if __name__ == "__main__":
    main()

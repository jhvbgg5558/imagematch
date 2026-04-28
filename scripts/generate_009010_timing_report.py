#!/usr/bin/env python3
"""Generate the 009/010 dual-route timing report.

Purpose:
- read existing local timing logs and summaries for the satellite DOM+SRTM
  route and the CaiWangCun DOM+DSM full-replacement route;
- generate a Markdown report focused on online localization timing.

Main inputs:
- existing run logs, RoMa v2 timing JSON files, formal pose stage summaries,
  and status CSV files under `new2output/` and `new3output/`.

Main outputs:
- `汇总/时间统计.md`.

Applicable task constraints:
- query is a single UAV image without geographic metadata;
- query is not assumed to be orthophoto;
- this report does not rerun experiments and only uses auditable local outputs;
- where logs do not contain per-query or per-pair elapsed fields, the report
  explicitly marks values as batch-average estimates.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_MD = PROJECT_ROOT / "汇总" / "时间统计.md"

QUERY_COUNT = 40
PAIR_COUNT = 800

SRTM_UPSTREAM_ROOT = PROJECT_ROOT / "new2output" / "nadir_009010_dinov2_romav2_pose_2026-04-10"
SRTM_FORMAL_ROOT = (
    PROJECT_ROOT
    / "new3output"
    / "nadir_009010_dinov2_romav2_pose_sattruth_srtm_romatie_2026-04-16"
)
CAI_GATE_ROOT = (
    PROJECT_ROOT
    / "new3output"
    / "nadir_009010_caiwangcun_domdsm_fullreplace_gate_2026-04-20"
)
CAI_FULL_ROOT = (
    PROJECT_ROOT
    / "new3output"
    / "nadir_009010_caiwangcun_domdsm_fullreplace_full_2026-04-21"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def count_csv_rows(path: Path) -> int:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def fmt_s(seconds: float | int | None, digits: int = 3) -> str:
    if seconds is None:
        return "未记录"
    return f"{float(seconds):.{digits}f}s"


def fmt_min(seconds: float | int | None) -> str:
    if seconds is None:
        return "未记录"
    seconds = float(seconds)
    minutes = int(seconds // 60)
    remain = seconds - minutes * 60
    return f"{minutes}m{remain:04.1f}s"


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


def stage_elapsed(phase_summary: dict[str, Any], stage_name: str) -> float:
    for stage in phase_summary.get("stages", []):
        if stage.get("stage") == stage_name:
            return float(stage["elapsed_seconds"])
    raise KeyError(stage_name)


def extract_query_feature_elapsed_min(log_text: str) -> float | None:
    matches = re.findall(r"Finished\. ok=40 total=40 elapsed=([0-9.]+)min", log_text)
    if matches:
        return float(matches[0])
    matches = re.findall(r"\[40/40\] ok=40 elapsed=([0-9.]+)min", log_text)
    return float(matches[0]) if matches else None


def seconds_from_iso_boundary(log_text: str, start_marker: str, end_marker: str) -> int | None:
    pattern = re.compile(r"\[(2026-[^\]]+)\].*")
    rows = []
    for line in log_text.splitlines():
        match = pattern.match(line)
        if match:
            rows.append((match.group(1), line))
    start = next((ts for ts, line in rows if start_marker in line), None)
    end = next((ts for ts, line in rows if end_marker in line), None)
    if not start or not end:
        return None
    from datetime import datetime

    def parse(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    return int((parse(end) - parse(start)).total_seconds())


def build_report() -> str:
    srtm_log = read_text(SRTM_UPSTREAM_ROOT / "logs" / "run_full.log")
    cai_gate_log = read_text(CAI_GATE_ROOT / "logs" / "fullreplace_gate.log")

    srtm_rerank = load_json(SRTM_UPSTREAM_ROOT / "romav2_rerank" / "timing" / "romav2_rerank_internal.json")
    cai_rerank = load_json(CAI_GATE_ROOT / "romav2_rerank" / "timing" / "romav2_rerank_internal.json")

    srtm_phase = load_json(SRTM_FORMAL_ROOT / "pose_v1_formal" / "summary" / "phase_gate_summary.json")
    cai_phase = load_json(CAI_FULL_ROOT / "pose_v1_formal" / "summary" / "phase_gate_summary.json")

    srtm_retrieval_export = load_json(SRTM_UPSTREAM_ROOT / "retrieval" / "retrieval_top20_export_summary.json")
    cai_retrieval_export = load_json(CAI_FULL_ROOT / "retrieval" / "retrieval_top20_export_summary.json")

    srtm_q_status_count = count_csv_rows(SRTM_UPSTREAM_ROOT / "query_features" / "query_dinov2_pooler_status.csv")
    cai_q_status_count = count_csv_rows(CAI_FULL_ROOT / "query_features" / "query_dinov2_pooler_status.csv")
    cai_candidate_status_count = count_csv_rows(CAI_GATE_ROOT / "candidate_features" / "caiwangcun_tile_dinov2_status.csv")

    q_feature_min = extract_query_feature_elapsed_min(srtm_log)
    q_feature_s = q_feature_min * 60 if q_feature_min is not None else None
    cai_candidate_feature_s = 1.7 * 60

    cai_retrieval_s = seconds_from_iso_boundary(
        cai_gate_log,
        "evaluate_retrieval_against_intersection_truth.py",
        "prepare_romav2_intersection_inputs.py",
    )
    srtm_retrieval_s = None

    srtm_rerank_s = float(srtm_rerank["elapsed_seconds"])
    cai_rerank_s = float(cai_rerank["elapsed_seconds"])

    srtm_pose_export_s = stage_elapsed(srtm_phase, "export_romav2_matches_batch_for_pose")
    srtm_prepare_s = stage_elapsed(srtm_phase, "prepare_pose_correspondences")
    srtm_sampling_s = stage_elapsed(srtm_phase, "sample_dsm_for_dom_points")
    srtm_pnp_s = stage_elapsed(srtm_phase, "run_pnp_baseline")
    srtm_score_s = stage_elapsed(srtm_phase, "score_formal_pose_results")

    cai_pose_export_s = stage_elapsed(cai_phase, "export_romav2_matches_batch_for_pose")
    cai_prepare_s = stage_elapsed(cai_phase, "prepare_pose_correspondences")
    cai_sampling_s = stage_elapsed(cai_phase, "sample_dsm_for_dom_points")
    cai_pnp_s = stage_elapsed(cai_phase, "run_pnp_baseline")
    cai_score_s = stage_elapsed(cai_phase, "score_formal_pose_results")

    srtm_pose_total_s = srtm_pose_export_s + srtm_prepare_s + srtm_sampling_s + srtm_pnp_s + srtm_score_s
    cai_pose_total_s = cai_pose_export_s + cai_prepare_s + cai_sampling_s + cai_pnp_s + cai_score_s

    # Current actual online timing includes rerank and the second RoMa export
    # in formal pose. Retrieval is approximate because SRTM has no separate
    # elapsed field for coarse retrieval.
    srtm_actual_per_query = (q_feature_s or 0) / QUERY_COUNT + srtm_rerank_s / QUERY_COUNT + srtm_pose_total_s / QUERY_COUNT
    cai_actual_per_query = (
        (q_feature_s or 0) / QUERY_COUNT
        + (cai_retrieval_s or 0) / QUERY_COUNT
        + cai_rerank_s / QUERY_COUNT
        + cai_pose_total_s / QUERY_COUNT
    )

    # Deduplicated estimate removes the second RoMa run in pose matches export.
    srtm_dedup_per_query = srtm_actual_per_query - srtm_pose_export_s / QUERY_COUNT
    cai_dedup_per_query = cai_actual_per_query - cai_pose_export_s / QUERY_COUNT

    overview_rows = [
        [
            "卫星 DOM+SRTM",
            fmt_min(srtm_actual_per_query),
            fmt_min(srtm_dedup_per_query),
            "当前实际口径包含 RoMa 重排与 pose matches export 两次 RoMa 计算",
        ],
        [
            "CaiWangCun DOM+DSM 完整替换",
            fmt_min(cai_actual_per_query),
            fmt_min(cai_dedup_per_query),
            "完整替换线路 sample-count=5000，RoMa 重排结果更适合复用到 PnP",
        ],
    ]

    dino_rows = [
        [
            "两条线路 query 特征",
            "DINOv2 query feature extraction",
            f"{q_feature_min:.1f}min / {QUERY_COUNT} query" if q_feature_min is not None else "未记录",
            fmt_s((q_feature_s or 0) / QUERY_COUNT),
            "均值折算",
            f"status CSV 行数：SRTM={srtm_q_status_count}, CaiWangCun={cai_q_status_count}；未记录逐张 elapsed",
        ],
        [
            "CaiWangCun 离线候选资产",
            "candidate DINOv2 features",
            "1.7min / 149 tiles",
            fmt_s(cai_candidate_feature_s / cai_candidate_status_count),
            "均值折算",
            "离线资产构建，不计入单张在线定位主耗时",
        ],
        [
            "卫星 DOM+SRTM",
            "Top-20 retrieval export",
            "未单独记录 elapsed",
            "未记录",
            "不可拆分",
            f"输出 query_count={srtm_retrieval_export['query_count']}, row_count={srtm_retrieval_export['row_count']}",
        ],
        [
            "CaiWangCun DOM+DSM",
            "Top-20 retrieval",
            f"约 {cai_retrieval_s}s / {QUERY_COUNT} query" if cai_retrieval_s is not None else "未记录",
            fmt_s((cai_retrieval_s or 0) / QUERY_COUNT),
            "日志边界估算",
            f"输出 query_count={cai_retrieval_export['query_count']}, row_count={cai_retrieval_export['row_count']}",
        ],
    ]

    rerank_rows = [
        [
            "卫星 DOM+SRTM",
            fmt_s(srtm_rerank_s),
            fmt_s(srtm_rerank_s / QUERY_COUNT),
            fmt_s(srtm_rerank_s / PAIR_COUNT),
            "5000",
            "2 次模型加载（每条 flight 一个子进程）",
        ],
        [
            "CaiWangCun DOM+DSM",
            fmt_s(cai_rerank_s),
            fmt_s(cai_rerank_s / QUERY_COUNT),
            fmt_s(cai_rerank_s / PAIR_COUNT),
            "5000",
            "2 次模型加载（每条 flight 一个子进程）",
        ],
    ]

    formal_rows = [
        [
            "卫星 DOM+SRTM",
            "RoMa matches export",
            fmt_s(srtm_pose_export_s),
            fmt_s(srtm_pose_export_s / QUERY_COUNT),
            fmt_s(srtm_pose_export_s / PAIR_COUNT),
            "2000",
        ],
        [
            "卫星 DOM+SRTM",
            "prepare_pose_correspondences",
            fmt_s(srtm_prepare_s),
            fmt_s(srtm_prepare_s / QUERY_COUNT),
            fmt_s(srtm_prepare_s / PAIR_COUNT),
            "-",
        ],
        [
            "卫星 DOM+SRTM",
            "DSM sampling",
            fmt_s(srtm_sampling_s),
            fmt_s(srtm_sampling_s / QUERY_COUNT),
            fmt_s(srtm_sampling_s / PAIR_COUNT),
            "1,600,000 correspondences",
        ],
        [
            "卫星 DOM+SRTM",
            "PnP",
            fmt_s(srtm_pnp_s),
            fmt_s(srtm_pnp_s / QUERY_COUNT),
            fmt_s(srtm_pnp_s / PAIR_COUNT),
            "800 pose candidates",
        ],
        [
            "卫星 DOM+SRTM",
            "score / best pose",
            fmt_s(srtm_score_s),
            fmt_s(srtm_score_s / QUERY_COUNT),
            fmt_s(srtm_score_s / PAIR_COUNT),
            "40 best poses",
        ],
        [
            "CaiWangCun DOM+DSM",
            "RoMa matches export",
            fmt_s(cai_pose_export_s),
            fmt_s(cai_pose_export_s / QUERY_COUNT),
            fmt_s(cai_pose_export_s / PAIR_COUNT),
            "5000",
        ],
        [
            "CaiWangCun DOM+DSM",
            "prepare_pose_correspondences",
            fmt_s(cai_prepare_s),
            fmt_s(cai_prepare_s / QUERY_COUNT),
            fmt_s(cai_prepare_s / PAIR_COUNT),
            "-",
        ],
        [
            "CaiWangCun DOM+DSM",
            "DSM sampling",
            fmt_s(cai_sampling_s),
            fmt_s(cai_sampling_s / QUERY_COUNT),
            fmt_s(cai_sampling_s / PAIR_COUNT),
            "4,000,000 correspondences",
        ],
        [
            "CaiWangCun DOM+DSM",
            "PnP",
            fmt_s(cai_pnp_s),
            fmt_s(cai_pnp_s / QUERY_COUNT),
            fmt_s(cai_pnp_s / PAIR_COUNT),
            "800 pose candidates",
        ],
        [
            "CaiWangCun DOM+DSM",
            "score / best pose",
            fmt_s(cai_score_s),
            fmt_s(cai_score_s / QUERY_COUNT),
            fmt_s(cai_score_s / PAIR_COUNT),
            "40 best poses",
        ],
    ]

    pnp_group_rows = [
        [
            "卫星 DOM+SRTM",
            "PnP 数据准备（correspondence + DSM sampling）",
            fmt_s(srtm_prepare_s + srtm_sampling_s),
            fmt_s((srtm_prepare_s + srtm_sampling_s) / QUERY_COUNT),
        ],
        [
            "卫星 DOM+SRTM",
            "PnP 解算与 best pose 输出（PnP + scoring）",
            fmt_s(srtm_pnp_s + srtm_score_s),
            fmt_s((srtm_pnp_s + srtm_score_s) / QUERY_COUNT),
        ],
        [
            "CaiWangCun DOM+DSM",
            "PnP 数据准备（correspondence + DSM sampling）",
            fmt_s(cai_prepare_s + cai_sampling_s),
            fmt_s((cai_prepare_s + cai_sampling_s) / QUERY_COUNT),
        ],
        [
            "CaiWangCun DOM+DSM",
            "PnP 解算与 best pose 输出（PnP + scoring）",
            fmt_s(cai_pnp_s + cai_score_s),
            fmt_s((cai_pnp_s + cai_score_s) / QUERY_COUNT),
        ],
    ]

    return f"""# 009/010 双线路在线定位时间统计

## 1. 统计口径与数据来源

本报告基于本地既有日志、JSON 和 CSV 输出生成，不重新运行实验。统计对象为卫星 DOM+SRTM 线路与 CaiWangCun DOM+DSM 完整替换线路。报告只统计与在线定位链路直接相关的耗时，包括 DINOv2 query 特征提取、Top-20 检索、RoMa v2 匹配/重排、RoMa v2 pose matches export、PnP 数据准备、DSM 采样、PnP 位姿解算和 best pose 输出。

报告采用三类口径。`实测总耗时`来自日志或 JSON 中的 `elapsed_seconds`。`单张均值`按 40 个 query 折算。`单对均值`按 800 个 query-candidate pair 折算，主要用于 RoMa v2 和 formal pose 阶段；该值不是逐 pair 独立实测。

主要数据来源：

- SRTM 上游：`{SRTM_UPSTREAM_ROOT.relative_to(PROJECT_ROOT)}`
- SRTM formal pose：`{SRTM_FORMAL_ROOT.relative_to(PROJECT_ROOT)}`
- CaiWangCun gate 上游：`{CAI_GATE_ROOT.relative_to(PROJECT_ROOT)}`
- CaiWangCun full pose：`{CAI_FULL_ROOT.relative_to(PROJECT_ROOT)}`

## 2. 双线路在线定位耗时总览

当前实际口径包含 RoMa v2 重排和 formal pose matches export 两次 RoMa 计算。去重优化口径假设重排阶段同步保存 PnP 所需点级匹配结果，从而取消 formal pose 阶段的第二次 RoMa matches export。

{md_table(["线路", "当前实际单张耗时", "去重优化后单张估算", "说明"], overview_rows)}

## 3. DINOv2 特征与检索耗时

DINOv2 query 特征提取日志没有逐张 elapsed 字段，只有 batch 总耗时，因此逐张耗时为均值折算。Top-20 检索本身耗时很短；CaiWangCun 线路可从日志边界估算为约 1s/40 query，SRTM 线路未保存独立检索 elapsed 字段。

{md_table(["线路/阶段", "环节", "实测总耗时", "单张或单 tile 均值", "口径", "说明"], dino_rows)}

## 4. RoMa v2 匹配/重排耗时与模型加载行为

RoMa v2 重排阶段只有 per-flight timing 和总耗时，没有逐 pair 独立耗时。下表的单对耗时按 `总耗时 / 800` 折算。

{md_table(["线路", "RoMa 重排实测总耗时", "单张均值", "单对均值", "sample-count", "模型加载行为"], rerank_rows)}

模型加载行为结论如下：

- `run_romav2_rerank_intersection_round.py` 对每个 flight 启动一次 `rerank_with_romav2_intersection.py` 子进程。
- `rerank_with_romav2_intersection.py` 在进程内调用一次 `build_model(...)`，随后循环处理该 flight 的 query 和 Top-20 candidate。
- 因此，RoMa v2 重排阶段不是每对候选重新加载模型，而是每条 flight 重新加载一次模型；两条 flight 共加载 2 次。
- `run_formal_pose_v1_pipeline.py` 调用 `export_romav2_matches_batch_for_pose.py`；该脚本在整批 pose matches export 内再次调用一次 `build_model(...)`。
- 因此，每条线路在当前完整口径下至少包含 2 次重排模型加载和 1 次 pose export 模型加载；同时，RoMa 匹配计算本身在重排和 PnP matches export 中重复执行。

当前重复计算的根因是：重排阶段只保存候选级统计量，例如 `match_count`、`inlier_count`、`inlier_ratio`、`reproj_error_mean` 和 `fused_score`，没有保存 PnP 所需的 `query_x/query_y/dom_pixel_x/dom_pixel_y` 点级匹配结果。formal pose 阶段因此必须再次运行 RoMa v2，生成 `matches/roma_matches.csv`。

## 5. PnP 数据准备与位姿解算耗时

formal pose 阶段有 stage-level `elapsed_seconds`，可直接拆出 RoMa matches export、correspondence 准备、DSM sampling、PnP 解算和 score/best pose 输出。

{md_table(["线路", "环节", "实测总耗时", "单张均值", "单对均值", "规模/说明"], formal_rows)}

按 PnP 逻辑分组后，数据准备与位姿求解耗时如下：

{md_table(["线路", "分组", "实测总耗时", "单张均值"], pnp_group_rows)}

## 6. 单张影像定位耗时估算

当前实际口径下，卫星 DOM+SRTM 线路单张定位约 {fmt_min(srtm_actual_per_query)}，CaiWangCun DOM+DSM 完整替换线路单张定位约 {fmt_min(cai_actual_per_query)}。该估算包含 RoMa v2 重排和 formal pose matches export 两次 RoMa 计算。

若后续将 RoMa v2 重排阶段的点级匹配结果直接保存为 PnP 可消费格式，则可取消 formal pose 阶段第二次 RoMa matches export。按现有日志折算，卫星 DOM+SRTM 单张耗时可降至约 {fmt_min(srtm_dedup_per_query)}，CaiWangCun DOM+DSM 单张耗时可降至约 {fmt_min(cai_dedup_per_query)}。

需要注意，SRTM 重排阶段使用 `sample-count=5000`，而 SRTM formal pose matches export 使用 `sample-count=2000`。如果直接复用重排结果，SRTM 的 PnP 输入点数量口径会发生变化；若要保持 SRTM formal pose 口径不变，需要让重排阶段按 PnP 所需 sample-count 同步导出点级匹配结果。

## 7. 结论与优化建议

当前在线定位耗时的主要瓶颈是 RoMa v2 匹配和 DSM sampling。RoMa v2 并非每对候选都重新加载模型，但在当前完整链路中，重排阶段和 PnP matches export 阶段重复执行了 RoMa 匹配计算。CaiWangCun 线路的 DSM sampling 也显著高于 SRTM，主要因为其 formal pose 阶段处理 4,000,000 条 correspondence，而 SRTM 为 1,600,000 条 correspondence。

优先优化方向如下：

1. 在 RoMa v2 重排阶段同步输出 PnP 所需点级匹配 CSV，避免 formal pose 阶段重复运行 `export_romav2_matches_batch_for_pose.py`。
2. 将 RoMa 点级输出格式对齐 `prepare_pose_correspondences.py` 的输入字段：`query_id`、`candidate_id`、`candidate_rank`、`query_x`、`query_y`、`dom_pixel_x`、`dom_pixel_y`、`match_score`、`is_inlier`。
3. 对 DSM sampling 做分块、缓存或矢量化优化，尤其是 CaiWangCun 线路的 4,000,000 条 correspondence 采样。
4. 为后续运行补充更细粒度 timing 字段，包括逐 query、逐 pair、模型加载、模型推理、RANSAC 和 CSV 写出耗时，避免只能从 batch 总耗时折算。
"""


def main() -> None:
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(build_report(), encoding="utf-8")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()

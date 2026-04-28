#!/usr/bin/env python3
"""Generate a Word report for RoMa v2 benefit-boundary analysis.

This script serves the current UAV-to-orthophoto retrieval task where:
- the query is a single arbitrary UAV image,
- the query has no geographic metadata,
- the query is not guaranteed to be orthophoto,
- the report must reuse the locked `query v2 + intersection truth` results
  without recomputing retrieval or changing evaluation assumptions.

Main inputs:
- existing Markdown report under `new1output/benefit_boundary_analysis_2026-03-31/reports`
- core CSV tables under `new1output/benefit_boundary_analysis_2026-03-31/tables`
- summary figures under `new1output/benefit_boundary_analysis_2026-03-31/figures`
- B-bucket RoMa visualization images under
  `new1output/query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_gpu/figures`

Main output:
- `benefit_boundary_analysis_report.docx`

Applicable constraints:
- do not rerun the benefit-boundary analysis
- do not modify existing tables/figures/cases assets
- keep the narrative aligned with the formal Markdown report and locked bucket rules
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


SUMMARY_FIGURES = [
    "figure_1_bucket_counts.png",
    "figure_2_bucket_by_flight.png",
    "figure_3_rank_scatter.png",
    "figure_4_top1_error_delta_boxplot.png",
    "figure_5_pitch_distribution.png",
    "figure_6_truthcount_footprint_distribution.png",
    "figure_7_b_rank_gain_distribution.png",
]

B_QUERY_IDS = ["q_002", "q_003", "q_013", "q_022", "q_029", "q_037"]


@dataclass
class AnalysisPaths:
    analysis_dir: Path
    report_md: Path
    tables_dir: Path
    figures_dir: Path
    out_docx: Path
    romav2_figures_dir: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--analysis-dir",
        default="new1output/benefit_boundary_analysis_2026-03-31",
        help="Benefit-boundary analysis directory.",
    )
    parser.add_argument(
        "--romav2-dir",
        default="new1output/query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_gpu",
        help="RoMa v2 formal result directory containing per-query figures.",
    )
    parser.add_argument(
        "--out-docx",
        default="",
        help="Optional explicit output .docx path. Defaults to <analysis-dir>/reports/benefit_boundary_analysis_report.docx",
    )
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def split_sections(report_text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"^##\s+(.+?)\s*$", flags=re.MULTILINE)
    matches = list(pattern.finditer(report_text))
    sections: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(report_text)
        title = match.group(1).strip()
        body = report_text[start:end].strip()
        sections.append((title, body))
    return sections


def csv_to_markdown_table(rows: list[dict[str, str]], headers: list[tuple[str, str]]) -> str:
    header_row = "| " + " | ".join(label for _, label in headers) + " |"
    sep_row = "| " + " | ".join("---" for _ in headers) + " |"
    data_rows = []
    for row in rows:
        data_rows.append(
            "| " + " | ".join(str(row.get(key, "")).replace("\n", " ").strip() for key, _ in headers) + " |"
        )
    return "\n".join([header_row, sep_row, *data_rows])


def format_ratio(value: str) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except ValueError:
        return value


def format_float(value: str, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except ValueError:
        return value


def build_paths(args: argparse.Namespace) -> AnalysisPaths:
    analysis_dir = Path(args.analysis_dir).resolve()
    out_docx = Path(args.out_docx).resolve() if args.out_docx else analysis_dir / "reports" / "benefit_boundary_analysis_report.docx"
    return AnalysisPaths(
        analysis_dir=analysis_dir,
        report_md=analysis_dir / "reports" / "benefit_boundary_analysis_report.md",
        tables_dir=analysis_dir / "tables",
        figures_dir=analysis_dir / "figures",
        out_docx=out_docx,
        romav2_figures_dir=Path(args.romav2_dir).resolve() / "figures",
    )


def safe_relpath(target: Path, from_dir: Path) -> str:
    try:
        return Path(target.resolve().relative_to(from_dir.resolve())).as_posix()
    except ValueError:
        import os

        return os.path.relpath(target.resolve(), from_dir.resolve()).replace("\\", "/")


def find_b_images(rows: list[dict[str, str]], romav2_figures_dir: Path) -> tuple[list[tuple[dict[str, str], Path | None]], list[Path]]:
    row_map = {row["query_id"]: row for row in rows}
    results: list[tuple[dict[str, str], Path | None]] = []
    missing: list[Path] = []
    for query_id in B_QUERY_IDS:
        row = row_map[query_id]
        matches = sorted(romav2_figures_dir.rglob(f"{query_id}_top10.png"))
        image_path = matches[0] if matches else None
        if image_path is None:
            missing.append(romav2_figures_dir / "*" / f"{query_id}_top10.png")
        results.append((row, image_path))
    return results, missing


def inject_summary_figures(section_body: str, figures_dir: Path, report_dir: Path) -> str:
    chunks = [section_body.strip()]
    for fig_name in SUMMARY_FIGURES:
        fig_path = figures_dir / fig_name
        if fig_path.exists():
            rel = safe_relpath(fig_path, report_dir)
            chunks.append(f"![{fig_name}]({rel}){{ width=85% }}")
        else:
            chunks.append(f"> 图像缺失：{fig_path}")
    return "\n\n".join(chunk for chunk in chunks if chunk)


def build_case_caption(row: dict[str, str]) -> str:
    return (
        f"- query_id: `{row['query_id']}`\n"
        f"- flight_id: `{row['flight_id']}`\n"
        f"- coarse_first_truth_rank: `{row['coarse_first_truth_rank']}`\n"
        f"- romav2_first_truth_rank: `{row['romav2_first_truth_rank']}`\n"
        f"- rank_gain: `{row['rank_gain']}`\n"
        f"- delta_top1_error_m: `{format_float(row['delta_top1_error_m'])}`"
    )


def build_word_markdown(paths: AnalysisPaths) -> tuple[str, list[Path]]:
    report_text = load_text(paths.report_md)
    sections = split_sections(report_text)
    bucket_rows = load_rows(paths.tables_dir / "bucket_summary.csv")
    contribution_rows = load_rows(paths.tables_dir / "supp_table_A_r1_contribution.csv")
    c_rows = load_rows(paths.tables_dir / "supp_table_B_c_bucket_breakdown.csv")
    pitch_rows = load_rows(paths.tables_dir / "supp_table_C_pitch_group_bucket_ratio.csv")
    per_query_rows = load_rows(paths.tables_dir / "per_query_boundary_analysis.csv")
    b_rows_with_images, missing_b_images = find_b_images(per_query_rows, paths.romav2_figures_dir)

    bucket_table_rows = [
        {
            "main_bucket": row["main_bucket"],
            "query_count": row["query_count"],
            "query_ratio": format_ratio(row["query_ratio"]),
        }
        for row in bucket_rows
    ]
    contribution_table_rows = [
        {
            "main_bucket": row["main_bucket"],
            "query_count": row["query_count"],
            "direct_new_top1_hits": row["direct_new_top1_hits"],
            "share_of_total_new_top1_hits": format_ratio(row["share_of_total_new_top1_hits"]),
            "interpretation": row["interpretation"],
        }
        for row in contribution_rows
    ]
    c_table_rows = [
        {
            "c_variant": row["c_variant"],
            "query_count": row["query_count"],
            "query_ratio": format_ratio(row["query_ratio"]),
        }
        for row in c_rows
    ]
    pitch_table_rows = [
        {
            "pitch_group": row["pitch_group"],
            "query_count": row["query_count"],
            "B_count": row["B_count"],
            "B_ratio_within_pitch_group": format_ratio(row["B_ratio_within_pitch_group"]),
            "C_count": row["C_count"],
            "C_ratio_within_pitch_group": format_ratio(row["C_ratio_within_pitch_group"]),
            "D_count": row["D_count"],
            "D_ratio_within_pitch_group": format_ratio(row["D_ratio_within_pitch_group"]),
        }
        for row in pitch_rows
    ]

    body_parts = [
        "---",
        "title: \"RoMa v2 收益边界分析报告\"",
        "author: \"Codex\"",
        "date: \"2026-03-31\"",
        "---",
        "",
        "# RoMa v2 收益边界分析报告",
        "",
        "## 封面信息",
        "",
        "- 结果目录：`D:\\aiproject\\imagematch\\new1output\\benefit_boundary_analysis_2026-03-31`",
        "- 主任务口径：`query v2 + intersection truth`",
        "- coarse 唯一真源：`new1output/query_reselect_2026-03-26_v2/romav2_eval_2026-03-30_gpu/coarse/retrieval_top20.csv`",
        "- 文档类型：正式 Word 导出版",
        "",
    ]

    for title, body in sections:
        body_text = body.strip()
        body_parts.append(f"## {title}")
        body_parts.append("")
        if title == "2. 主桶结果":
            body_parts.append(body_text)
            body_parts.append("")
            body_parts.append("### 主桶数量与占比")
            body_parts.append("")
            body_parts.append(
                csv_to_markdown_table(
                    bucket_table_rows,
                    [
                        ("main_bucket", "主桶"),
                        ("query_count", "query 数"),
                        ("query_ratio", "占比"),
                    ],
                )
            )
            body_parts.append("")
            body_parts.append("### 汇总图")
            body_parts.append("")
            body_parts.append(inject_summary_figures("", paths.figures_dir, paths.out_docx.parent))
        elif title == "3. 收益解释":
            body_parts.append(body_text)
            body_parts.append("")
            body_parts.append("### 新增 Top-1 命中贡献")
            body_parts.append("")
            body_parts.append(
                csv_to_markdown_table(
                    contribution_table_rows,
                    [
                        ("main_bucket", "主桶"),
                        ("query_count", "query 数"),
                        ("direct_new_top1_hits", "新增 Top-1 命中"),
                        ("share_of_total_new_top1_hits", "新增命中占比"),
                        ("interpretation", "解释"),
                    ],
                )
            )
            body_parts.append("")
            body_parts.append("### B 类 6 个收益案例")
            body_parts.append("")
            for row, image_path in b_rows_with_images:
                body_parts.append(f"#### {row['query_id']}")
                body_parts.append("")
                if image_path is None:
                    expected = paths.romav2_figures_dir / "*" / f"{row['query_id']}_top10.png"
                    body_parts.append(f"> 图像缺失：{expected}")
                else:
                    rel = safe_relpath(image_path, paths.out_docx.parent)
                    body_parts.append(f"![{row['query_id']} top10]({rel}){{ width=90% }}")
                body_parts.append("")
                body_parts.append(build_case_caption(row))
                body_parts.append("")
        elif title == "4. 失败边界":
            body_parts.append(body_text)
            body_parts.append("")
            body_parts.append("### C 类细分")
            body_parts.append("")
            body_parts.append(
                csv_to_markdown_table(
                    c_table_rows,
                    [
                        ("c_variant", "C 细分"),
                        ("query_count", "query 数"),
                        ("query_ratio", "占比"),
                    ],
                )
            )
            body_parts.append("")
            body_parts.append("### 按 pitch_group 的 B/C/D 比例")
            body_parts.append("")
            body_parts.append(
                csv_to_markdown_table(
                    pitch_table_rows,
                    [
                        ("pitch_group", "pitch_group"),
                        ("query_count", "query 数"),
                        ("B_count", "B 数量"),
                        ("B_ratio_within_pitch_group", "B 占比"),
                        ("C_count", "C 数量"),
                        ("C_ratio_within_pitch_group", "C 占比"),
                        ("D_count", "D 数量"),
                        ("D_ratio_within_pitch_group", "D 占比"),
                    ],
                )
            )
        else:
            body_parts.append(body_text)
        body_parts.append("")

    return "\n".join(body_parts).strip() + "\n", missing_b_images


def find_pandoc() -> str:
    candidates = [
        "pandoc",
        r"D:\APPtools\anaconda\Scripts\pandoc.exe",
    ]
    for candidate in candidates:
        try:
            result = subprocess.run(
                [candidate, "--version"],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return candidate
        except FileNotFoundError:
            continue
    raise FileNotFoundError("pandoc executable not found.")


def export_docx(markdown_text: str, out_docx: Path) -> None:
    pandoc = find_pandoc()
    out_docx.parent.mkdir(parents=True, exist_ok=True)
    command = [
        pandoc,
        "-f",
        "markdown+pipe_tables",
        "-o",
        str(out_docx),
        "--standalone",
        "--resource-path",
        str(out_docx.parent),
    ]
    result = subprocess.run(command, capture_output=True, input=markdown_text.encode("utf-8"))
    if result.returncode != 0:
        raise RuntimeError(
            "pandoc export failed with code "
            f"{result.returncode}\nSTDOUT:\n{result.stdout.decode('utf-8', errors='replace')}\n"
            f"STDERR:\n{result.stderr.decode('utf-8', errors='replace')}"
        )


def main() -> int:
    args = parse_args()
    paths = build_paths(args)
    markdown_text, missing_b_images = build_word_markdown(paths)
    export_docx(markdown_text, paths.out_docx)
    for missing in missing_b_images:
        print(f"[missing-b-image] {missing}", file=sys.stderr)
    print(paths.out_docx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

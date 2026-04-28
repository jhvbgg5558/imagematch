#!/usr/bin/env python3
"""Run imagematch experiments from YAML manifests."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


METHODS = {
    "romav2_intersection",
    "lightglue_intersection",
    "dino_v2_vs_v3_comparison",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to experiment YAML.")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and print commands without executing.")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise SystemExit(f"Experiment config must be a YAML mapping: {path}")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def require_fields(config: dict[str, Any], fields: list[str]) -> None:
    missing = [name for name in fields if not config.get(name)]
    if missing:
        raise SystemExit(f"Missing required config fields: {', '.join(missing)}")


def ensure_files_exist(items: dict[str, Any], keys: list[str]) -> None:
    missing: list[str] = []
    for key in keys:
        value = items.get(key)
        if not value:
            missing.append(f"{key}: <empty>")
            continue
        if not Path(str(value)).exists():
            missing.append(f"{key}: {value}")
    if missing:
        raise SystemExit("Missing required input paths:\n- " + "\n- ".join(missing))


def normalize_config(config_path: Path, raw: dict[str, Any]) -> dict[str, Any]:
    require_fields(raw, ["experiment_id", "dataset_id", "method", "out_root"])
    method = str(raw["method"])
    if method not in METHODS:
        raise SystemExit(f"Unsupported method: {method}. Supported: {', '.join(sorted(METHODS))}")

    config = dict(raw)
    config["config_path"] = str(config_path.resolve())
    config["method"] = method
    config["python_bin"] = str(config.get("python_bin") or sys.executable)
    config["out_root"] = str(Path(str(config["out_root"])).resolve())
    config["query_round_root"] = str(Path(str(config.get("query_round_root", "."))).resolve())
    config["inputs"] = dict(config.get("inputs") or {})
    config["params"] = dict(config.get("params") or {})
    config["docs"] = dict(config.get("docs") or {})
    config["update_docs"] = bool(config.get("update_docs", False))
    return config


def workflow_paths(config: dict[str, Any]) -> dict[str, Path]:
    out_root = Path(config["out_root"])
    docs_cfg = config.get("docs", {})
    snippet_path = Path(str(docs_cfg["summary_snippet_path"])) if docs_cfg.get("summary_snippet_path") else out_root / "docs_snippet.md"
    return {
        "out_root": out_root,
        "status_json": out_root / "workflow_status.json",
        "summary_json": out_root / "workflow_summary.json",
        "resolved_yaml": out_root / "resolved_config.yaml",
        "log_txt": out_root / "workflow_log.txt",
        "snippet_md": snippet_path,
    }


def update_status(
    path: Path,
    config: dict[str, Any],
    *,
    status: str,
    current_stage: str | None,
    completed_stages: list[str],
    command_history: list[dict[str, Any]],
    error: str | None = None,
) -> None:
    payload = {
        "experiment_id": config["experiment_id"],
        "dataset_id": config["dataset_id"],
        "method": config["method"],
        "status": status,
        "current_stage": current_stage,
        "completed_stages": completed_stages,
        "updated_at": utc_now(),
        "out_root": config["out_root"],
        "config_path": config["config_path"],
        "command_history": command_history,
    }
    if error:
        payload["error"] = error
    write_json(path, payload)


def stream_command(cmd: list[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        rendered = shlex.join(cmd)
        log.write(f"$ {rendered}\n")
        log.flush()
        print(f"$ {rendered}")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
        proc.wait()
        log.write(f"[exit_code={proc.returncode}]\n")
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)


def build_report_paths(out_root: Path, stem: str) -> tuple[Path, Path]:
    reports_dir = out_root / "reports"
    return reports_dir / f"{stem}.md", reports_dir / f"{stem}.docx"


def build_method_commands(config: dict[str, Any]) -> list[tuple[str, list[str]]]:
    repo_root = Path(__file__).resolve().parents[1]
    script_dir = repo_root / "scripts"
    python_bin = config["python_bin"]
    inputs = config["inputs"]
    params = config["params"]
    out_root = Path(config["out_root"])
    method = config["method"]

    if method == "romav2_intersection":
        ensure_files_exist(
            inputs,
            [
                "baseline_result_dir",
                "query_features_npz",
                "query_seed_csv",
                "query_truth_tiles_csv",
                "faiss_index",
                "mapping_json",
                "query_manifest_csv",
                "tiles_csv",
            ],
        )
        top_k = int(params.get("top_k", 20))
        return [
            (
                "romav2_pipeline",
                [
                    python_bin,
                    str(script_dir / "run_romav2_intersection_pipeline.py"),
                    "--baseline-result-dir",
                    str(inputs["baseline_result_dir"]),
                    "--query-features-npz",
                    str(inputs["query_features_npz"]),
                    "--query-seed-csv",
                    str(inputs["query_seed_csv"]),
                    "--query-truth-tiles-csv",
                    str(inputs["query_truth_tiles_csv"]),
                    "--faiss-index",
                    str(inputs["faiss_index"]),
                    "--mapping-json",
                    str(inputs["mapping_json"]),
                    "--query-manifest-csv",
                    str(inputs["query_manifest_csv"]),
                    "--tiles-csv",
                    str(inputs["tiles_csv"]),
                    "--out-root",
                    str(out_root),
                    "--top-k",
                    str(top_k),
                    "--python-bin",
                    python_bin,
                    "--device",
                    str(params.get("device", "cpu")),
                    "--setting",
                    str(params.get("setting", "satast")),
                    "--sample-count",
                    str(int(params.get("sample_count", 5000))),
                    "--ransac-reproj-thresh",
                    str(float(params.get("ransac_reproj_thresh", 4.0))),
                    "--min-inliers",
                    str(int(params.get("min_inliers", 20))),
                    "--min-inlier-ratio",
                    str(float(params.get("min_inlier_ratio", 0.01))),
                    "--promotion-rank-gate",
                    str(int(params.get("promotion_rank_gate", 5))),
                    "--ranking-mode",
                    str(params.get("ranking_mode", "fused")),
                    "--global-weight",
                    str(float(params.get("global_weight", 0.4))),
                    "--geom-weight",
                    str(float(params.get("geom_weight", 0.6))),
                    "--valid-bonus",
                    str(float(params.get("valid_bonus", 0.1))),
                    "--promotion-bonus",
                    str(float(params.get("promotion_bonus", 0.05))),
                    "--coarse-model-label",
                    str(params.get("coarse_model_label", "DINOv3")),
                ],
            )
        ]

    if method == "lightglue_intersection":
        ensure_files_exist(
            inputs,
            [
                "baseline_result_dir",
                "query_features_npz",
                "query_seed_csv",
                "query_truth_tiles_csv",
                "faiss_index",
                "mapping_json",
                "query_manifest_csv",
                "tiles_csv",
            ],
        )
        top_k = int(params.get("top_k", 50))
        report_md, report_docx = build_report_paths(out_root, f"LightGlue_intersection_truth_top{top_k}_workflow")
        return [
            (
                "lightglue_pipeline",
                [
                    python_bin,
                    str(script_dir / "run_lightglue_intersection_pipeline.py"),
                    "--baseline-result-dir",
                    str(inputs["baseline_result_dir"]),
                    "--query-features-npz",
                    str(inputs["query_features_npz"]),
                    "--query-seed-csv",
                    str(inputs["query_seed_csv"]),
                    "--query-truth-tiles-csv",
                    str(inputs["query_truth_tiles_csv"]),
                    "--faiss-index",
                    str(inputs["faiss_index"]),
                    "--mapping-json",
                    str(inputs["mapping_json"]),
                    "--query-manifest-csv",
                    str(inputs["query_manifest_csv"]),
                    "--tiles-csv",
                    str(inputs["tiles_csv"]),
                    "--out-root",
                    str(out_root),
                    "--top-k",
                    str(top_k),
                    "--python-bin",
                    python_bin,
                    "--max-num-keypoints",
                    str(int(params.get("max_num_keypoints", 256))),
                    "--device",
                    str(params.get("device", "cpu")),
                    "--min-inliers",
                    str(int(params.get("min_inliers", 5))),
                    "--min-inlier-ratio",
                    str(float(params.get("min_inlier_ratio", 0.5))),
                    "--promotion-rank-gate",
                    str(int(params.get("promotion_rank_gate", 5))),
                    "--ranking-mode",
                    str(params.get("ranking_mode", "fused")),
                    "--global-weight",
                    str(float(params.get("global_weight", 0.4))),
                    "--geom-weight",
                    str(float(params.get("geom_weight", 0.6))),
                    "--valid-bonus",
                    str(float(params.get("valid_bonus", 0.1))),
                    "--promotion-bonus",
                    str(float(params.get("promotion_bonus", 0.05))),
                ],
            ),
            (
                "lightglue_report",
                [
                    python_bin,
                    str(script_dir / "generate_lightglue_intersection_report.py"),
                    "--result-dir",
                    str(out_root),
                    "--out-md",
                    str(report_md),
                    "--out-docx",
                    str(report_docx),
                ],
            ),
        ]

    if method == "dino_v2_vs_v3_comparison":
        ensure_files_exist(inputs, ["dinov2_dir", "dinov3_dir"])
        report_md, report_docx = build_report_paths(out_root, "DINOv3_vs_DINOv2_intersection_truth_v2_workflow")
        return [
            (
                "dino_comparison_report",
                [
                    python_bin,
                    str(script_dir / "generate_dino_v2_vs_v3_comparison_report.py"),
                    "--dinov2-dir",
                    str(inputs["dinov2_dir"]),
                    "--dinov3-dir",
                    str(inputs["dinov3_dir"]),
                    "--out-md",
                    str(report_md),
                    "--out-docx",
                    str(report_docx),
                ],
            )
        ]

    raise SystemExit(f"Unsupported method: {method}")


def collect_method_summary(config: dict[str, Any]) -> dict[str, Any]:
    out_root = Path(config["out_root"])
    method = config["method"]
    inputs = config["inputs"]

    if method == "romav2_intersection":
        overall_path = out_root / "overall_summary.json"
        timing_path = out_root / "timing" / "timing_summary.json"
        summary = {
            "overall_summary_path": str(overall_path),
            "docs_snippet_path": str(workflow_paths(config)["snippet_md"]),
        }
        if overall_path.exists():
            overall = json.loads(overall_path.read_text(encoding="utf-8"))
            summary["metrics"] = {
                "baseline_r10": overall["baseline_intersection_recall@10"],
                "romav2_r10": overall["romav2_intersection_recall@10"],
                "delta_r10": overall["delta_intersection_recall@10"],
                "baseline_mrr": overall["baseline_intersection_mrr"],
                "romav2_mrr": overall["romav2_intersection_mrr"],
                "delta_mrr": overall["delta_intersection_mrr"],
            }
        if timing_path.exists():
            summary["timing_summary_path"] = str(timing_path)
        return summary

    if method == "lightglue_intersection":
        overall_path = out_root / "overall_summary.json"
        timing_path = out_root / "timing" / "timing_summary.json"
        summary = {
            "overall_summary_path": str(overall_path),
            "docs_snippet_path": str(workflow_paths(config)["snippet_md"]),
        }
        if overall_path.exists():
            overall = json.loads(overall_path.read_text(encoding="utf-8"))
            summary["metrics"] = {
                "baseline_r10": overall["baseline_intersection_recall@10"],
                "lightglue_r10": overall["lightglue_intersection_recall@10"],
                "delta_r10": overall["delta_intersection_recall@10"],
                "baseline_mrr": overall["baseline_intersection_mrr"],
                "lightglue_mrr": overall["lightglue_intersection_mrr"],
                "delta_mrr": overall["delta_intersection_mrr"],
            }
        if timing_path.exists():
            summary["timing_summary_path"] = str(timing_path)
        return summary

    if method == "dino_v2_vs_v3_comparison":
        dinov2_summary = json.loads((Path(inputs["dinov2_dir"]) / "retrieval" / "summary_top20.json").read_text(encoding="utf-8"))
        dinov3_summary = json.loads((Path(inputs["dinov3_dir"]) / "retrieval" / "summary_top20.json").read_text(encoding="utf-8"))
        return {
            "docs_snippet_path": str(workflow_paths(config)["snippet_md"]),
            "metrics": {
                "dinov2_r1": dinov2_summary["intersection_recall@1"],
                "dinov3_r1": dinov3_summary["intersection_recall@1"],
                "delta_r1": float(dinov3_summary["intersection_recall@1"]) - float(dinov2_summary["intersection_recall@1"]),
                "dinov2_mrr": dinov2_summary["intersection_mrr"],
                "dinov3_mrr": dinov3_summary["intersection_mrr"],
                "delta_mrr": float(dinov3_summary["intersection_mrr"]) - float(dinov2_summary["intersection_mrr"]),
            },
        }

    return {}


def build_docs_snippet(config: dict[str, Any], summary: dict[str, Any]) -> str:
    method = config["method"]
    experiment_id = config["experiment_id"]
    dataset_id = config["dataset_id"]
    out_root = config["out_root"]
    lines = [
        f"# {experiment_id}",
        "",
        f"- dataset_id: `{dataset_id}`",
        f"- method: `{method}`",
        f"- out_root: `{out_root}`",
    ]
    metrics = summary.get("metrics", {})

    if method == "romav2_intersection" and metrics:
        lines.extend(
            [
                f"- baseline R@10: `{metrics['baseline_r10']:.3f}`",
                f"- RoMa v2 R@10: `{metrics['romav2_r10']:.3f}`",
                f"- ΔR@10: `{metrics['delta_r10']:+.3f}`",
                f"- baseline MRR: `{metrics['baseline_mrr']:.3f}`",
                f"- RoMa v2 MRR: `{metrics['romav2_mrr']:.3f}`",
                f"- ΔMRR: `{metrics['delta_mrr']:+.3f}`",
            ]
        )
    elif method == "lightglue_intersection" and metrics:
        lines.extend(
            [
                f"- baseline R@10: `{metrics['baseline_r10']:.3f}`",
                f"- LightGlue R@10: `{metrics['lightglue_r10']:.3f}`",
                f"- ΔR@10: `{metrics['delta_r10']:+.3f}`",
                f"- baseline MRR: `{metrics['baseline_mrr']:.3f}`",
                f"- LightGlue MRR: `{metrics['lightglue_mrr']:.3f}`",
                f"- ΔMRR: `{metrics['delta_mrr']:+.3f}`",
            ]
        )
    elif method == "dino_v2_vs_v3_comparison" and metrics:
        lines.extend(
            [
                f"- DINOv2 R@1: `{metrics['dinov2_r1']:.3f}`",
                f"- DINOv3 R@1: `{metrics['dinov3_r1']:.3f}`",
                f"- ΔR@1 (v3-v2): `{metrics['delta_r1']:+.3f}`",
                f"- DINOv2 MRR: `{metrics['dinov2_mrr']:.3f}`",
                f"- DINOv3 MRR: `{metrics['dinov3_mrr']:.3f}`",
                f"- ΔMRR (v3-v2): `{metrics['delta_mrr']:+.3f}`",
            ]
        )

    lines.extend(["", "- 建议：如需写入主进度文档，优先摘取本摘要中的 overall 指标与结论。"])
    return "\n".join(lines) + "\n"


def build_summary_payload(config: dict[str, Any], command_history: list[dict[str, Any]], status: str, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": config["experiment_id"],
        "dataset_id": config["dataset_id"],
        "method": config["method"],
        "status": status,
        "config_path": config["config_path"],
        "out_root": config["out_root"],
        "command_history": command_history,
        "summary": summary,
        "update_docs": config["update_docs"],
    }


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).resolve()
    raw = load_yaml(config_path)
    config = normalize_config(config_path, raw)
    paths = workflow_paths(config)
    commands = build_method_commands(config)

    if args.dry_run:
        print(f"experiment_id: {config['experiment_id']}")
        print(f"dataset_id: {config['dataset_id']}")
        print(f"method: {config['method']}")
        print(f"out_root: {config['out_root']}")
        print("planned_stages:")
        for stage_name, cmd in commands:
            print(f"- {stage_name}: {shlex.join(cmd)}")
        return

    paths["out_root"].mkdir(parents=True, exist_ok=True)
    write_yaml(paths["resolved_yaml"], config)
    command_history: list[dict[str, Any]] = []
    completed_stages: list[str] = []
    update_status(
        paths["status_json"],
        config,
        status="running",
        current_stage=commands[0][0] if commands else None,
        completed_stages=completed_stages,
        command_history=command_history,
    )

    try:
        for stage_name, cmd in commands:
            update_status(
                paths["status_json"],
                config,
                status="running",
                current_stage=stage_name,
                completed_stages=completed_stages,
                command_history=command_history,
            )
            stream_command(cmd, paths["log_txt"])
            command_history.append({"stage": stage_name, "cmd": cmd, "finished_at": utc_now()})
            completed_stages.append(stage_name)

        summary = collect_method_summary(config)
        paths["snippet_md"].parent.mkdir(parents=True, exist_ok=True)
        paths["snippet_md"].write_text(build_docs_snippet(config, summary), encoding="utf-8")
        write_json(paths["summary_json"], build_summary_payload(config, command_history, "completed", summary))
        update_status(
            paths["status_json"],
            config,
            status="completed",
            current_stage=None,
            completed_stages=completed_stages,
            command_history=command_history,
        )
        print(paths["summary_json"])
    except Exception as exc:  # noqa: BLE001
        error_text = f"{type(exc).__name__}: {exc}"
        tb = traceback.format_exc()
        paths["log_txt"].parent.mkdir(parents=True, exist_ok=True)
        with paths["log_txt"].open("a", encoding="utf-8") as log:
            log.write("\n[workflow_error]\n")
            log.write(tb)
        write_json(paths["summary_json"], build_summary_payload(config, command_history, "failed", {"error": error_text}))
        update_status(
            paths["status_json"],
            config,
            status="failed",
            current_stage=None,
            completed_stages=completed_stages,
            command_history=command_history,
            error=error_text,
        )
        raise


if __name__ == "__main__":
    main()

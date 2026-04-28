#!/usr/bin/env python3
"""Measure per-query feature extraction and FAISS retrieval timing."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter

import faiss
import numpy as np
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure per-query timing for feature extraction and retrieval.")
    parser.add_argument("--query-csv", required=True, help="CSV with query_id and image_path.")
    parser.add_argument("--faiss-index", required=True, help="FAISS index path.")
    parser.add_argument("--model-name", default="facebook/dinov2-base")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda", "auto"])
    parser.add_argument("--input-size", type=int, default=518)
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--pooling", default="pooler", choices=["pooler", "cls", "mean", "gem"])
    parser.add_argument("--gem-p", type=float, default=3.0)
    return parser.parse_args()


def choose_device(name: str) -> str:
    import torch

    if name == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return name


def build_transform(input_size: int):
    from torchvision import transforms

    return transforms.Compose(
        [
            transforms.Resize((input_size, input_size), interpolation=transforms.InterpolationMode.BICUBIC),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=(0.485, 0.456, 0.406),
                std=(0.229, 0.224, 0.225),
            ),
        ]
    )


def load_queries(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def aggregate_tokens(outputs, pooling: str, gem_p: float):
    import torch

    last_hidden = outputs.last_hidden_state
    cls_token = last_hidden[:, 0]
    patch_tokens = last_hidden[:, 1:] if last_hidden.shape[1] > 1 else cls_token.unsqueeze(1)

    if pooling == "pooler":
        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            return outputs.pooler_output
        return cls_token
    if pooling == "cls":
        return cls_token
    if pooling == "mean":
        return patch_tokens.mean(dim=1)
    if pooling == "gem":
        return patch_tokens.clamp_min(1e-6).pow(gem_p).mean(dim=1).pow(1.0 / gem_p)
    raise ValueError(f"Unsupported pooling: {pooling}")


def summarize(values: list[float]) -> dict[str, float]:
    values_ms = [v * 1000.0 for v in values]
    if not values_ms:
        return {"count": 0, "mean_ms": 0.0, "median_ms": 0.0, "p90_ms": 0.0}
    ordered = sorted(values_ms)
    p90_idx = min(len(ordered) - 1, max(0, int(np.ceil(0.9 * len(ordered)) - 1)))
    return {
        "count": len(values_ms),
        "mean_ms": mean(values_ms),
        "median_ms": median(values_ms),
        "p90_ms": ordered[p90_idx],
    }


def main() -> None:
    import torch
    from transformers import AutoModel

    args = parse_args()
    output_csv = Path(args.output_csv)
    summary_json = Path(args.summary_json)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_json.parent.mkdir(parents=True, exist_ok=True)

    device = choose_device(args.device)
    transform = build_transform(args.input_size)
    model = AutoModel.from_pretrained(args.model_name, local_files_only=args.local_files_only)
    model.eval()
    model.to(device)
    index = faiss.read_index(args.faiss_index)
    queries = load_queries(Path(args.query_csv))
    if not queries:
        raise SystemExit("No queries loaded.")

    def encode(image_path: str):
        with Image.open(image_path) as img:
            tensor = transform(img.convert("RGB")).unsqueeze(0).to(device)
        with torch.inference_mode():
            outputs = model(pixel_values=tensor)
            feat = aggregate_tokens(outputs, args.pooling, args.gem_p)
            feat = torch.nn.functional.normalize(feat, dim=1)
        return feat.detach().cpu().numpy().astype("float32")

    # Warmup
    for _ in range(max(0, args.warmup_runs)):
        _ = encode(queries[0]["image_path"])

    feature_times = []
    retrieval_times = []
    total_times = []
    per_query_rows = []

    for row in queries:
        qid = row["query_id"]
        image_path = row["image_path"]

        t0 = perf_counter()
        t_feat0 = perf_counter()
        feat = encode(image_path)
        t_feat = perf_counter() - t_feat0

        t_ret0 = perf_counter()
        _scores, _indices = index.search(feat, 10)
        t_ret = perf_counter() - t_ret0
        t_total = perf_counter() - t0

        feature_times.append(t_feat)
        retrieval_times.append(t_ret)
        total_times.append(t_total)
        per_query_rows.append(
            {
                "query_id": qid,
                "feature_ms": t_feat * 1000.0,
                "retrieval_ms": t_ret * 1000.0,
                "total_ms": t_total * 1000.0,
            }
        )

    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query_id", "feature_ms", "retrieval_ms", "total_ms"])
        writer.writeheader()
        writer.writerows(per_query_rows)

    summary = {
        "pooling": args.pooling,
        "feature_timing": summarize(feature_times),
        "retrieval_timing": summarize(retrieval_times),
        "total_timing": summarize(total_times),
    }
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Timing CSV saved to {output_csv}")
    print(f"Timing summary saved to {summary_json}")
    print(
        "Finished. "
        f"feature_mean_ms={summary['feature_timing']['mean_ms']:.2f} "
        f"retrieval_mean_ms={summary['retrieval_timing']['mean_ms']:.2f} "
        f"total_mean_ms={summary['total_timing']['mean_ms']:.2f}"
    )


if __name__ == "__main__":
    main()

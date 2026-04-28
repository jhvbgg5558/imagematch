#!/usr/bin/env python3
"""Extract global DINOv2 features for satellite or query images."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract DINOv2 global features.")
    parser.add_argument(
        "--input-csv",
        required=True,
        help="CSV containing image_path and id columns.",
    )
    parser.add_argument(
        "--id-column",
        default="tile_id",
        help="ID column name in input CSV. Default: tile_id",
    )
    parser.add_argument(
        "--image-column",
        default="image_path",
        help="Image path column name in input CSV. Default: image_path",
    )
    parser.add_argument(
        "--output-npz",
        required=True,
        help="Output .npz file containing ids and feature matrix.",
    )
    parser.add_argument(
        "--output-csv",
        required=True,
        help="Output CSV with status for each sample.",
    )
    parser.add_argument(
        "--model-name",
        default="facebook/dinov2-base",
        help="Hugging Face model name. Default: facebook/dinov2-base",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for feature extraction.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="Execution device.",
    )
    parser.add_argument(
        "--input-size",
        type=int,
        default=518,
        help="Square image size fed to DINOv2 after resize. Default: 518.",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Load model weights from local Hugging Face cache only.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional sample limit for smoke tests.",
    )
    parser.add_argument(
        "--pooling",
        default="pooler",
        choices=["pooler", "cls", "mean", "gem"],
        help="Global pooling strategy. Default: pooler",
    )
    parser.add_argument(
        "--gem-p",
        type=float,
        default=3.0,
        help="GeM exponent when --pooling=gem. Default: 3.0",
    )
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


def load_rows(path: Path, id_column: str, image_column: str, limit: int) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if id_column not in reader.fieldnames or image_column not in reader.fieldnames:
            raise SystemExit(
                f"CSV must contain columns {id_column!r} and {image_column!r}; "
                f"found {reader.fieldnames}"
            )
        rows = list(reader)
    if limit > 0:
        rows = rows[:limit]
    return rows


def batches(items: list[dict[str, str]], batch_size: int):
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def read_images(batch_rows: list[dict[str, str]], image_column: str, transform):
    tensors = []
    ok_rows = []
    failed = []
    for row in batch_rows:
        path = Path(row[image_column])
        try:
            with Image.open(path) as img:
                tensors.append(transform(img.convert("RGB")))
            ok_rows.append(row)
        except Exception as exc:  # pragma: no cover - external files
            failed.append((row, str(exc)))
    return tensors, ok_rows, failed


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
        pooled = patch_tokens.clamp_min(1e-6).pow(gem_p).mean(dim=1).pow(1.0 / gem_p)
        return pooled
    raise ValueError(f"Unsupported pooling: {pooling}")


def main() -> None:
    import torch
    from transformers import AutoModel

    args = parse_args()
    input_csv = Path(args.input_csv)
    output_npz = Path(args.output_npz)
    output_csv = Path(args.output_csv)
    output_npz.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    rows = load_rows(input_csv, args.id_column, args.image_column, args.limit)
    if not rows:
        raise SystemExit("No rows to process.")

    device = choose_device(args.device)
    print(f"Samples: {len(rows)}")
    print(f"Device: {device}")
    print(f"Model: {args.model_name}")
    print(f"Input size: {args.input_size}")
    print(f"Pooling: {args.pooling}")

    transform = build_transform(args.input_size)
    model = AutoModel.from_pretrained(args.model_name, local_files_only=args.local_files_only)
    model.eval()
    model.to(device)

    ids: list[str] = []
    features: list[np.ndarray] = []
    statuses: list[tuple[str, str, str]] = []

    t0 = perf_counter()
    processed = 0

    with torch.inference_mode():
        for batch in batches(rows, args.batch_size):
            tensors, ok_rows, failed_rows = read_images(batch, args.image_column, transform)
            for row, error in failed_rows:
                statuses.append((row[args.id_column], row[args.image_column], f"read_failed: {error}"))

            if not ok_rows:
                processed += len(batch)
                continue

            pixel_values = torch.stack(tensors, dim=0).to(device)
            outputs = model(pixel_values=pixel_values)
            batch_features = aggregate_tokens(outputs, args.pooling, args.gem_p)
            batch_features = torch.nn.functional.normalize(batch_features, dim=1)
            batch_np = batch_features.detach().cpu().numpy().astype("float32")

            for row, feat in zip(ok_rows, batch_np):
                ids.append(row[args.id_column])
                features.append(feat)
                statuses.append((row[args.id_column], row[args.image_column], "ok"))

            processed += len(batch)
            if processed % 200 == 0 or processed == len(rows):
                elapsed = perf_counter() - t0
                print(f"[{processed}/{len(rows)}] ok={len(ids)} elapsed={elapsed/60:.1f}min")

    matrix = np.vstack(features) if features else np.zeros((0, 0), dtype="float32")
    np.savez_compressed(output_npz, ids=np.array(ids, dtype=object), features=matrix)

    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([args.id_column, args.image_column, "status"])
        writer.writerows(statuses)

    elapsed = perf_counter() - t0
    print(f"Features saved to {output_npz}")
    print(f"Status CSV saved to {output_csv}")
    print(f"Finished. ok={len(ids)} total={len(rows)} elapsed={elapsed/60:.1f}min")


if __name__ == "__main__":
    main()

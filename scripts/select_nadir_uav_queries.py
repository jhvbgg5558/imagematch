#!/usr/bin/env python3
"""Select nadir-like UAV query images for the 009/010 pose experiment.

Purpose:
- select exactly 20 near-nadir query images from each of the fixed 009 and 010
  UAV flights;
- keep the selected-query CSV schema compatible with the existing query
  sanitization and coverage-truth scripts;
- fail loudly if either flight lacks enough `gimbal_pitch_degree <= -85.0`
  candidates.

Main inputs:
- raw UAV flight directories under `D:/数据/武汉影像/无人机0.1m`;
- DJI XMP metadata embedded in each original JPG.

Main outputs:
- copied selected JPGs under `<output-root>/selected_queries/<flight_id>/`;
- `<output-root>/selected_queries/selected_images_summary.csv`;
- per-flight `selected_images.csv` and `selection_notes.md`.

Applicable task constraints:
- only flights 009 and 010 are eligible;
- query IDs are assigned later by downstream scripts from row order, so this
  script writes 009 rows first, then 010 rows;
- metadata may be used for offline selection and truth construction only, not
  as runtime retrieval input.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


DEFAULT_RAW_UAV_ROOT = Path("D:/数据/武汉影像/无人机0.1m")
DEFAULT_EXPERIMENT_ROOT = Path("new2output/nadir_009010_dinov2_romav2_pose_2026-04-10")
DEFAULT_FLIGHTS = (
    "DJI_202510311347_009_新建面状航线1",
    "DJI_202510311413_010_新建面状航线1",
)
XMP_PATTERNS = {
    "gps_latitude": re.compile(rb'drone-dji:GpsLatitude="([+-]?[0-9.]+)"'),
    "gps_longitude": re.compile(rb'drone-dji:GpsLongitude="([+-]?[0-9.]+)"'),
    "absolute_altitude": re.compile(rb'drone-dji:AbsoluteAltitude="([+-]?[0-9.]+)"'),
    "relative_altitude": re.compile(rb'drone-dji:RelativeAltitude="([+-]?[0-9.]+)"'),
    "gimbal_pitch_degree": re.compile(rb'drone-dji:GimbalPitchDegree="([+-]?[0-9.]+)"'),
    "gimbal_yaw_degree": re.compile(rb'drone-dji:GimbalYawDegree="([+-]?[0-9.]+)"'),
    "flight_pitch_degree": re.compile(rb'drone-dji:FlightPitchDegree="([+-]?[0-9.]+)"'),
}
IMAGE_NAME_RE = re.compile(r"_(\d{4})_V\.JPG$", re.IGNORECASE)


@dataclass(frozen=True)
class ImageRecord:
    flight_id: str
    image_name: str
    image_path: Path
    frame_index: int
    latitude: float
    longitude: float
    absolute_altitude: float
    relative_altitude: float
    gimbal_pitch_degree: float
    gimbal_yaw_degree: float
    flight_pitch_degree: float

    @property
    def pitch_error_from_nadir(self) -> float:
        return abs(self.gimbal_pitch_degree + 90.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", default=str(DEFAULT_RAW_UAV_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_EXPERIMENT_ROOT))
    parser.add_argument("--flight-id", action="append", default=[])
    parser.add_argument("--per-flight-count", type=int, default=20)
    parser.add_argument("--pitch-max", type=float, default=-85.0)
    parser.add_argument(
        "--allow-nonformal-override",
        action="store_true",
        help="Allow non-formal flight/count/pitch overrides for diagnostics only.",
    )
    parser.add_argument(
        "--path-style",
        choices=("native", "wsl"),
        default="wsl",
        help="How paths are written into CSV manifests. Use wsl for the .conda WSL runtime.",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def validate_formal_args(args: argparse.Namespace, flights: tuple[str, ...]) -> None:
    if args.allow_nonformal_override:
        return
    if flights != DEFAULT_FLIGHTS:
        raise SystemExit("formal nadir experiment only allows the fixed 009/010 flight pair")
    if args.per_flight_count != 20:
        raise SystemExit("formal nadir experiment requires exactly 20 queries per flight")
    if abs(args.pitch_max - (-85.0)) > 1e-9:
        raise SystemExit("formal nadir experiment requires gimbal_pitch_degree <= -85.0")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def resolve_runtime_path(path: str | Path) -> Path:
    text = str(path)
    if os.name != "nt" and len(text) >= 3 and text[1:3] in {":\\", ":/"}:
        drive = text[0].lower()
        rest = text[3:].replace("\\", "/")
        return Path(f"/mnt/{drive}/{rest}")
    if os.name == "nt" and text.startswith("/mnt/") and len(text) > 6:
        drive = text[5].upper()
        rest = text[7:].replace("/", "\\")
        return Path(f"{drive}:\\{rest}")
    return Path(text)


def to_manifest_path(path: Path, path_style: str) -> str:
    resolved = path.resolve()
    text = str(resolved).replace("\\", "/")
    if path_style == "wsl" and len(text) >= 3 and text[1:3] == ":/":
        return f"/mnt/{text[0].lower()}{text[2:]}"
    return text


def parse_record(flight_id: str, image_path: Path) -> ImageRecord | None:
    data = image_path.read_bytes()
    values: dict[str, float] = {}
    for key, pattern in XMP_PATTERNS.items():
        match = pattern.search(data)
        if not match:
            return None
        values[key] = float(match.group(1).decode("utf-8"))

    frame_match = IMAGE_NAME_RE.search(image_path.name)
    if not frame_match:
        return None
    return ImageRecord(
        flight_id=flight_id,
        image_name=image_path.name,
        image_path=image_path,
        frame_index=int(frame_match.group(1)),
        latitude=values["gps_latitude"],
        longitude=values["gps_longitude"],
        absolute_altitude=values["absolute_altitude"],
        relative_altitude=values["relative_altitude"],
        gimbal_pitch_degree=values["gimbal_pitch_degree"],
        gimbal_yaw_degree=values["gimbal_yaw_degree"],
        flight_pitch_degree=values["flight_pitch_degree"],
    )


def load_eligible_records(flight_root: Path, pitch_max: float) -> list[ImageRecord]:
    rows: list[ImageRecord] = []
    for image_path in sorted(flight_root.glob("*.JPG")):
        record = parse_record(flight_root.name, image_path)
        if record is None:
            continue
        if record.gimbal_pitch_degree <= pitch_max:
            rows.append(record)
    return rows


def evenly_sample(records: list[ImageRecord], count: int) -> list[ImageRecord]:
    if len(records) <= count:
        return sorted(records, key=lambda item: item.frame_index)
    sorted_rows = sorted(records, key=lambda item: item.frame_index)
    if count == 1:
        return [sorted_rows[len(sorted_rows) // 2]]
    indices = sorted({round(i * (len(sorted_rows) - 1) / (count - 1)) for i in range(count)})
    while len(indices) < count:
        for idx in range(len(sorted_rows)):
            if idx not in indices:
                indices.add(idx)
                if len(indices) == count:
                    break
    return [sorted_rows[idx] for idx in sorted(indices)]


def select_records(records: list[ImageRecord], count: int) -> list[ImageRecord]:
    if len(records) < count:
        raise SystemExit(f"eligible nadir candidates={len(records)} is less than required count={count}")

    errors = sorted({round(item.pitch_error_from_nadir, 6) for item in records})
    pool: list[ImageRecord] = []
    for error in errors:
        pool.extend([item for item in records if round(item.pitch_error_from_nadir, 6) == error])
        if len(pool) >= count:
            break
    return evenly_sample(pool, count)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise SystemExit(f"no rows to write: {path}")
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def selected_row(record: ImageRecord, copied_path: Path, path_style: str) -> dict[str, str]:
    return {
        "flight_id": record.flight_id,
        "image_name": record.image_name,
        "original_path": to_manifest_path(record.image_path, path_style),
        "copied_path": to_manifest_path(copied_path, path_style),
        "latitude": f"{record.latitude:.9f}",
        "longitude": f"{record.longitude:.9f}",
        "absolute_altitude": f"{record.absolute_altitude:.3f}",
        "relative_altitude": f"{record.relative_altitude:.3f}",
        "gimbal_pitch_degree": f"{record.gimbal_pitch_degree:.2f}",
        "gimbal_yaw_degree": f"{record.gimbal_yaw_degree:.2f}",
        "flight_pitch_degree": f"{record.flight_pitch_degree:.2f}",
        "tags": "nadir",
        "pitch_group": "nadir",
        "selection_reason": "Selected from strict nadir pool with gimbal_pitch_degree <= -85.0 and even frame spacing.",
        "review_status": "auto_selected_nadir_009010",
    }


def write_notes(path: Path, rows: list[dict[str, str]], eligible_count: int, selected_count: int, pitch_max: float) -> None:
    pitches = [float(row["gimbal_pitch_degree"]) for row in rows]
    frames = [IMAGE_NAME_RE.search(row["image_name"]).group(1) for row in rows if IMAGE_NAME_RE.search(row["image_name"])]
    text = [
        "# Nadir Query Selection Notes",
        "",
        f"- Eligible pitch rule: `gimbal_pitch_degree <= {pitch_max:.1f}`.",
        f"- Eligible candidates: `{eligible_count}`.",
        f"- Selected candidates: `{selected_count}`.",
        f"- Selected pitch min/max: `{min(pitches):.2f}` / `{max(pitches):.2f}`.",
        f"- Selected frame range: `{frames[0] if frames else ''}` to `{frames[-1] if frames else ''}`.",
    ]
    path.write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_root = resolve_runtime_path(args.input_root)
    output_root = resolve_runtime_path(args.output_root)
    selected_root = output_root / "selected_queries"
    flights = tuple(args.flight_id) if args.flight_id else DEFAULT_FLIGHTS
    validate_formal_args(args, flights)

    if not input_root.exists():
        raise SystemExit(f"input root not found: {input_root}")
    ensure_dir(selected_root)

    all_rows: list[dict[str, str]] = []
    for flight_id in flights:
        flight_root = input_root / flight_id
        if not flight_root.exists():
            raise SystemExit(f"flight root not found: {flight_root}")
        eligible = load_eligible_records(flight_root, args.pitch_max)
        selected = select_records(eligible, args.per_flight_count)

        flight_out = selected_root / flight_id
        if flight_out.exists() and args.overwrite:
            for jpg in flight_out.glob("*.JPG"):
                jpg.unlink()
        ensure_dir(flight_out)

        flight_rows: list[dict[str, str]] = []
        for record in selected:
            copied = flight_out / record.image_name
            if copied.exists() and not args.overwrite:
                pass
            else:
                shutil.copy2(record.image_path, copied)
            row = selected_row(record, copied, args.path_style)
            flight_rows.append(row)
            all_rows.append(row)

        write_csv(flight_out / "selected_images.csv", flight_rows)
        write_notes(
            flight_out / "selection_notes.md",
            flight_rows,
            eligible_count=len(eligible),
            selected_count=len(selected),
            pitch_max=args.pitch_max,
        )

    write_csv(selected_root / "selected_images_summary.csv", all_rows)
    print(selected_root / "selected_images_summary.csv")


if __name__ == "__main__":
    main()

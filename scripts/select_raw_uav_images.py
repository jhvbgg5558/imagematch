#!/usr/bin/env python3
"""Select representative raw UAV images from four flights.

Inputs:
- raw UAV flight directories containing original JPG images
- DJI EXIF/XMP metadata embedded in each JPG

Outputs:
- copied JPG selections per flight
- per-flight CSV manifests
- aggregate CSV manifest

Used for:
- current engineering-style retrieval task where query is an arbitrary UAV image
- pre-truth-construction sample selection only
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


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

DEFAULT_PITCH_MIN_DEG = -85.0
DEFAULT_PITCH_MAX_DEG = -40.0
FLIGHT_TARGETS = {
    "downview_core": 5,
    "tilted_core": 5,
    "diverse_extra": 0,
}


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
    tags: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select representative raw UAV images per flight.")
    parser.add_argument("--input-root", required=True, help="Root directory containing per-flight raw JPG folders.")
    parser.add_argument("--output-root", required=True, help="Directory to store copied selections and manifests.")
    parser.add_argument("--pitch-min", type=float, default=DEFAULT_PITCH_MIN_DEG, help="Lower bound for eligible gimbal pitch.")
    parser.add_argument("--pitch-max", type=float, default=DEFAULT_PITCH_MAX_DEG, help="Upper bound for eligible gimbal pitch.")
    parser.add_argument(
        "--pitch-split",
        type=float,
        default=None,
        help="Optional manual split between downview and tilted pools; if omitted, the script uses the per-flight median pitch.",
    )
    parser.add_argument("--downview-target", type=int, default=FLIGHT_TARGETS["downview_core"], help="Target count from the downview pool per flight.")
    parser.add_argument("--tilted-target", type=int, default=FLIGHT_TARGETS["tilted_core"], help="Target count from the tilted pool per flight.")
    parser.add_argument("--diverse-target", type=int, default=FLIGHT_TARGETS["diverse_extra"], help="Target count for diversity supplement per flight.")
    return parser.parse_args()


def parse_image_record(
    flight_dir: Path,
    image_path: Path,
    pitch_min: float,
    pitch_max: float,
    pitch_split: float,
) -> ImageRecord | None:
    with image_path.open("rb") as f:
        data = f.read()

    values: dict[str, float] = {}
    for field, pattern in XMP_PATTERNS.items():
        match = pattern.search(data)
        if not match:
            return None
        values[field] = float(match.group(1).decode("utf-8"))

    frame_match = IMAGE_NAME_RE.search(image_path.name)
    if not frame_match:
        return None
    frame_index = int(frame_match.group(1))

    pitch = values["gimbal_pitch_degree"]
    if pitch < pitch_min or pitch > pitch_max:
        return None

    tags: list[str] = []
    return ImageRecord(
        flight_id=flight_dir.name,
        image_name=image_path.name,
        image_path=image_path,
        frame_index=frame_index,
        latitude=values["gps_latitude"],
        longitude=values["gps_longitude"],
        absolute_altitude=values["absolute_altitude"],
        relative_altitude=values["relative_altitude"],
        gimbal_pitch_degree=pitch,
        gimbal_yaw_degree=values["gimbal_yaw_degree"],
        flight_pitch_degree=values["flight_pitch_degree"],
        tags=tuple(tags),
    )


def load_flight_records(flight_dir: Path, pitch_min: float, pitch_max: float, pitch_split: float) -> list[ImageRecord]:
    records: list[ImageRecord] = []
    for image_path in sorted(flight_dir.glob("*.JPG")):
        record = parse_image_record(flight_dir, image_path, pitch_min, pitch_max, pitch_split)
        if record is not None:
            records.append(record)
    return records


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def is_valid_spacing(candidate: ImageRecord, selected: Iterable[ImageRecord], min_frame_gap: int, min_dist_m: float) -> bool:
    for item in selected:
        frame_gap = abs(candidate.frame_index - item.frame_index)
        dist_m = haversine_m(candidate.latitude, candidate.longitude, item.latitude, item.longitude)
        if frame_gap < min_frame_gap and dist_m < min_dist_m:
            return False
    return True


def pick_evenly_spaced(
    candidates: list[ImageRecord],
    already_selected: list[ImageRecord],
    count: int,
    min_frame_gap: int,
    min_dist_m: float,
) -> list[ImageRecord]:
    if not candidates or count <= 0:
        return []

    chosen: list[ImageRecord] = []
    used_names: set[str] = {item.image_name for item in already_selected}
    ordered = sorted(candidates, key=lambda x: x.frame_index)
    targets = [round(i * (len(ordered) - 1) / max(1, count - 1)) for i in range(count)]

    for target in targets:
        for idx in sorted(range(len(ordered)), key=lambda j: (abs(j - target), j)):
            candidate = ordered[idx]
            if candidate.image_name in used_names:
                continue
            if not is_valid_spacing(candidate, [*already_selected, *chosen], min_frame_gap, min_dist_m):
                continue
            chosen.append(candidate)
            used_names.add(candidate.image_name)
            break

    if len(chosen) >= count:
        return chosen[:count]

    for candidate in ordered:
        if candidate.image_name in used_names:
            continue
        if not is_valid_spacing(candidate, [*already_selected, *chosen], min_frame_gap, min_dist_m):
            continue
        chosen.append(candidate)
        used_names.add(candidate.image_name)
        if len(chosen) >= count:
            break

    return chosen[:count]


def diversity_score(candidate: ImageRecord, selected: list[ImageRecord]) -> float:
    if not selected:
        return 1e9
    min_frame_gap = min(abs(candidate.frame_index - item.frame_index) for item in selected)
    min_dist = min(haversine_m(candidate.latitude, candidate.longitude, item.latitude, item.longitude) for item in selected)
    min_yaw_gap = min(abs(candidate.gimbal_yaw_degree - item.gimbal_yaw_degree) for item in selected)
    return min_dist + min_frame_gap * 2.0 + min_yaw_gap * 0.5


def fill_diverse_extras(candidates: list[ImageRecord], selected: list[ImageRecord], count: int) -> list[ImageRecord]:
    chosen: list[ImageRecord] = []
    used_names = {item.image_name for item in selected}

    while len(chosen) < count:
        pool = [item for item in candidates if item.image_name not in used_names]
        if not pool:
            break
        pool.sort(key=lambda item: diversity_score(item, [*selected, *chosen]), reverse=True)
        candidate = pool[0]
        used_names.add(candidate.image_name)
        chosen.append(candidate)

    return chosen


def select_for_flight(
    records: list[ImageRecord],
    downview_target: int,
    tilted_target: int,
    diverse_target: int,
    pitch_min: float,
    pitch_max: float,
    pitch_split: float | None,
) -> tuple[list[tuple[ImageRecord, str, str]], dict[str, int]]:
    if not records:
        raise ValueError("No valid records found for flight.")

    strict_spacing = (15, 25.0)
    relaxed_spacing = (8, 12.0)

    ordered = sorted(records, key=lambda item: item.gimbal_pitch_degree)
    if pitch_split is None:
        split_index = len(ordered) // 2
        downview_candidates = ordered[:split_index]
        tilt_candidates = ordered[split_index:]
        split_value = (ordered[split_index - 1].gimbal_pitch_degree + ordered[split_index].gimbal_pitch_degree) / 2.0 if 0 < split_index < len(ordered) else ordered[0].gimbal_pitch_degree
    else:
        split_value = pitch_split
        downview_candidates = [item for item in ordered if item.gimbal_pitch_degree <= pitch_split]
        tilt_candidates = [item for item in ordered if item.gimbal_pitch_degree > pitch_split]

    selected: list[ImageRecord] = []
    for frame_gap, dist_m in (strict_spacing, relaxed_spacing):
        selected = []
        selected.extend(
            pick_evenly_spaced(
                downview_candidates,
                selected,
                downview_target,
                frame_gap,
                dist_m,
            )
        )
        selected.extend(
            pick_evenly_spaced(
                tilt_candidates,
                selected,
                tilted_target,
                frame_gap,
                dist_m,
            )
        )
        if diverse_target > 0:
            selected.extend(fill_diverse_extras(records, selected, diverse_target))
        if len(selected) == downview_target + tilted_target + diverse_target:
            break

    if len(selected) < downview_target + tilted_target + diverse_target:
        used = {item.image_name for item in selected}
        for item in sorted(records, key=lambda x: x.frame_index):
            if item.image_name in used:
                continue
            selected.append(item)
            used.add(item.image_name)
            if len(selected) >= downview_target + tilted_target + diverse_target:
                break

    required_total = downview_target + tilted_target + diverse_target
    if len(selected) < required_total:
        raise ValueError(
            f"Flight {records[0].flight_id} only yielded {len(selected)} eligible samples "
            f"within pitch window [{pitch_min:.1f}, {pitch_max:.1f}] but {required_total} are required."
        )

    selected = sorted(selected[:required_total], key=lambda x: x.frame_index)

    counts = {
        "available_downview": len(downview_candidates),
        "available_tilt": len(tilt_candidates),
        "selected_downview": 0,
        "selected_tilt": 0,
        "selected_extra": 0,
    }
    selected_rows: list[tuple[ImageRecord, str, str]] = []
    for item in selected:
        if item in downview_candidates:
            tags = "downview"
            reason = (
                f"Selected from downview pool using the lower half of pitches in [{pitch_min:.1f}, {pitch_max:.1f}] "
                "and temporal/spatial spacing."
            )
            counts["selected_downview"] += 1
        elif item in tilt_candidates:
            tags = "tilted"
            reason = (
                f"Selected from tilted pool using the upper half of pitches in [{pitch_min:.1f}, {pitch_max:.1f}] "
                "and temporal/spatial spacing."
            )
            counts["selected_tilt"] += 1
        else:
            tags = "diverse_extra"
            reason = "Selected as diversity supplement based on spatial, frame-index, and yaw separation."
            counts["selected_extra"] += 1
        selected_rows.append((item, tags, reason))

    return selected_rows, counts


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "flight_id",
                "image_name",
                "original_path",
                "copied_path",
                "latitude",
                "longitude",
                "absolute_altitude",
                "relative_altitude",
                "gimbal_pitch_degree",
                "gimbal_yaw_degree",
                "flight_pitch_degree",
                "tags",
                "pitch_group",
                "selection_reason",
                "review_status",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_notes(
    path: Path,
    rows: list[dict[str, str]],
    counts: dict[str, int],
    pitch_min: float,
    pitch_max: float,
    pitch_split: float | None,
) -> None:
    ensure_dir(path.parent)
    down_count = sum(row["tags"] == "downview" for row in rows)
    tilt_count = sum(row["tags"] == "tilted" for row in rows)
    with path.open("w", encoding="utf-8") as f:
        f.write(f"# {rows[0]['flight_id']} Selection Notes\n\n")
        f.write(f"- Selected images: {len(rows)}\n")
        f.write(f"- Pitch window: [{pitch_min:.1f}, {pitch_max:.1f}] deg\n")
        if pitch_split is None:
            f.write("- Pitch split: per-flight median pitch\n")
        else:
            f.write(f"- Pitch split: {pitch_split:.1f} deg\n")
        f.write(f"- Downview samples: {down_count}\n")
        f.write(f"- Tilted/wide-coverage samples: {tilt_count}\n")
        if counts["available_downview"] == 0:
            f.write("- Note: this flight has no downview candidates under the current pitch window.\n")
        if counts["available_tilt"] == 0:
            f.write("- Note: this flight has no tilted candidates under the current pitch window.\n")
        f.write("- Review status: auto-selected from embedded DJI metadata; no manual pixel-level review performed.\n")


def main() -> None:
    args = parse_args()
    if args.pitch_split is not None and not (args.pitch_min <= args.pitch_split <= args.pitch_max):
        raise SystemExit("Expected pitch_min <= pitch_split <= pitch_max.")
    if min(args.downview_target, args.tilted_target, args.diverse_target) < 0:
        raise SystemExit("Selection targets must be non-negative.")
    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    ensure_dir(output_root)

    aggregate_rows: list[dict[str, str]] = []

    for flight_dir in sorted(path for path in input_root.iterdir() if path.is_dir()):
        records = load_flight_records(flight_dir, args.pitch_min, args.pitch_max, args.pitch_split)
        if not records:
            continue

        selected, counts = select_for_flight(
            records,
            args.downview_target,
            args.tilted_target,
            args.diverse_target,
            args.pitch_min,
            args.pitch_max,
            args.pitch_split,
        )
        flight_out_dir = output_root / flight_dir.name
        ensure_dir(flight_out_dir)

        flight_rows: list[dict[str, str]] = []
        for item, tags, reason in selected:
            copied_path = flight_out_dir / item.image_name
            shutil.copy2(item.image_path, copied_path)
            row = {
                "flight_id": item.flight_id,
                "image_name": item.image_name,
                "original_path": str(item.image_path),
                "copied_path": str(copied_path),
                "latitude": f"{item.latitude:.9f}",
                "longitude": f"{item.longitude:.9f}",
                "absolute_altitude": f"{item.absolute_altitude:.3f}",
                "relative_altitude": f"{item.relative_altitude:.3f}",
                "gimbal_pitch_degree": f"{item.gimbal_pitch_degree:.2f}",
                "gimbal_yaw_degree": f"{item.gimbal_yaw_degree:.2f}",
                "flight_pitch_degree": f"{item.flight_pitch_degree:.2f}",
                "tags": tags,
                "pitch_group": tags,
                "selection_reason": reason,
                "review_status": "auto_selected",
            }
            flight_rows.append(row)
            aggregate_rows.append(row)

        write_csv(flight_out_dir / "selected_images.csv", flight_rows)
        write_notes(flight_out_dir / "selection_notes.md", flight_rows, counts, args.pitch_min, args.pitch_max, args.pitch_split)

    write_csv(output_root / "selected_images_summary.csv", aggregate_rows)

    print(f"Saved {len(aggregate_rows)} selected images across {len({row['flight_id'] for row in aggregate_rows})} flights.")


if __name__ == "__main__":
    main()

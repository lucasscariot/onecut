from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from fractions import Fraction
import json
import math
from pathlib import Path
import re

from onecut.errors import OneCutError
from onecut.process import run


LEGACY_OUTPUTS = {
    "captioned_vlog.mp4",
    "final_vlog.mp4",
    "final_onecut.mp4",
    "final_with_title.mp4",
    "title_card.mp4",
}
WORKFLOW_FILES = {"captions.txt", "comments.txt", "make_vlog.sh", "prepare_comments.sh"}
COMPACT_TIMESTAMP = re.compile(r"(?<!\d)((?:19|20)\d{6})[T _.-]?(\d{6})(?!\d)")
SEPARATED_TIMESTAMP = re.compile(
    r"(?<!\d)((?:19|20)\d{2})[-_.](\d{2})[-_.](\d{2})"
    r"[T _.-](\d{2})[-_.](\d{2})[-_.](\d{2})(?!\d)"
)


@dataclass(frozen=True)
class Source:
    path: Path
    sort_timestamp: float
    timestamp_label: str
    timestamp_source: str
    codec_name: str
    width: int
    height: int
    display_width: int
    display_height: int
    rotation: int
    fps: Fraction
    pixel_format: str
    bit_depth: int
    hdr: bool
    duration: float
    has_audio: bool


def _parse_fraction(value: str | None, fallback: Fraction) -> Fraction:
    try:
        parsed = Fraction(value)
        return parsed if parsed > 0 else fallback
    except (TypeError, ValueError, ZeroDivisionError):
        return fallback


def even_dimension(value: float) -> int:
    return max(2, int(round(value / 2)) * 2)


def _rotation_for(video: dict) -> int:
    rotation = video.get("tags", {}).get("rotate")
    for side_data in video.get("side_data_list", []):
        if side_data.get("rotation") is not None:
            rotation = side_data["rotation"]
            break
    try:
        return int(round(float(rotation) / 90) * 90) % 360
    except (TypeError, ValueError):
        return 0


def _filename_timestamp(name: str) -> dt.datetime | None:
    match = COMPACT_TIMESTAMP.search(name)
    if match:
        return dt.datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
    match = SEPARATED_TIMESTAMP.search(name)
    if match:
        return dt.datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
    return None


def probe(ffprobe: Path, path: Path) -> dict | None:
    result = run(
        [
            ffprobe,
            "-v", "error",
            "-show_streams",
            "-show_format",
            "-of", "json",
            path,
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None


def _timestamp(data: dict, path: Path) -> tuple[float, str, str]:
    values = [data.get("format", {}).get("tags", {}).get("creation_time")]
    values.extend(stream.get("tags", {}).get("creation_time") for stream in data.get("streams", []))
    for value in values:
        if not value:
            continue
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.timestamp(), value, "metadata"
        except ValueError:
            continue
    created = getattr(path.stat(), "st_birthtime", None)
    if created is not None and math.isfinite(created) and created > 0:
        label = dt.datetime.fromtimestamp(created).astimezone().isoformat(timespec="seconds")
        return created, label, "created time"
    parsed = _filename_timestamp(path.name)
    if parsed:
        return parsed.timestamp(), parsed.isoformat(), "filename"
    modified = path.stat().st_mtime
    label = dt.datetime.fromtimestamp(modified).isoformat(timespec="seconds")
    return modified, label, "modified time"


def _source_from_probe(path: Path, data: dict) -> Source | None:
    demuxers = set(data.get("format", {}).get("format_name", "").split(","))
    if demuxers & {"tty", "image2", "image2pipe"}:
        return None
    video = next(
        (
            stream
            for stream in data.get("streams", [])
            if stream.get("codec_type") == "video"
            and not stream.get("disposition", {}).get("attached_pic")
        ),
        None,
    )
    if video is None:
        return None
    duration_value = video.get("duration") or data.get("format", {}).get("duration")
    try:
        duration = float(duration_value)
    except (TypeError, ValueError):
        return None
    if duration <= 0:
        return None

    try:
        width, height = int(video["width"]), int(video["height"])
    except (KeyError, TypeError, ValueError):
        return None
    fps = _parse_fraction(video.get("avg_frame_rate"), Fraction(0, 1))
    if fps <= 0:
        fps = _parse_fraction(video.get("r_frame_rate"), Fraction(30, 1))
    pixel_format = video.get("pix_fmt") or "yuv420p"
    bit_depth_match = re.search(r"(\d+)(?:le|be)$", pixel_format)
    bit_depth = int(bit_depth_match.group(1)) if bit_depth_match else 8
    try:
        bit_depth = max(bit_depth, int(video.get("bits_per_raw_sample") or 0))
    except ValueError:
        pass
    sar = _parse_fraction(
        (video.get("sample_aspect_ratio") or "1:1").replace(":", "/"),
        Fraction(1, 1),
    )
    display_width = even_dimension(width * float(sar))
    display_height = even_dimension(height)
    rotation = _rotation_for(video)
    if rotation in (90, 270):
        display_width, display_height = display_height, display_width
    color_transfer = video.get("color_transfer") or "unknown"
    timestamp, label, source = _timestamp(data, path)
    return Source(
        path=path,
        sort_timestamp=timestamp,
        timestamp_label=label,
        timestamp_source=source,
        codec_name=video.get("codec_name") or "unknown",
        width=width,
        height=height,
        display_width=display_width,
        display_height=display_height,
        rotation=rotation,
        fps=fps,
        pixel_format=pixel_format,
        bit_depth=bit_depth,
        hdr=color_transfer in {"smpte2084", "arib-std-b67"},
        duration=duration,
        has_audio=any(stream.get("codec_type") == "audio" for stream in data.get("streams", [])),
    )


def discover_sources(
    input_dir: Path,
    output_file: Path,
    partial_file: Path,
    ffprobe: Path,
) -> tuple[Source, ...]:
    records: list[Source] = []
    for path in input_dir.iterdir():
        if not path.is_file():
            continue
        if (
            path.resolve() in {output_file.resolve(), partial_file.resolve()}
            or path.name.lower() in LEGACY_OUTPUTS
            or path.name.lower() in WORKFLOW_FILES
        ):
            continue
        data = probe(ffprobe, path)
        if data is None:
            continue
        source = _source_from_probe(path.resolve(), data)
        if source:
            records.append(source)
    records.sort(key=lambda item: (item.sort_timestamp, item.path.name.casefold()))
    if not records:
        raise OneCutError("no source videos were found in the selected folder.")
    return tuple(records)


def print_sources(sources: tuple[Source, ...]) -> None:
    print("== Finding and sorting source clips ==")
    for index, source in enumerate(sources, start=1):
        print(
            f"{index:6}\t{source.path.name}  "
            f"[{source.timestamp_label}; {source.timestamp_source}]"
        )

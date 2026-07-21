from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import datetime as dt
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import re
import tempfile

from onecut.config import Config, QUALITY_PRESETS
from onecut.errors import OneCutError
from onecut.process import has_ffmpeg_feature, run


LEGACY_OUTPUTS = {
    "captioned_vlog.mp4",
    "final_vlog.mp4",
    "final_onecut.mp4",
    "final_with_title.mp4",
    "title_card.mp4",
}
WORKFLOW_FILES = {"comments.txt", "make_vlog.sh", "prepare_comments.sh"}
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
    color_transfer: str
    color_primaries: str
    color_space: str
    hdr: bool
    duration: float
    has_audio: bool


@dataclass(frozen=True)
class RenderSettings:
    width: int
    height: int
    fps: Fraction
    ten_bit: bool
    has_hdr: bool
    has_zscale: bool
    video_bitrate: str
    quality: str
    dominant_orientation: str
    sources: tuple[Source, ...]


def _parse_fraction(value: str | None, fallback: Fraction) -> Fraction:
    try:
        parsed = Fraction(value)
        return parsed if parsed > 0 else fallback
    except (TypeError, ValueError, ZeroDivisionError):
        return fallback


def _make_even(value: float) -> int:
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
    display_width = _make_even(width * float(sar))
    display_height = _make_even(height)
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
        color_transfer=color_transfer,
        color_primaries=video.get("color_primaries") or "unknown",
        color_space=video.get("color_space") or "unknown",
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


def determine_settings(config: Config, sources: tuple[Source, ...], ffmpeg: Path) -> RenderSettings:
    print("== Inspecting source quality ==")
    try:
        max_fps = Fraction(config.max_fps)
    except (ValueError, ZeroDivisionError) as error:
        raise OneCutError("MAX_FPS must be a positive number.", 2) from error
    if max_fps <= 0:
        raise OneCutError("MAX_FPS must be a positive number.", 2)

    orientation_seconds: dict[str, float] = defaultdict(float)
    for source in sources:
        orientation = "landscape" if source.display_width >= source.display_height else "portrait"
        orientation_seconds[orientation] += source.duration
    dominant = max(orientation_seconds, key=orientation_seconds.get)

    if config.output_size == "auto":
        candidates = [
            source
            for source in sources
            if ("landscape" if source.display_width >= source.display_height else "portrait") == dominant
        ]
        canvas = max(candidates, key=lambda item: item.display_width * item.display_height)
        width, height = canvas.display_width, canvas.display_height
        scale = min(
            1.0,
            config.max_long_edge / max(width, height),
            config.max_short_edge / min(width, height),
        )
        width, height = _make_even(width * scale), _make_even(height * scale)
    else:
        width, height = map(int, re.split("[xX]", config.output_size))
        if width < 2 or height < 2:
            raise OneCutError("OUTPUT_SIZE dimensions must be at least 2 pixels.", 2)
        width, height = _make_even(width), _make_even(height)

    if config.output_fps == "auto":
        fps_seconds: dict[Fraction, float] = defaultdict(float)
        for source in sources:
            fps_seconds[source.fps] += source.duration
        fps = max(fps_seconds, key=lambda value: (fps_seconds[value], float(value)))
    else:
        fps = _parse_fraction(config.output_fps, Fraction(0, 1))
        if fps <= 0:
            raise OneCutError(
                "OUTPUT_FPS must be 'auto' or a positive number/rational such as 30 or 30000/1001.", 2
            )
    fps = min(fps, max_fps)

    bitrate = config.video_bitrate
    if bitrate == "auto":
        _, _, _, reference_rate = QUALITY_PRESETS[config.quality]
        reference_pixels = QUALITY_PRESETS[config.quality][1] * QUALITY_PRESETS[config.quality][2]
        fps_multiplier = 1.0 if float(fps) <= 30 else 1.5
        rate = reference_rate * (width * height / reference_pixels) * fps_multiplier
        bitrate = f"{max(6, min(200, round(rate)))}M"
    elif not re.fullmatch(r"\d+(?:\.\d+)?[kKmM]", bitrate):
        raise OneCutError("VIDEO_BITRATE must be 'auto' or a value such as 20M or 8000k.", 2)

    settings = RenderSettings(
        width=width,
        height=height,
        fps=fps,
        ten_bit=any(source.bit_depth > 8 or source.hdr for source in sources),
        has_hdr=any(source.hdr for source in sources),
        has_zscale=has_ffmpeg_feature(ffmpeg, ("-filters",), " zscale "),
        video_bitrate=bitrate,
        quality=config.quality,
        dominant_orientation=dominant,
        sources=sources,
    )
    label = QUALITY_PRESETS[config.quality][0]
    depth = "10-bit" if settings.ten_bit else "8-bit"
    print(
        f"Output ({label}): {width}x{height} at {float(fps):.3f} fps, "
        f"{depth} HEVC at {bitrate}"
    )
    if len(orientation_seconds) > 1:
        print(f"Mixed orientations: using a {dominant} canvas and padding the others")
    return settings


def trim_clip(mode: str, seconds_text: str, clip_text: str, ffmpeg: Path, ffprobe: Path) -> None:
    if not re.fullmatch(r"\d+(?:\.\d+)?", seconds_text):
        raise OneCutError("seconds must be a positive number.", 2)
    try:
        seconds = float(seconds_text)
    except ValueError as error:
        raise OneCutError("seconds must be a positive number.", 2) from error
    if seconds <= 0 or not math.isfinite(seconds):
        raise OneCutError("seconds must be a positive number.", 2)
    clip = Path(clip_text).expanduser()
    if not clip.is_file():
        raise OneCutError(f"clip was not found: {clip}", 2)

    keep_duration = seconds
    if mode == "trim-end":
        data = probe(ffprobe, clip)
        if not data:
            raise OneCutError(f"FFprobe could not inspect {clip.name}.")
        try:
            duration = float(data.get("format", {}).get("duration"))
        except (TypeError, ValueError) as error:
            raise OneCutError(f"could not determine the duration of {clip.name}.") from error
        keep_duration = duration - seconds
        if keep_duration <= 0:
            raise OneCutError("trim duration must be shorter than the clip.", 2)

    original_stat = clip.stat()
    temporary_handle = tempfile.NamedTemporaryFile(
        prefix=f".{clip.name}.onecut-trim.", suffix=".mp4", dir=clip.parent, delete=False
    )
    temporary = Path(temporary_handle.name)
    temporary_handle.close()
    temporary.unlink(missing_ok=True)
    try:
        command: list[str | Path] = [ffmpeg, "-y"]
        if mode == "trim-start":
            command.extend(["-ss", seconds_text, "-i", clip])
        else:
            command.extend(["-i", clip, "-t", f"{keep_duration:.6f}"])
        command.extend(
            [
                "-map", "0:v?", "-map", "0:a?", "-map_metadata", "0",
                "-movflags", "use_metadata_tags", "-c", "copy", "-f", "mp4", temporary,
            ]
        )
        result = run(command)
        if result.returncode != 0:
            raise OneCutError(f"FFmpeg could not trim {clip.name}.")
        os.utime(temporary, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        os.replace(temporary, clip)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Trimmed: {clip.name}")

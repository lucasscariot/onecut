from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys

from onecut.errors import OneCutError


QUALITY_PRESETS = {
    "youtube-1080": ("1080p Compact", 1920, 1080, 12),
    "youtube-1440": ("1440p Balanced", 2560, 1440, 24),
    "youtube-4k": ("4K Maximum", 3840, 2160, 65),
}


def resolve_input_dir() -> Path:
    raw_input = os.environ.get("ONECUT_DIR", os.environ.get("VLOG_DIR", os.getcwd()))
    input_dir = Path(raw_input).expanduser().resolve()
    if not input_dir.is_dir():
        raise OneCutError(f"the selected folder does not exist: {input_dir}", 2)
    return input_dir


def resolve_output_paths(input_dir: Path, argument: str | None) -> tuple[Path, Path]:
    output = Path(argument or "final_onecut.mp4").expanduser()
    if not output.is_absolute():
        output = input_dir / output
    if output.suffix.lower() != ".mp4":
        raise OneCutError("the output filename must end in .mp4", 2)
    output = output.resolve()
    partial = output.with_name(f".{output.name}.partial.mp4")
    return output, partial


def _positive_float(name: str, default: str) -> float:
    raw = os.environ.get(name, default)
    try:
        value = float(raw)
    except ValueError as error:
        raise OneCutError(f"{name} must be a positive number.", 2) from error
    if value <= 0:
        raise OneCutError(f"{name} must be a positive number.", 2)
    return value


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as error:
        raise OneCutError(f"{name} must be a positive integer.", 2) from error
    if value <= 0:
        raise OneCutError(f"{name} must be a positive integer.", 2)
    return value


def choose_quality(current: str) -> str:
    if not sys.stdin.isatty():
        return current
    indexes = {
        "youtube-1080": "1",
        "youtube-1440": "2",
        "youtube-4k": "3",
    }
    print("\nChoose the YouTube export quality:")
    print("  1) 1080p Compact  - smaller file, about 12 Mbps (18 Mbps at 48-60 fps)")
    print("  2) 1440p Balanced - sharper upload, about 24 Mbps (36 Mbps at 48-60 fps)")
    print("  3) 4K Maximum     - best quality, about 65 Mbps (98 Mbps at 48-60 fps)")
    choices = {"1": "youtube-1080", "2": "youtube-1440", "3": "youtube-4k"}
    while True:
        try:
            selected = input(f"Selection [{indexes[current]}]: ").strip()
        except EOFError:
            return current
        if not selected:
            return current
        if selected in choices:
            return choices[selected]
        print("Please choose 1, 2, or 3.", file=sys.stderr)


@dataclass(frozen=True)
class Config:
    display_seconds: float
    title_seconds: float
    output_size: str
    output_fps: str
    max_long_edge: int
    max_short_edge: int
    max_fps: str
    video_bitrate: str
    quality: str
    video_encoder: str
    font_regular: str | None
    font_bold: str | None

    @classmethod
    def load(cls, *, prompt_for_quality: bool = False) -> "Config":
        quality_override = os.environ.get("EXPORT_QUALITY")
        quality = quality_override or "youtube-4k"
        if quality not in QUALITY_PRESETS:
            raise OneCutError(
                f"unknown export quality {quality!r}. Use youtube-1080, "
                "youtube-1440, or youtube-4k.",
                2,
            )
        if prompt_for_quality and not quality_override:
            quality = choose_quality(quality)
        _, long_edge, short_edge, _ = QUALITY_PRESETS[quality]
        output_size = os.environ.get("OUTPUT_SIZE", "auto")
        if output_size != "auto" and not re.fullmatch(r"\d+[xX]\d+", output_size):
            raise OneCutError(
                "OUTPUT_SIZE must be 'auto' or WIDTHxHEIGHT, for example 1920x1080.", 2
            )
        video_encoder = os.environ.get("VIDEO_ENCODER", "auto")
        if video_encoder not in {"auto", "videotoolbox", "libx265"}:
            raise OneCutError("VIDEO_ENCODER must be auto, videotoolbox, or libx265.", 2)
        return cls(
            display_seconds=_positive_float("DISPLAY_SECONDS", "4"),
            title_seconds=_positive_float("TITLE_SECONDS", "5"),
            output_size=output_size,
            output_fps=os.environ.get("OUTPUT_FPS", "auto"),
            max_long_edge=_positive_int("MAX_LONG_EDGE", long_edge),
            max_short_edge=_positive_int("MAX_SHORT_EDGE", short_edge),
            max_fps=os.environ.get("MAX_FPS", "60"),
            video_bitrate=os.environ.get("VIDEO_BITRATE", "auto"),
            quality=quality,
            video_encoder=video_encoder,
            font_regular=os.environ.get("FONT_REGULAR"),
            font_bold=os.environ.get("FONT_BOLD"),
        )

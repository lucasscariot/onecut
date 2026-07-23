from __future__ import annotations

import math
import os
from pathlib import Path
import re
import sys
import tempfile

from onecut.errors import OneCutError
from onecut.process import resolve_media_tools, run as run_process
from onecut.sources import probe


NAMES = frozenset({"trim-start", "trim-end", "keep-first"})


def run(mode: str, arguments: list[str]) -> int:
    if len(arguments) != 2:
        print(f"Usage: onecut {mode} <seconds> <clip.mp4>", file=sys.stderr)
        return 2
    ffmpeg, ffprobe = resolve_media_tools()
    trim_clip(mode, arguments[0], arguments[1], ffmpeg, ffprobe)
    return 0


def trim_clip(
    mode: str,
    seconds_text: str,
    clip_text: str,
    ffmpeg: Path,
    ffprobe: Path,
) -> None:
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
        prefix=f".{clip.name}.onecut-trim.",
        suffix=".mp4",
        dir=clip.parent,
        delete=False,
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
                "-map", "0:v:0?", "-map", "0:a:0?", "-map_metadata", "0",
                "-movflags", "use_metadata_tags", "-c", "copy", "-f", "mp4", temporary,
            ]
        )
        result = run_process(command)
        if result.returncode != 0:
            raise OneCutError(f"FFmpeg could not trim {clip.name}.")
        os.utime(temporary, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        os.replace(temporary, clip)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Trimmed: {clip.name}")

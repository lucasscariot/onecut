from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from typing import Sequence

from onecut.errors import OneCutError


def _subprocess_environment() -> dict[str, str]:
    env = dict(os.environ)
    for key in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        original = env.get(f"{key}_ORIG")
        if original is not None:
            env[key] = original
    return env


def run(
    command: Sequence[str | Path],
    *,
    capture_output: bool = False,
    check: bool = False,
    text: bool = True,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(value) for value in command],
        capture_output=capture_output,
        check=check,
        text=text,
        env=_subprocess_environment(),
    )


def bundled_resource(*parts: str) -> Path:
    return Path(__file__).resolve().parent.joinpath(*parts)


def resolve_media_tools() -> tuple[Path, Path]:
    override = os.environ.get("ONECUT_FFMPEG_DIR")
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(bundled_resource("vendor"))

    suffix = ".exe" if os.name == "nt" else ""
    for directory in candidates:
        ffmpeg = directory / f"ffmpeg{suffix}"
        ffprobe = directory / f"ffprobe{suffix}"
        if ffmpeg.is_file() and ffprobe.is_file():
            return ffmpeg, ffprobe

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if ffmpeg_path and ffprobe_path:
        return Path(ffmpeg_path), Path(ffprobe_path)

    raise OneCutError(
        "FFmpeg and FFprobe were not found. Use the packaged OneCut binary, "
        "install FFmpeg, or set ONECUT_FFMPEG_DIR."
    )


def tool_output(executable: Path, *arguments: str) -> str:
    result = run(
        [executable, "-hide_banner", *arguments],
        capture_output=True,
    )
    return (result.stdout or "") + (result.stderr or "")


def has_ffmpeg_feature(ffmpeg: Path, arguments: tuple[str, ...], token: str) -> bool:
    return token in tool_output(ffmpeg, *arguments)

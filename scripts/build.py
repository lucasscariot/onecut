#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


def main() -> int:
    try:
        import PyInstaller.__main__
    except ImportError:
        print(
            "ERROR: install build dependencies with: python -m pip install '.[build]'",
            file=sys.stderr,
        )
        return 1

    project_root = Path(__file__).resolve().parents[1]
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        print("ERROR: FFmpeg and FFprobe are required to build OneCut.", file=sys.stderr)
        return 1
    if Path(ffmpeg).resolve().parent == Path(ffprobe).resolve().parent:
        os.environ.setdefault("ONECUT_FFMPEG_DIR", str(Path(ffmpeg).resolve().parent))

    PyInstaller.__main__.run(
        [
            "--clean",
            "--noconfirm",
            "--distpath", str(project_root / "dist"),
            "--workpath", str(project_root / "build"),
            str(project_root / "onecut.spec"),
        ]
    )
    executable = project_root / "dist" / "onecut" / "onecut"
    result = subprocess.run([executable, "--version"], check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

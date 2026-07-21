# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
import shutil


project_root = Path(SPECPATH)
tool_directory = os.environ.get("ONECUT_FFMPEG_DIR")
ffmpeg = Path(tool_directory, "ffmpeg") if tool_directory else Path(shutil.which("ffmpeg") or "")
ffprobe = Path(tool_directory, "ffprobe") if tool_directory else Path(shutil.which("ffprobe") or "")
if not ffmpeg.is_file() or not ffprobe.is_file():
    raise SystemExit(
        "FFmpeg and FFprobe are required to build OneCut. "
        "Install them or set ONECUT_FFMPEG_DIR."
    )

a = Analysis(
    [str(project_root / "src" / "onecut" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[
        (str(ffmpeg.resolve()), "onecut/vendor"),
        (str(ffprobe.resolve()), "onecut/vendor"),
    ],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="onecut",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="onecut",
)

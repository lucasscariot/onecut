from __future__ import annotations

from pathlib import Path
import sys
import tempfile

from onecut.caption_file import parse_captions
from onecut.config import Config, resolve_input_dir, resolve_output_paths
from onecut.errors import OneCutError
from onecut.overlays import create_overlays
from onecut.process import resolve_media_tools
from onecut.rendering import determine_settings, render_video
from onecut.sources import discover_sources, print_sources


USAGE = "Usage: onecut render [output.mp4]"


def run(arguments: list[str]) -> int:
    if len(arguments) > 1:
        print(USAGE, file=sys.stderr)
        return 2

    input_dir = resolve_input_dir()
    output_file, partial_file = resolve_output_paths(
        input_dir,
        arguments[0] if arguments else None,
    )
    captions_file = input_dir / "captions.txt"
    legacy_captions_file = input_dir / "comments.txt"
    if not captions_file.is_file() and legacy_captions_file.is_file():
        captions_file = legacy_captions_file
    if not captions_file.is_file():
        raise OneCutError(
            f"captions.txt was not found in {input_dir}.\n"
            "Run 'onecut captions' to create it."
        )

    ffmpeg, ffprobe = resolve_media_tools()
    sources = discover_sources(input_dir, output_file, partial_file, ffprobe)
    print_sources(sources)
    config = Config.load(prompt_for_quality=True)
    settings = determine_settings(config, sources, ffmpeg)
    print(f"== Reading {captions_file.name} ==")
    copy = parse_captions(captions_file, sources, config.display_seconds)

    with tempfile.TemporaryDirectory(prefix="onecut-") as temporary:
        work_dir = Path(temporary)
        title_path, caption_paths = create_overlays(work_dir, config, settings, copy)
        render_video(
            ffmpeg,
            ffprobe,
            config,
            settings,
            copy,
            title_path,
            caption_paths,
            work_dir / "filter-complex.txt",
            output_file,
            partial_file,
        )
    return 0

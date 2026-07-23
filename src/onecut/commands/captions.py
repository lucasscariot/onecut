from __future__ import annotations

import sys

from onecut.caption_file import prepare_captions
from onecut.config import resolve_input_dir, resolve_output_paths
from onecut.process import resolve_media_tools
from onecut.sources import discover_sources, print_sources


USAGE = "Usage: onecut captions"


def run(arguments: list[str]) -> int:
    if arguments:
        print(USAGE, file=sys.stderr)
        return 2

    input_dir = resolve_input_dir()
    output_file, partial_file = resolve_output_paths(input_dir, None)
    captions_file = input_dir / "captions.txt"
    legacy_captions_file = input_dir / "comments.txt"
    previous_captions_file = captions_file
    if not captions_file.is_file() and legacy_captions_file.is_file():
        previous_captions_file = legacy_captions_file

    _, ffprobe = resolve_media_tools()
    sources = discover_sources(input_dir, output_file, partial_file, ffprobe)
    print_sources(sources)
    prepare_captions(captions_file, sources, preserve_from=previous_captions_file)
    return 0

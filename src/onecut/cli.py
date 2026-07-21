from __future__ import annotations

from pathlib import Path
import sys
import tempfile

from onecut import __version__
from onecut.comments import parse_comments, prepare_comments
from onecut.config import Config
from onecut.errors import OneCutError
from onecut.images import create_overlays
from onecut.media import (
    determine_settings,
    discover_sources,
    print_sources,
    trim_clip,
)
from onecut.process import resolve_media_tools
from onecut.render import render_video


USAGE = """Usage: onecut [output.mp4]
       onecut comments
       onecut trim-start <seconds> <clip.mp4>
       onecut trim-end <seconds> <clip.mp4>
       onecut keep-first <seconds> <clip.mp4>

trim-start removes seconds from the beginning of a clip.
trim-end removes seconds from the end of a clip.
keep-first keeps only the first seconds of a clip."""


def _output_paths(config: Config, argument: str | None) -> tuple[Path, Path]:
    output = Path(argument or "final_onecut.mp4").expanduser()
    if not output.is_absolute():
        output = config.input_dir / output
    if output.suffix.lower() != ".mp4":
        raise OneCutError("the output filename must end in .mp4", 2)
    output = output.resolve()
    partial = output.with_name(f".{output.name}.partial.mp4")
    return output, partial


def main(arguments: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if arguments is None else arguments)
    invoked_as_comments = Path(sys.argv[0]).name == "onecut-comments"
    if invoked_as_comments and not argv:
        argv = ["comments"]

    if argv and argv[0] in {"-h", "--help"}:
        print(USAGE)
        return 0
    if argv and argv[0] == "--version":
        print(f"onecut {__version__}")
        return 0

    try:
        if argv and argv[0] in {"trim-start", "trim-end", "keep-first"}:
            if len(argv) != 3:
                print(USAGE, file=sys.stderr)
                return 2
            ffmpeg, ffprobe = resolve_media_tools()
            trim_clip(argv[0], argv[1], argv[2], ffmpeg, ffprobe)
            return 0

        prepare_mode = bool(argv and argv[0] in {"comments", "--prepare-comments"})
        if prepare_mode:
            argv.pop(0)
        if len(argv) > 1 or (prepare_mode and argv):
            print(USAGE, file=sys.stderr)
            return 2

        config = Config.load(prepare_comments=prepare_mode)
        output_file, partial_file = _output_paths(config, argv[0] if argv else None)
        if not prepare_mode and not config.comments_file.is_file():
            raise OneCutError(
                f"comments.txt was not found in {config.input_dir}.\n"
                "Run 'onecut comments' to create it."
            )
        ffmpeg, ffprobe = resolve_media_tools()
        sources = discover_sources(
            config.input_dir,
            output_file,
            partial_file,
            ffprobe,
        )
        print_sources(sources)
        settings = determine_settings(config, sources, ffmpeg)
        if prepare_mode:
            prepare_comments(config.comments_file, sources, config.quality)
            return 0

        print("== Reading comments.txt ==")
        copy = parse_comments(config.comments_file, sources, config.display_seconds)
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
    except OneCutError as error:
        message = str(error)
        prefix = "" if message.startswith("ERROR:") else "ERROR: "
        print(f"{prefix}{message}", file=sys.stderr)
        return error.exit_code
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130


def entrypoint() -> None:
    raise SystemExit(main())


def comments_entrypoint() -> None:
    raise SystemExit(main(["comments", *sys.argv[1:]]))

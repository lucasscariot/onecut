from __future__ import annotations

import sys

from onecut import __version__
from onecut.commands import captions, render, trim
from onecut.errors import OneCutError


USAGE = """Usage: onecut <command> [arguments]

Commands:
  render [output.mp4]              Render the clips into a finished video
  captions                         Create or refresh captions.txt
  trim-start <seconds> <clip.mp4>  Remove time from the beginning of a clip
  trim-end <seconds> <clip.mp4>    Remove time from the end of a clip
  keep-first <seconds> <clip.mp4>  Keep only the beginning of a clip

Options:
  -h, --help                       Show this command list
  --version                        Show the installed version"""


def main(arguments: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if arguments is None else arguments)

    if not argv or argv[0] in {"-h", "--help"}:
        print(USAGE)
        return 0
    if argv[0] == "--version":
        print(f"onecut {__version__}")
        return 0

    try:
        command, command_arguments = argv[0], argv[1:]
        if command == "render":
            return render.run(command_arguments)
        if command == "captions":
            return captions.run(command_arguments)
        if command in trim.NAMES:
            return trim.run(command, command_arguments)
        print(f"Unknown command: {command}\n\n{USAGE}", file=sys.stderr)
        return 2
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

# OneCut

Turn a folder of video clips into one finished video with a self-contained CLI.

```sh
onecut captions       # generate or refresh captions.txt
onecut                # create final_onecut.mp4
onecut holiday.mp4    # choose an output filename
onecut trim-start 22 CAM_20260720192120_0023_D.MP4  # remove the first 22 seconds
onecut keep-first 10 CAM_20260720134126_0039_D.MP4 # keep only the first 10 seconds
onecut trim-end 5 CAM_20260720134126_0039_D.MP4    # remove the final 5 seconds
```

OneCut sorts clips chronologically, keeps their audio, adds an optional title
card, and overlays timed captions.

## Install

Install the latest macOS Apple Silicon binary with:

```sh
curl -fsSL https://raw.githubusercontent.com/lucasscariot/onecut/main/install.sh | bash
```

It downloads a checksum-verified application directory to
`~/.local/share/onecut`, links its executable into `~/.local/bin`, and makes
`onecut` available on your `PATH`. The application directory contains Python,
Pillow, FFmpeg, and FFprobe.

To install a specific release, set `ONECUT_VERSION`, for example:

```sh
curl -fsSL https://raw.githubusercontent.com/lucasscariot/onecut/main/install.sh \
  | ONECUT_VERSION=v0.2.0 bash
```

## Requirements

The packaged CLI has no runtime dependencies. Running from source requires
Python 3.11+, Pillow, FFmpeg, and FFprobe.

## Use

Run OneCut from the folder containing your clips, or point it at a folder:

```sh
ONECUT_DIR=/path/to/clips onecut
```

`onecut captions` creates `captions.txt`. Add `TITLE:` and `DESC:` for an
optional opening card, then add bullets under each `CLIP:` section. Timestamps
are relative to the source clip, for example `- 00:12 A quiet morning`.

## Trim a clip

These commands update the supplied clip only after FFmpeg finishes successfully:

```sh
onecut trim-start 22 clip.mp4  # remove the first 22 seconds
onecut trim-end 5 clip.mp4     # remove the last 5 seconds
onecut keep-first 10 clip.mp4  # keep only the first 10 seconds
```

They preserve the clip's embedded metadata and modification time, and copy the
video/audio streams without re-encoding. Because a lossless cut must use a
video keyframe, the actual video boundary can be slightly before or after the
requested timestamp.

When rendering in a terminal, choose an upload preset from the prompt. For
non-interactive use, set `EXPORT_QUALITY=youtube-1080`, `youtube-1440`, or
`youtube-4k`; otherwise OneCut defaults to 4K.

## Development

Create a virtual environment and install the package:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test,build]'
```

Run the unit and end-to-end tests with:

```sh
pytest
./tests/smoke-test.sh
```

Build a self-contained application directory containing Python, Pillow,
FFmpeg, and FFprobe:

```sh
python scripts/build.py
./dist/onecut/onecut --version
```

The build uses `ffmpeg` and `ffprobe` from `PATH`. Set `ONECUT_FFMPEG_DIR` to
bundle a specific matching pair. PyInstaller includes their linked libraries
in the application directory, so normal commands do not unpack dependencies
into a temporary directory at startup.

The code is split by responsibility under `src/onecut`: CLI orchestration,
media discovery and probing, comment parsing, Pillow overlay creation, and
FFmpeg rendering. The tiny test clip is intentionally versioned; other source
footage and rendered videos remain ignored.

Tagged releases are built and smoke-tested on a GitHub-hosted macOS arm64
runner before publication. Release assets also record the exact FFmpeg build
configuration; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

OneCut is licensed under the [GNU General Public License v3.0](LICENSE).

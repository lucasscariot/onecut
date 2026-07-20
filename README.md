# OneCut

Turn a folder of video clips into one finished video.

```sh
onecut comments       # generate or refresh comments.txt
onecut                # create final_onecut.mp4
onecut holiday.mp4    # choose an output filename
onecut trim-start 22 CAM_20260720192120_0023_D.MP4  # remove the first 22 seconds
onecut keep-first 10 CAM_20260720134126_0039_D.MP4 # keep only the first 10 seconds
onecut trim-end 5 CAM_20260720134126_0039_D.MP4    # remove the final 5 seconds
```

OneCut sorts clips chronologically, keeps their audio, adds an optional title
card, and overlays timed captions. `onecut-comments` is shorthand for
`onecut comments`.

## Install

For now, clone the repository and run it from the checkout:

```sh
git clone https://github.com/lucasscariot/onecut.git
cd onecut
./bin/onecut comments
```

Install directly with:

```sh
curl -fsSL https://raw.githubusercontent.com/lucasscariot/onecut/main/install.sh | bash
```

It installs `onecut` and `onecut-comments` in `~/.local/bin`. Make sure that
directory is on your `PATH`.

## Requirements

- FFmpeg, including `ffprobe`
- Python 3
- Pillow: `python3 -m pip install Pillow`

On macOS with Homebrew: `brew install ffmpeg python pillow`.

## Use

Run OneCut from the folder containing your clips, or point it at a folder:

```sh
ONECUT_DIR=/path/to/clips onecut
```

`onecut comments` creates `comments.txt`. Add `TITLE:` and `DESC:` for an
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

Choose an upload preset when generating comments, or set
`EXPORT_QUALITY=youtube-1080`, `youtube-1440`, or `youtube-4k`.

## Development

Run the end-to-end smoke test with:

```sh
./tests/smoke-test.sh
```

The tiny test clip is intentionally versioned. Source footage and rendered
videos are ignored so this repository stays code-only.

## License

OneCut is licensed under the [GNU General Public License v3.0](LICENSE).

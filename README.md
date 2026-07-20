# OneCut

Turn a folder of video clips into one finished video.

```sh
onecut comments       # generate or refresh comments.txt
onecut                # create final_vlog.mp4
onecut holiday.mp4    # choose an output filename
```

OneCut sorts clips chronologically, keeps their audio, adds an optional title
card, and overlays timed captions. `onecut-comments` is shorthand for
`onecut comments`.

## Install

For now, clone the repository and run it from the checkout:

```sh
git clone https://github.com/YOUR_GITHUB_USERNAME/onecut.git
cd onecut
./bin/onecut comments
```

After the GitHub repository exists, the installer will support:

```sh
curl -fsSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/onecut/main/install.sh | bash
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
VLOG_DIR=/path/to/clips onecut
```

`onecut comments` creates `comments.txt`. Add `TITLE:` and `DESC:` for an
optional opening card, then add bullets under each `CLIP:` section. Timestamps
are relative to the source clip, for example `- 00:12 A quiet morning`.

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

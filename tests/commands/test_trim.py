from pathlib import Path
from types import SimpleNamespace

from onecut.commands import trim


def test_trim_maps_only_primary_video_and_audio(monkeypatch, tmp_path: Path) -> None:
    clip = tmp_path / "clip.mov"
    clip.write_bytes(b"original")
    commands: list[list[str | Path]] = []

    def fake_run(command: list[str | Path]):
        commands.append(command)
        Path(command[-1]).write_bytes(b"trimmed")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(trim, "run_process", fake_run)

    trim.trim_clip("keep-first", "1", str(clip), Path("ffmpeg"), Path("ffprobe"))

    assert commands == [
        [
            Path("ffmpeg"),
            "-y",
            "-i",
            clip,
            "-t",
            "1.000000",
            "-map",
            "0:v:0?",
            "-map",
            "0:a:0?",
            "-map_metadata",
            "0",
            "-movflags",
            "use_metadata_tags",
            "-c",
            "copy",
            "-f",
            "mp4",
            commands[0][-1],
        ]
    ]
    assert clip.read_bytes() == b"trimmed"

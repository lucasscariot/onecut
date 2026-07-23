from pathlib import Path

from onecut.caption_file import (
    format_time,
    parse_captions,
    parse_local_bullet,
    prepare_captions,
)
from onecut.sources import Source


def source(name: str = "clip.mp4", duration: float = 10.0) -> Source:
    from fractions import Fraction

    return Source(
        path=Path(name),
        sort_timestamp=0,
        timestamp_label="2026-01-01T00:00:00",
        timestamp_source="filename",
        codec_name="h264",
        width=1920,
        height=1080,
        display_width=1920,
        display_height=1080,
        rotation=0,
        fps=Fraction(30),
        pixel_format="yuv420p",
        bit_depth=8,
        hdr=False,
        duration=duration,
        has_audio=True,
    )


def test_parse_local_bullet_formats() -> None:
    assert parse_local_bullet("- 01:02 hello") == (62.0, "hello")
    assert parse_local_bullet("- 1:02:03.5 hello") == (3723.5, "hello")
    assert parse_local_bullet("- placeholder") == (0.0, "placeholder")


def test_format_time_handles_rounding() -> None:
    assert format_time(59.9999) == "01:00"
    assert format_time(3661.25, include_fraction=True) == "1:01:01.25"


def test_parse_structured_captions(tmp_path: Path) -> None:
    captions = tmp_path / "captions.txt"
    captions.write_text(
        "TITLE: A day out\nDESC: In the hills\n\nCLIP: clip.mp4\n- 00:02 Hello\n",
        encoding="utf-8",
    )
    parsed = parse_captions(captions, (source(),), 4.0)
    assert parsed.title == "A day out"
    assert parsed.description == "In the hills"
    assert [(item.start, item.end, item.text) for item in parsed.captions] == [
        (2.0, 6.0, "Hello")
    ]


def test_parse_legacy_quality_line_is_ignored(tmp_path: Path) -> None:
    captions = tmp_path / "comments.txt"
    captions.write_text(
        "QUALITY: youtube-1080\nTITLE: A day out\nDESC: In the hills\n\n"
        "CLIP: clip.mp4\n- 00:02 Hello\n",
        encoding="utf-8",
    )
    parsed = parse_captions(captions, (source(),), 4.0)
    assert parsed.title == "A day out"
    assert [(item.start, item.end, item.text) for item in parsed.captions] == [
        (2.0, 6.0, "Hello")
    ]


def test_prepare_migrates_legacy_file_without_quality(tmp_path: Path) -> None:
    legacy = tmp_path / "comments.txt"
    legacy.write_text(
        "QUALITY: youtube-1080\nTITLE: A day out\nDESC: In the hills\n\n"
        "CLIP: clip.mp4\n- 00:02 Hello\n",
        encoding="utf-8",
    )
    captions = tmp_path / "captions.txt"

    prepare_captions(captions, (source(),), preserve_from=legacy)

    content = captions.read_text(encoding="utf-8")
    assert "QUALITY:" not in content
    assert "TITLE: A day out" in content
    assert "- 00:02 Hello" in content
    assert legacy.is_file()

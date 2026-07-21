from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from onecut.captions import RenderCopy
from onecut.config import Config
from onecut.errors import OneCutError
from onecut.media import RenderSettings


def _font(path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if path:
        font_path = Path(path).expanduser()
        if not font_path.is_file():
            raise OneCutError(f"font was not found: {font_path}", 2)
        try:
            return ImageFont.truetype(str(font_path), size)
        except OSError as error:
            raise OneCutError(f"font could not be loaded: {font_path}", 2) from error
    # Pillow embeds the open-licensed Aileron font, keeping packaged builds
    # independent from fonts installed on the host operating system.
    return ImageFont.load_default(size=size)


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str | None,
    initial_size: int,
    minimum_size: int,
    max_width: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(initial_size, minimum_size - 1, -max(2, initial_size // 36)):
        font = _font(font_path, size)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
    return _font(font_path, minimum_size)


def _wrap_pixels(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> str:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words.pop(0)
        for word in words:
            candidate = f"{current} {word}"
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return "\n".join(lines)


def create_overlays(
    work_dir: Path,
    config: Config,
    settings: RenderSettings,
    copy: RenderCopy,
) -> tuple[Path | None, tuple[Path, ...]]:
    width, height = settings.width, settings.height
    scale = min(width / 1920, height / 1080)

    def px(value: int) -> int:
        return max(1, round(value * scale))

    title_path: Path | None = None
    if copy.title or copy.description:
        image = Image.new("RGB", (width, height), "black")
        draw = ImageDraw.Draw(image)
        if copy.title:
            title_font = _fit_font(
                draw,
                copy.title,
                config.font_bold,
                px(72),
                px(42),
                width - px(240),
            )
            wrapped_title = _wrap_pixels(draw, copy.title, title_font, width - px(240))
        else:
            title_font = _font(config.font_bold, px(72))
            wrapped_title = ""
        description_font = _font(config.font_regular, px(38))
        wrapped_description = _wrap_pixels(
            draw, copy.description, description_font, width - px(320)
        )
        title_box = (
            draw.multiline_textbbox(
                (0, 0), wrapped_title, font=title_font, spacing=px(14), align="center"
            )
            if wrapped_title
            else (0, 0, 0, 0)
        )
        description_box = (
            draw.multiline_textbbox(
                (0, 0),
                wrapped_description,
                font=description_font,
                spacing=px(10),
                align="center",
            )
            if wrapped_description
            else (0, 0, 0, 0)
        )
        gap = px(38) if wrapped_title and wrapped_description else 0
        total_height = (
            title_box[3] - title_box[1] + gap + description_box[3] - description_box[1]
        )
        y = (height - total_height) / 2
        if wrapped_title:
            draw.multiline_text(
                (width / 2, y),
                wrapped_title,
                font=title_font,
                fill="white",
                anchor="ma",
                align="center",
                spacing=px(14),
                stroke_width=px(1) if config.font_bold is None else 0,
            )
            y += title_box[3] - title_box[1] + gap
        if wrapped_description:
            draw.multiline_text(
                (width / 2, y),
                wrapped_description,
                font=description_font,
                fill=(215, 215, 215),
                anchor="ma",
                align="center",
                spacing=px(10),
            )
        title_path = work_dir / "title.png"
        image.save(title_path)

    caption_paths: list[Path] = []
    caption_font = _font(config.font_bold, px(46))
    for index, caption in enumerate(copy.captions):
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        wrapped = _wrap_pixels(draw, caption.text, caption_font, width - px(300))
        bounds = draw.multiline_textbbox(
            (0, 0),
            wrapped,
            font=caption_font,
            spacing=px(12),
            align="center",
            stroke_width=px(1),
        )
        text_width, text_height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        padding_x, padding_y = px(28), px(20)
        left = (width - text_width) / 2 - padding_x
        top = height - text_height - (2 * padding_y) - px(64)
        right = (width + text_width) / 2 + padding_x
        bottom = height - px(64)
        draw.rounded_rectangle(
            (left, top, right, bottom), radius=px(18), fill=(0, 0, 0, 170)
        )
        draw.multiline_text(
            (width / 2, top + padding_y - bounds[1]),
            wrapped,
            font=caption_font,
            fill="white",
            anchor="ma",
            align="center",
            spacing=px(12),
            stroke_width=px(1),
            stroke_fill=(0, 0, 0, 220),
        )
        path = work_dir / f"caption-{index:03d}.png"
        image.save(path)
        caption_paths.append(path)

    print(f"Title card: {'yes' if title_path else 'no'}")
    print(f"Timed captions: {len(caption_paths)}")
    return title_path, tuple(caption_paths)

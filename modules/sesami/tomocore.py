"""/sesami tomocore image composition: a name-tag frame overlay plus a
rough person-count estimate, on top of a live camera capture.

People counting uses OpenCV's bundled HOG pedestrian detector (no extra
model download needed) -- it's a rough estimate, not an exact count, and
is biased toward people standing/facing the camera.
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

IMG_DIR = Path(__file__).resolve().parent / "img"
NAMEFRAME_PATH = IMG_DIR / "nameframeT.png"

# Fraction of nameframeT.png's own width where the yellow/white regions
# meet (measured on the 205px-wide source image: yellow runs to ~x=71).
_NAMEFRAME_SPLIT = 71 / 205

_LOCATION_LABEL = "部室"
_WATER_BLUE = (100, 200, 255)
_DARK_TEXT = (40, 40, 40)
_LIGHT_TEXT = (255, 255, 255)

# Searched in order; the first one found is used. Ubuntu doesn't ship a
# Japanese-capable font by default, so one of these packages must be
# installed (e.g. `sudo apt install fonts-noto-cjk`).
_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJKjp-Regular.otf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/truetype/takao-gothic/TakaoGothic.ttf",
    "/usr/share/fonts/truetype/ipaexfont-gothic/ipaexg.ttf",
]


class TomocoreError(Exception):
    """User-facing error (missing font, bad image, ...)."""


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise TomocoreError(
        "日本語フォントが見つかりません。`sudo apt install fonts-noto-cjk` 等でインストールしてください。"
    )


def _count_people(image: Image.Image) -> int:
    cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    rects, _weights = hog.detectMultiScale(cv_image, winStride=(8, 8), padding=(8, 8), scale=1.05)
    return len(rects)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw, center: tuple[float, float], text: str, font: ImageFont.FreeTypeFont, fill
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((center[0] - w / 2 - bbox[0], center[1] - h / 2 - bbox[1]), text, font=font, fill=fill)


def _draw_mixed_text(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    segments: list[tuple[str, tuple[int, int, int]]],
    font: ImageFont.FreeTypeFont,
) -> None:
    """Draw segments side by side (each its own color), centered as a whole."""
    widths = [draw.textlength(text, font=font) for text, _color in segments]
    bbox = draw.textbbox((0, 0), "人", font=font)  # representative glyph for vertical centering
    x = center[0] - sum(widths) / 2
    y = center[1] - (bbox[3] - bbox[1]) / 2 - bbox[1]
    for (text, color), width in zip(segments, widths):
        draw.text((x, y), text, font=font, fill=color)
        x += width


def _paste_nameframe(base: Image.Image, camera_label: str) -> None:
    nameframe = Image.open(NAMEFRAME_PATH).convert("RGBA")
    target_width = int(base.width * 0.45)
    scale = target_width / nameframe.width
    target_height = max(1, round(nameframe.height * scale))
    nameframe = nameframe.resize((target_width, target_height), Image.Resampling.LANCZOS)

    x = (base.width - target_width) // 2
    y = round(base.height * 0.03)
    base.paste(nameframe, (x, y), nameframe)

    draw = ImageDraw.Draw(base)
    font = _load_font(max(10, round(target_height * 0.55)))

    split_x = x + round(target_width * _NAMEFRAME_SPLIT)
    yellow_center = ((x + split_x) / 2, y + target_height / 2)
    white_center = ((split_x + x + target_width) / 2, y + target_height / 2)

    _draw_centered_text(draw, yellow_center, camera_label, font, _DARK_TEXT)
    _draw_centered_text(draw, white_center, _LOCATION_LABEL, font, _DARK_TEXT)


def _draw_people_banner(base: Image.Image, count: int) -> None:
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    band_top = round(base.height * 0.75)
    ImageDraw.Draw(overlay).rectangle([(0, band_top), (base.width, base.height)], fill=(60, 60, 60, 150))
    base.alpha_composite(overlay)

    draw = ImageDraw.Draw(base)
    font = _load_font(max(16, round(base.height * 0.06)))
    center = (base.width / 2, (band_top + base.height) / 2)
    _draw_mixed_text(
        draw,
        center,
        [("人が", _LIGHT_TEXT), (f"{count}人", _WATER_BLUE), ("います", _LIGHT_TEXT)],
        font,
    )


def _compose_sync(jpeg_bytes: bytes, camera_label: str) -> bytes:
    image = Image.open(io.BytesIO(jpeg_bytes)).convert("RGBA")
    count = _count_people(image.convert("RGB"))

    _paste_nameframe(image, camera_label)
    _draw_people_banner(image, count)

    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=90)
    return buf.getvalue()


async def compose(jpeg_bytes: bytes, camera_label: str) -> bytes:
    return await asyncio.to_thread(_compose_sync, jpeg_bytes, camera_label)

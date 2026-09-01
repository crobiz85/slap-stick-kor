"""Shared Hangul glyph rendering helpers for the Robotrek build."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GLYPH_WIDTH = 16
GLYPH_HEIGHT = 16
GLYPH_SAFE_MARGIN = 1


def find_default_font() -> Path:
    candidates = (
        Path(r"C:\Windows\Fonts\malgun.ttf"),
        Path(r"C:\Windows\Fonts\malgunbd.ttf"),
        Path(r"C:\Windows\Fonts\gulim.ttc"),
        Path(r"C:\Windows\Fonts\NotoSansKR-VF.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No Korean-capable font found; pass --font explicitly")


def render_mask(character: str, font: ImageFont.FreeTypeFont, render_size: int) -> Image.Image:
    canvas = Image.new("L", (GLYPH_WIDTH, GLYPH_HEIGHT), 0)
    draw = ImageDraw.Draw(canvas)
    bbox = draw.textbbox((0, 0), character, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    safe_width = GLYPH_WIDTH - (GLYPH_SAFE_MARGIN * 2)
    safe_height = GLYPH_HEIGHT - (GLYPH_SAFE_MARGIN * 2)
    if width > safe_width or height > safe_height:
        raise ValueError(
            f"glyph {character!r} is {width}x{height}; "
            f"font size {render_size} exceeds the {safe_width}x{safe_height} safe area"
        )
    draw.text(
        (
            GLYPH_SAFE_MARGIN + (safe_width - width) // 2 - bbox[0],
            GLYPH_SAFE_MARGIN + (safe_height - height) // 2 - bbox[1],
        ),
        character,
        font=font,
        fill=255,
    )
    mask = Image.new("1", (GLYPH_WIDTH, GLYPH_HEIGHT), 0)
    mask.paste(canvas.point(lambda value: 255 if value >= 72 else 0))
    return mask


def encode_tile(mask: Image.Image) -> bytes:
    encoded = bytearray()
    for row in range(8):
        low = 0
        high = 0
        for column in range(8):
            ink = mask.getpixel((column, row)) != 0
            value = 1 if ink else 3
            bit = 7 - column
            low |= (value & 1) << bit
            high |= ((value >> 1) & 1) << bit
        encoded.extend((low, high))
    return bytes(encoded)

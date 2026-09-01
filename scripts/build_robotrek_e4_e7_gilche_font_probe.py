"""Build the 843-glyph Robotrek probe with the supplied gilche 8x16 font."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

import build_robotrek_e4_e7_full_font_probe as builder


ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "assets" / "fonts" / "gilche-1bpp-8x16.fnt"
FONT_SHA256 = "5BE8F0C52F8FDA3AF4E8B7429D49AE69C4C4BD7D3A59D9C5B848CD1EFAEDB586"
GLYPH_BYTES = 16
GLYPH_COUNT = 2432


def ks_x_1001_hangul() -> list[str]:
    result: list[str] = []
    for lead in range(0xB0, 0xC9):
        for trail in range(0xA1, 0xFF):
            result.append(bytes((lead, trail)).decode("euc_kr"))
    if len(result) != 2350:
        raise AssertionError("unexpected KS X 1001 Hangul count")
    return result


RAW = FONT.read_bytes()
if len(RAW) != GLYPH_BYTES * GLYPH_COUNT:
    raise ValueError(f"unexpected gilche size: {len(RAW)}")
if hashlib.sha256(RAW).hexdigest().upper() != FONT_SHA256:
    raise ValueError("unexpected gilche SHA-256")

INDEX_FOR = {character: index for index, character in enumerate(ks_x_1001_hangul())}


def render_gilche(character: str) -> tuple[bytes, Image.Image]:
    try:
        index = INDEX_FOR[character]
    except KeyError as error:
        raise ValueError(f"gilche lacks required character: {character}") from error

    rows = RAW[index * GLYPH_BYTES : (index + 1) * GLYPH_BYTES]
    mask = Image.new("L", (8, 16), 0)
    for y, value in enumerate(rows):
        for x in range(8):
            if value & (0x80 >> x):
                mask.putpixel((x, y), 255)

    if mask.getbbox() is None:
        raise ValueError(f"blank gilche glyph: {character}")
    top = builder.encode_tile(mask.crop((0, 0, 8, 8)))
    bottom = builder.encode_tile(mask.crop((0, 8, 8, 16)))
    return top + bottom, mask


builder.CUSTOM_RENDERER = render_gilche
builder.FONT_MANIFEST_LABEL = str(FONT)
builder.FONT_NOTE = "supplied gilche native 1bpp 8x16; no scaling or antialiasing"
builder.OUTPUT = ROOT / "build" / "robotrek-kor-e4-e7-gilche-font-probe.sfc"
builder.PREVIEW = ROOT / "build" / "robotrek-kor-e4-e7-gilche-font-preview.png"
builder.SAMPLE_PREVIEW = ROOT / "build" / "robotrek-kor-e4-e7-gilche-sample-preview.png"
builder.MANIFEST = ROOT / "build" / "robotrek-kor-e4-e7-gilche-font-probe.json"
builder.VERIFY = ROOT / "diagnostics" / "robotrek-e4-e7-gilche-font-verification.json"


def main() -> None:
    builder.main()
    manifest = json.loads(builder.MANIFEST.read_text(encoding="utf-8"))
    manifest.update(
        {
            "font_sha256": FONT_SHA256,
            "font_source_format": "2432 glyphs x 16 bytes, 1bpp 8x16",
            "font_mapping": "first 2350 glyphs follow KS X 1001 Wansung Hangul order",
            "font_scaling": "none",
        }
    )
    builder.MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

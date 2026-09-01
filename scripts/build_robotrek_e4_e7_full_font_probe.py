"""Build the stable 843-glyph E4-E7 Korean font probe for Robotrek (USA).

The input order in ``robotrek-needed-hangul.tsv`` is preserved, so the most
frequent syllables receive the earliest codes.  The resulting map is the
canonical encoding table for later dialogue insertion.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from robotrek_font_utils import encode_tile, find_default_font, render_mask
from build_robotrek_e4_d8_single_probe import (
    DISPATCHER_CPU,
    DISPATCHER_OFFSET,
    DMA_BANK_OFFSET,
    DMA_BANK_ORIGINAL,
    DOG_TEXT_OFFSET,
    DOG_TEXT_ORIGINAL,
    FONT_SOURCE_OFFSET,
    FONT_SOURCE_ORIGINAL,
    KOREAN_PAGE0_OFFSET,
    NATIVE_FONT_MIRROR_OFFSET,
    NATIVE_FONT_SIZE,
    NATIVE_FONT_SOURCE,
    SOURCE,
    SOURCE_CALCULATOR_CPU,
    SOURCE_CALCULATOR_OFFSET,
    SOURCE_LENGTH,
    SOURCE_SHA256,
    STUB_TABLE_OFFSET,
    TARGET_LENGTH,
    TEXT_DISPATCH_OFFSET,
    TEXT_DISPATCH_ORIGINAL,
    make_dispatch_stubs,
    make_dispatcher,
    make_source_calculator,
    sha256,
)
from robotrek_hirom_utils import refresh_full_hirom_checksum


ROOT = Path(__file__).resolve().parent.parent
NEEDED = ROOT / "translation" / "robotrek-needed-hangul.tsv"
MAP = ROOT / "translation" / "robotrek-e4-e7-glyph-map.tsv"
OUTPUT = ROOT / "build" / "robotrek-kor-e4-e7-full-font-probe.sfc"
PREVIEW = ROOT / "build" / "robotrek-kor-e4-e7-full-font-preview.png"
SAMPLE_PREVIEW = ROOT / "build" / "robotrek-kor-e4-e7-sample-preview.png"
MANIFEST = ROOT / "build" / "robotrek-kor-e4-e7-full-font-probe.json"
VERIFY = ROOT / "diagnostics" / "robotrek-e4-e7-full-font-verification.json"

PREFIX_FIRST = 0xE4
PREFIX_COUNT = 4
PAGE_SIZE = 0x2000
GLYPHS_PER_PAGE = 256
CAPACITY = PREFIX_COUNT * GLYPHS_PER_PAGE
EXPECTED_GLYPHS = 843
SAMPLE = "한글확장"
NARROW_THRESHOLD = 128
PREFERRED_FONT_PATH = Path(r"C:\Windows\Fonts\malgunbd.ttf")
FONT_SIZE = 12
DIRECT_8X16_RENDER = False
FONT_NOTE = "provisional 8x16 Malgun Bold/Lanczos"
CUSTOM_RENDERER: Callable[[str], tuple[bytes, Image.Image]] | None = None
FONT_MANIFEST_LABEL: str | None = None


def read_required() -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    with NEEDED.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            character = row["character"]
            if len(character) != 1 or not (0xAC00 <= ord(character) <= 0xD7A3):
                raise ValueError(f"invalid Hangul entry: {character!r}")
            rows.append((character, int(row["frequency_in_reference"])))
    if len(rows) != EXPECTED_GLYPHS or len({char for char, _ in rows}) != EXPECTED_GLYPHS:
        raise ValueError(f"expected {EXPECTED_GLYPHS} unique Hangul syllables, got {len(rows)}")
    return rows


def render_narrow(character: str, font: ImageFont.FreeTypeFont) -> tuple[bytes, Image.Image]:
    if DIRECT_8X16_RENDER:
        canvas = Image.new("L", (8, 16), 0)
        draw = ImageDraw.Draw(canvas)
        bbox = draw.textbbox((0, 0), character, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width > 9 or height > 16:
            raise ValueError(f"direct glyph {character!r} is {width}x{height}, larger than the supported 9x16 crop")
        draw.text(
            ((8 - width) // 2 - bbox[0], (16 - height) // 2 - bbox[1]),
            character,
            font=font,
            fill=255,
        )
        narrow = canvas.point(lambda pixel: 255 if pixel >= NARROW_THRESHOLD else 0, mode="1")
    else:
        wide = render_mask(character, font, FONT_SIZE)
        reduced = wide.convert("L").resize((8, 16), Image.Resampling.LANCZOS)
        narrow = reduced.point(
            lambda pixel: 255 if pixel >= NARROW_THRESHOLD else 0,
            mode="1",
        )
    if narrow.getbbox() is None:
        raise ValueError(f"blank rendered glyph: {character}")
    top = encode_tile(narrow.crop((0, 0, 8, 8)))
    bottom = encode_tile(narrow.crop((0, 8, 8, 16)))
    return top + bottom, narrow


def install_glyph(target: bytearray, ordinal: int, encoded: bytes) -> tuple[int, int, int, int]:
    page, index = divmod(ordinal, GLYPHS_PER_PAGE)
    prefix = PREFIX_FIRST + page
    page_base = KOREAN_PAGE0_OFFSET + page * PAGE_SIZE
    top_offset = page_base + index * 16
    bottom_offset = top_offset + 0x1000
    target[top_offset : top_offset + 16] = encoded[:16]
    target[bottom_offset : bottom_offset + 16] = encoded[16:]
    return prefix, index, top_offset, bottom_offset


def make_preview(entries: list[tuple[str, Image.Image]]) -> Image.Image:
    columns = 32
    scale = 3
    cell_width, cell_height = 8 * scale, 16 * scale
    rows = (len(entries) + columns - 1) // columns
    preview = Image.new("RGB", (columns * cell_width, rows * cell_height), "#20242b")
    for ordinal, (_, mask) in enumerate(entries):
        x = (ordinal % columns) * cell_width
        y = (ordinal // columns) * cell_height
        tile = Image.new("RGB", mask.size, "#20242b")
        tile.paste("white", mask=mask.convert("L"))
        preview.paste(tile.resize((cell_width, cell_height), Image.Resampling.NEAREST), (x, y))
    return preview


def make_sample_preview(entries: list[tuple[str, Image.Image]]) -> Image.Image:
    masks = {character: mask for character, mask in entries}
    scale = 12
    preview = Image.new("RGB", (len(SAMPLE) * 8 * scale, 16 * scale), "black")
    for position, character in enumerate(SAMPLE):
        mask = masks[character]
        tile = Image.new("RGB", mask.size, "black")
        tile.paste("white", mask=mask.convert("L"))
        preview.paste(
            tile.resize((8 * scale, 16 * scale), Image.Resampling.NEAREST),
            (position * 8 * scale, 0),
        )
    return preview


def main() -> None:
    source = SOURCE.read_bytes()
    if len(source) != SOURCE_LENGTH or sha256(source) != SOURCE_SHA256:
        raise ValueError("unexpected Robotrek (USA) source ROM")
    for offset, expected, label in (
        (TEXT_DISPATCH_OFFSET, TEXT_DISPATCH_ORIGINAL, "text dispatcher"),
        (FONT_SOURCE_OFFSET, FONT_SOURCE_ORIGINAL, "font source calculator"),
        (DMA_BANK_OFFSET, DMA_BANK_ORIGINAL, "font DMA bank"),
        (DOG_TEXT_OFFSET, DOG_TEXT_ORIGINAL, "dog dialogue"),
    ):
        if source[offset : offset + len(expected)] != expected:
            raise ValueError(f"{label} signature mismatch at 0x{offset:06X}")

    required = read_required()
    font_path = PREFERRED_FONT_PATH if PREFERRED_FONT_PATH.exists() else find_default_font()
    font = None if CUSTOM_RENDERER is not None else ImageFont.truetype(str(font_path), FONT_SIZE)
    target = bytearray(source)
    target.extend(b"\xFF" * (TARGET_LENGTH - SOURCE_LENGTH))
    target[NATIVE_FONT_MIRROR_OFFSET : NATIVE_FONT_MIRROR_OFFSET + NATIVE_FONT_SIZE] = source[
        NATIVE_FONT_SOURCE : NATIVE_FONT_SOURCE + NATIVE_FONT_SIZE
    ]

    map_rows: list[dict[str, str | int]] = []
    previews: list[tuple[str, Image.Image]] = []
    code_for: dict[str, bytes] = {}
    for ordinal, (character, frequency) in enumerate(required):
        if CUSTOM_RENDERER is not None:
            encoded, mask = CUSTOM_RENDERER(character)
        else:
            assert font is not None
            encoded, mask = render_narrow(character, font)
        prefix, index, top_offset, bottom_offset = install_glyph(target, ordinal, encoded)
        code_for[character] = bytes((prefix, index))
        previews.append((character, mask))
        map_rows.append(
            {
                "character": character,
                "frequency": frequency,
                "ordinal": ordinal,
                "code": f"{prefix:02X} {index:02X}",
                "page": prefix - PREFIX_FIRST,
                "index": index,
                "top_file_offset": f"0x{top_offset:06X}",
                "bottom_file_offset": f"0x{bottom_offset:06X}",
            }
        )

    dispatcher = make_dispatcher()
    stubs = make_dispatch_stubs(source)
    calculator = make_source_calculator()
    dispatch_patch = bytes((0x5C, DISPATCHER_CPU & 0xFF, DISPATCHER_CPU >> 8, 0xD8))
    dispatch_patch += b"\xEA" * (len(TEXT_DISPATCH_ORIGINAL) - len(dispatch_patch))
    target[TEXT_DISPATCH_OFFSET : TEXT_DISPATCH_OFFSET + len(dispatch_patch)] = dispatch_patch
    source_patch = bytes((0x22, SOURCE_CALCULATOR_CPU & 0xFF, SOURCE_CALCULATOR_CPU >> 8, 0xD8, 0x85, 0x46))
    source_patch += b"\xEA" * (len(FONT_SOURCE_ORIGINAL) - len(source_patch))
    target[FONT_SOURCE_OFFSET : FONT_SOURCE_OFFSET + len(source_patch)] = source_patch
    target[DMA_BANK_OFFSET : DMA_BANK_OFFSET + len(DMA_BANK_ORIGINAL)] = bytes.fromhex("A9 D8 8D 04 43")
    target[DISPATCHER_OFFSET : DISPATCHER_OFFSET + len(dispatcher)] = dispatcher
    target[STUB_TABLE_OFFSET : STUB_TABLE_OFFSET + len(stubs)] = stubs
    target[SOURCE_CALCULATOR_OFFSET : SOURCE_CALCULATOR_OFFSET + len(calculator)] = calculator

    sample_bytes = b"".join(code_for[character] for character in SAMPLE)
    sample_record = b"\xD7\xCD" + sample_bytes + b"\xCD\xC0"
    if len(sample_record) != len(DOG_TEXT_ORIGINAL):
        raise AssertionError("sample must preserve the fixed dialogue record size")
    target[DOG_TEXT_OFFSET : DOG_TEXT_OFFSET + len(sample_record)] = sample_record
    checksum = refresh_full_hirom_checksum(target)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    MAP.parent.mkdir(parents=True, exist_ok=True)
    VERIFY.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(target)
    with MAP.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(map_rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(map_rows)
    make_preview(previews).save(PREVIEW)
    make_sample_preview(previews).save(SAMPLE_PREVIEW)

    page_counts = [sum(1 for row in map_rows if row["page"] == page) for page in range(PREFIX_COUNT)]
    verification = {
        "status": "static_verified_runtime_test_required",
        "required_unique_hangul": len(required),
        "mapped_unique_hangul": len(code_for),
        "missing_hangul": [],
        "capacity": CAPACITY,
        "unused_codes": CAPACITY - len(required),
        "page_counts": page_counts,
        "blank_glyphs": [],
        "sample": SAMPLE,
        "sample_codes": sample_bytes.hex(" ").upper(),
        "sample_record_offset": f"0x{DOG_TEXT_OFFSET:06X}",
        "sample_record_bytes": sample_record.hex(" ").upper(),
        "native_font_mirror_matches_source": target[NATIVE_FONT_MIRROR_OFFSET:NATIVE_FONT_MIRROR_OFFSET + NATIVE_FONT_SIZE] == source[NATIVE_FONT_SOURCE:NATIVE_FONT_SOURCE + NATIVE_FONT_SIZE],
        "output_size": len(target),
        "output_sha256": sha256(target),
    }
    manifest = {
        "kind": "Robotrek USA stable E4-E7 843-glyph Korean font probe",
        "source": SOURCE.name,
        "source_sha256": SOURCE_SHA256,
        "output": str(OUTPUT.relative_to(ROOT)),
        "output_sha256": sha256(target),
        "font": FONT_MANIFEST_LABEL or str(font_path),
        "glyph_map": str(MAP.relative_to(ROOT)),
        "preview": str(PREVIEW.relative_to(ROOT)),
        "sample_preview": str(SAMPLE_PREVIEW.relative_to(ROOT)),
        "required_glyphs": len(required),
        "capacity": CAPACITY,
        "unused_codes": CAPACITY - len(required),
        "page_counts": page_counts,
        "encoding_pages": [f"{PREFIX_FIRST + page:02X} 00-{PREFIX_FIRST + page:02X} FF" for page in range(PREFIX_COUNT)],
        "sample_dialogue": SAMPLE,
        "sample_codes": sample_bytes.hex(" ").upper(),
        "header_checksum": f"0x{checksum:04X}",
        "note": f"Font artwork is {FONT_NOTE}; code allocation is stable.",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    VERIFY.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

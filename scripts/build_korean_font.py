"""Build a first Korean glyph map and preview for the Slap Stick font banks.

The Japanese ROM uses inverted Game Boy 2BPP tiles: color 3 is the blank
background and color 0 is ink.  This script only creates a reviewed glyph map
and preview; it does not modify a ROM.
"""

from pathlib import Path
import argparse
import re

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
DRAFT_PATH = ROOT / "translation" / "korean-draft.tsv"
MENU_PREVIEW_PATH = ROOT / "translation" / "korean-menu-preview.tsv"
GAME_MENU_PATH = ROOT / "translation" / "korean-game-menu.tsv"
DEFAULT_MAP_PATH = ROOT / "translation" / "korean-glyph-map.tsv"
DEFAULT_PREVIEW_PATH = ROOT / "build" / "korean-font-preview.png"
HANGUL_START = 0xAC00
HANGUL_END = 0xD7A3
GLYPH_BYTES = 16
FONT_BANK_OFFSET = 0x60000
FONT_LEAD_BYTE = 0x82
CONTROL_MARKER = re.compile(r"\[[^\]]+\]|\\n|˳")


def find_default_font() -> Path:
    candidates = (
        Path(r"C:\Windows\Fonts\gulim.ttc"),
        Path(r"C:\Windows\Fonts\malgun.ttf"),
        Path(r"C:\Windows\Fonts\NotoSansKR-VF.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No Korean-capable font found; pass --font explicitly")


def read_draft_characters() -> list[str]:
    characters = set()
    for source_path in (DRAFT_PATH, MENU_PREVIEW_PATH, GAME_MENU_PATH):
        if not source_path.exists():
            continue
        for line in source_path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            columns = line.split("\t")
            if len(columns) < 2:
                continue
            korean_column = 3 if source_path == GAME_MENU_PATH else 1
            if len(columns) <= korean_column:
                continue
            korean = CONTROL_MARKER.sub("", columns[korean_column])
            characters.update(
                character
                for character in korean
                if HANGUL_START <= ord(character) <= HANGUL_END
            )
    return sorted(characters)


def read_used_kanji_codes() -> set[int]:
    used: set[int] = set()
    for line in (ROOT / "translation" / "script.tsv").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 4:
            continue
        raw = columns[3].split()
        for index, token in enumerate(raw[:-1]):
            if token.upper() == "82":
                used.add(int(raw[index + 1], 16))
    return used


def allocate_codes(characters: list[str]) -> dict[str, int]:
    # 0x82xx is the dictionary/font page used by ordinary dialog rendering.
    # Prefer slots outside the Japanese dictionary, then unused lower slots.
    used = read_used_kanji_codes()
    available = list(range(0x90, 0x100))
    available.extend(value for value in range(0x90) if value not in used)
    if len(characters) > len(available):
        raise ValueError(f"Need {len(characters)} glyph slots but only {len(available)} are available")
    return dict(zip(characters, available))


def render_mask(character: str, font: ImageFont.FreeTypeFont, render_size: int) -> Image.Image:
    canvas = Image.new("L", (8, 8), 0)
    draw = ImageDraw.Draw(canvas)
    bbox = draw.textbbox((0, 0), character, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text(
        ((8 - width) // 2 - bbox[0], (8 - height) // 2 - bbox[1]),
        character,
        font=font,
        fill=255,
    )
    # Keep the 8x8 glyph strokes crisp enough for the original low-resolution
    # renderer; direct pixel rendering avoids turning Hangul into solid blobs.
    mask = Image.new("1", (8, 8), 0)
    mask.paste(canvas.point(lambda value: 255 if value >= 64 else 0))
    return mask


def encode_tile(mask: Image.Image) -> bytes:
    output = bytearray()
    for row in range(8):
        low = 0
        high = 0
        for column in range(8):
            ink = mask.getpixel((column, row)) != 0
            value = 0 if ink else 3
            bit = 7 - column
            low |= (value & 1) << bit
            high |= ((value >> 1) & 1) << bit
        output.extend((low, high))
    return bytes(output)


def write_preview(
    characters: list[str],
    masks: dict[str, Image.Image],
    codes: dict[str, int],
    output_path: Path,
    scale: int,
) -> None:
    columns = 16
    rows = (len(characters) + columns - 1) // columns
    image = Image.new("L", (columns * 8 * scale, rows * 8 * scale), 255)
    for index, character in enumerate(characters):
        x = (index % columns) * 8 * scale
        y = (index // columns) * 8 * scale
        enlarged = masks[character].convert("L").resize((8 * scale, 8 * scale), Image.Resampling.NEAREST)
        image.paste(enlarged.point(lambda value: 0 if value else 255), (x, y))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def write_map(
    characters: list[str],
    codes: dict[str, int],
    tiles: dict[str, bytes],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Generated from Korean draft, compact menu preview, and game-screen prompts; 0x82xx dialog-font slots.\n")
        handle.write("# The preview builder duplicates these tiles into the 0x83xx game-menu page.\n")
        handle.write("# character\tcodepoint\tcode bytes\tfile offset\t2bpp tile bytes\n")
        for character in characters:
            low = codes[character]
            offset = FONT_BANK_OFFSET + low * GLYPH_BYTES
            handle.write(
                f"{character}\tU+{ord(character):04X}\t{FONT_LEAD_BYTE:02X} {low:02X}\t"
                f"0x{offset:05X}\t{tiles[character].hex(' ').upper()}\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Korean glyph map and preview without modifying the ROM.")
    parser.add_argument("--font", type=Path, default=None, help="Korean-capable TTF/TTC font")
    parser.add_argument("--font-size", type=int, default=8)
    parser.add_argument("--preview-scale", type=int, default=8)
    parser.add_argument("--output-map", type=Path, default=DEFAULT_MAP_PATH)
    parser.add_argument("--output-preview", type=Path, default=DEFAULT_PREVIEW_PATH)
    args = parser.parse_args()

    font_path = args.font or find_default_font()
    characters = read_draft_characters()
    codes = allocate_codes(characters)
    font = ImageFont.truetype(str(font_path), args.font_size)
    masks = {character: render_mask(character, font, args.font_size) for character in characters}
    tiles = {character: encode_tile(masks[character]) for character in characters}

    write_map(characters, codes, tiles, args.output_map)
    write_preview(characters, masks, codes, args.output_preview, args.preview_scale)
    print(f"font={font_path}")
    print(f"glyphs={len(characters)}")
    print(args.output_map)
    print(args.output_preview)


if __name__ == "__main__":
    main()

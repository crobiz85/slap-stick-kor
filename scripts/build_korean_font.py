"""Build the Korean glyph map used by the playable Slap Stick preview.

The game's dictionary codes ``80xx`` and ``81xx`` resolve to 16×16 Japanese
glyphs at ``0x50000`` and ``0x54000`` respectively.  Each glyph is four
8×8 Game Boy-style 2BPP tiles (64 bytes), and the text engine writes those
glyphs to its VRAM cells at run time.  This script allocates only codes absent
from the extracted Japanese script, then renders replacement source tiles into
their actual locations.  It never modifies a ROM itself.
"""

from pathlib import Path
import argparse
import re

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
DRAFT_PATH = ROOT / "translation" / "korean-draft.tsv"
MENU_PREVIEW_PATH = ROOT / "translation" / "korean-menu-preview.tsv"
GAME_MENU_PATH = ROOT / "translation" / "korean-game-menu.tsv"
ITEM_PREVIEW_PATH = ROOT / "translation" / "korean-item-preview.tsv"
DEFAULT_MAP_PATH = ROOT / "translation" / "korean-glyph-map.tsv"
DEFAULT_PREVIEW_PATH = ROOT / "build" / "korean-font-preview.png"
HANGUL_START = 0xAC00
HANGUL_END = 0xD7A3
GLYPH_WIDTH = 16
GLYPH_HEIGHT = 16
TILE_WIDTH = 8
TILE_HEIGHT = 8
GLYPH_BYTES = 64
FONT_BANK_OFFSET = 0x50000
FONT_LEAD_BYTE = 0x80
SECOND_FONT_BANK_OFFSET = 0x54000
SECOND_FONT_LEAD_BYTE = 0x81
CONTROL_MARKER = re.compile(r"\[[^\]]+\]|\\n|˳")

# These are the only long dialogue drafts inserted by the current preview
# patch.  The rest remain in korean-draft.tsv for translation work but must
# not consume scarce, verified 0x80/0x81 glyph slots yet.
PREVIEW_DRAFT_IDS = {
    "0016", "0017", "0018", "0019", "0020",
    "0058", "0059", "0060", "0061", "0062", "0063",
}


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
    for source_path in (DRAFT_PATH, MENU_PREVIEW_PATH, GAME_MENU_PATH, ITEM_PREVIEW_PATH):
        if not source_path.exists():
            continue
        for line in source_path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            columns = line.split("\t")
            if len(columns) < 2:
                continue
            if source_path == DRAFT_PATH and columns[0] not in PREVIEW_DRAFT_IDS:
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


def read_used_kanji_codes(lead_byte: int) -> set[int]:
    used: set[int] = set()
    for line in (ROOT / "translation" / "script.tsv").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 4:
            continue
        raw = columns[3].split()
        for index, token in enumerate(raw[:-1]):
            if token.upper() == f"{lead_byte:02X}":
                used.add(int(raw[index + 1], 16))
    return used


def available_codes(lead_byte: int) -> list[int]:
    used = read_used_kanji_codes(lead_byte)
    # A leading 0x80/0x81 is followed by a glyph index, not a standalone
    # control byte.  Every index seen in the extracted script is reserved;
    # keeping only the complement prevents overwriting Japanese text.
    return [value for value in range(0x100) if value not in used]


def allocate_codes(characters: list[str]) -> dict[str, tuple[int, int]]:
    primary = [(FONT_LEAD_BYTE, value) for value in available_codes(FONT_LEAD_BYTE)]
    secondary = [(SECOND_FONT_LEAD_BYTE, value) for value in available_codes(SECOND_FONT_LEAD_BYTE)]
    available = primary + secondary
    if len(characters) > len(available):
        raise ValueError(f"Need {len(characters)} glyph slots but only {len(available)} are available")
    return dict(zip(characters, available))


def render_mask(character: str, font: ImageFont.FreeTypeFont, render_size: int) -> Image.Image:
    # Each source glyph is a native 16×16 bitmap, stored as a 2×2 grid of
    # 8×8 2BPP tiles.
    canvas = Image.new("L", (GLYPH_WIDTH, GLYPH_HEIGHT), 0)
    draw = ImageDraw.Draw(canvas)
    bbox = draw.textbbox((0, 0), character, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text(
        ((GLYPH_WIDTH - width) // 2 - bbox[0], (GLYPH_HEIGHT - height) // 2 - bbox[1]),
        character,
        font=font,
        fill=255,
    )
    mask = Image.new("1", (GLYPH_WIDTH, GLYPH_HEIGHT), 0)
    mask.paste(canvas.point(lambda value: 255 if value >= 72 else 0))
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


def encode_glyph(mask: Image.Image) -> bytes:
    if mask.size != (GLYPH_WIDTH, GLYPH_HEIGHT):
        raise ValueError(f"expected a {GLYPH_WIDTH}x{GLYPH_HEIGHT} glyph, got {mask.size}")
    return b"".join(
        encode_tile(mask.crop(bounds))
        for bounds in (
            (0, 0, TILE_WIDTH, TILE_HEIGHT),
            (TILE_WIDTH, 0, GLYPH_WIDTH, TILE_HEIGHT),
            (0, TILE_HEIGHT, TILE_WIDTH, GLYPH_HEIGHT),
            (TILE_WIDTH, TILE_HEIGHT, GLYPH_WIDTH, GLYPH_HEIGHT),
        )
    )


def write_preview(
    characters: list[str],
    masks: dict[str, Image.Image],
    codes: dict[str, tuple[int, int]],
    output_path: Path,
    scale: int,
) -> None:
    columns = 16
    rows = (len(characters) + columns - 1) // columns
    image = Image.new("L", (columns * GLYPH_WIDTH * scale, rows * GLYPH_HEIGHT * scale), 255)
    for index, character in enumerate(characters):
        x = (index % columns) * GLYPH_WIDTH * scale
        y = (index // columns) * GLYPH_HEIGHT * scale
        enlarged = masks[character].convert("L").resize(
            (GLYPH_WIDTH * scale, GLYPH_HEIGHT * scale), Image.Resampling.NEAREST
        )
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
        handle.write("# Generated for the current Korean preview from compact menus, game-screen prompts, and six dialogue drafts.\n")
        handle.write("# Uses script-unused slots in the verified 0x80xx/0x81xx 16x16 source font pages.\n")
        handle.write("# character\tcodepoint\tcode bytes\tfile offset\t2bpp tile bytes\n")
        for character in characters:
            lead_byte, low = codes[character]
            bank_offset = FONT_BANK_OFFSET if lead_byte == FONT_LEAD_BYTE else SECOND_FONT_BANK_OFFSET
            offset = bank_offset + low * GLYPH_BYTES
            handle.write(
                f"{character}\tU+{ord(character):04X}\t{lead_byte:02X} {low:02X}\t"
                f"0x{offset:05X}\t{tiles[character].hex(' ').upper()}\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Korean glyph map and preview without modifying the ROM.")
    parser.add_argument("--font", type=Path, default=None, help="Korean-capable TTF/TTC font")
    parser.add_argument("--font-size", type=int, default=16)
    parser.add_argument("--preview-scale", type=int, default=8)
    parser.add_argument("--output-map", type=Path, default=DEFAULT_MAP_PATH)
    parser.add_argument("--output-preview", type=Path, default=DEFAULT_PREVIEW_PATH)
    args = parser.parse_args()

    font_path = args.font or find_default_font()
    characters = read_draft_characters()
    codes = allocate_codes(characters)
    font = ImageFont.truetype(str(font_path), args.font_size)
    masks = {character: render_mask(character, font, args.font_size) for character in characters}
    tiles = {character: encode_glyph(masks[character]) for character in characters}

    write_map(characters, codes, tiles, args.output_map)
    write_preview(characters, masks, codes, args.output_preview, args.preview_scale)
    print(f"font={font_path}")
    print(f"glyphs={len(characters)}")
    print(args.output_map)
    print(args.output_preview)


if __name__ == "__main__":
    main()

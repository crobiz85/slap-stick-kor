from pathlib import Path
import argparse
import struct
import zlib
import binascii


ROM = Path(__file__).parent.parent / "Slap Stick (J).smc"


def decode_snes_tile(tile_data: bytes, bpp: int) -> list[int]:
    """Decode one SNES planar 8x8 tile into grayscale palette indices."""
    pixels = [0] * 64
    for row in range(8):
        for plane in range(bpp):
            plane_row = row + (plane // 2) * 16 + (8 if plane % 2 else 0)
            value = tile_data[plane_row]
            for col in range(8):
                pixels[row * 8 + col] |= ((value >> (7 - col)) & 1) << plane
    return pixels


def decode_gb2bpp_tile(tile_data: bytes) -> list[int]:
    """Decode one Game Boy 2BPP 8x8 tile."""
    pixels = [0] * 64
    for row in range(8):
        low = tile_data[row * 2]
        high = tile_data[row * 2 + 1]
        for col in range(8):
            bit = 7 - col
            pixels[row * 8 + col] = ((high >> bit) & 1) << 1 | ((low >> bit) & 1)
    return pixels


def render(
    data: bytes,
    bpp: int,
    columns: int,
    tile_format: str,
    tiles_per_glyph: int,
) -> bytes:
    if tile_format == "gb2bpp" and bpp != 2:
        raise ValueError("Game Boy 2BPP format requires --bpp 2")

    tile_size = 16 if tile_format == "gb2bpp" else 8 * bpp
    glyph_size = tile_size * tiles_per_glyph
    glyphs = len(data) // glyph_size
    rows = (glyphs + columns - 1) // columns
    width, height = columns * 8 * tiles_per_glyph, rows * 8
    pixels = bytearray([255] * (width * height))
    max_value = (1 << bpp) - 1

    for glyph in range(glyphs):
        glyph_x = (glyph % columns) * 8 * tiles_per_glyph
        glyph_y = (glyph // columns) * 8
        for part in range(tiles_per_glyph):
            tile = glyph * tiles_per_glyph + part
            tile_data = data[tile * tile_size : tile * tile_size + tile_size]
            if tile_format == "gb2bpp":
                tile_pixels = decode_gb2bpp_tile(tile_data)
            else:
                tile_pixels = decode_snes_tile(tile_data, bpp)
            for index, value in enumerate(tile_pixels):
                row, col = divmod(index, 8)
                x = glyph_x + part * 8 + col
                if tile_format == "gb2bpp":
                    # This game's font uses color 3 as the transparent/background
                    # value, so the preview needs the opposite grayscale direction.
                    shade = value * 255 // max_value
                else:
                    shade = 255 - (value * 255 // max_value)
                pixels[(glyph_y + row) * width + x] = shade

    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
    scanlines = b"".join(b"\x00" + pixels[y * width : (y + 1) * width] for y in range(height))
    png += png_chunk(b"IDAT", zlib.compress(scanlines))
    png += png_chunk(b"IEND", b"")
    return png


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a candidate SNES font/graphics block.")
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=0x40000)
    parser.add_argument("--size", type=lambda value: int(value, 0), default=0x2000)
    parser.add_argument("--bpp", type=int, choices=(2, 4, 8), default=2)
    parser.add_argument("--format", choices=("gb2bpp", "snes"), default="gb2bpp")
    parser.add_argument("--tiles-per-glyph", type=int, choices=(1, 2), default=1)
    parser.add_argument("--columns", type=int, default=32)
    parser.add_argument("--output", type=Path, default=Path("font-preview.png"))
    args = parser.parse_args()

    data = ROM.read_bytes()[args.offset : args.offset + args.size]
    args.output.write_bytes(
        render(data, args.bpp, args.columns, args.format, args.tiles_per_glyph)
    )
    print(args.output)


if __name__ == "__main__":
    main()

from pathlib import Path
import argparse
import struct
import zlib
import binascii


ROM = Path(__file__).parent.parent / "Slap Stick (J).smc"


def decode_tile(tile_data: bytes, bpp: int) -> list[int]:
    """Decode one SNES planar 8x8 tile into grayscale palette indices."""
    pixels = [0] * 64
    for row in range(8):
        for plane in range(bpp):
            plane_row = row + (plane // 2) * 16 + (8 if plane % 2 else 0)
            value = tile_data[plane_row]
            for col in range(8):
                pixels[row * 8 + col] |= ((value >> (7 - col)) & 1) << plane
    return pixels


def render(data: bytes, bpp: int, columns: int) -> bytes:
    tile_size = 8 * bpp
    tiles = len(data) // tile_size
    rows = (tiles + columns - 1) // columns
    width, height = columns * 8, rows * 8
    pixels = bytearray([255] * (width * height))
    max_value = (1 << bpp) - 1

    for tile in range(tiles):
        tile_x = (tile % columns) * 8
        tile_y = (tile // columns) * 8
        tile_data = data[tile * tile_size : tile * tile_size + tile_size]
        for index, value in enumerate(decode_tile(tile_data, bpp)):
            row, col = divmod(index, 8)
            pixels[(tile_y + row) * width + tile_x + col] = 255 - (value * 255 // max_value)

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
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=0x80000)
    parser.add_argument("--size", type=lambda value: int(value, 0), default=0x2000)
    parser.add_argument("--bpp", type=int, choices=(2, 4, 8), default=2)
    parser.add_argument("--columns", type=int, default=32)
    parser.add_argument("--output", type=Path, default=Path("font-preview.png"))
    args = parser.parse_args()

    data = ROM.read_bytes()[args.offset : args.offset + args.size]
    args.output.write_bytes(render(data, args.bpp, args.columns))
    print(args.output)


if __name__ == "__main__":
    main()

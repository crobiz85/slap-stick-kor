from pathlib import Path
import struct
import zlib
import binascii


ROM = Path(__file__).parent.parent / "Slap Stick (J).smc"
OUT = Path(__file__).parent.parent / "font-preview.png"

data = ROM.read_bytes()[0x80000:0x82000]
# Data Crystal describes this block as Game Boy-style 2BPP tiles: 16 bytes
# per 8x8 tile, so the 0x2000-byte block contains 512 tiles.
tiles = len(data) // 16
columns = 32
rows = (tiles + columns - 1) // columns
width, height = columns * 8, rows * 8
pixels = bytearray([255] * (width * height))

for tile in range(tiles):
    tile_x = (tile % columns) * 8
    tile_y = (tile // columns) * 8
    tile_data = data[tile * 16 : tile * 16 + 16]
    for row in range(8):
        # SNES 2BPP tiles store the two bitplanes in separate 8-byte rows.
        plane0 = tile_data[row]
        plane1 = tile_data[8 + row]
        for col in range(8):
            value = ((plane0 >> (7 - col)) & 1)
            value |= (((plane1 >> (7 - col)) & 1) << 1)
            pixels[(tile_y + row) * width + tile_x + col] = 255 - value * 85


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


png = b"\x89PNG\r\n\x1a\n"
png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
scanlines = b"".join(b"\x00" + pixels[y * width : (y + 1) * width] for y in range(height))
png += png_chunk(b"IDAT", zlib.compress(scanlines))
png += png_chunk(b"IEND", b"")
OUT.write_bytes(png)
print(OUT)

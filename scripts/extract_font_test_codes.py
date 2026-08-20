"""Extract character codes from the ROM's built-in font test data.

The test data prints a space byte (20) followed by either a one-byte glyph
code or a little-endian two-byte Japanese code.  It is a useful inventory of
glyphs, but it is not by itself a complete text table for the dialogue
stream.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ROM_PATH = ROOT / "Slap Stick (J).smc"
OUTPUT_PATH = ROOT / "translation" / "font-test-codes.tsv"

TEST_START = 0x01E725
TEST_END = 0x01E8CB
SJIS_LEAD_RANGES = ((0x81, 0x9F), (0xE0, 0xFC))


def is_sjis_lead(value: int) -> bool:
    return any(start <= value <= end for start, end in SJIS_LEAD_RANGES)


def unicode_hint(code_bytes: bytes) -> str:
    if len(code_bytes) != 2:
        return ""
    try:
        # The ROM stores the 16-bit code low byte first, while CP932 expects
        # the usual high-byte/low-byte order.
        return code_bytes[::-1].decode("cp932")
    except UnicodeDecodeError:
        return "?"


def main() -> None:
    rom = ROM_PATH.read_bytes()
    data = rom[TEST_START:TEST_END]
    rows: list[tuple[int, bytes, str]] = []
    index = 0
    while index < len(data):
        if data[index] != 0x20 or index + 1 >= len(data):
            index += 1
            continue
        source = TEST_START + index + 1
        first = data[index + 1]
        if index + 2 < len(data) and is_sjis_lead(data[index + 2]):
            code_bytes = data[index + 1 : index + 3]
            index += 3
        else:
            code_bytes = bytes([first])
            index += 2
        rows.append((source, code_bytes, unicode_hint(code_bytes)))

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Candidate glyph codes printed by the built-in font test.\n")
        handle.write("# source offset\traw code bytes\tcode\twidth\tShift-JIS hint\n")
        seen: set[bytes] = set()
        for source, code_bytes, hint in rows:
            if code_bytes in seen:
                continue
            seen.add(code_bytes)
            code = int.from_bytes(code_bytes, "little")
            handle.write(
                f"0x{source:06X}\t{code_bytes.hex(' ').upper()}\t"
                f"0x{code:04X}\t{len(code_bytes)}\t{hint}\n"
            )

    print(f"occurrences={len(rows)} unique={len({code_bytes for _, code_bytes, _ in rows})}")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()

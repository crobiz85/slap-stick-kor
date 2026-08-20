"""Extract the small pointer-indexed string bank in ROM bank $84.

The table at file offset $04F7C2 contains 16-bit offsets into the same
HiROM bank.  The pointed-to records are terminated by $CC.  This script
keeps the original bytes intact; the game's character table and control
codes still need to be decoded before a translation can be written.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ROM_PATH = ROOT / "Slap Stick (J).smc"
OUTPUT_PATH = ROOT / "translation" / "static-strings.tsv"

# Bank $84 maps file offsets $040000-$04FFFF.  The pointer list begins at
# $04F7C2; the two bytes immediately before it belong to another table.
POINTER_START = 0x04F7C2
POINTER_END = 0x04F832  # inclusive of the pointer at $04F830
STRING_START = 0x04F832
STRING_END = 0x04FA20
MAX_RECORD_LENGTH = 0x100


def placeholder(payload: bytes) -> str:
    """Render printable bytes while making control/high bytes visible."""
    return "".join(
        chr(value) if 0x20 <= value <= 0x7E else f"<{value:02X}>"
        for value in payload
    )


def read_pointers(rom: bytes) -> list[tuple[int, int]]:
    """Read valid, monotonic pointers from the configured pointer table."""
    pointers: list[tuple[int, int]] = []
    previous = STRING_START - 1
    for source in range(POINTER_START, POINTER_END, 2):
        pointer = rom[source] | (rom[source + 1] << 8)
        target = 0x040000 + pointer
        if not STRING_START <= target < STRING_END:
            continue
        if target < previous:
            raise ValueError(
                f"pointer table is not monotonic at 0x{source:06X}: "
                f"0x{target:06X} follows 0x{previous:06X}"
            )
        pointers.append((source, target))
        previous = target
    return pointers


def read_record(rom: bytes, target: int) -> tuple[bytes, int]:
    """Return payload and its $CC terminator offset."""
    terminator = rom.find(b"\xCC", target, min(target + MAX_RECORD_LENGTH, STRING_END))
    if terminator < 0:
        raise ValueError(f"no CC terminator found for target 0x{target:06X}")
    return rom[target:terminator], terminator


def main() -> None:
    rom = ROM_PATH.read_bytes()
    pointers = read_pointers(rom)
    rows: list[tuple[int, int, bytes]] = []
    for source, target in pointers:
        payload, _terminator = read_record(rom, target)
        rows.append((source, target, payload))

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Pointer-indexed encoded strings from file 0x04F832-0x04FA1F.\n")
        handle.write("# pointer offset\ttarget offset\tlength\traw bytes\tplaceholder rendering\n")
        for source, target, payload in rows:
            handle.write(
                f"0x{source:06X}\t0x{target:06X}\t{len(payload):04X}\t"
                f"{payload.hex(' ').upper()}\t{placeholder(payload)}\n"
            )

    print(f"pointers={len(pointers)} strings={len(rows)}")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()

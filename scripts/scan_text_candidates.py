from pathlib import Path


ROM = Path(__file__).parent.parent / "Slap Stick (J).smc"
OUT = Path(__file__).parent.parent / "translation" / "text-candidates.txt"

# Data Crystal identifies these as script/string-template pages. This first
# pass deliberately preserves encoded bytes; it is not a translation dump yet.
RANGES = [
    (0x18000, 0x28000),
    (0x28000, 0x2E9AA),
    (0x48000, 0x50000),
    (0x58000, 0x60000),
    (0x68000, 0x70000),
    (0x78000, 0x80000),
    (0x88000, 0x90000),
    (0x98000, 0xA0000),
]


def is_text_like(value: int) -> bool:
    # The game uses a custom character table. At this stage we only exclude
    # common control bytes and filler; decoding happens after table discovery.
    return 0x20 <= value <= 0xEF


def render(values: bytes) -> str:
    return "".join(chr(value) if 0x20 <= value <= 0x7E else f"<{value:02X}>" for value in values)


rom = ROM.read_bytes()
found: list[tuple[int, bytes]] = []

for start, end in RANGES:
    cursor = start
    while cursor < end:
        while cursor < end and not is_text_like(rom[cursor]):
            cursor += 1
        run_start = cursor
        while cursor < end and is_text_like(rom[cursor]):
            cursor += 1
        run = rom[run_start:cursor]
        if len(run) >= 10 and len(set(run)) >= 4:
            found.append((run_start, run))

with OUT.open("w", encoding="utf-8", newline="\n") as handle:
    handle.write("# Encoded text candidates; custom table is not applied yet.\n")
    handle.write(f"# Candidates: {len(found)}\n\n")
    for offset, values in found:
        handle.write(f"0x{offset:06X}\t{len(values):04X}\t{values.hex(' ').upper()}\t{render(values)}\n")

print(f"wrote {len(found)} candidates to {OUT}")

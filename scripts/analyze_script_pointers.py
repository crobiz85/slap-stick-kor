"""Report Robotrek/Slap Stick string references and CC-terminated payloads.

This is intentionally an analysis tool, not an inserter.  The game uses a
custom text stream, so the output preserves bytes until the character table
and control-code meanings are verified.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ROM_PATH = ROOT / "Slap Stick (J).smc"
POINTER_OUT = ROOT / "translation" / "pointer-report.tsv"
BLOCK_OUT = ROOT / "translation" / "text-blocks-raw.tsv"
ANCHORED_OUT = ROOT / "translation" / "anchored-text.tsv"

ROM = ROM_PATH.read_bytes()
RANGES = [
    (0x18000, 0x2FF66),
    (0x48000, 0x50000),
    (0x58000, 0x60000),
    (0x68000, 0x70000),
    (0x78000, 0x80000),
    (0x88000, 0x8F51E),
    (0x98000, 0x9F478),
]


def in_ranges(offset: int) -> bool:
    return any(start <= offset < end for start, end in RANGES)


def hirom_offset(bank: int, address: int) -> int | None:
    """Map the game's $80-$BF HiROM mirror to a file offset."""
    if 0x80 <= bank <= 0xBF:
        offset = (bank - 0x80) * 0x10000 + address
        return offset if offset < len(ROM) else None
    if 0xC0 <= bank <= 0xFF:
        offset = (bank - 0xC0) * 0x10000 + address
        return offset if offset < len(ROM) else None
    return None


def render(values: bytes) -> str:
    return "".join(
        chr(value) if 0x20 <= value <= 0x7E else f"<{value:02X}>"
        for value in values
    )


def pointer_rows() -> list[tuple[int, int, int, int, bytes]]:
    rows = []
    for source in range(len(ROM) - 4):
        if ROM[source] != 0xCF or ROM[source + 4] != 0xCC:
            continue
        address = ROM[source + 1] | (ROM[source + 2] << 8)
        bank = ROM[source + 3]
        target = hirom_offset(bank, address)
        if target is not None:
            rows.append((source, bank, address, target, ROM[target : target + 64]))
    return rows


def anchored_text(rows: list[tuple[int, int, int, int, bytes]]) -> list[tuple[int, int, bytes]]:
    """Return unique pointer targets whose next CC closes a text-like stream."""
    found: list[tuple[int, int, bytes]] = []
    seen: set[int] = set()
    for source, _bank, _address, target, _preview in rows:
        if target in seen:
            continue
        terminator = ROM.find(b"\xCC", target, min(target + 0x100, len(ROM)))
        if terminator < 0:
            continue
        payload = ROM[target:terminator]
        textish = sum(
            value in (0x0A, 0x0D, 0x1F) or 0x20 <= value <= 0xBF
            for value in payload
        )
        if len(payload) >= 8 and textish / len(payload) >= 0.72:
            found.append((source, target, payload))
            seen.add(target)
    return found


def cc_blocks() -> list[tuple[int, bytes, str]]:
    """Find likely payloads immediately preceding CC in known script pages."""
    blocks = []
    for start, end in RANGES:
        cursor = start
        while cursor < end:
            terminator = ROM.find(b"\xCC", cursor, end)
            if terminator < 0:
                break
            # A double zero is the most reliable record boundary observed in
            # these pages.  Keep the candidate bounded so code tables do not
            # swallow an entire bank.
            boundary = max(start, terminator - 0x100)
            for marker in (b"\x00\x00", b"\xCC"):
                found = ROM.rfind(marker, boundary, terminator)
                if found >= boundary:
                    boundary = found + len(marker)
            payload = ROM[boundary:terminator]
            textish = sum(
                value in (0x0A, 0x0D, 0x1F) or 0x20 <= value <= 0xBF
                for value in payload
            )
            if len(payload) >= 10 and textish / len(payload) >= 0.72:
                blocks.append((boundary, payload, "CC"))
            cursor = terminator + 1
    return blocks


rows = pointer_rows()
with POINTER_OUT.open("w", encoding="utf-8", newline="\n") as handle:
    handle.write("# source\tSNES target\tfile target\tbytes at target\n")
    for source, bank, address, target, preview in rows:
        handle.write(
            f"0x{source:06X}\t${bank:02X}:{address:04X}\t"
            f"0x{target:06X}\t{preview.hex(' ').upper()}\n"
        )

blocks = cc_blocks()
with BLOCK_OUT.open("w", encoding="utf-8", newline="\n") as handle:
    handle.write("# Likely CC-terminated encoded text payloads; no TBL applied.\n")
    handle.write("# offset\tlength\traw bytes\tplaceholder rendering\n")
    for offset, payload, terminator in blocks:
        handle.write(
            f"0x{offset:06X}\t{len(payload):04X}\t"
            f"{payload.hex(' ').upper()}\t{render(payload)}\n"
        )

anchored = anchored_text(rows)
with ANCHORED_OUT.open("w", encoding="utf-8", newline="\n") as handle:
    handle.write("# Pointer-anchored encoded text; custom TBL/control codes are not applied.\n")
    handle.write("# reference source\ttext file offset\tlength\traw bytes\tplaceholder rendering\n")
    for source, target, payload in anchored:
        handle.write(
            f"0x{source:06X}\t0x{target:06X}\t{len(payload):04X}\t"
            f"{payload.hex(' ').upper()}\t{render(payload)}\n"
        )

print(f"pointers={len(rows)} anchored={len(anchored)} blocks={len(blocks)}")
print(POINTER_OUT)
print(ANCHORED_OUT)
print(BLOCK_OUT)

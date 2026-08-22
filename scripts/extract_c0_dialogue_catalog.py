"""Extract C0-terminated main-dialogue records into a stable review catalog.

The previous catalog only followed ``CC``-terminated menu/template blocks.  The
story engine also stores many running dialogue records as ``C0``-terminated
streams, so those records were never offered for translation.  This extractor
keeps that second family separate: IDs use the ROM offset and therefore do not
change when the catalog is regenerated.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re

from decode_japanese_strings import decode


ROOT = Path(__file__).resolve().parent.parent
ROM_PATH = ROOT / "Slap Stick (J).smc"
OUTPUT_PATH = ROOT / "translation" / "c0-dialogue-catalog.tsv"

# The verified script pages contain both menu/template ``CC`` streams and
# event dialogue closed with ``C0``.  Restricting the scan avoids font and
# program banks, which can coincidentally contain byte C0.
SCRIPT_RANGES = (
    (0x58000, 0x60000),
    (0x68000, 0x70000),
    (0x78000, 0x80000),
    (0x88000, 0x8F51E),
    (0x98000, 0x9F478),
)

JAPANESE = re.compile(r"[ぁ-ゟァ-ヿ一-龯]")
UNKNOWN = re.compile(r"\[(?:BYTE|CMD):")

# These controls begin a visible dialogue page or a deliberate continuation.
# The final scored candidate is chosen rather than blindly trusting the last
# marker: byte values also occur in pointer tables near dialogue records.
START_MARKERS = frozenset((0xD0, 0xD7, 0xD8, 0xDA))


def candidate_score(payload: bytes) -> tuple[int, int, int]:
    """Return a sort key favouring readable Japanese over binary lookalikes."""
    text = decode(payload)
    japanese = len(JAPANESE.findall(text))
    unknown = len(UNKNOWN.findall(text))
    controls = text.count("[") - unknown
    # Long strings are useful, but only after their decoding looks like text.
    score = japanese * 12 - unknown * 15 - controls * 2 + min(len(payload), 0x180) // 8
    return score, japanese, unknown


def find_record_start(rom: bytes, record_floor: int, terminator: int) -> int | None:
    """Select the best nearby visible-text marker for one C0 terminator."""
    window_start = max(record_floor, terminator - 0x300)
    candidates = []
    for offset in range(window_start, terminator):
        if rom[offset] not in START_MARKERS:
            continue
        payload = rom[offset:terminator]
        score, japanese, unknown = candidate_score(payload)
        # More than two unknown bytes almost always means the scan started in
        # a nearby pointer/setup table.  Real dialogue uses named controls;
        # a small allowance remains for as-yet-unclassified inline effects.
        if japanese >= 5 and unknown <= 2:
            candidates.append((score, japanese, -unknown, -len(payload), offset))
    if not candidates:
        return None
    return max(candidates)[-1]


def records(rom: bytes) -> list[tuple[int, bytes]]:
    """Return non-overlapping, readable C0 dialogue records in script pages."""
    found: dict[tuple[int, int], bytes] = {}
    for range_start, range_end in SCRIPT_RANGES:
        record_floor = range_start
        for terminator in range(range_start, range_end):
            if rom[terminator] != 0xC0:
                continue
            # C0 closes the current record.  Never let a later record borrow
            # its predecessor merely because both happen to contain D7.
            start = find_record_start(rom, record_floor, terminator)
            if start is None:
                record_floor = terminator + 1
                continue
            payload = rom[start:terminator]
            found[(start, terminator)] = payload
            record_floor = terminator + 1

    # A shorter continuation may end at the same C0.  Keep only the longest
    # readable stream for that endpoint, then order the stable physical IDs.
    by_end: dict[int, tuple[int, bytes]] = {}
    for (start, end), payload in found.items():
        existing = by_end.get(end)
        if existing is None or len(payload) > len(existing[1]):
            by_end[end] = (start, payload)
    return sorted(by_end.values(), key=lambda row: row[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract C0-terminated Slap Stick dialogue records.")
    parser.add_argument("--rom", type=Path, default=ROM_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    rows = records(args.rom.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# C0-terminated main-dialogue review catalog; generated from the verified Japanese ROM.\n")
        handle.write("# id\tfile offset\tlength\traw bytes\tJapanese\tKorean translation\tstatus\n")
        for offset, payload in rows:
            entry_id = f"C0-{offset:06X}"
            japanese = decode(payload).replace("\t", " ")
            handle.write(
                f"{entry_id}\t0x{offset:06X}\t{len(payload):04X}\t"
                f"{payload.hex(' ').upper()}\t{japanese}\t\tpending\n"
            )

    print(f"catalogued={len(rows)}")
    print(args.output)


if __name__ == "__main__":
    main()

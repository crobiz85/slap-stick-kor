"""Build a conservative relocation worksheet for Korean draft strings.

The current Korean drafts are longer than their inline Japanese records.  This
tool records the exact source slot, its CC terminator, nearby capacity, and
pointer-like byte references.  It never changes the ROM and does not claim
that a heuristic reference is a real game pointer.
"""

from pathlib import Path

from encode_translation_drafts import encode_text, read_glyph_map


ROOT = Path(__file__).resolve().parent.parent
ROM_PATH = ROOT / "Slap Stick (J).smc"
SCRIPT_PATH = ROOT / "translation" / "script.tsv"
OUTPUT_PATH = ROOT / "translation" / "relocation-plan.tsv"


def read_draft_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in SCRIPT_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 7 or columns[6] != "draft-ko" or not columns[5]:
            continue
        rows.append(
            {
                "id": columns[0],
                "offset": int(columns[1], 16),
                "length": int(columns[2], 16),
                "raw": bytes.fromhex(columns[3]),
                "korean": columns[5],
            }
        )
    return sorted(rows, key=lambda row: int(row["offset"]))


def region_for(offset: int) -> str:
    regions = (
        (0x18000, 0x28000, "script-data-18000-27FFF"),
        (0x28000, 0x2E9AA, "script-table-28000-2E999"),
        (0x2E9AA, 0x30000, "script-code-2E9AA-2FFFF"),
        (0x48000, 0x50000, "script-page-48000-4FFFF"),
        (0x58000, 0x60000, "script-page-58000-5FFFF"),
        (0x68000, 0x70000, "script-page-68000-6FFFF"),
        (0x78000, 0x80000, "script-page-78000-7FFFF"),
        (0x88000, 0x90000, "script-page-88000-8FFFF"),
        (0x98000, 0xA0000, "script-page-98000-9FFFF"),
    )
    for start, end, name in regions:
        if start <= offset < end:
            return name
    return "outside-known-script-ranges"


def find_all(data: bytes, needle: bytes) -> list[int]:
    return [
        index
        for index in range(len(data) - len(needle) + 1)
        if data[index : index + len(needle)] == needle
    ]


def pointer_summary(rom: bytes, offset: int) -> tuple[int, int, int, str]:
    bank = 0x80 + (offset >> 16)
    address = offset & 0xFFFF
    mirrored = bytes((address & 0xFF, address >> 8, bank))
    mirrored_alt = bytes((address & 0xFF, address >> 8, 0xC0 + (offset >> 16)))
    raw_refs = find_all(rom, mirrored) + find_all(rom, mirrored_alt)
    cf_refs = [
        start - 1
        for start in sorted(set(raw_refs))
        if start >= 1 and rom[start - 1] == 0xCF
    ]
    word = bytes((address & 0xFF, address >> 8))
    word_refs = find_all(rom, word)
    sample = ",".join(f"0x{value:06X}" for value in cf_refs[:4]) or "-"
    return len(set(raw_refs)), len(cf_refs), len(word_refs), sample


def first_cc_after(rom: bytes, start: int, limit: int = 0x100) -> int | None:
    end = min(len(rom), start + limit)
    found = rom.find(b"\xCC", start, end)
    return found if found >= 0 else None


def main() -> None:
    rom = ROM_PATH.read_bytes()
    glyphs = read_glyph_map()
    rows = read_draft_rows()
    next_offsets = {
        row["id"]: rows[index + 1]["offset"] if index + 1 < len(rows) else None
        for index, row in enumerate(rows)
    }

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Conservative worksheet; heuristic references require emulator/code verification.\n")
        handle.write(
            "# id\toriginal offset\toriginal length\tencoded length\toverflow bytes\tfits\t"
            "next CC offset\tbytes after segment before next CC\tnext draft offset\tregion\t"
            "raw 3-byte refs\tCF pointer refs\t16-bit word refs\tCF ref samples\taction\n"
        )
        for row in rows:
            entry_id = str(row["id"])
            offset = int(row["offset"])
            length = int(row["length"])
            korean = str(row["korean"])
            try:
                encoded_length = len(encode_text(korean, glyphs))
                error = ""
            except ValueError as exc:
                encoded_length = 0
                error = str(exc)

            terminator = first_cc_after(rom, offset + length)
            if terminator is None:
                terminator_text = "-"
                gap_text = "-"
            else:
                terminator_text = f"0x{terminator:06X}"
                gap_text = str(max(0, terminator - (offset + length)))

            next_offset = next_offsets[entry_id]
            next_text = f"0x{next_offset:06X}" if next_offset is not None else "-"
            raw_refs, cf_refs, word_refs, samples = pointer_summary(rom, offset)
            fits = "yes" if not error and encoded_length <= length else "no" if not error else "error"
            overflow = max(0, encoded_length - length) if not error else 0
            action = "relocate-and-update-container-reference"
            handle.write(
                f"{entry_id}\t0x{offset:06X}\t{length:04X}\t{encoded_length:04X}\t"
                f"{overflow:04X}\t{fits}\t{terminator_text}\t{gap_text}\t{next_text}\t"
                f"{region_for(offset)}\t{raw_refs}\t{cf_refs}\t{word_refs}\t{samples}\t{action}"
                f"{(' [' + error + ']') if error else ''}\n"
            )

    print(f"planned={len(rows)}")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()

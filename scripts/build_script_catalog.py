"""Build a reviewable Japanese script catalog from decoded candidate blocks.

This deliberately keeps only segments that look like dialogue and marks all
of them as review.  It is an editing worksheet, not yet a patch source.
"""

from pathlib import Path
import re

from decode_japanese_strings import decode


ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "translation" / "text-blocks-raw.tsv"
OUTPUT_PATH = ROOT / "translation" / "script.tsv"

JAPANESE = re.compile(r"[ぁ-ゟァ-ヿ一-龯]")


def read_rows() -> list[tuple[int, bytes]]:
    rows = []
    for line in INPUT_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 3:
            continue
        raw = bytes.fromhex(columns[2])
        rows.append((int(columns[0], 16), raw))
    return rows


def split_segments(payload: bytes) -> list[tuple[int, bytes]]:
    """Split at the observed D7 dialogue-state marker."""
    starts = [index for index, value in enumerate(payload) if value == 0xD7]
    if not starts:
        return [(0, payload)]
    segments = []
    if starts[0] > 0:
        segments.append((0, payload[: starts[0]]))
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(payload)
        segments.append((start, payload[start:end]))
    return segments


def is_dialogue(text: str) -> bool:
    japanese_count = len(JAPANESE.findall(text))
    unknown_count = text.count("[BYTE:") + text.count("[CMD:")
    return japanese_count >= 3 and unknown_count <= 5


def main() -> None:
    catalog = []
    seen: set[tuple[int, int]] = set()
    next_id = 1

    for block_offset, payload in read_rows():
        for relative, segment in split_segments(payload):
            text = decode(segment).replace("\t", " ")
            absolute = block_offset + relative
            key = (absolute, len(segment))
            if key in seen or not is_dialogue(text):
                continue
            seen.add(key)
            catalog.append((next_id, absolute, len(segment), segment, text))
            next_id += 1

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Review worksheet; Japanese source is decoded, Korean column is intentionally blank.\n")
        handle.write("# id\tfile offset\tlength\traw bytes\tJapanese\tKorean translation\tstatus\n")
        for entry_id, offset, length, raw, japanese in catalog:
            handle.write(
                f"{entry_id:04d}\t0x{offset:06X}\t{length:04X}\t"
                f"{raw.hex(' ').upper()}\t{japanese}\t\treview\n"
            )

    print(f"catalogued={len(catalog)}")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()

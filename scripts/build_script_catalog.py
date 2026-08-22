"""Build a reviewable Japanese script catalog from decoded candidate blocks.

This deliberately keeps only segments that look like dialogue.  Korean drafts
are kept in a separate TSV overlay so regenerating the catalog never erases
manual translation work.  It is an editing worksheet, not yet a patch source.
"""

from pathlib import Path
import re

from decode_japanese_strings import decode


ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "translation" / "text-blocks-raw.tsv"
OUTPUT_PATH = ROOT / "translation" / "script.tsv"
DRAFT_PATH = ROOT / "translation" / "korean-draft.tsv"

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


def read_drafts() -> dict[str, tuple[str, str]]:
    """Read optional Korean drafts keyed by the stable catalog id."""
    if not DRAFT_PATH.exists():
        return {}

    drafts = {}
    for line in DRAFT_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t", 2)
        if len(columns) < 3:
            continue
        entry_id, korean, status = (column.strip() for column in columns)
        drafts[entry_id] = (korean, status or "draft-ko")
    return drafts


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
    drafts = read_drafts()

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
        handle.write("# Review worksheet; Korean drafts are overlaid from translation/korean-draft.tsv.\n")
        handle.write("# id\tfile offset\tlength\traw bytes\tJapanese\tKorean translation\tstatus\n")
        for entry_id, offset, length, raw, japanese in catalog:
            korean, status = drafts.get(f"{entry_id:04d}", ("", "review"))
            handle.write(
                f"{entry_id:04d}\t0x{offset:06X}\t{length:04X}\t"
                f"{raw.hex(' ').upper()}\t{japanese}\t{korean}\t{status}\n"
            )

    print(f"catalogued={len(catalog)}")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()

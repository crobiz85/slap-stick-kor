"""Build a review sheet for the C0 dialogue catalog.

The review sheet is deliberately independent from the ROM builder.  It tracks
translation priority, exact duplicates, and records containing engine controls
so the manuscript can be completed before any relocation or font work.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "translation" / "c0-dialogue-catalog.tsv"
TRANSLATED = ROOT / "translation" / "korean-c0-dialogue.tsv"
MANUSCRIPT_BATCH = ROOT / "translation" / "korean-c0-manuscript-early.tsv"
OUTPUT = ROOT / "translation" / "c0-dialogue-review.tsv"


def load_rows(path: Path) -> list[dict[str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 5:
            continue
        rows.append({"id": cols[0], "offset": cols[1], "length": cols[2], "raw": cols[3], "jp": cols[4].rstrip()})
    return rows


def normalized(text: str) -> str:
    text = re.sub(r"\[[^]]+\]", "", text)
    return re.sub(r"\s+", "", text).replace("˳", "")


def classify(row: dict[str, str]) -> tuple[str, str]:
    offset = int(row["offset"], 16)
    length = int(row["length"], 16)
    jp = row["jp"]
    raw = row["raw"]
    controls = set(re.findall(r"\[([A-Z]+)(?::[^]]+)?\]", jp))
    if 0x5A3A8 <= offset < 0x5A550:
        return "opening", "P1"
    if any(token in raw for token in ("F7", "F4", "F0", "FF")) and "[DFT]" not in jp:
        return "engine-data", "P3"
    if offset < 0x60000:
        if length >= 0x80 or "E2" in controls or "NAM" in controls or "TER" in controls:
            return "early-story", "P1"
        return "early-town", "P2"
    if offset >= 0x8D000 and (length >= 0x80 or "E2" in controls or "NAM" in controls):
        return "late-story", "P1"
    if "CLR" in controls and length < 0x20:
        return "static-short", "P3"
    if length >= 0x80 or "FIN" in controls or "TER" in controls:
        return "event-dialogue", "P2"
    return "npc-dialogue", "P3"


def main() -> None:
    rows = load_rows(CATALOG)
    translated = {row["id"] for row in load_rows(TRANSLATED)}
    translated.update(
        line.split("\t", 1)[0]
        for line in MANUSCRIPT_BATCH.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    groups: defaultdict[str, list[str]] = defaultdict(list)
    for row in rows:
        groups[normalized(row["jp"])].append(row["id"])
    duplicate_of = {}
    for ids in groups.values():
        if len(ids) > 1:
            for entry_id in ids[1:]:
                duplicate_of[entry_id] = ids[0]

    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# C0 translation review sheet generated from the verified catalog.\n")
        handle.write("# id\toffset\tslot length\tcategory\tpriority\tduplicate of\ttranslation\tJapanese\n")
        for row in rows:
            category, priority = classify(row)
            status = "translated" if row["id"] in translated else "pending"
            handle.write(
                f"{row['id']}\t{row['offset']}\t0x{int(row['length'], 16):04X}\t"
                f"{category}\t{priority}\t{duplicate_of.get(row['id'], '')}\t{status}\t{row['jp']}\n"
            )

    counts = defaultdict(int)
    for row in rows:
        category, priority = classify(row)
        counts[(category, priority)] += 1
    print(f"rows={len(rows)} translated={len(translated & {row['id'] for row in rows})}")
    for key, count in sorted(counts.items()):
        print(f"{key[0]} {key[1]} {count}")
    print(OUTPUT)


if __name__ == "__main__":
    main()

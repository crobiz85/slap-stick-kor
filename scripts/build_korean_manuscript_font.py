"""Build an expanded Korean font map for the reviewed C0 manuscript.

The first preview conservatively used only glyph slots that were unused by the
entire Japanese ROM.  That leaves many available slots stranded: once a C0
record is translated, its old Japanese glyph references no longer need to be
preserved.  This builder reclaims only glyph codes used exclusively by records
that the inline dialogue build can actually replace, then allocates the most
frequent additional Hangul syllables into those reclaimed slots.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_korean_font import (  # noqa: E402
    DEFAULT_MAP_PATH,
    FONT_LEAD_BYTE,
    SECOND_FONT_LEAD_BYTE,
    THIRD_FONT_LEAD_BYTE,
    HANGUL_START,
    HANGUL_END,
    THIRD_FONT_BANK_OFFSET,
    SECOND_FONT_BANK_OFFSET,
    FONT_BANK_OFFSET,
    GLYPH_BYTES,
    encode_glyph,
    find_default_font,
    read_existing_codes,
    read_used_kanji_codes,
    render_mask,
    write_map,
    write_preview,
)
from encode_translation_drafts import encode_text  # noqa: E402
from build_korean_dialogue_inline import (  # noqa: E402
    read_catalog,
    read_translations,
)


DEFAULT_OUTPUT_MAP = ROOT / "translation" / "korean-glyph-map-manuscript.tsv"
DEFAULT_OUTPUT_PREVIEW = ROOT / "build" / "korean-font-manuscript-preview.png"
DEFAULT_REPORT = ROOT / "build" / "korean-manuscript-font-report.json"
MANUSCRIPT_CAP = 738


def hangul(text: str) -> list[str]:
    return [character for character in text if HANGUL_START <= ord(character) <= HANGUL_END]


def catalog_usage(catalog: dict[str, dict], ids: set[str]) -> dict[int, set[int]]:
    usage = {FONT_LEAD_BYTE: set(), SECOND_FONT_LEAD_BYTE: set(), THIRD_FONT_LEAD_BYTE: set()}
    for entry_id in ids:
        raw = catalog[entry_id]["raw"]
        for index in range(len(raw) - 1):
            if raw[index] in usage:
                usage[raw[index]].add(raw[index + 1])
    return usage


def available_codes(used: dict[int, set[int]], released: dict[int, set[int]]) -> list[tuple[int, int]]:
    return [
        (lead, value)
        for lead in (FONT_LEAD_BYTE, SECOND_FONT_LEAD_BYTE, THIRD_FONT_LEAD_BYTE)
        for value in range(0x100)
        if value not in (used[lead] - released[lead])
    ]


def selected_rows(candidate: set[str], translations: dict[str, dict], catalog: dict[str, dict]) -> set[str]:
    dummy_glyphs = {character: bytes((0x80, 0x00)) for character in candidate}
    selected = set()
    for entry_id, row in translations.items():
        if row["category"] == "cold-boot-opening":
            continue
        cat = catalog.get(entry_id)
        if cat is None or cat["offset"] != row["offset"] or cat["length"] != row["length"]:
            continue
        try:
            encoded = encode_text(row["text"], dummy_glyphs)
        except ValueError:
            continue
        if len(encoded) <= cat["length"] and cat["raw"]:
            selected.add(entry_id)
    return selected


def choose_characters(
    translations: dict[str, dict],
    existing_codes: dict[str, tuple[int, int]],
    used: dict[int, set[int]],
    catalog: dict[str, dict],
) -> tuple[list[str], set[str], dict[int, set[int]], list[tuple[int, int]]]:
    counts = Counter()
    for row in translations.values():
        counts.update(hangul(row["text"]))
    existing = set(existing_codes)
    all_characters = existing | set(counts)
    ranked_missing = sorted(all_characters - existing, key=lambda character: (-counts[character], character))
    # Bootstrap from a broad, frequency-ranked set.  Starting with only the
    # old map creates a circular fixed point: no new glyph can unlock a row,
    # so no translated row can release its old Japanese slot.
    candidate = existing | set(ranked_missing[: max(0, MANUSCRIPT_CAP - len(existing))])

    for _ in range(12):
        selected = selected_rows(candidate, translations, catalog)
        all_c0 = catalog_usage(catalog, set(catalog))
        selected_c0 = catalog_usage(catalog, selected)
        unselected_c0 = {lead: all_c0[lead] - selected_c0[lead] for lead in all_c0}
        outside = {lead: used[lead] - all_c0[lead] for lead in used}
        released = {
            lead: selected_c0[lead] - unselected_c0[lead] - outside[lead]
            for lead in used
        }
        slots = available_codes(used, released)
        capacity = min(len(slots), MANUSCRIPT_CAP)
        if len(candidate) >= capacity:
            candidate = set(sorted(candidate, key=lambda character: (-counts[character], character))[:capacity])
            break
        ranked = sorted(all_characters - candidate, key=lambda character: (-counts[character], character))
        candidate.update(ranked[: capacity - len(candidate)])

    selected = selected_rows(candidate, translations, catalog)
    all_c0 = catalog_usage(catalog, set(catalog))
    selected_c0 = catalog_usage(catalog, selected)
    unselected_c0 = {lead: all_c0[lead] - selected_c0[lead] for lead in all_c0}
    outside = {lead: used[lead] - all_c0[lead] for lead in used}
    released = {
        lead: selected_c0[lead] - unselected_c0[lead] - outside[lead]
        for lead in used
    }
    slots = available_codes(used, released)
    if len(candidate) > len(slots):
        candidate = set(sorted(candidate, key=lambda character: (-counts[character], character))[: len(slots)])
        selected = selected_rows(candidate, translations, catalog)
    return sorted(candidate), selected, released, slots


def allocate(characters: list[str], previous: dict[str, tuple[int, int]], slots: list[tuple[int, int]]) -> dict[str, tuple[int, int]]:
    available = set(slots)
    assigned = {}
    for character in characters:
        code = previous.get(character)
        if code in available and code not in assigned.values():
            assigned[character] = code
    free = (slot for slot in slots if slot not in assigned.values())
    for character in characters:
        if character not in assigned:
            assigned[character] = next(free)
    return assigned


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reclaimed-slot Korean font for the C0 manuscript.")
    parser.add_argument("--font", type=Path, default=None)
    parser.add_argument("--font-size", type=int, default=12)
    parser.add_argument("--output-map", type=Path, default=DEFAULT_OUTPUT_MAP)
    parser.add_argument("--output-preview", type=Path, default=DEFAULT_OUTPUT_PREVIEW)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--plan", type=Path, help="use the exact selected IDs from a batch-plan JSON")
    parser.add_argument(
        "--previous-map",
        type=Path,
        default=DEFAULT_MAP_PATH,
        help="preserve code assignments from an earlier generated glyph map",
    )
    args = parser.parse_args()

    catalog = read_catalog()
    translations = read_translations()
    previous = read_existing_codes(args.previous_map.resolve())
    used = {
        FONT_LEAD_BYTE: read_used_kanji_codes(FONT_LEAD_BYTE),
        SECOND_FONT_LEAD_BYTE: read_used_kanji_codes(SECOND_FONT_LEAD_BYTE),
        THIRD_FONT_LEAD_BYTE: read_used_kanji_codes(THIRD_FONT_LEAD_BYTE),
    }
    if args.plan:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        selected = set(plan["selected_ids"])
        missing_ids = sorted(selected - set(translations))
        if missing_ids:
            raise ValueError(f"plan IDs are missing from manuscript: {', '.join(missing_ids)}")
        released = catalog_usage(catalog, selected)
        all_c0 = catalog_usage(catalog, set(catalog))
        unselected_c0 = {lead: all_c0[lead] - released[lead] for lead in released}
        outside = {lead: used[lead] - all_c0[lead] for lead in used}
        released = {
            lead: released[lead] - unselected_c0[lead] - outside[lead]
            for lead in used
        }
        slots = available_codes(used, released)
        characters = set(previous)
        for entry_id in selected:
            characters.update(hangul(translations[entry_id]["text"]))
        characters = sorted(characters)
    else:
        characters, selected, released, slots = choose_characters(translations, previous, used, catalog)
    if len(characters) > len(slots):
        raise ValueError(f"Need {len(characters)} glyph slots but only {len(slots)} are available")

    font_path = args.font or find_default_font()
    from PIL import ImageFont

    font = ImageFont.truetype(str(font_path), args.font_size)
    codes = allocate(characters, previous, slots)
    masks = {character: render_mask(character, font, args.font_size) for character in characters}
    tiles = {character: encode_glyph(masks[character]) for character in characters}
    write_map(characters, codes, tiles, args.output_map)
    write_preview(characters, masks, codes, args.output_preview, 8)
    report = {
        "glyph_count": len(characters),
        "available_slots": len(slots),
        "selected_rows": len(selected),
        "released_slots": sum(len(values) for values in released.values()),
        "released_by_bank": {f"0x{lead:02X}": len(values) for lead, values in released.items()},
        "output_map": str(args.output_map),
        "output_preview": str(args.output_preview),
        "selected_ids": sorted(selected, key=lambda entry_id: catalog[entry_id]["offset"]),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("glyph_count", "available_slots", "selected_rows", "released_slots")}, ensure_ascii=False))
    print(args.output_map)
    print(args.report)


if __name__ == "__main__":
    main()

"""Plan a larger, safe C0 dialogue batch for the Korean font.

The original ROM has a fixed set of Japanese 16x16 glyph slots.  A dialogue
record that is replaced no longer needs the Japanese glyphs used only by that
record, so those slots can be reclaimed for new Hangul syllables.  This tool
finds a monotonic batch: it starts with rows encodable by the existing font,
then adds rows when the row's own reclaimed slots make its missing syllables
fit.  It never writes a ROM.
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
    read_existing_codes,
    read_used_kanji_codes,
)
from build_korean_dialogue_inline import (  # noqa: E402
    ORIGINAL_ROM,
    read_catalog,
    read_translations,
)
from encode_translation_drafts import encode_text, read_glyph_map  # noqa: E402


DEFAULT_OUTPUT = ROOT / "build" / "korean-dialogue-batch-plan.json"
DEFAULT_IDS = ROOT / "build" / "korean-dialogue-batch-ids.txt"

BANKS = (FONT_LEAD_BYTE, SECOND_FONT_LEAD_BYTE, THIRD_FONT_LEAD_BYTE)


def hangul(text: str) -> set[str]:
    return {character for character in text if HANGUL_START <= ord(character) <= HANGUL_END}


def code_usage(catalog: dict[str, dict], ids: set[str]) -> dict[int, set[int]]:
    usage = {lead: set() for lead in BANKS}
    for entry_id in ids:
        raw = catalog[entry_id]["raw"]
        for index in range(len(raw) - 1):
            lead = raw[index]
            if lead in usage:
                usage[lead].add(raw[index + 1])
    return usage


def released_codes(
    catalog: dict[str, dict], selected: set[str], used: dict[int, set[int]]
) -> dict[int, set[int]]:
    all_usage = code_usage(catalog, set(catalog))
    selected_usage = code_usage(catalog, selected)
    unselected_usage = {
        lead: all_usage[lead] - selected_usage[lead] for lead in BANKS
    }
    outside = {lead: used[lead] - all_usage[lead] for lead in BANKS}
    return {
        lead: selected_usage[lead] - unselected_usage[lead] - outside[lead]
        for lead in BANKS
    }


def released_from_usage(
    all_usage: dict[int, set[int]],
    selected_usage: dict[int, set[int]],
    used: dict[int, set[int]],
) -> dict[int, set[int]]:
    unselected_usage = {
        lead: all_usage[lead] - selected_usage[lead] for lead in BANKS
    }
    outside = {lead: used[lead] - all_usage[lead] for lead in BANKS}
    return {
        lead: selected_usage[lead] - unselected_usage[lead] - outside[lead]
        for lead in BANKS
    }


def available_codes(
    used: dict[int, set[int]], released: dict[int, set[int]]
) -> list[tuple[int, int]]:
    return [
        (lead, value)
        for lead in BANKS
        for value in range(0x100)
        if value not in (used[lead] - released[lead])
    ]


def pointer_refs(data: bytes, target: int) -> list[int]:
    address = target & 0xFFFF
    needle = bytes((0x02, 0x1D, address & 0xFF, address >> 8))
    result = []
    start = 0
    while True:
        found = data.find(needle, start)
        if found < 0:
            return result
        result.append(found)
        start = found + 1


def safe_rows(
    original: bytes, catalog: dict[str, dict], translations: dict[str, dict]
) -> dict[str, dict]:
    rows = {}
    for entry_id, row in translations.items():
        category = row["category"]
        if category == "cold-boot-opening":
            continue
        cat = catalog.get(entry_id)
        if cat is None or cat["offset"] != row["offset"] or cat["length"] != row["length"]:
            continue
        actual = original[cat["offset"] : cat["offset"] + cat["length"]]
        if actual != cat["raw"] or original[cat["offset"] + cat["length"]] != 0xC0:
            continue
        rows[entry_id] = {
            "text": row["text"],
            "category": category,
            "length": cat["length"],
            "raw": cat["raw"],
        }
    return rows


def trial_missing(
    row: dict, glyphs: dict[str, bytes], active: set[str], allow_overlength: bool = False
) -> tuple[set[str], int] | None:
    missing = hangul(row["text"]) - active
    trial = dict(glyphs)
    # ``active`` also contains syllables added by earlier rows in this plan.
    # They are not in the stable map yet, but they are available to later
    # rows once the expanded map is built.
    trial.update({character: b"\x80\x00" for character in active if character not in trial})
    trial.update({character: b"\x80\x00" for character in missing})
    try:
        encoded = encode_text(row["text"], trial)
    except ValueError:
        return None
    if not allow_overlength and len(encoded) > row["length"]:
        return None
    return missing, len(encoded)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan a reclaimed-slot Korean C0 dialogue batch")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ids-output", type=Path, default=DEFAULT_IDS)
    parser.add_argument("--max-rows", type=int, default=180)
    parser.add_argument("--allow-overlength", action="store_true", help="include rows intended for pointer relocation")
    parser.add_argument("--require-pointer", action="store_true", help="only include rows with a verified 02 1D reference")
    parser.add_argument("--exclude-ids", help="comma-separated IDs to leave out of the plan")
    args = parser.parse_args()

    original = ORIGINAL_ROM.read_bytes()
    catalog = read_catalog()
    translations = read_translations()
    glyphs = read_glyph_map(DEFAULT_MAP_PATH)
    existing_codes = read_existing_codes(DEFAULT_MAP_PATH)
    used = {
        FONT_LEAD_BYTE: read_used_kanji_codes(FONT_LEAD_BYTE),
        SECOND_FONT_LEAD_BYTE: read_used_kanji_codes(SECOND_FONT_LEAD_BYTE),
        THIRD_FONT_LEAD_BYTE: read_used_kanji_codes(THIRD_FONT_LEAD_BYTE),
    }
    rows = safe_rows(original, catalog, translations)
    excluded = {
        item.strip() for item in args.exclude_ids.split(",") if item.strip()
    } if args.exclude_ids else set()
    rows = {entry_id: row for entry_id, row in rows.items() if entry_id not in excluded}
    pointers = {
        entry_id: pointer_refs(original, catalog[entry_id]["offset"])
        for entry_id in rows
    }
    all_usage = code_usage(catalog, set(catalog))
    row_usage = {entry_id: code_usage(catalog, {entry_id}) for entry_id in rows}
    active = set(glyphs)
    selected: set[str] = set()
    selected_usage = {lead: set() for lead in BANKS}
    encoded_lengths: dict[str, int] = {}
    missing_by_row: dict[str, set[str]] = {}

    # First retain every row that the current, tested font can already encode.
    for entry_id, row in rows.items():
        result = trial_missing(row, glyphs, active, args.allow_overlength)
        if args.require_pointer and not pointers[entry_id]:
            result = None
        # Keep the already-tested inline set as the seed when planning a
        # relocation batch.  Overlength rows are added only by the iterative
        # pass below, where their pointer route is checked.
        if args.allow_overlength and result is not None:
            encoded_length = result[1]
            if encoded_length > row["length"]:
                result = None
        if result is not None and not result[0]:
            selected.add(entry_id)
            for lead in BANKS:
                selected_usage[lead].update(row_usage[entry_id][lead])
            encoded_lengths[entry_id] = result[1]

    # Add rows one at a time.  A row may pay for its new glyphs with glyph
    # codes that become releasable when that same row is replaced.
    while len(selected) < args.max_rows:
        released = released_from_usage(all_usage, selected_usage, used)
        slots = available_codes(used, released)
        free_slots = len(set(slots) - set(existing_codes.values()))
        candidates = []
        for entry_id, row in rows.items():
            if entry_id in selected:
                continue
            result = trial_missing(row, glyphs, active, args.allow_overlength)
            if args.require_pointer and not pointers[entry_id]:
                continue
            if result is None:
                continue
            missing, encoded_length = result
            after_usage = {
                lead: selected_usage[lead] | row_usage[entry_id][lead]
                for lead in BANKS
            }
            after_released = released_from_usage(all_usage, after_usage, used)
            after_slots = available_codes(used, after_released)
            after_free = len(set(after_slots) - set(existing_codes.values()))
            if len(active | missing) > len(existing_codes) + after_free:
                continue
            # Prefer rows that introduce few glyphs and reclaim many old
            # codes.  The earlier look-ahead encoded every other row for every
            # candidate; that made relocation planning needlessly quadratic.
            next_active = active | missing
            release_gain = sum(len(after_released[lead]) - len(released[lead]) for lead in BANKS)
            score = (release_gain * 20 - len(missing) * 80 - encoded_length / 100)
            candidates.append((score, -len(missing), entry_id, missing, encoded_length, after_free))
        if not candidates:
            break
        _score, _cost, entry_id, missing, encoded_length, _after_free = max(candidates)
        selected.add(entry_id)
        for lead in BANKS:
            selected_usage[lead].update(row_usage[entry_id][lead])
        active.update(missing)
        missing_by_row[entry_id] = missing
        encoded_lengths[entry_id] = encoded_length

    released = released_from_usage(all_usage, selected_usage, used)
    slots = available_codes(used, released)
    free_slots = len(set(slots) - set(existing_codes.values()))
    counts = Counter()
    for entry_id in selected:
        counts.update(hangul(rows[entry_id]["text"]))
    blocked = Counter()
    blocked_examples: dict[str, list[str]] = {}
    for entry_id, row in rows.items():
        if entry_id in selected:
            continue
        result = trial_missing(row, glyphs, active, args.allow_overlength)
        if result is None:
            trial = dict(glyphs)
            trial.update({character: b"\x80\x00" for character in active if character not in trial})
            try:
                encoded_length = len(encode_text(row["text"], trial))
            except ValueError as exc:
                reason = "encoding-error:" + str(exc)
            else:
                reason = "overlength" if encoded_length > row["length"] else "unsupported-control"
        else:
            missing, _encoded_length = result
            after_usage = {
                lead: selected_usage[lead] | row_usage[entry_id][lead]
                for lead in BANKS
            }
            after_released = released_from_usage(all_usage, after_usage, used)
            after_slots = available_codes(used, after_released)
            if len(active | missing) > len(existing_codes) + len(set(after_slots) - set(existing_codes.values())):
                reason = "not-enough-safe-slots"
            else:
                reason = "not-selected"
        blocked[reason] += 1
        blocked_examples.setdefault(reason, []).append(entry_id)
    report = {
        "existing_glyphs": len(glyphs),
        "planned_glyphs": len(active),
        "new_glyphs": len(active - set(glyphs)),
        "selected_rows": len(selected),
        "new_rows": len(selected),
        "available_new_slots": free_slots,
        "released_slots": sum(len(values) for values in released.values()),
        "released_by_bank": {f"0x{lead:02X}": len(released[lead]) for lead in BANKS},
        "blocked_counts": dict(blocked),
        "blocked_examples": {key: values[:20] for key, values in blocked_examples.items()},
        "selected_ids": sorted(selected, key=lambda entry_id: catalog[entry_id]["offset"]),
        "new_glyphs_by_frequency": [
            character for character, _count in counts.most_common() if character not in glyphs
        ],
        "rows": {
            entry_id: {
                "category": rows[entry_id]["category"],
                "missing_glyphs": sorted(missing_by_row.get(entry_id, set())),
                "encoded_length": encoded_lengths[entry_id],
                "slot_length": rows[entry_id]["length"],
                "text": rows[entry_id]["text"],
            }
            for entry_id in sorted(selected, key=lambda item: catalog[item]["offset"])
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.ids_output.parent.mkdir(parents=True, exist_ok=True)
    args.ids_output.write_text("\n".join(report["selected_ids"]) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "existing_glyphs", "planned_glyphs", "new_glyphs", "selected_rows",
        "available_new_slots", "released_slots",
        "blocked_counts",
    )}, ensure_ascii=False))
    print(args.output)
    print(args.ids_output)


if __name__ == "__main__":
    main()

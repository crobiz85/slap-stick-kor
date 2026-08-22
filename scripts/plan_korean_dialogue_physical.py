"""Select the largest practical safe C0 dialogue batch.

This planner keeps the already-tested dialogue IDs, then adds encodable Korean
records while checking both constraints that matter for this ROM:

* Korean glyph codes must remain available without changing existing glyph
  assignments.
* Oversized records must fit in the same verified HiROM bank after their old
  slots are released and their 02 1D pointers are retargeted.

Menus, map labels, events, graphics, and the opening are intentionally outside
this planner's scope.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import random
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_korean_dialogue_inline import (  # noqa: E402
    ORIGINAL_ROM,
    read_catalog,
    read_translations,
)
from build_korean_font import (  # noqa: E402
    FONT_LEAD_BYTE,
    HANGUL_END,
    HANGUL_START,
    SECOND_FONT_LEAD_BYTE,
    THIRD_FONT_LEAD_BYTE,
    read_existing_codes,
    read_used_kanji_codes,
)
from encode_translation_drafts import encode_text, read_glyph_map  # noqa: E402
from plan_korean_dialogue_batch import (  # noqa: E402
    available_codes,
    code_usage,
    pointer_refs,
    released_from_usage,
    safe_rows,
)


BANKS = (0x50000, 0x60000, 0x70000, 0x80000, 0x90000)
FONT_BANKS = (FONT_LEAD_BYTE, SECOND_FONT_LEAD_BYTE, THIRD_FONT_LEAD_BYTE)
DEFAULT_BASE = ROOT / "build" / "slap-stick-kor-font-relocation-filtered-forced.smc"
DEFAULT_CANDIDATE_MAP = ROOT / "translation" / "korean-glyph-map-hangul.tsv"
DEFAULT_SEED_MANIFEST = ROOT / "build" / "korean-dialogue-relocated-forced.json"
DEFAULT_PREVIOUS_MAP = ROOT / "translation" / "korean-glyph-map-relocation-filtered-forced.tsv"
DEFAULT_OUTPUT = ROOT / "build" / "korean-dialogue-physical-coverage-plan.json"
DEFAULT_IDS = ROOT / "build" / "korean-dialogue-physical-coverage-ids.txt"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def hangul(text: str) -> set[str]:
    return {character for character in text if HANGUL_START <= ord(character) <= HANGUL_END}


def merge_glyph_maps(*paths: Path) -> dict[str, bytes]:
    glyphs: dict[str, bytes] = {}
    for path in paths:
        glyphs.update(read_glyph_map(path))
    return glyphs


def ff_runs(data: bytes, bank: int) -> list[list[int]]:
    runs: list[list[int]] = []
    start: int | None = None
    for offset in range(bank, bank + 0x10000):
        if data[offset] == 0xFF:
            if start is None:
                start = offset
        elif start is not None:
            runs.append([start, offset])
            start = None
    if start is not None:
        runs.append([start, bank + 0x10000])
    return runs


def merge_runs(runs: list[list[int]], additions: list[tuple[int, int]]) -> list[list[int]]:
    ordered = sorted(runs + [[start, end] for start, end in additions])
    merged: list[list[int]] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def subtract_runs(runs: list[list[int]], blocked: list[tuple[int, int]]) -> list[list[int]]:
    """Remove intervals that the inline builder overwrites with text/padding."""
    result = [run[:] for run in runs]
    for block_start, block_end in sorted(blocked):
        next_runs: list[list[int]] = []
        for run_start, run_end in result:
            if block_end <= run_start or block_start >= run_end:
                next_runs.append([run_start, run_end])
                continue
            if run_start < block_start:
                next_runs.append([run_start, block_start])
            if block_end < run_end:
                next_runs.append([block_end, run_end])
        result = next_runs
    return result


def physical_fit(
    selected: set[str], candidates: dict[str, dict], base_runs: dict[int, list[list[int]]]
) -> bool:
    for bank in BANKS:
        rows = [
            candidates[entry_id]
            for entry_id in selected
            if candidates[entry_id]["bank"] == bank and not candidates[entry_id]["inline"]
        ]
        inline_blocks = [
            (candidates[entry_id]["offset"], candidates[entry_id]["offset"] + candidates[entry_id]["slot_length"])
            for entry_id in selected
            if candidates[entry_id]["bank"] == bank and candidates[entry_id]["inline"]
        ]
        runs = merge_runs(
            subtract_runs(base_runs[bank], inline_blocks),
            [(row["offset"], row["offset"] + row["slot_length"] + 1) for row in rows],
        )
        for row in sorted(rows, key=lambda item: item["encoded_length"], reverse=True):
            needed = row["encoded_length"] + 1
            for run in runs:
                if run[1] - run[0] >= needed:
                    run[0] += needed
                    break
            else:
                return False
    return True


def font_fit(
    selected: set[str],
    candidates: dict[str, dict],
    catalog: dict[str, dict],
    used: dict[int, set[int]],
    all_usage: dict[int, set[int]],
    existing_codes: dict[str, tuple[int, int]],
) -> tuple[bool, int, int]:
    selected_usage = {lead: set() for lead in FONT_BANKS}
    characters = set(existing_codes)
    for entry_id in selected:
        row = candidates[entry_id]
        characters.update(row["characters"])
        for lead in FONT_BANKS:
            selected_usage[lead].update(row["usage"][lead])
    released = released_from_usage(all_usage, selected_usage, used)
    slots = set(available_codes(used, released))
    existing_slot_pairs = {tuple(code) for code in existing_codes.values()}
    if not existing_slot_pairs.issubset(slots):
        return False, len(slots), len(characters)
    return len(characters) <= len(slots), len(slots), len(characters)


def candidate_order(
    remaining: list[str], candidates: dict[str, dict], variant: int, rng: random.Random
) -> list[str]:
    if variant == 0:
        return sorted(
            remaining,
            key=lambda entry_id: (
                not candidates[entry_id]["inline"],
                len(candidates[entry_id]["characters"]),
                candidates[entry_id]["encoded_length"] - candidates[entry_id]["slot_length"],
                candidates[entry_id]["encoded_length"],
            ),
        )
    if variant == 1:
        return sorted(
            remaining,
            key=lambda entry_id: (
                not candidates[entry_id]["inline"],
                candidates[entry_id]["encoded_length"],
                len(candidates[entry_id]["characters"]),
                candidates[entry_id]["encoded_length"] - candidates[entry_id]["slot_length"],
            ),
        )
    if variant == 2:
        return sorted(
            remaining,
            key=lambda entry_id: (
                not candidates[entry_id]["inline"],
                candidates[entry_id]["encoded_length"] - candidates[entry_id]["slot_length"],
                len(candidates[entry_id]["characters"]),
                candidates[entry_id]["encoded_length"],
            ),
        )
    shuffled = list(remaining)
    rng.shuffle(shuffled)
    return shuffled


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan a physically safe expanded Korean C0 dialogue batch")
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--candidate-map", type=Path, default=DEFAULT_CANDIDATE_MAP)
    parser.add_argument("--seed-ids", type=Path, help="text file containing stable seed IDs")
    parser.add_argument("--seed-manifest", type=Path, default=DEFAULT_SEED_MANIFEST)
    parser.add_argument("--previous-map", type=Path, default=DEFAULT_PREVIOUS_MAP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ids-output", type=Path, default=DEFAULT_IDS)
    parser.add_argument("--trials", type=int, default=4)
    args = parser.parse_args()

    original = ORIGINAL_ROM.read_bytes()
    base = args.base.resolve().read_bytes()
    catalog = read_catalog()
    translations = read_translations()
    rows = safe_rows(original, catalog, translations)
    glyphs = merge_glyph_maps(args.candidate_map.resolve(), args.previous_map.resolve())
    used = {lead: read_used_kanji_codes(lead) for lead in FONT_BANKS}
    all_usage = code_usage(catalog, set(catalog))
    existing_codes = read_existing_codes(args.previous_map.resolve())
    base_runs = {bank: ff_runs(base, bank) for bank in BANKS}

    candidates: dict[str, dict] = {}
    for entry_id, row in rows.items():
        if row["category"] == "cold-boot-opening":
            continue
        try:
            encoded_length = len(encode_text(row["text"], glyphs))
        except ValueError:
            continue
        cat = catalog[entry_id]
        inline = encoded_length <= row["length"]
        pointers = pointer_refs(original, cat["offset"])
        if not inline and not pointers:
            continue
        usage = {lead: set() for lead in FONT_BANKS}
        raw = cat["raw"]
        for index in range(len(raw) - 1):
            if raw[index] in usage:
                usage[raw[index]].add(raw[index + 1])
        candidates[entry_id] = {
            "id": entry_id,
            "offset": cat["offset"],
            "slot_length": row["length"],
            "encoded_length": encoded_length,
            "inline": inline,
            "bank": cat["offset"] & ~0xFFFF,
            "characters": sorted(hangul(row["text"])),
            "usage": usage,
            "pointers": pointers,
        }

    if args.seed_ids:
        seed = {
            line.strip()
            for line in args.seed_ids.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
    else:
        seed_manifest = json.loads(args.seed_manifest.read_text(encoding="utf-8"))
        seed = set(seed_manifest["selected_ids"])
    missing_seed = sorted(seed - set(candidates))
    if missing_seed:
        raise ValueError(f"seed IDs are not safe candidates: {', '.join(missing_seed)}")
    if not physical_fit(seed, candidates, base_runs):
        raise ValueError("the supplied seed batch does not fit the physical base")
    if not font_fit(seed, candidates, catalog, used, all_usage, existing_codes)[0]:
        raise ValueError("the supplied seed batch does not fit the existing glyph map")

    remaining = sorted(set(candidates) - seed)
    best = set(seed)
    rng = random.Random(20260822)
    for trial in range(max(1, args.trials)):
        selected = set(seed)
        order = candidate_order(remaining, candidates, trial % 4, rng)
        for entry_id in order:
            trial_set = selected | {entry_id}
            if not physical_fit(trial_set, candidates, base_runs):
                continue
            if not font_fit(trial_set, candidates, catalog, used, all_usage, existing_codes)[0]:
                continue
            selected.add(entry_id)
        if len(selected) > len(best):
            best = selected

    font_ok, available_glyph_slots, used_glyph_slots = font_fit(
        best, candidates, catalog, used, all_usage, existing_codes
    )
    if not font_ok or not physical_fit(best, candidates, base_runs):
        raise ValueError("final batch failed the safety checks")

    manifest = {
        "kind": "Slap Stick Korean physically packed C0 dialogue plan",
        "base": str(args.base.resolve().relative_to(ROOT)),
        "base_sha256": sha256(base),
        "candidate_map": str(args.candidate_map.resolve().relative_to(ROOT)),
        "previous_map": str(args.previous_map.resolve().relative_to(ROOT)),
        "seed_count": len(seed),
        "candidate_count": len(candidates),
        "selected_count": len(best),
        "inline_count": sum(candidates[entry_id]["inline"] for entry_id in best),
        "relocated_count": sum(not candidates[entry_id]["inline"] for entry_id in best),
        "available_glyph_slots": available_glyph_slots,
        "used_glyph_slots": used_glyph_slots,
        "selected_ids": sorted(best, key=lambda entry_id: catalog[entry_id]["offset"]),
        "rows": {
            entry_id: {
                key: candidates[entry_id][key]
                for key in ("offset", "slot_length", "encoded_length", "inline", "bank", "characters")
            }
            for entry_id in sorted(best, key=lambda item: catalog[item]["offset"])
        },
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.ids_output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.ids_output.resolve().write_text("\n".join(manifest["selected_ids"]) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in (
        "candidate_count", "selected_count", "inline_count", "relocated_count",
        "available_glyph_slots", "used_glyph_slots",
    )}, ensure_ascii=False))
    print(args.output.resolve())
    print(args.ids_output.resolve())


if __name__ == "__main__":
    main()

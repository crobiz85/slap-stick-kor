"""Build a dialogue-only ROM with verified C0 string relocation.

This is the next step after the inline batch: selected C0 records that do not
fit their Japanese slots are copied into FF free space in the same HiROM bank,
and every verified ``02 1D`` call is retargeted.  Menus, maps, graphics, and
event code are not changed.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_korean_dialogue_inline import (  # noqa: E402
    ORIGINAL_ROM,
    control_review_is_dangerous,
    read_catalog,
    read_translations,
)
from encode_translation_drafts import encode_text, read_glyph_map  # noqa: E402


DEFAULT_PLAN = ROOT / "build" / "korean-dialogue-relocation-plan.json"
DEFAULT_BASE = ROOT / "build" / "slap-stick-kor-font-relocation.smc"
DEFAULT_OUTPUT = ROOT / "build" / "slap-stick-kor-dialogue-relocated.smc"
DEFAULT_MANIFEST = ROOT / "build" / "slap-stick-kor-dialogue-relocated.json"

# C0 records are stored in HiROM banks.  After an oversized source slot is
# released, its bytes become safe relocation space too, so search the whole
# corresponding bank rather than only the trailing half of that bank.
C0_RELOCATION_RANGES = {
    bank: (bank, bank + 0x10000)
    for bank in (0x50000, 0x60000, 0x70000, 0x80000, 0x90000)
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def pointer_refs(
    data: bytes, target: int, catalog: dict[str, dict] | None = None
) -> list[int]:
    address = target & 0xFFFF
    needle = bytes((0x02, 0x1D, address & 0xFF, address >> 8))
    result = []
    start = 0
    while True:
        found = data.find(needle, start)
        if found < 0:
            return result
        if catalog is None or not any(
            item["offset"] <= found <= item["offset"] + item["length"]
            for item in catalog.values()
        ):
            result.append(found)
        start = found + 1


def find_ff_run(data: bytes, start: int, end: int, length: int) -> int:
    run_start = None
    for offset in range(start, end):
        if data[offset] == 0xFF:
            run_start = offset if run_start is None else run_start
            if offset - run_start + 1 >= length:
                return run_start
        else:
            run_start = None
    raise ValueError(f"no FF run of {length} bytes in 0x{start:06X}-0x{end:06X}")


def c0_range(offset: int) -> tuple[int, int]:
    bank = offset & ~0xFFFF
    if bank not in C0_RELOCATION_RANGES:
        raise ValueError(f"no verified C0 relocation range for 0x{offset:06X}")
    return C0_RELOCATION_RANGES[bank]


def contains_embedded_event_call(raw: bytes) -> bool:
    """Return true when a C0 record contains an inline event-string call.

    ``02 1D`` is executable event data in this game's dialogue stream, not
    ordinary printable text.  Replacing the whole record with encoded text
    removes the call and leaves the event interpreter waiting at the next
    message.  Such records must remain byte-identical until they receive a
    script-aware translation.
    """
    return b"\x02\x1D" in raw


def load_plan(path: Path) -> set[str]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    return set(plan["selected_ids"])


def build(
    base: bytes,
    original: bytes,
    map_path: Path,
    plan_path: Path,
    base_path: Path = DEFAULT_BASE,
    translation_path: Path | None = None,
) -> tuple[bytes, dict]:
    catalog = read_catalog()
    translations = read_translations(translation_path)
    glyphs = read_glyph_map(map_path)
    selected_ids = load_plan(plan_path)
    if not selected_ids:
        raise ValueError("relocation plan contains no selected IDs")

    rows = []
    skipped = []
    for entry_id in selected_ids:
        if entry_id not in catalog or entry_id not in translations:
            raise ValueError(f"plan ID is missing from catalog/manuscript: {entry_id}")
        cat = catalog[entry_id]
        row = translations[entry_id]
        if control_review_is_dangerous(row.get("control_review", "")):
            skipped.append({"id": entry_id, "reason": row["control_review"]})
            continue
        actual = original[cat["offset"] : cat["offset"] + cat["length"]]
        if actual != cat["raw"]:
            raise ValueError(f"source mismatch for {entry_id}")
        if original[cat["offset"] + cat["length"]] != 0xC0:
            raise ValueError(f"missing C0 terminator for {entry_id}")
        if contains_embedded_event_call(actual):
            skipped.append({
                "id": entry_id,
                "reason": "embedded-event-call-02-1D",
            })
            continue
        try:
            encoded = encode_text(row["text"], glyphs)
        except ValueError as exc:
            # A row with an unmapped manuscript glyph cannot be safely
            # rewritten either.  Keep its original bytes and report it with
            # the other conservative fallbacks instead of aborting the whole
            # dialogue build.
            skipped.append({"id": entry_id, "reason": f"encoding-error: {exc}"})
            continue
        pointers = pointer_refs(original, cat["offset"], catalog)
        if len(encoded) > cat["length"] and not pointers:
            # An oversized record without a verified 02 1D call cannot be
            # relocated safely.  Preserve the source bytes and continue with
            # the rest of the catalogue instead of corrupting unrelated code.
            skipped.append({
                "id": entry_id,
                "reason": "oversized-without-verified-02-1D-pointer",
            })
            continue
        rows.append({
            "id": entry_id,
            "offset": cat["offset"],
            "slot_length": cat["length"],
            "text": row["text"],
            "encoded": encoded,
            "pointers": pointers,
        })

    target = bytearray(base)
    allowed: list[tuple[int, int]] = []
    inline = []
    relocated = []
    restored_original = []
    # Rows whose manuscript control review is incomplete are deliberately
    # left in the original byte form.  The font baseline may already contain
    # an earlier preview replacement at these offsets, so restore the complete
    # source slot and its C0 terminator before allocating relocation space.
    for item in skipped:
        cat = catalog[item["id"]]
        start = cat["offset"]
        end = start + cat["length"] + 1
        target[start:end] = original[start:end]
        allowed.append((start, end))
        restored_original.append({
            "id": item["id"],
            "offset": f"0x{start:06X}",
            "length": cat["length"],
            "reason": item["reason"],
        })
    # First release the old physical slots of oversized records.  This is
    # safe only after their direct call sites have been found and retargeted.
    for row in rows:
        if len(row["encoded"]) <= row["slot_length"]:
            continue
        if not row["pointers"]:
            raise ValueError(f"no verified 02 1D pointer for oversized {row['id']}")
        start = row["offset"]
        end = start + row["slot_length"] + 1
        target[start:end] = b"\xFF" * (end - start)
        allowed.append((start, end))

    # Inline rows retain their original C0 boundary.
    for row in rows:
        if len(row["encoded"]) > row["slot_length"]:
            continue
        start = row["offset"]
        end = start + row["slot_length"]
        payload = row["encoded"]
        target[start : start + len(payload)] = payload
        target[start + len(payload) : end] = b" " * (end - start - len(payload))
        if target[end] != 0xC0:
            raise ValueError(f"inline C0 boundary failed for {row['id']}")
        allowed.append((start, end))
        inline.append({"id": row["id"], "offset": f"0x{start:06X}", "encoded_length": len(payload)})

    # Allocate oversized rows inside their original HiROM bank.  Largest first
    # avoids leaving unusable holes when several records share a page.
    groups: dict[tuple[int, int], list[dict]] = {}
    for row in rows:
        if len(row["encoded"]) > row["slot_length"]:
            groups.setdefault(c0_range(row["offset"]), []).append(row)
    relocation_manifest = []
    pointer_manifest = []
    for relocation_range, group in groups.items():
        for row in sorted(group, key=lambda item: len(item["encoded"]), reverse=True):
            payload = row["encoded"] + b"\xC0"
            start = find_ff_run(target, relocation_range[0], relocation_range[1], len(payload))
            target[start : start + len(payload)] = payload
            allowed.append((start, start + len(payload)))
            for reference in row["pointers"]:
                target[reference + 2] = start & 0xFF
                target[reference + 3] = (start >> 8) & 0xFF
                allowed.append((reference + 2, reference + 4))
                pointer_manifest.append({
                    "id": row["id"],
                    "reference": f"0x{reference:06X}",
                    "old_offset": f"0x{row['offset']:06X}",
                    "new_offset": f"0x{start:06X}",
                })
            relocation_manifest.append({
                "id": row["id"],
                "old_offset": f"0x{row['offset']:06X}",
                "new_offset": f"0x{start:06X}",
                "slot_length": row["slot_length"],
                "encoded_length": len(row["encoded"]),
                "references": [f"0x{ref:06X}" for ref in row["pointers"]],
            })

    # Static proof: the relocation ROM changes only the custom font base plus
    # selected C0 slots, new strings, and the exact pointer operands.
    for offset, (before, after) in enumerate(zip(base, target)):
        if before == after:
            continue
        if not any(start <= offset < end for start, end in allowed):
            raise ValueError(f"unexpected byte changed outside dialogue relocation: 0x{offset:06X}")
    for row in rows:
        if len(row["encoded"]) <= row["slot_length"]:
            continue
        relocated_row = next(item for item in relocation_manifest if item["id"] == row["id"])
        start = int(relocated_row["new_offset"], 16)
        payload = row["encoded"]
        if target[start : start + len(payload)] != payload or target[start + len(payload)] != 0xC0:
            raise ValueError(f"relocated C0 verification failed for {row['id']}")

    manifest = {
        "kind": "Slap Stick Korean C0 dialogue relocation test",
        "base_rom": str(base_path.relative_to(ROOT)),
        "base_sha256": sha256(base),
        "target_sha256": sha256(bytes(target)),
        "source_original_sha256": sha256(original),
        "scope": "selected C0 dialogue records, same-bank FF relocation, and verified 02 1D pointer operands",
        "selected_count": len(rows),
        "inline_count": len(inline),
        "relocated_count": len(relocation_manifest),
        "selected_ids": sorted(selected_ids, key=lambda entry_id: catalog[entry_id]["offset"]),
        "skipped_control_rows": skipped,
        "restored_original_rows": restored_original,
        "inline": inline,
        "relocated": relocation_manifest,
        "pointer_updates": pointer_manifest,
        "changed_bytes_vs_font_base": sum(before != after for before, after in zip(base, target)),
    }
    return bytes(target), manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a safe same-bank C0 dialogue relocation ROM")
    parser.add_argument("--original", type=Path, default=ORIGINAL_ROM)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--glyph-map", type=Path, required=True)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--translation", type=Path, help="translation manuscript override")
    args = parser.parse_args()

    original = args.original.resolve().read_bytes()
    base_path = args.base.resolve()
    base = base_path.read_bytes()
    if len(original) != len(base):
        raise ValueError("original and base ROM sizes differ")
    target, manifest = build(
        base,
        original,
        args.glyph_map.resolve(),
        args.plan.resolve(),
        base_path,
        args.translation.resolve() if args.translation else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(target)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        key: manifest[key]
        for key in ("target_sha256", "selected_count", "inline_count", "relocated_count", "changed_bytes_vs_font_base")
    }, ensure_ascii=False))
    print(args.output)
    print(args.manifest)


if __name__ == "__main__":
    main()

"""Build a dialogue-only Korean test ROM from the safe font-only baseline.

This deliberately does not touch menus, the opening, graphics, pointers, or
event code.  It replaces only C0-terminated dialogue records whose Korean
encoding fits in the verified Japanese record slot.  Longer records are
reported for a later relocation pass instead of being written optimistically.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from encode_translation_drafts import encode_text, read_glyph_map  # noqa: E402


ORIGINAL_ROM = ROOT / "Slap Stick (J).smc"
FONT_ONLY_ROM = ROOT / "build" / "slap-stick-kor-font-only.smc"
CATALOG_PATH = ROOT / "translation" / "c0-dialogue-catalog.tsv"
# The reviewed manuscript is the source of truth.  The older canonical file
# contains only the first ROM-safe test subset and must not silently limit the
# dialogue build.
TRANSLATION_PATH = ROOT / "translation" / "korean-c0-manuscript.tsv"
CANONICAL_PATH = ROOT / "translation" / "korean-c0-dialogue.tsv"
DEFAULT_REPORT = ROOT / "build" / "korean-c0-dialogue-report.tsv"
DEFAULT_ROM = ROOT / "build" / "slap-stick-kor-dialogue-inline.smc"
DEFAULT_MANIFEST = ROOT / "build" / "slap-stick-kor-dialogue-inline.json"

# These are the verified Korean glyph pages used by the font-only baseline.
FONT_RANGES = ((0x50000, 0x54000), (0x54000, 0x58000), (0x60000, 0x64000))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_catalog() -> dict[str, dict]:
    rows = {}
    for line in CATALOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 4:
            continue
        entry_id = columns[0]
        rows[entry_id] = {
            "offset": int(columns[1], 16),
            "length": int(columns[2], 16),
            "raw": bytes.fromhex(columns[3]),
        }
    return rows


def read_translations() -> dict[str, dict]:
    rows = {}
    for line in TRANSLATION_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 5:
            raise ValueError(f"bad translation row: {line}")
        # Canonical rows have five columns; the complete manuscript has eight
        # and stores category/status separately.  Keep category available so
        # cold-boot opening rows remain excluded by default.
        category = columns[4]
        status = columns[5] if len(columns) >= 6 else columns[4]
        rows[columns[0]] = {
            "offset": int(columns[1], 16),
            "length": int(columns[2], 16),
            "text": columns[3],
            "category": category,
            "status": status,
        }
    # The canonical subset is the previously tested, known-good ROM route.
    # Keep it as a fallback/override so a manuscript line that needs a glyph
    # not present in the current font cannot make an older working line vanish
    # from the test ROM.
    for line in CANONICAL_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 5:
            raise ValueError(f"bad canonical translation row: {line}")
        rows[columns[0]] = {
            "offset": int(columns[1], 16),
            "length": int(columns[2], 16),
            "text": columns[3],
            "category": columns[4],
            "status": columns[4],
        }
    return rows


def encode_rows(original: bytes) -> list[dict]:
    catalog = read_catalog()
    translations = read_translations()
    glyphs = read_glyph_map()
    result = []
    for entry_id, row in translations.items():
        cat = catalog.get(entry_id)
        if cat is None:
            raise ValueError(f"{entry_id} is missing from the C0 catalog")
        if row["offset"] != cat["offset"] or row["length"] != cat["length"]:
            raise ValueError(f"{entry_id} translation coordinates disagree with catalog")
        actual = original[cat["offset"] : cat["offset"] + cat["length"]]
        source_match = actual == cat["raw"]
        terminator = original[cat["offset"] + cat["length"]]
        encoded = b""
        error = ""
        try:
            encoded = encode_text(row["text"], glyphs)
        except ValueError as exc:
            error = str(exc)
        result.append(
            {
                "id": entry_id,
                "offset": cat["offset"],
                "slot_length": cat["length"],
                "encoded_length": len(encoded),
                "fits": bool(encoded) and len(encoded) <= cat["length"],
                "source_match": source_match,
                "terminator": terminator == 0xC0,
                "category": row["category"],
                "status": row["status"],
                "text": row["text"],
                "encoded": encoded,
                "error": error,
            }
        )
    return result


def choose_rows(rows: list[dict], requested: set[str] | None, include_opening: bool) -> tuple[list[dict], dict[str, str]]:
    selected = []
    reasons = {}
    for row in rows:
        if requested is not None:
            if row["id"] not in requested:
                reasons[row["id"]] = "not-requested"
                continue
        elif row["category"] == "cold-boot-opening" and not include_opening:
            reasons[row["id"]] = "opening-excluded"
            continue
        if not row["source_match"]:
            reasons[row["id"]] = "source-mismatch"
            continue
        if not row["terminator"]:
            reasons[row["id"]] = "missing-c0-terminator"
            continue
        if row["error"]:
            reasons[row["id"]] = "encoding-error"
            continue
        if not row["fits"]:
            reasons[row["id"]] = "overlength"
            continue
        selected.append(row)
        reasons[row["id"]] = "selected"
    if requested is not None:
        known = {row["id"] for row in rows}
        missing = sorted(requested - known)
        if missing:
            raise ValueError(f"requested IDs are not in translation table: {', '.join(missing)}")
    return selected, reasons


def write_report(rows: list[dict], reasons: dict[str, str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Catalog-driven C0 dialogue preflight. No ROM bytes are written by report mode.\n")
        handle.write("# id\tstatus\toffset\tslot length\tencoded length\tfits\tsource match\tC0 terminator\tdecision\tnote\n")
        for row in rows:
            note = row["error"] or ""
            handle.write(
                f"{row['id']}\t{row['status']}\t0x{row['offset']:06X}\t"
                f"0x{row['slot_length']:04X}\t0x{row['encoded_length']:04X}\t"
                f"{'yes' if row['fits'] else 'no'}\t"
                f"{'yes' if row['source_match'] else 'no'}\t"
                f"{'yes' if row['terminator'] else 'no'}\t"
                f"{reasons[row['id']]}\t{note}\n"
            )


def assert_font_only_base(base: bytes) -> None:
    if len(base) != 0x180000:
        raise ValueError("font-only ROM size is not 1.5 MiB")
    original = ORIGINAL_ROM.read_bytes()
    for start, end in FONT_RANGES:
        if base[start:end] == original[start:end]:
            raise ValueError(f"font-only baseline has no glyph changes in 0x{start:06X}-0x{end:06X}")


def build_rom(base: bytes, selected: list[dict]) -> tuple[bytes, dict]:
    target = bytearray(base)
    original = ORIGINAL_ROM.read_bytes()
    changed_ranges = []
    for row in selected:
        start = row["offset"]
        end = start + row["slot_length"]
        payload = row["encoded"]
        # Keep the original C0 terminator at offset + slot_length.  The unused
        # bytes are unreachable after the terminator but are cleared to spaces
        # so stale Japanese bytes cannot be mistaken for part of the record.
        target[start : start + len(payload)] = payload
        target[start + len(payload) : end] = b" " * (row["slot_length"] - len(payload))
        if target[end] != 0xC0:
            raise ValueError(f"{row['id']} lost its C0 terminator")
        changed_ranges.append((start, end))

    # Static proof: relative to the known-safe font-only baseline, every
    # changed byte must be inside one selected dialogue slot.  Font bytes and
    # all menus/graphics/event code therefore remain identical to the base.
    for offset, (before, after) in enumerate(zip(base, target)):
        if before == after:
            continue
        if not any(start <= offset < end for start, end in changed_ranges):
            raise ValueError(f"unexpected byte changed outside selected C0 slots: 0x{offset:06X}")
    for _start, end in changed_ranges:
        if target[end] != 0xC0:
            raise ValueError(f"C0 boundary check failed at 0x{end:06X}")

    manifest = {
        "kind": "Slap Stick Korean dialogue-inline test",
        "base_rom": str(FONT_ONLY_ROM.relative_to(ROOT)),
        "base_sha256": sha256(base),
        "target_sha256": sha256(bytes(target)),
        "source_original_sha256": sha256(original),
        "scope": "C0 dialogue slots only; no menus, opening, graphics, pointers, or event code",
        "selected": [
            {
                "id": row["id"],
                "offset": f"0x{row['offset']:06X}",
                "slot_length": row["slot_length"],
                "encoded_length": row["encoded_length"],
            }
            for row in selected
        ],
        "changed_bytes_vs_font_only": sum(before != after for before, after in zip(base, target)),
    }
    return bytes(target), manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight/build safe inline Korean C0 dialogue.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--build", action="store_true", help="also write the dialogue-only test ROM")
    parser.add_argument("--output", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--include-opening", action="store_true", help="allow opening rows in default selection")
    parser.add_argument("--ids", help="comma-separated C0 IDs to select explicitly")
    args = parser.parse_args()

    if not ORIGINAL_ROM.exists():
        raise SystemExit(f"missing original ROM: {ORIGINAL_ROM}")
    if not FONT_ONLY_ROM.exists():
        raise SystemExit(f"missing font-only baseline: {FONT_ONLY_ROM}")
    original = ORIGINAL_ROM.read_bytes()
    base = FONT_ONLY_ROM.read_bytes()
    assert_font_only_base(base)
    rows = encode_rows(original)
    requested = {item.strip() for item in args.ids.split(",") if item.strip()} if args.ids else None
    selected, reasons = choose_rows(rows, requested, args.include_opening)
    write_report(rows, reasons, args.report)

    print(f"catalog_rows={len(rows)}")
    print(f"selected_fit_rows={len(selected)}")
    print(f"overlength_rows={sum(reason == 'overlength' for reason in reasons.values())}")
    print(f"report={args.report}")
    if not args.build:
        return

    target, manifest = build_rom(base, selected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(target)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"rom={args.output}")
    print(f"manifest={args.manifest}")
    print(f"changed_bytes_vs_font_only={manifest['changed_bytes_vs_font_only']}")


if __name__ == "__main__":
    main()

"""Build a conservative Korean-dialogue test ROM for Robotrek (USA).

The proven E4-E7/D8 font route is installed with the selected gilche font.
Simple physical dialogue records are redirected through the game's native CF
external-string command.  Records containing internal jumps/returns or mixed
binary data are deliberately left untouched until their entry boundaries are
resolved.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_robotrek_e4_e7_gilche_font_probe as gilche  # noqa: E402
import build_robotrek_e4_e7_full_font_probe as font_builder  # noqa: E402
from build_robotrek_e4_d8_single_probe import (  # noqa: E402
    DISPATCHER_CPU,
    DISPATCHER_OFFSET,
    DMA_BANK_OFFSET,
    DMA_BANK_ORIGINAL,
    FONT_SOURCE_OFFSET,
    FONT_SOURCE_ORIGINAL,
    KOREAN_PAGE0_OFFSET,
    NATIVE_FONT_MIRROR_OFFSET,
    NATIVE_FONT_SIZE,
    NATIVE_FONT_SOURCE,
    SOURCE,
    SOURCE_CALCULATOR_CPU,
    SOURCE_CALCULATOR_OFFSET,
    SOURCE_LENGTH,
    SOURCE_SHA256,
    STUB_TABLE_OFFSET,
    TARGET_LENGTH,
    TEXT_DISPATCH_OFFSET,
    TEXT_DISPATCH_ORIGINAL,
    make_dispatch_stubs,
    make_dispatcher,
    make_source_calculator,
)
from build_robotrek_english_retranslation_list import (  # noqa: E402
    DRAFTS,
    INDIRECT_CF,
    MIXED_DATA_IDS,
    NON_DIALOGUE_IDS,
)
from robotrek_hirom_utils import refresh_full_hirom_checksum  # noqa: E402


CATALOG = ROOT / "translation" / "robotrek-english-dialogue-catalog.tsv"
OLD_MAP = ROOT / "translation" / "robotrek-e4-e7-glyph-map.tsv"
OUTPUT = ROOT / "build" / "robotrek-usa-korean-dialogue-safe-test.sfc"
MANIFEST = ROOT / "build" / "robotrek-usa-korean-dialogue-safe-test.json"
OUTPUT_MAP = ROOT / "build" / "robotrek-usa-korean-dialogue-safe-test-glyph-map.tsv"

PREFIX_FIRST = 0xE4
CAPACITY = 1024
PAYLOAD_PAGES = tuple(
    {
        "file_start": 0x198000 + index * 0x10000,
        "file_end": 0x1A0000 + index * 0x10000,
        "cpu_bank": 0xD9 + index,
    }
    for index in range(7)
)

SINGLE = {
    "DFT": 0xD7,
    "FIN": 0xD1,
    "NXT": 0xDC,
    "TER": 0xCC,
    "CLR": 0xD0,
    "WIPE": 0xD0,
    "WAIT": 0xD2,
    "JMP": 0xD3,
}
PARAM = {"PAL": 0xC3, "NAM": 0xC2, "PAU": 0xC9, "SPEAKER": 0xE0}
RAW_BYTE = re.compile(r"[0-9A-F]{2}")


def sha256(data: bytes | bytearray) -> str:
    return hashlib.sha256(bytes(data)).hexdigest().upper()


def read_catalog() -> list[dict[str, str]]:
    with CATALOG.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader((line for line in handle if not line.startswith("#")), delimiter="\t"))


def encode_text(text: str, code_for: dict[str, bytes]) -> bytes:
    output = bytearray()
    position = 0
    while position < len(text):
        character = text[position]
        if character == "\n":
            output.append(0xCD)
            position += 1
            continue
        if character == "[":
            end = text.find("]", position + 1)
            if end >= 0:
                body = text[position + 1 : end]
                name, separator, parameter = body.partition(":")
                if name in SINGLE and not separator:
                    output.append(SINGLE[name])
                    position = end + 1
                    continue
                if name in PARAM and separator and RAW_BYTE.fullmatch(parameter):
                    output.extend((PARAM[name], int(parameter, 16)))
                    position = end + 1
                    continue
                if name == "BYTE" and separator and RAW_BYTE.fullmatch(parameter):
                    output.append(int(parameter, 16))
                    position = end + 1
                    continue
                if RAW_BYTE.fullmatch(body):
                    output.append(int(body, 16))
                    position = end + 1
                    continue
                # Korean/English labels in brackets are visible text, not commands.
        if character in code_for:
            output.extend(code_for[character])
        elif character == "…":
            output.extend(b"...")
        elif character in "·˳":
            output.append(ord("."))
        elif character in "‘’":
            output.append(ord("'"))
        elif ord(character) < 0x80:
            output.append(ord(character))
        else:
            raise ValueError(f"no glyph encoding for {character!r} (U+{ord(character):04X})")
        position += 1
    return bytes(output)


def install_font(target: bytearray, texts: list[str]) -> tuple[dict[str, bytes], list[dict[str, object]]]:
    existing: list[str] = []
    with OLD_MAP.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            existing.append(row["character"])
    frequency = Counter(character for text in texts for character in text if "가" <= character <= "힣")
    ordered = existing + sorted((set(frequency) - set(existing)), key=lambda c: (-frequency[c], c))
    if len(ordered) > CAPACITY:
        raise ValueError(f"Korean glyph capacity exceeded: {len(ordered)} > {CAPACITY}")

    rows: list[dict[str, object]] = []
    code_for: dict[str, bytes] = {}
    for ordinal, character in enumerate(ordered):
        encoded, _mask = gilche.render_gilche(character)
        prefix, index, top, bottom = font_builder.install_glyph(target, ordinal, encoded)
        code_for[character] = bytes((prefix, index))
        rows.append(
            {
                "character": character,
                "frequency": frequency[character],
                "ordinal": ordinal,
                "code": f"{prefix:02X} {index:02X}",
                "top_file_offset": f"0x{top:06X}",
                "bottom_file_offset": f"0x{bottom:06X}",
            }
        )
    return code_for, rows


def pack(target: bytearray, cursor: tuple[int, int], payload: bytes) -> tuple[int, int, int, tuple[int, int]]:
    page_index, offset = cursor
    while page_index < len(PAYLOAD_PAGES):
        page = PAYLOAD_PAGES[page_index]
        offset = max(offset, page["file_start"])
        if offset + len(payload) <= page["file_end"]:
            target[offset : offset + len(payload)] = payload
            address = 0x8000 + offset - page["file_start"]
            return offset, page["cpu_bank"], address, (page_index, offset + len(payload))
        page_index += 1
        if page_index < len(PAYLOAD_PAGES):
            offset = PAYLOAD_PAGES[page_index]["file_start"]
    raise ValueError("expanded dialogue space exhausted")


def main() -> None:
    source = SOURCE.read_bytes()
    if len(source) != SOURCE_LENGTH or sha256(source) != SOURCE_SHA256:
        raise ValueError("unexpected Robotrek (USA) source ROM")
    for offset, expected, label in (
        (TEXT_DISPATCH_OFFSET, TEXT_DISPATCH_ORIGINAL, "text dispatcher"),
        (FONT_SOURCE_OFFSET, FONT_SOURCE_ORIGINAL, "font source calculator"),
        (DMA_BANK_OFFSET, DMA_BANK_ORIGINAL, "font DMA bank"),
    ):
        if source[offset : offset + len(expected)] != expected:
            raise ValueError(f"{label} signature mismatch at 0x{offset:06X}")

    rows = read_catalog()
    row_for = {row["record_id"]: row for row in rows}
    target = bytearray(source)
    target.extend(b"\xFF" * (TARGET_LENGTH - len(target)))
    target[NATIVE_FONT_MIRROR_OFFSET : NATIVE_FONT_MIRROR_OFFSET + NATIVE_FONT_SIZE] = source[
        NATIVE_FONT_SOURCE : NATIVE_FONT_SOURCE + NATIVE_FONT_SIZE
    ]

    candidate_ids: list[str] = []
    skipped: dict[str, str] = {}
    for row in rows:
        record_id = row["record_id"]
        if record_id not in DRAFTS:
            continue
        if record_id in NON_DIALOGUE_IDS:
            skipped[record_id] = "non-dialogue data"
        elif record_id in MIXED_DATA_IDS:
            skipped[record_id] = "mixed binary/text boundary unresolved"
        elif record_id in INDIRECT_CF:
            skipped[record_id] = "handled once through its shared CF target"
        else:
            raw = bytes.fromhex(row["raw_hex"])
            if 0xD3 in raw or 0xCC in raw or raw.count(0xD7) != 1:
                skipped[record_id] = "internal jump/return or nested entry requires relocation fixups"
            elif int(row["length_without_terminator"]) < 6:
                skipped[record_id] = "CF wrapper does not fit"
            else:
                candidate_ids.append(record_id)

    font_texts = [DRAFTS[record_id] for record_id in candidate_ids]
    font_texts.extend(DRAFTS[record_id] for record_id in INDIRECT_CF)
    code_for, map_rows = install_font(target, font_texts)

    dispatcher = make_dispatcher()
    stubs = make_dispatch_stubs(source)
    calculator = make_source_calculator()
    dispatch_patch = bytes((0x5C, DISPATCHER_CPU & 0xFF, DISPATCHER_CPU >> 8, 0xD8))
    dispatch_patch += b"\xEA" * (len(TEXT_DISPATCH_ORIGINAL) - len(dispatch_patch))
    source_patch = bytes((0x22, SOURCE_CALCULATOR_CPU & 0xFF, SOURCE_CALCULATOR_CPU >> 8, 0xD8, 0x85, 0x46))
    source_patch += b"\xEA" * (len(FONT_SOURCE_ORIGINAL) - len(source_patch))
    target[TEXT_DISPATCH_OFFSET : TEXT_DISPATCH_OFFSET + len(dispatch_patch)] = dispatch_patch
    target[FONT_SOURCE_OFFSET : FONT_SOURCE_OFFSET + len(source_patch)] = source_patch
    target[DMA_BANK_OFFSET : DMA_BANK_OFFSET + len(DMA_BANK_ORIGINAL)] = bytes.fromhex("A9 D8 8D 04 43")
    target[DISPATCHER_OFFSET : DISPATCHER_OFFSET + len(dispatcher)] = dispatcher
    target[STUB_TABLE_OFFSET : STUB_TABLE_OFFSET + len(stubs)] = stubs
    target[SOURCE_CALCULATOR_OFFSET : SOURCE_CALCULATOR_OFFSET + len(calculator)] = calculator

    cursor = (0, PAYLOAD_PAGES[0]["file_start"])
    applied: list[dict[str, object]] = []
    source_ranges: list[tuple[int, int]] = []
    destination_ranges: list[tuple[int, int]] = []
    for record_id in candidate_ids:
        row = row_for[record_id]
        encoded = encode_text(DRAFTS[record_id], code_for)
        # A low byte of C0 is valid after an E4-E7 Korean-page prefix.  The
        # command dispatcher consumes it as the glyph index, so a raw byte
        # search for C0 would incorrectly reject valid Korean syllables.
        if not encoded or encoded[0] != 0xD7:
            skipped[record_id] = "translated record does not begin with DFT"
            continue
        # USA-native form is D7 CF <u24> C0.  D7 executes in the source
        # record, so the external continuation must omit its leading D7 and
        # return with CC.
        payload = encoded[1:] + b"\xCC"
        destination, bank, address, cursor = pack(target, cursor, payload)
        wrapper = bytes((0xD7, 0xCF, address & 0xFF, address >> 8, bank, 0xC0))
        source_offset = int(row["start_offset"], 16)
        slot = int(row["length_without_terminator"])
        replacement = wrapper + bytes(slot - len(wrapper))
        target[source_offset : source_offset + slot] = replacement
        if target[source_offset + slot] != 0xC0:
            raise ValueError(f"original terminator changed: {record_id}")
        source_ranges.append((source_offset, source_offset + slot + 1))
        destination_ranges.append((destination, destination + len(payload)))
        applied.append(
            {
                "id": record_id,
                "source": f"0x{source_offset:06X}",
                "slot_bytes": slot,
                "destination": f"0x{destination:06X}",
                "cpu": f"{bank:02X}:{address:04X}",
                "payload_bytes": len(payload),
            }
        )

    # Three unique strings are already called through native CF wrappers.
    seen_targets: set[int] = set()
    indirect_applied: list[dict[str, object]] = []
    for record_id, (target_hex, target_length) in INDIRECT_CF.items():
        target_offset = int(target_hex, 16)
        if target_offset in seen_targets:
            continue
        seen_targets.add(target_offset)
        encoded = encode_text(DRAFTS[record_id], code_for)
        # These catalogue drafts are already continuations and usually omit
        # DFT because their source wrapper executes D7.  Tolerate either form.
        continuation = encoded[1:] if encoded and encoded[0] == 0xD7 else encoded
        payload = continuation + b"\xCC"
        destination, bank, address, cursor = pack(target, cursor, payload)
        # The existing source record has already executed D7 before calling
        # this shared target.  Chain once more with CF, then CC returns to the
        # original caller after the relocated continuation completes.
        nested_wrapper = bytes((0xCF, address & 0xFF, address >> 8, bank, 0xCC))
        if len(nested_wrapper) > target_length:
            skipped[record_id] = "nested shared CF wrapper does not fit"
            continue
        replacement = nested_wrapper + bytes(target_length - len(nested_wrapper))
        target[target_offset : target_offset + target_length] = replacement
        indirect_applied.append(
            {
                "id": record_id,
                "target": target_hex,
                "slot_bytes": target_length,
                "destination": f"0x{destination:06X}",
                "cpu": f"{bank:02X}:{address:04X}",
                "payload_bytes": len(payload),
                "wrapper": nested_wrapper.hex(" ").upper(),
            }
        )

    for ranges, label in ((source_ranges, "source"), (destination_ranges, "destination")):
        ordered = sorted(ranges)
        for previous, current in zip(ordered, ordered[1:]):
            if current[0] < previous[1]:
                raise ValueError(f"overlapping {label} ranges: {previous} / {current}")

    checksum = refresh_full_hirom_checksum(target)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(target)
    with OUTPUT_MAP.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(map_rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(map_rows)

    manifest = {
        "kind": "Robotrek USA Korean dialogue conservative test build",
        "status": "runtime-test-required",
        "source_sha256": SOURCE_SHA256,
        "output_sha256": sha256(target),
        "output_size": len(target),
        "font": "gilche 1bpp 8x16 (selected option 1)",
        "glyph_count": len(code_for),
        "glyph_capacity": CAPACITY,
        "direct_records_applied": len(applied),
        "shared_cf_targets_applied": len(indirect_applied),
        "shared_cf_record_ids_effectively_applied": len(INDIRECT_CF),
        "translated_record_ids_effectively_applied": len(applied) + len(INDIRECT_CF),
        "translated_record_ids_pending_fixups": sum(
            reason != "handled once through its shared CF target" for reason in skipped.values()
        ),
        "payload_bytes": sum(row["payload_bytes"] for row in applied),
        "header_checksum": f"0x{checksum:04X}",
        "external_call_format": "D7 CF <address-low> <address-high> <bank> C0; target continuation ends CC",
        "safety_policy": "mixed data and records with internal D3/CC/nested D7 are left unchanged",
        "applied": applied,
        "indirect_applied": indirect_applied,
        "skipped": skipped,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in (
        "status", "output_sha256", "output_size", "glyph_count", "direct_records_applied",
        "shared_cf_targets_applied", "shared_cf_record_ids_effectively_applied",
        "translated_record_ids_effectively_applied", "translated_record_ids_pending_fixups",
        "payload_bytes", "header_checksum"
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

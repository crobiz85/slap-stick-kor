"""Build a playable Korean preview patch for the verified Japanese ROM.

This is intentionally conservative.  It inserts the generated 0x83xx Korean
glyphs and patches the six contiguous main-dialog records 0058-0063.  Record
0058 stays at its original inline location; records 0059-0063 are relocated
to verified FF padding in the same HiROM bank and their ``02 1D`` references
are updated.  The remaining early menu/event records still need a container
entry-point analysis and are not changed by this builder.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import binascii
import hashlib
import json

from encode_translation_drafts import encode_text, read_glyph_map


ROOT = Path(__file__).resolve().parent.parent
ROM_PATH = ROOT / "Slap Stick (J).smc"
SCRIPT_PATH = ROOT / "translation" / "script.tsv"
GLYPH_MAP_PATH = ROOT / "translation" / "korean-glyph-map.tsv"
DEFAULT_ROM_OUT = ROOT / "build" / "slap-stick-kor-preview.smc"
DEFAULT_BPS_OUT = ROOT / "patches" / "slap-stick-kor-preview.bps"
DEFAULT_IPS_OUT = ROOT / "patches" / "slap-stick-kor-preview.ips"
DEFAULT_MANIFEST_OUT = ROOT / "patches" / "slap-stick-kor-preview.json"

PATCHED_IDS = ("0058", "0059", "0060", "0061", "0062", "0063")
RELOCATED_IDS = PATCHED_IDS[1:]
DIALOG_BANK_START = 0x58000
DIALOG_BANK_END = 0x60000


@dataclass(frozen=True)
class DraftRow:
    entry_id: str
    offset: int
    original_length: int
    korean: str


def read_drafts() -> dict[str, DraftRow]:
    drafts: dict[str, DraftRow] = {}
    for line in SCRIPT_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 7 or columns[6] != "draft-ko" or not columns[5]:
            continue
        drafts[columns[0]] = DraftRow(
            entry_id=columns[0],
            offset=int(columns[1], 16),
            original_length=int(columns[2], 16),
            korean=columns[5],
        )
    return drafts


def read_glyph_tiles() -> list[tuple[str, int, bytes]]:
    result = []
    for line in GLYPH_MAP_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 5:
            continue
        character = columns[0]
        offset = int(columns[3], 16)
        tile = bytes.fromhex(columns[4])
        if len(tile) != 16:
            raise ValueError(f"glyph {character!r} has {len(tile)} bytes, expected 16")
        result.append((character, offset, tile))
    return result


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


def pointer_refs(data: bytes, target: int) -> list[int]:
    address = target & 0xFFFF
    needle = bytes((0x02, 0x1D, address & 0xFF, address >> 8))
    return [
        offset
        for offset in range(len(data) - len(needle) + 1)
        if data[offset : offset + len(needle)] == needle
    ]


def encode_rows(drafts: dict[str, DraftRow], glyphs: dict[str, bytes]) -> dict[str, bytes]:
    encoded = {}
    for entry_id in PATCHED_IDS:
        row = drafts[entry_id]
        encoded[entry_id] = encode_text(row.korean, glyphs)
        if entry_id == "0058":
            if len(encoded[entry_id]) <= row.original_length:
                raise ValueError("0058 unexpectedly fits; patch assumptions should be reviewed")
        elif len(encoded[entry_id]) <= row.original_length:
            raise ValueError(f"{entry_id} no longer needs relocation; patch assumptions should be reviewed")
    return encoded


def patch_rom(source: bytes, drafts: dict[str, DraftRow], encoded: dict[str, bytes]) -> tuple[bytes, dict]:
    target = bytearray(source)
    glyphs = read_glyph_tiles()
    for character, offset, tile in glyphs:
        if offset < 0 or offset + len(tile) > len(target):
            raise ValueError(f"glyph {character!r} is outside the ROM: 0x{offset:06X}")
        target[offset : offset + len(tile)] = tile

    total_relocated = sum(len(encoded[entry_id]) for entry_id in RELOCATED_IDS)
    relocation_start = find_ff_run(target, DIALOG_BANK_START, DIALOG_BANK_END, total_relocated)
    relocation_offsets: dict[str, int] = {}
    cursor = relocation_start
    for entry_id in RELOCATED_IDS:
        relocation_offsets[entry_id] = cursor
        target[cursor : cursor + len(encoded[entry_id])] = encoded[entry_id]
        cursor += len(encoded[entry_id])

    # 0058 is an inline record.  The relocated records free its old tail.
    inline = drafts["0058"]
    target[inline.offset : inline.offset + len(encoded["0058"])] = encoded["0058"]

    pointer_manifest = {}
    for entry_id in RELOCATED_IDS:
        old_offset = drafts[entry_id].offset
        new_offset = relocation_offsets[entry_id]
        refs = pointer_refs(source, old_offset)
        if not refs:
            raise ValueError(f"no 02 1D pointer reference found for {entry_id} at 0x{old_offset:06X}")
        for ref in refs:
            target[ref + 2] = new_offset & 0xFF
            target[ref + 3] = (new_offset >> 8) & 0xFF
        pointer_manifest[entry_id] = {
            "old_offset": f"0x{old_offset:06X}",
            "new_offset": f"0x{new_offset:06X}",
            "references": [f"0x{ref:06X}" for ref in refs],
        }

    changed = sum(left != right for left, right in zip(source, target))
    manifest = {
        "kind": "Slap Stick Korean preview patch",
        "source_length": len(source),
        "target_length": len(target),
        "source_sha256": hashlib.sha256(source).hexdigest().upper(),
        "target_sha256": hashlib.sha256(target).hexdigest().upper(),
        "patched_records": list(PATCHED_IDS),
        "unpatched_draft_records": [entry_id for entry_id in drafts if entry_id not in PATCHED_IDS],
        "glyph_count": len(glyphs),
        "inline_record": {
            "id": "0058",
            "offset": f"0x{inline.offset:06X}",
            "encoded_length": len(encoded["0058"]),
        },
        "relocation_start": f"0x{relocation_start:06X}",
        "relocation_end": f"0x{cursor:06X}",
        "relocated_bytes": total_relocated,
        "pointer_updates": pointer_manifest,
        "changed_bytes": changed,
    }
    return bytes(target), manifest


def encode_number(value: int) -> bytes:
    result = bytearray()
    while True:
        digit = value & 0x7F
        value >>= 7
        if value:
            result.append(digit | 0x80)
            value -= 1
        else:
            result.append(digit)
            return bytes(result)


def write_bps(source: bytes, target: bytes, output: Path, metadata: bytes) -> None:
    patch = bytearray(b"BPS1")
    patch.extend(encode_number(len(source)))
    patch.extend(encode_number(len(target)))
    patch.extend(encode_number(len(metadata)))
    patch.extend(metadata)
    cursor = 0
    while cursor < len(source):
        same = source[cursor] == target[cursor]
        end = cursor + 1
        while end < len(source) and (source[end] == target[end]) == same:
            end += 1
        length = end - cursor
        mode = 0 if same else 1
        patch.extend(encode_number(((length - 1) << 2) | mode))
        if not same:
            patch.extend(target[cursor:end])
        cursor = end
    patch.extend((binascii.crc32(source) & 0xFFFFFFFF).to_bytes(4, "little"))
    patch.extend((binascii.crc32(target) & 0xFFFFFFFF).to_bytes(4, "little"))
    patch.extend((binascii.crc32(patch) & 0xFFFFFFFF).to_bytes(4, "little"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patch)


def write_ips(source: bytes, target: bytes, output: Path) -> None:
    patch = bytearray(b"PATCH")
    cursor = 0
    while cursor < len(source):
        if source[cursor] == target[cursor]:
            cursor += 1
            continue
        start = cursor
        cursor += 1
        while cursor < len(source) and source[cursor] != target[cursor] and cursor - start < 0xFFFF:
            cursor += 1
        length = cursor - start
        patch.extend(start.to_bytes(3, "big"))
        patch.extend(length.to_bytes(2, "big"))
        patch.extend(target[start:cursor])
    patch.extend(b"EOF")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patch)


def apply_our_bps(source: bytes, patch: bytes) -> bytes:
    if patch[:4] != b"BPS1":
        raise ValueError("not a BPS patch")

    def read_number(position: int) -> tuple[int, int]:
        result = 0
        shift = 1
        while True:
            digit = patch[position]
            position += 1
            result += (digit & 0x7F) * shift
            if digit & 0x80:
                shift <<= 7
                result += shift
            else:
                return result, position

    position = 4
    source_size, position = read_number(position)
    target_size, position = read_number(position)
    metadata_size, position = read_number(position)
    position += metadata_size
    if source_size != len(source):
        raise ValueError("BPS source size does not match ROM")

    result = bytearray()
    while len(result) < target_size:
        action, position = read_number(position)
        mode = action & 3
        length = (action >> 2) + 1
        if mode == 0:
            source_offset = len(result)
            result.extend(source[source_offset : source_offset + length])
        elif mode == 1:
            result.extend(patch[position : position + length])
            position += length
        else:
            raise ValueError(f"unsupported BPS action mode {mode}")
    return bytes(result)


def apply_our_ips(source: bytes, patch: bytes) -> bytes:
    if patch[:5] != b"PATCH":
        raise ValueError("not an IPS patch")
    result = bytearray(source)
    position = 5
    while patch[position : position + 3] != b"EOF":
        offset = int.from_bytes(patch[position : position + 3], "big")
        size = int.from_bytes(patch[position + 3 : position + 5], "big")
        position += 5
        if size:
            result[offset : offset + size] = patch[position : position + size]
            position += size
            continue
        run_length = int.from_bytes(patch[position : position + 2], "big")
        value = patch[position + 2]
        position += 3
        result[offset : offset + run_length] = bytes((value,)) * run_length
    return bytes(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and verify the Korean preview BPS/IPS patch.")
    parser.add_argument("--rom", type=Path, default=ROM_PATH)
    parser.add_argument("--rom-output", type=Path, default=DEFAULT_ROM_OUT)
    parser.add_argument("--bps-output", type=Path, default=DEFAULT_BPS_OUT)
    parser.add_argument("--ips-output", type=Path, default=DEFAULT_IPS_OUT)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST_OUT)
    args = parser.parse_args()

    source = args.rom.read_bytes()
    drafts = read_drafts()
    missing = [entry_id for entry_id in PATCHED_IDS if entry_id not in drafts]
    if missing:
        raise ValueError(f"missing draft rows: {', '.join(missing)}")
    encoded = encode_rows(drafts, read_glyph_map())
    target, manifest = patch_rom(source, drafts, encoded)

    args.rom_output.parent.mkdir(parents=True, exist_ok=True)
    args.rom_output.write_bytes(target)
    write_bps(source, target, args.bps_output, b"Slap Stick Korean preview; 0058-0063 and 0x83xx font")
    write_ips(source, target, args.ips_output)
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rebuilt = apply_our_bps(source, args.bps_output.read_bytes())
    if rebuilt != target:
        raise ValueError("BPS self-check failed: applying the generated patch did not reproduce target ROM")
    rebuilt_ips = apply_our_ips(source, args.ips_output.read_bytes())
    if rebuilt_ips != target:
        raise ValueError("IPS self-check failed: applying the generated patch did not reproduce target ROM")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"BPS={args.bps_output}")
    print(f"IPS={args.ips_output}")
    print(f"ROM={args.rom_output}")


if __name__ == "__main__":
    main()

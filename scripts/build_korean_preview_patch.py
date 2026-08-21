"""Build a playable Korean preview patch for the verified Japanese ROM.

This is intentionally conservative. It inserts Korean glyphs into unused 16×16
source glyphs for the 0x80xx/0x81xx/0x82xx dictionary pages, patches compact Korean strings into the verified raw-menu and item-menu
slots, patches a second set of verified game-screen prompts in their original
slots, and patches the six early main-dialog records 0058-0063 plus the first
post-intro cutscene record 0067. Record 0058 stays at its original inline location;
records 0059-0063 are relocated to verified FF
padding in the same HiROM bank and their ``02 1D`` references are updated.  The
raw-menu strings are deliberately compact until their entry table is verified;
eight additional fixed-length save/skill menu records are patched only when the
encoded Korean draft fits its original slot.
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
MENU_PREVIEW_PATH = ROOT / "translation" / "korean-menu-preview.tsv"
GAME_MENU_PATH = ROOT / "translation" / "korean-game-menu.tsv"
EARLY_GAME_PATH = ROOT / "translation" / "korean-early-game.tsv"
C0_DIALOGUE_PATH = ROOT / "translation" / "korean-c0-dialogue.tsv"
ITEM_PREVIEW_PATH = ROOT / "translation" / "korean-item-preview.tsv"
DEFAULT_ROM_OUT = ROOT / "build" / "slap-stick-kor-preview.smc"
DEFAULT_BPS_OUT = ROOT / "patches" / "slap-stick-kor-preview.bps"
DEFAULT_IPS_OUT = ROOT / "patches" / "slap-stick-kor-preview.ips"
DEFAULT_MANIFEST_OUT = ROOT / "patches" / "slap-stick-kor-preview.json"

RAW_MENU_IDS = ("0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009", "0010", "0011", "0012")
FIXED_DRAFT_MENU_IDS = ("0001", "0013", "0014", "0015", "0016", "0017", "0018", "0019", "0020")
ITEM_PREVIEW_IDS = tuple(f"{index:04d}" for index in range(21, 36))
GAME_MENU_IDS = (
    "GAME-NAME-ENTRY",
    "GAME-0018", "GAME-0019", "GAME-0020", "GAME-0021", "GAME-0025", "GAME-0029",
    "GAME-0033", "GAME-0042", "GAME-0043", "GAME-0044", "GAME-0045",
)
EARLY_GAME_IDS = ()
C0_DIALOGUE_IDS = ("C0-05A3A8", "C0-05A3EA", "C0-06C3BE")
MAIN_DIALOG_IDS = ("0058", "0059", "0060", "0061", "0062", "0063", "0064", "0065", "0066", "0067")
PATCHED_IDS = RAW_MENU_IDS + FIXED_DRAFT_MENU_IDS + ITEM_PREVIEW_IDS + GAME_MENU_IDS + EARLY_GAME_IDS + C0_DIALOGUE_IDS + MAIN_DIALOG_IDS
INLINE_DIALOG_IDS = ("0058", "0064", "0065", "0066", "0067")
RELOCATED_IDS = tuple(entry_id for entry_id in MAIN_DIALOG_IDS if entry_id not in INLINE_DIALOG_IDS)
DIALOG_BANK_START = 0x58000
DIALOG_BANK_END = 0x60000
FONT_BANK_START = 0x50000
FONT_BANK_SIZE = 0x4000
SECOND_FONT_BANK_START = 0x54000
THIRD_FONT_BANK_START = 0x60000
GLYPH_BYTES = 64


@dataclass(frozen=True)
class DraftRow:
    entry_id: str
    offset: int
    original_length: int
    korean: str


@dataclass(frozen=True)
class GameMenuRow:
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


def read_menu_previews() -> dict[str, str]:
    previews: dict[str, str] = {}
    for line in MENU_PREVIEW_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) >= 2:
            previews[columns[0]] = columns[1]
    return previews


def read_item_previews() -> dict[str, str]:
    previews: dict[str, str] = {}
    for line in ITEM_PREVIEW_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) >= 2:
            previews[columns[0]] = columns[1]
    return previews


def read_game_menu() -> dict[str, GameMenuRow]:
    rows: dict[str, GameMenuRow] = {}
    for line in GAME_MENU_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) >= 4:
            rows[columns[0]] = GameMenuRow(
                entry_id=columns[0],
                offset=int(columns[1], 16),
                original_length=int(columns[2], 16),
                korean=columns[3],
            )
    return rows


def read_early_game() -> dict[str, GameMenuRow]:
    rows: dict[str, GameMenuRow] = {}
    for line in EARLY_GAME_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) >= 4:
            rows[columns[0]] = GameMenuRow(
                entry_id=columns[0],
                offset=int(columns[1], 16),
                original_length=int(columns[2], 16),
                korean=columns[3],
            )
    return rows


def read_c0_dialogue() -> dict[str, GameMenuRow]:
    rows: dict[str, GameMenuRow] = {}
    for line in C0_DIALOGUE_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) >= 4:
            rows[columns[0]] = GameMenuRow(
                entry_id=columns[0],
                offset=int(columns[1], 16),
                original_length=int(columns[2], 16),
                korean=columns[3],
            )
    return rows


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
        if len(tile) != GLYPH_BYTES:
            raise ValueError(f"glyph {character!r} has {len(tile)} bytes, expected {GLYPH_BYTES}")
        result.append((character, offset, tile))
    return result


def is_visible_font_offset(offset: int, length: int) -> bool:
    return any(
        start <= offset and offset + length <= start + FONT_BANK_SIZE
        for start in (FONT_BANK_START, SECOND_FONT_BANK_START, THIRD_FONT_BANK_START)
    )


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


def encode_rows(
    drafts: dict[str, DraftRow],
    game_menu: dict[str, GameMenuRow],
    early_game: dict[str, GameMenuRow],
    c0_dialogue: dict[str, GameMenuRow],
    glyphs: dict[str, bytes],
) -> dict[str, bytes]:
    encoded = {}
    menu_previews = read_menu_previews()
    item_previews = read_item_previews()
    for entry_id in RAW_MENU_IDS + FIXED_DRAFT_MENU_IDS:
        row = drafts[entry_id]
        source_text = menu_previews.get(entry_id, row.korean)
        if not source_text:
            raise ValueError(f"missing menu text: {entry_id}")
        encoded[entry_id] = encode_text(source_text, glyphs)
        if len(encoded[entry_id]) > row.original_length:
            raise ValueError(
                f"{entry_id} compact preview is {len(encoded[entry_id])} bytes, "
                f"slot is {row.original_length} bytes"
            )
    for entry_id in ITEM_PREVIEW_IDS:
        row = drafts[entry_id]
        if entry_id not in item_previews:
            raise ValueError(f"missing compact item preview: {entry_id}")
        encoded[entry_id] = encode_text(item_previews[entry_id], glyphs)
        if len(encoded[entry_id]) > row.original_length:
            raise ValueError(
                f"{entry_id} compact item preview is {len(encoded[entry_id])} bytes, "
                f"slot is {row.original_length} bytes"
            )
    for entry_id in GAME_MENU_IDS:
        row = game_menu[entry_id]
        encoded[entry_id] = encode_text(row.korean, glyphs)
        if len(encoded[entry_id]) > row.original_length:
            raise ValueError(
                f"{entry_id} preview is {len(encoded[entry_id])} bytes, "
                f"slot is {row.original_length} bytes"
            )
    for entry_id in EARLY_GAME_IDS:
        row = early_game[entry_id]
        encoded[entry_id] = encode_text(row.korean, glyphs)
        if len(encoded[entry_id]) > row.original_length:
            raise ValueError(
                f"{entry_id} preview is {len(encoded[entry_id])} bytes, "
                f"slot is {row.original_length} bytes"
            )
    for entry_id in C0_DIALOGUE_IDS:
        row = c0_dialogue[entry_id]
        encoded[entry_id] = encode_text(row.korean, glyphs)
        if len(encoded[entry_id]) > row.original_length:
            raise ValueError(
                f"{entry_id} preview is {len(encoded[entry_id])} bytes, "
                f"slot is {row.original_length} bytes"
            )
    for entry_id in MAIN_DIALOG_IDS:
        row = drafts[entry_id]
        encoded[entry_id] = encode_text(row.korean, glyphs)
        if entry_id == "0058":
            if len(encoded[entry_id]) <= row.original_length:
                raise ValueError("0058 unexpectedly fits; patch assumptions should be reviewed")
        elif entry_id in INLINE_DIALOG_IDS:
            if len(encoded[entry_id]) > row.original_length:
                raise ValueError(
                    f"{entry_id} is {len(encoded[entry_id])} bytes, slot is {row.original_length} bytes"
                )
        elif len(encoded[entry_id]) <= row.original_length:
            raise ValueError(f"{entry_id} no longer needs relocation; patch assumptions should be reviewed")
    return encoded


def patch_rom(
    source: bytes,
    drafts: dict[str, DraftRow],
    game_menu: dict[str, GameMenuRow],
    early_game: dict[str, GameMenuRow],
    c0_dialogue: dict[str, GameMenuRow],
    encoded: dict[str, bytes],
) -> tuple[bytes, dict]:
    target = bytearray(source)
    glyphs = read_glyph_tiles()
    for character, offset, tile in glyphs:
        if offset < 0 or offset + len(tile) > len(target):
            raise ValueError(f"glyph {character!r} is outside the ROM: 0x{offset:06X}")
        target[offset : offset + len(tile)] = tile
        if not is_visible_font_offset(offset, len(tile)):
            raise ValueError(f"glyph {character!r} is outside the visible Korean font pages: 0x{offset:06X}")

    total_relocated = sum(len(encoded[entry_id]) for entry_id in RELOCATED_IDS)
    relocation_start = find_ff_run(target, DIALOG_BANK_START, DIALOG_BANK_END, total_relocated)
    relocation_offsets: dict[str, int] = {}
    cursor = relocation_start
    for entry_id in RELOCATED_IDS:
        relocation_offsets[entry_id] = cursor
        target[cursor : cursor + len(encoded[entry_id])] = encoded[entry_id]
        cursor += len(encoded[entry_id])

    # 0058 deliberately uses the old 0059 tail; those records are relocated
    # before it is written.  The remaining early scene records fit in their
    # verified original slots and remain in place.
    for entry_id in INLINE_DIALOG_IDS:
        inline = drafts[entry_id]
        target[inline.offset : inline.offset + len(encoded[entry_id])] = encoded[entry_id]

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

    raw_menu_manifest = {}
    for entry_id in RAW_MENU_IDS + FIXED_DRAFT_MENU_IDS + ITEM_PREVIEW_IDS:
        row = drafts[entry_id]
        payload = encoded[entry_id]
        target[row.offset : row.offset + len(payload)] = payload
        # The raw block keeps its original slot boundary.  Space-fill the
        # unused tail so stale Japanese bytes cannot continue the preview text.
        target[row.offset + len(payload) : row.offset + row.original_length] = b" " * (
            row.original_length - len(payload)
        )
        raw_menu_manifest[entry_id] = {
            "offset": f"0x{row.offset:06X}",
            "slot_length": row.original_length,
            "encoded_length": len(payload),
        }

    game_menu_manifest = {}
    for entry_id in GAME_MENU_IDS:
        row = game_menu[entry_id]
        payload = encoded[entry_id]
        target[row.offset : row.offset + len(payload)] = payload
        target[row.offset + len(payload) : row.offset + row.original_length] = b" " * (
            row.original_length - len(payload)
        )
        game_menu_manifest[entry_id] = {
            "offset": f"0x{row.offset:06X}",
            "slot_length": row.original_length,
            "encoded_length": len(payload),
        }

    early_game_manifest = {}
    for entry_id in EARLY_GAME_IDS:
        row = early_game[entry_id]
        payload = encoded[entry_id]
        target[row.offset : row.offset + len(payload)] = payload
        target[row.offset + len(payload) : row.offset + row.original_length] = b" " * (
            row.original_length - len(payload)
        )
        early_game_manifest[entry_id] = {
            "offset": f"0x{row.offset:06X}",
            "slot_length": row.original_length,
            "encoded_length": len(payload),
        }

    c0_dialogue_manifest = {}
    for entry_id in C0_DIALOGUE_IDS:
        row = c0_dialogue[entry_id]
        payload = encoded[entry_id]
        target[row.offset : row.offset + len(payload)] = payload
        target[row.offset + len(payload) : row.offset + row.original_length] = b" " * (
            row.original_length - len(payload)
        )
        c0_dialogue_manifest[entry_id] = {
            "offset": f"0x{row.offset:06X}",
            "slot_length": row.original_length,
            "encoded_length": len(payload),
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
        "raw_menu_preview": raw_menu_manifest,
        "game_menu_preview": game_menu_manifest,
        "early_game_preview": early_game_manifest,
        "c0_dialogue_preview": c0_dialogue_manifest,
        "font_pages": {
            "lead_bytes": ["0x80", "0x81", "0x82"],
            "offset_ranges": ["0x50000-0x53FFF", "0x54000-0x57FFF", "0x60000-0x63FFF"],
            "note": "Korean glyphs use only code slots absent from the extracted Japanese script on the game's visible menu pages.",
        },
        "glyph_count": len(glyphs),
        "inline_records": [
            {
                "id": entry_id,
                "offset": f"0x{drafts[entry_id].offset:06X}",
                "encoded_length": len(encoded[entry_id]),
            }
            for entry_id in INLINE_DIALOG_IDS
        ],
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
    game_menu = read_game_menu()
    early_game = read_early_game()
    c0_dialogue = read_c0_dialogue()
    missing = [entry_id for entry_id in RAW_MENU_IDS + FIXED_DRAFT_MENU_IDS + ITEM_PREVIEW_IDS + MAIN_DIALOG_IDS if entry_id not in drafts]
    if missing:
        raise ValueError(f"missing draft rows: {', '.join(missing)}")
    missing_game = [entry_id for entry_id in GAME_MENU_IDS if entry_id not in game_menu]
    if missing_game:
        raise ValueError(f"missing game menu rows: {', '.join(missing_game)}")
    missing_early = [entry_id for entry_id in EARLY_GAME_IDS if entry_id not in early_game]
    if missing_early:
        raise ValueError(f"missing early game rows: {', '.join(missing_early)}")
    missing_c0 = [entry_id for entry_id in C0_DIALOGUE_IDS if entry_id not in c0_dialogue]
    if missing_c0:
        raise ValueError(f"missing C0 dialogue rows: {', '.join(missing_c0)}")
    encoded = encode_rows(drafts, game_menu, early_game, c0_dialogue, read_glyph_map())
    target, manifest = patch_rom(source, drafts, game_menu, early_game, c0_dialogue, encoded)

    args.rom_output.parent.mkdir(parents=True, exist_ok=True)
    args.rom_output.write_bytes(target)
    write_bps(source, target, args.bps_output, b"Slap Stick Korean preview; menus, dialog, unused 16x16 0x80xx/0x81xx/0x82xx font glyphs")
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

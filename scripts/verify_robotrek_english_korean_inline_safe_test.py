"""Static integrity checks for the current inline-safe Robotrek test ROM."""

from __future__ import annotations

import json
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_robotrek_english_korean_inline_safe_test as build  # noqa: E402
import build_robotrek_english_korean_safe_test as common  # noqa: E402
from robotrek_hirom_utils import refresh_full_hirom_checksum  # noqa: E402


def merged(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[list[int]] = []
    for start, end in sorted(ranges):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return [(start, end) for start, end in result]


def main() -> None:
    # Padding must precede C8/D1, while a glyph operand with the same byte
    # value is still data. These expectations are independent of the builder.
    for data, slot, expected in (
        (b"A\xC8\xCC", 7, b"A    \xC8\xCC"),
        (b"A\xD1\xCC", 6, b"A   \xD1\xCC"),
        (b"A\xC8", 4, b"A  \xC8"),
        (b"A\xD1", 4, b"A  \xD1"),
        (b"\xE4\xC8\xCC", 5, b"\xE4\xC8  \xCC"),
        (b"\xE4\xD1", 4, b"\xE4\xD1  "),
        (b"A\xC8\xCC", 3, b"A\xC8\xCC"),
    ):
        assert build.pad_fixed_segment(data, slot) == expected
    source = build.SOURCE.read_bytes()
    output = build.OUTPUT.read_bytes()
    # Polon's post-boss cry closes its window before returning to the event.
    # In v0.1.12, C8 + four rendered spaces + CC overwrote VRAM $C100.
    # Keep both commands adjacent and the event resume address unchanged.
    assert output[0x0A9CA4:0x0A9CA6] == source[0x0A9CA4:0x0A9CA6] == b"\xC8\xCC"
    assert output[0x0A9CA0:0x0A9CA4] == b"    "
    assert output[0x0A9CA6] == source[0x0A9CA6] == 0xD7
    manifest = json.loads(build.MANIFEST.read_text(encoding="utf-8"))
    catalog = {row["record_id"]: row for row in common.read_catalog()}
    catalog.update({row["record_id"]: row for row in build.read_supplemental_rows()})

    with build.OUTPUT_MAP.open("r", encoding="utf-8", newline="") as handle:
        code_for = {
            row["character"]: bytes.fromhex(row["code"])
            for row in csv.DictReader(handle, delimiter="\t")
        }

    allowed: list[tuple[int, int]] = [
        (0xFFDC, 0xFFE0),
        (build.TEXT_DISPATCH_OFFSET, build.TEXT_DISPATCH_OFFSET + len(build.TEXT_DISPATCH_ORIGINAL)),
        (build.FONT_SOURCE_OFFSET, build.FONT_SOURCE_OFFSET + len(build.FONT_SOURCE_ORIGINAL)),
        (build.DMA_BANK_OFFSET, build.DMA_BANK_OFFSET + len(build.DMA_BANK_ORIGINAL)),
    ]

    for row in manifest["applied"]:
        start = int(row["offset"], 16)
        end = start + int(row["slot_bytes"]) + 1
        allowed.append((start, end))
        assert output[start] == 0xD7, row["id"]
        assert output[int(row["terminator"], 16)] == 0xC0, row["id"]
        encoded = output[start : int(row["terminator"], 16)]
        raw = bytes.fromhex(catalog[row["id"]]["raw_hex"])
        assert build.event_flow_signature(encoded) == build.event_flow_signature(raw), row["id"]

    fixed_by_id = {row["id"]: row for row in manifest["fixed_entry_applied"]}
    for record_id, row in fixed_by_id.items():
        catalog_row = catalog[record_id]
        start = int(catalog_row["start_offset"], 16)
        raw = bytes.fromhex(catalog_row["raw_hex"])
        allowed.append((start, start + len(raw) + 1))
        encoded_region = output[start : start + len(raw)]
        if record_id == "EN-058580":
            d3_positions = [
                position for position, command in build.scan_commands(encoded_region) if command == 0xD3
            ]
            assert len(d3_positions) == 5
            assert all(encoded_region[position : position + 3] == bytes.fromhex("D3 81 89") for position in d3_positions)
            assert output[0x058981 : 0x058983] == bytes.fromhex("C3 03")
        else:
            assert build.event_flow_signature(encoded_region) == build.event_flow_signature(raw), record_id
            if any(command == 0xD3 for _position, command in build.scan_commands(raw)):
                if record_id in build.INTERNAL_D3_ANCHORS:
                    target_entries = {
                        int(segment["entry"], 16)
                        for segment in row["segments"]
                        if segment["entry_kind"] == "D3_TARGET"
                    }
                    base_low = start & 0xFFFF
                    internal_targets = {
                        start + ((raw[position + 1] | (raw[position + 2] << 8)) - base_low)
                        for position, command in build.scan_commands(raw)
                        if command == 0xD3
                        and 0 <= (raw[position + 1] | (raw[position + 2] << 8)) - base_low < len(raw)
                    }
                    assert target_entries == internal_targets, record_id
                else:
                    assert build.d3_targets_are_stable(raw, encoded_region, start), record_id
        for segment in row["segments"]:
            entry = int(segment["entry"], 16)
            kinds = set(segment["entry_kind"].split("+"))
            if "DFT" in kinds:
                assert output[entry] == 0xD7, (record_id, segment)
            if "AFTER_CC" in kinds:
                assert output[entry - 1] == 0xCC, (record_id, segment)

    payload_ranges: list[tuple[int, int]] = []
    for row in manifest["shared_cf_applied"]:
        record_id = row["id"]
        target = int(row["target"], 16)
        slot_bytes = int(row["slot_bytes"])
        destination = int(row["destination"], 16)
        payload_bytes = int(row["payload_bytes"])
        allowed.append((target, target + slot_bytes))

        encoded = common.encode_text(build.DRAFTS[record_id], code_for)
        continuation = encoded[1:] if encoded and encoded[0] == 0xD7 else encoded
        expected_payload = continuation + b"\xCC"
        assert len(expected_payload) == payload_bytes, record_id

        if row.get("mode") == "direct":
            assert destination == target, record_id
            assert output[target : target + payload_bytes] == expected_payload, record_id
            assert output[target + payload_bytes : target + slot_bytes] == bytes(
                slot_bytes - payload_bytes
            ), record_id
            continue

        wrapper = bytes.fromhex(row["wrapper"])

        assert output[target : target + len(wrapper)] == wrapper, record_id
        assert output[target + len(wrapper) : target + slot_bytes] == bytes(
            slot_bytes - len(wrapper)
        ), record_id
        assert wrapper[0] == 0xCF and wrapper[-1] == 0xCC, record_id

        bank_hex, address_hex = row["cpu"].split(":")
        bank = int(bank_hex, 16)
        address = int(address_hex, 16)
        assert wrapper[1:4] == bytes((address & 0xFF, address >> 8, bank)), record_id
        page = next(page for page in common.PAYLOAD_PAGES if page["cpu_bank"] == bank)
        assert destination == page["file_start"] + address - 0x8000, record_id
        assert destination + payload_bytes <= page["file_end"], record_id

        assert output[destination : destination + payload_bytes] == expected_payload, record_id
        payload_ranges.append((destination, destination + payload_bytes))

    assert len(manifest["shared_cf_applied"]) == manifest["shared_cf_targets_applied"]
    assert len(build.INDIRECT_CF) == manifest["shared_cf_record_ids_effectively_applied"]
    for previous, current in zip(sorted(payload_ranges), sorted(payload_ranges)[1:]):
        assert previous[1] <= current[0], (previous, current)

    runtime_scratch = bytearray(source)
    runtime_rows, runtime_ranges = build.apply_runtime_record_patches(
        runtime_scratch,
        source,
        code_for,
    )
    assert runtime_rows == manifest["runtime_record_applied"]
    assert len(runtime_rows) == manifest["runtime_records_applied"]
    assert len(runtime_rows) == len(build.RUNTIME_RECORD_PATCHES)
    for start, end in runtime_ranges:
        assert output[start:end] == runtime_scratch[start:end]
        allowed.append((start, end))

    screen_by_id = {row["id"]: row for row in manifest["screen_text_applied"]}
    assert set(screen_by_id) == {str(row["id"]) for row in build.SCREEN_TEXT_PATCHES}
    for spec in build.SCREEN_TEXT_PATCHES:
        record_id = str(spec["id"])
        row = screen_by_id[record_id]
        start = int(spec["start"])
        end = int(spec["end"])
        end_command = int(spec["end_command"])
        encoded = common.encode_text(str(spec["draft"]), code_for)
        slot = end - start
        assert int(row["slot_bytes"]) == slot, record_id
        assert int(row["encoded_bytes"]) == len(encoded), record_id
        assert row["end_command"] == f"0x{end_command:02X}", record_id
        assert int(row["end_command_offset"], 16) == end, record_id
        if end_command == 0xC0:
            expected = encoded + b"\xC0" + bytes(slot - len(encoded))
            assert output[start : end + 1] == expected, record_id
            assert int(row["terminator"], 16) == start + len(encoded), record_id
            allowed.append((start, end + 1))
        else:
            expected = build.pad_fixed_segment(encoded, slot)
            assert output[start:end] == expected, record_id
            assert output[end] == end_command, record_id
            assert row["terminator"] is None, record_id
            allowed.append((start, end))

    assert len(screen_by_id) == manifest["screen_text_spans_applied"]

    # 2026-09-04 screenshots: preserve window geometry, speaker/palette,
    # speed/pause operands and both shared-choice layouts, not merely text.
    new_screen_starts = {0x05F5F1, 0x08CD9A, 0x08CDB4, 0x09C508,
                         0x09EF77, 0x09EFEA, 0x09F01F, 0x0AE47B, 0x0AE981}
    important_commands = {0xC1, 0xC2, 0xC3, 0xC7, 0xC8, 0xC9,
                          0xCC, 0xD1, 0xD3, 0xD7, 0xD8, 0xD9, 0xDC, 0xDE, 0xE0}
    for spec in build.SCREEN_TEXT_PATCHES:
        start, end = int(spec["start"]), int(spec["end"])
        if start not in new_screen_starts:
            continue
        encoded = common.encode_text(str(spec["draft"]), code_for)
        def signature(data: bytes) -> list[tuple[int, bytes]]:
            return [(command, data[position + 1:position + 1 + build.COMMAND_PARAMETERS.get(command, 0)])
                    for position, command in build.scan_commands(data)
                    if command in important_commands]
        assert signature(encoded) == signature(source[start:end]), spec["id"]
        # English words must not survive inside the translated payload.
        operands = {i for pos, cmd in build.scan_commands(encoded)
                    for i in range(pos, pos + 1 + build.COMMAND_PARAMETERS.get(cmd, 0))}
        assert not any((65 <= value <= 90 or 97 <= value <= 122)
                       for i, value in enumerate(encoded) if i not in operands), spec["id"]
        if start in (0x05F5F1, 0x0AE981):
            new_lines = [p for p, c in build.scan_commands(encoded) if c == 0xCD]
            old_lines = [p for p, c in build.scan_commands(source[start:end]) if c == 0xCD]
            assert len(new_lines) == len(old_lines) == (3 if start == 0x05F5F1 else 1)
            assert output[end] == 0xCC
            assert output[end + 1:end + 17] == source[end + 1:end + 17]

    speaker_rows = manifest["speaker_name_applied"]
    assert len(speaker_rows) == len(build.SPEAKER_NAME_DRAFTS)
    assert len(speaker_rows) == manifest["speaker_names_applied"]
    cursor = build.SPEAKER_TEXT_START
    for speaker_id, (row, draft) in enumerate(
        zip(speaker_rows, build.SPEAKER_NAME_DRAFTS)
    ):
        encoded = common.encode_text(draft, code_for) + b"\xCC"
        assert row["speaker_id"] == f"0x{speaker_id:02X}"
        assert int(row["offset"], 16) == cursor
        assert int(row["encoded_bytes"]) == len(encoded)
        assert output[cursor : cursor + len(encoded)] == encoded
        pointer_offset = build.SPEAKER_POINTER_TABLE + speaker_id * 2
        assert int.from_bytes(output[pointer_offset : pointer_offset + 2], "little") == (
            cursor & 0xFFFF
        )
        cursor += len(encoded)
    assert output[cursor : build.SPEAKER_TEXT_END] == bytes(
        build.SPEAKER_TEXT_END - cursor
    )
    allowed.extend(
        [
            (
                build.SPEAKER_POINTER_TABLE,
                build.SPEAKER_POINTER_TABLE + len(build.SPEAKER_NAME_DRAFTS) * 2,
            ),
            (build.SPEAKER_TEXT_START, build.SPEAKER_TEXT_END),
        ]
    )

    allowed = merged(allowed)
    unexpected = []
    range_index = 0
    for offset, (before, after) in enumerate(zip(source, output)):
        if before == after:
            continue
        while range_index < len(allowed) and offset >= allowed[range_index][1]:
            range_index += 1
        if range_index >= len(allowed) or offset < allowed[range_index][0]:
            unexpected.append(offset)
    assert not unexpected, [f"0x{offset:06X}" for offset in unexpected[:20]]

    checksum_copy = bytearray(output)
    checksum = refresh_full_hirom_checksum(checksum_copy)
    assert checksum_copy == output
    assert manifest["header_checksum"] == f"0x{checksum:04X}"
    assert common.sha256(output) == manifest["output_sha256"]

    battle_reward = screen_by_id["REAUDIT-01CED1-BATTLE-BONUS-D3-TARGET"]
    battle_reward_end = int(battle_reward["end_command_offset"], 16)
    assert output[battle_reward_end - 1 : battle_reward_end + 1] == b"\xD1\xCC"
    assert output[0x01CED1:0x01CED6] == bytes.fromhex("DF 01 04 D0 05")
    assert output[0x01CEFB:0x01CEFE] == bytes.fromhex("D3 D1 CE")

    # Repeat interaction calls a D3 wrapper into the final paragraph of the
    # deserter's first speech. Compacting the whole speech erased this entry.
    assert source[0x0C9765:0x0C976A] == bytes.fromhex("02 1D A5 98 6B")
    assert output[0x0C9765:0x0C976A] == source[0x0C9765:0x0C976A]
    assert source[0x0C98A5:0x0C98AA] == bytes.fromhex("D7 D3 65 98 C0")
    assert output[0x0C98A5:0x0C98AA] == source[0x0C98A5:0x0C98AA]
    assert output[0x0C9864] == source[0x0C9864] == 0xD1
    treasure = common.encode_text(
        "이 동굴의 [PAL:02]보석 상자[PAL:00]를 가져가.\n난 필요 없어.", code_for
    ) + b"\xC0"
    assert output[0x0C9865:0x0C9865 + len(treasure)] == treasure
    warning = output[0x0C979F:0x0C9865]
    assert not any(command == 0xC0 for _, command in build.scan_commands(warning))

    # Both guard interactions share a CF body whose operand contains C0.
    # This is not a dialogue terminator; preserve both calls and the CC return.
    for guard_start in (0x0AC086, 0x0AC0F6):
        assert source[guard_start:guard_start + 5] == bytes.fromhex("D7 CF FC C0 8A")
        assert output[guard_start:guard_start + 5] == source[guard_start:guard_start + 5]
    assert output[0x0AC14A] == source[0x0AC14A] == 0xCC
    assert "REAUDIT-0AC0FC-MEETING-ROOM-GUARD-SHARED" in screen_by_id

    # The mouse experiment chant returns into event code, not another text
    # segment. Keep its CC fixed and leave the surrounding event scripts intact.
    chant = common.encode_text(
        "[DFT][PAL:03]실험! 실험!\n정말 신나!\n실험! 실험!\n정말 좋아![PAL:00]", code_for
    )
    assert output[0x0AD9AB:0x0AD9AB + len(chant)] == chant
    assert output[0x0AD9EA] == source[0x0AD9EA] == 0xCC
    for event_start, event_end in (
        (0x0AD250, 0x0AD33E),
        (0x0AD8CE, 0x0AD944),
        (0x0AD9EB, 0x0ADAB6),
    ):
        assert output[event_start:event_end] == source[event_start:event_end], hex(event_start)

    # Screen-text patches are encoded directly, so symbolic window aliases
    # must never leak into the ROM as visible ASCII.  The mouse shop used to
    # start with the literal string "[BOTTOM]" instead of the D8 command,
    # which prevented the interaction from opening at all.
    assert b"[BOTTOM]" not in output
    assert b"[TOP2]" not in output
    assert b"[TOP]" not in output
    assert output[0x0C9B46] == 0xD8
    assert output[0x0C9C55] == 0xD8
    assert output[0x0CA054] == 0xD9

    horn = fixed_by_id["EN-078E70"]
    assert [segment["entry_kind"] for segment in horn["segments"]] == ["DFT", "AFTER_CC+DFT"]

    mint_news = fixed_by_id["EN-058580"]
    assert mint_news["segments"][-1]["entry"] == "0x058981"
    assert mint_news["segments"][-1]["entry_kind"] == "D3_TARGET"

    arrest = fixed_by_id["EN-05A794"]
    assert arrest["segments"][-1]["entry"] == "0x05A7E5"
    # The arrest cutscene has a separately callable Nagisa entry immediately
    # after its D3 link.  Moving or dropping DB corrupts the following map
    # scene even when the visible policeman text itself appears to finish.
    assert output[0x05A7B0:0x05A7B4] == bytes.fromhex("D3 E5 A7 DB")
    assert output[0x05A7E5:0x05A7E7] == bytes.fromhex("C3 00")

    applied_record_ids = {row["id"] for row in manifest["applied"]} | set(fixed_by_id)
    assert set(build.NXT_OPERANDS) <= applied_record_ids
    for record_id, expected_operands in build.NXT_OPERANDS.items():
        catalog_row = catalog[record_id]
        start = int(catalog_row["start_offset"], 16)
        raw = bytes.fromhex(catalog_row["raw_hex"])
        translated = output[start : start + len(raw)]
        raw_operands = tuple(
            raw[position + 1]
            for position, command in build.scan_commands(raw)
            if command == 0xDC
        )
        translated_operands = tuple(
            translated[position + 1]
            for position, command in build.scan_commands(translated)
            if command == 0xDC
        )
        assert raw_operands == expected_operands, record_id
        assert translated_operands == expected_operands, record_id

    cave_row = catalog["EN-068DE9"]
    cave_start = int(cave_row["start_offset"], 16)
    cave_region = output[cave_start : cave_start + len(bytes.fromhex(cave_row["raw_hex"]))]
    assert bytes.fromhex("C9 1E C8 CC") in cave_region

    print(
        json.dumps(
            {
                "status": "static-verification-passed",
                "sha256": manifest["output_sha256"],
                "translated_records": manifest["total_translated_records_applied"],
                "direct_records": manifest["direct_records_applied"],
                "fixed_entry_records": manifest["fixed_entry_records_applied"],
                "supplemental_records": manifest["supplemental_records_applied"],
                "shared_cf_targets": manifest["shared_cf_targets_applied"],
                "screen_text_spans": manifest["screen_text_spans_applied"],
                "translation_units": manifest["total_translation_units_applied"],
                "unexpected_source_changes": len(unexpected),
                "horn_event_entries": horn["segments"],
                "checksum": manifest["header_checksum"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

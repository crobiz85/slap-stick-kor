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
from build_slap_stick_font_loader_probe import refresh_full_hirom_checksum  # noqa: E402


def merged(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[list[int]] = []
    for start, end in sorted(ranges):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return [(start, end) for start, end in result]


def main() -> None:
    source = build.SOURCE.read_bytes()
    output = build.OUTPUT.read_bytes()
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
        wrapper = bytes.fromhex(row["wrapper"])
        allowed.append((target, target + slot_bytes))

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

        encoded = common.encode_text(build.DRAFTS[record_id], code_for)
        continuation = encoded[1:] if encoded and encoded[0] == 0xD7 else encoded
        expected_payload = continuation + b"\xCC"
        assert len(expected_payload) == payload_bytes, record_id
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
            padding = build.fixed_command_padding(slot - len(encoded))
            if end_command in (0xD3, 0xCC, 0xDE) and encoded.endswith(b"\xD1"):
                expected = encoded[:-1] + padding + encoded[-1:]
            else:
                expected = encoded + padding
            assert output[start:end] == expected, record_id
            assert output[end] == end_command, record_id
            assert row["terminator"] is None, record_id
            allowed.append((start, end))

    assert len(screen_by_id) == manifest["screen_text_spans_applied"]

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

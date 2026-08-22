"""Restore an executable C0 event block in a coverage preview ROM.

The coverage build accidentally treated one C0 record containing an inline
``02 1D`` event-string call as ordinary dialogue.  This small reproducible
repair restores that record byte-for-byte from the Japanese source while
leaving every other coverage change untouched.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    original = args.original.read_bytes()
    base = args.base.read_bytes()
    if len(original) != len(base):
        raise ValueError("original and base ROM sizes differ")

    target = bytearray(base)
    # These records contain executable 02 1D string calls.  The coverage
    # preview replaced them as if they were ordinary dialogue, so preserve
    # every affected source record, not just the first observed boundary.
    event_blocks = [
        ("C0-05DADC", 0x05DADC, 0x5C),
        ("C0-05F3F5", 0x05F3F5, 0x12),
        ("C0-06C631", 0x06C631, 0x23),
        ("C0-06DDD4", 0x06DDD4, 0x2C),
        ("C0-07D767", 0x07D767, 0x3C),
        ("C0-07E786", 0x07E786, 0x42),
    ]
    restored_blocks = []
    changed_byte_count = 0
    for entry_id, offset, slot_length in event_blocks:
        before = base[offset : offset + slot_length + 1]
        source = original[offset : offset + slot_length + 1]
        if len(source) != slot_length + 1 or bytes([2, 29]) not in source:
            raise ValueError(f"source {entry_id} is not an embedded-event block")
        if source[-1] != 0xC0:
            raise ValueError(f"source {entry_id} is missing its C0 terminator")
        target[offset : offset + len(source)] = source
        changed = sum(a != b for a, b in zip(before, source))
        changed_byte_count += changed
        restored_blocks.append({
            "id": entry_id,
            "offset": f"0x{offset:06X}",
            "slot_length": slot_length,
            "reason": "preserve embedded event calls 02 1D",
            "changed_bytes": changed,
            "before": before.hex(" ").upper(),
            "after": source.hex(" ").upper(),
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(target)
    manifest = {
        "base_rom": str(args.base),
        "output_rom": str(args.output),
        "original_rom": str(args.original),
        "base_sha256": sha256(base),
        "target_sha256": sha256(target),
        "changed_bytes_vs_base": changed_byte_count,
        "restored_event_blocks": restored_blocks,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

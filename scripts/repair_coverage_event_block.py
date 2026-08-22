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

    # C0-05F3F5 is the first failing message boundary in the coverage ROM.
    offset = 0x05F3F5
    slot_length = 0x12
    original_block = bytes.fromhex(
        "DA 02 1D 3D F6 02 41 28 02 D0 3E 00 02 1D 66 F6 02 0A C0"
    )
    before = base[offset : offset + slot_length + 1]
    source = original[offset : offset + slot_length + 1]
    if source != original_block:
        raise ValueError("source C0-05F3F5 bytes do not match the expected event block")
    if b"\x02\x1D" not in source:
        raise ValueError("expected embedded event call is missing")
    if before == source:
        raise ValueError("base already contains the original event block")

    target = bytearray(base)
    target[offset : offset + len(source)] = source
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(target)
    manifest = {
        "base_rom": str(args.base),
        "output_rom": str(args.output),
        "original_rom": str(args.original),
        "base_sha256": sha256(base),
        "target_sha256": sha256(target),
        "changed_bytes_vs_base": len(source),
        "restored_event_block": {
            "id": "C0-05F3F5",
            "offset": "0x05F3F5",
            "slot_length": slot_length,
            "reason": "preserve embedded event calls 02 1D",
            "before": before.hex(" ").upper(),
            "after": source.hex(" ").upper(),
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

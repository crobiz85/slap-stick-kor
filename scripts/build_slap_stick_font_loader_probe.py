"""Build a native-glyph loader expansion proof for Japanese Slap Stick.

This probe deliberately leaves the live C6:4000/C7:0000 areas untouched.  It
uses two currently-unused *pairs* (BF01/BF02), keeps the original Japanese
glyph resolver for every other pair, and sends only those two pairs to a new
font page in the physical 2 MiB extension at D8:0000.

The proof changes one fixed dog line to ``BF01 BF02 BF01 BF02``.  It is not a
dialogue translation build; its purpose is to verify the actual renderer path
and the cross-bank source address before we scale the method to the script.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import ImageFont

from build_korean_font import encode_glyph, find_default_font, render_mask


ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = ROOT / "Slap Stick (J).smc"
OUTPUT_PATH = ROOT / "build" / "slap-stick-kor-font-loader-probe-bf-direct.smc"
MANIFEST_PATH = ROOT / "build" / "slap-stick-kor-font-loader-probe-bf-direct.json"

SOURCE_LENGTH = 0x180000
TARGET_LENGTH = 0x200000

# Text loop call site: C4:9E87, file offset 0x049E87.
CALL_SITE_OFFSET = 0x049E87
CALL_SITE_ORIGINAL = bytes.fromhex("20 79 A7 20 44 AC 80")
# JSL consumes the old resolver call and the first byte of the old AC44 JSR.
# The three bytes after it become a JMP continuation.  The bridge uses RTL,
# which removes the JSL return address before this JMP runs.
CALL_SITE_REPLACEMENT = bytes.fromhex("22 27 FF C4 4C 72 9E")  # JSL C4:FF27 / JMP $9E72

# The fixed dog line is a stable, nine-byte test payload.
DOG_TEXT_OFFSET = 0x05A072
DOG_ORIGINAL = bytes.fromhex("41 6F 3C 68 20 41 6F 3C 68")
DOG_REPLACEMENT = bytes.fromhex("BF 01 BF 02 20 BF 01 BF 02")

# C4:FF27 is a verified FF-filled code cave.  Keep this guard strict: if any
# original byte is no longer FF, abort instead of overwriting unknown code.
BRIDGE_OFFSET = 0x04FF27
BRIDGE_CPU_ADDRESS = 0xC4FF27
BRIDGE_CAVE_BYTES = 217

# The physical file expansion is already described by the Japanese ROM
# header as a 2 MiB HiROM (size byte 0x0B); the source file is just truncated
# at 1.5 MiB.  D8:0000 therefore maps to file offset 0x180000.
EXTENDED_FONT_OFFSET = 0x180000
EXTENDED_FONT_CODES = (("한", 0x01, 0x180040), ("글", 0x02, 0x180080))


class Assembler:
    def __init__(self) -> None:
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.branches: list[tuple[int, str]] = []

    def emit(self, *values: int) -> None:
        self.data.extend(values)

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"duplicate label: {name}")
        self.labels[name] = len(self.data)

    def branch8(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0)
        self.branches.append((len(self.data) - 1, label))

    def resolve(self) -> bytes:
        for operand_index, label in self.branches:
            if label not in self.labels:
                raise ValueError(f"unknown label: {label}")
            displacement = self.labels[label] - (operand_index + 1)
            if not -128 <= displacement <= 127:
                raise ValueError(f"branch out of range: {label} ({displacement})")
            self.data[operand_index] = displacement & 0xFF
        return bytes(self.data)


def make_c4_bridge() -> bytes:
    """Assemble a native glyph bridge ending in RTL."""

    asm = Assembler()

    # Entry state matches C4:9E87: A is the lead byte (M=8), Y points at the
    # second byte.  Only BF01/BF02 take the expanded route; all other pairs
    # execute the untouched original resolver and upload call.
    asm.emit(0xC9, 0xBF)  # CMP #$BF
    asm.branch8(0xD0, "normal")  # BNE normal
    asm.emit(0xB9, 0x00, 0x00)  # LDA $0000,Y
    asm.emit(0xC9, 0x01)  # CMP #$01
    asm.branch8(0xF0, "special")  # BEQ special
    asm.emit(0xC9, 0x02)  # CMP #$02
    asm.branch8(0xF0, "special")  # BEQ special
    asm.branch8(0x80, "normal")  # BRA normal

    asm.label("special")
    asm.emit(0xB9, 0x00, 0x00)  # LDA $0000,Y (M=8)
    asm.emit(0xC8)  # INY: consume the low byte
    asm.emit(0xC2, 0x20)  # REP #$20: 16-bit A/Y-compatible arithmetic
    asm.emit(0x5A)  # PHY, matching the original resolver
    asm.emit(0x29, 0xFF, 0x00)  # AND #$00FF
    for _ in range(6):
        asm.emit(0x0A)  # ASL A; low byte * 0x40 = 64-byte glyph tile
    asm.emit(0x85, 0x46)  # STA $46: source offset
    asm.emit(0xA9, 0xD8, 0x00)  # LDA #$00D8: extended source bank D8
    asm.emit(0x85, 0x48)  # STA $48
    asm.emit(0x38)  # SEC, matching the original resolver
    asm.emit(0x20, 0x57, 0xA6)  # JSR $A657
    asm.emit(0x20, 0xCA, 0xA8)  # JSR $A8CA

    # Exact post-upload tail from C4:A779, followed by the caller's upload
    # routine (C4:AC44), then RTL to the patched JMP continuation.
    asm.emit(0xAE, 0xD2, 0x0E)  # LDX $0ED2
    asm.emit(0xBD, 0xCE, 0x0E)  # LDA $0ECE,X
    asm.emit(0x18, 0x69, 0x03, 0x00)  # CLC / ADC #$0003
    asm.emit(0x9D, 0xCE, 0x0E)  # STA $0ECE,X
    asm.emit(0xBD, 0xAA, 0x0E)  # LDA $0EAA,X
    asm.emit(0x18, 0x69, 0x03, 0x00)  # CLC / ADC #$0003
    asm.emit(0x9D, 0xAA, 0x0E)  # STA $0EAA,X
    asm.emit(0x7A)  # PLY
    asm.emit(0x20, 0x44, 0xAC)  # JSR $AC44, as at C4:9E8A
    asm.emit(0x6B)  # RTL

    asm.label("normal")
    asm.emit(0x20, 0x79, 0xA7)  # JSR $A779, original resolver
    asm.emit(0x20, 0x44, 0xAC)  # JSR $AC44, original caller continuation
    asm.emit(0x6B)  # RTL
    return asm.resolve()


def sha256(data: bytes | bytearray) -> str:
    return hashlib.sha256(bytes(data)).hexdigest().upper()


def refresh_full_hirom_checksum(target: bytearray) -> int:
    """Write a checksum for the physical 2 MiB target.

    The original 1.5 MiB image declares a 2 MiB cartridge, so the source
    checksum is computed as if its final 512 KiB were mirrored.  The target is
    a real 2 MiB image; after zeroing the checksum fields, its physical sum is
    used directly with the standard 0x01FE adjustment.
    """

    if len(target) != TARGET_LENGTH:
        raise ValueError("target must be exactly 2 MiB")
    target[0xFFDC:0xFFE0] = b"\x00" * 4
    checksum = (sum(target) + 0x01FE) & 0xFFFF
    complement = checksum ^ 0xFFFF
    target[0xFFDC:0xFFDE] = complement.to_bytes(2, "little")
    target[0xFFDE:0xFFE0] = checksum.to_bytes(2, "little")
    return checksum


def count_pair_in_catalogues(pair: bytes) -> int:
    """Count exact pair tokens in the extracted text/control catalogues."""

    count = 0
    paths = (
        ROOT / "translation" / "script.tsv",
        ROOT / "translation" / "c0-dialogue-catalog.tsv",
        ROOT / "translation" / "c0-dialogue-review.tsv",
        ROOT / "translation" / "control-annotated.tsv",
        ROOT / "translation" / "font-test-codes.tsv",
    )
    needle = " ".join(f"{value:02X}" for value in pair)
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            count += line.upper().count(needle)
    return count


def main() -> None:
    source = SOURCE_PATH.read_bytes()
    if len(source) != SOURCE_LENGTH:
        raise ValueError(f"expected 1.5 MiB source, got 0x{len(source):X}")
    if source[CALL_SITE_OFFSET : CALL_SITE_OFFSET + len(CALL_SITE_ORIGINAL)] != CALL_SITE_ORIGINAL:
        raise ValueError("native glyph call site is not the expected original JSR")
    if source[DOG_TEXT_OFFSET : DOG_TEXT_OFFSET + len(DOG_ORIGINAL)] != DOG_ORIGINAL:
        raise ValueError("expected original dog line was not found")
    if any(value != 0xFF for value in source[BRIDGE_OFFSET : BRIDGE_OFFSET + BRIDGE_CAVE_BYTES]):
        raise ValueError("C4:FF27 code cave is no longer FF-filled")

    pair_counts = {
        "BF01": count_pair_in_catalogues(bytes.fromhex("BF 01")),
        "BF02": count_pair_in_catalogues(bytes.fromhex("BF 02")),
    }
    if any(pair_counts.values()):
        raise ValueError(f"candidate pairs are already present in extracted catalogues: {pair_counts}")

    bridge = make_c4_bridge()
    if len(bridge) > BRIDGE_CAVE_BYTES:
        raise ValueError(f"bridge is {len(bridge)} bytes, cave is only {BRIDGE_CAVE_BYTES}")

    font_path = find_default_font()
    font = ImageFont.truetype(str(font_path), 12)
    target = bytearray(source)
    target.extend(b"\xFF" * (TARGET_LENGTH - SOURCE_LENGTH))

    # Preserve the old C4 cave contents except for the new bridge.
    target[CALL_SITE_OFFSET : CALL_SITE_OFFSET + len(CALL_SITE_REPLACEMENT)] = CALL_SITE_REPLACEMENT
    target[BRIDGE_OFFSET : BRIDGE_OFFSET + len(bridge)] = bridge

    glyph_report = []
    for character, low_byte, offset in EXTENDED_FONT_CODES:
        tile = encode_glyph(render_mask(character, font, 12))
        if len(tile) != 64:
            raise ValueError(f"unexpected tile size for {character}: {len(tile)}")
        target[offset : offset + len(tile)] = tile
        glyph_report.append(
            {
                "character": character,
                "code": f"BF {low_byte:02X}",
                "cpu_source": f"D8:{(offset - EXTENDED_FONT_OFFSET):04X}",
                "file_offset": f"0x{offset:06X}",
                "tile_bytes": len(tile),
            }
        )

    target[DOG_TEXT_OFFSET : DOG_TEXT_OFFSET + len(DOG_REPLACEMENT)] = DOG_REPLACEMENT
    checksum = refresh_full_hirom_checksum(target)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_bytes(target)

    # Ensure C6/C7 and all unrelated bytes in the original 1.5 MiB remain
    # unchanged except for the documented call site, dog line, bridge cave,
    # and checksum fields.
    allowed = set(range(CALL_SITE_OFFSET, CALL_SITE_OFFSET + len(CALL_SITE_REPLACEMENT)))
    allowed.update(range(BRIDGE_OFFSET, BRIDGE_OFFSET + len(bridge)))
    allowed.update(range(DOG_TEXT_OFFSET, DOG_TEXT_OFFSET + len(DOG_REPLACEMENT)))
    allowed.update(range(0xFFDC, 0xFFE0))
    unexpected_changes = [
        index
        for index, (before, after) in enumerate(zip(source, target[:SOURCE_LENGTH]))
        if before != after and index not in allowed
    ]
    if unexpected_changes:
        raise AssertionError(f"unexpected source changes: {unexpected_changes[:10]}")
    if target[0x60000:0x80000] != source[0x60000:0x80000]:
        raise AssertionError("C6:0000-C7:0000 changed unexpectedly")

    manifest = {
        "kind": "Japanese Slap Stick native glyph loader expansion proof",
        "source": SOURCE_PATH.name,
        "source_sha256": sha256(source),
        "target": OUTPUT_PATH.name,
        "target_sha256": sha256(target),
        "source_length": len(source),
        "target_length": len(target),
        "header_size_byte": f"0x{target[0xFFD7]:02X}",
        "candidate_pairs": pair_counts,
        "renderer_change": {
            "call_site": "C4:9E87",
            "original": CALL_SITE_ORIGINAL.hex(" ").upper(),
            "replacement": CALL_SITE_REPLACEMENT.hex(" ").upper(),
            "bridge_cpu": f"C4:{BRIDGE_CPU_ADDRESS & 0xFFFF:04X}",
            "bridge_bytes": len(bridge),
            "return_cpu": "C4:9E8B",
            "continuation": "4C 72 9E (JMP C4:9E72)",
        },
        "extended_font": {
            "physical_bank": "D8",
            "file_range": "0x180000-0x1FFFFF",
            "glyphs": glyph_report,
        },
        "dialogue_change": {
            "file_offset": f"0x{DOG_TEXT_OFFSET:06X}",
            "original": DOG_ORIGINAL.hex(" ").upper(),
            "replacement": DOG_REPLACEMENT.hex(" ").upper(),
            "display": "한글 한글",
        },
        "safety_checks": {
            "c6_c7_untouched": True,
            "unexpected_original_changes": 0,
            "source_code_cave_verified_ff": True,
            "catalogue_pair_collisions": pair_counts,
        },
        "header_checksum": f"0x{checksum:04X}",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

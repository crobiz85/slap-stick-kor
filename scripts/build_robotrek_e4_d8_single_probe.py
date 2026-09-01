"""Build a one-glyph E4/D8 font-prefix probe for Robotrek (USA).

The probe expands the clean 1.5 MiB ROM to 2 MiB, mirrors the original
English 8x16 font into D8:8000, installs one narrow Korean glyph at D8:0000,
and adds E4-E7 as direct two-byte Korean page prefixes.  Only one fixed-size
dog dialogue is changed to E4 00 for the runtime check.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageFont

from build_korean_font import encode_tile, find_default_font, render_mask
from robotrek_hirom_utils import Assembler, refresh_full_hirom_checksum


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "Robotrek (USA).sfc"
OUTPUT = ROOT / "build" / "robotrek-kor-e4-d8-single-probe.sfc"
MANIFEST = ROOT / "build" / "robotrek-kor-e4-d8-single-probe.json"
PREVIEW = ROOT / "build" / "robotrek-kor-e4-d8-single-probe-glyph.png"

SOURCE_SHA256 = "1E2DED7B1E350449B7A99B7EC414525E4B9B086C416DEEEE5EB3E48E032C46BD"
SOURCE_LENGTH = 0x180000
TARGET_LENGTH = 0x200000

TEXT_DISPATCH_OFFSET = 0x0492C3
TEXT_DISPATCH_ORIGINAL = bytes.fromhex(
    "C2 20 F4 A1 92 29 3F 00 0A AA BF D4 92 84 3A 48 60"
)
TEXT_COMMAND_TABLE_OFFSET = 0x0492D4
TEXT_COMMAND_WORDS = 0x40

FONT_SOURCE_OFFSET = 0x0499D0
FONT_SOURCE_ORIGINAL = bytes.fromhex("29 FF 00 0A 0A 0A 0A 85 46 A9 C8 00 85 48")
DMA_BANK_OFFSET = 0x0BFCE3
DMA_BANK_ORIGINAL = bytes.fromhex("A9 C8 8D 04 43")

DOG_TEXT_OFFSET = 0x05A23D
DOG_TEXT_ORIGINAL = bytes.fromhex("D7 CD 42 6F 77 20 77 6F 77 2E CD C0")
DOG_TEXT_PROBE = bytes.fromhex("D7 CD E4 00 20 20 20 20 20 20 CD C0")

NATIVE_FONT_SOURCE = 0x080000
NATIVE_FONT_SIZE = 0x2000
KOREAN_PAGE0_OFFSET = 0x180000  # D8:0000
NATIVE_FONT_MIRROR_OFFSET = 0x188000  # D8:8000
DISPATCHER_OFFSET = 0x18A000  # D8:A000
DISPATCHER_CPU = 0xA000
STUB_TABLE_OFFSET = 0x18A100  # D8:A100
STUB_TABLE_CPU = 0xA100
SOURCE_CALCULATOR_OFFSET = 0x18B000  # D8:B000
SOURCE_CALCULATOR_CPU = 0xB000


def sha256(data: bytes | bytearray) -> str:
    return hashlib.sha256(bytes(data)).hexdigest().upper()


def make_narrow_hangul(character: str = "한") -> tuple[bytes, Image.Image]:
    """Render one 8x16 glyph as the native top/bottom 8x8 tile pair."""

    font_path = find_default_font()
    font = ImageFont.truetype(str(font_path), 12)
    wide = render_mask(character, font, 12)
    narrow = wide.resize((8, 16), Image.Resampling.NEAREST)
    top = encode_tile(narrow.crop((0, 0, 8, 8)))
    bottom = encode_tile(narrow.crop((0, 8, 8, 16)))
    if len(top) != 16 or len(bottom) != 16:
        raise AssertionError("native 8x16 glyph must be two 16-byte tiles")
    return top + bottom, narrow


def make_dispatcher() -> bytes:
    """Route E4-E7 to one Korean glyph and preserve all other dispatches."""

    asm = Assembler()
    # Entry matches C4:92C3: A is the command byte, M=8, Y points to the
    # following byte.  E4-E7 consume that byte as a Korean glyph index.
    asm.emit(0xC9, 0xE4)  # CMP #$E4
    asm.branch8(0x90, "normal")  # BCC normal
    asm.emit(0xC9, 0xE8)  # CMP #$E8
    asm.branch8(0xB0, "normal")  # BCS normal
    asm.emit(0x38, 0xE9, 0xE4)  # SEC / SBC #$E4 -> page 0..3
    asm.emit(0x18, 0x69, 0xD0)  # CLC / ADC #$D0 -> one-shot page marker
    asm.emit(0x85, 0x48)  # STA $48 (M=8)
    asm.emit(0xB9, 0x00, 0x00)  # LDA $0000,Y: glyph index
    asm.emit(0xC8)  # INY: consume index
    asm.emit(0xC2, 0x20)  # REP #$20
    asm.emit(0x29, 0xFF, 0x00)  # AND #$00FF
    asm.emit(0xF4, 0xA1, 0x92)  # PEA $92A1; handler RTS returns to C4:92A2
    asm.emit(0x5C, 0xCD, 0x99, 0xC4)  # JML C4:99CD ordinary glyph tail

    asm.label("normal")
    # Reproduce C4:92C3's stack-dispatch semantics from D8.  RTS first enters
    # a D8 JML stub; the original C4 handler then RTSes to C4:92A2.
    asm.emit(0xC2, 0x20)  # REP #$20
    asm.emit(0xF4, 0xA1, 0x92)  # PEA $92A1
    asm.emit(0x29, 0x3F, 0x00)  # AND #$003F
    asm.emit(0x0A, 0x0A)  # four-byte stub index
    asm.emit(0x18, 0x69, (STUB_TABLE_CPU - 1) & 0xFF, (STUB_TABLE_CPU - 1) >> 8)
    asm.emit(0x48)  # PHA stub address-1
    asm.emit(0x60)  # RTS into D8 stub
    return asm.resolve()


def make_dispatch_stubs(source: bytes) -> bytes:
    """Build 64 D8 JML stubs matching the original 6-bit dispatch lookup."""

    stubs = bytearray()
    for index in range(TEXT_COMMAND_WORDS):
        offset = TEXT_COMMAND_TABLE_OFFSET + index * 2
        target = int.from_bytes(source[offset : offset + 2], "little")
        stubs.extend((0x5C, target & 0xFF, target >> 8, 0xC4))  # JML C4:target
    return bytes(stubs)


def make_source_calculator() -> bytes:
    """Return D8 offset for native ASCII or one-shot Korean page marker."""

    asm = Assembler()
    # Entry/exit M=16.  $48 low byte D0-D3 means Korean page 0-3 for this
    # glyph only; every other value uses the mirrored native font at D8:8000.
    asm.emit(0x29, 0xFF, 0x00)  # AND #$00FF
    asm.emit(0x0A, 0x0A, 0x0A, 0x0A)  # glyph index * 16
    asm.emit(0x48)  # PHA base offset
    asm.emit(0xA5, 0x48, 0x29, 0xFF, 0x00)  # LDA $48 / AND #$00FF
    asm.emit(0xC9, 0xD0, 0x00)  # CMP #$00D0
    asm.branch8(0x90, "ascii")  # BCC ascii
    asm.emit(0xC9, 0xD4, 0x00)  # CMP #$00D4
    asm.branch8(0xB0, "ascii")  # BCS ascii
    asm.emit(0x38, 0xE9, 0xD0, 0x00)  # page = marker-D0
    for _ in range(13):
        asm.emit(0x0A)  # page * 0x2000
    asm.emit(0x18, 0x63, 0x01)  # CLC / ADC $01,S (index*16)
    asm.emit(0x85, 0x46)  # STA $46
    asm.emit(0x68)  # PLA discard saved base
    asm.branch8(0x80, "reset")

    asm.label("ascii")
    asm.emit(0x68)  # PLA index*16
    asm.emit(0x18, 0x69, 0x00, 0x80)  # native mirror base D8:8000
    asm.emit(0x85, 0x46)

    asm.label("reset")
    asm.emit(0xA9, 0xC8, 0x00, 0x85, 0x48)  # restore original scratch value
    asm.emit(0xA5, 0x46)  # return source offset in A
    asm.emit(0x6B)  # RTL
    return asm.resolve()


def main() -> None:
    source = SOURCE.read_bytes()
    if len(source) != SOURCE_LENGTH:
        raise ValueError(f"expected 0x{SOURCE_LENGTH:X}-byte source")
    if sha256(source) != SOURCE_SHA256:
        raise ValueError("unexpected Robotrek (USA) source hash")
    signatures = (
        (TEXT_DISPATCH_OFFSET, TEXT_DISPATCH_ORIGINAL, "text dispatcher"),
        (FONT_SOURCE_OFFSET, FONT_SOURCE_ORIGINAL, "font source calculator"),
        (DMA_BANK_OFFSET, DMA_BANK_ORIGINAL, "font DMA bank"),
        (DOG_TEXT_OFFSET, DOG_TEXT_ORIGINAL, "dog dialogue"),
    )
    for offset, expected, label in signatures:
        if source[offset : offset + len(expected)] != expected:
            raise ValueError(f"{label} signature mismatch at 0x{offset:06X}")

    dispatcher = make_dispatcher()
    stubs = make_dispatch_stubs(source)
    calculator = make_source_calculator()
    if len(dispatcher) > STUB_TABLE_OFFSET - DISPATCHER_OFFSET:
        raise ValueError("dispatcher overlaps stub table")
    if len(stubs) != 0x100:
        raise AssertionError("64 four-byte dispatch stubs must occupy 0x100 bytes")

    target = bytearray(source)
    target.extend(b"\xFF" * (TARGET_LENGTH - SOURCE_LENGTH))
    # Preserve every native English glyph after changing the fixed DMA bank.
    target[NATIVE_FONT_MIRROR_OFFSET : NATIVE_FONT_MIRROR_OFFSET + NATIVE_FONT_SIZE] = source[
        NATIVE_FONT_SOURCE : NATIVE_FONT_SOURCE + NATIVE_FONT_SIZE
    ]

    glyph, preview = make_narrow_hangul("한")
    target[KOREAN_PAGE0_OFFSET : KOREAN_PAGE0_OFFSET + 16] = glyph[:16]
    target[KOREAN_PAGE0_OFFSET + 0x1000 : KOREAN_PAGE0_OFFSET + 0x1010] = glyph[16:]

    dispatch_patch = bytes((0x5C, DISPATCHER_CPU & 0xFF, DISPATCHER_CPU >> 8, 0xD8))
    dispatch_patch += b"\xEA" * (len(TEXT_DISPATCH_ORIGINAL) - len(dispatch_patch))
    target[TEXT_DISPATCH_OFFSET : TEXT_DISPATCH_OFFSET + len(dispatch_patch)] = dispatch_patch

    source_patch = bytes((0x22, SOURCE_CALCULATOR_CPU & 0xFF, SOURCE_CALCULATOR_CPU >> 8, 0xD8))
    source_patch += bytes((0x85, 0x46))
    source_patch += b"\xEA" * (len(FONT_SOURCE_ORIGINAL) - len(source_patch))
    target[FONT_SOURCE_OFFSET : FONT_SOURCE_OFFSET + len(source_patch)] = source_patch
    target[DMA_BANK_OFFSET : DMA_BANK_OFFSET + len(DMA_BANK_ORIGINAL)] = bytes.fromhex(
        "A9 D8 8D 04 43"
    )

    target[DISPATCHER_OFFSET : DISPATCHER_OFFSET + len(dispatcher)] = dispatcher
    target[STUB_TABLE_OFFSET : STUB_TABLE_OFFSET + len(stubs)] = stubs
    target[SOURCE_CALCULATOR_OFFSET : SOURCE_CALCULATOR_OFFSET + len(calculator)] = calculator
    target[DOG_TEXT_OFFSET : DOG_TEXT_OFFSET + len(DOG_TEXT_PROBE)] = DOG_TEXT_PROBE
    checksum = refresh_full_hirom_checksum(target)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(target)
    preview.resize((8 * 12, 16 * 12), Image.Resampling.NEAREST).save(PREVIEW)

    manifest = {
        "kind": "Robotrek USA E4/D8 one-glyph runtime probe",
        "source": SOURCE.name,
        "source_sha256": SOURCE_SHA256,
        "output": str(OUTPUT.relative_to(ROOT)),
        "output_sha256": sha256(target),
        "source_size": len(source),
        "target_size": len(target),
        "encoding_tested": "E4 00 -> D8:0000 top tile + D8:1000 bottom tile",
        "visible_glyph": "한",
        "dialogue_offset": f"0x{DOG_TEXT_OFFSET:06X}",
        "dialogue_bytes": DOG_TEXT_PROBE.hex(" ").upper(),
        "patches": {
            "text_dispatch": f"0x{TEXT_DISPATCH_OFFSET:06X}",
            "font_source": f"0x{FONT_SOURCE_OFFSET:06X}",
            "dma_bank": f"0x{DMA_BANK_OFFSET:06X}",
            "dispatcher": f"0x{DISPATCHER_OFFSET:06X} ({len(dispatcher)} bytes)",
            "dispatch_stubs": f"0x{STUB_TABLE_OFFSET:06X} ({len(stubs)} bytes)",
            "source_calculator": f"0x{SOURCE_CALCULATOR_OFFSET:06X} ({len(calculator)} bytes)",
            "native_font_mirror": "0x188000-0x189FFF",
        },
        "header_checksum": f"0x{checksum:04X}",
        "scope": [
            "one fixed-size dialogue payload",
            "E4-E7 text command hook",
            "D8 font source selection",
            "original native English font mirrored unchanged",
        ],
        "excluded": ["dialogue relocation", "pointer changes", "event changes", "item/menu translation"],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

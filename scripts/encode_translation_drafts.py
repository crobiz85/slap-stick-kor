"""Encode Korean draft rows into the game's byte stream for preflight only.

The output is a build report.  It never writes ROM bytes, because strings that
do not fit in their original slots still need relocation/pointer work.
"""

from pathlib import Path
import argparse
import re

from decode_japanese_strings import HIRAGANA, KATAKANA


ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "translation" / "script.tsv"
GLYPH_MAP_PATH = ROOT / "translation" / "korean-glyph-map.tsv"
DEFAULT_OUTPUT_PATH = ROOT / "build" / "draft-encoded.tsv"

TOKEN = re.compile(r"\[(?P<name>[A-Z0-9]+)(?::(?P<params>[0-9A-F]+))?\]")
CONTROL_BYTES = {
    "END": b"\xC0",
    "CLR": b"\xD0",
    "FIN": b"\xD1",
    "WAI": b"\xD2",
    "JMP": b"\xD3",
    "DF4": b"\xD8",
    "KATAKANA": b"\xD4",
    "HIRAGANA": b"\xD5",
    "DFT": b"\xD7",
    "NXT": b"\xDC",
    "TER": b"\xCC",
}
PARAM_BYTES = {
    "POS": (0xC1, 2),
    "NAM": (0xC2, 1),
    "PAL": (0xC3, 1),
    "PAU": (0xC9, 1),
    "DF2": (0xD6, 1),
    "DLY": (0xDA, 1),
    "STR": (0xCF, 3),
    "TPL": (0xDE, 1),
    "TBL": (0xC5, 4),
    "NUM": (0xC6, 3),
    "BOX": (0xC7, 3),
    "DEC": (0xDD, 4),
    # The decoder labels opcode E0 as E2; it has a two-byte argument and is
    # used by the first in-game cutscene.
    "E2": (0xE0, 2),
    # This is a distinct in-game button prompt opcode.  The source ROM uses
    # the literal E2 byte followed by a two-byte glyph payload; do not confuse
    # it with the decoder's E0-labelled E2 control above.
    "BTN": (0xE2, 2),
}


def read_glyph_map(path: Path = GLYPH_MAP_PATH) -> dict[str, bytes]:
    mapping = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 3:
            continue
        mapping[columns[0]] = bytes.fromhex(columns[2])
    return mapping


def read_drafts() -> dict[str, tuple[int, str]]:
    drafts = {}
    for line in SCRIPT_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 7 or columns[6] != "draft-ko" or not columns[5]:
            continue
        drafts[columns[0]] = (int(columns[2], 16), columns[5])
    return drafts


def encode_text(text: str, glyphs: dict[str, bytes], glyph_lead_byte: int | None = None) -> bytes:
    output = bytearray()
    layer = HIRAGANA
    position = 0
    while position < len(text):
        if text[position] == "\\" and text[position : position + 2] == "\\n":
            output.append(0xCD)
            position += 2
            continue

        if text[position] == "[":
            match = TOKEN.match(text, position)
            if not match:
                raise ValueError(f"invalid control token near {text[position:]}")
            name = match.group("name")
            params = match.group("params")
            if name in CONTROL_BYTES:
                output.extend(CONTROL_BYTES[name])
                if name == "KATAKANA":
                    layer = KATAKANA
                elif name == "HIRAGANA":
                    layer = HIRAGANA
            elif name in PARAM_BYTES:
                opcode, expected_length = PARAM_BYTES[name]
                if params is None or len(params) != expected_length * 2:
                    raise ValueError(f"bad {name} parameter length: {params}")
                output.append(opcode)
                output.extend(bytes.fromhex(params))
            elif name == "CMD":
                if params is None or len(params) != 2:
                    raise ValueError(f"bad CMD parameter length: {params}")
                output.extend(bytes.fromhex(params))
            else:
                raise ValueError(f"unsupported control token: {match.group(0)}")
            position = match.end()
            continue

        character = text[position]
        if character in glyphs:
            if glyph_lead_byte is None:
                output.extend(glyphs[character])
            else:
                output.extend((glyph_lead_byte, glyphs[character][1]))
        elif character == ".":
            output.append(HIRAGANA.index("˳"))
        elif character == ",":
            output.append(HIRAGANA.index("ˎ"))
        elif character == "…":
            output.extend((HIRAGANA.index("·"),) * 3)
        elif character in layer:
            output.append(layer.index(character))
        else:
            raise ValueError(f"no game glyph for {character!r}")
        position += 1
    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight-encode Korean draft rows without modifying the ROM.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    glyphs = read_glyph_map()
    drafts = read_drafts()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Preflight only; encoded bytes are not yet a ROM patch.\n")
        handle.write("# id\toriginal length\tencoded length\tfits\tencoded bytes\terror\n")
        for entry_id in sorted(drafts):
            original_length, korean = drafts[entry_id]
            try:
                encoded = encode_text(korean, glyphs)
                fits = "yes" if len(encoded) <= original_length else "no"
                error = ""
                encoded_hex = encoded.hex(" ").upper()
            except ValueError as exc:
                fits = "error"
                error = str(exc)
                encoded_hex = ""
                encoded = b""
            handle.write(
                f"{entry_id}\t{original_length:04X}\t{len(encoded):04X}\t{fits}\t"
                f"{encoded_hex}\t{error}\n"
            )

    print(f"encoded={len(drafts)}")
    print(args.output)


if __name__ == "__main__":
    main()

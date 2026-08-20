"""Annotate known control-code candidates without decoding character bytes.

The Japanese ROM's text stream is not safe to render as ASCII or Shift-JIS
yet.  This tool therefore keeps the raw bytes and only labels controls that
are supported by repeated ROM patterns and the Robotrek hacking notes.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "translation" / "text-blocks-raw.tsv"
OUTPUT_PATH = ROOT / "translation" / "control-annotated.tsv"

CONTROL_LENGTHS = {
    0xC0: 1,
    0xC2: 2,
    0xC3: 2,
    0xCD: 1,
    0xD1: 1,
    0xCC: 1,
}

CONTROL_NAMES = {
    0xC0: "DIALOG_END?",
    0xC2: "VARIABLE?",
    0xC3: "COLOR",
    0xCD: "LINE_BREAK?",
    0xD1: "NEXT_PAGE?",
    0xCC: "RECORD_END",
}

COLOR_NAMES = {
    0x00: "white",
    0x02: "yellow",
    0x03: "pink",
}


def annotate(payload: bytes) -> str:
    tokens: list[str] = []
    index = 0
    while index < len(payload):
        value = payload[index]
        if value == 0xC3 and index + 1 < len(payload):
            color = payload[index + 1]
            label = COLOR_NAMES.get(color, f"0x{color:02X}")
            tokens.append(f"[COLOR:{label}]")
            index += 2
            continue
        if value == 0xC2 and index + 1 < len(payload):
            tokens.append(f"[VARIABLE:0x{payload[index + 1]:02X}]")
            index += 2
            continue
        if value in CONTROL_NAMES:
            tokens.append(f"[{CONTROL_NAMES[value]}]")
            index += CONTROL_LENGTHS[value]
            continue
        if value == 0x20:
            tokens.append(" ")
        else:
            tokens.append(f"<{value:02X}>")
        index += 1
    return "".join(tokens)


def main() -> None:
    rows = []
    for line in INPUT_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 4:
            continue
        offset, length, raw_hex = columns[:3]
        payload = bytes.fromhex(raw_hex)
        rows.append((offset, length, payload))

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Known controls are annotated; character bytes remain undecoded.\n")
        handle.write("# offset\tlength\traw bytes\tcontrol annotation\n")
        for offset, length, payload in rows:
            handle.write(
                f"{offset}\t{length}\t{payload.hex(' ').upper()}\t{annotate(payload)}\n"
            )

    print(f"annotated={len(rows)}")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()

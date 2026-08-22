"""Create a local ROM used only to verify the visible Korean font route.

The production preview intentionally leaves the opening sequence untranslated.
For a deterministic emulator check, this tool replaces the early story record
0057 with a short Korean line using the production glyph map.  The generated
ROM is written under build/ (ignored by Git) and is never distributed.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from encode_translation_drafts import encode_text, read_glyph_map  # noqa: E402


SOURCE = ROOT / "build" / "slap-stick-kor-preview.smc"
OUTPUT = ROOT / "build" / "font-route-smoke.smc"
OFFSET = 0x04EE09
SLOT_LENGTH = 0x5F


def main() -> None:
    target = bytearray(SOURCE.read_bytes())
    payload = encode_text("[NXT]로봇[END]", read_glyph_map())
    if len(payload) > SLOT_LENGTH:
        raise ValueError("font-route smoke text exceeds the original story slot")
    target[OFFSET : OFFSET + SLOT_LENGTH] = b" " * SLOT_LENGTH
    target[OFFSET : OFFSET + len(payload)] = payload
    OUTPUT.write_bytes(target)
    print(f"ROM={OUTPUT}")
    print(f"offset=0x{OFFSET:06X} bytes={payload.hex(' ').upper()}")


if __name__ == "__main__":
    main()

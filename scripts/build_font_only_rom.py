"""Build a font-only Korean test ROM from the clean Japanese Slap Stick ROM.

This deliberately does not patch dialogue, menus, pointers, map labels, event
data, graphics, or opening data.  It only copies the generated 16x16 Korean
glyph tiles into the verified font-page slots listed in the glyph map.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "Slap Stick (J).smc"
DEFAULT_MAP = ROOT / "translation" / "korean-glyph-map.tsv"
DEFAULT_OUTPUT = ROOT / "build" / "slap-stick-kor-font-only.smc"
DEFAULT_MANIFEST = ROOT / "build" / "slap-stick-kor-font-only.json"
GLYPH_BYTES = 64
FONT_RANGES = (
    (0x50000, 0x54000),
    (0x54000, 0x58000),
    (0x60000, 0x64000),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_glyph_rows(path: Path) -> list[tuple[str, int, bytes]]:
    rows: list[tuple[str, int, bytes]] = []
    seen_offsets: set[int] = set()
    seen_codes: set[bytes] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 5:
            raise ValueError(f"{path}:{line_number}: expected five columns")
        character = columns[0]
        code = bytes.fromhex(columns[2])
        offset = int(columns[3], 16)
        tile = bytes.fromhex(columns[4])
        if len(code) != 2:
            raise ValueError(f"{path}:{line_number}: invalid code bytes")
        if len(tile) != GLYPH_BYTES:
            raise ValueError(f"{path}:{line_number}: expected {GLYPH_BYTES} tile bytes")
        if offset in seen_offsets:
            raise ValueError(f"{path}:{line_number}: duplicate file offset 0x{offset:06X}")
        if code in seen_codes:
            raise ValueError(f"{path}:{line_number}: duplicate code {code.hex(' ').upper()}")
        if not any(start <= offset and offset + GLYPH_BYTES <= end for start, end in FONT_RANGES):
            raise ValueError(f"{path}:{line_number}: offset 0x{offset:06X} is outside verified font pages")
        seen_offsets.add(offset)
        seen_codes.add(code)
        rows.append((character, offset, tile))
    return rows


def build(source_path: Path, map_path: Path, output_path: Path, manifest_path: Path) -> None:
    source = source_path.read_bytes()
    target = bytearray(source)
    rows = read_glyph_rows(map_path)
    changed_offsets: list[dict[str, object]] = []
    changed_bytes = 0
    for character, offset, tile in rows:
        original = bytes(source[offset : offset + GLYPH_BYTES])
        target[offset : offset + GLYPH_BYTES] = tile
        changed_bytes += sum(a != b for a, b in zip(original, tile))
        changed_offsets.append(
            {
                "character": character,
                "offset": f"0x{offset:06X}",
                "changed_bytes": sum(a != b for a, b in zip(original, tile)),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(target)
    manifest = {
        "kind": "Slap Stick Korean font-only test ROM",
        "source": str(source_path.relative_to(ROOT)),
        "source_sha256": sha256(source),
        "target": str(output_path.relative_to(ROOT)),
        "target_sha256": sha256(target),
        "source_length": len(source),
        "target_length": len(target),
        "glyph_map": str(map_path.relative_to(ROOT)),
        "glyph_count": len(rows),
        "changed_bytes": changed_bytes,
        "scope": ["font glyph tiles only"],
        "excluded": ["dialogue", "menus", "pointers", "events", "map labels", "opening", "background graphics"],
        "glyphs": changed_offsets,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("source_sha256", "target_sha256", "glyph_count", "changed_bytes")}, indent=2))
    print(output_path)
    print(manifest_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a font-only Korean Slap Stick ROM")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--glyph-map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    build(
        args.source.resolve(),
        args.glyph_map.resolve(),
        args.output.resolve(),
        args.manifest.resolve(),
    )


if __name__ == "__main__":
    main()

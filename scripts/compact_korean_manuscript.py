"""Create a conservative, reviewable compact Korean C0 manuscript.

Only explicit phrase rewrites are used here.  The goal is to recover a few
bytes in fixed-size dialogue slots without performing broad grammar-changing
replacements such as turning every formal sentence into casual speech.
"""

from __future__ import annotations

from pathlib import Path
import argparse

from encode_translation_drafts import encode_text, read_glyph_map


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "translation" / "korean-c0-manuscript.tsv"
DEFAULT_OUTPUT = ROOT / "translation" / "korean-c0-manuscript-compact.tsv"
DEFAULT_REPORT = ROOT / "build" / "korean-c0-manuscript-compaction.tsv"
DEFAULT_GLYPH_MAP = ROOT / "translation" / "korean-glyph-map-hangul.tsv"
DEFAULT_CANONICAL = ROOT / "translation" / "korean-c0-dialogue.tsv"


# Ordered longest-first rewrites.  These are intentionally phrase-specific so
# that words such as 무엇이었는지 do not become the malformed 뭐가었는지.
REWRITES = (
    ("무엇이었는지", "뭐였는지"),
    ("개를 찾아줘!", "개 찾아줘!"),
    ("개가 약을 갖고 있대.", "개가 약 갖고 있대."),
    ("기다려 주세요", "기다려 줘"),
    ("말해 주세요", "말해 줘"),
    ("알려 주세요", "알려 줘"),
    ("찾아 주세요", "찾아 줘"),
    ("도와 주세요", "도와 줘"),
    ("기다려주세요", "기다려줘"),
    ("말해주세요", "말해줘"),
    ("알려주세요", "알려줘"),
    ("찾아주세요", "찾아줘"),
    ("도와주세요", "도와줘"),
    ("부탁드립니다", "부탁해요"),
    ("부탁할게요", "부탁할게"),
    ("부탁할게", "부탁해"),
    ("주십시오", "줘"),
    ("무엇을", "뭘"),
    ("무엇이", "뭐가"),
    ("그것을", "그걸"),
    ("이것을", "이걸"),
    ("저것을", "저걸"),
    ("하는 것이", "하는 게"),
    ("할 것이", "할 게"),
    ("있는 것이", "있는 게"),
    ("그렇지만", "하지만"),
    ("그러니까", "그러니"),
    ("그런데", "근데"),
    ("왜 이렇게", "왜 이리"),
    ("우리들은", "우린"),
    ("너희들은", "너희는"),
    ("하지 않으면", "안 하면"),
    ("것은", "건"),
    ("것을", "걸"),
)


def compact_text(text: str) -> tuple[str, list[tuple[str, str]]]:
    result = text
    applied: list[tuple[str, str]] = []
    for old, new in REWRITES:
        if old not in result:
            continue
        result = result.replace(old, new)
        applied.append((old, new))
    return result, applied


def read_canonical_texts(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) >= 4:
            result[columns[0]] = columns[3]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a conservative compact Korean manuscript")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--glyph-map", type=Path, default=DEFAULT_GLYPH_MAP)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    args = parser.parse_args()

    glyphs = read_glyph_map(args.glyph_map.resolve())
    canonical_texts = read_canonical_texts(args.canonical.resolve())
    output_lines: list[str] = []
    report_rows: list[tuple[str, str, str, str, str, int, int, int]] = []
    changed = 0
    saved = 0

    for line in args.input.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            output_lines.append(line)
            continue
        columns = line.split("\t")
        if len(columns) < 8:
            raise ValueError(f"expected eight columns: {line}")
        # Match the effective text used by the ROM builders: the canonical
        # reviewed subset takes precedence over the manuscript row, then the
        # conservative compaction is applied to that effective text.
        before = canonical_texts.get(columns[0], columns[3])
        after, applied = compact_text(before)
        columns[3] = after
        output_lines.append("\t".join(columns))
        if not applied or before == after:
            continue
        try:
            before_length = len(encode_text(before, glyphs))
            after_length = len(encode_text(after, glyphs))
            row_saved = before_length - after_length
        except ValueError:
            # Some manuscript rows intentionally contain glyphs not in the
            # current preview map.  Keep the compact text, but leave byte
            # accounting blank until that row is assigned a glyph.
            before_length = ""
            after_length = ""
            row_saved = ""
        changed += 1
        if isinstance(row_saved, int):
            saved += row_saved
        report_rows.append(
            (
                columns[0],
                columns[1],
                columns[4],
                before,
                after,
                before_length,
                after_length,
                row_saved,
            )
        )

    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    with args.report.resolve().open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Conservative phrase-level compaction report. Lengths are encoded bytes.\n")
        handle.write("# id\toffset\tcategory\tbefore\tafter\tbefore length\tafter length\tsaved\n")
        for row in report_rows:
            handle.write("\t".join(str(value) for value in row) + "\n")

    print(f"changed_rows={changed}")
    print(f"saved_encoded_bytes={saved}")
    print(f"manuscript={args.output.resolve()}")
    print(f"report={args.report.resolve()}")


if __name__ == "__main__":
    main()

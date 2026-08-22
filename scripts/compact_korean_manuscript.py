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

# These rows contain control bytes that the generic Korean manuscript cannot
# express safely.  The RAW prefixes below were copied from the verified
# original C0 records through their first DFT opcode; only the visible text
# after that point is replaced.  The marker in column 8 makes the relocation
# builder treat the row as reviewed rather than restoring the Japanese slot.
CONTROL_SAFE_OVERRIDES = {
    "C0-058AA3": (
        "[DFT]오빠, 그 집에 이사 왔지?\\n"
        "[PAL:02][BTN:8000][KATAKANA]버튼[HIRAGANA]으로\\n"
        "[KATAKANA]차임[HIRAGANA]을 울리는 거야.[PAL:00][FIN]\\n\\n"
        "답례는 이사 떡이면 충분하니까˳",
        "safe:restored-fin",
    ),
    "C0-05DADC": (
        "[RAW:DADA028000029780F5026202000BDB020BC88001DB020B2080FCDA021D10DB6B021D6DDB6B021D39DB6B021D98DB6B021DC5DB6BD7]"
        "촌장님은 바빠.\\n할 말은\\n간단히.",
        "safe:preserved-original-controls",
    ),
    "C0-05E67E": (
        "[DFT][E2:053F]예전 발명품은\\n자원을 많이 써.\\n재능 차이지.",
        "safe:normalized-terminal-punctuation",
    ),
    "C0-06B72E": (
        "[DFT]으[KATAKANA]ー[HIRAGANA]앙!\\n[PAU:1E]안 움직여!",
        "safe:restored-pause",
    ),
    "C0-07D767": (
        "[RAW:D03C00021D7DD7][E2:0FDC]············\\n"
        "[PAU:1E]···[NXT]가[KATAKANA]아키하바라[HIRAGANA] 군···˳",
        "safe:preserved-original-controls",
    ),
    "C0-07E786": (
        "[RAW:DA020A6903020A6A8302CF1EE7876B021DCBE86BD7]"
        "벽을 부숴!\\n[PAU:0A]뒤로!",
        "safe:preserved-original-controls",
    ),
    "C0-06C96A": (
        "[DFT][E2:0F5D]미안하지만\\n[PAL:02]빈방[PAL:00]에서\\n잠깐 쉴게.[FIN]볼일 있으면 오게.\\n"
        "[PAU:1E]\\n에고, 정말\\n미안하군.",
        "safe:shortened-inline",
    ),
    "C0-05F548": (
        "[DFT][E2:0147]멋진 [E2:1A00]이 됐네.\\n"
        "정비와 파워 업은 발명 머신으로 해.[FIN]\\n"
        "[PAL:02][E2:1A53]강도도 프로그램할 수 있어.[PAL:00]\\n"
        "시험해 봐.[FIN]\\n"
        "선물이야. 소형 트랜시버야.\\n"
        "어디서든 내게 연락할 수 있어.[FIN]\\n"
        "용건이 있으면 써.\\n"
        "[PAL:02]장비하고 [BTN:0040]버튼을 누르면 돼.[FIN][PAL:00]\\n"
        "[NAM:00]은 [PAL:02]트랜시버[PAL:00]를 받았다![TER]\\n"
        "[DFT]나도 필요할 땐\\n"
        "이걸 써서[RAW:81]",
        "safe:restored-byte",
    ),
}


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
        override = CONTROL_SAFE_OVERRIDES.get(columns[0])
        if override is not None:
            after = override[0]
            columns[7] = override[1]
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

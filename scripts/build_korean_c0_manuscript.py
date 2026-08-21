"""Merge the canonical C0 drafts and the reviewed manuscript batches.

This file is the translation source of truth.  It is intentionally separate
from the inline ROM builder: a manuscript can be complete even when a line is
longer than its Japanese slot or still needs a relocated font page.
"""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "translation" / "c0-dialogue-catalog.tsv"
CURRENT = ROOT / "translation" / "korean-c0-dialogue.tsv"
BATCH = ROOT / "translation" / "korean-c0-manuscript-early.tsv"
OUTPUT = ROOT / "translation" / "korean-c0-manuscript.tsv"


def rows(path: Path) -> list[list[str]]:
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        result.append(line.split("\t"))
    return result


def controls(text: str) -> set[str]:
    return {name for name, _args in re.findall(r"\[([A-Z0-9]+)(?::([^]]+))?\]", text)}


def main() -> None:
    catalog = {}
    for cols in rows(CATALOG):
        catalog[cols[0]] = {"offset": cols[1], "length": cols[2], "jp": cols[4]}

    merged = {}
    for cols in rows(CURRENT):
        if len(cols) < 5:
            raise ValueError(f"bad canonical row: {cols}")
        merged[cols[0]] = {
            "text": cols[3],
            "category": cols[4],
            "status": "draft-existing",
            "source": "korean-c0-dialogue.tsv",
        }
    for cols in rows(BATCH):
        if len(cols) < 4:
            raise ValueError(f"bad batch row: {cols}")
        merged[cols[0]] = {
            "text": cols[1],
            "category": cols[2],
            "status": cols[3],
            "source": BATCH.name,
        }

    unknown = sorted(set(merged) - set(catalog))
    if unknown:
        raise ValueError(f"manuscript IDs missing from catalog: {', '.join(unknown)}")

    warnings = []
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Complete Korean manuscript assembled from reviewed C0 translation batches.\n")
        handle.write("# id\tfile offset\toriginal length\tKorean translation\tcategory\tstatus\tsource\tcontrol review\n")
        for entry_id, meta in sorted(merged.items(), key=lambda item: int(catalog[item[0]]["offset"], 16)):
            cat = catalog[entry_id]
            source_controls = controls(cat["jp"])
            target_controls = controls(meta["text"])
            # The decoder exposes the original button/icon sequence as
            # [CMD:E2], while the encoder needs its actual two-byte E2
            # argument.  Treat the normalized form as equivalent here.
            if "CMD" in source_controls and "E2" in target_controls:
                source_controls.remove("CMD")
            missing = sorted(source_controls - target_controls)
            note = "ok" if not missing else "missing:" + ",".join(missing)
            if missing:
                warnings.append((entry_id, missing))
            handle.write(
                f"{entry_id}\t{cat['offset']}\t{cat['length']}\t{meta['text']}\t"
                f"{meta['category']}\t{meta['status']}\t{meta['source']}\t{note}\n"
            )

    print(f"manuscript_rows={len(merged)}")
    print(f"new_batch_rows={sum(entry_id in {cols[0] for cols in rows(BATCH)} for entry_id in merged)}")
    print(f"control_warnings={len(warnings)}")
    for entry_id, missing in warnings[:20]:
        print(f"warning {entry_id}: missing {','.join(missing)}")
    print(OUTPUT)


if __name__ == "__main__":
    main()

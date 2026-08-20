"""Decode Slap Stick's Japanese string stream using the published JP table.

The table is documented at Data Crystal's Robotrek/Strings JP page.  The ROM
stores ordinary kana/Latin bytes directly, dictionary entries as 80/81/82
followed by an index, and a small command range from C0 upward.
"""

from pathlib import Path
import argparse


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_PATH = ROOT / "translation" / "text-blocks-raw.tsv"
DEFAULT_OUTPUT_PATH = ROOT / "translation" / "decoded-text-blocks.tsv"


def build_layer(prefix: str, upper: str, kana: str, small: str, suffix: str) -> list[str]:
    values = list(prefix + " " + upper + kana + small + suffix)
    if len(values) != 0x80:
        raise ValueError(f"bad layer length: {len(values):02X}")
    return values


HIRAGANA = build_layer(
    "がぎぐげござじずぜぞだぢづでど?┌┘()ばびぶべぼぱぴぷぺぽˎ˳",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん",
    "ぁぃぅぇぉっゃゅょゎ",
    "0123456789!·:",
)

# The source table has one two-codepoint glyph at index 1F (a combining
# mark plus a quote).  A placeholder keeps all following byte positions
# aligned while making the unusual glyph explicit in decoded text.
KATAKANA = (
    list("ガギグゲゴザジズゼゾダヂヅデド…→←↑↓バビブベボパピプペポ\"")
    + ["̋”", "※"]
    + list("abcdefghijklmnopqrstuvwxyz")
    + list("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン")
    + list("ァィゥェォッャュョヮ")
    + list("ー╳%=╔╝*+-/&. ")
)
if len(KATAKANA) != 0x80:
    raise ValueError(f"bad katakana layer length: {len(KATAKANA):02X}")


# The three in-ROM dictionaries are indexed by the byte following 80/81/82.
# They are copied from the JP string definition, including a few special glyphs.
DICTIONARIES = {
    0x80: "名前技合計集▌▐使必要回復裝備選来買売説明戦闘登場順空番中実行背画面上作業顔今発新ŁⅨ成台持十分終入力冒険消手半書研究所通信電波状態悪大音出人注意型岩身自姿効果変穴話敵見家事全般日曜工貸森花道不飛機步土地移動乘宇宙星用物塞止赤青黄色宝石紙版幹部思誄光放玉南島村長質置元減時天気在操品箱捨目ⅠⅡⅢⅣⅤⅥⅦⅧ員町助極楽過去開室警察具屋下水路口港博士漁師河原幽停車司令財庫迷幽霊西館塔先祖樣墓農船着密林宿火山調理食堂秘私震生會受付雪航設驗会本語教居住区号貨兵休息倉処心小留守何太陽一度帰店近辺々現報役砂危立才対策訪談予",
    0x81: "定遊子供方協金週題仕年好評判知切言安失敗同当残念取材特伝待最真的彼正体多件記者別礼相奴間木白昔練早犬重後以若外困追問少惑命割男落板聞旅支平和君有無料招視鳥主強耳夢急角起女案内客常夏感謝郊読勉経得爆張進配雑血代初友改造返荷由高王軍団表姫借法数片希望苦労勝娘反仲關係遠声世病味美芸能考黒服首月古門他神底決頭冷給科学例救疑父親職禁次期民退治副官隊我根朝接紀格位資源完写点欲與両寄商義像結局久呼雨告孫二制利校拾連続攻擊識第費忘組錄武器卵帳亡妻似幼母功海右公運修寒悲倍単左準字保委彈証収直貫破然流川愛泣俺鉄球始余働末温整故",
    0x82: "草泉純負兄文句景向形足化幸加藥再喜暗界求申百忠建井戸恐卷著可解三満階四肉未拝遺產弱虫痛死送恩熱粉裹男性情応答観統属胸探志算聖営管都便願野專增械每逆飯腹暴速印葉参達試絕営鳴静製陸漢図席酒罪列独条短衣存細茶夜損活橋側展将枚馬骨走省広構非齒引承各総術仮映臓刀縁市砲巨座責任油標永害風良投笑育査限",
}


CONTROL_LENGTHS = {
    0xC1: 2, 0xC2: 1, 0xC3: 1, 0xC5: 4, 0xC6: 3, 0xC7: 3,
    0xC9: 1, 0xCE: 1, 0xCF: 3, 0xD4: 0, 0xD5: 0, 0xDA: 1,
    0xDD: 4, 0xDE: 1, 0xE0: 2, 0xE1: 1,
}

CONTROL_NAMES = {
    0xC0: "END", 0xC1: "POS", 0xC2: "NAM", 0xC3: "PAL", 0xC4: "PGE",
    0xC5: "TBL", 0xC6: "NUM", 0xC7: "BOX", 0xC8: "DES", 0xC9: "PAU",
    0xCA: "CA", 0xCB: "CB", 0xCC: "TER", 0xCD: "N", 0xCE: "SKP",
    0xCF: "STR", 0xD0: "CLR", 0xD1: "FIN", 0xD2: "WAI", 0xD3: "JMP",
    0xD4: "KATAKANA", 0xD5: "HIRAGANA", 0xD6: "DF2", 0xD7: "DFT",
    0xD8: "DF4", 0xD9: "DF5", 0xDA: "DLY", 0xDB: "DD", 0xDC: "NXT",
    0xDD: "DEC", 0xDE: "TPL", 0xDF: "ESC", 0xE0: "E2", 0xE1: "E3",
}


def decode(payload: bytes) -> str:
    output: list[str] = []
    layer = HIRAGANA
    index = 0
    while index < len(payload):
        value = payload[index]

        if value < 0x80:
            output.append(layer[value])
            index += 1
            continue

        if value in DICTIONARIES and index + 1 < len(payload):
            dictionary_index = payload[index + 1]
            entries = DICTIONARIES[value]
            output.append(entries[dictionary_index] if dictionary_index < len(entries) else f"[D{value:02X}:{dictionary_index:02X}]")
            index += 2
            continue

        if value < 0xC0:
            output.append(f"[BYTE:{value:02X}]")
            index += 1
            continue

        name = CONTROL_NAMES.get(value, f"CMD:{value:02X}")
        length = CONTROL_LENGTHS.get(value, 0)
        params = payload[index + 1 : index + 1 + length]
        if value == 0xC2 and params:
            output.append(f"[NAM:{params[0]:02X}]")
        elif value == 0xC3 and params:
            output.append(f"[PAL:{params[0]:02X}]")
        elif value in (0xD4, 0xD5):
            layer = KATAKANA if value == 0xD4 else HIRAGANA
            output.append(f"[{name}]")
        elif value == 0xCD:
            output.append("\\n")
        elif value == 0xCC:
            output.append("[TER]")
        elif length:
            output.append(f"[{name}:{params.hex().upper()}]")
        else:
            output.append(f"[{name}]")
        index += 1 + length
    return "".join(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Decode Slap Stick Japanese string candidates.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    rows = []
    for line in args.input.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 3:
            continue
        raw_index = next(
            (index for index, value in enumerate(columns) if value and all(len(token) == 2 for token in value.split())),
            None,
        )
        if raw_index is None and len(columns) >= 4 and not columns[3]:
            raw_index = 3
        if raw_index is None:
            continue
        payload = bytes.fromhex(columns[raw_index]) if columns[raw_index] else b""
        rows.append((columns[:raw_index], payload))

    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Japanese decode using Data Crystal Robotrek/Strings JP definitions.\n")
        handle.write("# source fields\traw bytes\tdecoded text\n")
        for fields, payload in rows:
            prefix = "\t".join(fields)
            handle.write(f"{prefix}\t{payload.hex(' ').upper()}\t{decode(payload)}\n")

    print(f"decoded={len(rows)}")
    print(args.output)


if __name__ == "__main__":
    main()

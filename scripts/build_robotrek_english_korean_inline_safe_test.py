"""Build a no-relocation Korean dialogue test for Robotrek (USA)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_robotrek_english_korean_safe_test as common  # noqa: E402
from build_robotrek_e4_d8_single_probe import (  # noqa: E402
    DISPATCHER_CPU,
    DISPATCHER_OFFSET,
    DMA_BANK_OFFSET,
    DMA_BANK_ORIGINAL,
    FONT_SOURCE_OFFSET,
    FONT_SOURCE_ORIGINAL,
    NATIVE_FONT_MIRROR_OFFSET,
    NATIVE_FONT_SIZE,
    NATIVE_FONT_SOURCE,
    SOURCE,
    SOURCE_CALCULATOR_CPU,
    SOURCE_CALCULATOR_OFFSET,
    SOURCE_LENGTH,
    SOURCE_SHA256,
    STUB_TABLE_OFFSET,
    TARGET_LENGTH,
    TEXT_DISPATCH_OFFSET,
    TEXT_DISPATCH_ORIGINAL,
    make_dispatch_stubs,
    make_dispatcher,
    make_source_calculator,
)
from build_robotrek_english_retranslation_list import (  # noqa: E402
    DRAFTS,
    INDIRECT_CF,
    MIXED_DATA_IDS,
    NON_DIALOGUE_IDS,
)
from robotrek_hirom_utils import refresh_full_hirom_checksum  # noqa: E402


OUTPUT = ROOT / "build" / "robotrek-usa-korean-dialogue-inline-safe-test.sfc"
MANIFEST = ROOT / "build" / "robotrek-usa-korean-dialogue-inline-safe-test.json"
OUTPUT_MAP = ROOT / "build" / "robotrek-usa-korean-dialogue-inline-safe-test-glyph-map.tsv"
CANDIDATES = ROOT / "translation" / "robotrek-english-dialogue-candidates.tsv"

# The main physical catalogue starts at 0x058000, but these genuine
# menu/system messages are used from the beginning of the game.  The other
# D7 hits in the same extraction region are code/graphics false positives.
SUPPLEMENTAL_DRAFTS = {
    "EN-01D18B": "[DFT][NXT][BYTE:01][BYTE:C5][BYTE:06][BYTE:E3][BYTE:76][BYTE:06] 여기선 못 써.",
    "EN-01D1A8": "[DFT][NXT][BYTE:01] [NAM:00] 열쇠 사용.[WAIT][BYTE:C8][TER][CLR][NXT][BYTE:01]아이템 채우기?\n 채우기\n 취소[TER][CLR][NXT][BYTE:01]아이템 정렬?\n 정렬\n 취소[TER][BYTE:C1][BYTE:03][BYTE:1B][BYTE:C7][BYTE:0D][BYTE:01][BYTE:00][NXT][BYTE:01]RUN 키 입력[TER][DFT]\n…손이 안 닿아…",
    "EN-01D953": "[DFT] [NAM:00] [PAL:02][BYTE:C5][BYTE:06][BYTE:E3][BYTE:EA][BYTE:05][PAL:00] 획득![TER][DFT] [NAM:00] [PAL:02][BYTE:C5][BYTE:06][BYTE:E3][BYTE:EA][BYTE:05][PAL:00] 발견![TER][DFT]\n비었다.",
    "EN-01D98B": "[DFT] [NAM:00] [PAL:02][BYTE:C6][BYTE:04][BYTE:EA][BYTE:05] GP[PAL:00] 발견![TER][DFT]\n가방이 꽉 찼다.",
    "EN-01D9BC": "[DFT]\n[NXT][BYTE:07] [BYTE:BA][BYTE:BA][BYTE:BA][BYTE:BA][BYTE:BA][BYTE:BA][BYTE:BA][BYTE:BA][PAU:1E][NXT][BYTE:03]안 열린다?",
    "EN-01D9DE": "[DFT] [NAM:00] [PAL:02][BYTE:C5][BYTE:06][BYTE:E3][BYTE:EE][BYTE:05][PAL:00] 제작법 습득.",
    "EN-01DA03": "[DFT] [NAM:00] [PAL:02][BYTE:C5][BYTE:06][BYTE:E3][BYTE:EE][BYTE:05][PAL:00] 제작법 습득.",
    "EN-01DA4C": "[DFT] [NAM:00] [PAL:02][BYTE:DF][BYTE:01][BYTE:04][BYTE:EA][BYTE:05][PAL:00] 메가 데이터 획득!",
}

# E0 speaker names are stored in a separate pointer table and are rendered
# automatically before dialogue.  They were outside every previous dialogue
# audit, which left labels such as "Mayor:" and "Mint:" in English.
SPEAKER_NAME_DRAFTS = (
    "[PAL:02]테트론[PAL:00]",
    "[PAL:03]나기사:\n[PAL:00]",
    "[PAL:02]아키하바라:\n[PAL:00]",
    "[PAL:02]코테츠:\n[PAL:00]",
    "[PAL:03]민트:\n[PAL:00]",
    "[PAL:02]아인스트 박사:\n[PAL:00]",
    "[PAL:02]쿠로가네:\n[PAL:00]",
    "[PAL:02]칼:\n[PAL:00]",
    "[PAL:02]전투원:\n[PAL:00]",
    "[PAL:02]촌장:\n[PAL:00]",
    "[PAL:02]블랙모어:\n[PAL:00]",
    "[PAL:03]로즈:\n[PAL:00]",
    "[PAL:02]나폴레옹:\n[PAL:00]",
    "[PAL:02]가토:\n[PAL:00]",
    "[PAL:03]티라:\n[PAL:00]",
    "[PAL:02]플라보노:\n[PAL:00]",
    "[PAL:03]폴론:\n[PAL:00]",
    "[PAL:02]라스크:\n[PAL:00]",
    "[PAL:03]쿠키:\n[PAL:00]",
    "[PAL:02]이고르:\n[PAL:00]",
    "[PAL:02]프링키 백작:\n[PAL:00]",
    "[PAL:02]시종:\n[PAL:00]",
    "[PAL:02]닥터 G:\n[PAL:00]",
    "[PAL:02]조수 A:\n[PAL:00]",
    "[PAL:02]노인:\n[PAL:00]",
    "[PAL:02]소장:\n[PAL:00]",
    "로봇",
    "[PAL:02]바이바이 장로[PAL:00]!",
    "로봇",
    "로봇들",
)
SPEAKER_POINTER_TABLE = 0x08D86E
SPEAKER_TEXT_START = 0x08D8AA
SPEAKER_TEXT_END = 0x08DA27

# Complete runtime records discovered outside the original English catalogue.
# Unlike SCREEN_TEXT_PATCHES, these may contain several fixed CC/DE/D3 event
# handoffs.  The dedicated writer below keeps every one at its source address.
RUNTIME_RECORD_PATCHES: tuple[dict[str, object], ...] = ()

RUNTIME_RECORD_PATCHES += (
    {"id": "RUNTIME-09F0A8-ROSE-STEAL-VALUABLES", "start": 0x09F0A8, "end": 0x09F0F0,
     "draft": ("[BOTTOM][SPEAKER:0B]느려![FIN]"
               "귀중품을 빼앗아. 돌아갈 방법을 찾을 수 있어!")},
    {"id": "RUNTIME-09F113-DOOR-CLOSED", "start": 0x09F113, "end": 0x09F12C,
     "draft": "[DFT]문이 굳게 닫혔다."},
    {"id": "RUNTIME-09F197-MOUSE-TOO-HEAVY", "start": 0x09F197, "end": 0x09F1B1,
     "draft": "[DFT]쥐의 힘으론 너무 무겁다."},
    {"id": "RUNTIME-09F1B2-COOKIE-WORRY", "start": 0x09F1B2, "end": 0x09F1F9,
     "draft": ("[DFT][PAL:03]나폴레옹, 가토, 미안해.\n"
               "라스크를 만나러 왔어.\n[BYTE:CE][BYTE:24]쿠키[PAL:00]가 걱정돼.")},
    {"id": "RUNTIME-09F25C-HATCH-CLOSED", "start": 0x09F25C, "end": 0x09F271,
     "draft": "[DFT]\n해치가 닫혀 있다!"},
    {"id": "RUNTIME-09F272-RETURN-FORM", "start": 0x09F272, "end": 0x09F2A6,
     "draft": "[DFT][SPEAKER:0C]왜 그 모습이지?\n원래 모습으로 돌아오지 그래?"},
    {"id": "RUNTIME-09F2BA-ENGINE-SIGN", "start": 0x09F2BA, "end": 0x09F2DD,
     "draft": "[DFT]\n기관실\n비상시에만 사용"},
    {"id": "RUNTIME-09F35D-SPACESHIP-LAUNCH", "start": 0x09F35D, "end": 0x09F446,
     "draft": ("[DFT][SPEAKER:0C][NAM:00]![PAU:14] 쿠키를 봤어?\n"
               "가토가 제정신이 아니야.[FIN]"
               "쿠키와 라스크가 우주선으로 떠나려 해…[DE]"
               "[DFT]움직인다! 미안해, [NAM:00].\n"
               "내가 조종실로 가서 가토의 시선을 끌게![FIN]"
               "10분 안에 엔진을 가동하면 지상으로 돌아갈 수 있어.")},
    {"id": "RUNTIME-09F447-NO-TIME-FOR-FORM", "start": 0x09F447, "end": 0x09F469,
     "draft": "[DFT][NAM:00]!?\n그 모습으로 놀 때가 아니야!"},
)

# Hacker fortress approach and password block.
RUNTIME_RECORD_PATCHES += (
    {"id": "RUNTIME-0CAF1B-MINT-WHAT-NOW", "start": 0x0CAF1B, "end": 0x0CAF49,
     "draft": "[DFT][SPEAKER:03]뭐?[PAU:1E] 또 왜??\n몰라. 네가 해!"},
    {"id": "RUNTIME-0CAF4A-KOTETSU-TRADER", "start": 0x0CAF4A, "end": 0x0CB06A,
     "draft": ("[DFT][SPEAKER:08]왔군, 코테츠. 오랜만이야.\n장사가 안 되나 봐.[FIN]"
               "[SPEAKER:03]농담 마. 네게 줄 물건을 모아 왔어.[DE]"
               "[DFT][SPEAKER:08]…응?[PAU:1E] 누구지?[FIN]"
               "[SPEAKER:03]아… 내 제자야. 잘 기억해 둬.[FIN]"
               "네가 좋아할 물건도 가져왔지. [PAL:03]무[PAU:14]후[PAU:14]후[PAL:00]도.[DE]"
               "[DFT][SPEAKER:08]뭐!?[PAU:1E] [PAL:03]무후후[PAL:00]!\n보여 줘.")},
    {"id": "RUNTIME-0CB0C0-JOIN-HACKERS", "start": 0x0CB0C0, "end": 0x0CB0FB,
     "draft": "[DFT]저런 자 밑에선 힘들지.\n해커에 들어오는 게 어때?"},
    {"id": "RUNTIME-0CB0FC-MARTIAL-LAW", "start": 0x0CB0FC, "end": 0x0CB182,
     "draft": ("[DFT]뭐? 코테츠의 제자?\n계엄 중이라 내보낼 수 없어.[FIN]"
               "코테츠? 절박한 얼굴로 저쪽에 뛰어갔어.[FIN]어디 갔다 왔지?")},
    {"id": "RUNTIME-0CB1A8-AUTHORIZED-ONLY", "start": 0x0CB1A8, "end": 0x0CB1C3,
     "draft": "[DFT]관계자 외 출입 금지!"},
    {"id": "RUNTIME-0CB27A-SOLDIERS-PRINCESS", "start": 0x0CB27A, "end": 0x0CB3C6,
     "draft": ("[DFT][PAL:02]전투원 A:\n[PAL:00]들었어? 통치자가 초코 공주를 데려왔대.[FIN]"
               "[PAL:02]전투원 B:\n[PAL:00]초코도 해커를 못 막았지.[FIN]"
               "통치자님이 최고야! 하하![PAU:1E] 알겠어?[DE]"
               "[PAU:3C][DFT]…어…[PAU:3C] 다음 공격지는 어디지?[DE]"
               "[DFT][PAL:02]전투원 C:\n[PAL:00]아마 다음은 [PAL:02]퀸티닉스[PAL:00]야. 곧이래.[FIN]"
               "[PAL:02]전투원 B:\n[PAL:00]작은 별이 요새를 이길 순 없지.")},
    {"id": "RUNTIME-0CB3C7-FORTRESS-RED-ALERT", "start": 0x0CB3C7, "end": 0x0CB409,
     "draft": "[DFT][PAL:03]해커 전투원에게 알린다!\n요새에 침입자다! 전원 비상![PAL:00]"},
    {"id": "RUNTIME-0CB51D-PASSWORD-INPUT", "start": 0x0CB51D, "end": 0x0CB57C,
     "draft": ("[DFT][PAL:02]암호[PAL:00]가 필요하다.\n입력할까?\n 입력\n 취소[TER]"
               "[BYTE:C8][TER][WIPE]\n정확히 입력해야 열린다!")},
)

# Hacker fortress interior, prison, and mouse/elevator sequence.
RUNTIME_RECORD_PATCHES += (
    {"id": "RUNTIME-0CB6A1-INTRUDER-FOUND", "start": 0x0CB6A1, "end": 0x0CB6C6,
     "draft": "[TOP]\n침입자다!\n[PAU:1E]서! 움직이지 마!"},
    {"id": "RUNTIME-0CB6C7-KOTETSU-FORTRESS-HELP", "start": 0x0CB6C7, "end": 0x0CB865,
     "draft": ("[TOP]통치자에게![PAU:3C] …어때.\n나를 모르겠어!? 코테츠야.[FIN]"
               "[PAL:03]민트[PAL:00]를 찾았나? 이 배 안에 있어![FIN]"
               "그 애가 돌아다니면 장사가 안 돼! 보면 배로 돌려보내.[FIN]"
               "공주는 [PAL:02]위층 감옥[PAL:00]에 있어. [PAL:02]붉은 문[PAL:00]을 봤지?[FIN]"
               "빨강·노랑·파랑 문마다 암호가 있어.[FIN]"
               "붉은 암호를 알려 주지.[FIN]"
               " [NAM:00], [PAL:02]붉은 암호[PAL:00]를 익혔다.[FIN]"
               "그럼 힘내! 난 민트를 찾아야 해. 귀찮군!")},
    {"id": "RUNTIME-0CB8BD-ANNOUNCED-INTRUDER", "start": 0x0CB8BD, "end": 0x0CB8EB,
     "draft": "[TOP]그 침입자군!\n통치자께 데려가겠다!"},
    {"id": "RUNTIME-0CB8EC-STILL-WANT-FIGHT", "start": 0x0CB8EC, "end": 0x0CB911,
     "draft": "[TOP]또 싸워? 배짱 좋군! 와라!"},
    {"id": "RUNTIME-0CB9A9-TIRA-WAITED", "start": 0x0CB9A9, "end": 0x0CBA21,
     "draft": ("[TOP][SPEAKER:0E][NAM:00]![PAU:14]\n날 구하러 온 줄 알았어.[FIN]"
               "무서웠지만 네가 오길 기다렸어…[FIN]"
               "[NAM:00], 이리 와. 나가는 길을 알아.")},
    {"id": "RUNTIME-0CBA5D-TIRA-GOOD-JOB", "start": 0x0CBA5D, "end": 0x0CBA7E,
     "draft": "[TOP][SPEAKER:0E][NAM:00], 끝이야. 잘했어."},
    {"id": "RUNTIME-0CBB2E-GATEAU-REST", "start": 0x0CBB2E, "end": 0x0CBBA4,
     "draft": ("[TOP][SPEAKER:0D]정말 잘했군. 가짜에게 속지 마라.[FIN]"
               "여기까지 왔으니 어울리는 곳으로 보내 주지. 거기서 쉬어라.")},
    {"id": "RUNTIME-0CBC22-MINT-MICE", "start": 0x0CBC22, "end": 0x0CBC48,
     "draft": "[TOP][SPEAKER:04][NAM:00]! 이 쥐들 좀 어떻게 해 줘!!"},
    {"id": "RUNTIME-0CBC49-MOUSE-HOLE", "start": 0x0CBC49, "end": 0x0CBC60,
     "draft": "[TOP][SPEAKER:04]뭐? 쥐구멍!?"},
    {"id": "RUNTIME-0CBC61-MINT-SEWER-FORTRESS", "start": 0x0CBC61, "end": 0x0CBD30,
     "draft": ("[TOP][SPEAKER:04]쥐구멍 옆이라니…[FIN]"
               "여긴 어디야? 냄새나고 쥐까지… 이럴 때가 아니지![FIN]"
               "요새의 다음 목표가 내 별 [PAL:02]퀸티닉스[PAL:00]래![FIN]"
               "빨리 나가야 해! 하지만 어떻게!? 저건 승강기인데 안 움직여!")},
    {"id": "RUNTIME-0CBD31-MOUSE-STAY-AWAY", "start": 0x0CBD31, "end": 0x0CBD4E,
     "draft": "[TOP][SPEAKER:04][NXT][BYTE:01]쥐다! 오지 마!![NXT][BYTE:00]"},
    {"id": "RUNTIME-0CBDC4-ELEVATOR-MOVING", "start": 0x0CBDC4, "end": 0x0CBE0D,
     "draft": ("[TOP][SPEAKER:04]봐, [NAM:00]! 승강기가 움직여! 타![FIN]"
               "쥐가 있는 곳은 못 견뎌. 미안!")},
    {"id": "RUNTIME-0CBE0E-MOUSE-ELEVATOR", "start": 0x0CBE0E, "end": 0x0CBE43,
     "draft": "[TOP][SPEAKER:04]쥐다! [NAM:00], 뭐 해!? 승강기가 움직여!"},
    {"id": "RUNTIME-0CBEA2-SQUEAK", "start": 0x0CBEA2, "end": 0x0CBEB3,
     "draft": "[TOP]\n찍! 찍!"},
    {"id": "RUNTIME-0CBEB4-MOUSE-NEST", "start": 0x0CBEB4, "end": 0x0CBEFB,
     "draft": "[TOP]이 여자를 맡으라고? 내가 할 말이야! 저러면 둥지에 못 가. 찍!"},
)

# Former ruler/janitor, No-Run program, and fortress gossip.
RUNTIME_RECORD_PATCHES += (
    {"id": "RUNTIME-0CC082-JANITOR-CAUGHT", "start": 0x0CC082, "end": 0x0CC0B4,
     "draft": "[TOP2][SPEAKER:0A]오지 마! 청소 중이야!\n[NXT][BYTE:06]……[NXT][BYTE:00]너…!"},
    {"id": "RUNTIME-0CC0B5-JANITOR-BLAMES", "start": 0x0CC0B5, "end": 0x0CC0EE,
     "draft": "[TOP2][SPEAKER:0A]으… 으…! 너 때문에 이 짓을 하잖아!"},
    {"id": "RUNTIME-0CC0EF-HARD-LUCK-CHOICE", "start": 0x0CC0EF, "end": 0x0CC14F,
     "draft": ("[TOP2][SPEAKER:0A]내 불행한 얘길 들을래!?\n 좋아.\n 싫어.[TER]"
               "[WIPE]그럼 나가! 네 얼굴은 보기 싫어!")},
    {"id": "RUNTIME-0CC150-JANITOR-BACKSTORY", "start": 0x0CC150, "end": 0x0CC22B,
     "draft": ("[WIPE]그럼 들어! 요새 폭발 때 간신히 빠져나와 이곳에 왔지.[FIN]"
               "퀸티닉스 때문에 [PAL:02]영원한 청소부[PAL:00]가 됐어! 난 해커의 지도자였는데![FIN]"
               "도망 못 가게 [PAL:02]달리기 금지 프로그램[PAL:00]도 만들었어. 달리면 몸이 아파!")},
    {"id": "RUNTIME-0CC22C-JANITOR-KEY-DEAL", "start": 0x0CC22C, "end": 0x0CC3C2,
     "draft": ("[TOP2]또 뭘 원해!? 공주를 찾는다고? 내 알 바 아냐![FIN]"
               "…잠깐. 요새 전체를 청소하는 건 나야.[FIN]"
               "그래서 내 [PAL:02]열쇠[PAL:00]는 모든 문을 열지. 와하하![FIN]"
               "원해? [PAL:02]달리기 금지 프로그램[PAL:00]을 멈추면 주지.[FIN]"
               "[PAL:02]노란 암호[PAL:00]도 알려 주마. 다니기 편할 거야.[FIN]"
               " [NAM:00], [PAL:02]노란 암호[PAL:00]를 익혔다![FIN]"
               "프로그램은 [PAL:02]요새 컴퓨터[PAL:00]에 있어.[FIN]"
               "알았으면 가! 공주가 걱정되지?")},
    {"id": "RUNTIME-0CC3C3-PROGRAM-DESTROYED", "start": 0x0CC3C3, "end": 0x0CC3EE,
     "draft": "[TOP2][SPEAKER:0A][JMP][BYTE:6C][BYTE:C3][TOP2][SPEAKER:0A]…뭐!? 프로그램을 없앴어?"},
    {"id": "RUNTIME-0CC3EF-JANITOR-FREE", "start": 0x0CC3EF, "end": 0x0CC41A,
     "draft": "[TOP2][SPEAKER:0A]잘했어! 이제 움직인다! 자유다!"},
    {"id": "RUNTIME-0CC41B-RECEIVE-KEY", "start": 0x0CC41B, "end": 0x0CC49F,
     "draft": ("[TOP2]정말 해낼 줄은 몰랐어! 나도 남자다! 열쇠를 주지.[DE]"
               "[TOP] [NAM:00], [PAL:02]열쇠[PAL:00]를 받았다![TER]"
               "[TOP]청소는 지긋지긋해! 난 나간다! 고마워!!")},
    {"id": "RUNTIME-0CC4A0-INVENTORY-FULL-KEY", "start": 0x0CC4A0, "end": 0x0CC4C0,
     "draft": "[TOP]가방이 꽉 찼군. 지저분해!!"},
    {"id": "RUNTIME-0CC4C1-MOUSE-FREE", "start": 0x0CC4C1, "end": 0x0CC4DC,
     "draft": "[TOP]운 좋은 쥐군. 넌 자유야."},
    {"id": "RUNTIME-0CC56D-NO-RUN-BATTLE", "start": 0x0CC56D, "end": 0x0CC63F,
     "draft": ("[TOP]또 만났군. 닥터 G가 내 기억을 늘리고 강화했지.[FIN]"
               "뭐? [PAL:02]달리기 금지 프로그램[PAL:00]? 갖고 있어.[FIN]"
               "쉽게는 못 줘. 원하면 날 이겨라.[FIN]"
               "스피드 칩과 속도 관리 프로그램을 시험할 때군.")},
    {"id": "RUNTIME-0CC640-BAGU-CANNOT-MANAGE", "start": 0x0CC640, "end": 0x0CC667,
     "draft": "[TOP][NXT][BYTE:06]…바구 바구… 관리 못 해… 바구."},
    {"id": "RUNTIME-0CC6A9-PRINCESS-GOSSIP", "start": 0x0CC6A9, "end": 0x0CC77E,
     "draft": ("[BOTTOM]통치자가 데려온 공주 봤어?[DE]"
               "[BOTTOM]지금 방에 있는 여자? 봤지! 귀엽더라.[DE]"
               "[BOTTOM]뭐? 난 못 봤어. 귀여운 공주? 보러 가자…[DE]"
               "[BOTTOM]하지만 [PAL:02]통치자의 방 열쇠[PAL:00]가 없어. 못 들어가. 아쉽군!!")},
)

# Tira, Gateau, and former-ruler fortress confrontation.
RUNTIME_RECORD_PATCHES += (
    {"id": "RUNTIME-0CC8B6-TIRA-FORTRESS-WONDER", "start": 0x0CC8B6, "end": 0x0CC933,
     "draft": ("[TOP][SPEAKER:0E][NAM:00]? 가토가 너도 데려왔어?[FIN]"
               "크고 사람도 많아서 신기해. 이런 요새가 있으면 해커도 안 무섭겠어.")},
    {"id": "RUNTIME-0CC934-TIRA-REALIZES-KIDNAPPING", "start": 0x0CC934, "end": 0x0CC9C4,
     "draft": ("[TOP][SPEAKER:0E]여기가 해커 요새라고? 그럼 난 납치된 거잖아. 몰랐어.[FIN]"
               "가만있을 순 없어. [NAM:00], 나가자. 내가 따라갈게.")},
    {"id": "RUNTIME-0CC9C5-TIRA-EASY-EXIT", "start": 0x0CC9C5, "end": 0x0CC9EC,
     "draft": "[TOP2][SPEAKER:0E]이쪽이면 쉽게 나가. [NAM:00], 가자."},
    {"id": "RUNTIME-0CC9ED-GATEAU-REVEALS-RULER", "start": 0x0CC9ED, "end": 0x0CCAE0,
     "draft": ("[TOP2][SPEAKER:0E]가토가 여긴 해커 요새랬어. 너도 와.[FIN]"
               "[SPEAKER:0D]그래, 티라. 사실 내가 이 요새의 통치자다.[FIN]"
               "[SPEAKER:0E]통치자? 그럼 당신이 해커의 통치자!?[FIN]"
               "[SPEAKER:0D]맞아. 하지만 널 해치진 않겠다.[FIN]"
               "[SPEAKER:0E]그럼 난 인질이야? 너무해. 비켜!")},
    {"id": "RUNTIME-0CCAE1-TIRA-CONSUL-ANGER", "start": 0x0CCAE1, "end": 0x0CCB40,
     "draft": ("[TOP2][SPEAKER:0E]아… 또 사고 쳤네… 영사님이 또 화내겠어.[FIN]"
               "밖은 우주였는데… 가토는 괜찮아?")},
    {"id": "RUNTIME-0CCBBA-GATEAU-TIME-SLIP", "start": 0x0CCBBA, "end": 0x0CCC7A,
     "draft": ("[TOP2][SPEAKER:0D]네가 [NAM:00]인가?[FIN]"
               "수백 년 만이군. 타임 슬립으로 배가 미래에 왔지.[FIN]"
               "덕분에 이 요새를 만들 힘도 얻었다.[FIN]"
               "여기까지 온 건 칭찬하지. 하지만 끝이다.")},
    {"id": "RUNTIME-0CCCBC-TIRA-CALL-SHIP", "start": 0x0CCCBC, "end": 0x0CCCED,
     "draft": "[TOP][SPEAKER:0E][NAM:00], 배를 부르면 초코로 돌아갈 수 있어."},
    {"id": "RUNTIME-0CCCEE-TIRA-NOT-RETURNING", "start": 0x0CCCEE, "end": 0x0CCD1B,
     "draft": "[TOP][SPEAKER:0E][NAM:00]? 안 돌아가? 영사님께 혼날 거야."},
    {"id": "RUNTIME-0CCD1C-TIRA-MOUSE-GREETING", "start": 0x0CCD1C, "end": 0x0CCD3B,
     "draft": "[TOP][SPEAKER:0E]어머, 작은 쥐야. 잘 지냈어?"},
    {"id": "RUNTIME-0CCD51-GATEAU-TAUNT", "start": 0x0CCD51, "end": 0x0CCDAA,
     "draft": ("[TOP2][PAL:02]초코에서 뭘 배웠든 넌 이길 수 없어.[FIN]"
               "소중한 친구들은 상관없나??[PAL:00]")},
    {"id": "RUNTIME-0CCE4D-NAGISA-INVOLVED", "start": 0x0CCE4D, "end": 0x0CCE71,
     "draft": "[TOP][SPEAKER:03]말도 안 돼. 왜 내가 휘말린 거야!!"},
    {"id": "RUNTIME-0CCE72-RELAXED-HERO", "start": 0x0CCE72, "end": 0x0CCE91,
     "draft": "[TOP]네가 [NAM:00]지? 왜 이렇게 태평해?"},
    {"id": "RUNTIME-0CCF64-MINT-RESCUED", "start": 0x0CCF64, "end": 0x0CCF9D,
     "draft": "[TOP][SPEAKER:04][NAM:00]! 날 구하러 왔어? 누구와 달리 믿음직하네!"},
    {"id": "RUNTIME-0CCF9E-KOTETSU-RESCUE", "start": 0x0CCF9E, "end": 0x0CCFD8,
     "draft": "[BOTTOM][SPEAKER:03]누구 얘기야! 병사에게 포위됐지만 구했잖아!"},
    {"id": "RUNTIME-0CCFD9-MINT-RUN", "start": 0x0CCFD9, "end": 0x0CD006,
     "draft": "[TOP][SPEAKER:04]둘 다 뭐 해! 빨리 가! 또 오면 어쩌려고!?"},
    {"id": "RUNTIME-0CD093-FORMER-RULER-ORDERS", "start": 0x0CD093, "end": 0x0CD10C,
     "draft": ("[TOP2][SPEAKER:0A]불로 뛰어드는 나방 같군.[FIN]"
               "통치자의 명령이다. 정신 차리면 실수를 용서하지. 저 둘을 잡아!")},
    {"id": "RUNTIME-0CD10D-BLUE-PASSWORD", "start": 0x0CD10D, "end": 0x0CD27B,
     "draft": ("[TOP][SPEAKER:0A]걱정 마. 둘은 탈출선으로 데려가는 거야.[FIN]"
               "이상하다고? 이 역겨운 일은 이제 지쳤어.[FIN]"
               "세계를 차지하려다 실패했지. 이젠 통치자를 곤란하게 만들 거야.[FIN]"
               "[PAL:02]파란 암호[PAL:00]를 알려 주지. 요새 안쪽으로 갈 때 필요해.[FIN]"
               " [NAM:00], [PAL:02]파란 암호[PAL:00]를 익혔다![FIN]"
               "[SPEAKER:0A]난 간다. 어디로냐고? 바람은 목적지가 없어.")},
    {"id": "RUNTIME-0CD2DF-MINT-UNLUCKY", "start": 0x0CD2DF, "end": 0x0CD30E,
     "draft": "[TOP][SPEAKER:04]뭐 하는 거야? 그만해! 아, 난 정말 운이 없어!"},
)

# Napoleon reunion and final Gateau pursuit.
RUNTIME_RECORD_PATCHES += (
    {"id": "RUNTIME-0CD465-GATEAU-NOBODY", "start": 0x0CD465, "end": 0x0CD497,
     "draft": "[TOP][SPEAKER:0D]아무도 없나! 왜 이 애 하나 끝내지 못해!?"},
    {"id": "RUNTIME-0CD498-RASK-BLOOD", "start": 0x0CD498, "end": 0x0CD4DF,
     "draft": "[TOP][PAL:02]보통 아이가 아니야. 알잖아? 라스크의 피가 흐른다고.[PAL:00]"},
    {"id": "RUNTIME-0CD4E0-NAPOLEON-DEFIES-GATEAU", "start": 0x0CD4E0, "end": 0x0CD61F,
     "draft": ("[TOP][SPEAKER:0D]…나폴레옹? 왜 여기 있지?[FIN]"
               "괜찮아. 설계자인 내게 거역할 순 없어.[FIN]"
               "명령한다! 해치워! 왜 그러지? 당장 해!![FIN]"
               "[SPEAKER:0C]가토… 아니, 가토! 난 예전의 내가 아냐![FIN]"
               "초코 과학자들이 날 재건했지. 이젠 네 명령을 무시할 수 있어![FIN]"
               "이 요새는 파괴된다. 포기해! 달리 방법이 있나?[FIN]"
               "[SPEAKER:0D]이건 계획 하나일 뿐. 곧 진짜 계획을 보게 될 거다!")},
    {"id": "RUNTIME-0CD620-GATEAU-LEAVES", "start": 0x0CD620, "end": 0x0CD65F,
     "draft": "[TOP][SPEAKER:0D]지금은 두고 가지. 곧 내 손으로 끝내 주마!"},
    {"id": "RUNTIME-0CD660-NAPOLEON-WAIT", "start": 0x0CD660, "end": 0x0CD679,
     "draft": "[TOP][SPEAKER:0C]기다려! 도망치나!?"},
    {"id": "RUNTIME-0CD790-NAPOLEON-THROW-CHOICES", "start": 0x0CD790, "end": 0x0CD901,
     "draft": ("[TOP][SPEAKER:0C]다시 만났군. 초코 과학자들이 날 되살렸어.[FIN]"
               "네가 온다기에 따라왔지. 감상에 젖을 때가 아니야.[DE]"
               "[TOP]여길 건너면 가토를 쫓을 수 있어. 너 혼자면 던져 줄게.[FIN]"
               "난 그자를 막아야 해. 네가 막겠나?\n 물론.\n 싫어.[TER]"
               "[WIPE]…그럴 줄 알았어.[DE]"
               "[TOP]앞일은 몰라. 준비됐나?\n 완벽해.\n 아직.[TER]"
               "[WIPE]…내가 잘못 봤군…")},
    {"id": "RUNTIME-0CD902-NAPOLEON-FAREWELL", "start": 0x0CD902, "end": 0x0CDA19,
     "draft": ("[WIPE]좋아. 가토는 네게 맡긴다. 난 여길 지킬게.[FIN]"
               "[NAM:00]… 넌 정말 라스크를 닮았어. 함께 있으면 그와 있는 듯했지.[FIN]"
               "네 발명품을 믿고 잘 써라. 가토 같은 실수는 하지 마.[DE]"
               "[TOP]그 모습은 위험해. 원래 모습으로 돌아가.[DE]"
               "[TOP]시간이 없어. 끝에 서.")},
    {"id": "RUNTIME-0CDA1A-NAPOLEON-WAIT-PREPARE", "start": 0x0CDA1A, "end": 0x0CDA52,
     "draft": "[WIPE]돌아가서 준비하는 게 낫겠어. 기다릴 테니 늦지 마."},
    {"id": "RUNTIME-0CDA53-NAPOLEON-GO-SOON", "start": 0x0CDA53, "end": 0x0CDA8B,
     "draft": "[TOP][SPEAKER:0C]무슨 일이야? 어서 가. 널 믿는다, [NAM:00]."},
    {"id": "RUNTIME-0CDAFB-GATEAU-TIME-MACHINE", "start": 0x0CDAFB, "end": 0x0CDBB6,
     "draft": ("[TOP][SPEAKER:0D]용감하군! 하지만 이제 뭘 할 수 있지?[FIN]"
               "이 기계를 아나? 안에는 [SPEAKER:00]이 들어 있다.[FIN]"
               "[SPEAKER:00]은 미래만 보여 주지만 이 기계는 달라.[FIN]"
               "완성되면 시간을 지배하고 널 영원히 없애 주마!")},
    {"id": "RUNTIME-0CDBB7-GATEAU-STILL-FIGHTING", "start": 0x0CDBB7, "end": 0x0CDBEE,
     "draft": "[TOP][SPEAKER:0D]아직 싸우나? 넌 패배자야! 내 상대가 못 돼!"},
    {"id": "RUNTIME-0CDBEF-GATEAU-FOLLOW-MACHINE", "start": 0x0CDBEF, "end": 0x0CDC59,
     "draft": ("[TOP]제법이군. 재미있어.[FIN]"
               "아직 용기가 남았다면 따라와![FIN]"
               "기계 안으로 들어가! 재미있는 걸 보여 주지.")},
    {"id": "RUNTIME-0CDD9F-PARENTS-MESSAGE", "start": 0x0CDD9F, "end": 0x0CDE05,
     "draft": ("[WIPE][PAU:30]저장됐다.[PAU:3C] [NAM:00], 아빠와 난 널 사랑해.[FIN]"
               "친구들에게도 넌 소중할 거야. 조심하고 힘내렴.")},
    {"id": "RUNTIME-0CDE5F-PASSWORD-ENTERED", "start": 0x0CDE5F, "end": 0x0CDE78,
     "draft": "[TOP] [NAM:00], 암호를 입력했다."},
)

# Password jars, Rask's memories, and the final time-space speech.
RUNTIME_RECORD_PATCHES += (
    {"id": "RUNTIME-0CE036-SET-RED-JAR", "start": 0x0CE036, "end": 0x0CE051,
     "draft": "[TOP] [NAM:00], [PAL:02]붉은 병[PAL:00] 설치!"},
    {"id": "RUNTIME-0CE052-TAKE-RED-JAR", "start": 0x0CE052, "end": 0x0CE070,
     "draft": "[TOP] [NAM:00], [PAL:02]붉은 병[PAL:00] 회수!"},
    {"id": "RUNTIME-0CE071-RED-JAR-FULL", "start": 0x0CE071, "end": 0x0CE094,
     "draft": "[TOP] 가방이 꽉 차서 되찾을 수 없다…"},
    {"id": "RUNTIME-0CE0DB-SET-YELLOW-JAR", "start": 0x0CE0DB, "end": 0x0CE0F9,
     "draft": "[TOP] [NAM:00], [PAL:02]노란 병[PAL:00] 설치!"},
    {"id": "RUNTIME-0CE0FA-TAKE-YELLOW-JAR", "start": 0x0CE0FA, "end": 0x0CE11B,
     "draft": "[TOP] [NAM:00], [PAL:02]노란 병[PAL:00] 회수!"},
    {"id": "RUNTIME-0CE194-SET-BLUE-JAR", "start": 0x0CE194, "end": 0x0CE1B0,
     "draft": "[TOP] [NAM:00], [PAL:02]파란 병[PAL:00] 설치!"},
    {"id": "RUNTIME-0CE1B1-TAKE-BLUE-JAR", "start": 0x0CE1B1, "end": 0x0CE1D0,
     "draft": "[TOP] [NAM:00], [PAL:02]파란 병[PAL:00] 회수!"},
    {"id": "RUNTIME-0CE365-PARENTS-NAME-BABY", "start": 0x0CE365, "end": 0x0CE4BA,
     "draft": ("[TOP][SPEAKER:02]날 봐. 웃고 있어. 내 말을 알아듣나 봐…[DE]"
               "[TOP][PAL:03]엄마:\n[PAL:00]여보… 아직 아무것도 못 봐요…[DE]"
               "[TOP][SPEAKER:02]…맞아… 그래도 이름을 지어야지.[FIN]"
               "[PAL:03]엄마:\n[PAL:00]무슨 말이에요… 당신 생각은 알아요.[FIN]"
               "[SPEAKER:02]…그래… [PAL:02][NAM:00][PAL:00]… 어때?[DE]"
               "[TOP][PAL:03]엄마:\n[PAL:00][NAM:00]… 좋은 이름이에요.[FIN]"
               "자, [NAM:00]. 아빠의 선물이란다…[DE]"
               "[SPEAKER:02][NAM:00], 건강하렴. 우린 늘 지켜볼게.")},
    {"id": "RUNTIME-0CE53E-COOKIE-RETURN-CHOCO", "start": 0x0CE53E, "end": 0x0CE5A1,
     "draft": ("[TOP2][SPEAKER:12]기다려, 라스크! 초코로 안 돌아갈 거야?[FIN]"
               "이 별엔 테트론이 많잖아. 초코 연구원들이 오면 돼.")},
    {"id": "RUNTIME-0CE5A2-RASK-DREAM", "start": 0x0CE5A2, "end": 0x0CE654,
     "draft": ("[TOP2][SPEAKER:11]미안해, 쿠키. 테트론을 보고 알았어.[FIN]"
               "이 별에 테트론이 있을 거란 걸. 그래도 직접 오고 싶었어.[FIN]"
               "여기엔 꿈이 있어. 초코엔 없는 꿈… 얼마나 걸려도 찾겠어…")},
    {"id": "RUNTIME-0CE655-COOKIE-OTHER-REASON", "start": 0x0CE655, "end": 0x0CE6B4,
     "draft": ("[TOP2][SPEAKER:12]…그게 전부는 아니지. 초코에서 설명해.[FIN]"
               "하지만… 테트론과 당신을 잊지 않을게…")},
    {"id": "RUNTIME-0CE712-RASK-WARNS-GATEAU", "start": 0x0CE712, "end": 0x0CE76D,
     "draft": ("[TOP][SPEAKER:11]가토… 이 테트론을 넘기려 했지만…[DE]"
               "[TOP]왜 미래를 보려 하지? 이 발명은 사람에게 해로워")},
    {"id": "RUNTIME-0CE76E-GATEAU-TEMPTS-RASK", "start": 0x0CE76E, "end": 0x0CE809,
     "draft": ("[TOP][SPEAKER:0D]욕심이 없군, 라스크. 왜 쓰지 않지?[FIN]"
               "미래를 알면 영웅이 될 수 있어.[FIN]"
               "버릴 거라면 내가 쓰지. 어때, 라스크?[DE]"
               "[TOP][SPEAKER:11]가토… 무슨 생각이지…")},
    {"id": "RUNTIME-0CE8DF-NO-ESCAPE-TIME-SPACE", "start": 0x0CE8DF, "end": 0x0CE924,
     "draft": "[TOP]달아날 셈인가? 헛수고다. 이 공간은 네 의지와 같아. 벗어날 수 없어."},
    {"id": "RUNTIME-0CE925-GATEAU-FINAL-SPEECH", "start": 0x0CE925, "end": 0x0CEA4E,
     "draft": ("[TOP][NXT][BYTE:05]시간의 흐름 속에 인간은 그저 존재할 뿐.[FIN]"
               "그들이 만든 것처럼 언젠가 사라지고 잊히지.[FIN]"
               "난 발명이 인간의 힘을 넘으리라 믿었다. [SPEAKER:00]이 기회를 줬지.[FIN]"
               "그래서 시간을 지배하는 힘을 얻었다. 이제 인간의 운명도 지배한다.[FIN]"
               "내 손으로 널 지우는 건 간단해… 테트론을 만든 라스크에게 보내는 신호다!")},
)

# Kirara library and developer-room runtime block.
RUNTIME_RECORD_PATCHES += (
    {"id": "RUNTIME-0CA4F2-KIRARA-WELCOME", "start": 0x0CA4F2, "end": 0x0CA54B,
     "draft": ("[BOTTOM]키라라입니다.\n잃어버린 책이 시대를 넘어 모입니다.[FIN]"
               "필요한 책 찾으세요. 들어오세요.")},
    {"id": "RUNTIME-0CA54C-MET-BEFORE", "start": 0x0CA54C, "end": 0x0CA5A8,
     "draft": ("[BOTTOM]뭐?[PAU:14] 전에 만났냐고?\n[PAU:14]…그래. 나도 그런 느낌이야.[FIN]"
               "아주 오래전에 만난 것 같아…")},
    {"id": "RUNTIME-0CA5A9-KIRARA-MOUSE", "start": 0x0CA5A9, "end": 0x0CA5C3,
     "draft": "[DFT]쥐구나. 키라라에 잘 왔어."},
    {"id": "RUNTIME-0CA62B-K-PEN-NAME", "start": 0x0CA62B, "end": 0x0CA671,
     "draft": "[DFT]시간도 기억도 별로 없어.\nK(필명)가 알면 화낼 텐데."},
    {"id": "RUNTIME-0CA672-SUPPON-HAMMER", "start": 0x0CA672, "end": 0x0CA6AF,
     "draft": "[DFT]추천 무기는 [PAL:02]자라 해머[PAL:00]야.\n구하기 어렵지만."},
    {"id": "RUNTIME-0CA6B0-QUINTET-GAMES", "start": 0x0CA6B0, "end": 0x0CA6EF,
     "draft": "[DFT]몸 좋네. 퀸텟에서 게임을 만들어 봐.[FIN]비서도 구하고."},
    {"id": "RUNTIME-0CA6F0-HAIR-NEXT-GAME", "start": 0x0CA6F0, "end": 0x0CA736,
     "draft": "[DFT]다들 내 머리로 놀려.[PAU:1E]\n아무튼 다음 게임도 기대해 줘!"},
    {"id": "RUNTIME-0CA737-FEMALE-PROGRAMMER", "start": 0x0CA737, "end": 0x0CA775,
     "draft": "[DFT]아직 수련 중이지만 곧 여성 프로그래머로 데뷔할 거야."},
    {"id": "RUNTIME-0CA776-F1-TOOTHACHE", "start": 0x0CA776, "end": 0x0CA7AC,
     "draft": "[DFT]기쁘게 F1을 시작했는데\n지금은 이가 욱신거려…"},
    {"id": "RUNTIME-0CA7AD-PC-NETWORK-BILL", "start": 0x0CA7AD, "end": 0x0CA7F3,
     "draft": "[DFT]요즘 PC 통신에 빠졌더니…\n전화 요금이 끔찍해…"},
    {"id": "RUNTIME-0CA7F4-BOYS-TO-MEN", "start": 0x0CA7F4, "end": 0x0CA822,
     "draft": "[DFT]이 게임은 소년을 남자로 키운다!"},
    {"id": "RUNTIME-0CA823-NOT-ENOUGH-CHIPS", "start": 0x0CA823, "end": 0x0CA862,
     "draft": "[DFT]큰일이야! 너무 바빠!\n칩이 부족해! 심각해!"},
    {"id": "RUNTIME-0CA863-RD-PARTITION", "start": 0x0CA863, "end": 0x0CA8A0,
     "draft": "[DFT]연구실에 칸막이를 세웠어.\n그것에 비하면 이건 작지."},
    {"id": "RUNTIME-0CA8CC-NOT-A-ROBOT", "start": 0x0CA8CC, "end": 0x0CA911,
     "draft": "[DFT]가끔 이곳은…[PAU:1E]\n사실 난 로봇이 아니야! 힘들군!"},
    {"id": "RUNTIME-0CAA6C-BUCKY-DEBUG-LESSON", "start": 0x0CAA6C, "end": 0x0CAB40,
     "draft": ("[DFT][PAL:03]질문 있어요. [PAL:02]버키[PAL:03]가 뭐죠?\n뻐드렁니 남자?[DE]"
               "[DFT][PAL:03]그렇군요![PAU:1E] 많이 배웠어요.\n버키는 이름을 남겨 행운이군요.[DE]"
               "[DFT][PAL:03]좋아요. [PAL:02][PAU:1E]디버그[PAL:03]를 이해했나요?\n"
               "[PAU:28]수업 끝. 이야기로 돌아갑니다.")},
    {"id": "RUNTIME-0CAE0A-PARTY-NUMBER", "start": 0x0CAE0A, "end": 0x0CAE24,
     "draft": "[DFT]파티 No.[BYTE:C6][BYTE:04][BYTE:86][BYTE:0B]와 싸웠다."},
    {"id": "RUNTIME-0CAE71-MINT-THIS-WAY", "start": 0x0CAE71, "end": 0x0CAE98,
     "draft": "[BOTTOM][SPEAKER:03]이쪽이야. 꾸물대면 두고 간다."},
    {"id": "RUNTIME-0CAEB7-HATCH-CLOSED", "start": 0x0CAEB7, "end": 0x0CAECB,
     "draft": "[DFT]해치가 닫혀 있다."},
)

# Early-game event text that is not represented by the physical D7 catalogue.
# These spans are deliberately split at absolute D3/CC/DE entry points.  A
# translated span may become shorter, but the command at ``end`` must remain at
# its original address so the event engine's saved/resume PCs stay valid.
SCREEN_TEXT_PATCHES = (
    {
        "id": "SCREEN-05AD50-KUROGANE-LETS-GO",
        "start": 0x05AD50,
        "end": 0x05AD64,
        "end_command": 0xC0,
        "draft": "[BYTE:D9][SPEAKER:02]쿠로가네, 가자.",
    },
    {
        "id": "SCREEN-05D5A9-MAYOR-DIRECTIONS",
        "start": 0x05D5A9,
        "end": 0x05D5D9,
        "end_command": 0xC0,
        "draft": "[DFT]촌장님을 만나려고?\n맨 안쪽 방에 계셔.",
    },
    {
        "id": "SCREEN-05E1E1-MAYOR-COMMUNICATIONS",
        "start": 0x05E1E1,
        "end": 0x05E2EC,
        "end_command": 0xD3,
        "draft": (
            "[BYTE:D8][SPEAKER:09]마을 사람들과 연락을 맡고 있네.[FIN]"
            "젊은이들과 이야기할 시간도 내고 있지.\n콜록! 콜록![FIN]"
            "이제 너도 로코코 주민이야.\n젊은 힘으로 세상과 마을을 위해 일해 주게.[FIN]"
            "여기 계신 분은 유명한 발명가\n[PAL:02]아인스트 박사[PAL:00]라네.[FIN]"
            "해커 소문이 끊이지 않아\n도움을 청했지.[FIN]"
        ),
    },
    {
        "id": "SCREEN-05E2F2-MAYOR-COMMUNICATIONS-TAIL",
        "start": 0x05E2F2,
        "end": 0x05E324,
        "end_command": 0xC0,
        "draft": "박사님처럼 훌륭한\n발명가가 되거라. 하하하.",
    },
    {
        "id": "SCREEN-05E9FF-DR-EINST",
        "start": 0x05E9FF,
        "end": 0x05EACC,
        "end_command": 0xC0,
        "draft": (
            "[DFT][SPEAKER:05]그래.[FIN]난 세계 최고의 발명가,\n"
            "[PAL:02]아인스트 박사[PAL:00]다![FIN]너도 발명가라고?\n"
            "나이도 관심사도 달라\n말이 안 통하겠군.[FIN]"
            "가르쳐 달라고?\n헛수고야.\n꼬마에게 가르칠 건 없어."
        ),
    },
    {
        "id": "SCREEN-05F910-INVENTION-MACHINE",
        "start": 0x05F910,
        "end": 0x05F9E0,
        "end_command": 0xD3,
        "draft": (
            "[DFT][SPEAKER:01]이건 [PAL:02]발명 기계[PAL:00]야.[FIN]"
            "발명가는 여기서 물건을 만들지.[FIN]"
            "책을 읽고 사람들과 얘기하면\n아이디어를 얻어.[FIN]"
            "아이템을 조합해도 돼.[FIN]"
            "로봇 제작과 정비,\n강화도 할 수 있어.[FIN]"
        ),
    },
    {
        "id": "SCREEN-05F9E3-INVENTION-MACHINE-TAIL",
        "start": 0x05F9E3,
        "end": 0x05FA00,
        "end_command": 0xC0,
        "draft": "[DFT][SPEAKER:01]먼저 [NAM:00],\n로봇을 만들어 봐.",
    },
    {
        "id": "SCREEN-05FC48-QUINTET-CONNECT",
        "start": 0x05FC48,
        "end": 0x05FCD1,
        "end_command": 0xC0,
        "draft": (
            "!!접속!![FIN]\n[PAL:02][퀸텟 네트워크][PAL:00]![FIN]"
            "[PAL:02][액트레이저 2]\n[가이아 환상기][PAL:00]\n"
            "인기 신작!\n지금 구매하세요![FIN][PAU:3C]*통신 불가*"
        ),
    },
    {
        "id": "SCREEN-078BFE-SOLDIER-OFFER",
        "start": 0x078BFE,
        "end": 0x078CDA,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8][SPEAKER:08]어때요, 박사님?\n좋은 연봉과 수당,\n의료 보험까지![FIN]"
            "[SPEAKER:02]변함없군!\n해커들은 다 똑같아.\n사악한 녀석들![FIN]"
            "[SPEAKER:08]사악함이 곧 선입니다.\n그게 우리 일이지요.[FIN]"
            "우리 미래엔 박사님 같은\n위대한 발명가가 필요합니다!"
        ),
    },
    {
        "id": "SCREEN-078CDB-SOLDIER-OFFER-TAIL",
        "start": 0x078CDB,
        "end": 0x078DB5,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:02]흠... 관심은 고맙지만\n발명을 악에 쓸 순 없어.[FIN]"
            "최신 발명품을 보여 주지.\n뭔지 궁금한가?[FIN]"
            "[SPEAKER:08]오, 나팔인가?\n고교 시절 악단에 있었죠.[FIN]"
            "[SPEAKER:02]그냥 나팔이 아니야.\n이렇게 쓰는 거지."
        ),
    },
    {
        "id": "SCREEN-0C84C6-TRANSCEIVER-SAVE",
        "start": 0x0C84C6,
        "end": 0x0C8517,
        "end_command": 0xCC,
        "draft": (
            "[BYTE:DB][SPEAKER:01]방금 시험했어.\n통신기는 잘 작동해.[FIN]"
            "저장할래?\n 저장할게.\n 아직 안 해."
        ),
    },
    {
        "id": "SCREEN-0C8518-TRANSCEIVER-SAVE-TAIL",
        "start": 0x0C8518,
        "end": 0x0C853F,
        "end_command": 0xC0,
        "draft": "[WIPE]알겠어.\n조심해. 문제 생기면 연락해.",
    },
    {
        "id": "SCREEN-0C8540-SAVE-RESULT",
        "start": 0x0C8540,
        "end": 0x0C8558,
        "end_command": 0xC0,
        "draft": "[WIPE][PAU:30]저장했어.\n조심해.",
    },
    {
        "id": "SCREEN-0C8705-GOOD-MORNING",
        "start": 0x0C8705,
        "end": 0x0C8782,
        "end_command": 0xD3,
        "draft": (
            "[BYTE:DB][SPEAKER:01]좋은 아침, [NAM:00].[FIN]"
            "이사하느라 피곤하겠네.\n짐은 다 풀었구나.[FIN]"
            "오늘은 촌장님께\n[PAL:02]인사[PAL:00]드리고 와.[FIN]"
        ),
    },
    {
        "id": "SCREEN-0C8785-GOOD-MORNING-TAIL",
        "start": 0x0C8785,
        "end": 0x0C87F0,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:DB][SPEAKER:01]지금 [PAL:02]공사 중인[PAL:00]\n큰 건물에 계셔.[FIN]"
            "이 길로 쭉 가면 돼.\n끝나면 바로 돌아와.\n딴 데 가지 말고."
        ),
    },
    {
        "id": "SCREEN-0C8822-READ-BOOK-FIRST",
        "start": 0x0C8822,
        "end": 0x0C8855,
        "end_command": 0xC0,
        "draft": "[BYTE:DB][SPEAKER:01]먼저 이 책 읽어.[FIN]다 읽기 전엔\n못 나가!",
    },
    {
        "id": "SCREEN-0C8856-READ-BOOK-FOLLOWUP",
        "start": 0x0C8856,
        "end": 0x0C8884,
        "end_command": 0xC0,
        "draft": "[BYTE:DB][SPEAKER:01]책 다 읽었니?\n이리 와. 보여 줄 게 있어.",
    },
    {
        "id": "SCREEN-0C88FE-SAVE-OR-HINT",
        "start": 0x0C88FE,
        "end": 0x0C8931,
        "end_command": 0xCC,
        "draft": "[BYTE:DB][SPEAKER:01]무슨 일이니, [NAM:00]?\n 저장할게.\n 힌트 줘.",
    },
    {
        "id": "SCREEN-0C8932-SAVE-OR-HINT-TAIL",
        "start": 0x0C8932,
        "end": 0x0C8956,
        "end_command": 0xC0,
        "draft": "[WIPE][PAU:30]저장했어.\n걱정 마. 계속 가자.",
    },
    {
        "id": "SCREEN-0C90B8-ROBOT-BOOK-READ",
        "start": 0x0C90B8,
        "end": 0x0C90D5,
        "end_command": 0xDE,
        "draft": "[DFT][NAM:00]는 [PAL:02]로봇 책[PAL:00]을 읽었다.",
    },
    {
        "id": "SCREEN-0C90D6-ROBOT-BOOK-LEARNED",
        "start": 0x0C90D6,
        "end": 0x0C9158,
        "end_command": 0xCC,
        "draft": (
            "[DFT][NAM:00]는 [SPEAKER:1D]을 익혔다.\n"
            "[PAU:3C][PAL:02][DC][05]이제 [SPEAKER:1C] 제작 가능![FIN]"
            "[PAL:00][DC][00]책 마지막 장에\n[PAL:02]2000 GP[PAL:00]가 있었다.[FIN]"
            "[NAM:00] [PAL:02]2000 GP[PAL:00] 획득!"
        ),
    },
    {
        "id": "SCREEN-0C9159-ROBOT-BOOK-REREAD",
        "start": 0x0C9159,
        "end": 0x0C9174,
        "end_command": 0xDE,
        "draft": "[DFT][NAM:00] [PAL:02][SPEAKER:1A] 책[PAL:00] 재독.",
    },
)

# The same omitted event bank contains Nagisa's early progression gates and
# the complete transceiver hint list.  Cover the whole readable early block so
# the user does not encounter another English line every few steps.
SCREEN_TEXT_PATCHES += (
    {
        "id": "EARLY-0C8461-LEAVING",
        "start": 0x0C8461,
        "end": 0x0C8482,
        "end_command": 0xC0,
        "draft": "[BYTE:DB][SPEAKER:01][NAM:00].\n말도 없이 나가려고?",
    },
    {
        "id": "EARLY-0C8483-COME-HERE",
        "start": 0x0C8483,
        "end": 0x0C849F,
        "end_command": 0xC0,
        "draft": "[BYTE:DB][SPEAKER:01][NAM:00], 이리 와.\n할 말 있어.",
    },
    {
        "id": "EARLY-0C84A0-SEE-MAYOR",
        "start": 0x0C84A0,
        "end": 0x0C84C5,
        "end_command": 0xC0,
        "draft": "[BYTE:DB][SPEAKER:01][NAM:00], 꾸물대지 말고\n촌장님께 가.",
    },
    {
        "id": "EARLY-0C8559-KUROGANE-MISSING",
        "start": 0x0C8559,
        "end": 0x0C85D2,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:DB][SPEAKER:01]있잖아, [NAM:00]. [PAL:02]쿠로가네[PAL:00]가\n"
            "산책 나간 뒤 안 돌아와.[FIN][PAL:02]아버지 집[PAL:00]에 갔을지도 몰라.\n"
            "확인해 줄래?"
        ),
    },
    {
        "id": "EARLY-0C85D3-CUTE-CUSTOMER",
        "start": 0x0C85D3,
        "end": 0x0C862D,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:DB][SPEAKER:01]어서 와, [NAM:00].\n귀여운 손님이 기다려.[FIN]"
            "네게 할 말이 있대.\n아주 얌전한 아이야."
        ),
    },
    {
        "id": "EARLY-0C862E-SOUTH-ISLE-LETTER",
        "start": 0x0C862E,
        "end": 0x0C86A0,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:DB][SPEAKER:01]안녕, [NAM:00].\n편지가 왔어.[FIN]"
            "[PAL:02]주민 여러분을 남쪽 섬으로 초대합니다.\n배는 항구에서 출발![PAL:00]\n"
            "내용은 그게 전부야."
        ),
    },
    {
        "id": "EARLY-0C86A1-MAYOR-THANKS",
        "start": 0x0C86A1,
        "end": 0x0C8704,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:DB][SPEAKER:01]어서 와, [NAM:00].\n아이들을 구했다며?[FIN]"
            "촌장님이 감사하고 싶대.\n촌장님 댁으로 가 봐.\n[PAU:1E]다녀와."
        ),
    },
    {
        "id": "EARLY-0C87F1-FATHER-SUBURBS",
        "start": 0x0C87F1,
        "end": 0x0C8821,
        "end_command": 0xC0,
        "draft": "[BYTE:DB][SPEAKER:01]아버지는 교외 집으로\n돌아갈 생각이래.",
    },
    {
        "id": "EARLY-0C8885-FATHER-PERMISSION",
        "start": 0x0C8885,
        "end": 0x0C88C0,
        "end_command": 0xC0,
        "draft": "[BYTE:DB][SPEAKER:01][NAM:00], 무리하지 마.[FIN]아버지 허락 없인\n밖에 못 나가.",
    },
    {
        "id": "EARLY-0C88C1-EARTHQUAKE",
        "start": 0x0C88C1,
        "end": 0x0C88FD,
        "end_command": 0xC0,
        "draft": "[BYTE:DB][SPEAKER:01]와... 지진이다.\n[PAU:28][NAM:00], 이제 나가도 돼.\n조심해.",
    },
    {
        "id": "EARLY-0C8957-TOO-NOISY",
        "start": 0x0C8957,
        "end": 0x0C8982,
        "end_command": 0xC0,
        "draft": "[BYTE:DB][PAL:02]\n너무 시끄러워서\n통신기를 못 써.[PAL:00]",
    },
    {
        "id": "EARLY-0C8983-HINT-FATHER",
        "start": 0x0C8983,
        "end": 0x0C89CB,
        "end_command": 0xC0,
        "draft": "[WIPE]아버지는 [PAL:02]교외[PAL:00]로 갔어.\n밖에선 [PAL:02]해커[PAL:00]를 조심해.",
    },
    {
        "id": "EARLY-0C89CC-HINT-EXPERIENCE",
        "start": 0x0C89CC,
        "end": 0x0C8A20,
        "end_command": 0xC0,
        "draft": "[WIPE]경험을 쌓으면 책을 읽고\n발명 힌트를 얻을 수 있어.\n[PAU:1E]힘내.",
    },
    {
        "id": "EARLY-0C8A21-HINT-CAVE",
        "start": 0x0C8A21,
        "end": 0x0C8A77,
        "end_command": 0xC0,
        "draft": "[WIPE]동굴을 찾아봐.[FIN]폭발 충격으로 어딘가에\n입구가 열렸을 거야.",
    },
    {
        "id": "EARLY-0C8A78-HINT-COMBINE",
        "start": 0x0C8A78,
        "end": 0x0C8ABA,
        "end_command": 0xC0,
        "draft": "[WIPE]발명 기계로 주운 물건을\n조합해 봐. 쓸모가 생길 거야.",
    },
    {
        "id": "EARLY-0C8ABB-HINT-CARL",
        "start": 0x0C8ABB,
        "end": 0x0C8AFA,
        "end_command": 0xC0,
        "draft": "[WIPE]칼을 찾는다면 동굴을 다시 봐.\n전과 다른 곳일지도 몰라.",
    },
    {
        "id": "EARLY-0C8AFB-HINT-VISIT-HOUSE",
        "start": 0x0C8AFB,
        "end": 0x0C8B1D,
        "end_command": 0xC0,
        "draft": "[WIPE]우리 집으로 와.\n아버지가 기다려.",
    },
    {
        "id": "EARLY-0C8B1E-HINT-GUARD",
        "start": 0x0C8B1E,
        "end": 0x0C8B71,
        "end_command": 0xC0,
        "draft": "[WIPE]경비가 있어?\n[PAU:1E]시선을 끌어 봐.\n큰 소리를 내면 어때?",
    },
    {
        "id": "EARLY-0C8B72-HINT-KUROGANE",
        "start": 0x0C8B72,
        "end": 0x0C8BB1,
        "end_command": 0xC0,
        "draft": "[WIPE]쿠로가네가 걱정돼.\n아버지 집엔 없는 것 같아.\n확인해 줄래?",
    },
    {
        "id": "EARLY-0C8BB2-HINT-BOAT",
        "start": 0x0C8BB2,
        "end": 0x0C8BF5,
        "end_command": 0xC0,
        "draft": "[WIPE][PAL:02]배는 로코코 옆 항구에서 떠나.[PAL:00]\n좀 쉬러 가는 게 어때?",
    },
    {
        "id": "EARLY-0C8BF6-HINT-INVISIBLE",
        "start": 0x0C8BF6,
        "end": 0x0C8C40,
        "end_command": 0xC0,
        "draft": "[WIPE]안 보이는 적도 있어.\n수상한 곳에선 [PAL:02]카멜레온 안경[PAL:00]을 써 봐.",
    },
    {
        "id": "EARLY-0C8C41-HINT-COUNT",
        "start": 0x0C8C41,
        "end": 0x0C8C6A,
        "end_command": 0xC0,
        "draft": "[WIPE]백작 얘긴?\n민트에게 무슨 일이 생겼나?",
    },
    {
        "id": "EARLY-0C8C6B-HINT-SOLDIER",
        "start": 0x0C8C6B,
        "end": 0x0C8CB5,
        "end_command": 0xC0,
        "draft": "[WIPE]그 병사는 겁쟁이야.\n놀라게 할 방법 없을까?\n차단기라든지...",
    },
    {
        "id": "EARLY-0C8CB6-HINT-DEVICE",
        "start": 0x0C8CB6,
        "end": 0x0C8CF9,
        "end_command": 0xC0,
        "draft": "[WIPE]주민들을 위해 지진 장치를 부숴.\n길을 아는 사람이 있을 거야.",
    },
    {
        "id": "EARLY-0C8CFA-HINT-ESCAPE",
        "start": 0x0C8CFA,
        "end": 0x0C8D3A,
        "end_command": 0xC0,
        "draft": "[WIPE]진정해, [NAM:00].\n먼저 탈출할 틈을 만들어.\n쓸 만한 아이템 없어?",
    },
    {
        "id": "EARLY-0C8D3B-HINT-MAYOR-KEY",
        "start": 0x0C8D3B,
        "end": 0x0C8D76,
        "end_command": 0xC0,
        "draft": "[WIPE]촌장님 방 열쇠가 있을 거야.\n가짜 촌장 방은 확인했어?",
    },
    {
        "id": "EARLY-0C8D77-HINT-MEMORY",
        "start": 0x0C8D77,
        "end": 0x0C8DAD,
        "end_command": 0xC0,
        "draft": "[WIPE]아버지가 기억을 잃었나 봐.\n되찾을 방법부터 찾아.",
    },
    {
        "id": "EARLY-0C8DAE-HINT-LISTEN",
        "start": 0x0C8DAE,
        "end": 0x0C8DFA,
        "end_command": 0xC0,
        "draft": "[WIPE]낯선 곳에선 사람들 얘길 들어.\n해야 할 일을 알게 될 거야.",
    },
    {
        "id": "EARLY-0C8DFB-HINT-NAPOLEON",
        "start": 0x0C8DFB,
        "end": 0x0C8E38,
        "end_command": 0xC0,
        "draft": "[WIPE]나폴레옹에게 수리 도구를\n보여 주면 어떨까?",
    },
    {
        "id": "EARLY-0C8E39-HINT-JARS",
        "start": 0x0C8E39,
        "end": 0x0C8E78,
        "end_command": 0xC0,
        "draft": "[WIPE]단지는 빨강, 노랑, 파랑 순서야.\n[NAM:00], 침착하게 버텨.",
    },
    {
        "id": "EARLY-0C8E79-HINT-ENGINE-ROOM",
        "start": 0x0C8E79,
        "end": 0x0C8EC3,
        "end_command": 0xC0,
        "draft": "[WIPE]기관실 폭발로 요새 뒤쪽 길이\n열릴지도 몰라. [NAM:00], 힘내.",
    },
    {
        "id": "EARLY-0C8EC4-HINT-SCRAPS",
        "start": 0x0C8EC4,
        "end": 0x0C8F0B,
        "end_command": 0xC0,
        "draft": "[WIPE]고철마다 특성이 달라.\n조합을 살펴보고 기억해 둬.",
    },
    {
        "id": "EARLY-0C8F0C-HINT-WEAPON-LEVEL",
        "start": 0x0C8F0C,
        "end": 0x0C8F57,
        "end_command": 0xC0,
        "draft": "[WIPE]무기를 여러 개 조합하면\n더 높은 레벨의 무기를 만들 수 있어.",
    },
    {
        "id": "EARLY-0C8F58-HINT-WEAPON-TYPES",
        "start": 0x0C8F58,
        "end": 0x0C8FA6,
        "end_command": 0xC0,
        "draft": "[WIPE]무기나 공격이 안 통하는 적도 있어.\n여러 무기를 시험해 봐.",
    },
    {
        "id": "EARLY-0C8FA7-HINT-EVASION",
        "start": 0x0C8FA7,
        "end": 0x0C8FF4,
        "end_command": 0xC0,
        "draft": "[WIPE]회피력이 높은 적에겐\n로봇의 방어력을 올려 봐.",
    },
)

# Screenshot-reported text that lives in event branches, help-book pages, and
# fixed item-description records rather than the ordinary D7 catalogue.  Keep
# every original C0/CC/D2/D3/DE boundary at its absolute event-script address.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REPORT-05BF23-OF-COURSE",
        "start": 0x05BF23,
        "end": 0x05BF4E,
        "end_command": 0xC0,
        "draft": "[WIPE]그래, 넌 관심 없겠지.\n미안해.",
    },
    {
        "id": "REPORT-05F5A9-STAY-AS-LONG",
        "start": 0x05F5A9,
        "end": 0x05F5C4,
        "end_command": 0xCC,
        "draft": "그래. 편히 둘러봐.",
    },
    {
        "id": "REPORT-05FB53-CALL-WHEN-NEEDED",
        "start": 0x05FB53,
        "end": 0x05FB6D,
        "end_command": 0xDE,
        "draft": "[DFT]필요하면 연락할게.",
    },
    {
        "id": "REPORT-05FB6E-CALL-WHEN-NEEDED-TAIL",
        "start": 0x05FB6E,
        "end": 0x05FBEA,
        "end_command": 0xC0,
        "draft": (
            "[DFT]이 소리를 잘 기억해 두렴.[FIN]"
            "할 일을 끝내면 위층으로 올라가.[FIN]"
            "그래, 로봇을 아버지께 보여 드려.\n"
            "정말 기뻐하실 거야."
        ),
    },
    {
        "id": "REPORT-0C917B-ROBOT-BOOK-MENU",
        "start": 0x0C917B,
        "end": 0x0C91B7,
        "end_command": 0xCC,
        "draft": "[DFT] 1. 로봇\n 2. 로봇 설정\n 3. 로봇 특성\n 읽기 끝.",
    },
    {
        "id": "REPORT-0C928C-ROBOT-PARAMETERS",
        "start": 0x0C928C,
        "end": 0x0C93FE,
        "end_command": 0xDE,
        "draft": (
            "[WIPE][BYTE:5B]로봇 설정[FIN]"
            "[PAL:02]프로그램 포인트[PAL:00] -\n로봇의 능력치를 배분한다.[FIN]"
            "[PAL:02]공격[PAL:00] - 적에게 주는 피해가 늘어난다.[FIN]"
            "[PAL:02]방어[PAL:00] - 적에게 받는 피해가 줄어든다.[FIN]"
            "[PAL:02]속도[PAL:00] - 공격을 피할 확률이 높아진다.[FIN]"
            "[PAL:02]충전[PAL:00] - 에너지 회복 속도가 빨라진다.[FIN]"
            "적의 특성과 상태에 맞춰\n로봇을 활용하자.[BYTE:5D]"
        ),
    },
    {
        "id": "REPORT-0C93FF-ROBOT-TRAITS",
        "start": 0x0C93FF,
        "end": 0x0C948E,
        "end_command": 0xDE,
        "draft": (
            "[WIPE][BYTE:5B]로봇은 3기까지 등록할 수 있다.[FIN]"
            "2호와 3호는 각자 특성이 다르다.[FIN]"
            "2호는 근접전,\n3호는 특수 공격에 강하다.[FIN]"
            "상황에 맞게 사용하자.[BYTE:5D]"
        ),
    },
    {
        "id": "REPORT-01D27D-MACHINE-STRANGER",
        "start": 0x01D27D,
        "end": 0x01D2B0,
        "end_command": 0xDE,
        "draft": "[WIPE]처음 보는 손님이네.\n이 기계는 처음이지?",
    },
    {
        "id": "REPORT-01E173-SMOKE-DESCRIPTION",
        "start": 0x01E173,
        "end": 0x01E1B7,
        "end_command": 0xCC,
        "draft": "전투 중 사용하면\n도망칠 수 있고 적의 움직임을 멈춘다.",
    },
    {
        "id": "REPORT-01E1B8-CURE-DESCRIPTION",
        "start": 0x01E1B8,
        "end": 0x01E1D0,
        "end_command": 0xCC,
        "draft": "로봇 에너지를 회복.",
    },
    {
        "id": "REPORT-01E1D1-CLEAN-DESCRIPTION",
        "start": 0x01E1D1,
        "end": 0x01E20F,
        "end_command": 0xCC,
        "draft": "녹으로 에너지가 줄어들 때\n로봇을 정상으로 돌린다.",
    },
    {
        "id": "REPORT-01E210-REPAIR-DESCRIPTION",
        "start": 0x01E210,
        "end": 0x01E241,
        "end_command": 0xCC,
        "draft": "고철이 된 로봇을\n원래 상태로 복구한다.",
    },
    {
        "id": "REPORT-01E242-BIG-BOMB-DESCRIPTION",
        "start": 0x01E242,
        "end": 0x01E26D,
        "end_command": 0xCC,
        "draft": "전투 중 명령으로\n사용하는 폭탄.",
    },
    {
        "id": "REPORT-079134-INVENTION-INSPIRATION",
        "start": 0x079134,
        "end": 0x079291,
        "end_command": 0xD3,
        "draft": (
            "[WIPE]발명에는 [PAL:02]영감[PAL:00]이 필요해.[FIN]"
            "책을 읽는 것이 첫 번째 방법이야.[FIN]"
            "처음에는 어려워도\n언젠가 이해할 수 있어.[FIN]"
            "사람들의 말을 듣고\n주변을 자세히 살펴봐.[FIN]"
            "재료를 사려면 GP도 필요해.\n공짜는 아니니 잊지 마.[FIN]"
        ),
    },
    {
        "id": "REPORT-079294-INVENTION-COMBINATION",
        "start": 0x079294,
        "end": 0x07935C,
        "end_command": 0xD3,
        "draft": (
            "[WIPE]아이템 또는 로봇 장비를\n2개 고르면 [PAL:02]조합[PAL:00]할 수 있어.[FIN]"
            "고철로도 여러 물건을 만들 수 있지.[FIN]"
            "조합에는 GP가 들지 않아.\n여러 가지를 실험해 봐.[FIN]"
            "새 무기를 조합하면\n더 강한 무기가 될 수 있어.[FIN]"
        ),
    },
    {
        "id": "REPORT-07935F-ROBOT-TUTORIAL",
        "start": 0x07935F,
        "end": 0x079518,
        "end_command": 0xCC,
        "draft": (
            "[WIPE][SPEAKER:1C]은 한 번 만들면 든든한 동료야.[FIN]"
            "발명 기계에서 3기까지 만들 수 있어.[FIN]"
            "만든 뒤에도 능력을 강화할 수 있지.[FIN]"
            "무기와 장비는 조합으로 만들어.[FIN]"
            "프로그램을 바꾸면\n특수 공격도 바꿀 수 있어.[FIN]"
            "에너지가 부족하면 [PAL:02]수리[PAL:00],\n"
            "정비는 발명 기계에서 해.[FIN]"
            "전투에서는 명령으로 로봇을 불러.[FIN]"
            "더 듣겠어?\n 네, 알려 주세요.\n 아니요, 그만 들을래요."
        ),
    },
    {
        "id": "REPORT-06879F-EINST-FAILURE",
        "start": 0x06879F,
        "end": 0x068830,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:05][BYTE:DC][BYTE:06]········\n"
            "[BYTE:DC][BYTE:00]그 표정은 뭐냐?[FIN]"
            "발명은 실패할 때도 있어.[FIN]"
            "이해 못 하는 녀석은 귀찮아![FIN]"
            "돈 받고 일했으니 촌장에게 전해!"
        ),
    },
    {
        "id": "REPORT-05E4B0-MAYOR-DOG-PANIC",
        "start": 0x05E4B0,
        "end": 0x05E4E5,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:09][BYTE:DC][BYTE:09]…"
            "[PAU:1E][BYTE:DC][BYTE:01]개라고!\n"
            "[PAU:1E]이봐! 그 동물은 밖에 내보내!"
        ),
    },
    {
        "id": "REPORT-068831-EINST-GET-OUT",
        "start": 0x068831,
        "end": 0x06883F,
        "end_command": 0xC0,
        "draft": "[BYTE:D9][SPEAKER:05]나가!",
    },
    {
        "id": "REPORT-06886A-EINST-RESCUE",
        "start": 0x06886A,
        "end": 0x0688D9,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:05]동굴에 갇힌 아이들을 구하겠다.[FIN]"
            "내가 만든 특제 폭탄으로\n벽을 날려 버리지.[FIN]"
            "다들 물러서!"
        ),
    },
    {
        "id": "REPORT-0688DA-EINST-DETONATE",
        "start": 0x0688DA,
        "end": 0x06890D,
        "end_command": 0xC0,
        "draft": "[BYTE:D8][SPEAKER:05]이제 폭발시킨다.\n멋진 광경이 될 거야!",
    },
    {
        "id": "REPORT-06890E-EINST-SUCCESS",
        "start": 0x06890E,
        "end": 0x068944,
        "end_command": 0xC0,
        "draft": "[BYTE:D8][SPEAKER:05]성공이다! 아이들도 무사하군.\n감사 표시로…",
    },
    {
        "id": "REPORT-08E53F-SMALL-HOLE",
        "start": 0x08E53F,
        "end": 0x08E55C,
        "end_command": 0xD2,
        "draft": "[DFT][NAM:00]: [PAL:02]작은 구멍[PAL:00] 발견!",
    },
    {
        "id": "REPORT-08E55F-FALLEN-ROCKS",
        "start": 0x08E55F,
        "end": 0x08E587,
        "end_command": 0xD2,
        "draft": "[DFT]낙석으로 길이 막혀 있다…",
    },
    {
        "id": "REPORT-08E58A-LOCKED",
        "start": 0x08E58A,
        "end": 0x08E59A,
        "end_command": 0xD2,
        "draft": "[DFT]잠겨 있다…",
    },
)

# Opening wake-up cutscene.  These are D8/DA records embedded after event
# opcodes, so they were also outside the normal D7 catalogue.
SCREEN_TEXT_PATCHES += (
    {
        "id": "OPENING-05A5B2-PLEASE-WAKE-UP",
        "start": 0x05A5B2,
        "end": 0x05A5CB,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8][BYTE:D6][BYTE:00][NAM:00]! [PAU:3C]"
            "[NAM:00]![PAU:3C]\n일어나!"
        ),
    },
    {
        "id": "OPENING-05A5CC-STILL-ASLEEP",
        "start": 0x05A5CC,
        "end": 0x05A5F0,
        "end_command": 0xC0,
        "draft": "[BYTE:D8][BYTE:D6][BYTE:00]... [PAU:1E]아직도 자?\n그럼...",
    },
    {
        "id": "OPENING-05A5F1-AKIHABARA-AWAKE",
        "start": 0x05A5F1,
        "end": 0x05A697,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:DA][SPEAKER:02]하하하. 드디어 깨어났구나.\n오래도 잤네.[FIN]"
            "네가 자는 동안\n방 정리를 끝냈다.[FIN]"
            "이제 일어나렴.\n[PAL:02]나기사[PAL:00]가 기다린다.\n"
            "그 애도 방금 짐 정리를 끝냈어."
        ),
    },
)

# Additional early-story D8 pages reported during runtime testing.
SCREEN_TEXT_PATCHES += (
    {
        "id": "EARLY-0597FD-CHILDREN-RESCUE",
        "start": 0x0597FD,
        "end": 0x059877,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8]...힘든 일이겠지만\n아이들의 목숨이 달렸어.[FIN]"
            "도와줘.\n강가는 아주 위험하니 조심해.\n[PAU:1E]자, 가자."
        ),
    },
    {
        "id": "EARLY-05E3C1-EINST-LEFT",
        "start": 0x05E3C1,
        "end": 0x05E418,
        "end_command": 0xD3,
        "draft": (
            "[BYTE:D8][SPEAKER:09]아인스트는 이제 여기 없네.[FIN]"
            "아이들이 동굴에 갇혔단 말을 듣고\n도우러 갔지.[FIN]"
        ),
    },
    {
        "id": "EARLY-05E41E-EINST-PRAISE",
        "start": 0x05E41E,
        "end": 0x05E43F,
        "end_command": 0xC0,
        "draft": "소문대로 훌륭한 발명가야.",
    },
    {
        "id": "EARLY-059482-SAVED-DATA-FLASH",
        "start": 0x059482,
        "end": 0x05951B,
        "end_command": 0xC0,
        "draft": (
            "[WIPE]이봐, 좋은 걸 알려 주지.\n"
            "저장 데이터를 불러오면\n몸이 깜빡여.[FIN]"
            "그때는 적이 나타나지 않아.[FIN]"
            "적에게 둘러싸였을 땐\n기회를 봐서 도망쳐."
        ),
    },
    {
        "id": "EARLY-059878-CHILDREN-RIVERSIDE",
        "start": 0x059878,
        "end": 0x0598EF,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9]뭐라고?\n[PAU:14]무슨 일이야?\n"
            "[PAU:1E]아이들이 강가로 달려갔어.[FIN]"
            "산사태에 해커까지 있어.\n내가 데리러 갈게.\n"
            "[PAU:1E]아, 이제야 왔군!"
        ),
    },
    {
        "id": "EARLY-05FA31-ROBOT-MAINTENANCE",
        "start": 0x05FA31,
        "end": 0x05FB52,
        "end_command": 0xCC,
        "draft": (
            "[DFT][SPEAKER:01]좋아! 로봇 완성.[FIN]"
            "이제 정비하고 강화해 봐.[FIN]"
            "발명 기계에서 로봇의\n능력을 설정할 수 있어.\n"
            "나중에 시험해 봐.[FIN]"
            "작은 통신기를 줄게.\n어디서든 나와 연락할 수 있어.[FIN]"
            "필요할 때 장비한 뒤\nA 버튼으로 사용해.[FIN]"
            "[NAM:00] [PAL:02]통신기[PAL:00] 획득!"
        ),
    },
    {
        "id": "EARLY-0C91BE-ROBOT-BOOK-INFORMATION",
        "start": 0x0C91BE,
        "end": 0x0C928B,
        "end_command": 0xCC,
        "draft": (
            "[BYTE:5B]이 책에 [SPEAKER:1D] 정보를\n남겨 둘게.[FIN]"
            "[SPEAKER:1C]은 단순한 도구가 아니라,\n"
            "인간이 못 하는 일을 돕는 동료야.[FIN]"
            "친구처럼 믿을 수 있고,\n필요할 때 널 도와줄 거야.[BYTE:5D]"
        ),
    },
)

# Runtime re-audit batch 1.  These entries use D0/D8/D9 starts (or a D7 row
# that the conservative catalogue left pending), so they were visible in-game
# but absent from the original translation coverage count.  The mayor reward
# event is split at its absolute CC resume point.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-05B9B4-CARL-PLAY-AGAIN",
        "start": 0x05B9B4,
        "end": 0x05B9C4,
        "end_command": 0xC0,
        "draft": "[BYTE:D9][SPEAKER:07]또 놀자!",
    },
    {
        "id": "REAUDIT-05E0E4-MAYOR-HESITATES",
        "start": 0x05E0E4,
        "end": 0x05E109,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][NXT][BYTE:01][SPEAKER:09]뭐?[PAU:1E]왜..."
            "[PAU:1E]음...[NXT][BYTE:00]"
        ),
    },
    {
        "id": "REAUDIT-05E13A-MAYOR-REWARD",
        "start": 0x05E13A,
        "end": 0x05E1B1,
        "end_command": 0xCC,
        "draft": (
            "[BYTE:D8][SPEAKER:09]이번엔 정말 잘했다.\n계속 힘내거라.[FIN]"
            "마을의 감사 표시다.\n받아 두거라.[FIN]"
            "[NAM:00] [PAL:02]1000 GP[PAL:00] 획득!"
        ),
    },
    {
        "id": "REAUDIT-05E1B2-MAYOR-EXPECTING-YOU",
        "start": 0x05E1B2,
        "end": 0x05E1E0,
        "end_command": 0xC0,
        "draft": "[BYTE:D8][SPEAKER:09]오래 기다렸다.\n하하하.",
    },
    {
        "id": "REAUDIT-069790-TROLLEY-ESCAPE",
        "start": 0x069790,
        "end": 0x069844,
        "end_command": 0xC0,
        "draft": (
            "[WIPE]헤헤, 고맙다.\n말이 통하는군.\n잘 해낼 거야.[FIN]"
            "내가 경비를 끌 테니\n안으로 들어가 [PAL:02]광차[PAL:00]로 탈출해.[FIN]"
            "셋에 맞춰 움직여.\n[NXT][BYTE:09]...[NXT][BYTE:01]준비됐나?\n"
            "[PAU:3C]하나..[PAU:3C]둘...[PAU:3C]셋![NXT][BYTE:00]"
        ),
    },
    {
        "id": "REAUDIT-069C38-META-CRAB-THREAT",
        "start": 0x069C38,
        "end": 0x069CC0,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9][PAL:02]메타 크랩:\n[PAL:00]아직도 못 찾았나?\n"
            "아이 하나에 시간을 얼마나 쓰는 거냐![FIN]"
            "블랙모어가 네 무능을 알면\n[PAU:3C]넌 끝장이야!"
        ),
    },
    {
        "id": "REAUDIT-06A415-CARL-TAUNT",
        "start": 0x06A415,
        "end": 0x06A440,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:07]받아라!\n넌 못 이겨![FIN]"
            "[PAU:1E]...아![NXT][BYTE:00]"
        ),
    },
    {
        "id": "REAUDIT-06AAEB-PRISON-SIGN",
        "start": 0x06AAEB,
        "end": 0x06AB38,
        "end_command": 0xC0,
        "draft": "[DFT]메타 크랩이 침입자를\n가두는 감옥이다.\n관계자 외 출입 금지!",
    },
)

# Runtime re-audit batch 2: simple, single-entry spans in the first two story
# regions.  Complex spans with internal DE/D3 resume points are handled in a
# separate split-entry batch.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-058CF4-HUMAN-SPEAKING-CRAB",
        "start": 0x058CF4,
        "end": 0x058D62,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9]\n저 [PAL:02]크랩[PAL:00]이 사람처럼 말해.[FIN]"
            "[PAL:02]흥미롭군. [PAL:03]항구[PAL:00]라고?[FIN]"
            "[PAL:00]좋아, 가 보자!"
        ),
    },
    {
        "id": "REAUDIT-05951C-LONELY",
        "start": 0x05951C,
        "end": 0x05952E,
        "end_command": 0xC0,
        "draft": "[WIPE]음...\n외롭군...",
    },
    {
        "id": "REAUDIT-05C40B-TOO-BAD",
        "start": 0x05C40B,
        "end": 0x05C41A,
        "end_command": 0xC0,
        "draft": "[WIPE]이런, 안됐네.",
    },
    {
        "id": "REAUDIT-05DC45-MAYOR-IMPOSTOR",
        "start": 0x05DC45,
        "end": 0x05DC73,
        "end_command": 0xC0,
        "draft": "[BYTE:D8][SPEAKER:04]들키질 않아!\n진짜 촌장과 똑같아!",
    },
    {
        "id": "REAUDIT-05E10A-MAYOR-HOT-DAY",
        "start": 0x05E10A,
        "end": 0x05E139,
        "end_command": 0xC0,
        "draft": "[BYTE:D8][NXT][BYTE:01][SPEAKER:09]오늘 참 덥구나...\n하하하...",
    },
    {
        "id": "REAUDIT-05E325-MAYOR-EINST-INTRO",
        "start": 0x05E325,
        "end": 0x05E392,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:09]저기 [PAL:02]아인스트 박사[PAL:00]께 가게.\n"
            "유명한 발명가지.[FIN]해커 소문이 끊이지 않자\n"
            "도움을 주러 왔네.\n고마운 일이지."
        ),
    },
    {
        "id": "REAUDIT-05E393-MAYOR-INVENTOR-WISH",
        "start": 0x05E393,
        "end": 0x05E3C0,
        "end_command": 0xC0,
        "draft": "[BYTE:D8][SPEAKER:09]아인스트처럼\n훌륭한 발명가가 되거라.",
    },
    {
        "id": "REAUDIT-05EC33-MINT-SCOOP",
        "start": 0x05EC33,
        "end": 0x05EC6A,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9][SPEAKER:04][NXT][BYTE:01]특종이다![NXT][BYTE:00]"
            "안 돼!\n기사부터 써야 해!"
        ),
    },
    {
        "id": "REAUDIT-05F4E8-CHANGE-MIND",
        "start": 0x05F4E8,
        "end": 0x05F512,
        "end_command": 0xC0,
        "draft": "[WIPE]좋아. 마음 바뀌면\n다시 와.",
    },
    {
        "id": "REAUDIT-068EAD-TIRA-INTRO",
        "start": 0x068EAD,
        "end": 0x068F1F,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8]음...[PAU:3C]이 별 사람인가?[PAU:1E]"
            "안녕, 난 [PAL:03]티라[PAL:00]야.[FIN]"
            "여긴 동굴 별이야?[PAU:3C]\n별로 덥지 않고 딱 좋아.\n"
            "[PAU:1E]마음에 들어."
        ),
    },
    {
        "id": "REAUDIT-069CC1-META-CRAB-ORDER",
        "start": 0x069CC1,
        "end": 0x069CE5,
        "end_command": 0xC0,
        "draft": "[BYTE:D9]아이를 데려가.\n[SPEAKER:00]을 찾아![PAU:1E]서둘러!",
    },
    {
        "id": "REAUDIT-069CE6-META-CRAB-SHOWER",
        "start": 0x069CE6,
        "end": 0x069D01,
        "end_command": 0xC0,
        "draft": "[BYTE:D9]그럼... 난 씻으러 갈게.",
    },
    {
        "id": "REAUDIT-06AEA3-KINDNESS",
        "start": 0x06AEA3,
        "end": 0x06AEE8,
        "end_command": 0xC0,
        "draft": "[WIPE]호의를 몰라주다니!\n그러면 훌륭한 어른이 못 돼!",
    },
    {
        "id": "REAUDIT-06AFD3-DIRECTION-SENSE",
        "start": 0x06AFD3,
        "end": 0x06B011,
        "end_command": 0xC0,
        "draft": (
            "[DFT][SPEAKER:04]여기 전에 오지 않았어?[FIN]"
            "혹시 [PAU:1E]길치...?"
        ),
    },
    {
        "id": "REAUDIT-06BA26-HACKER-QUITS",
        "start": 0x06BA26,
        "end": 0x06BAD6,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9]구해 줘서 고마워.\n큰일 날 뻔했어.[FIN]"
            "[SPEAKER:00]가 열쇠야.\n가져가면 해커 대장이 된댔지만...[FIN]"
            "난 해커를 그만두고\n조용히 살 곳을 찾을래.\n"
            "[PAU:1E]정말 고마워."
        ),
    },
    {
        "id": "REAUDIT-06BD45-TETRON-IN-DOLL",
        "start": 0x06BD45,
        "end": 0x06BD78,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:08]찾았다.[PAU:1E]이거야.\n"
            "[SPEAKER:00]는 인형 안에 있어..."
        ),
    },
    {
        "id": "REAUDIT-06BD79-DOLL-POWER",
        "start": 0x06BD79,
        "end": 0x06BDFB,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][PAL:03]이 바보야. 그렇게 간단치 않아.[FIN]"
            "내 몸속 돌이\n이상한 힘을 줬어.\n줄 수 없어.[FIN]"
            "여기 있어.\n나중에 합류해.[PAL:00]"
        ),
    },
    {
        "id": "REAUDIT-06BEF9-IGOR-REPORT",
        "start": 0x06BEF9,
        "end": 0x06BFA2,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9]어땠나, 이고르?[PAU:1E]믿을 만한 아이군.[FIN]"
            "[PAL:02]정말 놀랐습니다.\n그 인형 때문에 애먹었는데...[FIN]"
            "[PAL:00]이제 이 집 시계가\n제시간을 찾겠군.\n"
            "라스크와 약속도 지켰으니 쉬어야지."
        ),
    },
    {
        "id": "REAUDIT-06C0A1-OLD-MAN-RETURNS",
        "start": 0x06C0A1,
        "end": 0x06C140,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:0F][NAM:00]! 널 찾고 있었다.\n"
            "덕분에 허리가 나았어.[FIN]테트론을 찾았나?\n"
            "난 돕지도 못했군.\n노인은 빠지는 게 낫지.[FIN]"
            "로코코로 돌아가나?\n할 말이 있다."
        ),
    },
    {
        "id": "REAUDIT-06C71F-FIND-DOG",
        "start": 0x06C71F,
        "end": 0x06C787,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:04]너! 아직도 여기야!?[PAU:28]"
            "...마침 잘 왔어.[FIN]이 사람이 다쳤어.\n"
            "[PAL:02]개를 찾아 줄래?[PAL:00]\n약은 그 개가 갖고 있어."
        ),
    },
    {
        "id": "REAUDIT-06C958-DOG-BARK",
        "start": 0x06C958,
        "end": 0x06C965,
        "end_command": 0xC0,
        "draft": "[DFT]멍멍멍!",
    },
    {
        "id": "REAUDIT-06D206-MANSION-GUIDE-ONE",
        "start": 0x06D206,
        "end": 0x06D2D5,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8]내 저택에 온 걸 환영하네.[PAU:1E]내가 이곳 주인,\n"
            "[PAL:02]존 폴 벨몬트 프링키 백작[PAL:00]일세.[FIN]"
            "이 글은 방문객을 위한 안내서야.[FIN]"
            "정확히 [PAL:02]100년 전[PAL:00],\n"
            "이고르가 본관과 서관을\n설계하고 지었지."
        ),
    },
    {
        "id": "REAUDIT-06D2D6-MANSION-GUIDE-TWO",
        "start": 0x06D2D6,
        "end": 0x06D342,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8]이 우물엔 물이 없지만\n지하 통로가 있네.[FIN]"
            "저택과 이어져 있지.\n[PAU:1E]보다시피 "
            "[PAU:1E]이게 [PAU:1E]내 취미야."
        ),
    },
    {
        "id": "REAUDIT-06D343-MANSION-GUIDE-THREE",
        "start": 0x06D343,
        "end": 0x06D3E8,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8]서관 안에서 본관으로 갈 수 있고,\n"
            "이 입구로도 들어갈 수 있네.[FIN]"
            "서관에는 [PAL:02]도서관[PAL:00]이 있지.[FIN]"
            "난 자서전을 쓰는 중이야.\n일부는 그곳에 보관했네."
        ),
    },
    {
        "id": "REAUDIT-06D3E9-MANSION-GUIDE-FOUR",
        "start": 0x06D3E9,
        "end": 0x06D479,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8]여기는 시계탑이야.\n[PAU:3C][PAL:02]젊은 라스크[PAL:00]가\n"
            "설계하고 지었지.[FIN]저택을 둘러보고 싶다면\n"
            "길을 열어 주겠네.\n[PAU:3C]이제 그만 읽게."
        ),
    },
    {
        "id": "REAUDIT-06DAE0-IGOR-WELCOME",
        "start": 0x06DAE0,
        "end": 0x06DB90,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8]어서 오게.\n[PAU:1E]자네가 올 줄 알았지.[FIN]"
            "아, 내 소개가 늦었군.\n난 [PAL:02]이고르[PAL:00], 이곳 관리자야.\n"
            "[PAL:02]프링키[PAL:00] 님을 모시지.[FIN]"
            "피곤할 테니\n쉴 방을 준비하겠네.\n이쪽으로."
        ),
    },
    {
        "id": "REAUDIT-06E07B-VOICE-IN-ROOM",
        "start": 0x06E07B,
        "end": 0x06E0DF,
        "end_command": 0xC0,
        "draft": (
            "[DFT][SPEAKER:04]뭐? [PAU:1E]이 방에서\n소리가 났다고?[FIN]"
            "무슨 말이야?\n아무도 없어.\n"
            "헛소리 말고 방으로 돌아가."
        ),
    },
    {
        "id": "REAUDIT-06E17E-DONT-WANDER",
        "start": 0x06E17E,
        "end": 0x06E1AB,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9][SPEAKER:04]말했잖아!\n"
            "위험하니 [PAU:1E]돌아다니지 마!"
        ),
    },
    {
        "id": "REAUDIT-06E9E0-NO-OTHER-WAY",
        "start": 0x06E9E0,
        "end": 0x06EA0D,
        "end_command": 0xC0,
        "draft": "[WIPE][SPEAKER:14]...유감이지만\n다른 방법이 없었어.",
    },
    {
        "id": "REAUDIT-06F44D-STEP-OVER-THERE",
        "start": 0x06F44D,
        "end": 0x06F47B,
        "end_command": 0xC0,
        "draft": "[WIPE][SPEAKER:08]정말인가!?\n그...그럼 저쪽으로 가게.",
    },
)

# Runtime re-audit batch 3: early-story compound events.  Every DE/D3 entry
# remains at its original absolute address so returning event PCs stay valid.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-068F7B-PRINCESS-RETURN",
        "start": 0x068F7B,
        "end": 0x068FCB,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8][NXT][BYTE:02]공주님! 나가면 안 돼요!\n"
            "배로 돌아가요...\n[NXT][BYTE:09]...[NXT][BYTE:02]"
            "[PAU:3C]어? 뭐지!"
        ),
    },
    {
        "id": "REAUDIT-068FCC-CONSUL-COINCIDENCE",
        "start": 0x068FCC,
        "end": 0x068FF4,
        "end_command": 0xD3,
        "draft": (
            "[BYTE:D8][NAM:00]인가?\n[PAU:3C]우연이군!\n"
            "난 재상이야.[FIN]"
        ),
    },
    {
        "id": "REAUDIT-068FF7-CONSUL-RECOGNIZES",
        "start": 0x068FF7,
        "end": 0x069060,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][NAM:00] 맞지?\n[PAU:1E]알아보겠어.\n"
            "[PAU:3C]난 재상이야.[FIN]...[PAU:3C]여긴 남들 눈에 띄어.\n"
            "다른 곳에서 설명하지.[NXT][BYTE:00]"
        ),
    },
    {
        "id": "REAUDIT-06EEF2-MINT-CONFRONTS",
        "start": 0x06EEF2,
        "end": 0x06EF19,
        "end_command": 0xDE,
        "draft": "[BYTE:D8][SPEAKER:04]잠깐!\n여기서 뭐 해?\n뭘 꾸미는 거야?",
    },
    {
        "id": "REAUDIT-06EF1A-PIPE-DOWN",
        "start": 0x06EF1A,
        "end": 0x06EF94,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8]조용히 해!\n찾는 것만 찾으면 떠날게.\n"
            "진정해.[FIN]너희 같은 애들과 일하기 힘들어!\n"
            "이 저택은 정말 이상해..."
        ),
    },
    {
        "id": "REAUDIT-06EF95-GHOST-WIMP",
        "start": 0x06EF95,
        "end": 0x06EFBD,
        "end_command": 0xDE,
        "draft": "[BYTE:D8][SPEAKER:04]...흠.\n유령이 무서워?\n겁쟁이네.",
    },
    {
        "id": "REAUDIT-06EFBE-GUARD-COMPLAINS",
        "start": 0x06EFBE,
        "end": 0x06F003,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8]...음... 아...\n[PAU:3C]조용히 해!\n"
            "[PAU:1E]왜 이런 골칫덩이를\n내가 지켜야 해!"
        ),
    },
)

# Runtime re-audit batch 4: volcano-village story entries.  The Shaman/Elder
# exchange is split at both fixed DE resume points.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-07A123-CRAB-BULLIES",
        "start": 0x07A123,
        "end": 0x07A165,
        "end_command": 0xC0,
        "draft": "[DFT]뭐야?\n이 크랩은 우리가 찾았어!\n좀 놀릴 거야. 저리 가!",
    },
    {
        "id": "REAUDIT-07C3A2-LISTENING-PROVERB",
        "start": 0x07C3A2,
        "end": 0x07C3EC,
        "end_command": 0xC0,
        "draft": "[WIPE]한 시간의 창피함보다\n평생 후회가 더 크지!\n언제든 와!",
    },
    {
        "id": "REAUDIT-07D1E2-SHAMAN-DEMAND",
        "start": 0x07D1E2,
        "end": 0x07D237,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8][PAL:02]주술사:\n[PAL:00]촌장! 보물을 안 돌려주면\n"
            "신께서 화산을 터뜨린대![FIN]내가 가져가지!"
        ),
    },
    {
        "id": "REAUDIT-07D238-ELDER-REFUSES",
        "start": 0x07D238,
        "end": 0x07D297,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8][PAL:02]촌장:\n[PAL:00]선한 신께서 그럴 리 없어!\n"
            "보물을 지키는 건 내 의무야.[FIN]넘겨줄 수 없네!"
        ),
    },
    {
        "id": "REAUDIT-07D298-SHAMAN-WARNS",
        "start": 0x07D298,
        "end": 0x07D2F0,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][PAL:02]주술사:\n[PAL:00]고집불통이군![FIN]"
            "나쁜 일이 생길 거야!\n생각을 바꿔! 다시 오지!"
        ),
    },
    {
        "id": "REAUDIT-07D2F1-DEFY-SHAMAN",
        "start": 0x07D2F1,
        "end": 0x07D31A,
        "end_command": 0xC0,
        "draft": "[BYTE:D9]주술사를 거역해?\n건방지군! 나가!",
    },
    {
        "id": "REAUDIT-07D31B-SHAMAN-MICE-CLAIM",
        "start": 0x07D31B,
        "end": 0x07D3B2,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][PAL:02]주술사:\n[PAL:00]촌장은 신의 말을 안 들어.\n"
            "그래서 신께서 내게 말하지![FIN]"
            "마을 사람들을 쥐로 만든 것도 나야!\n"
            "보물 있는 곳을 말해!"
        ),
    },
    {
        "id": "REAUDIT-07D3B3-ELDER-AND-SHAMAN",
        "start": 0x07D3B3,
        "end": 0x07D47B,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][PAL:02]촌장:\n[PAL:00]신께서 그럴 리 없어.\n"
            "보물을 지키는 건 내 의무야.[FIN]넘겨줄 수 없네.[FIN]"
            "[PAL:02]주술사:\n[PAL:00]늘 그렇듯 고집불통이군!\n"
            "이건 신의 마법이야![FIN]신의 말을 안 들으면\n"
            "누구든 쥐가 되지! 잘 봐!"
        ),
    },
    {
        "id": "REAUDIT-07D47C-EVERYONE-MICE",
        "start": 0x07D47C,
        "end": 0x07D4AB,
        "end_command": 0xC0,
        "draft": "[BYTE:D8]모두 쥐가 됐지.\n이젠 너다!\n...어?",
    },
    {
        "id": "REAUDIT-07D4AC-DEITY-CURSE-FAILS",
        "start": 0x07D4AC,
        "end": 0x07D51F,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9]또 방해야!\n주술사가 화나셨어.\n"
            "널 쥐로 만들 거야!\n신의 저주다![FIN]"
            "[NXT][BYTE:09].........\n[PAU:1E][NXT][BYTE:01]???????????[NXT][BYTE:00]"
        ),
    },
    {
        "id": "REAUDIT-07D7BB-WAIT-FOR-DEITY",
        "start": 0x07D7BB,
        "end": 0x07D7FE,
        "end_command": 0xC0,
        "draft": "[BYTE:D8]여기서 기다려.\n곧 신께서 오실 거야.\n우린 무서우니 간다!",
    },
    {
        "id": "REAUDIT-07E33B-MADE-PROGRESS",
        "start": 0x07E33B,
        "end": 0x07E361,
        "end_command": 0xC0,
        "draft": "[DFT]하하하.\n드디어 여기까지 왔군!",
    },
    {
        "id": "REAUDIT-07E868-CANNOT-ESCAPE",
        "start": 0x07E868,
        "end": 0x07E88B,
        "end_command": 0xC0,
        "draft": "[BYTE:D9]\n준비됐나?[PAU:14]못 달아나!",
    },
)

# Runtime re-audit batch 5: Choco meeting/lab events.  The telegram and lab
# alarm scenes are split at their fixed DE/CC resume entries.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-088A61-MINT-ROSE-ROOF",
        "start": 0x088A61,
        "end": 0x088AE9,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9][SPEAKER:04][NAM:00], [PAU:3C]가짜 촌장 기사에 쓸\n"
            "사진 찍자.[FIN]지금 그럴 때가 아니라고?\n"
            "[PAU:1E]로즈를 찾아?\n아마 [PAL:02]옥상[PAL:00]에 있어..."
            "[PAU:3C]무슨 일인데?"
        ),
    },
    {
        "id": "REAUDIT-0891A4-CONTACT-CARL",
        "start": 0x0891A4,
        "end": 0x0891CC,
        "end_command": 0xC0,
        "draft": "[WIPE]...아.\n칼과 연락될 줄 알았는데...",
    },
    {
        "id": "REAUDIT-08A51E-GATEAU-PLAN",
        "start": 0x08A51E,
        "end": 0x08A553,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:15]내가 잘 들었나?\n"
            "가토가 뭘 한다고?\n공주가..."
        ),
    },
    {
        "id": "REAUDIT-08A554-JOIN-MEETING",
        "start": 0x08A554,
        "end": 0x08A573,
        "end_command": 0xC0,
        "draft": "[BYTE:D8][SPEAKER:15][NAM:00], 회의에 와.\n도와줘.",
    },
    {
        "id": "REAUDIT-08A677-SOLDIER-TELEGRAM",
        "start": 0x08A677,
        "end": 0x08A6B5,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8][PAL:02]병사:\n[PAL:00]큰일입니다!\n"
            "가토에게 전보가 왔는데...\n[PAU:1E]저..."
        ),
    },
    {
        "id": "REAUDIT-08A6B6-GATEAU-TELEGRAM",
        "start": 0x08A6B6,
        "end": 0x08A7EF,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:15]말해! 변명은 됐어![FIN]"
            "[PAL:02]병사:\n[PAL:00]그... 읽겠습니다.[FIN]"
            "[PAL:02]티라와 테트론은 내 손에 있다.\n"
            "너희는 이길 수 없다.\n저항을 멈추고 항복하라![FIN]"
            "아니면 티라의 목숨은 없다.\n\n"
            "[PAU:3C][NXT][BYTE:07]해커 지배자 [PAU:14]가토[FIN]"
            "[PAL:00][SPEAKER:15]......[NXT][BYTE:00]뭐라고!\n"
            "그자가 해커 지배자였나?\n[PAU:1E]몰랐군...[FIN]"
            "뭔가 해야 해!\n[PAU:1E]모두 회의실로 모여!\n"
            "대책을 정한다!"
        ),
    },
    {
        "id": "REAUDIT-08ABB1-SHOW-WAY",
        "start": 0x08ABB1,
        "end": 0x08ABBF,
        "end_command": 0xC0,
        "draft": "[WIPE]따라와.",
    },
    {
        "id": "REAUDIT-08ABE2-TAKE-TO-SPACESHIP",
        "start": 0x08ABE2,
        "end": 0x08AC19,
        "end_command": 0xC0,
        "draft": "[WIPE]알겠어. 준비되면 말해.\n우주선으로 데려갈게.",
    },
    {
        "id": "REAUDIT-08AC1A-WHEN-READY",
        "start": 0x08AC1A,
        "end": 0x08AC38,
        "end_command": 0xC0,
        "draft": "[WIPE]알겠어. 준비되면 말해.",
    },
    {
        "id": "REAUDIT-08B451-INVENTORY-FULL",
        "start": 0x08B451,
        "end": 0x08B47F,
        "end_command": 0xC0,
        "draft": "[WIPE]정말!? 가방이 꽉 찼어!\n못 줘! 하하하.",
    },
    {
        "id": "REAUDIT-08B480-TOO-MUCH-TO-ASK",
        "start": 0x08B480,
        "end": 0x08B4C1,
        "end_command": 0xC0,
        "draft": (
            "[WIPE]...그래, [PAU:1E]맞아.\n"
            "너무 무리한 부탁이었군.\n[PAU:1E]...미안해."
        ),
    },
    {
        "id": "REAUDIT-08BE20-WANTS-TO-SEE",
        "start": 0x08BE20,
        "end": 0x08BE59,
        "end_command": 0xCC,
        "draft": "[WIPE]그러니 더 보고 싶잖아!\n잠깐만.\n안 돼!",
    },
    {
        "id": "REAUDIT-08BE5A-LAB-ALARM",
        "start": 0x08BE5A,
        "end": 0x08BE9B,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D9][SPEAKER:19]큰일입니다!\n테트론과 [PAU:1E]티라,\n"
            "[PAU:1E]가토가 [PAU:1E]모두 사라졌어요!"
        ),
    },
    {
        "id": "REAUDIT-08BE9C-LAB-EXPLANATION",
        "start": 0x08BE9C,
        "end": 0x08BF09,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9][SPEAKER:15]뭐라고? 설명해![FIN]"
            "[SPEAKER:19]잠깐 자리를 비운 사이\n"
            "그가 연구실을 나갔어요![FIN]"
            "[SPEAKER:15]서 있지 말고 찾아!"
        ),
    },
    {
        "id": "REAUDIT-08BF0A-MEMORY-FILM",
        "start": 0x08BF0A,
        "end": 0x08BF64,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9][SPEAKER:19]도와줘서 고마워.\n"
            "[PAU:1E][PAL:02][SPEAKER:1A] 잔해[PAL:00]는 보관했어.[FIN]"
            "기억에 남아 있었어.\n"
            "[PAU:1E]영상을 찍었으니 봐."
        ),
    },
)

# Runtime re-audit batch 6: Hacker lab and past-Choco story, first half.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-09805A-TRIBUTE",
        "start": 0x09805A,
        "end": 0x09808E,
        "end_command": 0xC0,
        "draft": "[BYTE:D8]여기 공물이야.\n소장실로 가져가.",
    },
    {
        "id": "REAUDIT-0982A3-GUARD-POST",
        "start": 0x0982A3,
        "end": 0x0982DD,
        "end_command": 0xC0,
        "draft": "[DFT]이봐. 자리 지켜.\n안에는 못 들어가!",
    },
    {
        "id": "REAUDIT-09898C-WHERE-ARE-WE",
        "start": 0x09898C,
        "end": 0x0989AE,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9][SPEAKER:04][NAM:00], 간 것 같아.\n"
            "[PAU:1E]여긴 어디지?"
        ),
    },
    {
        "id": "REAUDIT-0989F5-DEITY-REVEALED",
        "start": 0x0989F5,
        "end": 0x098A9A,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9]어서 와, 꼬마 아가씨.\n무서워 마. 난 상냥해.[FIN]"
            "난 신이니까...[FIN]\n[NXT][BYTE:09].............\n[NXT][BYTE:00]"
            "[PAU:0A]너는...[PAU:0A]민트![FIN]"
            "[SPEAKER:04]그리고 너!\n[PAU:1E]또 나쁜 짓이야?\n"
            "창피한 줄 알아!"
        ),
    },
    {
        "id": "REAUDIT-098A9B-COWARD",
        "start": 0x098A9B,
        "end": 0x098AB9,
        "end_command": 0xC0,
        "draft": "[BYTE:D9][SPEAKER:04]도망칠 셈이야?!\n겁쟁이!",
    },
    {
        "id": "REAUDIT-098C22-KOTETSU-INVITATION",
        "start": 0x098C22,
        "end": 0x098C5C,
        "end_command": 0xC0,
        "draft": "[BYTE:D8]나야, 코테츠.\n\n너도 속았나?\n딱하군.",
    },
    {
        "id": "REAUDIT-099540-LAB-STAMP",
        "start": 0x099540,
        "end": 0x0995E8,
        "end_command": 0xC0,
        "draft": (
            "[WIPE]좋아... 좋아!\n[PAU:1E]조용히 하면 손에 "
            "[PAL:02]도장[PAL:00]을 찍어 주지![FIN]"
            "이게 있으면 연구소 대부분에 들어갈 수 있어.\n"
            "하지만 [PAL:03]비밀[PAL:00]이야.[FIN]"
            "[NAM:00]은 병사에게 [PAL:02]도장[PAL:00]을 받았다!"
        ),
    },
    {
        "id": "REAUDIT-099BE5-RESEARCH-BUDGET",
        "start": 0x099BE5,
        "end": 0x099C2E,
        "end_command": 0xC0,
        "draft": (
            "[DFT]조용히!\n소장이 연구비로 예산을 다 써서\n"
            "제대로 된 밥도 못 해!"
        ),
    },
    {
        "id": "REAUDIT-099CFB-RUDE-KIDS",
        "start": 0x099CFB,
        "end": 0x099D3F,
        "end_command": 0xC0,
        "draft": "[WIPE]기가 막혀!\n요즘 애들은 너무 바쁘고 무례해!\n가지 마!",
    },
    {
        "id": "REAUDIT-09C00E-HUGE-THING",
        "start": 0x09C00E,
        "end": 0x09C065,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9][PAL:02]마을 사람:\n[PAL:00]...[PAU:1E]야야야야!![FIN]"
            "이게 뭐야!\n엄청 큰 게 왔어!\n큰일이야!"
        ),
    },
    {
        "id": "REAUDIT-09C39D-RASK-DISTRACTED",
        "start": 0x09C39D,
        "end": 0x09C415,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:0D][PAL:02]라스크[PAL:00]였나?\n"
            "[PAU:1E]아무 말도 안 했어?[FIN]"
            "[SPEAKER:12]딴생각에 빠져 있었어.[FIN]"
            "늘 그렇지...\n[PAU:1E]그래도 이곳 얘긴 해 줬어..."
        ),
    },
    {
        "id": "REAUDIT-09C416-RASK-RETURNS",
        "start": 0x09C416,
        "end": 0x09C473,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9]...[PAU:1E]라스크![PAU:1E]네 얘기 중이었어![FIN]"
            "왜 [PAU:1E][PAL:02]초코[PAL:00]를 떠났어?\n"
            "무슨 일이 있었지?\n[PAU:1E]그리고 [SPEAKER:00]은...?"
        ),
    },
    {
        "id": "REAUDIT-09C4C2-COOKIE-WAIT",
        "start": 0x09C4C2,
        "end": 0x09C507,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:0D]쿠키, [PAU:1E]잠깐.[FIN]"
            "진짜인지 직접 보여 줘.\n"
            "그 뒤 나폴레옹에게 확인하지."
        ),
    },
    {
        "id": "REAUDIT-09C519-WATCH-HIM",
        "start": 0x09C519,
        "end": 0x09C553,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:0D]우리 둘은 몰라.\n"
            "[PAU:1E]하지만 아주 수상해.\n지켜봐야 해."
        ),
    },
    {
        "id": "REAUDIT-09C848-DEPARTURE-PLAN",
        "start": 0x09C848,
        "end": 0x09C92C,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:0C]가토, 끔찍한 일이야!\n"
            "쿠키가 반대할 거야![FIN]"
            "[SPEAKER:0D]이 배는 곧 떠난다.\n"
            "남들 눈이 없는 곳에서 연구를 계속하지.[FIN]"
            "나폴레옹, 떠난 뒤 네 기억을 고쳐 주마.\n"
            "넌 내 조수가 돼.[FIN]"
            "[SPEAKER:0C]난 [PAU:1E][SPEAKER:1A]야.\n거절할 수 없어.[FIN]"
            "출발 준비를 하지."
        ),
    },
)

# Runtime re-audit batch 7: past-Choco story, second half, plus the clean
# mouse warning at the end of the neighbouring mixed data table.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-08E518-MOUSE-WAIT",
        "start": 0x08E518,
        "end": 0x08E52E,
        "end_command": 0xC0,
        "draft": "[DFT]...앗! 쥐다!\n잠깐!",
    },
    {
        "id": "REAUDIT-09C92D-BOY-THWARTS-PLAN",
        "start": 0x09C92D,
        "end": 0x09C960,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:0D]봤지? 라스크 닮은 소년이\n"
            "계획을 막고 있어.[PAU:3C]"
        ),
    },
    {
        "id": "REAUDIT-09CCA9-TETRON-CONTROLS-YOU",
        "start": 0x09CCA9,
        "end": 0x09CCE0,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8][SPEAKER:0C]가토, 무슨 짓이야!?[FIN]"
            "이 테트론이 시킨 거야?"
        ),
    },
    {
        "id": "REAUDIT-09CCE1-LOOK-AT-TETRON",
        "start": 0x09CCE1,
        "end": 0x09CD0E,
        "end_command": 0xC0,
        "draft": "[BYTE:D8][SPEAKER:0D]궁금한가?\n말해 주지.\n이걸 봐.",
    },
    {
        "id": "REAUDIT-09CDD0-FUTURE-FORTRESS",
        "start": 0x09CDD0,
        "end": 0x09CE0D,
        "end_command": 0xC0,
        "draft": "[BYTE:D8][SPEAKER:0D]보이나? 이건 미래에\n초코를 공격할 요새다.",
    },
    {
        "id": "REAUDIT-09CE0E-FORTRESS-REACTOR",
        "start": 0x09CE0E,
        "end": 0x09CE4B,
        "end_command": 0xC0,
        "draft": "[BYTE:D8][SPEAKER:0D]이 요새엔 강력한 원자로가 있다.\n방벽도 되지.",
    },
    {
        "id": "REAUDIT-09CE4C-CONQUER-PLANETS",
        "start": 0x09CE4C,
        "end": 0x09CE8E,
        "end_command": 0xC0,
        "draft": "[BYTE:D8]초코만이 아니다.\n모든 행성을 정복할 요새다.",
    },
    {
        "id": "REAUDIT-09D134-FIVE-THOUSAND-GP",
        "start": 0x09D134,
        "end": 0x09D1BF,
        "end_command": 0xC0,
        "draft": (
            "[WIPE]정말인가?[PAU:1E]고맙네, 받지.\n"
            "이고르에게도 큰 도움이 될 거야.[FIN]"
            "보답해야겠군.\n[PAU:1E]많진 않지만 받아 줘. 고맙네.[FIN]"
            "[NAM:00] [PAL:02]5000 GP[PAL:00] 획득!"
        ),
    },
    {
        "id": "REAUDIT-09D5A8-WOMAN-BLOCKED",
        "start": 0x09D5A8,
        "end": 0x09D662,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][PAL:03]여자:\n[PAL:00]뭐라고, [PAU:1E]못 간다고요?\n"
            "아픈 사람이...\n[PAU:1E]빨리 가야 해요.[FIN]"
            "[SPEAKER:08]그 사람은 됐고!\n난 어때?[FIN]"
            "뭐예요? 못됐네요![FIN]"
            "[PAL:03]여자:\n[PAL:00]어머... 세상에...\n...음...\n"
            "[PAU:1E][NXT][BYTE:01]당신은...![NXT][BYTE:00]"
        ),
    },
    {
        "id": "REAUDIT-09D663-EAVESDROPPER",
        "start": 0x09D663,
        "end": 0x09D6D2,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9][SPEAKER:08]흠![FIN][PAU:1E]뭐야? 엿듣고 있었군!\n"
            "이제 재미 좀 보자![FIN]난 [PAL:02]도둑단[PAL:00]이다!\n"
            "덤비면 후회할 거야!"
        ),
    },
    {
        "id": "REAUDIT-09D6D3-COWARD-SLEEP",
        "start": 0x09D6D3,
        "end": 0x09D6F4,
        "end_command": 0xC0,
        "draft": "[BYTE:D9][SPEAKER:08]겁쟁이는 집에 가서 자!",
    },
    {
        "id": "REAUDIT-09D6F5-AGAIN",
        "start": 0x09D6F5,
        "end": 0x09D717,
        "end_command": 0xC0,
        "draft": "[BYTE:D9][SPEAKER:08]끈질기군!\n다시 붙자!",
    },
    {
        "id": "REAUDIT-09D718-TELL-ROSE",
        "start": 0x09D718,
        "end": 0x09D739,
        "end_command": 0xC0,
        "draft": "[BYTE:D9][SPEAKER:08]으악!\n로즈에게 이를 거야!",
    },
    {
        "id": "REAUDIT-09D7B2-POLON-RESCUE",
        "start": 0x09D7B2,
        "end": 0x09D89F,
        "end_command": 0xC0,
        "draft": (
            "[DFT][PAL:03]여자:\n[PAL:00]이제 괜찮아요?\n"
            "많이 아팠으니 이건 필요 없겠네요...[FIN]"
            "음... [PAU:1E]미안해요.\n[PAU:1E]자는 동안 몰랐죠.\n"
            "난 [PAL:03]폴론[PAL:00]이에요.[FIN]"
            "강가에 쓰러진 걸 발견해\n우리 집으로 데려왔어요.\n"
            "[PAU:1E]많이 다쳤어요...[FIN]우리 집으로 가요.\n"
            "푹 쉬어야 해요...[PAU:3C]알겠죠?"
        ),
    },
    {
        "id": "REAUDIT-09E2C8-ROBOT-SURPRISE",
        "start": 0x09E2C8,
        "end": 0x09E338,
        "end_command": 0xC0,
        "draft": (
            "[DFT][SPEAKER:0C]놀랐어!\n[PAU:1E]이곳 사람도 로봇을 만들 줄이야.[FIN]"
            "가토와 함께 왔지만\n헤어졌어.\n"
            "[PAU:1E]그가 그런 짓을 하다니..."
        ),
    },
    {
        "id": "REAUDIT-09E3DB-REPAIR-NAPOLEON",
        "start": 0x09E3DB,
        "end": 0x09E47C,
        "end_command": 0xC0,
        "draft": (
            "[WIPE][SPEAKER:0C]그건 수리 부품이야?[PAU:1E]아...[PAU:1E]잊고 있었어.\n"
            "할 일이 있어.[FIN][SPEAKER:00]을 돌려주지 않으면\n"
            "라스크를 볼 면목이 없어.\n[PAU:1E]네게 빚졌군.[FIN]"
            "[NAM:00]이 [PAL:02]수리[PAL:00]로\n"
            "[PAL:02]나폴레옹[PAL:00]을 고쳤다!"
        ),
    },
    {
        "id": "REAUDIT-09E47D-NO-SYMPATHY",
        "start": 0x09E47D,
        "end": 0x09E4AF,
        "end_command": 0xC0,
        "draft": "[WIPE][SPEAKER:0C]동정은 싫어!\n멈춘 곳을 남에게 보이기 싫어!",
    },
)

# Runtime re-audit batch 8: final region.  All D3/DE/CC continuation entries
# are split so event resumes and choice/call flows keep their original PCs.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-0A8606-RIVER-LIGHT",
        "start": 0x0A8606,
        "end": 0x0A8688,
        "end_command": 0xC0,
        "draft": (
            "[DFT]강가에 [PAU:14]엄청난 빛이 떨어지는 걸 봤어!![FIN]"
            "보러 가고 싶었는데 엄마가 위험하대.\n"
            "남자애들은 갔는데!!\n[PAU:14]걔들은 다 해도 되나 봐!"
        ),
    },
    {
        "id": "REAUDIT-0A87C5-STINGY-MAN",
        "start": 0x0A87C5,
        "end": 0x0A87DD,
        "end_command": 0xC0,
        "draft": "[WIPE]쩨쩨한 아저씨![PAU:28]흥!",
    },
    {
        "id": "REAUDIT-0A87DE-FLOWER-SEEDS",
        "start": 0x0A87DE,
        "end": 0x0A8825,
        "end_command": 0xC0,
        "draft": (
            "[WIPE]정말?! 좋은 사람이네!\n내가 심을게![FIN]"
            "[NAM:00]은 [PAL:02]꽃씨[PAL:00]를 건넸다."
        ),
    },
    {
        "id": "REAUDIT-0A8EA5-DONATE-TEN",
        "start": 0x0A8EA5,
        "end": 0x0A8EB1,
        "end_command": 0xD3,
        "draft": "[WIPE]응,[PAL:02]10 GP",
    },
    {
        "id": "REAUDIT-0A8EB4-DONATE-HUNDRED",
        "start": 0x0A8EB4,
        "end": 0x0A8ED3,
        "end_command": 0xC0,
        "draft": "[WIPE]좋아, [PAL:02]100 GP[PAL:00].\n후원 고마워.",
    },
    {
        "id": "REAUDIT-0A8ED4-DONATE-THOUSAND",
        "start": 0x0A8ED4,
        "end": 0x0A8EFA,
        "end_command": 0xC0,
        "draft": "[WIPE]뭐? [PAU:1E][PAL:02]1000 GP[PAL:00]?\n[PAU:1E]후원 고마워!",
    },
    {
        "id": "REAUDIT-0A8FF0-MAYOR-HOUSE-COMPLETE",
        "start": 0x0A8FF0,
        "end": 0x0A903C,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8]드디어 촌장 집이 완성됐다!\n"
            "마을 발전의 상징이 될 거야."
        ),
    },
    {
        "id": "REAUDIT-0A903D-LARGE-DONOR",
        "start": 0x0A903D,
        "end": 0x0A906E,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8]큰돈을 낸 분입니다.\n"
            "[PAL:02][NAM:00][PAL:00] 님이죠."
        ),
    },
    {
        "id": "REAUDIT-0A906F-DONATION-STATUE",
        "start": 0x0A906F,
        "end": 0x0A90EB,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8][NAM:00] 님은 지금까지\n"
            "[BYTE:C6][BYTE:04][BYTE:86][BYTE:0B] GP를 기부했습니다.[FIN]"
            "큰돈을 내 주셔서[FIN]마을 위원회는 광장에\n"
            "[PAL:02][NAM:00] 동상[PAL:00]을 세우기로 했습니다."
        ),
    },
    {
        "id": "REAUDIT-0A90EC-ELECTION-PHOTO",
        "start": 0x0A90EC,
        "end": 0x0A919A,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8]마을 위원회가 선거를 준비합니다.\n"
            "그 뒤 촌장 집을 이용할 수 있습니다.[FIN]"
            "모두 협조해 주세요.\n이제 [PAU:1E][PAL:02]기념사진[PAL:00]을 찍습니다.[FIN]"
            "촌장 집 앞으로 모여 주세요."
        ),
    },
    {
        "id": "REAUDIT-0AB657-DONATE-FIVE-THOUSAND",
        "start": 0x0AB657,
        "end": 0x0AB6A7,
        "end_command": 0xC0,
        "draft": (
            "[WIPE]오... [PAU:14]정말?!\n[PAU:14]친절에 감동했어! 고마워![FIN]"
            "[NAM:00]은 [PAL:02]5000 GP[PAL:00]를 건넸다!"
        ),
    },
    {
        "id": "REAUDIT-0AB6A8-JUST-KIDDING",
        "start": 0x0AB6A8,
        "end": 0x0AB6C3,
        "end_command": 0xC0,
        "draft": "[WIPE]하하, 농담이야. 걱정 마.",
    },
    {
        "id": "REAUDIT-0AB6C4-NO-MONEY",
        "start": 0x0AB6C4,
        "end": 0x0AB6E7,
        "end_command": 0xC0,
        "draft": "[WIPE]그런 돈 없으면서 허세 마.",
    },
    {
        "id": "REAUDIT-0AC086-DOOR-GUARD",
        "start": 0x0AC086,
        "end": 0x0AC0CE,
        "end_command": 0xC0,
        "draft": (
            "[DFT][BYTE:CF][BYTE:FC][BYTE:C0][BYTE:8A][FIN]"
            "뭐? 문을 안 지키면 바보?\n"
            "[PAU:28][NXT][BYTE:08]...[NXT][BYTE:00]맞아! 고마워!"
        ),
    },
    {
        "id": "REAUDIT-0AC538-THREE-TETRONS",
        "start": 0x0AC538,
        "end": 0x0AC56B,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8][SPEAKER:0A]잘 들어! 너희 덕분에\n"
            "[SPEAKER:00] 3개를 모았다!"
        ),
    },
    {
        "id": "REAUDIT-0AC56C-OCCUPY-QUINTENIX",
        "start": 0x0AC56C,
        "end": 0x0AC612,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8]이제 시작이다!\n퀸티닉스를 점령해 힘을 보이자!\n"
            "[PAL:02]새 무기[PAL:00]도 있다.[FIN]좋아, 모두 가자!\n"
            "고향 사람들에게 우리 힘을\n보여 줄 기회다!"
        ),
    },
    {
        "id": "REAUDIT-0AD3BE-DRG-ASSISTANT",
        "start": 0x0AD3BE,
        "end": 0x0AD46D,
        "end_command": 0xC0,
        "draft": (
            "[DFT]난 [PAL:02]Dr.G[PAL:00]의 조수야.\n"
            "박사라지만 컴퓨터 전문가이지.[FIN]"
            "사람의 [PAL:02]기억을 컴퓨터에 저장[PAL:00]하려고 해.\n"
            "결과도 좋아.[FIN]실험 대상은 [PAL:02]기억상실[PAL:00]이었는데..."
        ),
    },
    {
        "id": "REAUDIT-0AD663-INVENTORY-REARRANGE",
        "start": 0x0AD663,
        "end": 0x0AD6A1,
        "end_command": 0xC0,
        "draft": "[WIPE]고마워요!\n대신 이걸 드리죠.\n가방을 정리해 주세요.",
    },
    {
        "id": "REAUDIT-0AD6A2-MAINFRAME-KEY",
        "start": 0x0AD6A2,
        "end": 0x0AD793,
        "end_command": 0xCC,
        "draft": (
            "[WIPE][NAM:00]은 [PAL:02]500 GP[PAL:00]를 건넸다![FIN]"
            "고마워요. 이번 달 청구서를 낼 수 있겠어요.[FIN]"
            "[PAL:02]메인프레임[PAL:00]에 그의 기억이 저장돼 있어요.[FIN]"
            "하지만 기밀이라 보호해야 해요.[FIN]"
            "이걸 드리죠.\n[PAL:02]메인프레임실[PAL:00]에 들어갈 수 있어요.\n"
            "Dr.G의 비밀이에요.[FIN][NAM:00] [PAL:02]열쇠[PAL:00] 획득!"
        ),
    },
    {
        "id": "REAUDIT-0AD794-NO-FIVE-HUNDRED",
        "start": 0x0AD794,
        "end": 0x0AD7CC,
        "end_command": 0xC0,
        "draft": "[WIPE]돈이... 없어요?!\n다 써 버렸어요?\n너무해! 흑!",
    },
    {
        "id": "REAUDIT-0AD80B-MAINFRAME-NETWORK",
        "start": 0x0AD80B,
        "end": 0x0AD874,
        "end_command": 0xC0,
        "draft": (
            "[DFT]이 요새 컴퓨터는\n모두 네트워크로 연결돼 있다.[FIN]"
            "여기가 [PAL:02]메인프레임[PAL:00]이다.\n"
            "메인프레임실은 Dr.G만 들어간다."
        ),
    },
    {
        "id": "REAUDIT-0ADAB6-PRISON-GUARD",
        "start": 0x0ADAB6,
        "end": 0x0ADAFE,
        "end_command": 0xC0,
        "draft": "[DFT]뭘 원해? 여긴 쓰레기장이 아냐.\n죄수들이 있다. 못 들어가.",
    },
    {
        "id": "REAUDIT-0AE322-STONE-MYSTERY",
        "start": 0x0AE322,
        "end": 0x0AE390,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8][SPEAKER:0A]...모르겠어!\n해커는 왜 이 돌에 집착하지?[FIN]"
            "아키하바라는 시간과 관련 있다지만...\n"
            "아무리 봐도 그냥 돌이야..."
        ),
    },
    {
        "id": "REAUDIT-0AE391-ANALYZE-AGAIN",
        "start": 0x0AE391,
        "end": 0x0AE3CC,
        "end_command": 0xDE,
        "draft": (
            "[BYTE:D8][SPEAKER:0B]벌써 포기해?\n"
            "아키하바라 박사에게\n다시 분석해 달랠까?"
        ),
    },
    {
        "id": "REAUDIT-0AE3CD-AGAINST-PRINCIPLES",
        "start": 0x0AE3CD,
        "end": 0x0AE3F5,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D8][SPEAKER:0A]흠...[PAU:1E]아냐,"
            "[PAU:1E]내 원칙에 어긋나!"
        ),
    },
    {
        "id": "REAUDIT-0AE891-PRISONER-CHOICE",
        "start": 0x0AE891,
        "end": 0x0AE8CF,
        "end_command": 0xCC,
        "draft": "[WIPE]뭘 원해? 나가면 정하지!\n 정보\n 돈",
    },
    {
        "id": "REAUDIT-0AE8D0-DONT-SAY-THAT",
        "start": 0x0AE8D0,
        "end": 0x0AE8EF,
        "end_command": 0xCC,
        "draft": (
            "[WIPE]그러지 마\n방법이..."
            "[BYTE:CF][BYTE:81][BYTE:E9][BYTE:8A]"
        ),
    },
    {
        "id": "REAUDIT-0AE8F0-AKIHABARA-INFO",
        "start": 0x0AE8F0,
        "end": 0x0AE928,
        "end_command": 0xC0,
        "draft": (
            "[WIPE][PAL:02]아키하바라 박사[PAL:00] 얘기야?\n"
            "좋아, 말하지!\n부탁한다!"
        ),
    },
    {
        "id": "REAUDIT-0AE929-PRISONER-MONEY",
        "start": 0x0AE929,
        "end": 0x0AE959,
        "end_command": 0xC0,
        "draft": "[WIPE]뭐!? [PAU:1E]돈!?\n[PAU:1E]내... 내가 줄게!\n가자!",
    },
    {
        "id": "REAUDIT-0AE9D7-DRG-BLAMED-ME",
        "start": 0x0AE9D7,
        "end": 0x0AEA1E,
        "end_command": 0xC0,
        "draft": (
            "[DFT]아...[PAU:1E]들어 봐.\nDr.G가 길을 잃은 걸\n"
            "내 탓으로 돌렸어!\n[PAU:1E]흑![PAU:1E]불쌍한 나"
        ),
    },
)

# Runtime re-audit batch 9: a translated D7 tail made this preceding D0 page
# look merely "partially translated".  Keep the DE handoff fixed and replace
# the last genuine English sentence found by the residual scan.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-0A8EFB-DONATION-DECLINED",
        "start": 0x0A8EFB,
        "end": 0x0A8F30,
        "end_command": 0xDE,
        "draft": (
            "[WIPE]음...\n[PAU:1E]고맙지만\n"
            "돈이 별로 없어 보이는데..."
        ),
    },
)

# Runtime re-audit batch 10: text reported from the battle result window and
# the Old House approach.  The Mint choice event is split at its first fixed
# CC return so the event script and branch addresses remain untouched.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-01CEA8-BATTLE-BONUS-PREFIX",
        "start": 0x01CEA8,
        "end": 0x01CED1,
        "end_command": 0xDF,
        "draft": (
            "[NAM:00] 데이터 획득!\n"
            "보너스 [BYTE:DF][BYTE:01][BYTE:04][BYTE:D2][BYTE:05] 메가.\n"
            "누적: "
        ),
    },
    {
        "id": "REAUDIT-01CED1-BATTLE-BONUS-D3-TARGET",
        "start": 0x01CED1,
        "end": 0x01CEE5,
        "end_command": 0xCC,
        "draft": "[BYTE:DF][BYTE:01][BYTE:04][BYTE:D0][BYTE:05] 메가.[FIN]",
    },
    {
        "id": "REAUDIT-06AEE9-MINT-JOIN-CHOICE",
        "start": 0x06AEE9,
        "end": 0x06AF57,
        "end_command": 0xCC,
        "draft": (
            "[DFT]뭐야? 또 너야?\n할 말 있으면 해!\n"
            "남자답게 말 못 해!?[FIN]"
            "같이 가길 원하면 말해!\n"
            " 같이 가자.\n 혼자 갈게."
        ),
    },
)

# Runtime re-audit batch 11: the original catalogue stopped main dialogue
# bank 3 at 0x07EC55 even though live story text continues through 0x07F3B4.
# These spans cover the reported screens and the immediately adjacent story
# branches in that omitted tail.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-01CEED-BATTLE-STAT-INCREASE",
        "start": 0x01CEED,
        "end": 0x01CEFB,
        "end_command": 0xD3,
        "draft": "로봇 능력상승\n",
    },
    {
        "id": "REAUDIT-01CEFE-BATTLE-LEVEL-UP",
        "start": 0x01CEFE,
        "end": 0x01CF0E,
        "end_command": 0xDE,
        "draft": (
            "[WIPE][NAM:00]\n레벨 "
            "[BYTE:C6][BYTE:02][BYTE:14][BYTE:0B]![PAU:3C]"
        ),
    },
    {
        "id": "REAUDIT-01CFC1-SHOP-PROMPT",
        "start": 0x01CFC1,
        "end": 0x01CFD0,
        "end_command": 0xCC,
        "draft": "[WIPE]뭘 찾니?",
    },
    {
        "id": "REAUDIT-01CFD1-SHOP-FAREWELL",
        "start": 0x01CFD1,
        "end": 0x01CFE5,
        "end_command": 0xC0,
        "draft": "[WIPE]또 와.",
    },
    {
        "id": "REAUDIT-05F767-CARL-CLOSED-DOOR",
        "start": 0x05F767,
        "end": 0x05F7C3,
        "end_command": 0xC0,
        "draft": (
            "[DFT][SPEAKER:07]문이 닫혔어. 전엔 열렸는데.[FIN]"
            "낡았어. 둘이 밀면 열릴 거야.\n"
            "준비됐지?[PAU:2A] 밀자!"
        ),
    },
    {
        "id": "REAUDIT-05F7C4-CARL-PUSHING",
        "start": 0x05F7C4,
        "end": 0x05F809,
        "end_command": 0xC0,
        "draft": (
            "[DFT][SPEAKER:07]야, 밀고 있는 거야?[FIN]"
            "나만 힘쓰는 것 같잖아!\n제대로 밀어!"
        ),
    },
    {
        "id": "REAUDIT-05F80A-CARL-STAND-GUARD",
        "start": 0x05F80A,
        "end": 0x05F831,
        "end_command": 0xC0,
        "draft": "[DFT][SPEAKER:07]난 여기서 망볼게.\n넌 들어가. 힘내!",
    },
    {
        "id": "REAUDIT-07EC92-BREAK-FIRST-WALL",
        "start": 0x07EC92,
        "end": 0x07ECB6,
        "end_command": 0xC0,
        "draft": "[DFT]이 벽을 부숴야 해.\n뒤로 물러서!",
    },
    {
        "id": "REAUDIT-07ECB7-FIRST-WALL-DONE",
        "start": 0x07ECB7,
        "end": 0x07ECD7,
        "end_command": 0xC0,
        "draft": "[DFT]…해냈어…\n가… 가자…",
    },
    {
        "id": "REAUDIT-07EE89-BREAK-SECOND-WALL",
        "start": 0x07EE89,
        "end": 0x07EEC1,
        "end_command": 0xC0,
        "draft": "[DFT]이 벽도 부숴야 해…\n[PAU:0A]뒤… 뒤로 물러서…",
    },
    {
        "id": "REAUDIT-07EEC2-BREAK-THIRD-WALL",
        "start": 0x07EEC2,
        "end": 0x07EEF5,
        "end_command": 0xC0,
        "draft": "[DFT]이것도… 부숴야… 해…\n뒤로… 물러서…",
    },
    {
        "id": "REAUDIT-07EEF6-THIRD-WALL-DONE",
        "start": 0x07EEF6,
        "end": 0x07EF24,
        "end_command": 0xC0,
        "draft": "[DFT]해… 해냈어…\n가… 가자…",
    },
    {
        "id": "REAUDIT-07EF25-ROBOT-LAST-WORDS",
        "start": 0x07EF25,
        "end": 0x07EFDA,
        "end_command": 0xC0,
        "draft": (
            "[DFT][NXT][BYTE:04]…안 돼… 힘이 다했어…\n시간이 없어…[FIN]"
            "곧 고철이 되겠지…\n부품을 챙겨… 널 지킬 거야.[FIN]"
            "마지막 부탁이야…\n[PAL:02]라스크[PAL:00]의 뜻을 이어 줘…[NXT][BYTE:00]"
        ),
    },
    {
        "id": "REAUDIT-07EFDB-SCRAP-A-RECEIVED",
        "start": 0x07EFDB,
        "end": 0x07EFF1,
        "end_command": 0xCC,
        "draft": "[DFT][NAM:00] [PAL:02]고철 A[PAL:00] 획득!",
    },
    {
        "id": "REAUDIT-07EFF2-SCRAP-A-FOUND-FULL",
        "start": 0x07EFF2,
        "end": 0x07F013,
        "end_command": 0xC0,
        "draft": "[DFT][NAM:00] [PAL:02]고철 A[PAL:00] 발견!\n가방이 찼다.",
    },
    {
        "id": "REAUDIT-07F04D-RASK-ROAD-MESSAGE",
        "start": 0x07F04D,
        "end": 0x07F0A1,
        "end_command": 0xC0,
        "draft": (
            "[DFT][PAL:02]이곳에 올 이에게 남긴다.\n"
            "먼 길이 더 가까울 때도 있다.\n"
            "믿는 길을 찾아라.[PAL:00]"
        ),
    },
    {
        "id": "REAUDIT-07F0B3-RASK-SIMPLE-DEVICE",
        "start": 0x07F0B3,
        "end": 0x07F149,
        "end_command": 0xC0,
        "draft": (
            "[DFT][PAL:02]간단한 장치다. 널 기다렸다.\n"
            "내게 남은 힘은 적다…[FIN]"
            "네가 올 때까지 버틸지 모르겠구나.\n"
            "아직 할 일이 많다. 네 부름을 기다리마.[PAL:00]"
        ),
    },
    {
        "id": "REAUDIT-07F1D0-EINST-BOAT-CAPSULE",
        "start": 0x07F1D0,
        "end": 0x07F24C,
        "end_command": 0xC0,
        "draft": (
            "[DFT][SPEAKER:04][NXT][BYTE:01]뭐라고![PAU:28][NXT][BYTE:00] "
            "아인스트 박사가 배로 도망쳤어!\n여기까지 쫓아왔지.[FIN]"
            "급히 가다 뭔가 떨어뜨렸어.\n저 캡슐이야."
        ),
    },
    {
        "id": "REAUDIT-07F24D-MINT-OPEN-CAPSULE",
        "start": 0x07F24D,
        "end": 0x07F2B8,
        "end_command": 0xC0,
        "draft": (
            "[DFT][SPEAKER:04]왜 캡슐을 안 열어? 겁먹었어?[FIN]"
            "그는 미친 발명가야!\n분명 이상한 장치가 들었을 거야."
        ),
    },
    {
        "id": "REAUDIT-07F35C-NAGISA-RETURN-ROCOCO",
        "start": 0x07F35C,
        "end": 0x07F3B4,
        "end_command": 0xC0,
        "draft": (
            "[DFT][PAL:03]나기사:\n[PAL:00][NAM:00], 들리니?\n"
            "무슨 일이 생겼어.[FIN]빨리 로코코로 돌아와!\n서둘러!"
        ),
    },
)

# Runtime re-audit batch 12: a live island/Old House text block at 0x0C951C
# was outside every previous catalogue and audit range.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-0C951C-COUNT-MANSION-RUINS",
        "start": 0x0C951C,
        "end": 0x0C959A,
        "end_command": 0xC0,
        "draft": (
            "[DFT]뭐라고?[PAU:1E] 백작의 저택?[FIN]"
            "무슨 소리야? 이곳은 십 년 전부터 폐허였어.[FIN]"
            "그전엔 폴린키라는 사람의 저택이었지."
        ),
    },
    {
        "id": "REAUDIT-0C959B-SCRAP-B-OFFER",
        "start": 0x0C959B,
        "end": 0x0C95F9,
        "end_command": 0xCC,
        "draft": (
            "[DFT]비가 온 뒤 땅에서 나온 거야.\n"
            "낡은 고철인데… 가질래?\n 네, 주세요!\n 아니요."
        ),
    },
    {
        "id": "REAUDIT-0C95FA-SCRAP-B-RECEIVED",
        "start": 0x0C95FA,
        "end": 0x0C961B,
        "end_command": 0xCC,
        "draft": (
            "[WIPE]좋아. 가져가.[FIN]"
            "[NAM:00][PAL:02]고철 B[PAL:00] 획득!"
        ),
    },
    {
        "id": "REAUDIT-0C961C-SCRAP-B-DECLINED",
        "start": 0x0C961C,
        "end": 0x0C962F,
        "end_command": 0xC0,
        "draft": "[WIPE]그래. 고철이야.",
    },
    {
        "id": "REAUDIT-0C9630-SCRAP-B-INVENTORY-FULL",
        "start": 0x0C9630,
        "end": 0x0C9646,
        "end_command": 0xC0,
        "draft": "[WIPE]가방이 가득 찼군.",
    },
    {
        "id": "REAUDIT-0C96C9-ISLAND-GUIDE",
        "start": 0x0C96C9,
        "end": 0x0C96FC,
        "end_command": 0xC0,
        "draft": "[DFT]난 섬 안내원이야!\n앞은 우리 마을이야. 가자!",
    },
    {
        "id": "REAUDIT-0C96FD-ISLAND-GUIDE-MOUSE",
        "start": 0x0C96FD,
        "end": 0x0C971B,
        "end_command": 0xC0,
        "draft": "[DFT]쥐는 안 태워 줘. 저리 가!!",
    },
    {
        "id": "REAUDIT-0C976A-DESERTER-INTRO",
        "start": 0x0C976A,
        "end": 0x0C979E,
        "end_command": 0xC0,
        "draft": "[DFT]미안해! 다시는 도망 안 칠게!\n[PAU:78]…뭐야? 해커야?",
    },
    {
        "id": "REAUDIT-0C979F-DESERTER-LASER-WARNING",
        "start": 0x0C979F,
        "end": 0x0C98A4,
        "end_command": 0xC0,
        "draft": (
            "[DFT]난 해커 전투원이었지만 끔찍한 얘길 듣고 도망쳤어.[FIN]"
            "해커는 이 별을 차지하려고 무서운 레이저 무기를 만들었어.[FIN]"
            "그런 계획인 줄 몰랐어… 생각만 해도 떨려.[FIN]"
            "이 동굴의 [PAL:02]보석 상자[PAL:00]를 가져가. 난 필요 없어."
        ),
    },
    {
        "id": "REAUDIT-0C992A-ROBOT-K-HINT",
        "start": 0x0C992A,
        "end": 0x0C99E4,
        "end_command": 0xC0,
        "draft": (
            "[DFT]날 찾았군… 난 프로그래머 로봇 K다.\n중요하진 않아.[FIN]"
            "보상으로 힌트를 주지.[FIN]"
            "[PAL:02]고철 9[PAL:00]와 [PAL:02]고철 10[PAL:00]은 핵심 부품이다.[FIN]"
            "찾아도 서둘러 합치지 말고 최적의 조합을 찾아라."
        ),
    },
    {
        "id": "REAUDIT-0C99E5-ROBOT-K-RETURN",
        "start": 0x0C99E5,
        "end": 0x0C9A1A,
        "end_command": 0xDE,
        "draft": "[DFT]또 왔군? 한가한가 봐.\n좋아, 하나 알려 주지.",
    },
    {
        "id": "REAUDIT-0C9A1B-QUICK-PACK-RECIPE",
        "start": 0x0C9A1B,
        "end": 0x0C9A80,
        "end_command": 0xC0,
        "draft": (
            "[DFT][PAL:02]빈 팩[PAL:00]과 [PAL:02]수리 도구[PAL:00]를 합치면\n"
            "[PAL:02]퀵 팩[PAL:00]을 만들 수 있다.[FIN]"
            "퀵 팩은 몇 번이든 만들 수 있어."
        ),
    },
    {
        "id": "REAUDIT-0C9A81-LEGENDARY-BLADE-RECIPE",
        "start": 0x0C9A81,
        "end": 0x0C9AC7,
        "end_command": 0xDE,
        "draft": (
            "[DFT][PAL:02]블레이드 3[PAL:00]와 [PAL:02]****[PAL:00]를 합치면\n"
            "전설의 검이 된다."
        ),
    },
    {
        "id": "REAUDIT-0C9AC8-MISSING-RECIPE-ITEM",
        "start": 0x0C9AC8,
        "end": 0x0C9AE6,
        "end_command": 0xC0,
        "draft": "[DFT][PAL:02]*****[PAL:00]?\n그건 없잖아.",
    },
    {
        "id": "REAUDIT-0C9AE7-MUST-HAVE-ITEM",
        "start": 0x0C9AE7,
        "end": 0x0C9AF8,
        "end_command": 0xC0,
        "draft": "[DFT]있어. 그거야.",
    },
    {
        "id": "REAUDIT-0C9B46-MOUSE-SHOP-MENU",
        "start": 0x0C9B46,
        "end": 0x0C9BD0,
        "end_command": 0xCC,
        "draft": (
            "[BYTE:D8]이 근처에서 장사하는 쥐는 나뿐이야.\n고철을 팔지! 찍찍![FIN]"
            "뭘 원해? 찍찍?\n 살게요.\n 정보 주세요.\n 구경만요."
        ),
    },
    {
        "id": "REAUDIT-0C9BD1-MOUSE-SHOP-FAREWELL",
        "start": 0x0C9BD1,
        "end": 0x0C9BE4,
        "end_command": 0xC0,
        "draft": "[WIPE]언제든 와! 찍찍!",
    },
    {
        "id": "REAUDIT-0C9BE5-MOUSE-SHOP-TUNNEL-HINT",
        "start": 0x0C9BE5,
        "end": 0x0C9C54,
        "end_command": 0xC0,
        "draft": (
            "[WIPE]이 터널은 촌장 집으로 이어져. 찍찍!\n"
            "하지만 [PAL:02]잠긴 문[PAL:00]이 있어.[FIN]"
            "열쇠는 아마 터널 어딘가에 있을 거야. 찾아봐."
        ),
    },
    {
        "id": "REAUDIT-0C9C55-MOUSE-SHOP-SQUEAK",
        "start": 0x0C9C55,
        "end": 0x0C9C65,
        "end_command": 0xC0,
        "draft": "[BYTE:D8]찍찍!",
    },
)

# Runtime re-audit batch 13: continue through the island sequence immediately
# following the newly reported guide and ruined-mansion scenes.
SCREEN_TEXT_PATCHES += (
    {
        "id": "REAUDIT-07F2B9-MINT-ROCOCO-FIRST",
        "start": 0x07F2B9,
        "end": 0x07F329,
        "end_command": 0xC0,
        "draft": (
            "[DFT][SPEAKER:04][NXT][BYTE:01]로코코에 무슨 일이!?[FIN]"
            "[NXT][BYTE:00]수상해. 아인스트도 걱정되지만 급한 일부터야.\n"
            "[NXT][BYTE:01]가야겠어![NXT][BYTE:00]"
        ),
    },
    {
        "id": "REAUDIT-0C9647-HEY-MOUSE",
        "start": 0x0C9647,
        "end": 0x0C9652,
        "end_command": 0xC0,
        "draft": "[DFT]쥐다.",
    },
    {
        "id": "REAUDIT-0C9CEA-ROSE-FAREWELL",
        "start": 0x0C9CEA,
        "end": 0x0C9D45,
        "end_command": 0xC0,
        "draft": (
            "[DFT][SPEAKER:0B]꼬마야, 배웅 왔니? 귀엽구나.[FIN]"
            "네 덕에 내 계획이 성공하겠어.[FIN]"
            "[PAU:14]그럼, 또 만나자."
        ),
    },
    {
        "id": "REAUDIT-0C9E0C-MOUSE-GET-OUT",
        "start": 0x0C9E0C,
        "end": 0x0C9E27,
        "end_command": 0xC0,
        "draft": "[DFT]…쥐잖아!\n나가!",
    },
    {
        "id": "REAUDIT-0C9E28-WRECKED-SHIP-COMPLAINT",
        "start": 0x0C9E28,
        "end": 0x0C9ED3,
        "end_command": 0xC0,
        "draft": (
            "[DFT]…[PAU:14]으악![PAU:14] 너잖아![FIN]"
            "[NXT][BYTE:01]나가! 나가![NXT][BYTE:00] 너 때문에 끔찍한 일을 당했어![FIN]"
            "배가 난파돼 외딴섬에 갇혔는데 수리 재료도 없어!\n"
            "상처에 소금을 뿌리는군!"
        ),
    },
    {
        "id": "REAUDIT-0C9ED4-EVERYTHING-YOUR-FAULT",
        "start": 0x0C9ED4,
        "end": 0x0C9F01,
        "end_command": 0xC0,
        "draft": "[DFT]모두 네 탓이야!!\n어쩌란 거야?!",
    },
    {
        "id": "REAUDIT-0C9F02-FEVER-FLOWER-BARGAIN",
        "start": 0x0C9F02,
        "end": 0x0C9F6E,
        "end_command": 0xC0,
        "draft": (
            "[DFT]뭐? [PAL:02]열꽃[PAL:00]을 찾는다고?[FIN]"
            "그럼 [PAL:02]배 부품[PAL:00]을 가져와!\n"
            "[PAL:02]고철 7[PAL:00]이 부족해. 가져오면 얘길 듣지!"
        ),
    },
    {
        "id": "REAUDIT-0C9F6F-SCRAP-7-FEVER-FLOWER",
        "start": 0x0C9F6F,
        "end": 0x0CA053,
        "end_command": 0xC0,
        "draft": (
            "[DFT]그건…[PAU:14] [PAL:02]고철 7[PAL:00]이잖아!\n"
            "내놔![PAU:0A] 이리 가져와![FIN]"
            "뭐?![PAU:0A] 열꽃? 확실하진 않지만\n"
            "[PAL:02]이 집 뒤 나무 밑에 자라![PAL:00] 가져가![FIN]"
            "[NAM:00]은 [PAL:02]고철 7[PAL:00]을 잃었다![FIN]"
            "좋아… 이제 이 외딴섬을 떠날 수 있겠군!"
        ),
    },
    {
        "id": "REAUDIT-0CA054-RETURN-NEXT-GAME",
        "start": 0x0CA054,
        "end": 0x0CA0C3,
        "end_command": 0xC0,
        "draft": (
            "[BYTE:D9]알겠나?![PAU:14] 도망치는 게 아니야![FIN]"
            "사람들이 원한다면 더 멋진 계획으로 돌아오지![FIN]"
            "그때까지,[PAU:14] 안녕![PAU:14] 와하하하!"
        ),
    },
    {
        "id": "REAUDIT-0CA148-ELOPED-WIFE-FEVER",
        "start": 0x0CA148,
        "end": 0x0CA1EB,
        "end_command": 0xC0,
        "draft": (
            "[DFT]우린 사랑의 도피를 했어. 이 섬에 온 뒤 아내가 심한 열병에 걸렸지.[FIN]"
            "어딘가에 [PAL:02]열꽃[PAL:00]이 핀다는데…[FIN]"
            "아내 곁을 떠날 수 없어 찾으러 가지도 못해…"
        ),
    },
    {
        "id": "REAUDIT-0CA1EC-FEVER-FLOWER-REWARD",
        "start": 0x0CA1EC,
        "end": 0x0CA295,
        "end_command": 0xCC,
        "draft": (
            "[DFT][NXT][BYTE:06]설마…[NXT][BYTE:00] 그게 열꽃인가?! 고마워. 아내에게 먹일게![FIN]"
            "[NAM:00]은 [PAL:02]붉은 꽃[PAL:00]을 건넸다![FIN]"
            "돈은 많지 않지만 늘 감사하겠어…[FIN]"
            "[NAM:00]은 [PAL:02]3000 GP[PAL:00]를 받았다!"
        ),
    },
    {
        "id": "REAUDIT-0CA296-MAKE-MEDICINE",
        "start": 0x0CA296,
        "end": 0x0CA2B9,
        "end_command": 0xC0,
        "draft": "[DFT]이 꽃으로 약을 만들게!\n고마워!!",
    },
    {
        "id": "REAUDIT-0CA2BA-WIFE-RECOVERED",
        "start": 0x0CA2BA,
        "end": 0x0CA2FB,
        "end_command": 0xC0,
        "draft": "[DFT]네 덕에 아내가 완전히 나았어.\n부모님께 못되게 군 벌이었나 봐…",
    },
    {
        "id": "REAUDIT-0CA2FC-MOUSE-HERE",
        "start": 0x0CA2FC,
        "end": 0x0CA30E,
        "end_command": 0xC0,
        "draft": "[DFT]쥐가… 여기에!?",
    },
    {
        "id": "REAUDIT-0CA356-WIFE-DREAM",
        "start": 0x0CA356,
        "end": 0x0CA3F9,
        "end_command": 0xC0,
        "draft": (
            "[DFT]네 덕에 완전히 나았어요. 열병 중 어린 시절 꿈을 꿨어요.[FIN]"
            "아플 때 아버지가 돌봐 주시던 꿈…[FIN]"
            "아버지는 걱정하셨는데 난 그런 꿈을…[PAU:14] 이상하네요."
        ),
    },
    {
        "id": "REAUDIT-0CA408-WIFE-FATHER-DREAM",
        "start": 0x0CA408,
        "end": 0x0CA432,
        "end_command": 0xC0,
        "draft": "[DFT]…아버지…\n…미안해요…",
    },
)

# Runtime re-audit batch 14: remaining battle/shop/invention system prompts.
SCREEN_TEXT_PATCHES += (
    {"id": "SYSTEM-01CF16-ROBOT-SELECT", "start": 0x01CF16, "end": 0x01CF2C, "end_command": 0xCC,
     "draft": "[WIPE][NXT][BYTE:01]로봇 선택"},
    {"id": "SYSTEM-01CF2D-NO-NEED-MAKE", "start": 0x01CF2D, "end": 0x01CF41, "end_command": 0xCC,
     "draft": "[WIPE][NXT][BYTE:01]제작 안 함.[WAIT]"},
    {"id": "SYSTEM-01CFE6-SHOP-BUY", "start": 0x01CFE6, "end": 0x01D00F, "end_command": 0xCC,
     "draft": ("[WIPE][BYTE:C5][BYTE:06][BYTE:E3][BYTE:82][BYTE:0B]\n"
               "[BYTE:C5][BYTE:7E][BYTE:DA][BYTE:82][BYTE:0B][FIN]"
               "[BYTE:C6][BYTE:04][BYTE:84][BYTE:0B]GP\n 구매\n 취소")},
    {"id": "SYSTEM-01D010-INVENTORY-FULL", "start": 0x01D010, "end": 0x01D029, "end_command": 0xCC,
     "draft": "[WIPE]가방이 가득 찼다.[WAIT]"},
    {"id": "SYSTEM-01D02A-NOT-ENOUGH-GP", "start": 0x01D02A, "end": 0x01D04B, "end_command": 0xCC,
     "draft": "[WIPE]GP가 부족해.\n살 수 없다.[WAIT]"},
    {"id": "SYSTEM-01D04C-ROBOT-ITEM", "start": 0x01D04C, "end": 0x01D084, "end_command": 0xCC,
     "draft": ("[BYTE:C1][BYTE:03][BYTE:13][BYTE:C7][BYTE:0D][BYTE:03][BYTE:00]"
               "[WIPE][NXT][BYTE:01]로봇용 아이템 선택\n"
               "[BYTE:E2][BYTE:00][BYTE:40] 아이템 설명")},
    {"id": "SYSTEM-01D085-USE-WHICH-ROBOT", "start": 0x01D085, "end": 0x01D098, "end_command": 0xCC,
     "draft": "[WIPE][NXT][BYTE:01]로봇 선택?"},
    {"id": "SYSTEM-01D099-ROBOT-DOESNT-NEED", "start": 0x01D099, "end": 0x01D0BC, "end_command": 0xCC,
     "draft": "[WIPE][NXT][BYTE:01]이 로봇엔 필요 없다.[WAIT]"},
    {"id": "SYSTEM-01D0BD-ITEM-USE", "start": 0x01D0BD, "end": 0x01D0D5, "end_command": 0xCC,
     "draft": ("[WIPE][NXT][BYTE:01][BYTE:C5][BYTE:06][BYTE:E3][BYTE:82][BYTE:0B] 쓸까\n"
               "사용\n취소")},
    {"id": "SYSTEM-01D0D6-SELECT-ORDER", "start": 0x01D0D6, "end": 0x01D0F2, "end_command": 0xCC,
     "draft": "[WIPE][NXT][BYTE:01][BYTE:E2][BYTE:80][BYTE:00] 버튼으로 정렬."},
    {"id": "SYSTEM-01D0F3-BUTTON-HELP", "start": 0x01D0F3, "end": 0x01D146, "end_command": 0xCC,
     "draft": ("[BYTE:C1][BYTE:03][BYTE:13][BYTE:C7][BYTE:0D][BYTE:03][BYTE:00]"
               "[WIPE][NXT][BYTE:01][PAL:04][BYTE:E2][BYTE:80][BYTE:00] 버튼[PAL:00]: 장비\n"
               "[PAL:04][BYTE:E2][BYTE:40][BYTE:00] 버튼[PAL:00]: 교환\n"
               "[PAL:04][BYTE:E2][BYTE:00][BYTE:40] 버튼[PAL:00]: 설명")},
    {"id": "SYSTEM-01D151-DISCARD", "start": 0x01D151, "end": 0x01D171, "end_command": 0xCC,
     "draft": ("[WIPE][NXT][BYTE:01][BYTE:C5][BYTE:06][BYTE:E3][BYTE:82][BYTE:0B] 버릴까\n"
               "취소\n버림")},
    {"id": "SYSTEM-01D172-CANT-DISCARD", "start": 0x01D172, "end": 0x01D18A, "end_command": 0xCC,
     "draft": "[WIPE][NXT][BYTE:01][BYTE:C5][BYTE:06][BYTE:E3][BYTE:82][BYTE:0B] 못 버림.[WAIT]"},
    {"id": "SYSTEM-01D420-ATTACK-LV", "start": 0x01D420, "end": 0x01D44B, "end_command": 0xCC,
     "draft": ("[WIPE][BYTE:C5][BYTE:06][BYTE:E3][BYTE:9E][BYTE:0B] "
               "[BYTE:C5][BYTE:2D][BYTE:E7][BYTE:A0][BYTE:0B]\n"
               " 공격 + [BYTE:C6][BYTE:03][BYTE:9A][BYTE:0B]\n"
               " 레벨 + [BYTE:C6][BYTE:03][BYTE:9C][BYTE:0B][WAIT]")},
    {"id": "SYSTEM-01D44C-ATTACK-DEFENSE", "start": 0x01D44C, "end": 0x01D47C, "end_command": 0xCC,
     "draft": ("[BYTE:C1][BYTE:03][BYTE:13][NXT][BYTE:01][BYTE:C7][BYTE:0D][BYTE:03][BYTE:00]"
               "[WIPE][BYTE:C5][BYTE:06][BYTE:E3][BYTE:9E][BYTE:0B]\n"
               " 공격 + [BYTE:C6][BYTE:03][BYTE:9A][BYTE:0B]\n"
               " 방어 + [BYTE:C6][BYTE:03][BYTE:9C][BYTE:0B][WAIT]")},
    {"id": "SYSTEM-01D49B-COMBINE-ITEMS", "start": 0x01D49B, "end": 0x01D4BA, "end_command": 0xCC,
     "draft": ("[BYTE:C1][BYTE:03][BYTE:13][NXT][BYTE:01][BYTE:C7][BYTE:0D][BYTE:03][BYTE:00]"
               "[WIPE]2개 조합\n[BYTE:C5][BYTE:A3][BYTE:D3][BYTE:A2][BYTE:0B]")},
    {"id": "SYSTEM-01D4BB-COMBINATION-POSSIBLE", "start": 0x01D4BB, "end": 0x01D4F3, "end_command": 0xCC,
     "draft": ("[WIPE][NXT][BYTE:01]조합 가능\n"
               "[BYTE:C5][BYTE:06][BYTE:E3][BYTE:9E][BYTE:0B] "
               "[BYTE:C5][BYTE:2D][BYTE:E7][BYTE:A0][BYTE:0B]\n 취소      조합")},
    {"id": "SYSTEM-01D505-CANT-COMBINE", "start": 0x01D505, "end": 0x01D517, "end_command": 0xCC,
     "draft": "[WIPE][NXT][BYTE:01]조합 못 함.[WAIT]"},
    {"id": "SYSTEM-01D518-INVENTORY-FULL", "start": 0x01D518, "end": 0x01D52B, "end_command": 0xD3,
     "draft": "[WIPE][NXT][BYTE:01]가방이 찼다.\n"},
    {"id": "SYSTEM-01D52E-RECYCLE-ITEMS", "start": 0x01D52E, "end": 0x01D54B, "end_command": 0xCC,
     "draft": ("[BYTE:C1][BYTE:03][BYTE:13][NXT][BYTE:01][BYTE:C7][BYTE:0D][BYTE:03][BYTE:00]"
               "[WIPE]재활용\n[BYTE:C5][BYTE:A3][BYTE:D3][BYTE:A2][BYTE:0B]")},
    {"id": "SYSTEM-01D54C-RECYCLE-GP", "start": 0x01D54C, "end": 0x01D57C, "end_command": 0xCC,
     "draft": ("[WIPE][NXT][BYTE:01][BYTE:C5][BYTE:06][BYTE:E3][BYTE:82][BYTE:0B] 재활용\n"
               "[BYTE:C6][BYTE:04][BYTE:84][BYTE:0B] GP\n 취소      재활용")},
    {"id": "SYSTEM-01D57D-CANT-RECYCLE", "start": 0x01D57D, "end": 0x01D599, "end_command": 0xCC,
     "draft": "[WIPE][NXT][BYTE:01]재활용 불가.[WAIT]"},
    {"id": "SYSTEM-01D59A-MAKE-ROBOT", "start": 0x01D59A, "end": 0x01D5CC, "end_command": 0xCC,
     "draft": ("[BYTE:C1][BYTE:03][BYTE:11][NXT][BYTE:01][BYTE:C7][BYTE:0D][BYTE:04][BYTE:00]"
               "제작 [BYTE:C6][BYTE:04][BYTE:84][BYTE:0B]GP\n 제작    취소")},
    {"id": "SYSTEM-01D5CD-THREE-ROBOTS", "start": 0x01D5CD, "end": 0x01D5FA, "end_command": 0xC0,
     "draft": ("[BYTE:C1][BYTE:03][BYTE:11][NXT][BYTE:01][BYTE:C7][BYTE:0D][BYTE:04][BYTE:00]"
               "로봇은 3대면 충분하다.")},
)

# Story/progression lines whose first drafts exceeded their physical slots by
# a few bytes.  These retain the event meaning while fitting without moving
# any script address.
IMPORTANT_COMPACT = {
    "EN-05829B": "[DFT][PAL:02]크리스피 상점[PAL:00]\n\n생활을 편하게 하는\n도구 상점입니다˳",
    "EN-05BC3C": "[DFT][NXT]너!! 내 딸 못 봤나?\n쪽지만 남기고 사라졌어![FIN]\n읽어 봐!\n[PAU:14][PAL:03]그와 함께 떠납니다.\n용서해 주세요.[PAL:00]\n이게 무슨 소리야![NXT]",
    "EN-05DCA0": "[DFT][SPEAKER:04][DC][09]……[C9][1E][DC][01]알았다!\n[C9][1E]촌장님은 개를 싫어해.\n다 아는 사실이지![FIN][DC][00][NAM:00], 개를 촌장실로 데려와.\n난 취재를 청할게!",
    "EN-05EB7C": "[DFT][SPEAKER:04][NAM:00], 준비됐어?\n개를 데리고 촌장님께 가자.[FIN]\n진짜 촌장이라면 개가 다가가면\n난리를 피울 거야!",
    "EN-05AFC0": "[DFT][SPEAKER:02]이제 일어나도 돼.\n정말 괜찮겠니?\n무리하지 마.",
    "EN-05DC74": "[DFT][SPEAKER:04]방법이 있을 텐데…\n[C9][1E]좋은 생각 없어?",
    "EN-06EBBB": "[DFT][PAL:02]전투원 A:\n[PAL:00]경비들은 어둠을 무서워해.[FIN]\n차단기 스위치를\n몇 번 껐다 켜면\n겁먹고 도망가더라.",
    "EN-069427": "[DFT]너구나! [PAL:02]열쇠[PAL:00]를 얻었어?\n어디 있어?[FIN]\n[PAL:02]장비해 보여 줘.[PAL:00]\n남에게 줄 물건은 장비해 보이는 게 규칙이야.",
    "EN-07CC08": "[DFT][SPEAKER:1B]\n주문을 외우자 비가 왔어요!\n모두 기뻐합니다![FIN]\n마을의 영웅이시여, 감사해요!\n구석의 상자 둘을 확인하세요!",
    # The original uses DE to hand control to the item-give event, then CC+DFT
    # for the inventory-full fallback.  Replacing DE with CC leaves the box open
    # while gameplay resumes, so preserve this three-stage control structure.
    "EN-078E70": "[DFT][SPEAKER:02]왔니, [NAM:00]. [SPEAKER:1C]을 얻었구나![FIN]\n발명 기계로 [SPEAKER:1C]의 [PAL:02]능력과 기술[PAL:00]을 설정하면 더 강해져.[FIN]\n요즘 해커 전투원이 주변을 염탐하고 있어.[FIN]\n발명은 유용해야 의미가 있지. 악용해선 안 돼.[FIN]\n이 [PAL:02]깜짝 뿔피리[PAL:00]를 줄게. 아주 큰 소리가 나.[DE]\n[NAM:00]은 [PAL:02]깜짝 뿔피리[PAL:00]를 받았다![TER][DFT]\n가방이 가득 찼구나. 정리하고 와.",
    "EN-079A76": "[DFT]해커 섬에 온 걸 환영합니다.\n[PAL:02]공군 기지[PAL:00]는 산 너머입니다.",
    "EN-0889B3": "[DFT]\n[NAM:00] [PAL:02]스톤1[PAL:00] 분실!",
    "EN-08A876": "[DFT]\n[NAM:00]\n[C9][14]기다려!",
    "EN-08B7E2": "[DFT][SPEAKER:0E][NAM:00], 어서 와요.\n올 줄 알았습니다.[FIN]\n자세한 건 재상이 설명할 테니\n그에게 물어보세요.",
    "EN-088FEB": "[DFT]뭐? 아키하바라 박사 아들이라고?\n박사는 [PAL:02]탑[PAL:00]에 끌려갔어. 찾아봐.[FIN]\n네 아버지께 네 얘길 들었어.\n하지만 [PAL:02]탑[PAL:00]은 하늘로만 갈 수 있어.[FIN]\n나도 [PAL:02]칼[PAL:00]이라는 아들이 있어.\n네 마음을 아니까 힘껏 도와줄게.",
    "EN-098FF0": "[DFT][SPEAKER:04]어땠어?[C9][1E] 뭐?[FIN]\n[C9][1E]없어?? 제대로 봤어?\n다시 찾아봐!![FIN]\n그자는 발명가가 아닌 가짜야!\n한 일을 전부 취재했어.[FIN]\n또 뭔가 꾸미고 있어!",
    "EN-09A96C": "[DFT][NAM:00]는\n인간이 됐다!",
    "EN-09CAC0": "[DFT][SPEAKER:0C]난 라스크 작품이고 [C9][1E]그를 알아.[FIN]\n넌 라스크가 아냐…\n하지만 [C9](성격은 닮았군…",
    "EN-09E975": "[DFT][SPEAKER:0B]정말? [SPEAKER:00]를 주면 내 시대로 갈 수 있어?[FIN]\n[SPEAKER:0D]넌 아무것도 모르는군.\n[SPEAKER:00]는 [PAL:02]시간을 비추는 프리즘[PAL:00]과 같아.[FIN]\n시험 삼아 네 과거를 보여 주지.",
    "EN-09BD2C": "[DFT][PAL:02]해커 공용 화장실\n[PAL:03]소장 전용 화장실\n[PAL:02]사용 금지!\n[C9][1E]물 내리는 걸 잊지 마![PAL:00]",
    "EN-0AA262": "[DFT][SPEAKER:11]동굴에서 여자와 수상한 자들을 봤어.\n[PAL:02][NAM:00]![PAL:00]…라고 들었지.[FIN]\n날 너로 착각해 공격했어.\n[C9][1E]그런데 그 여자[C9][1E]와 [SPEAKER:00]는…",
    "EN-0AB8FE": "[DFT]난 배로 갈게.[FIN]\n[PAL:02]가토[PAL:00]에게 알리고 얘기하자.\n[C9][1E]알겠지? [PAL:02]환상의 숲[PAL:00]에서 기다릴게.",
    "EN-0ADED2": "[DFT][SPEAKER:02][NAM:00], 이쪽! [C9][1E]빨리!",
}


COMPACT_REPLACEMENTS: dict[str, tuple[tuple[str, str], ...]] = {
    "EN-058580": (
        (("[JMP][BYTE:B9][BYTE:87][DFT]"), ("[JMP][BYTE:81][BYTE:89][DFT]")),
        (("\n\n[PAL:03]로코코 기자 민트[PAL:00]"), ("\n\n[JMP][BYTE:81][BYTE:89][PAL:03]로코코 기자 민트[PAL:00]")),
    ),
    "EN-059926": (
        (("[FIN][DFT]네 얘기는 들었다."), ("[FIN][JMP][BYTE:E5][BYTE:A7][DFT]네 얘기는 들었다.")),
    ),
    "EN-058C75": (
        (("되찾았다![FIN][DFT]"), ("되찾았다![TER][DFT]")),
        (("으아아! 미안해!"), ("으악! 미안해!")),
        (("다시는 나쁜 짓 안 할게!"), ("나쁜 짓 안 할게!")),
        (("[NAM:00]은 [PAL:02]뿔피리[PAL:00]를 되찾았다!"), ("[NAM:00] [PAL:02]뿔피리[PAL:00] 회수!")),
    ),
    "EN-059403": (
        (("아니, 괜찮다.[FIN][DFT]"), ("아니, 괜찮다.[TER][DFT]")),
    ),
    "EN-05A794": (
        (("[NAM:00]! 돌아왔구나!"), ("[NAM:00]!돌아왔구나!")),
        (("돌아왔구나![FIN][DFT][PAL:03]나기사:"), ("돌아왔구나![FIN][JMP][BYTE:E5][BYTE:A7][BYTE:DB][PAL:03]나기사:")),
        (("대체 어쩔 셈이냐, [NAM:00]!"), ("대체 무슨 짓이냐!")),
    ),
    "EN-05B028": (
        (("나쁜 사람들 같진 않구나.[TER][CLR]"), ("나쁜 사람들 같진 않구나.[DE][CLR]")),
        (("나쁜 사람들 같진 않아.[TER][DFT]"), ("나쁜 사람들 같진 않아.[DE][DFT]")),
        (("잘 사용하렴.[TER][DFT]"), ("잘 사용하렴.[DE][DFT]")),
        (("난 그렇게 나쁜 사람들 같진 않구나."), ("난 나쁜 사람들 같진 않아.")),
        (("너도 그렇게 생각하니?\n난 그렇게 나쁜 사람들 같진 않아."), ("너도?\n난 나쁜 사람들 같진 않아.")),
    ),
    "EN-05B187": (
        (("중요한 물건이라면 돌려주마.[TER][DFT]"), ("중요한 물건이라면 돌려주마.[DE][DFT]")),
    ),
    "EN-05B36B": (
        (("[PAL:02]초코별[PAL:00]에서 왔습니다.[TER][DFT]"), ("[PAL:02]초코별[PAL:00]에서 왔습니다.[DE][DFT]")),
        (("[NAM:00] 님께 도움을 청하러 왔습니다.[TER][DFT]"), ("[NAM:00] 님께 도움을 청하러 왔습니다.[DE][DFT]")),
        (("당신을 찾아왔습니다.[TER][DFT]"), ("당신을 찾아왔습니다.[DE][DFT]")),
        (("[NXT]공주님의 설명은 너무 길어집니다.[TER][DFT]"), ("[NXT]공주님의 설명은 너무 길어집니다.[DE][DFT]")),
        (("도와주신다면 이걸 사용해 초코별로 오십시오.[TER][DFT]"), ("도와주신다면 이걸 사용해 초코별로 오십시오.[DE][DFT]")),
        (("놀라겠지만 우리는\n[PAL:02]초코별[PAL:00]에서 왔습니다."), ("우리는 [PAL:02]초코별[PAL:00]에서 왔습니다.")),
        (("이분은 [PAL:03]티라 공주님[PAL:00]입니다.\n[NAM:00] 님께 도움을 청하러 왔습니다."), ("[PAL:03]티라 공주[PAL:00]입니다.\n[NAM:00], 도와주세요.")),
        (("당신이 가진 로봇의 힘을 빌리라는\n쿠키 님의 유언이었습니다."), ("쿠키 님은 당신 로봇의 힘을\n빌리라 하셨습니다.")),
        (("해커는 강력한 [PAL:02]우주 요새[PAL:00]를 가졌습니다.\n그것을 파괴하려면 로봇이 필요합니다."), ("해커의 [PAL:02]우주 요새[PAL:00]를 파괴하려면\n로봇의 힘이 필요합니다.")),
        (("음… 선뜻 믿기 어려운 이야기군."), ("음… 믿기 어렵군.")),
        (("사실입니다. 우선 이것을 드리겠습니다."), ("사실입니다. 이것을 드리죠.")),
        (("도와주신다면 이걸 사용해 초코별로 오십시오."), ("도와주시려면 이걸로 초코별에 오십시오.")),
        (("[NXT]공주님! 제가 설명하겠습니다!\n[NXT]공주님의 설명은 너무 길어집니다."), ("[NXT]공주님! 제가 설명하죠!\n[NXT]공주님 설명은 깁니다.")),
    ),
    "EN-05B877": (
        (("너한테 줄게.[TER][DFT]"), ("너한테 줄게.[DE][DFT]")),
    ),
    "EN-05BD05": (
        (("결혼한다네.[TER][DFT]"), ("결혼한다네.[DE][DFT]")),
    ),
    "EN-05CC66": (
        (("젊은 남자의 일기다.[TER][DFT]"), ("젊은 남자의 일기다.[DE][DFT]")),
    ),
    "EN-05F513": (
        ((" 구경만요."), (" 구경만요.[TER][CLR][CF][BYTE:A9][BYTE:F5][BYTE:85]")),
    ),
    "EN-05F567": (
        (("[DFT]오늘은"), ("[DFT][CF][BYTE:F1][BYTE:F5][BYTE:85][TER][DFT]오늘은")),
        (("오늘은 너무 더워서 쉬는 날이야.\n헛걸음하게 해서 미안해."), ("오늘은 너무 더워 쉬는 날이야.\n헛걸음시켜 미안해.")),
    ),
    "EN-0695BD": (
        (("인사 한 번 했다가 이 꼴이라니![TER][DFT]"), ("인사 한 번 했다가 이 꼴이라니![DE][DFT]")),
    ),
    "EN-069A1A": (
        (("아니요.[TER][CLR]"), ("아니요.[TER][DFT][CLR]")),
        (("구멍을 팠어.[FIN]\n아니라고?"), ("구멍을 팠어.[FIN][JMP][BYTE:BE][BYTE:9A][DFT][CLR]아니라고?")),
        (("넌 누구냐? 새 일꾼인가?"), ("누구냐? 새 일꾼인가?")),
        (("왜 땅을 파냐고? 찾는 게 있어. 신경 꺼!"), ("찾을 게 있다. 신경 꺼!")),
        (("나중에 메타 크랩에게 네 처분을 물어보지."), ("메타 크랩에게 네 처분을 물어보지.")),
        (("난 일하는 중이다."), ("난 일한다.")),
    ),
    "EN-06A949": (
        (("석판[PAL:00]을 찾았다.[TER][DFT]"), ("석판[PAL:00]을 찾았다.[DE][DFT]")),
        (("고철보단 낫네."), ("고철보단 낫네.[DE]")),
        (("칼은 [PAL:02]석판[PAL:00]을 찾았다."), ("칼 [PAL:02]석판[PAL:00] 발견!")),
    ),
    "EN-06B1BB": (
        (("내 가방에 쥐가 있었다고…?[FIN]\n그보다"), ("내 가방에 쥐가 있었다고…?[DE][DFT]\n그보다")),
    ),
    "EN-06C966": (
        (("파슬리라는 흰 개야.[FIN][SPEAKER:0F]"), ("파슬리라는 흰 개야.[FIN][JMP][BYTE:55][BYTE:CA][DFT][SPEAKER:0F]")),
    ),
    "EN-06D4B3": (
        (("[DFT][PAL:02]나의 멋진 인생 1권"), ("[DFT][BYTE:80]\n[DFT][PAL:02]나의 멋진 인생 1권")),
    ),
    "EN-06CAEA": (
        (("찾아야 해. 서둘러…[TER][DFT]"), ("찾아야 해. 서둘러…[DE][DFT]")),
    ),
    "EN-06CBD7": (
        (("[NAM:00], 먼저 가.[TER][DFT]"), ("[NAM:00], 먼저 가.[DE][DFT]")),
        (("[PAL:02]빛[PAL:00]을 줄게. 조심해.[TER][DFT]"), ("[PAL:02]빛[PAL:00]을 줄게. 조심해.[DE][DFT]")),
    ),
    "EN-06E785": (
        (("도와주셔서 감사합니다.[TER][DFT]"), ("도와주셔서 감사합니다.[DE][DFT]")),
        (("그 앞에서 친구가 구조를 기다립니다.[TER][DFT]"), ("그 앞에서 친구가 구조를 기다립니다.[DE][DFT]")),
    ),
    "EN-06E5BE": (
        (("[DFT]열쇠 가진 자가"), ("[DFT][JMP][BYTE:A2][BYTE:E5][DFT]열쇠 가진 자가")),
    ),
    "EN-06E8A7": (
        (("아직 있습니다.[FIN][SPEAKER:14]"), ("아직 있습니다.[FIN][JMP][BYTE:7F][BYTE:E9][DFT][SPEAKER:14]")),
        (("생각해 보셨습니까?[FIN]\n어서 오십시오."), ("생각해 보셨습니까?[FIN][JMP][BYTE:7F][BYTE:E9][DFT]어서 오십시오.")),
        (("손님, 나쁜 소식입니다.\n그 흰 골칫거리가 아직 있습니다."), ("큰일입니다.\n흰 골칫거리가 남았습니다.")),
    ),
    "EN-06F2AE": (
        (("[DC][07]…………[DC][00]말도 안 돼![TER][DFT]"), ("[DC][07]…………[DC][00]말도 안 돼![DE][DFT]")),
    ),
    "EN-06F0A0": (
        (("관련됐을지도 몰라.[FIN][SPEAKER:0F]"), ("관련됐을지도 몰라.[FIN][JMP][BYTE:3B][BYTE:F1][DFT][SPEAKER:0F]")),
    ),
    "EN-078FE4": (
        (("무사해서 다행이야.[FIN][SPEAKER:02]"), ("무사해서 다행이야.[FIN][JMP][BYTE:2B][BYTE:90][DFT][SPEAKER:02]")),
    ),
    "EN-079B70": (
        (("게의 부탁을 거절할 순 없지.[TER][DFT]"), ("게의 부탁을 거절할 순 없지.[DE][DFT]")),
    ),
    "EN-079CFB": (
        (("안내할게.[TER][DFT]"), ("안내할게.[DE][DFT]")),
    ),
    "EN-07A455": (
        (("찾았다고? 고마워! 선물을 줄게![TER][DFT]"), ("찾았다고? 고마워! 선물을 줄게![DE][DFT]")),
    ),
    "EN-07CB3D": (
        (("[DFT][SPEAKER:1B]"), ("[DFT][JMP][BYTE:C4][BYTE:CA][DFT][SPEAKER:1B]")),
    ),
    "EN-05E998": (("[NAM:00]은 [PAL:02]열쇠[PAL:00]를 찾았다!", "[NAM:00] [PAL:02]열쇠[PAL:00]!"),),
    "EN-06A797": (
        (("[NAM:00]은 [PAL:02]1000트론[PAL:00]을 받았다!"), ("[NAM:00] [PAL:02]1000트론[PAL:00] 획득!")),
        (("난 나갈 테니 조심해!"), ("난 갈 테니 조심해!")),
    ),
    "EN-06A09F": (
        (("서두르지 않으면 게찜으로 만들겠다![FIN]\n졸고 있나?"), ("서두르지 않으면 게찜으로 만들겠다![FIN]\n[JMP][BYTE:03][BYTE:A2][CLR]\n졸고 있나?")),
    ),
    "EN-06E6A1": (("[NAM:00]은 [PAL:02]열쇠[PAL:00]를 찾았다!", "[NAM:00] [PAL:02]열쇠[PAL:00]!"),),
    "EN-07EA3D": (("주고 싶은 게 있는데…", "줄 게 있는데…"),),
    "EN-088928": ((" [NAM:00]는 [PAL:02]스톤 1[PAL:00]을 얻었다!", "[NAM:00] [PAL:02]스톤 1[PAL:00] 획득!"),),
    "EN-089CA8": (("…하지만 소지품이 가득 찼군요.", "소지품이 가득 찼군요."),),
    "EN-08A885": (("조심해. [C9][0A]꼭 무사히 돌아와.", "조심해. [C9][0A]무사히 돌아와."),),
    "EN-08B231": (
        ((" [NAM:00]는 [PAL:02]빨강 단지[PAL:00]를 받았다!"), (" [NAM:00] [PAL:02]빨강 단지[PAL:00] 획득!")),
        ((" [NAM:00]는 [PAL:02]파랑 단지[PAL:00]를 받았다!"), (" [NAM:00] [PAL:02]파랑 단지[PAL:00] 획득!")),
        ((" [NAM:00]는 [PAL:02]노랑 단지[PAL:00]를 받았다!"), (" [NAM:00] [PAL:02]노랑 단지[PAL:00] 획득!")),
        (("이봐! [C9][1E]들었어? 저 녀석이 간대!"), ("[C9][1E]들었어? 저 녀석이 간대!")),
    ),
    "EN-099700": (("은 여기서 [B0] 방향이야.", "은 [B0] 쪽이야."),),
    "EN-09CB12": (
        (("유전자는 비슷해도 다른 사람이다."), ("유전자가 비슷할 뿐이야.")),
        (("하지만 이 별 사람은 "), ("이 별 사람은 ")),
    ),
    "EN-0A8D76": (
        (("[NAM:00]님의 현재 기부액은 "), ("[NAM:00]님의 기부액은 ")),
        (("최소 10 GP입니다."), ("최소 10 GP.")),
    ),
    "EN-0AA3EA": (
        (("그래, 나폴레옹이야!"), ("그래, 나야!")),
        (("무슨 일이 있었는지 말해 줘."), ("무슨 일이 있었어?")),
        (("기다려, 나폴레옹!"), ("기다려!")),
        (("나폴레옹! 가지 마!"), ("가지 마!")),
    ),
    "EN-0AB559": (
        (("그렇게 귀여운 여자를 걱정시키면 안 되지."), ("귀여운 여자를 걱정시키면 안 되지.")),
        (("[C9][1E]그런데 저 남자, 공처가 같군."), ("[C9][1E]저 남자, 공처가 같군.")),
    ),
    "EN-0ACFB6": (
        (("휴, 간신히 나왔군…"), ("나왔군…")),
        (("좋아, 약속은 지키지! 조수 A! 돈 있나!?"), ("약속대로, 돈!?")),
        (("그게 필요한 열쇠야!"), ("필요한 열쇠야!")),
        ((" [NAM:00]는 [PAL:02]열쇠[PAL:00]를 받았다!"), (" [NAM:00] [PAL:02]열쇠[PAL:00] 획득!")),
        (("소지품이 가득 차서 열쇠를 못 주겠어."), ("가방이 가득해서 열쇠를 못 줘.")),
    ),
    "EN-0ACD04": (
        (("[D3][B5][WIPE]"), ("[JMP][BYTE:B5][BYTE:CD][CLR]")),
    ),
}


INTERNAL_D3_ANCHORS = {
    "EN-05A794": "[PAL:00]\n대체 무슨 짓이냐!",
    "EN-069A1A": "찾을 게 있다. 신경 꺼!",
    "EN-06A09F": "알았으면 가! 다음 보고를 잊지 마!",
    "EN-0ACD04": "[PAL:02]인간을 컴퓨터에 넣는 계획[PAL:00]이 진행 중이야.",
    "EN-06E8A7": "그것을 이 방으로 데려오시겠습니까?",
}


# DC/NXT is a two-byte command.  The old draft token emitted only DC, causing
# the next visible glyph (or even C0) to be consumed as its operand.  Preserve
# the operand sequence from each original record explicitly.
NXT_OPERANDS: dict[str, tuple[int, ...]] = {
    "EN-05806C": (0x07, 0x00),
    "EN-05952F": (0x09, 0x00),
    "EN-05A3CF": (0x06, 0x00),
    "EN-05AE24": (0x01, 0x00),
    "EN-05B36B": (0x01, 0x00),
    "EN-05B877": (0x06, 0x00),
    "EN-05BC3C": (0x01, 0x00),
    "EN-05BCC0": (0x01, 0x00),
    "EN-05C6EC": (0x01, 0x00),
    "EN-05C76D": (0x01, 0x00),
    "EN-05C7DC": (0x01, 0x00),
    "EN-05C844": (0x01, 0x00),
    "EN-05C878": (0x01, 0x00),
    "EN-05C905": (0x06, 0x01, 0x00),
    "EN-05C95D": (0x01, 0x00),
    "EN-05C9F4": (0x01, 0x00),
    "EN-05CA63": (0x01, 0x00),
    "EN-05CACE": (0x01, 0x00),
    "EN-05CAFA": (0x01, 0x00),
    "EN-05D164": (0x09, 0x01, 0x00),
    "EN-05D68D": (0x05, 0x00),
    "EN-05D8E0": (0x09, 0x00),
    "EN-0693CA": (0x09, 0x01, 0x00),
    "EN-069730": (0x09, 0x00),
    "EN-06A9BF": (0x06, 0x00, 0x01, 0x00),
    "EN-06BCDF": (0x00,),
    "EN-06CE4C": (0x01, 0x00),
    "EN-06DF33": (0x09, 0x00),
    "EN-07A166": (0x09, 0x00),
}


def draft_for(record_id: str) -> str:
    if record_id in SUPPLEMENTAL_DRAFTS:
        return SUPPLEMENTAL_DRAFTS[record_id]
    text = IMPORTANT_COMPACT.get(record_id, DRAFTS[record_id])
    for before, after in COMPACT_REPLACEMENTS.get(record_id, ()):
        if before not in text:
            raise ValueError(f"compact replacement source missing: {record_id}: {before!r}")
        text = text.replace(before, after, 1)
    operands = NXT_OPERANDS.get(record_id)
    if operands is not None:
        if text.count("[NXT]") != len(operands):
            raise ValueError(
                f"NXT operand count mismatch: {record_id}: "
                f"{text.count('[NXT]')} != {len(operands)}"
            )
        for operand in operands:
            text = text.replace("[NXT]", f"[BYTE:DC][BYTE:{operand:02X}]", 1)
    elif "[NXT]" in text:
        raise ValueError(f"unmapped NXT operand sequence: {record_id}")
    return text


def read_supplemental_rows() -> list[dict[str, str]]:
    with CANDIDATES.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader((line for line in handle if not line.startswith("#")), delimiter="\t"))
    by_id = {row["record_id"]: row for row in rows}
    missing = sorted(set(SUPPLEMENTAL_DRAFTS) - set(by_id))
    if missing:
        raise ValueError(f"supplemental candidate rows missing: {missing}")
    return [by_id[record_id] for record_id in SUPPLEMENTAL_DRAFTS]


def punctuation_compact(text: str, slot: int, code_for: dict[str, int]) -> tuple[str, bytes] | None:
    """Fit a near-miss without changing words, line breaks, or control codes."""

    candidate = text
    encoded = common.encode_text(candidate, code_for)
    while len(encoded) > slot:
        if "!!" in candidate:
            candidate = candidate.replace("!!", "!", 1)
        elif "…" in candidate:
            candidate = candidate.replace("…", ".", 1)
        elif "˳" in candidate:
            candidate = candidate.replace("˳", "", 1)
        elif "." in candidate:
            index = candidate.rfind(".")
            candidate = candidate[:index] + candidate[index + 1 :]
        elif "!" in candidate:
            index = candidate.rfind("!")
            candidate = candidate[:index] + candidate[index + 1 :]
        elif "," in candidate:
            index = candidate.rfind(",")
            candidate = candidate[:index] + candidate[index + 1 :]
        else:
            return None
        encoded = common.encode_text(candidate, code_for)
    return candidate, encoded


def fixed_command_padding(length: int) -> bytes:
    """Fill a fixed-address span with ordinary, immediately processed spaces.

    C9 00 looked like a zero-frame pause but actually produced a long delay
    for every pair.  Fixed D3/CC/DE addresses still require padding, so use the
    same space filler as the already runtime-tested segmented record writer.
    """

    return b" " * length


def apply_speaker_name_table(
    target: bytearray,
    source: bytes,
    code_for: dict[str, int],
) -> tuple[list[dict[str, object]], list[tuple[int, int]]]:
    """Repack the 30 E0 speaker expansions and update their 16-bit pointers."""

    entry_count = len(SPEAKER_NAME_DRAFTS)
    pointer_end = SPEAKER_POINTER_TABLE + entry_count * 2
    if pointer_end != SPEAKER_TEXT_START:
        raise ValueError("speaker pointer table does not meet text table")

    original_pointers = [
        int.from_bytes(source[offset : offset + 2], "little")
        for offset in range(SPEAKER_POINTER_TABLE, pointer_end, 2)
    ]
    original_offsets = [0x080000 + pointer for pointer in original_pointers]
    if original_offsets[0] != SPEAKER_TEXT_START:
        raise ValueError("speaker table first pointer mismatch")
    if original_offsets != sorted(original_offsets) or len(set(original_offsets)) != entry_count:
        raise ValueError("speaker table pointers are not ordered and unique")
    for index, start in enumerate(original_offsets):
        end = source.find(b"\xCC", start, SPEAKER_TEXT_END)
        if end < 0:
            raise ValueError(f"speaker entry {index:02X} has no CC terminator")
        if index + 1 < entry_count and end + 1 != original_offsets[index + 1]:
            raise ValueError(f"speaker entry {index:02X} is not contiguous")
    if source.find(b"\xCC", original_offsets[-1], SPEAKER_TEXT_END) + 1 != SPEAKER_TEXT_END:
        raise ValueError("speaker table end signature mismatch")

    encoded_entries = [
        common.encode_text(draft, code_for) + b"\xCC"
        for draft in SPEAKER_NAME_DRAFTS
    ]
    packed = b"".join(encoded_entries)
    capacity = SPEAKER_TEXT_END - SPEAKER_TEXT_START
    if len(packed) > capacity:
        raise ValueError(f"speaker table overflow: {len(packed)} > {capacity}")

    cursor = SPEAKER_TEXT_START
    rows: list[dict[str, object]] = []
    for speaker_id, encoded in enumerate(encoded_entries):
        target[SPEAKER_POINTER_TABLE + speaker_id * 2 : SPEAKER_POINTER_TABLE + speaker_id * 2 + 2] = (
            (cursor & 0xFFFF).to_bytes(2, "little")
        )
        target[cursor : cursor + len(encoded)] = encoded
        rows.append(
            {
                "speaker_id": f"0x{speaker_id:02X}",
                "offset": f"0x{cursor:06X}",
                "encoded_bytes": len(encoded),
                "draft": SPEAKER_NAME_DRAFTS[speaker_id],
            }
        )
        cursor += len(encoded)
    target[cursor:SPEAKER_TEXT_END] = bytes(SPEAKER_TEXT_END - cursor)
    return rows, [
        (SPEAKER_POINTER_TABLE, pointer_end),
        (SPEAKER_TEXT_START, SPEAKER_TEXT_END),
    ]


def apply_screen_text_patches(
    target: bytearray,
    source: bytes,
    code_for: dict[str, int],
) -> tuple[list[dict[str, object]], list[tuple[int, int]]]:
    applied: list[dict[str, object]] = []
    ranges: list[tuple[int, int]] = []
    encoded_by_id = {
        str(row["id"]): common.encode_text(str(row["draft"]), code_for)
        for row in SCREEN_TEXT_PATCHES
    }
    overflows = [
        f"{row['id']}:{len(encoded_by_id[str(row['id'])])}>{int(row['end']) - int(row['start'])}"
        for row in SCREEN_TEXT_PATCHES
        if len(encoded_by_id[str(row["id"])]) > int(row["end"]) - int(row["start"])
    ]
    if overflows:
        raise ValueError("screen patch overflows: " + ", ".join(overflows))
    for row in SCREEN_TEXT_PATCHES:
        patch_id = str(row["id"])
        start = int(row["start"])
        end = int(row["end"])
        end_command = int(row["end_command"])
        if not 0 <= start < end < len(source):
            raise ValueError(f"invalid screen patch range: {patch_id}")
        if source[end] != end_command:
            raise ValueError(
                f"screen patch end signature mismatch: {patch_id}: "
                f"0x{source[end]:02X} != 0x{end_command:02X}"
            )
        encoded = encoded_by_id[patch_id]
        slot = end - start
        if len(encoded) > slot:
            raise ValueError(f"screen patch overflow: {patch_id}: {len(encoded)} > {slot}")

        if end_command == 0xC0:
            # Terminate immediately after the Korean text; the remaining bytes
            # are unreachable padding inside the original record.
            replacement = encoded + b"\xC0" + bytes(slot - len(encoded))
            target[start : end + 1] = replacement
            changed_end = end + 1
            terminator = start + len(encoded)
        else:
            # The external event resumes at this exact marker address.
            padding = fixed_command_padding(slot - len(encoded))
            # D1 resets the text page/cursor.  If fixed-address padding follows
            # it, those visible spaces are processed on the freshly reset page
            # and can offset or hide the next continuation.  Keep a final page
            # break immediately beside every fixed handoff/return marker and
            # put the inert filler first.  The battle reward template ends in
            # D1+CC and exposed this bug intermittently on the following level
            # or experience page.
            if end_command in (0xD3, 0xCC, 0xDE) and encoded.endswith(b"\xD1"):
                replacement = encoded[:-1] + padding + encoded[-1:]
            else:
                replacement = encoded + padding
            target[start:end] = replacement
            changed_end = end
            terminator = None
            if target[end] != end_command:
                raise ValueError(f"screen patch moved fixed command: {patch_id}")

        ranges.append((start, changed_end))
        applied.append(
            {
                "id": patch_id,
                "offset": f"0x{start:06X}",
                "slot_bytes": slot,
                "encoded_bytes": len(encoded),
                "end_command": f"0x{end_command:02X}",
                "end_command_offset": f"0x{end:06X}",
                "terminator": None if terminator is None else f"0x{terminator:06X}",
            }
        )
    return applied, ranges


def trailing_command_start(data: bytes) -> int:
    """Find the start of the contiguous command suffix at the end of data."""

    cursor = len(data)
    for position, command in reversed(scan_commands(data)):
        command_end = position + 1 + COMMAND_PARAMETERS.get(command, 0)
        if command_end == cursor:
            cursor = position
        elif command_end < cursor:
            break
    return cursor


def runtime_fixed_anchors(data: bytes) -> list[tuple[int, bytes]]:
    """Return fixed return/handoff commands with their complete operands."""

    anchors: list[tuple[int, bytes]] = []
    for position, command in scan_commands(data):
        if command not in (0xCC, 0xD3, 0xDE):
            continue
        size = 1 + COMMAND_PARAMETERS.get(command, 0)
        anchors.append((position, data[position : position + size]))
    return anchors


def apply_runtime_record_patches(
    target: bytearray,
    source: bytes,
    code_for: dict[str, int],
) -> tuple[list[dict[str, object]], list[tuple[int, int]]]:
    """Patch uncatalogued C0 records while preserving every event anchor."""

    applied: list[dict[str, object]] = []
    ranges: list[tuple[int, int]] = []
    for spec in RUNTIME_RECORD_PATCHES:
        patch_id = str(spec["id"])
        start = int(spec["start"])
        end = int(spec["end"])
        if not 0 <= start < end < len(source) or source[end] != 0xC0:
            raise ValueError(f"invalid runtime record range: {patch_id}")
        raw = source[start:end]
        draft = (
            str(spec["draft"])
            .replace("[TOP2]", "[BYTE:D9]")
            .replace("[BOTTOM]", "[BYTE:D8]")
            .replace("[TOP]", "[DFT]")
        )
        encoded = common.encode_text(draft, code_for)
        source_anchors = runtime_fixed_anchors(raw)
        translated_anchors = runtime_fixed_anchors(encoded)
        if [anchor for _position, anchor in translated_anchors] != [
            anchor for _position, anchor in source_anchors
        ]:
            raise ValueError(f"runtime anchor signature mismatch: {patch_id}")

        source_cursor = 0
        translated_cursor = 0
        segment_rows: list[dict[str, object]] = []
        for index, ((source_anchor, anchor), (translated_anchor, _)) in enumerate(
            zip(source_anchors, translated_anchors)
        ):
            anchor_size = len(anchor)
            source_end = source_anchor + anchor_size
            translated_end = translated_anchor + anchor_size
            slot = source_end - source_cursor
            segment = encoded[translated_cursor:translated_end]
            if len(segment) > slot:
                raise ValueError(
                    f"runtime fixed segment overflow: {patch_id}:{index}: "
                    f"{len(segment)}>{slot}"
                )
            padding = fixed_command_padding(slot - len(segment))
            suffix = trailing_command_start(segment)
            replacement = segment[:suffix] + padding + segment[suffix:]
            destination = start + source_cursor
            target[destination : destination + slot] = replacement
            segment_rows.append(
                {
                    "offset": f"0x{destination:06X}",
                    "slot_bytes": slot,
                    "encoded_bytes": len(segment),
                    "anchor": anchor.hex(" ").upper(),
                    "anchor_offset": f"0x{start + source_anchor:06X}",
                }
            )
            source_cursor = source_end
            translated_cursor = translated_end

        slot = len(raw) - source_cursor
        segment = encoded[translated_cursor:]
        if len(segment) > slot:
            raise ValueError(
                f"runtime final segment overflow: {patch_id}: {len(segment)}>{slot}"
            )
        destination = start + source_cursor
        replacement = segment + b"\xC0" + bytes(slot - len(segment))
        target[destination : end + 1] = replacement
        segment_rows.append(
            {
                "offset": f"0x{destination:06X}",
                "slot_bytes": slot,
                "encoded_bytes": len(segment),
                "terminator": f"0x{destination + len(segment):06X}",
            }
        )
        ranges.append((start, end + 1))
        applied.append(
            {
                "id": patch_id,
                "offset": f"0x{start:06X}",
                "end_offset": f"0x{end:06X}",
                "anchor_count": len(source_anchors),
                "segments": segment_rows,
            }
        )
    return applied, ranges


# Parameter lengths used only to locate real command boundaries.  This avoids
# mistaking an E3 phrase index or an E4-E7 Korean glyph index of D7 for a DFT.
COMMAND_PARAMETERS = {
    0xC1: 2,
    0xC2: 1,
    0xC3: 1,
    0xC5: 4,
    0xC6: 3,
    0xC7: 3,
    0xC9: 1,
    0xCE: 1,
    0xCF: 3,
    0xD3: 2,
    0xDA: 1,
    0xDC: 1,
    0xDD: 4,
    0xE0: 1,
    0xE2: 2,
    0xE3: 1,
    0xE4: 1,
    0xE5: 1,
    0xE6: 1,
    0xE7: 1,
}


def scan_commands(data: bytes) -> list[tuple[int, int]]:
    commands: list[tuple[int, int]] = []
    position = 0
    while position < len(data):
        value = data[position]
        if value >= 0xC0:
            commands.append((position, value))
            position += 1 + COMMAND_PARAMETERS.get(value, 0)
        else:
            position += 1
    return commands


def dft_positions(data: bytes) -> list[int]:
    return [position for position, command in scan_commands(data) if command == 0xD7]


def fixed_entry_markers(data: bytes) -> list[tuple[int, tuple[str, ...]]]:
    """Return every address that the event engine can enter independently.

    DFT starts are direct dialogue entries.  The byte immediately after CC is
    also an entry because the event script resumes there after the external
    text call returns (item-acquired and choice-result text commonly use it).
    """

    labels: dict[int, set[str]] = {}
    for position, command in scan_commands(data):
        if command == 0xD7:
            labels.setdefault(position, set()).add("DFT")
        elif command == 0xCC and position + 1 < len(data):
            labels.setdefault(position + 1, set()).add("AFTER_CC")
    return [(position, tuple(sorted(kinds))) for position, kinds in sorted(labels.items())]


def event_flow_signature(data: bytes) -> list[tuple[int, bytes]]:
    """Commands whose count/order/operands must match the original event."""

    signature: list[tuple[int, bytes]] = []
    for position, command in scan_commands(data):
        if command == 0xD3:
            signature.append((command, data[position + 1 : position + 3]))
        elif command == 0xDC:
            signature.append((command, data[position + 1 : position + 2]))
        elif command in (0xC8, 0xCC, 0xD7, 0xDE):
            signature.append((command, b""))
    return signature


def punctuation_compact_bytes(data: bytes, slot: int) -> bytes | None:
    """Remove only printable ASCII punctuation, never command parameters."""

    if len(data) <= slot:
        return data
    removable: list[int] = []
    position = 0
    while position < len(data):
        value = data[position]
        if value >= 0xC0:
            position += 1 + COMMAND_PARAMETERS.get(value, 0)
            continue
        if value in (ord("."), ord("!"), ord(",")):
            removable.append(position)
        position += 1
    needed = len(data) - slot
    if len(removable) < needed:
        return None
    remove = set(removable[-needed:])
    return bytes(value for index, value in enumerate(data) if index not in remove)


def d3_targets_are_stable(raw: bytes, encoded: bytes, base_offset: int) -> bool:
    """Allow external targets and internal targets fixed by an identical entry prefix."""

    original_markers = fixed_entry_markers(raw)
    translated_markers = fixed_entry_markers(encoded)
    if [kinds for _position, kinds in original_markers] != [
        kinds for _position, kinds in translated_markers
    ]:
        return False
    base_low = base_offset & 0xFFFF
    for position, command in scan_commands(raw):
        if command != 0xD3:
            continue
        target_low = raw[position + 1] | (raw[position + 2] << 8)
        relative = target_low - base_low
        if not 0 <= relative < len(raw):
            continue
        matched = False
        for index, (original_entry, _kinds) in enumerate(original_markers):
            delta = relative - original_entry
            if not 0 <= delta <= 8:
                continue
            translated_entry = translated_markers[index][0]
            if raw[original_entry:relative] == encoded[translated_entry : translated_entry + delta]:
                matched = True
                break
        if not matched:
            return False
    return True


def apply_mint_news_record(
    target: bytearray,
    row: dict[str, str],
    code_for: dict[str, int],
) -> tuple[dict[str, object], tuple[int, int]]:
    """Rebuild the five Mint reports around their original shared-signature target."""

    record_id = row["record_id"]
    if record_id != "EN-058580":
        raise ValueError(record_id)
    raw = bytes.fromhex(row["raw_hex"])
    encoded = common.encode_text(draft_for(record_id), code_for)
    original_dfts = dft_positions(raw)
    translated_dfts = dft_positions(encoded)
    if len(original_dfts) != 5 or len(translated_dfts) != 5:
        raise ValueError("unexpected Mint report entry count")

    translated_d3s = [position for position, command in scan_commands(encoded) if command == 0xD3]
    if len(translated_d3s) != 5:
        raise ValueError("unexpected Mint report jump count")
    for position in translated_d3s:
        if encoded[position : position + 3] != bytes.fromhex("D3 81 89"):
            raise ValueError("Mint report jump does not target shared signature")

    base_offset = int(row["start_offset"], 16)
    signature_target = 0x8981 - (base_offset & 0xFFFF)
    signature_source = translated_d3s[-1] + 3
    original_entries = original_dfts + [signature_target]
    translated_entries = translated_dfts + [signature_source]
    original_bounds = original_entries + [len(raw)]
    translated_bounds = translated_entries + [len(encoded)]
    segments = [
        encoded[translated_bounds[index] : translated_bounds[index + 1]]
        for index in range(len(original_entries))
    ]
    slot_sizes = [
        original_bounds[index + 1] - original_bounds[index]
        for index in range(len(original_entries))
    ]
    if any(len(segment) > slot for segment, slot in zip(segments, slot_sizes)):
        details = ", ".join(
            f"{len(segment)}>{slot}"
            for segment, slot in zip(segments, slot_sizes)
            if len(segment) > slot
        )
        raise ValueError(f"Mint report fixed segment overflow: {details}")

    segment_rows: list[dict[str, object]] = []
    for index, (original_start, segment, slot) in enumerate(zip(original_entries, segments, slot_sizes)):
        destination = base_offset + original_start
        if index + 1 < len(original_entries):
            replacement = segment + b" " * (slot - len(segment))
        else:
            replacement = segment + b"\xC0" + bytes(slot - len(segment))
        target[destination : destination + len(replacement)] = replacement
        segment_rows.append(
            {
                "entry": f"0x{destination:06X}",
                "entry_kind": "DFT" if index < 5 else "D3_TARGET",
                "encoded_bytes": len(segment),
                "slot_bytes": slot,
            }
        )
    return (
        {
            "id": record_id,
            "offset": f"0x{base_offset:06X}",
            "entry_count": len(original_entries),
            "segments": segment_rows,
        },
        (base_offset, base_offset + len(raw) + 1),
    )


def main() -> None:
    source = SOURCE.read_bytes()
    if len(source) != SOURCE_LENGTH or common.sha256(source) != SOURCE_SHA256:
        raise ValueError("unexpected Robotrek (USA) source ROM")
    for offset, expected, label in (
        (TEXT_DISPATCH_OFFSET, TEXT_DISPATCH_ORIGINAL, "text dispatcher"),
        (FONT_SOURCE_OFFSET, FONT_SOURCE_ORIGINAL, "font source calculator"),
        (DMA_BANK_OFFSET, DMA_BANK_ORIGINAL, "font DMA bank"),
    ):
        if source[offset : offset + len(expected)] != expected:
            raise ValueError(f"{label} signature mismatch at 0x{offset:06X}")

    rows = common.read_catalog()
    target = bytearray(source)
    target.extend(b"\xFF" * (TARGET_LENGTH - len(target)))
    target[NATIVE_FONT_MIRROR_OFFSET : NATIVE_FONT_MIRROR_OFFSET + NATIVE_FONT_SIZE] = source[
        NATIVE_FONT_SOURCE : NATIVE_FONT_SOURCE + NATIVE_FONT_SIZE
    ]

    eligible: list[dict[str, str]] = []
    segmented_candidates: list[dict[str, str]] = []
    skipped: dict[str, str] = {}
    for row in rows:
        record_id = row["record_id"]
        if record_id not in DRAFTS:
            continue
        if record_id in NON_DIALOGUE_IDS:
            skipped[record_id] = "non-dialogue data"
        elif record_id in MIXED_DATA_IDS:
            skipped[record_id] = "mixed binary/text boundary unresolved"
        elif record_id in INDIRECT_CF:
            skipped[record_id] = "shared CF target retained in English for this inline build"
        else:
            raw = bytes.fromhex(row["raw_hex"])
            controls = scan_commands(raw)
            command_values = {command for _position, command in controls}
            if 0xD3 in command_values or 0xCC in command_values or len(dft_positions(raw)) != 1:
                skipped[record_id] = "internal jump/return or nested entry"
                segmented_candidates.append(row)
            else:
                eligible.append(row)

    # These eight records are outside the main catalogue but use the same
    # physical D7...C0 format.  Route them through the fixed-entry writer so
    # every nested D7/CC resume address remains absolute.
    supplemental_rows = read_supplemental_rows()
    segmented_candidates.extend(supplemental_rows)

    # Include segmented candidates too; their exact two-byte glyph lengths are
    # needed before deciding whether every fixed entry segment fits.
    code_for, map_rows = common.install_font(
        target,
        [draft_for(row["record_id"]) for row in eligible + segmented_candidates]
        + [DRAFTS[record_id] for record_id in INDIRECT_CF]
        + [str(row["draft"]) for row in SCREEN_TEXT_PATCHES]
        + [str(row["draft"]) for row in RUNTIME_RECORD_PATCHES]
        + list(SPEAKER_NAME_DRAFTS),
    )

    dispatcher = make_dispatcher()
    stubs = make_dispatch_stubs(source)
    calculator = make_source_calculator()
    dispatch_patch = bytes((0x5C, DISPATCHER_CPU & 0xFF, DISPATCHER_CPU >> 8, 0xD8))
    dispatch_patch += b"\xEA" * (len(TEXT_DISPATCH_ORIGINAL) - len(dispatch_patch))
    source_patch = bytes((0x22, SOURCE_CALCULATOR_CPU & 0xFF, SOURCE_CALCULATOR_CPU >> 8, 0xD8, 0x85, 0x46))
    source_patch += b"\xEA" * (len(FONT_SOURCE_ORIGINAL) - len(source_patch))
    target[TEXT_DISPATCH_OFFSET : TEXT_DISPATCH_OFFSET + len(dispatch_patch)] = dispatch_patch
    target[FONT_SOURCE_OFFSET : FONT_SOURCE_OFFSET + len(source_patch)] = source_patch
    target[DMA_BANK_OFFSET : DMA_BANK_OFFSET + len(DMA_BANK_ORIGINAL)] = bytes.fromhex("A9 D8 8D 04 43")
    target[DISPATCHER_OFFSET : DISPATCHER_OFFSET + len(dispatcher)] = dispatcher
    target[STUB_TABLE_OFFSET : STUB_TABLE_OFFSET + len(stubs)] = stubs
    target[SOURCE_CALCULATOR_OFFSET : SOURCE_CALCULATOR_OFFSET + len(calculator)] = calculator

    applied: list[dict[str, object]] = []
    punctuation_compacted: list[str] = []
    ranges: list[tuple[int, int]] = []
    for row in eligible:
        record_id = row["record_id"]
        draft = draft_for(record_id)
        encoded = common.encode_text(draft, code_for)
        raw = bytes.fromhex(row["raw_hex"])
        if event_flow_signature(encoded) != event_flow_signature(raw):
            skipped[record_id] = "event-flow signature mismatch"
            continue
        slot = int(row["length_without_terminator"])
        if len(encoded) > slot:
            compacted = punctuation_compact(draft, slot, code_for)
            if compacted is None:
                skipped[record_id] = f"encoded length overflow: {len(encoded)} > {slot}"
                continue
            _draft, encoded = compacted
            punctuation_compacted.append(record_id)
        offset = int(row["start_offset"], 16)
        # End immediately at the translated text. Bytes after this C0 are
        # unreachable padding kept inside the original physical slot.
        replacement = encoded + b"\xC0" + bytes(slot - len(encoded))
        target[offset : offset + slot + 1] = replacement
        ranges.append((offset, offset + slot + 1))
        applied.append(
            {
                "id": record_id,
                "offset": f"0x{offset:06X}",
                "slot_bytes": slot,
                "encoded_bytes": len(encoded),
                "terminator": f"0x{offset + len(encoded):06X}",
            }
        )

    segmented_applied: list[dict[str, object]] = []
    segmented_punctuation_compacted: list[str] = []
    for row in segmented_candidates:
        record_id = row["record_id"]
        raw = bytes.fromhex(row["raw_hex"])
        if record_id == "EN-058580":
            mint_row, mint_range = apply_mint_news_record(target, row, code_for)
            skipped.pop(record_id, None)
            segmented_applied.append(mint_row)
            ranges.append(mint_range)
            continue
        encoded = common.encode_text(draft_for(record_id), code_for)
        if event_flow_signature(encoded) != event_flow_signature(raw):
            skipped[record_id] = "event-flow signature mismatch"
            continue
        base_offset = int(row["start_offset"], 16)
        original_markers = fixed_entry_markers(raw)
        translated_markers = fixed_entry_markers(encoded)
        if record_id in INTERNAL_D3_ANCHORS:
            base_low = base_offset & 0xFFFF
            internal_targets = []
            for position, command in scan_commands(raw):
                if command != 0xD3:
                    continue
                target_low = raw[position + 1] | (raw[position + 2] << 8)
                relative = target_low - base_low
                if 0 <= relative < len(raw):
                    internal_targets.append(relative)
            anchor_bytes = common.encode_text(INTERNAL_D3_ANCHORS[record_id], code_for)
            anchor_position = encoded.find(anchor_bytes)
            internal_targets = sorted(set(internal_targets))
            if len(internal_targets) != 1 or anchor_position < 0 or encoded.find(
                anchor_bytes, anchor_position + 1
            ) >= 0:
                skipped[record_id] = "internal D3 anchor is ambiguous"
                continue
            original_markers = sorted(original_markers + [(internal_targets[0], ("D3_TARGET",))])
            translated_markers = sorted(translated_markers + [(anchor_position, ("D3_TARGET",))])
        original_kinds = [kinds for _position, kinds in original_markers]
        translated_kinds = [kinds for _position, kinds in translated_markers]
        if original_kinds != translated_kinds:
            skipped[record_id] = (
                f"fixed-entry layout mismatch: {translated_kinds!r} != {original_kinds!r}"
            )
            continue
        if (
            record_id not in INTERNAL_D3_ANCHORS
            and any(command == 0xD3 for _position, command in scan_commands(raw))
            and not d3_targets_are_stable(raw, encoded, base_offset)
        ):
            skipped[record_id] = "internal D3 target is not fixed by a matching entry prefix"
            continue
        original_entries = [position for position, _kinds in original_markers]
        translated_entries = [position for position, _kinds in translated_markers]
        original_bounds = original_entries + [len(raw)]
        translated_bounds = translated_entries + [len(encoded)]
        translated_segments = [
            encoded[translated_bounds[index] : translated_bounds[index + 1]]
            for index in range(len(original_entries))
        ]
        original_slot_sizes = [
            original_bounds[index + 1] - original_bounds[index]
            for index in range(len(original_entries))
        ]
        compacted_any = False
        for index, (segment, slot_size) in enumerate(zip(translated_segments, original_slot_sizes)):
            if len(segment) <= slot_size:
                continue
            compacted = punctuation_compact_bytes(segment, slot_size)
            if compacted is not None:
                translated_segments[index] = compacted
                compacted_any = True
        segment_sizes = [
            (len(segment), slot_size)
            for segment, slot_size in zip(translated_segments, original_slot_sizes)
        ]
        if any(encoded_size > slot_size for encoded_size, slot_size in segment_sizes):
            skipped[record_id] = "fixed-entry segment overflow: " + ", ".join(
                f"{encoded_size}>{slot_size}"
                for encoded_size, slot_size in segment_sizes
                if encoded_size > slot_size
            )
            continue
        if compacted_any:
            segmented_punctuation_compacted.append(record_id)

        segment_rows: list[dict[str, object]] = []
        for index, ((encoded_size, slot_size), original_start, segment) in enumerate(
            zip(segment_sizes, original_entries, translated_segments)
        ):
            destination = base_offset + original_start
            if index + 1 < len(original_entries):
                # Keep the following entry at its original absolute address.
                # When it is an AFTER_CC entry, CC itself must remain directly
                # before that address; padding after CC would change the event
                # engine's resume PC and can leave the dialogue box open.
                padding = b" " * (slot_size - len(segment))
                next_kinds = set(original_markers[index + 1][1])
                if "AFTER_CC" in next_kinds:
                    if not segment or segment[-1] != 0xCC:
                        raise ValueError(f"missing CC before fixed entry: {record_id}")
                    replacement = segment[:-1] + padding + segment[-1:]
                else:
                    replacement = segment + padding
            else:
                replacement = segment + b"\xC0" + bytes(slot_size - len(segment))
            target[destination : destination + len(replacement)] = replacement
            segment_rows.append(
                {
                    "entry": f"0x{destination:06X}",
                    "entry_kind": "+".join(original_markers[index][1]),
                    "encoded_bytes": encoded_size,
                    "slot_bytes": slot_size,
                }
            )
        skipped.pop(record_id, None)
        ranges.append((base_offset, base_offset + len(raw) + 1))
        segmented_applied.append(
            {
                "id": record_id,
                "offset": f"0x{base_offset:06X}",
                "entry_count": len(original_entries),
                "segments": segment_rows,
            }
        )

    # Five catalogue records resolve to three native CF continuation targets.
    # Keep the native wrappers and replace each shared continuation with one
    # additional CF hop to expanded Korean text.  This preserves the original
    # caller's D7/CC stack discipline and fixes every caller at once.
    payload_cursor = (0, common.PAYLOAD_PAGES[0]["file_start"])
    seen_shared_targets: set[int] = set()
    shared_cf_applied: list[dict[str, object]] = []
    payload_ranges: list[tuple[int, int]] = []
    for record_id, (target_hex, target_length) in INDIRECT_CF.items():
        target_offset = int(target_hex, 16)
        if target_offset in seen_shared_targets:
            skipped.pop(record_id, None)
            continue
        seen_shared_targets.add(target_offset)
        encoded = common.encode_text(DRAFTS[record_id], code_for)
        continuation = encoded[1:] if encoded and encoded[0] == 0xD7 else encoded
        payload = continuation + b"\xCC"
        destination, bank, address, payload_cursor = common.pack(
            target, payload_cursor, payload
        )
        wrapper = bytes((0xCF, address & 0xFF, address >> 8, bank, 0xCC))
        if len(wrapper) > target_length:
            raise ValueError(f"shared CF wrapper overflow: {record_id}")
        target[target_offset : target_offset + target_length] = (
            wrapper + bytes(target_length - len(wrapper))
        )
        ranges.append((target_offset, target_offset + target_length))
        payload_ranges.append((destination, destination + len(payload)))
        shared_cf_applied.append(
            {
                "id": record_id,
                "target": target_hex,
                "slot_bytes": target_length,
                "destination": f"0x{destination:06X}",
                "cpu": f"{bank:02X}:{address:04X}",
                "payload_bytes": len(payload),
                "wrapper": wrapper.hex(" ").upper(),
            }
        )
        for shared_id, (shared_target, _shared_length) in INDIRECT_CF.items():
            if int(shared_target, 16) == target_offset:
                skipped.pop(shared_id, None)

    runtime_record_applied, runtime_record_ranges = apply_runtime_record_patches(
        target, source, code_for
    )
    ranges.extend(runtime_record_ranges)
    screen_text_applied, screen_text_ranges = apply_screen_text_patches(
        target, source, code_for
    )
    ranges.extend(screen_text_ranges)
    speaker_names_applied, speaker_name_ranges = apply_speaker_name_table(
        target, source, code_for
    )
    ranges.extend(speaker_name_ranges)

    ordered = sorted(ranges)
    for previous, current in zip(ordered, ordered[1:]):
        if current[0] < previous[1]:
            raise ValueError(f"overlapping source records: {previous} / {current}")
    for row in applied:
        if target[int(row["terminator"], 16)] != 0xC0:
            raise ValueError(f"missing inline terminator: {row['id']}")
    for previous, current in zip(sorted(payload_ranges), sorted(payload_ranges)[1:]):
        if current[0] < previous[1]:
            raise ValueError(f"overlapping shared payloads: {previous} / {current}")

    checksum = refresh_full_hirom_checksum(target)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(target)
    with OUTPUT_MAP.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(map_rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(map_rows)

    unresolved = len(skipped)
    supplemental_applied = sum(
        row["id"] in SUPPLEMENTAL_DRAFTS for row in segmented_applied
    )
    manifest = {
        "kind": "Robotrek USA Korean dialogue inline-only safe test",
        "status": "runtime-test-required",
        "source_sha256": SOURCE_SHA256,
        "output_sha256": common.sha256(target),
        "output_size": len(target),
        "font": "gilche 1bpp 8x16 (selected option 1)",
        "glyph_count": len(code_for),
        "direct_records_applied": len(applied),
        "fixed_entry_records_applied": len(segmented_applied),
        "supplemental_records_applied": supplemental_applied,
        "shared_cf_targets_applied": len(shared_cf_applied),
        "shared_cf_record_ids_effectively_applied": len(INDIRECT_CF),
        "screen_text_spans_applied": len(screen_text_applied),
        "runtime_records_applied": len(runtime_record_applied),
        "speaker_names_applied": len(speaker_names_applied),
        "total_translated_records_applied": (
            len(applied) + len(segmented_applied) + len(INDIRECT_CF)
        ),
        "total_translation_units_applied": (
            len(applied)
            + len(segmented_applied)
            + len(INDIRECT_CF)
            + len(screen_text_applied)
            + len(runtime_record_applied)
            + len(speaker_names_applied)
        ),
        "translated_records_pending_or_shared_cf": len(skipped),
        "translated_records_pending_non_cf": unresolved,
        "important_compact_drafts": sorted(IMPORTANT_COMPACT),
        "punctuation_compacted_drafts": sorted(punctuation_compacted),
        "segmented_punctuation_compacted_drafts": sorted(segmented_punctuation_compacted),
        "header_checksum": f"0x{checksum:04X}",
        "mechanism": (
            "in-place dialogue replacement plus three shared continuation CF relocations; "
            "original script controls and caller entry points are preserved"
        ),
        "applied": applied,
        "fixed_entry_applied": segmented_applied,
        "shared_cf_applied": shared_cf_applied,
        "screen_text_applied": screen_text_applied,
        "runtime_record_applied": runtime_record_applied,
        "speaker_name_applied": speaker_names_applied,
        "skipped": skipped,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in (
        "status", "output_sha256", "output_size", "glyph_count", "direct_records_applied",
        "fixed_entry_records_applied", "supplemental_records_applied",
        "shared_cf_targets_applied", "shared_cf_record_ids_effectively_applied",
        "screen_text_spans_applied", "runtime_records_applied", "total_translated_records_applied",
        "speaker_names_applied",
        "total_translation_units_applied",
        "translated_records_pending_or_shared_cf", "translated_records_pending_non_cf", "header_checksum"
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

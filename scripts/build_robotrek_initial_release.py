"""Create and self-check a local IPS candidate; never publish automatically."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VERSION = "v0.1.12-alpha"
SOURCE = ROOT / "Robotrek (USA).sfc"
TARGET = ROOT / "build" / "robotrek-usa-korean-dialogue-inline-safe-test.sfc"
BUILD_MANIFEST = ROOT / "build" / "robotrek-usa-korean-dialogue-inline-safe-test.json"
IPS = ROOT / "build" / f"robotrek-korean-{VERSION}.ips"
MANIFEST = ROOT / "build" / f"robotrek-korean-{VERSION}-release.json"

EXPECTED_SOURCE_SHA256 = "1E2DED7B1E350449B7A99B7EC414525E4B9B086C416DEEEE5EB3E48E032C46BD"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def write_ips(source: bytes, target: bytes, output: Path) -> None:
    patch = bytearray(b"PATCH")
    cursor = 0
    while cursor < len(target):
        if cursor < len(source) and source[cursor] == target[cursor]:
            cursor += 1
            continue
        start = cursor
        cursor += 1
        while cursor < len(target) and cursor - start < 0xFFFF:
            if cursor < len(source) and source[cursor] == target[cursor]:
                break
            cursor += 1
        patch.extend(start.to_bytes(3, "big"))
        patch.extend((cursor - start).to_bytes(2, "big"))
        patch.extend(target[start:cursor])
    patch.extend(b"EOF")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patch)


def apply_ips(source: bytes, patch: bytes) -> bytes:
    if patch[:5] != b"PATCH":
        raise ValueError("not an IPS patch")
    result = bytearray(source)
    position = 5
    while patch[position : position + 3] != b"EOF":
        offset = int.from_bytes(patch[position : position + 3], "big")
        size = int.from_bytes(patch[position + 3 : position + 5], "big")
        position += 5
        if size:
            result[offset : offset + size] = patch[position : position + size]
            position += size
        else:
            run_length = int.from_bytes(patch[position : position + 2], "big")
            value = patch[position + 2]
            position += 3
            result[offset : offset + run_length] = bytes((value,)) * run_length
    return bytes(result)


def main() -> None:
    source = SOURCE.read_bytes()
    target = TARGET.read_bytes()
    build_manifest = json.loads(BUILD_MANIFEST.read_text(encoding="utf-8"))

    source_hash = sha256(source)
    target_hash = sha256(target)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"unexpected source ROM: {source_hash}")
    if target_hash != build_manifest["output_sha256"]:
        raise ValueError("target ROM does not match the verified build manifest")

    write_ips(source, target, IPS)

    if apply_ips(source, IPS.read_bytes()) != target:
        raise ValueError("IPS self-check failed")

    release_manifest = {
        "version": VERSION,
        "status": "local-test-unpublished",
        "source_rom": "Robotrek (USA), headerless",
        "source_size": len(source),
        "source_sha256": source_hash,
        "target_size": len(target),
        "target_sha256": target_hash,
        "translation_units": build_manifest["total_translation_units_applied"],
        "screen_text_spans": build_manifest["screen_text_spans_applied"],
        "runtime_records": build_manifest["runtime_records_applied"],
        "speaker_names": build_manifest["speaker_names_applied"],
        "actionable_untranslated_records": None,
        "residual_audit_status": "mixed-event and system text still under expanded audit",
        "catalog_rows_skipped_as_mixed_or_covered": build_manifest[
            "translated_records_pending_non_cf"
        ],
        "ips_sha256": sha256(IPS.read_bytes()),
        "notes": [
            "쥐 실험 이벤트의 '실험! 실험!' 대사 번역 추가; CC 복귀 주소와 뒤따르는 이벤트 코드 보존",
            "2026-09-02 사용자가 v0.1.12에서 컴퓨터 내부 이동 장면 정상 동작 확인; 근본 원인 및 다른 장면은 별도 검증 대상",
        ],
        "prior_version_improvements": [
            "동굴의 탈영 해커 재대화가 참조하는 보석 상자 문단을 0x0C9865에 고정해 빈 대화창 원인 수정",
            "회의실 경비의 공용 CF 대사 번역 추가 및 두 호출 경로와 CC 복귀 주소 보존 검증",
            "로코코 구출 후 촌장 대사의 중첩 CF 호출을 제거해 빈 대화창 멈춤 수정",
            "쥐 상점 대사 시작의 문자 [BOTTOM]을 실제 D8 창 명령으로 수정해 대화 진입 불능 해결",
            "같은 직접 화면 패치의 [TOP2] 문자를 실제 D9 창 명령으로 수정하고 재발 검증 추가",
            "쥐 상점 강화 결과가 공유하는 내부 D3 대상 0x01CED1을 원본 주소에 고정해 혼합 영문과 화면 이상 수정",
            "강화 결과 문구를 '로봇 능력 상승'과 누적 메가 데이터로 정리",
            "경관 체포 대사의 D3 E5 A7 뒤 별도 DB 진입점을 원본 주소 0x05A7B3에 복원해 후속 화면 깨짐 수정",
            "문제 경관 문장을 이름 명령 없이 자연스럽게 다듬어 비정상 이름 표기 방지",
            "전투 후 성장/레벨 상승 문구 한글화 및 D1+CC 사이 패딩으로 다음 결과 화면이 가려지던 문제 수정",
            "기존 목록이 누락한 0x07EC55-0x07F3B4의 벽 파괴, 로봇 최후, 석판 메시지 연속 대사 반영",
            "별도 실사용 0x0C951C-0x0CA432 구역의 저택, 섬 안내원, 고철, 열꽃 연속 대사 반영",
            "Mayor, Mint를 포함한 자동 화자명 표 30개 한글화",
            "NXT/CF/C6 제어 명령이 글자로 노출되던 인코딩 문법 수정",
            "암전 경비 구간의 차단기 반복 조작 힌트를 명확하게 수정",
            "혼합 이벤트·시스템 문구를 포함하는 확장 잔여 검사를 계속 진행 중",
            "0x09F0A8-0x09F469 및 0x0C9000-0x0CEB00 후반 실행 대사 110개 고정 주소 번역",
            "후반 창 위치 표기 TOP/TOP2/BOTTOM을 실제 D7/D9/D8 명령으로 정규화",
            "DC/NXT 제어 코드의 원본 인자를 복원해 대사 출력 지연과 이벤트 멈춤 수정",
            "동굴 탈출 대사의 C9 1E C8 CC 이벤트 흐름 복원",
            "D3/DE/CC 고정 재진입 주소를 분할 보존하고 번역 단위 정적 검증 통과",
            "실기/에뮬레이터 진행 검증이 필요한 알파 배포본",
        ],
    }
    MANIFEST.write_text(
        json.dumps(release_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(release_manifest, ensure_ascii=False, indent=2))
    print(f"IPS={IPS}")


if __name__ == "__main__":
    main()

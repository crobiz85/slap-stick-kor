# Slap Stick 한국어화 프로젝트

슈퍼패미컴판 `Slap Stick`(スラップスティック, Enix/Quintet, 1994)의 한국어화 작업 공간입니다.

## 현재 상태

- 기준 ROM: `Slap Stick (J).smc`
- ROM 형식: 무헤더 HiROM / FastROM
- ROM 크기: 1,572,864 bytes (12 Mbit)
- 내부 타이틀: `SLAP STICK 1 JPN`
- SHA-256: `08144EA1CE3CF6AB107837278D308E4E859574A047A2EE8EB456F7900AD4BE21`
- 일본판 원본 ROM과 실행 파일은 저작권·재배포 문제 때문에 저장소에 포함하지 않습니다.
- 대사 추출: 구조 분석 진행 중
  - `CF + 3바이트 포인터 + CC` 참조 형식 확인
  - 포인터 참조 6개 확인, 유효한 고유 문자열 2개를 `translation/anchored-text.tsv`에 보존
  - `$84:F7C2`의 16비트 포인터 표와 56개 `CC` 종료 문자열을
    `translation/static-strings.tsv`로 원문 바이트 그대로 추출
  - 반복되는 `C2/C3/CD/D1` 제어코드 후보를 `translation/control-codes.tsv`에 정리하고,
    `translation/control-annotated.tsv`에 위치를 표시
  - 내장 폰트 테스트 데이터에서 1바이트/2바이트 글리프 코드 후보를
    `translation/font-test-codes.tsv`로 분리
  - 일본판 문자표·K1~K3 사전·문자열 명령을 반영한 일본어 디코더 추가
  - 후보 블록 167개, 포인터 문자열 2개, 정적 문자열 56개를 일본어/제어코드 형태로
    `translation/decoded-text-blocks.tsv`, `translation/decoded-anchored-text.tsv`,
    `translation/decoded-static-strings.tsv`에 추출
  - 후보 블록에는 오탐이 남아 있어 게임 화면 대조 전에는 패치 입력으로 사용하지 않음
  - 검토용 대사 원고 240개를 `translation/script.tsv`로 분리했으며
    초반 메뉴·이벤트 17개에는 `translation/korean-draft.tsv`의 한국어 초안을 덧씌움
  - 일본판 폰트 위치와 반전 Game Boy 2BPP 형식을 확인하고, 초안에 필요한 한글 글리프
    132자를 대화용 `0x82xx` 미사용 슬롯에 배치해 `translation/korean-glyph-map.tsv`로 생성
  - 초안 17개 중 메인 대사 0058~0063 6개는 실제 재배치·포인터 갱신까지 적용
  - 초반 메뉴·이벤트 11개는 원래 고정 슬롯에 들어가는 압축형 프리뷰 문구를
    `translation/korean-menu-preview.tsv`로 관리해 함께 삽입
  - `translation/relocation-plan.tsv`에 원문 슬롯·CC 종료 위치·포인터 후보·재배치 조치를 기록함

## 작업 방향

1. 원본 ROM의 무결성과 헤더를 `scripts/verify_rom.ps1`로 확인합니다.
2. 문자 테이블과 제어코드를 확정하고, 전체 대사/메뉴를 추출해 `translation/`에 저장합니다.
3. 한국어 글리프와 가변폭/문자 출력 제약을 확인합니다.
4. 스크립트와 65816 패치를 재현 가능한 방식으로 빌드합니다.
5. 결과물은 원본 ROM을 요구하는 BPS/IPS 패치로 배포합니다.

추출 작업의 구체적인 주소 범위와 순서는 `docs/extraction-plan.md`에 기록합니다. 현재 원시 분석 결과는
`translation/pointer-report.tsv`, `translation/anchored-text.tsv`, `translation/static-strings.tsv`,
`translation/text-blocks-raw.tsv`, `translation/control-annotated.tsv`,
`translation/decoded-text-blocks.tsv`, `translation/decoded-anchored-text.tsv`,
`translation/decoded-static-strings.tsv`, `translation/script.tsv`,
`translation/korean-draft.tsv`, `translation/korean-glyph-map.tsv`,
`translation/korean-menu-preview.tsv`, `translation/font-layout.tsv`입니다.
마지막 파일은 오탐이 포함된 연구용 후보 목록이므로 번역 원고로 사용하지 않습니다.

## 로컬 자료

현재 제공된 도구는 다음과 같습니다.

- `Hex_Search.exe`: ROM 내 바이트/문자열 검색
- `Table_Generator.exe`: 테이블 파일 작성 보조
- `United_Script_Editor_v241015.1.exe`: 스크립트 편집 보조
- `6502_65816_Assembler_v1.1.zip`: 65816 어셈블러 자료
- `le120.zip`: 번역 작업 관련 보조 자료로 보이며, 내용 확인 후 필요한 파일만 사용

분석 스크립트는 다음과 같습니다.

- `scripts/analyze_script_pointers.py`: 포인터 참조와 `CC` 종료 후보 추출
- `scripts/extract_static_strings.py`: `$84:F7C2` 포인터 표 기반 정적 문자열 추출
- `scripts/annotate_control_codes.py`: 확인 전 제어코드를 보수적으로 표시
- `scripts/extract_font_test_codes.py`: 내장 폰트 테스트의 글리프 코드 목록 추출
- `scripts/decode_japanese_strings.py`: 일본판 문자표·사전·제어코드로 후보 대사 해독
- `scripts/build_script_catalog.py`: 해독 후보를 대화 단위 검토 원고로 정리하고 한국어 초안을 병합
- `scripts/render_font.py`: 일본판 2BPP 글꼴 영역을 미리보기 PNG로 렌더링
- `scripts/build_korean_font.py`: 초안에서 한글 글리프를 뽑아 후보 코드·타일 바이트·미리보기 생성
- `scripts/encode_translation_drafts.py`: 제어코드를 유지한 한글 바이트열과 원문 슬롯 길이 사전 검사
- `scripts/build_relocation_plan.py`: 원문 슬롯·다음 `CC` 위치·포인터 후보를 재배치 검토표로 생성
- `scripts/build_korean_preview_patch.py`: 한글 폰트와 메인 대사 6개를 삽입하고 BPS/IPS를 자체 검증하여 생성

도구 사용법과 출처는 `tools/README.md`에 기록합니다. 실행 파일 자체는 저장소에 올리지 않습니다.

## 프리뷰 패치

`patches/slap-stick-kor-preview.bps` 또는 `patches/slap-stick-kor-preview.ips`를
무헤더 일본판 원본 ROM에 적용합니다. 원본 ROM 자체는 저장소에 포함하지 않습니다.
패치는 대화용 `0x82xx` 미사용 슬롯에 넣은 132자 한글 폰트와 초안 17개를 포함합니다.
메인 대사 0058~0063은 자연스러운 원고를 재배치하고, 0002~0012는 진입점 확인 전까지
짧은 프리뷰 문구를 원래 슬롯에 넣습니다. `0x83xx`는 메뉴·폰트 테스트용 영역이라
대화 패치에는 사용하지 않습니다.

## 검증

PowerShell에서 다음처럼 실행합니다.

```powershell
.\scripts\verify_rom.ps1 -RomPath '.\Slap Stick (J).smc'
```

깨끗한 기준 ROM이 확인된 뒤에만 추출·패치 작업을 진행합니다.

## 참고 자료

- [Data Crystal: Robotrek / Slap Stick ROM map](https://datacrystal.tcrf.net/wiki/Robotrek)
- [Data Crystal: Robotrek / Strings JP](https://datacrystal.tcrf.net/wiki/Robotrek/Strings_JP)
- [SuperFamicom.org: Slap Stick ROM information](https://superfamicom.org/info/slap-stick)
- [네이버 카페 자료 31021](https://cafe.naver.com/f-e/cafes/16259867/articles/31021)
- [네이버 카페 자료 32509](https://cafe.naver.com/f-e/cafes/16259867/articles/32509)
- [네이버 카페 자료 32457](https://cafe.naver.com/f-e/cafes/16259867/articles/32457)
- [네이버 카페 자료 12357](https://m.cafe.naver.com/ca-fe/web/cafes/16259867/articles/12357)

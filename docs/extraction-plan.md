# 대사 추출 계획

## 현재 판정

대사 저장 구조 분석을 시작했고, 실제 문자열 참조 형식과 일본판 문자표를 확인했습니다. 후보
블록에는 오탐이 남아 있으므로 자동 결과는 검토용 대사 덤프이며, 그대로 패치 입력으로 사용하지
않습니다.

- 포인터 형식: `CF [주소 low] [주소 high] [은행] CC`
- HiROM 미러 주소를 파일 오프셋으로 변환할 수 있음
- ROM 전체에서 이 패턴 6개 확인
- 중복을 제거하고 `CC`까지 확인되는 고유 문자열 2개 확인
- `$84:F7C2`부터 이어지는 16비트 포인터 56개와 `$84:F832`부터 이어지는
  `CC` 종료 정적 문자열 56개 확인
- 결과: `translation/static-strings.tsv`
- `C2`, `C3`, `CD`, `D1`의 반복 패턴을 보수적으로 표시한
  `translation/control-codes.tsv`, `translation/control-annotated.tsv` 생성
- 내장 폰트 테스트 영역에서 1바이트 및 little-endian 2바이트 글리프 후보를
  `translation/font-test-codes.tsv`로 추출
- Data Crystal의 일본판 String 정의에서 기본 히라가나/가타카나 레이어와 K1~K3 사전,
  C0~E3 명령 목록을 확인하고 `scripts/decode_japanese_strings.py`에 반영
- 167개 후보 블록을 일본어·제어코드가 보이는 형태로 `translation/decoded-text-blocks.tsv`에 출력
- `D7` 대화 상태 마커 기준으로 일본어가 포함된 세그먼트 240개를
  `translation/script.tsv` 검토 원고로 분리하고, 초반 메뉴·이벤트 17개는
  `translation/korean-draft.tsv`에서 한국어 초안을 병합하도록 구성
- 결과: `translation/pointer-report.tsv`, `translation/anchored-text.tsv`
- 휴리스틱 후보 167개는 코드와 데이터가 섞여 있으므로 원시 파일과 디코드 파일 모두 연구용으로만 사용

## 확인된 ROM 구조

Data Crystal의 Robotrek 자료에 따르면 이 게임은 다음과 같이 나뉩니다.

- `0x18000-0x27FFF`: 공용 데이터 테이블과 문자열이 섞인 코드 페이지
- `0x28000-0x2E9A9`: 스크립트·스프라이트 정의 테이블
- `0x2E9AA-0x2FF66`: 스크립트 코드
- `0x48000-0x4FFB3`: 문자열 처리 루틴과 일부 스크립트
- `0x58000-0x5FCD6`, `0x68000-0x6F7D5`, `0x78000-0x7F3B4`, `0x88000-0x8F51E`, `0x98000-0x9F478`: 스크립트 코드/문자열 템플릿 영역
- `0x80000-0x81FFF`: 기존 ROM map에서 그래픽/폰트 후보로 언급된 영역. 현재 2BPP 미리보기는
  노이즈로 확인되어 실제 폰트 위치·압축 여부를 아직 확정하지 않음

게임은 Quintet 계열 압축 데이터를 포함하므로 그래픽 분석은 별도 압축 해제가 필요할 수 있습니다.
대사는 Shift-JIS가 아니라 게임 전용 바이트 테이블입니다.

Data Crystal의 ROM map은 문자열 처리 코드와 스크립트 코드가 여러 코드 페이지에 나뉘어 있고,
`0x80000-0x81FFF`는 2BPP 원시 그래픽(font) 영역으로 기록합니다. Snes-Projects의 Robotrek
분석 메모도 확장 시 `CF` 포인터와 `CC` 경계를 사용한다고 설명하므로, 이 프로젝트는 그 구조를
기준으로 검증을 진행합니다.

## 다음 작업

1. `decoded-text-blocks.tsv`의 실제 대화 블록을 게임 화면·일본어 대본과 대조합니다.
2. 같은 디코더를 정적 문자열·포인터 문자열에 적용해 누락·오탐을 줄입니다.
3. `translation/korean-draft.tsv`에 `script.tsv` ID별 한국어 초안을 작성하고 제어코드를 유지합니다.
4. 한국어 글리프를 넣을 폰트 위치와 텍스트 길이 제약을 검증한 뒤 삽입기를 작성합니다.

제어코드 후보를 비교할 때는 [일본판 String 정의](https://datacrystal.tcrf.net/wiki/Robotrek/Strings_JP)를
우선 사용하고, [Robotrek 프랑스어 번역 연구 글](https://romhack.org/viewtopic.php?t=817)은
미국판/번역판 보조 자료로만 사용합니다.

처음부터 ROM을 확장하지 않습니다. 텍스트 공간이 실제로 부족한지 확인한 뒤, 필요할 때만
`Lunar Expand`의 호환 ExHiROM 방식을 검토합니다. Lunar Expand 문서에도 RoboTrek이 해당
호환 방식이 필요한 사례로 언급되어 있으므로, 확장 시에는 포인터 은행 매핑을 함께 검증해야 합니다.

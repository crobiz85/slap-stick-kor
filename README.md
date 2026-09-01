# Robotrek 한국어 패치

SNES 영문판 `Robotrek (USA)`를 기준으로 작업하는 한국어 패치 프로젝트입니다.

## 일본어판에서 영문판으로 전환한 이유

초기에는 일본어판을 기준으로 진행했지만, 최종 패치 대상과 실제 검증 환경을 미국판
(`Robotrek (USA)`)으로 통일했습니다. 일본어판과 미국판은 대사 인코딩·문자 테이블·문자열
배치·포인터 및 이벤트 제어 코드가 달라 일본어판용 주소와 번역 데이터를 그대로 사용할 수
없습니다. 현재 번역 목록, 진행 불가 수정, 화면 깨짐 검증은 모두 해시가 확인된 영문판을
기준으로 다시 정리했으며, 따라서 패치도 영문판에만 적용됩니다.

## 현재 배포본

- 버전: `v0.1.9-alpha`
- 배포 형식: IPS만 제공
- 패치: [`patches/robotrek-korean-v0.1.9-alpha.ips`](patches/robotrek-korean-v0.1.9-alpha.ips)
- 적용 대상: 무헤더 `Robotrek (USA)` ROM
- 원본 크기: `1,572,864 bytes`
- 원본 SHA-256: `1E2DED7B1E350449B7A99B7EC414525E4B9B086C416DEEEE5EB3E48E032C46BD`
- 적용 결과 크기: `2,097,152 bytes`
- 적용 결과 SHA-256: `38C7E24A54D2373850884AFA297CC9A3F8D123E77A62C68F9B23E9E28952CD07`

원본 ROM과 패치 적용 완료 ROM은 저장소 및 배포 파일에 포함하지 않습니다.

## 적용 방법

1. 합법적으로 소유한 무헤더 영문판 `Robotrek (USA)` ROM을 준비합니다.
2. 사용하는 IPS 패처 또는 에뮬레이터의 IPS 기능으로
   `robotrek-korean-v0.1.9-alpha.ips`를 원본에 적용합니다.
3. 패처가 생성한 확장 ROM을 에뮬레이터에서 실행합니다. 원본 해시가 위 값과 다르면 적용하지 마세요.

패치 적용이 실패하면 헤더가 붙은 ROM인지, 원본 버전이 미국판인지, 파일 해시가 일치하는지 먼저 확인하세요.

현재 버전은 진행 검증용 알파입니다. 혼합 이벤트·시스템 문구의 잔여 미번역과 실제 플레이 중
발견되는 줄바꿈·이벤트 문제를 계속 수정하고 있습니다.

## 재현 가능한 빌드

저장소에는 현재 빌드가 실제로 참조하는 스크립트와 번역 자료만 유지합니다. 원본 ROM은 로컬
작업 폴더에 `Robotrek (USA).sfc`라는 이름으로 직접 준비해야 합니다.

```powershell
python scripts/build_robotrek_english_korean_inline_safe_test.py
python scripts/verify_robotrek_english_korean_inline_safe_test.py
python scripts/build_robotrek_initial_release.py
```

마지막 명령은 `patches/`에 IPS 파일만 생성하며, 생성한 IPS를 원본에 다시 적용해 결과 ROM과
완전히 같은지 자체 검증합니다. BPS, ZIP, 완성 ROM은 생성하거나 배포하지 않습니다.

## 실제 사용한 외부 도구·글꼴

- [Python](https://www.python.org/) `3.12.13`: 빌드·검증·IPS 생성 스크립트 실행
- [Pillow](https://python-pillow.org/) `12.3.0`: 한글 글리프 렌더링과 SNES 타일 변환
- `assets/fonts/gilche-1bpp-8x16.fnt`: 실제 패치에 사용한 GILCHE 1bpp 8×16 글꼴
  (38,912 bytes, SHA-256 `5BE8F0C52F8FDA3AF4E8B7429D49AE69C4C4BD7D3A59D9C5B848CD1EFAEDB586`)
- 출처: [한식구 카페 「[폰트] 7x11 길체」](https://cafe.naver.com/hansicgu/824)
  (작성자 에슘, 2008-11-22). 사용자가 제공한 게시글 첨부파일과 저장소의 글꼴 파일은
  바이트 단위로 일치합니다.

## v0.1.9-alpha 핵심 수정

- 쥐 상점 대사 시작에 문자로 들어간 `[BOTTOM]`을 실제 `D8` 창 명령으로 수정
- 직접 화면 패치의 `[TOP2]`를 실제 `D9` 창 명령으로 수정하고 재발 검증 추가
- 쥐 상점 강화 결과의 내부 `D3` 대상 주소 보존
- 경관 체포 대사의 별도 `DB` 진입점 복원
- 전투 후 성장·레벨 상승 결과 화면 및 후반부 진행 대사 보강
- 이벤트 제어 코드와 고정 재진입 주소에 대한 정적 검증 추가

## 오류·번역 제보

멈춤, 크래시, 화면 깨짐, 출력 지연 또는 미번역을 발견하면 발생 위치와 직전 행동,
에뮬레이터·패치 버전을 함께 기록해 주세요. 대사 화면은 스크린샷으로 제보하면 확인이 쉽습니다.
원본 ROM이나 패치 적용 완료 ROM을 이슈·릴리스·첨부 파일에 올리지 마세요.

## 저작권 및 배포 원칙

- `Robotrek` 및 원작 게임의 저작권과 상표권은 각 권리자에게 있습니다. 이 프로젝트는
  권리자와 제휴·승인 관계가 없는 비공식 팬 번역입니다.
- 게임 ROM, 패치 적용 완료 ROM, 원본 그래픽·음원은 저장소와 배포 파일에 포함하지 않습니다.
- 공개 배포물은 합법적으로 소유한 원본 ROM에 직접 적용하는 IPS 차분 패치뿐입니다.
- 패치는 비상업적·개인적 사용을 전제로 하며, 적용 결과물을 재배포하지 마세요.
- 번역·패치 사용에 따른 손상이나 진행 문제에 대해 보증하지 않습니다.

## 실제 확인한 외부 자료

- [한식구 카페 — 「[폰트] 7x11 길체」](https://cafe.naver.com/hansicgu/824):
  실제 사용한 GILCHE 글꼴의 출처입니다(작성자 에슘, 2008-11-22). 게시글 첨부파일과
  저장소의 `gilche-1bpp-8x16.fnt`가 일치합니다.
- [Data Crystal — Robotrek](https://datacrystal.tcrf.net/wiki/Robotrek): 영문판의
  무헤더·HiROM·1.5 MiB·FastROM 형식을 대조하는 데 사용했습니다.
- [Data Crystal — Robotrek ROM map](https://datacrystal.tcrf.net/wiki/Robotrek/ROM_map):
  ROM 주소 범위를 확인하는 기술 참고 자료입니다.
- [SuperFamicom.org — Slap Stick](https://superfamicom.org/info/slap-stick):
  Robotrek/Slap Stick 명칭과 USA 원본의 크기·내부 타이틀·SHA-256을 교차 확인하는 데 사용했습니다.
- [GBA-SRW-J](https://github.com/snake7594/GBA-SRW-J): 패치 적용 절차와 ROM 미포함·법적 고지의
  문서 구성만 참고했습니다. 코드·번역·폰트·게임 자료는 사용하지 않았습니다.

위 링크의 코드나 게임 데이터를 패치에 복사한 것은 아니며, 확인한 ROM 구조·식별 정보만 문서와
검증 기준에 반영했습니다.

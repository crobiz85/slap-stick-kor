# Robotrek 한국어 패치

SNES 영문판 `Robotrek (USA)`를 기준으로 작업하는 한국어 패치 프로젝트입니다.

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

ROM 확장을 지원하는 IPS 패처로 `robotrek-korean-v0.1.9-alpha.ips`를 무헤더 영문판 원본에 적용합니다.
원본 해시가 위 값과 다르면 적용하지 마세요.

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

## v0.1.9-alpha 핵심 수정

- 쥐 상점 대사 시작에 문자로 들어간 `[BOTTOM]`을 실제 `D8` 창 명령으로 수정
- 직접 화면 패치의 `[TOP2]`를 실제 `D9` 창 명령으로 수정하고 재발 검증 추가
- 쥐 상점 강화 결과의 내부 `D3` 대상 주소 보존
- 경관 체포 대사의 별도 `DB` 진입점 복원
- 전투 후 성장·레벨 상승 결과 화면 및 후반부 진행 대사 보강
- 이벤트 제어 코드와 고정 재진입 주소에 대한 정적 검증 추가

## 라이선스와 배포 원칙

- 게임 ROM은 저작권자의 저작물이며 이 저장소에서 제공하지 않습니다.
- 공개 배포물은 원본 ROM이 있어야 사용할 수 있는 IPS 차이 패치뿐입니다.
- 개인 소유 원본에서 생성한 완성 ROM을 공개 저장소나 릴리스에 올리지 마세요.

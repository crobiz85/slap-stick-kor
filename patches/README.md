# Slap Stick 한국어 프리뷰 패치

`slap-stick-kor-preview.bps` 또는 `slap-stick-kor-preview.ips`를 깨끗한 무헤더 일본판 ROM에 적용합니다.

- 원본 ROM SHA-256: `08144EA1CE3CF6AB107837278D308E4E859574A047A2EE8EB456F7900AD4BE21`
- 패치 대상 크기: 1,572,864 bytes
- 포함: 대화용 `0x82xx` 미사용 슬롯의 132자 한글 폰트, 초안 ID `0002`~`0012`, `0058`~`0063` 17개
- 초반 메뉴·이벤트 11개는 원래 슬롯에 맞춘 압축형 프리뷰 문구이며, 자연스러운 전체 문구는 후속 재배치 대상
- 패치 파일은 원본 ROM을 포함하지 않으며, 적용 후 결과물은 에뮬레이터에서 직접 확인해야 합니다.

재생성:

```powershell
$py = 'C:\Users\crobi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py scripts/build_korean_preview_patch.py
```

# 배경음악(BGM) 가이드

모든 에피소드는 BGM을 넣는다. 음원은 `bgm/` 공용 라이브러리에서 고르고, 맞는 곡이 없으면 아래 오픈 소스 사이트에서 찾아서 라이브러리에 등록한 뒤 쓴다.

## 찾는 곳 (우선순위)

| 순위 | 사이트 | 라이선스 | 출처 표기 |
|---|---|---|---|
| 1 | Pixabay Music (pixabay.com/music) | Pixabay Content License | 불필요 |
| 2 | OpenGameArt (opengameart.org) 중 **CC0** 곡 | CC0 | 불필요 |
| 3 | Incompetech (incompetech.com, Kevin MacLeod) | CC BY 4.0 | **필수** |
| 4 | Free Music Archive (freemusicarchive.org) 중 **CC0 / CC BY** 곡 | 곡마다 다름 | CC BY면 필수 |

## 라이선스 규칙

- **허용**: CC0, CC BY, Pixabay Content License
- **금지**: NC(비영리) 포함 라이선스 — 수익 창출 채널에서 쓸 수 없음
- **금지**: ND(변경 금지) 포함 라이선스 — 길이 자르기·페이드가 변경에 해당할 수 있음
- **금지**: 라이선스가 명확하지 않은 곡, 유튜브에서 추출한 음원, 유명 곡 리믹스
- CC BY 곡을 쓰면 해당 에피소드 `upload.md` 설명란에 출처 표기를 반드시 넣는다
  - 형식: `Music: "<곡명>" by <아티스트> (<출처 URL>) / Licensed under CC BY 4.0`
- 받은 곡의 라이선스 페이지 URL을 `bgm/library.json`에 기록한다 (저작권 클레임 대응용)

## 이 포맷에 맞는 분위기

- 4지선다 패션/라이프스타일 질문형: **트렌디하고 그루비한 비트**
  - 키워드: `fashion`, `groove`, `funk`, `house`, `chill hop`, `upbeat`, `catwalk`, `sexy`
  - BPM 110~128, 보컬 없는 곡
- 첫 1초 안에 비트가 들어오는 구간이 있어야 한다 (훅과 같이 터지도록)
- 무서운·슬픈·서사적인 곡, 가사 있는 곡은 제외

## 편집 규칙

- 영상 길이(10~12초)에 맞게 자른다. `config.json`의 `bgm.start`(초)부터 사용
  - 시작점은 비트가 바로 들어오는 지점으로 잡는다 (인트로 무음·빌드업 건너뛰기)
- 페이드 인 0.1초, 페이드 아웃 0.3초 (루프 때 끊기는 느낌 최소화)
- 음량
  - TTS 없음: BGM이 메인 → 통합 음량 약 -14 LUFS로 정규화
  - TTS 있음: BGM을 -18dB 수준으로 낮추고 음성 구간은 사이드체인 덕킹

## 라이브러리 등록

새 곡을 받으면:
1. `bgm/<track-id>.mp3`로 저장 (track-id는 영문 소문자-하이픈)
2. `bgm/library.json`에 항목 추가 (스키마는 파일 안 예시 참고)
3. 오디오 파일 자체는 git에 올리지 않는다 (재배포 조건이 곡마다 달라서). `source_url`로 다시 받을 수 있게만 기록한다.

## 로컬 Claude Code에 붙여 넣을 BGM 찾기 명령

```
docs/bgm-guide.md 규칙대로 episodes/<에피소드명>/config.json의 bgm.mood에 맞는 배경음악 후보 3곡을 찾아줘.
- 우선순위: Pixabay Music → OpenGameArt CC0 → Incompetech → FMA (CC0/CC BY만)
- NC·ND 라이선스, 라이선스 불명확한 곡, 보컬 있는 곡은 제외
- 각 후보마다 곡명, 아티스트, 출처 URL, 라이선스, BPM, 비트가 바로 들어오는 추천 시작 지점(초)을 표로 보여줘
- 내가 고르면 bgm/<track-id>.mp3로 받고, bgm/library.json에 등록하고, config.json의 bgm.track과 bgm.start를 채워줘
- CC BY 곡이면 upload.md 설명란 맨 아래에 출처 표기를 추가해줘
- 사이트에서 직접 다운로드가 막히면 다운로드 링크만 알려줘. 내가 받아서 bgm/에 넣을게
```

# poll-shorts

"결혼식 하객룩으로 제일 별로인 건?" 같은 **4지선다 질문형 쇼츠**를 만드는 레포.
정답을 공개하지 않고 댓글로 번호를 받는 구조라서, 정답이 하나로 갈리지 않는 선택지 구성이 핵심이다.

## 영상 구조 (10~12초, 루프)

| 구간 | 화면 |
|---|---|
| 0~1.5s | 훅: `hook_image` 번호 이미지를 블러로 깔고 질문 표시 (블러 25px → 8px) |
| 1.5~7s | 선택지 1~4를 한 장씩 풀스크린, 각 1.3초, 1.00 → 1.06 줌인 |
| 7~11s | 2×2 그리드 + 질문 + CTA |
| 끝 | 마지막 0.2초 컷 → 첫 장면으로 루프 |

## 폴더 구조

```
poll-shorts/
├── CLAUDE.md                  # 로컬 Claude Code 작업 규칙 (필수 규칙 모음)
├── README.md
├── docs/
│   ├── build-prompt.md        # 렌더 파이프라인을 처음 만들 때 Claude Code에 넣을 명령
│   ├── image-prompt-guide.md  # ChatGPT 이미지 생성 규칙
│   └── bgm-guide.md           # 배경음악 찾는 곳·라이선스 규칙·편집 규칙
├── bgm/                       # 공용 BGM 라이브러리 (library.json에 출처 기록, 오디오는 git 제외)
├── episodes/
│   ├── _template/             # 새 에피소드 만들 때 복사
│   │   ├── config.json
│   │   ├── prompts.md
│   │   ├── upload.md
│   │   └── assets/
│   └── wedding-guest-women/   # 1편: 여자 하객룩
│       ├── config.json        # 질문·선택지·CTA·훅 이미지
│       ├── prompts.md         # 선택지별 ChatGPT 이미지 프롬프트
│       ├── upload.md          # 쇼츠 제목·설명
│       ├── assets/            # 01.png~04.png (직접 넣기), 선택: 01.mp4~04.mp4, tts.wav
│       └── out/               # 렌더 결과 (git 제외)
└── src/                       # 렌더 파이프라인 코드 (build-prompt.md로 생성)
```

## 작업 순서

1. `episodes/<에피소드>/prompts.md`의 프롬프트로 ChatGPT에서 이미지 4장 생성
2. `assets/01.png`~`04.png`로 저장 (4:5 비율)
3. BGM: `config.json`의 `bgm.track`이 비어 있으면 `docs/bgm-guide.md`의 명령으로 오픈 소스 음원 후보를 찾아 고르기
4. 파이프라인이 없으면 `docs/build-prompt.md` 내용을 로컬 Claude Code에 붙여 넣기
5. 렌더 → `out/final.mp4` + 검증 프레임 확인
6. `upload.md`의 제목·설명으로 업로드

## 에피소드 목록

| # | 폴더 | 질문 | 상태 |
|---|---|---|---|
| 1 | `wedding-guest-women` | 결혼식 하객룩으로 제일 선 넘은 건? | 이미지 생성 대기 |

## 다음 주제 후보

- 소개팅룩으로 제일 선 넘은 건?
- 소개팅 첫 만남 최악의 메뉴? (곱창 / 마라탕 / 간장게장 / 오마카세 더치페이)
- 첫 출근룩으로 제일 별로인 건?
- 회식 자리 최악의 동료는?
- 캠핑 같이 가기 싫은 유형은?

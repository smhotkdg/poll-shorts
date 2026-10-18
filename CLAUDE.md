# poll-shorts 작업 규칙

4지선다 질문형 쇼츠 렌더 레포. 전체 구조는 README.md 참고.

## 필수 규칙 (모든 렌더에 적용)

- **정확한 가로 중앙 정렬**: 모든 텍스트·배지·그리드는 화면 가로 중앙에 정렬하고 좌우 여백이 대칭이어야 한다. 렌더 후 프레임을 추출해 좌우 여백 픽셀을 측정해서 대칭인지 검증하고 결과를 출력한다.
- **텍스트 위치**: 화면 맨 위·맨 아래에 붙이지 않는다. 단독 텍스트는 세로 약 40% 지점(중심보다 약간 위). 그리드 화면의 질문은 세로 약 20~25% 지점.
- **자막·라벨 뒤 배경 패널/박스 금지**: 가독성은 외곽선·그림자로만 확보한다.
- **상단 진행 칩/진행 바 금지**: 단계 표시 텍스트를 넣지 않는다.
- 한글 폰트: 굵은 고딕 계열 (Pretendard Bold 또는 Noto Sans KR Black)
- highlight 단어는 빨간색 `#E53935`, 나머지는 흰색 + 검은 외곽선/그림자
- 렌더 후 0.3s / 1.2s / 4.0s / 9.0s 프레임을 png로 `out/frames/`에 저장해서 보여준다.

## 출력 사양

- 1080x1920, 30fps, 10~12초, H.264 + AAC → `episodes/<에피소드>/out/final.mp4`

## 배경음악 (모든 에피소드 필수)

- `config.json`의 `bgm.track`에 적힌 `bgm/<track>.mp3`를 사용한다.
- `bgm.track`이 비어 있거나 파일이 없으면, 렌더 전에 `docs/bgm-guide.md` 규칙대로 오픈 소스(Pixabay Music → OpenGameArt CC0 → Incompetech → FMA CC0/CC BY)에서 `bgm.mood`에 맞는 후보 3곡을 찾아 보여주고 내가 고르게 한다.
- NC·ND·라이선스 불명확 음원은 절대 쓰지 않는다. CC BY 곡은 `upload.md`에 출처 표기를 넣는다.
- 새 곡은 `bgm/library.json`에 등록한다. 오디오 파일은 커밋하지 않는다.
- 음량: TTS 없으면 약 -14 LUFS, TTS 있으면 BGM -18dB + 음성 구간 덕킹. 페이드 인 0.1초 / 아웃 0.3초.

## 입력

- `episodes/<에피소드>/config.json`
- `episodes/<에피소드>/assets/01.png`~`04.png` (4:5). `01.mp4`~`04.mp4`가 있으면 영상 클립 우선
- `bgm/<track>.mp3` (config의 `bgm.track`)
- 선택: `assets/tts.wav`

## 에피소드 산출물

새 에피소드를 만들 때는 `episodes/_template/`을 복사하고, 렌더와 함께 `upload.md`에 쇼츠 제목 후보와 재미있는 설명 텍스트를 꼭 채운다.

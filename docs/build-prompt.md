# 렌더 파이프라인 생성 명령

`src/`가 비어 있을 때 아래 내용을 로컬 Claude Code에 그대로 붙여 넣는다.

```
이 레포(poll-shorts)의 CLAUDE.md와 README.md를 읽고, src/ 폴더에 "4지선다 투표형 쇼츠" 자동 합성 파이프라인을 만들어줘.
실행: python src/render.py episodes/<에피소드명>

[입력]
- episodes/<에피소드명>/config.json (스키마는 episodes/_template/config.json 참고)
- episodes/<에피소드명>/assets/01.png~04.png (4:5). 01.mp4~04.mp4가 있으면 영상 클립 우선 사용
- 선택: tts.wav, bgm.mp3 (BGM은 -18dB 정도로 작게)

[출력] 1080x1920, 30fps, 총 10~12초, H.264 → episodes/<에피소드명>/out/final.mp4

[구성]
1) 0~1.5s 훅: hook_image 번호 이미지를 풀스크린으로 깔고 가우시안 블러 25px로 시작, 0.5s~1.5s 동안 블러 25→8로 서서히 감소. 질문 텍스트는 세로 약 40% 지점(중심보다 약간 위). highlight 단어는 빨간색(#E53935), 나머지는 흰색 + 검은 외곽선/그림자. hook_image가 없으면 질문만 표시
2) 1.5~7s: 선택지 1~4를 한 장씩 풀스크린으로 각 1.3초, 1.00→1.06 천천히 줌인. 번호 원형 배지(config의 badge_colors)와 라벨을 중심보다 약간 위에 표시
3) 7~11s: 2x2 그리드. 셀 간격 균일, 그리드 위에 질문(세로 약 20~25% 지점, 맨 위에 붙이지 말 것), 그리드 아래에 cta. 각 셀 하단에 번호 배지 + 라벨
4) 마지막 0.2초는 컷 처리해서 첫 장면으로 자연스럽게 루프
타이밍 값은 config의 timing을 따른다.

[필수 규칙]
- 모든 텍스트·배지·그리드는 정확히 가로 중앙 정렬. 렌더 후 프레임을 추출해 좌우 여백 픽셀을 측정해서 대칭인지 검증하고 결과 출력
- 자막·라벨 뒤 배경 패널/박스 금지 (외곽선·그림자만)
- 상단 진행 칩/진행 바 금지
- 한글 폰트는 굵은 고딕 계열(Pretendard Bold 또는 Noto Sans KR Black)
- 렌더 후 0.3s / 1.2s / 4.0s / 9.0s 프레임을 out/frames/에 png로 저장해서 보여줄 것

먼저 episodes/wedding-guest-women으로 렌더해서 결과를 보여줘.
```

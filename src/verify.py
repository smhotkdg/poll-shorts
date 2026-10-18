"""렌더 결과 검증.

실행: python src/verify.py episodes/<에피소드명>

final.mp4에서 검증 시점 프레임을 다시 뽑아, 같은 시점의 배경만 있는 프레임(_bg_*.png)과 비교해
텍스트·배지 픽셀만 분리한 뒤 좌우/상하 여백을 측정한다. 그리드는 셀 없는 배경판(_plate_*.png) 대비로 측정한다.
좌우 차이가 TOL_PX를 넘거나 규칙 위반이 있으면 종료 코드 1.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

TOL_PX = 2
EDGE_MIN = 0.05  # 화면 위·아래 5% 안쪽에 붙으면 위반


def extract_frame(video, n, w, h):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"select=eq(n\\,{n})", "-vframes", "1",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(int)


def ink_extent(mask, min_count=3):
    cols = np.where(mask.sum(axis=0) >= min_count)[0]
    rows = np.where(mask.sum(axis=1) >= min_count)[0]
    if not len(cols) or not len(rows):
        return None
    return cols[0], cols[-1], rows[0], rows[-1]


def has_box(mask, ext, patch=10):
    """bbox 네 모서리가 모두 꽉 차 있으면 배경 박스로 판단."""
    x0, x1, y0, y1 = ext
    corners = [mask[y0:y0 + patch, x0:x0 + patch], mask[y0:y0 + patch, x1 - patch + 1:x1 + 1],
               mask[y1 - patch + 1:y1 + 1, x0:x0 + patch], mask[y1 - patch + 1:y1 + 1, x1 - patch + 1:x1 + 1]]
    return sum(c.mean() > 0.8 for c in corners) >= 3


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ep = Path(sys.argv[1]).resolve()
    out = ep / "out"
    video = out / "final.mp4"
    if len(sys.argv) > 2:
        video = Path(sys.argv[2]).resolve()
    meta = json.loads((out / "frames" / "layout.json").read_text(encoding="utf-8"))
    W, H, FPS = meta["width"], meta["height"], meta["fps"]
    ok = True
    rows = []

    for key, elems in meta["frames"].items():
        n = round(float(key) * FPS)
        frame = extract_frame(video, n, W, H)
        bg = np.asarray(Image.open(out / "frames" / f"_bg_{key}s.png").convert("RGB")).astype(int)
        # 눈에 보이는 잉크 = 배경보다 밝아진 글자·링 픽셀 + 거의 검정인 외곽선 픽셀.
        # 부드러운 그림자는 배경을 일부만 어둡게 해서 배경 밝기에 따라 번짐 폭이 달라지므로 제외
        fmax, bmax = frame.max(axis=2), bg.max(axis=2)
        diff = ((frame - bg).max(axis=2) > 60) | ((fmax < 45) & (fmax <= bmax * 0.35))

        # 상단 진행 칩/바 검사: 위 8% 띠에 오버레이 픽셀이 있으면 안 됨
        top_band = diff[: int(H * 0.08)].sum()
        if top_band > 50:
            ok = False
            print(f"[{key}s] 위반: 상단 8% 영역에 오버레이 픽셀 {top_band}개 (진행 칩/바 의심)")

        cells = {e["name"]: e for e in elems if e.get("kind") == "grid"}
        for e in elems:
            if e.get("kind") == "grid":
                continue
            # 요소 레이어는 잉크 기준으로 잘려 있으므로 자기 영역 + 인코딩 번짐 여유만 본다
            pad = 4
            y0, y1 = max(0, e["y0"] - pad), min(H, e["y1"] + pad)
            if e["name"].startswith("cell_tag_"):
                cell = cells["cell_" + e["name"].split("_")[-1]]
                x0, x1 = cell["x0"], cell["x1"]
            else:
                x0, x1 = 0, W
            sub = diff[y0:y1, x0:x1]
            ext = ink_extent(sub)
            if ext is None:
                ok = False
                rows.append((key, e["name"], "-", "-", "-", "-", "-", "미검출", "FAIL"))
                continue
            l, r = ext[0], (x1 - x0 - 1) - ext[1]
            top, bottom = y0 + ext[2], H - 1 - (y0 + ext[3])
            box = has_box(sub, ext)
            ref = "셀 기준" if x0 else "화면 기준"
            edge_ok = top >= H * EDGE_MIN and bottom >= H * EDGE_MIN
            good = abs(l - r) <= TOL_PX and edge_ok and not box
            ok &= good
            rows.append((key, e["name"], l, r, abs(l - r), top, bottom,
                         f"{ref}, 박스{'있음' if box else '없음'}", "OK" if good else "FAIL"))

        # 그리드: 단색 배경 대비 측정 + 셀 간격 균일성
        if cells:
            plate = np.asarray(Image.open(out / "frames" / f"_plate_{key}s.png").convert("RGB")).astype(int)
            g = np.abs(frame - plate).max(axis=2) > 50  # 셀 그림자(옅은 어두워짐)는 제외
            gy0 = min(c["y0"] for c in cells.values())
            gy1 = max(c["y1"] for c in cells.values())
            band = g[gy0:gy1]
            ext = ink_extent(band, min_count=20)
            l, r = ext[0], W - 1 - ext[1]
            colfill = band.sum(axis=0) >= 20
            gap_cols = np.where(~colfill[ext[0]:ext[1] + 1])[0]
            rowfill = g[:, ext[0]:ext[1] + 1].sum(axis=1) >= 20
            gap_rows = np.where(~rowfill[gy0:gy1])[0]
            good = abs(l - r) <= TOL_PX
            ok &= good
            rows.append((key, "grid(2x2)", l, r, abs(l - r), gy0, H - gy1,
                         f"가로 간격 {len(gap_cols)}px / 세로 간격 {len(gap_rows)}px", "OK" if good else "FAIL"))
            # 행별 라벨 쌍: 왼쪽 라벨의 왼쪽 여백 vs 오른쪽 라벨의 오른쪽 여백 (화면 기준)
            for row_i in (0, 1):
                a, b = f"cell_tag_{row_i * 2 + 1}", f"cell_tag_{row_i * 2 + 2}"
                ea = next(x for x in elems if x["name"] == a)
                eb = next(x for x in elems if x["name"] == b)
                ya, yb = max(0, ea["y0"] - 24), min(H, ea["y1"] + 24)
                exa = ink_extent(diff[ya:yb, :W // 2])
                exb = ink_extent(diff[ya:yb, W // 2:])
                l2, r2 = exa[0], W - 1 - (W // 2 + exb[1])
                rows.append((key, f"라벨 행{row_i + 1} ({a}↔{b})", l2, r2, abs(l2 - r2), "-", "-",
                             "화면 기준, 라벨 길이 달라 참고값", "참고"))

    print("\n| 프레임 | 요소 | 왼쪽 여백 | 오른쪽 여백 | 차이 | 위 여백 | 아래 여백 | 비고 | 판정 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")

    # ---- ffprobe
    pr = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels"
         ":format=duration", "-of", "json", str(video)], capture_output=True, text=True, check=True).stdout)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    a = next((s for s in pr["streams"] if s["codec_type"] == "audio"), None)
    dur = float(pr["format"]["duration"])
    num, den = map(int, v["r_frame_rate"].split("/"))
    fps = num / den
    print("\n[ffprobe]")
    print(f"- 비디오: {v['codec_name']} {v['width']}x{v['height']} @ {fps:g}fps")
    print(f"- 오디오: {a['codec_name']} {a['sample_rate']}Hz {a['channels']}ch" if a else "- 오디오: 없음")
    print(f"- 길이: {dur:.3f}s")
    # 길이는 config 타이밍으로 계산된 설계 길이와 비교. 기본 사양(10~12초) 밖이면 경고만 낸다
    spec_ok = (v["codec_name"] == "h264" and (v["width"], v["height"]) == (1080, 1920) and abs(fps - 30) < 0.01
               and abs(dur - meta["duration"]) <= 0.05 and a is not None and a["codec_name"] == "aac")
    ok &= spec_ok
    print(f"- 사양(1080x1920, 30fps, 설계 길이 {meta['duration']:.1f}s, H.264+AAC): {'OK' if spec_ok else 'FAIL'}")
    if not 10 <= dur <= 12:
        print(f"- 경고: 길이 {dur:.1f}s가 기본 사양 10~12초 밖입니다 (config timing 의도 확인)")

    if a:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-af", "ebur128=peak=true",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
        summary = r[r.rindex("Summary:"):]
        lufs = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1))
        tp = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
        lufs_ok = abs(lufs - (-14)) <= 1.0
        ok &= lufs_ok
        print(f"\n[음량] 통합 {lufs:.1f} LUFS (목표 -14±1), True Peak {tp.group(1) if tp else '?'} dBFS → "
              f"{'OK' if lufs_ok else 'FAIL'}")

        # 모노 다운믹스는 피크를 부풀리므로 채널별 절댓값 최대로 본다
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "f32le", "-ac", "2", "-ar", "48000", "-"],
                             capture_output=True, check=True).stdout
        st = np.frombuffer(raw, np.float32).reshape(-1, 2)
        s = st[np.arange(len(st)), np.abs(st).argmax(axis=1)]
        win = 480  # 10ms

        def db(x):
            return 20 * np.log10(max(np.abs(x).max(), 1e-9))

        head, tail = db(s[:win]), db(s[-win:])
        jump = abs(float(s[-1]) - float(s[0]))
        body = db(s)
        seam_ok = head < body - 20 and tail < body - 20 and jump < 0.01
        ok &= seam_ok
        print(f"[루프 지점] 끝 10ms 피크 {tail:.1f} dBFS, 처음 10ms 피크 {head:.1f} dBFS, "
              f"전체 피크 {body:.1f} dBFS, 끝→처음 샘플 차이 {jump:.4f} → {'튐 없음' if seam_ok else '튈 수 있음'}")

    print(f"\n종합: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

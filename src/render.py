"""4지선다 질문형 쇼츠 렌더러.

실행: python src/render.py episodes/<에피소드명> [--no-bgm]

- 합성은 Pillow로 프레임을 만들고 ffmpeg(libx264)로 파이프 인코딩한다.
- 검증용으로 out/frames/에 0.3/1.2/4.0/9.0초 프레임, 같은 시점의 배경만 있는 프레임(_bg_*.png), 그리드 시점의 셀 없는 배경판(_plate_*.png),
  요소별 위치 정보(layout.json)를 함께 저장한다. 실제 측정은 src/verify.py가 final.mp4에서 한다.
"""
import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
ROOT = Path(__file__).resolve().parent.parent
FRAME_TIMES = [0.3, 1.2, 4.0, 9.0]

FONT_PATHS = [
    "C:/Windows/Fonts/Pretendard-Bold.ttf",
    "C:/Windows/Fonts/Pretendard-Bold.otf",
    "C:/Windows/Fonts/NotoSansKR-Black.ttf",
    "C:/Windows/Fonts/NotoSansKR-Black.otf",
    "C:/Windows/Fonts/NotoSansKR-VF.ttf",  # 가변 폰트 → Weight 900(Black)으로 설정
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
]
EMOJI_FONT_PATHS = ["C:/Windows/Fonts/seguiemj.ttf", "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"]

GRID_BG = (17, 17, 19)
WHITE = (255, 255, 255)


# ---------------------------------------------------------------- 폰트 / 텍스트

_font_cache = {}


def font(size, weight=900):
    key = ("ko", size, weight)
    if key not in _font_cache:
        for p in FONT_PATHS:
            if Path(p).exists():
                f = ImageFont.truetype(p, size)
                if p.endswith("-VF.ttf"):
                    f.set_variation_by_axes([weight])
                _font_cache[key] = f
                break
        else:
            sys.exit("한글 굵은 고딕 폰트(Pretendard Bold / Noto Sans KR Black)를 찾을 수 없습니다.")
    return _font_cache[key]


def emoji_font(size):
    key = ("emoji", size)
    if key not in _font_cache:
        p = next((p for p in EMOJI_FONT_PATHS if Path(p).exists()), None)
        _font_cache[key] = ImageFont.truetype(p, size) if p else None
    return _font_cache[key]


def is_emoji(ch):
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or o in (0xFE0F, 0x200D)


def split_runs(text, color):
    """텍스트를 (문자열, 색, 이모지 여부) 런으로 나눈다."""
    runs = []
    for ch in text:
        emo = is_emoji(ch)
        if runs and runs[-1][2] == emo:
            runs[-1][0] += ch
        else:
            runs.append([ch, color, emo])
    return runs


def text_layer(segments, size):
    """segments: [(text, color)] 한 줄. 흰 글자 + 검은 외곽선 + 그림자, 배경 박스 없음.
    잉크(실제 픽셀) 기준으로 잘라낸 RGBA 레이어를 돌려준다."""
    f = font(size)
    ef = emoji_font(int(size * 0.9))
    stroke = max(2, round(size * 0.04))  # 얇은 외곽선 + 넓은 그림자로 가독성 확보
    runs = [r for text, color in segments for r in split_runs(text, color)]

    def run_font(r):
        return ef if (r[2] and ef) else f

    width = sum(run_font(r).getlength(r[0]) for r in runs)
    pad = stroke + 40
    cw, ch = int(width + pad * 2), int(size * 1.6 + pad * 2)
    base_y = pad + int(size * 1.15)

    def draw_runs(img, shadow):
        d = ImageDraw.Draw(img)
        x = pad
        for r in runs:
            rf = run_font(r)
            if r[2] and ef:
                # 이모지도 글자와 같은 두께의 검은 외곽선을 둘러야 좌우 시각 중심이 맞는다
                d.text((x, base_y), r[0], font=rf, anchor="ls", fill=(0, 0, 0, 255),
                       stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
                if not shadow:
                    d.text((x, base_y), r[0], font=rf, anchor="ls", embedded_color=True)
            else:
                fill = (0, 0, 0, 255) if shadow else r[1]
                d.text((x, base_y), r[0], font=rf, anchor="ls", fill=fill,
                       stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
            x += rf.getlength(r[0])

    shadow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    draw_runs(shadow, True)
    alpha = shadow.getchannel("A").filter(ImageFilter.GaussianBlur(size * 0.14)).point(lambda v: min(255, int(v * 0.9)))
    shadow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    shadow.putalpha(alpha)
    layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    layer.alpha_composite(shadow, (0, round(size * 0.04)))  # 세로로만 오프셋 → 좌우 대칭 유지
    draw_runs(layer, False)
    return crop_ink(layer)


def crop_ink(layer, threshold=12):
    bbox = layer.getchannel("A").point(lambda v: 255 if v > threshold else 0).getbbox()
    return layer.crop(bbox) if bbox else layer


def colorize(text, highlight, hl_color):
    """한 줄 텍스트를 highlight 부분만 빨간색인 segments로."""
    if highlight and highlight in text:
        i = text.index(highlight)
        segs = [(text[:i], WHITE), (highlight, hl_color), (text[i + len(highlight):], WHITE)]
        return [s for s in segs if s[0]]
    return [(text, WHITE)]


def wrap_question(text, highlight, size, max_w):
    """강조 구간 앞에서 끊을 수 있으면 우선 끊고, 아니면 단어 단위 greedy 줄바꿈."""
    f = font(size)
    if f.getlength(text) <= max_w:
        return [text]
    if highlight and highlight in text:
        i = text.index(highlight)
        a, b = text[:i].strip(), text[i:].strip()
        if a and f.getlength(a) <= max_w and f.getlength(b) <= max_w:
            return [a, b]
    lines, cur = [], ""
    for word in text.split(" "):
        cand = (cur + " " + word).strip()
        if cur and f.getlength(cand) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    return lines + [cur]


def stack_lines(lines, highlight, hl_color, size, gap):
    """여러 줄을 각 줄 가로 중앙 기준으로 쌓은 레이어."""
    layers = [text_layer(colorize(l, highlight, hl_color), size) for l in lines]
    w = max(l.width for l in layers)
    h = sum(l.height for l in layers) + gap * (len(layers) - 1)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    y = 0
    for l in layers:
        out.alpha_composite(l, ((w - l.width) // 2, y))
        y += l.height + gap
    return out


def hex_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, p):
    return tuple(round(a + (b - a) * p) for a, b in zip(c1, c2))


def badge_layer(no, color, diameter):
    """번호 원형 배지: 위→아래 은은한 그라데이션 + 얇은 흰 링 + 부드러운 그림자, 숫자는 외곽선 없이."""
    ss = 4  # 슈퍼샘플링으로 원 가장자리 매끄럽게
    pad = diameter // 4
    size = diameter + pad * 2
    D, o = diameter * ss, pad * ss
    base = hex_rgb(color)

    # 원 마스크와 세로 그라데이션 채움
    mask = Image.new("L", (size * ss, size * ss), 0)
    ImageDraw.Draw(mask).ellipse([o, o, o + D - 1, o + D - 1], fill=255)
    top, bottom = mix(base, WHITE, 0.22), mix(base, (0, 0, 0), 0.14)
    grad = Image.new("RGB", (1, D))
    grad.putdata([mix(top, bottom, y / (D - 1)) for y in range(D)])
    fill = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    fill.paste(grad.resize((D, D)), (o, o))
    fill.putalpha(mask)

    # 얇은 흰 링
    ring_w = max(2, round(diameter * 0.035)) * ss
    ring = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse([o, o, o + D - 1, o + D - 1], outline=(255, 255, 255, 235), width=ring_w)
    fill.alpha_composite(ring)
    circle = fill.resize((size, size), Image.LANCZOS)

    # 넓고 옅은 그림자 (세로로만 오프셋 → 좌우 대칭 유지)
    shadow_a = circle.getchannel("A").filter(ImageFilter.GaussianBlur(diameter * 0.09)).point(lambda v: int(v * 0.45))
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sh = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sh.putalpha(shadow_a)
    layer.alpha_composite(sh, (0, max(2, round(diameter * 0.05))))
    layer.alpha_composite(circle)

    # 숫자: Bold, 외곽선 없이 옅은 그림자만. 잉크 박스 기준으로 원 중심에 맞춘다
    f = font(int(diameter * 0.5), weight=700)
    txt = Image.new("L", (size, size), 0)
    ImageDraw.Draw(txt).text((size / 2, size / 2), str(no), font=f, anchor="mm", fill=255)
    x0, y0, x1, y1 = txt.getbbox()
    dx, dy = round(size / 2 - (x0 + x1) / 2), round(size / 2 - (y0 + y1) / 2)
    txt = ImageChops.offset(txt, dx, dy)
    num_sh = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    num_sh.putalpha(txt.filter(ImageFilter.GaussianBlur(diameter * 0.03)).point(lambda v: int(v * 0.35)))
    layer.alpha_composite(num_sh, (0, max(1, round(diameter * 0.02))))
    num = Image.new("RGBA", (size, size), WHITE + (0,))
    num.putalpha(txt)
    layer.alpha_composite(num)
    return crop_ink(layer)


def solid_box(layer):
    """그림자 번짐을 뺀, 눈에 보이는 불투명 부분(alpha>200)의 bbox."""
    return layer.getchannel("A").point(lambda v: 255 if v > 200 else 0).getbbox() or (0, 0, *layer.size)


def hstack(a, b, gap):
    """a, b를 눈에 보이는 가장자리 사이 간격이 gap이 되도록 가로로 붙인다 (세로는 보이는 부분 중심 맞춤)."""
    sa, sb = solid_box(a), solid_box(b)
    bx = sa[2] + gap - sb[0]  # b 레이어의 x 위치
    ay = -round((sa[1] + sa[3]) / 2)
    by = -round((sb[1] + sb[3]) / 2)
    x0, y0 = min(0, bx), min(ay, by)
    w = max(a.width, bx + b.width) - x0
    h = max(ay + a.height, by + b.height) - y0
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(a, (-x0, ay - y0))
    out.alpha_composite(b, (bx - x0, by - y0))
    return out


# ---------------------------------------------------------------- 미디어 소스

def cover_box(sw, sh, tw, th, zoom=1.0):
    """소스(sw,sh)를 (tw,th)에 cover로 채우는 중앙 크롭 박스 (zoom>1이면 더 좁게)."""
    scale = max(tw / sw, th / sh) * zoom
    cw, ch = tw / scale, th / scale
    x0, y0 = (sw - cw) / 2, (sh - ch) / 2
    return (x0, y0, x0 + cw, y0 + ch)


class Source:
    """이미지 또는 영상 클립(01.mp4 등). 영상이면 프레임 인덱스로 접근, 끝나면 루프."""

    def __init__(self, image_path):
        clip = image_path.with_suffix(".mp4")
        self.frames = None
        if clip.exists():
            self.frames = self._read_clip(clip)
            self.image = self.frames[0]
        else:
            self.image = Image.open(image_path).convert("RGB")

    @staticmethod
    def _read_clip(path, max_seconds=4.5):
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
        sw, sh = map(int, probe.stdout.strip().split(",")[:2])
        # 메모리 절약: 세로 1920 기준으로 축소해 읽는다
        scale = min(1.0, 1920 / sh)
        rw, rh = int(sw * scale) // 2 * 2, int(sh * scale) // 2 * 2
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-t", str(max_seconds), "-vf", f"fps={FPS},scale={rw}:{rh}",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        n = len(raw) // (rw * rh * 3)
        return [Image.frombytes("RGB", (rw, rh), raw[i * rw * rh * 3:(i + 1) * rw * rh * 3]) for i in range(n)]

    def get(self, idx=0):
        return self.frames[idx % len(self.frames)] if self.frames else self.image

    def render(self, tw, th, zoom=1.0, idx=0):
        img = self.get(idx)
        return img.resize((tw, th), Image.LANCZOS, box=cover_box(img.width, img.height, tw, th, zoom))


# ---------------------------------------------------------------- 장면 구성

class Scene:
    def __init__(self, ep_dir, cfg):
        self.cfg = cfg
        t = cfg["timing"]
        self.t = t
        self.sources = [Source(ep_dir / c["image"]) for c in cfg["choices"]]
        hl_color = cfg.get("highlight_color", "#E53935")
        layout = cfg.get("layout", {})
        self.single_y = layout.get("single_text_y", 0.4)
        self.grid_q_y = layout.get("grid_question_y", 0.22)

        q, hl = cfg["question"], cfg.get("highlight")
        self.hook_q = stack_lines(wrap_question(q, hl, 96, 940), hl, hl_color, 96, 14)
        self.grid_q = stack_lines(wrap_question(q, hl, 80, 940), hl, hl_color, 80, 10)
        self.cta = text_layer([(cfg["cta"], WHITE)], 72)

        colors = cfg["badge_colors"]
        self.big_badges = [badge_layer(c["no"], colors[i % len(colors)], 132) for i, c in enumerate(cfg["choices"])]
        self.big_labels = [text_layer([(c["label"], WHITE)], 96) for c in cfg["choices"]]
        self.cell_tags = [hstack(badge_layer(c["no"], colors[i % len(colors)], 64),
                                 text_layer([(c["label"], WHITE)], 50), 12)
                          for i, c in enumerate(cfg["choices"])]

        # 그리드 배치: 질문(세로 grid_question_y) → 2x2(셀 4:5, 간격 균일) → CTA 묶음이
        # 화면 세로 중앙에 오도록, 질문 위 여백 = CTA 아래 여백이 되게 셀 크기를 계산한다
        self.gap, inner = 16, 34
        sq, sc = solid_box(self.grid_q), solid_box(self.cta)
        qh, ch = sq[3] - sq[1], sc[3] - sc[1]
        q_cy = H * self.grid_q_y
        margin = q_cy - qh / 2
        q_bottom = q_cy + qh / 2
        grid_h = (H - margin) - ch - inner - q_bottom - inner
        self.cell_h = int((grid_h - self.gap) // 2)
        self.cell_w = round(self.cell_h * 0.8)
        slack = grid_h - (self.cell_h * 2 + self.gap)  # 반올림 잔여는 위아래 간격에 나눠 준다
        grid_w = self.cell_w * 2 + self.gap
        self.grid_x = (W - grid_w) // 2
        self.grid_y = round(q_bottom + inner + slack / 2)
        grid_bottom = self.grid_y + self.cell_h * 2 + self.gap
        self.cta_cy = grid_bottom + inner + slack / 2 + ch / 2
        self.cell_mask = self._rounded_mask(self.cell_w, self.cell_h, 28)
        self.cell_frame = self._cell_frame()

        hook = cfg.get("hook_image")
        self.hook_src = self.sources[hook - 1] if hook else None
        self.grid_plate = self._grid_plate()

        self.t_choices = t["hook"]
        self.t_grid = t["hook"] + t["per_choice"] * len(self.sources)
        self.t_cut = self.t_grid + t["grid"]
        self.duration = self.t_cut + t["loop_cut"]

    @staticmethod
    def _rounded_mask(w, h, r):
        ss = 4
        m = Image.new("L", (w * ss, h * ss), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], r * ss, fill=255)
        return m.resize((w, h), Image.LANCZOS)

    def _cell_frame(self):
        """셀 아래 부드러운 그림자 + 셀 둘레 얇은 반투명 흰 선 (셀 위치 기준 오프셋 pad)."""
        pad = 40
        w, h = self.cell_w + pad * 2, self.cell_h + pad * 2
        shadow = Image.new("L", (w, h), 0)
        shadow.paste(self.cell_mask, (pad, pad))
        shadow = shadow.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.55))
        under = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        under.putalpha(shadow)
        ss = 4
        line = Image.new("L", (self.cell_w * ss, self.cell_h * ss), 0)
        ImageDraw.Draw(line).rounded_rectangle([0, 0, self.cell_w * ss - 1, self.cell_h * ss - 1], 28 * ss,
                                               outline=255, width=2 * ss)
        over = Image.new("RGBA", (self.cell_w, self.cell_h), WHITE + (0,))
        over.putalpha(line.resize((self.cell_w, self.cell_h), Image.LANCZOS).point(lambda v: int(v * 0.35)))
        return pad, under, over

    def _grid_plate(self):
        """그리드 배경: 훅 이미지를 크게 블러 + 어둡게 (없으면 단색)."""
        if self.hook_src is None:
            return Image.new("RGBA", (W, H), GRID_BG + (255,))
        img = self.hook_src.render(W, H, 1.15).filter(ImageFilter.GaussianBlur(45))
        dark = Image.new("RGB", (W, H), GRID_BG)
        return Image.blend(img, dark, 0.68).convert("RGBA")

    @staticmethod
    def place(canvas, layer, cx, cy, name, layout):
        """layer의 눈에 보이는 부분 중심을 (cx, cy)에 정확히 놓는다 (그림자 번짐은 기준에서 제외)."""
        sx0, sy0, sx1, sy1 = solid_box(layer)
        x = round(cx - (sx0 + sx1) / 2)
        y = round(cy - (sy0 + sy1) / 2)
        canvas.alpha_composite(layer, (x, y))
        layout.append({"name": name, "x0": x, "y0": y, "x1": x + layer.width, "y1": y + layer.height})

    def frame(self, t, with_overlay=True, with_cells=True):
        """시각 t의 프레임과 요소 배치 정보를 만든다.
        with_overlay=False: 텍스트·배지 제외 (검증용 배경), with_cells=False: 그리드 셀까지 제외."""
        layout = []
        T = self.t
        if t >= self.t_cut:
            t = 0.0  # 루프 컷: 마지막 0.2초는 첫 장면으로 끊어 붙인다
        if t < self.t_choices:
            bg = self._hook_bg(t)
            canvas = bg.convert("RGBA")
            if with_overlay:
                self.place(canvas, self.hook_q, W / 2, H * self.single_y, "hook_question", layout)
        elif t < self.t_grid:
            i = min(int((t - self.t_choices) / T["per_choice"]), len(self.sources) - 1)
            local = t - self.t_choices - i * T["per_choice"]
            p = local / T["per_choice"]
            zoom = T["zoom_from"] + (T["zoom_to"] - T["zoom_from"]) * p
            canvas = self.sources[i].render(W, H, zoom, int(local * FPS)).convert("RGBA")
            if with_overlay:
                cy = H * self.single_y
                self.place(canvas, self.big_badges[i], W / 2, cy - 100, f"badge_{i + 1}", layout)
                self.place(canvas, self.big_labels[i], W / 2, cy + 50, f"label_{i + 1}", layout)
        else:
            local = t - self.t_grid
            canvas = self.grid_plate.copy()
            pad, under, over = self.cell_frame
            for i, src in enumerate(self.sources):
                r, c = divmod(i, 2)
                x = self.grid_x + c * (self.cell_w + self.gap)
                y = self.grid_y + r * (self.cell_h + self.gap)
                layout.append({"name": f"cell_{i + 1}", "x0": x, "y0": y,
                               "x1": x + self.cell_w, "y1": y + self.cell_h, "kind": "grid"})
                if not with_cells:
                    continue
                canvas.alpha_composite(under, (x - pad, y - pad + 8))
                cell = src.render(self.cell_w, self.cell_h, 1.0, int(local * FPS)).convert("RGBA")
                cell.putalpha(self.cell_mask)
                canvas.alpha_composite(cell, (x, y))
                canvas.alpha_composite(over, (x, y))
                if with_overlay:
                    self.place(canvas, self.cell_tags[i], x + self.cell_w / 2,
                               y + self.cell_h - 30 - self.cell_tags[i].height / 2, f"cell_tag_{i + 1}", layout)
            if with_overlay:
                self.place(canvas, self.grid_q, W / 2, H * self.grid_q_y, "grid_question", layout)
                self.place(canvas, self.cta, W / 2, self.cta_cy, "cta", layout)
        return canvas.convert("RGB"), layout

    def _hook_bg(self, t):
        T = self.t
        if self.hook_src is None:
            return Image.new("RGB", (W, H), GRID_BG)
        if t <= T["hook_blur_start"]:
            radius = T["hook_blur_from"]
        else:
            p = min(1.0, (t - T["hook_blur_start"]) / (T["hook"] - T["hook_blur_start"]))
            radius = T["hook_blur_from"] + (T["hook_blur_to"] - T["hook_blur_from"]) * p
        img = self.hook_src.render(W, H, 1.0, int(t * FPS))
        return img.filter(ImageFilter.GaussianBlur(radius))


# ---------------------------------------------------------------- 오디오

def loudnorm_args(src, filters, target, duration):
    """loudnorm 2-pass. 1차 측정값으로 2차에 linear 정규화."""
    af = f"{filters},loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *src, "-af", af, "-t", f"{duration:.3f}", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    return (f"{filters},loudnorm=I={target}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
            f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}"
            f":linear=true,aresample=48000")


def build_audio(cfg, ep_dir, duration, out_wav):
    bgm = cfg["bgm"]
    track = ROOT / "bgm" / f"{bgm['track']}.mp3"
    fi, fo = bgm.get("fade_in", 0.1), bgm.get("fade_out", 0.3)
    fades = f"afade=t=in:st=0:d={fi},afade=t=out:st={duration - fo:.3f}:d={fo}"
    bgm_in = ["-ss", str(bgm.get("start", 0)), "-t", f"{duration:.3f}", "-i", str(track)]
    tts = ep_dir / cfg["tts"] if cfg.get("tts") else None

    if tts and tts.exists():
        # TTS 있음: BGM -18dB, 음성 구간 사이드체인 덕킹, 음성은 -14 LUFS 근처로
        gain = bgm.get("gain_db_with_tts", -18)
        duck = (",[v2][b]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[bd]"
                if bgm.get("duck_under_tts", True) else ";[b]anull[bd]")
        fc = (f"[0:a]{fades},volume={gain}dB,aresample=48000[b];"
              f"[1:a]aresample=48000,loudnorm=I=-14:TP=-1.5,asplit=2[v1][v2]{duck};"
              f"[bd][v1]amix=inputs=2:duration=first:normalize=0,apad=whole_dur={duration:.3f}")
        cmd = ["ffmpeg", "-y", "-v", "error", *bgm_in, "-i", str(tts), "-filter_complex", fc,
               "-t", f"{duration:.3f}", "-ac", "2", "-ar", "48000", str(out_wav)]
    else:
        target = bgm.get("loudness_lufs_no_tts", -14)
        af = loudnorm_args(bgm_in, f"apad=whole_dur={duration:.3f},{fades}", target, duration)
        cmd = ["ffmpeg", "-y", "-v", "error", *bgm_in, "-af", af, "-t", f"{duration:.3f}",
               "-ac", "2", "-ar", "48000", str(out_wav)]
    subprocess.run(cmd, check=True)


# ---------------------------------------------------------------- 메인

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--no-bgm", action="store_true", help="레이아웃 확인용 무음 렌더 (최종본 아님)")
    args = ap.parse_args()

    ep_dir = Path(args.episode).resolve()
    cfg = json.loads((ep_dir / "config.json").read_text(encoding="utf-8"))
    for c in cfg["choices"]:
        p = ep_dir / c["image"]
        if not p.exists() and not p.with_suffix(".mp4").exists():
            sys.exit(f"입력 없음: {p}")

    bgm = cfg.get("bgm", {})
    track = ROOT / "bgm" / f"{bgm.get('track')}.mp3"
    if not args.no_bgm and (not bgm.get("track") or not track.exists()):
        sys.exit(f"BGM 없음: bgm.track={bgm.get('track')!r}. docs/bgm-guide.md 규칙대로 곡을 먼저 고르세요.")

    out_dir = ep_dir / "out"
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    scene = Scene(ep_dir, cfg)
    n_frames = round(scene.duration * FPS)
    print(f"구성: 훅 0~{scene.t_choices}s / 선택지 ~{scene.t_grid:.1f}s / 그리드 ~{scene.t_cut:.1f}s / "
          f"루프 컷 ~{scene.duration:.1f}s ({n_frames}프레임)")

    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "bgm.wav"
        if not args.no_bgm:
            build_audio(cfg, ep_dir, scene.duration, audio)

        final = out_dir / ("final.mp4" if not args.no_bgm else "preview_silent.mp4")
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(FPS), "-i", "-"]
        if not args.no_bgm:
            cmd += ["-i", str(audio), "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-t", f"{scene.duration:.3f}", "-movflags", "+faststart", str(final)]
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

        times = list(FRAME_TIMES)
        if not any(scene.t_grid <= t < scene.t_cut for t in times):
            # 필수 시점이 모두 그리드 이전이면 그리드 검증용 프레임을 하나 더 저장
            times.append(round(scene.t_grid + scene.t["grid"] / 2, 1))
        save_at = {round(t * FPS): t for t in times}
        layout_all = {}
        for n in range(n_frames):
            t = n / FPS
            img, layout = scene.frame(t)
            enc.stdin.write(img.tobytes())
            if n in save_at:
                ft = save_at[n]
                img.save(frames_dir / f"{ft:.1f}s.png")
                scene.frame(t, with_overlay=False)[0].save(frames_dir / f"_bg_{ft:.1f}s.png")
                if scene.t_grid <= t < scene.t_cut:
                    scene.frame(t, with_overlay=False, with_cells=False)[0].save(frames_dir / f"_plate_{ft:.1f}s.png")
                layout_all[f"{ft:.1f}"] = layout
        enc.stdin.close()
        if enc.wait() != 0:
            sys.exit("ffmpeg 인코딩 실패")

    (frames_dir / "layout.json").write_text(
        json.dumps({"width": W, "height": H, "fps": FPS, "duration": scene.duration, "frames": layout_all},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완료: {final}")
    print(f"검증 프레임: {frames_dir}")


if __name__ == "__main__":
    main()

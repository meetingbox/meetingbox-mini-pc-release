"""Preview the recording screen layout (Figma 863:626) on 1260×800."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from frame19_layout import (  # noqa: E402
    BACK_BTN,
    BG_RGB,
    BTN_PAUSE,
    BTN_SETTINGS,
    CANVAS_H,
    CANVAS_W,
    LEFT_VEC,
    LISTENING_PILL,
    PARTICIPANTS_FS_RATIO,
    PARTICIPANTS_LABEL,
    PEOPLE_ICON,
    PROVIDER_FS_RATIO,
    PROVIDER_LABEL,
    REC_DOT,
    REC_LABEL,
    REC_LABEL_FS_RATIO,
    RIGHT_VEC,
    RING_DARK,
    RING_GLOW,
    RING_GRADIENT,
    STARTED_FS_RATIO,
    STARTED_LABEL,
    STATUS,
    STATUS_FS_RATIO,
    STOP_PILL,
    TIMER,
    TIMER_FS_RATIO,
    TITLE_FS_RATIO,
    TITLE_LABEL,
    VIDEO_ICON,
    font_px,
    scaled_canvas,
)

ASSETS = ROOT / "assets" / "recording" / "figma"
OUT = ASSETS / "recording_layout_preview.png"
SCREEN_W, SCREEN_H = 1260, 800

_LAYERS: tuple[tuple[str, dict], ...] = (
    ("frame19_ring_glow.png", RING_GLOW),
    ("frame19_ring_dark.png", RING_DARK),
    ("frame19_ring_gradient.png", RING_GRADIENT),
    ("frame19_vector_left.png", LEFT_VEC),
    ("frame19_vector_right.png", RIGHT_VEC),
    ("btn_back.png", BACK_BTN),
    ("icon_rec_dot_red.png", REC_DOT),
    ("icon_people.png", PEOPLE_ICON),
    ("icon_video.png", VIDEO_ICON),
    ("listening_pill.png", LISTENING_PILL),
    ("btn_pause.png", BTN_PAUSE),
    ("stop_recording_pill.png", STOP_PILL),
    ("btn_settings.png", BTN_SETTINGS),
)


def _rect(box, cw, ch, ox, oy):
    x0 = int(ox + box["x"] * cw)
    y0 = int(oy + box["y_top"] * ch)
    x1 = int(ox + (box["x"] + box["w"]) * cw)
    y1 = int(oy + (box["y_top"] + box["h"]) * ch)
    return x0, y0, x1, y1


def _draw_text(draw, box, cw, ch, ox, oy, text, fill, font, anchor="lm"):
    x0, y0, x1, y1 = _rect(box, cw, ch, ox, oy)
    if anchor == "lm":
        draw.text((x0, (y0 + y1) // 2), text, fill=fill, font=font, anchor="lm")
    elif anchor == "ma":
        draw.text(((x0 + x1) // 2, y0), text, fill=fill, font=font, anchor="ma")


def main() -> None:
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), BG_RGB)
    cw, ch = scaled_canvas(SCREEN_W, SCREEN_H)
    ox = (SCREEN_W - cw) / 2
    oy = (SCREEN_H - ch) / 2

    for name, box in _LAYERS:
        path = ASSETS / name
        if not path.is_file():
            print(f"SKIP {name}")
            continue
        asset = Image.open(path).convert("RGBA")
        x0, y0, x1, y1 = _rect(box, cw, ch, ox, oy)
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        asset = asset.resize((w, h), Image.Resampling.LANCZOS)
        img.paste(asset, (x0, y0), asset)

    draw = ImageDraw.Draw(img)
    try:
        ft_timer = ImageFont.truetype("arialbd.ttf", font_px(TIMER_FS_RATIO, ch))
        ft_status = ImageFont.truetype("arialbd.ttf", font_px(STATUS_FS_RATIO, ch))
        ft_rec = ImageFont.truetype("arialbd.ttf", font_px(REC_LABEL_FS_RATIO, ch))
        ft_started = ImageFont.truetype("arial.ttf", font_px(STARTED_FS_RATIO, ch))
        ft_title = ImageFont.truetype("arialbd.ttf", font_px(TITLE_FS_RATIO, ch))
        ft_part = ImageFont.truetype("arial.ttf", font_px(PARTICIPANTS_FS_RATIO, ch))
        ft_provider = ImageFont.truetype("arial.ttf", font_px(PROVIDER_FS_RATIO, ch))
    except OSError:
        ft_timer = ft_status = ft_rec = ft_started = ft_title = ft_part = ft_provider = (
            ImageFont.load_default()
        )

    _draw_text(draw, TIMER, cw, ch, ox, oy, "00 : 12 : 45", (255, 255, 255), ft_timer, "ma")
    _draw_text(draw, STATUS, cw, ch, ox, oy, "Recording in progress", (182, 186, 242), ft_status, "ma")
    _draw_text(draw, REC_LABEL, cw, ch, ox, oy, "Recording...", (255, 255, 255), ft_rec, "lm")
    _draw_text(draw, STARTED_LABEL, cw, ch, ox, oy, "Started at 11:01 AM", (182, 186, 242), ft_started, "lm")
    _draw_text(draw, TITLE_LABEL, cw, ch, ox, oy, "Product Sync", (255, 255, 255), ft_title, "lm")
    _draw_text(draw, PARTICIPANTS_LABEL, cw, ch, ox, oy, "3 Participants", (0, 107, 249), ft_part, "lm")
    _draw_text(draw, PROVIDER_LABEL, cw, ch, ox, oy, "Google Meet", (182, 186, 242), ft_provider, "lm")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

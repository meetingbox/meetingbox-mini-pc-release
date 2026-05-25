"""Preview Frame 19 on 1260×800 canvas (matches device behaviour)."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from frame19_layout import (  # noqa: E402
    BACK_BTN,
    BG_RGB,
    CANVAS_H,
    CANVAS_W,
    ELLIPSE17,
    LEFT_VEC,
    RING_DARK,
    RING_GLOW,
    RING_GRADIENT,
    RIGHT_VEC,
    STATUS,
    STATUS_FS_RATIO,
    STATUS_PILL_RECORDING,
    TIMER,
    TIMER_FS_RATIO,
    font_px,
    scaled_canvas,
)

ASSETS = ROOT / "assets" / "recording" / "figma"
OUT = ASSETS / "frame19_layout_preview.png"
SCREEN_W, SCREEN_H = 1260, 800

_LAYERS: tuple[tuple[str, dict], ...] = (
    ("btn_back.png", BACK_BTN),
    ("frame19_ellipse17.png", ELLIPSE17),
    ("frame19_ring_glow.png", RING_GLOW),
    ("frame19_ring_dark.png", RING_DARK),
    ("frame19_ring_gradient.png", RING_GRADIENT),
    ("frame19_vector_left.png", LEFT_VEC),
    ("frame19_vector_right.png", RIGHT_VEC),
    ("rec_status_recording.png", STATUS_PILL_RECORDING),
)


def _rect(box, cw: float, ch: float, ox: float, oy: float) -> tuple[int, int, int, int]:
    x0 = int(ox + box["x"] * cw)
    y0 = int(oy + box["y_top"] * ch)
    x1 = int(ox + (box["x"] + box["w"]) * cw)
    y1 = int(oy + (box["y_top"] + box["h"]) * ch)
    return x0, y0, x1, y1


def main() -> None:
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), BG_RGB)
    cw, ch = scaled_canvas(SCREEN_W, SCREEN_H)
    ox = (SCREEN_W - cw) / 2
    oy = (SCREEN_H - ch) / 2

    for name, box in _LAYERS:
        path = ASSETS / name
        if not path.is_file():
            continue
        asset = Image.open(path).convert("RGBA")
        x0, y0, x1, y1 = _rect(box, cw, ch, ox, oy)
        asset = asset.resize((max(1, x1 - x0), max(1, y1 - y0)), Image.Resampling.LANCZOS)
        img.paste(asset, (x0, y0), asset)

    draw = ImageDraw.Draw(img)
    try:
        ft = ImageFont.truetype("arialbd.ttf", font_px(TIMER_FS_RATIO, ch))
        fs = ImageFont.truetype("arialbd.ttf", font_px(STATUS_FS_RATIO, ch))
    except OSError:
        ft = fs = ImageFont.load_default()

    tx0, ty0, tx1, ty1 = _rect(TIMER, cw, ch, ox, oy)
    draw.text(((tx0 + tx1) / 2, ty0), "00 : 12 : 45", fill=(255, 255, 255), font=ft, anchor="ma")
    sx0, sy0, sx1, sy1 = _rect(STATUS, cw, ch, ox, oy)
    draw.text(((sx0 + sx1) / 2, sy0), "Recording in progress", fill=(182, 186, 242), font=fs, anchor="ma")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

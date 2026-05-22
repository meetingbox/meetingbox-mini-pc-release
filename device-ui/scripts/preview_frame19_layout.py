"""Preview Frame 19 with uniform scale-to-fit (matches device behaviour)."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from frame19_layout import (  # noqa: E402
    BG_RGB,
    DESIGN_H,
    DESIGN_W,
    LEFT_VEC,
    RIGHT_VEC,
    STATUS,
    STATUS_FS_RATIO,
    TIMER,
    TIMER_FS_RATIO,
    fit_canvas_size,
    font_px,
)

ASSETS = ROOT / "assets" / "recording" / "figma"
OUT = ASSETS / "frame19_layout_preview.png"

SCREEN_W, SCREEN_H = 1260, 800


def _rect(box, cw: float, ch: float, ox: float, oy: float) -> tuple[int, int, int, int]:
    x0 = int(ox + box["x"] * cw)
    y0 = int(oy + box["y_top"] * ch)
    x1 = int(ox + (box["x"] + box["w"]) * cw)
    y1 = int(oy + (box["y_top"] + box["h"]) * ch)
    return x0, y0, x1, y1


def main() -> None:
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), BG_RGB)
    cw, ch = fit_canvas_size(SCREEN_W, SCREEN_H)
    ox = (SCREEN_W - cw) / 2
    oy = (SCREEN_H - ch) / 2

    for name, box in (("frame19_vector_left.png", LEFT_VEC), ("frame19_vector_right.png", RIGHT_VEC)):
        path = ASSETS / name
        if path.is_file():
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

    tx0, ty0, _, _ = _rect(TIMER, cw, ch, ox, oy)
    draw.text((tx0, ty0), "00 : 12 : 45", fill=(255, 255, 255), font=ft)
    sx0, sy0, _, _ = _rect(STATUS, cw, ch, ox, oy)
    draw.text((sx0, sy0), "Recording in progress", fill=(182, 186, 242), font=fs)

    # Outline scaled canvas (debug — shows letterbox vs stretch)
    draw.rectangle(
        [int(ox), int(oy), int(ox + cw), int(oy + ch)],
        outline=(40, 60, 100),
        width=1,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"Wrote {OUT} screen={SCREEN_W}x{SCREEN_H} canvas={cw:.0f}x{ch:.0f} ref={DESIGN_W:.0f}x{DESIGN_H:.0f}")


if __name__ == "__main__":
    main()

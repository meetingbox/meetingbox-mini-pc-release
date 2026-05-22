"""Render Frame 19 ratio layout preview PNG (no Kivy required)."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from frame19_layout import (  # noqa: E402
    BG_RGB,
    LEFT_VEC,
    RIGHT_VEC,
    STATUS,
    STATUS_FS_RATIO,
    TIMER,
    TIMER_FS_RATIO,
    font_px,
)

ASSETS = ROOT / "assets" / "recording" / "figma"
OUT = ASSETS / "frame19_layout_preview.png"

# Preview at default device resolution
W, H = 1260, 800


def _rect(box, width: int, height: int) -> tuple[int, int, int, int]:
    x0 = int(box["x"] * width)
    y0 = int(box["y_top"] * height)
    x1 = int((box["x"] + box["w"]) * width)
    y1 = int((box["y_top"] + box["h"]) * height)
    return x0, y0, x1, y1


def main() -> None:
    img = Image.new("RGB", (W, H), BG_RGB)
    draw = ImageDraw.Draw(img)

    for name, box in (("frame19_vector_left.png", LEFT_VEC), ("frame19_vector_right.png", RIGHT_VEC)):
        path = ASSETS / name
        if path.is_file():
            asset = Image.open(path).convert("RGBA")
            x0, y0, x1, y1 = _rect(box, W, H)
            asset = asset.resize((max(1, x1 - x0), max(1, y1 - y0)), Image.Resampling.LANCZOS)
            img.paste(asset, (x0, y0), asset)

    try:
        font_timer = ImageFont.truetype("arialbd.ttf", font_px(TIMER_FS_RATIO, H))
        font_status = ImageFont.truetype("arialbd.ttf", font_px(STATUS_FS_RATIO, H))
    except OSError:
        font_timer = ImageFont.load_default()
        font_status = font_timer

    tx0, ty0, _, _ = _rect(TIMER, W, H)
    draw.text((tx0, ty0), "00 : 12 : 45", fill=(255, 255, 255), font=font_timer)

    sx0, sy0, _, _ = _rect(STATUS, W, H)
    draw.text((sx0, sy0), "Recording in progress", fill=(182, 186, 242), font=font_status)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"Wrote {OUT} ({W}x{H})")


if __name__ == "__main__":
    main()

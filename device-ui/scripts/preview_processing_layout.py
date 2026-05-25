"""Preview the processing screen layout (Figma 397:261) on 1260×800."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from processing_layout import (  # noqa: E402
    BACK_BTN,
    BG_RGB,
    CANVAS_H,
    CANVAS_W,
    CHECK_BADGE,
    DOT_SEPARATOR,
    DURATION_FS_RATIO,
    DURATION_LABEL,
    HEADLINE_BOTTOM,
    HEADLINE_FS_RATIO,
    HEADLINE_LABEL,
    LISTENING_PILL,
    NOTIFY_BAR,
    ORB_GLOW,
    RING_GLOW,
    RING_LIGHTEN,
    RING_OUTER,
    RING_SOLID,
    SETTINGS_BTN,
    STEPS_CARD,
    SUBTITLE_BOTTOM,
    SUBTITLE_FS_RATIO,
    TITLE_FS_RATIO,
    TITLE_LABEL,
    font_px,
    scaled_canvas,
)

ASSETS = ROOT / "assets" / "processing" / "figma"
OUT = ASSETS / "processing_layout_preview.png"

# Default render at the Figma reference resolution. ``--all`` (or any extra
# argv) additionally renders the layout at every entry in ``_RESOLUTIONS`` so
# we can verify the screen behaves on tiny kiosk panels and big HDMI monitors.
SCREEN_W, SCREEN_H = 1260, 800

_RESOLUTIONS: tuple[tuple[int, int, str], ...] = (
    (1260, 800, "design_1260x800"),
    (1280, 720, "hd_16x9_1280x720"),
    (1024, 600, "kiosk_1024x600"),
    (800, 480, "tiny_800x480"),
    (1920, 1080, "fhd_1920x1080"),
    (600, 1024, "portrait_600x1024"),
)

_LAYERS: tuple[tuple[str, dict], ...] = (
    ("orb_glow.png", ORB_GLOW),
    ("ring_glow.png", RING_GLOW),
    ("ring_lighten.png", RING_LIGHTEN),
    ("ring_solid.png", RING_SOLID),
    ("ring_outer.png", RING_OUTER),
    ("btn_back.png", BACK_BTN),
    ("listening_pill.png", LISTENING_PILL),
    ("btn_settings.png", SETTINGS_BTN),
    ("check_badge.png", CHECK_BADGE),
    ("dot_separator.png", DOT_SEPARATOR),
    ("steps_card.png", STEPS_CARD),
    ("notify_bar.png", NOTIFY_BAR),
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


def _render(screen_w: int, screen_h: int, out_path: Path) -> None:
    """Render the processing screen layout at the given screen size."""
    img = Image.new("RGB", (screen_w, screen_h), BG_RGB)
    cw, ch = scaled_canvas(screen_w, screen_h)
    ox = (screen_w - cw) / 2
    oy = (screen_h - ch) / 2

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
        ft_h = ImageFont.truetype("arialbd.ttf", font_px(HEADLINE_FS_RATIO, ch))
        ft_title = ImageFont.truetype("arial.ttf", font_px(TITLE_FS_RATIO, ch))
        ft_dur = ImageFont.truetype("arial.ttf", font_px(DURATION_FS_RATIO, ch))
        ft_sub = ImageFont.truetype("arial.ttf", font_px(SUBTITLE_FS_RATIO, ch))
    except OSError:
        ft_h = ft_title = ft_dur = ft_sub = ImageFont.load_default()

    _draw_text(draw, HEADLINE_LABEL, cw, ch, ox, oy, "Recording complete", (255, 255, 255), ft_h, "lm")
    _draw_text(draw, TITLE_LABEL, cw, ch, ox, oy, "Product Sync", (182, 186, 242), ft_title, "lm")
    _draw_text(draw, DURATION_LABEL, cw, ch, ox, oy, "32min", (182, 186, 242), ft_dur, "lm")
    _draw_text(draw, HEADLINE_BOTTOM, cw, ch, ox, oy, "Summarizing your meeting...", (255, 255, 255), ft_h, "lm")
    _draw_text(draw, SUBTITLE_BOTTOM, cw, ch, ox, oy, "This may take a few seconds", (182, 186, 242), ft_sub, "lm")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    print(f"Wrote {out_path} ({screen_w}x{screen_h})")


def main() -> None:
    _render(SCREEN_W, SCREEN_H, OUT)
    if len(sys.argv) > 1:
        for sw, sh, tag in _RESOLUTIONS:
            _render(sw, sh, ASSETS / f"processing_layout_preview_{tag}.png")


if __name__ == "__main__":
    main()

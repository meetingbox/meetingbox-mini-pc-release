"""Frame 19 layout — Figma `863:635`.

Figma pixel sizes are a **design reference only**.  On device:
1. Keep internal layout as ratios inside the reference frame (423×438).
2. Scale that frame **uniformly** to fit the real screen (preserve aspect ratio).
3. Centre the result; full-screen background fills any letterbox margins.

This matches how Figma previews relate to production screens of different sizes.
"""

from __future__ import annotations

from typing import TypedDict


class Box(TypedDict):
    x: float
    y_top: float
    w: float
    h: float


# Figma Frame 19 reference size (aspect ratio lock — not the device resolution)
DESIGN_W = 423.0
DESIGN_H = 438.0

LEFT_VEC: Box = dict(x=52 / DESIGN_W, y_top=67.47 / DESIGN_H, w=36.97 / DESIGN_W, h=173.32 / DESIGN_H)
RIGHT_VEC: Box = dict(x=335.8 / DESIGN_W, y_top=67.47 / DESIGN_H, w=36.97 / DESIGN_W, h=173.32 / DESIGN_H)
TIMER: Box = dict(x=104 / DESIGN_W, y_top=298 / DESIGN_H, w=178 / DESIGN_W, h=42 / DESIGN_H)
STATUS: Box = dict(x=62 / DESIGN_W, y_top=346 / DESIGN_H, w=290 / DESIGN_W, h=34 / DESIGN_H)

TIMER_FS_RATIO = 35 / DESIGN_H
STATUS_FS_RATIO = 28.251121520996094 / DESIGN_H

BG_RGB = (1, 8, 26)


def fit_canvas_size(screen_w: float, screen_h: float) -> tuple[float, float]:
    """Uniform scale-to-fit: largest size that preserves DESIGN aspect ratio."""
    if screen_w <= 0 or screen_h <= 0:
        return DESIGN_W, DESIGN_H
    scale = min(screen_w / DESIGN_W, screen_h / DESIGN_H)
    return DESIGN_W * scale, DESIGN_H * scale


def kivy_hints(box: Box) -> dict:
    """Ratio box → Kivy hints inside the scaled design canvas."""
    return {
        "size_hint": (box["w"], box["h"]),
        "pos_hint": {"x": box["x"], "y": 1.0 - box["y_top"] - box["h"]},
    }


def font_px(fs_ratio: float, canvas_height: float) -> int:
    """Font size tracks the scaled canvas height (same proportion as Figma)."""
    return max(6, round(fs_ratio * canvas_height))

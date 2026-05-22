"""Frame 19 layout — Figma `863:635` inside `863:626`.

The correct approach:
- Reference canvas = full recording screen 1260×800 (same as Figma)
- Frame 19 sits at (392, 104), size 423×438 inside that canvas
- All element positions are absolute within 1260×800
- Scale the 1260×800 canvas uniformly to fit the device screen
- Frame 19 then appears at the same proportional position as in Figma
"""

from __future__ import annotations

from typing import TypedDict


class Box(TypedDict):
    x: float       # left edge as fraction of CANVAS_W
    y_top: float   # top edge as fraction of CANVAS_H  (Figma top-down)
    w: float       # width fraction of CANVAS_W
    h: float       # height fraction of CANVAS_H


# Full recording screen canvas (Figma Frame 18 — parent of Frame 19)
CANVAS_W = 1260.0
CANVAS_H = 800.0

# Frame 19 origin inside the canvas
_F19_X = 392.0
_F19_Y = 104.0

# Absolute positions of Frame 19 children in 1260×800 space
# (Frame 19 local coords + Frame 19 origin)
LEFT_VEC: Box = dict(
    x=(_F19_X + 52.0) / CANVAS_W,
    y_top=(_F19_Y + 67.47) / CANVAS_H,
    w=36.97 / CANVAS_W,
    h=173.32 / CANVAS_H,
)
RIGHT_VEC: Box = dict(
    x=(_F19_X + 335.8) / CANVAS_W,
    y_top=(_F19_Y + 67.47) / CANVAS_H,
    w=36.97 / CANVAS_W,
    h=173.32 / CANVAS_H,
)
TIMER: Box = dict(
    x=(_F19_X + 104.0) / CANVAS_W,
    y_top=(_F19_Y + 298.0) / CANVAS_H,
    w=178.0 / CANVAS_W,
    h=42.0 / CANVAS_H,
)
STATUS: Box = dict(
    x=(_F19_X + 62.0) / CANVAS_W,
    y_top=(_F19_Y + 346.0) / CANVAS_H,
    w=290.0 / CANVAS_W,
    h=34.0 / CANVAS_H,
)

# Font sizes as fraction of canvas height (preserves Figma proportions)
TIMER_FS_RATIO = 35.0 / CANVAS_H
STATUS_FS_RATIO = 28.251121520996094 / CANVAS_H

BG_RGB = (1, 8, 26)


def scaled_canvas(screen_w: float, screen_h: float) -> tuple[float, float]:
    """Uniform scale-to-fit: 1260×800 canvas scaled to fit the device screen."""
    if screen_w <= 0 or screen_h <= 0:
        return CANVAS_W, CANVAS_H
    scale = min(screen_w / CANVAS_W, screen_h / CANVAS_H)
    return CANVAS_W * scale, CANVAS_H * scale


def kivy_hints(box: Box) -> dict:
    """Box ratios → Kivy size_hint + pos_hint (bottom-left origin)."""
    return {
        "size_hint": (box["w"], box["h"]),
        "pos_hint": {"x": box["x"], "y": 1.0 - box["y_top"] - box["h"]},
    }


def font_px(fs_ratio: float, canvas_height: float) -> int:
    """Font px scales with the canvas height, same proportion as Figma."""
    return max(6, round(fs_ratio * canvas_height))

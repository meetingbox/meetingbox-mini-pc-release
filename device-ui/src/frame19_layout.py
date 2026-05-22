"""Frame 19 layout — Figma `863:635`.

The parent screen in Figma is 1260×800 (Frame 18).
Frame 19 sits inside it at (392, 104) with size 423×438.

All ratios are expressed relative to the 1260×800 screen — the entire parent
frame is what gets uniformly scaled to fill the real device screen.
That way every element is positioned exactly as seen in Figma, on any display.
"""

from __future__ import annotations

from typing import TypedDict


class Box(TypedDict):
    x: float       # left edge fraction of screen width
    y_top: float   # top edge fraction of screen height (Figma top-down)
    w: float       # width fraction
    h: float       # height fraction


# Figma parent screen size — the ONE coordinate system
SCREEN_W = 1260.0
SCREEN_H = 800.0

# Frame 19 origin inside the parent screen
_F19_X = 392.0
_F19_Y = 104.0
_F19_W = 423.0
_F19_H = 438.0


def _box(local_x: float, local_y: float, w: float, h: float) -> Box:
    """Convert Frame-19-local Figma px to parent-screen ratios."""
    return dict(
        x=(_F19_X + local_x) / SCREEN_W,
        y_top=(_F19_Y + local_y) / SCREEN_H,
        w=w / SCREEN_W,
        h=h / SCREEN_H,
    )


# Frame 19 children expressed in parent-screen ratios
LEFT_VEC  = _box(52.0,   67.47,  36.97, 173.32)
RIGHT_VEC = _box(335.8,  67.47,  36.97, 173.32)
TIMER     = _box(104.0, 298.0,  178.0,   42.0)
STATUS    = _box(62.0,  346.0,  290.0,   34.0)

# Font sizes relative to the parent screen height
TIMER_FS_RATIO  = 35.0  / SCREEN_H
STATUS_FS_RATIO = 28.251121520996094 / SCREEN_H

BG_RGB = (1, 8, 26)


def uniform_scale(screen_w: float, screen_h: float) -> float:
    """Scale factor to fit the 1260×800 reference frame on any real screen."""
    if screen_w <= 0 or screen_h <= 0:
        return 1.0
    return min(screen_w / SCREEN_W, screen_h / SCREEN_H)


def scaled_canvas(screen_w: float, screen_h: float) -> tuple[float, float]:
    """Pixel size of the scaled 1260×800 reference frame."""
    s = uniform_scale(screen_w, screen_h)
    return SCREEN_W * s, SCREEN_H * s


def kivy_hints(box: Box) -> dict:
    """Ratio box → Kivy size_hint + pos_hint (bottom-left origin)."""
    return {
        "size_hint": (box["w"], box["h"]),
        "pos_hint": {"x": box["x"], "y": 1.0 - box["y_top"] - box["h"]},
    }


def font_px(fs_ratio: float, canvas_h: float) -> int:
    return max(6, round(fs_ratio * canvas_h))

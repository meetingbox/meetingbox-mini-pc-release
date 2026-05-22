"""Frame 19 layout — Figma `863:635` inside `863:626` (1260×800).

Reference canvas = full recording screen.  Frame 19 is a child at (389, 105),
size 420×420.  Element positions are absolute within 1260×800, then the whole
canvas scales uniformly to fit any device screen.
"""

from __future__ import annotations

from typing import TypedDict


class Box(TypedDict):
    x: float
    y_top: float
    w: float
    h: float


CANVAS_W = 1260.0
CANVAS_H = 800.0

# Frame 19 — updated Figma metadata (863:635)
_F19_X = 389.0
_F19_Y = 105.0
_F19_W = 420.0
_F19_H = 420.0


def _abs(local_x: float, local_y: float, local_w: float, local_h: float) -> Box:
    """Frame-19-local px → absolute ratio box on the 1260×800 canvas."""
    return dict(
        x=(_F19_X + local_x) / CANVAS_W,
        y_top=(_F19_Y + local_y) / CANVAS_H,
        w=local_w / CANVAS_W,
        h=local_h / CANVAS_H,
    )


LEFT_VEC: Box = _abs(52.0, 67.47265625, 36.975, 173.3189239501953)
RIGHT_VEC: Box = _abs(331.0299987792969, 67.47265625, 36.97499084472656, 173.3189239501953)
TIMER: Box = _abs(89.0, 300.0, 243.0, 42.0)
STATUS: Box = _abs(65.0, 346.0, 290.0, 34.0)

TIMER_FS_RATIO = 35.0 / CANVAS_H
STATUS_FS_RATIO = 28.251 / CANVAS_H

BG_RGB = (1, 8, 26)


def scaled_canvas(screen_w: float, screen_h: float) -> tuple[float, float]:
    if screen_w <= 0 or screen_h <= 0:
        return CANVAS_W, CANVAS_H
    scale = min(screen_w / CANVAS_W, screen_h / CANVAS_H)
    return CANVAS_W * scale, CANVAS_H * scale


def kivy_hints(box: Box) -> dict:
    return {
        "size_hint": (box["w"], box["h"]),
        "pos_hint": {"x": box["x"], "y": 1.0 - box["y_top"] - box["h"]},
    }


def font_px(fs_ratio: float, canvas_height: float) -> int:
    return max(6, round(fs_ratio * canvas_height))

"""Frame 19 layout — Figma `863:635` inside recording screen `863:626`.

Reference canvas = 1260×800.  Frame 19 sits at (389, 105), size 420×420.
All positions are absolute fractions of the canvas; scale uniformly to device.
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

# Frame 19 origin on the 1260×800 canvas (updated Figma 2026-05-22)
_F19_X = 389.0
_F19_Y = 105.0


def canvas_box(lx: float, ly: float, lw: float, lh: float) -> Box:
    """Screen-absolute px on 1260×800 → canvas ratio box."""
    return dict(
        x=lx / CANVAS_W,
        y_top=ly / CANVAS_H,
        w=lw / CANVAS_W,
        h=lh / CANVAS_H,
    )


def _abs(lx: float, ly: float, lw: float, lh: float) -> Box:
    """Frame-19-local px → canvas ratio box."""
    return canvas_box(_F19_X + lx, _F19_Y + ly, lw, lh)


# Header — top-left of recording screen `863:626` (same grid as calendar/home)
BACK_BTN = canvas_box(24.02, 21.19, 76.28, 76.28)
# Status pill sits to the right of the back button, vertically centred in the header row
_STATUS_Y_REC = 21.19 + (76.28 - 32.0) / 2
_STATUS_Y_PAU = 21.19 + (76.28 - 38.0) / 2
STATUS_PILL_RECORDING = canvas_box(118.66, _STATUS_Y_REC, 129.0, 32.0)
STATUS_PILL_PAUSED = canvas_box(118.66, _STATUS_Y_PAU, 121.0, 38.0)

# Back → front draw order (Frame 19)
ELLIPSE17 = _abs(68.9921875, 12.0, 285.7979431152344, 283.25390625)
RING_GLOW = _abs(101.97265625, 44.68359375, 219.8445587158203, 217.8876190185547)
RING_DARK = _abs(101.97265625, 46.6640625, 219.8445587158203, 217.8876190185547)
RING_GRADIENT = _abs(101.97265625, 44.68359375, 219.8445587158203, 217.8876190185547)
LEFT_VEC = _abs(52.0, 67.47265625, 36.974998474121094, 173.3189239501953)
RIGHT_VEC = _abs(331.0299987792969, 67.47265625, 36.97499084472656, 173.3189239501953)
TIMER = _abs(89.0, 300.0, 243.0, 42.0)
STATUS = _abs(65.0, 346.0, 290.0, 34.0)

TIMER_FS_RATIO = 35.0 / CANVAS_H
STATUS_FS_RATIO = 28.251121520996094 / CANVAS_H

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

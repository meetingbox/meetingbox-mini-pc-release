"""Frame 19 layout ratios only (`863:635`) — no parent-frame pixel refs.

Every value is a fraction of the full screen (0–1).  Derived once from Figma
Frame 19 (423×438 design canvas) and reused by the recording screen + previews.
"""

from __future__ import annotations

from typing import TypedDict


class Box(TypedDict):
    x: float       # left edge, fraction of width
    y_top: float   # top edge, fraction of height (Figma-style)
    w: float       # width fraction
    h: float       # height fraction


# ── Frame 19 children (ratios) ───────────────────────────────────────────────
LEFT_VEC: Box = dict(x=52 / 423, y_top=67.47 / 438, w=36.97 / 423, h=173.32 / 438)
RIGHT_VEC: Box = dict(x=335.8 / 423, y_top=67.47 / 438, w=36.97 / 423, h=173.32 / 438)
TIMER: Box = dict(x=104 / 423, y_top=298 / 438, w=178 / 423, h=42 / 438)
STATUS: Box = dict(x=62 / 423, y_top=346 / 438, w=290 / 423, h=34 / 438)

TIMER_FS_RATIO = 35 / 438
STATUS_FS_RATIO = 28.251121520996094 / 438

BG_RGB = (1, 8, 26)


def kivy_hints(box: Box) -> dict:
    """Convert a ratio box to Kivy ``size_hint`` + ``pos_hint`` (bottom-left origin)."""
    return {
        "size_hint": (box["w"], box["h"]),
        "pos_hint": {"x": box["x"], "y": 1.0 - box["y_top"] - box["h"]},
    }


def font_px(fs_ratio: float, screen_height: int) -> int:
    return max(6, round(fs_ratio * screen_height))

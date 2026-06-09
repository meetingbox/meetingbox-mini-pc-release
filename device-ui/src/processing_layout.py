"""Processing / "Summarizing" screen layout — Figma ``1036:16``
(dvqlN0JtWQODt6jYbTrbDG, "Copy").

Light-theme post-recording screen drawn with Kivy primitives:

  * slate wash background
  * "Recording Complete" + "Meeting Name · 32 min" header
  * centre orb with a calm, breathing concentric-ring animation
  * "Summarizing your meeting..." / "This may take a few seconds" captions
  * a rotating stage line ("Extracting key points...")
  * a bottom countdown — "Back to home screen in N seconds" — that returns the
    user to the home screen (the summary-ready notification is surfaced there)

Canvas 1260 × 800; values are exact Figma absolute coordinates.

Layer reference (Figma node IDs):
  1036:199 Recording Complete
  1036:200 Meeting Name · 32 min
  1036:148 Group 199  centre orb (concentric rings)
  1036:173 Summarizing your meeting...
  1036:175 This may take a few seconds
  1036:182 Extracting key points...  (rotating stage line)
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


def canvas_box(lx: float, ly: float, lw: float, lh: float) -> Box:
    return dict(
        x=lx / CANVAS_W,
        y_top=ly / CANVAS_H,
        w=lw / CANVAS_W,
        h=lh / CANVAS_H,
    )


# ── Boxes ─────────────────────────────────────────────────────────────────
STATUS_BAR = canvas_box(1129.0, 28.0, 91.13, 21.0)
ORB = canvas_box(493.0, 226.0, 258.0, 258.0)

HEADLINE = canvas_box(418.0, 92.0, 424.0, 55.0)          # "Recording Complete"
META = canvas_box(330.0, 171.0, 600.0, 36.0)             # "Meeting Name · 32 min"

SUMMARIZING = canvas_box(366.0, 504.0, 528.0, 48.0)      # centred
SUBTITLE = canvas_box(330.0, 572.0, 600.0, 30.0)         # centred
STAGE = canvas_box(330.0, 646.0, 600.0, 36.0)            # rotating, centred
COUNTDOWN = canvas_box(330.0, 712.0, 600.0, 30.0)        # centred

# ── Typography (Figma px on the 800-tall canvas) ──────────────────────────
HEADLINE_FS_RATIO = 45.0 / CANVAS_H
META_FS_RATIO = 30.0 / CANVAS_H
SUMMARIZING_FS_RATIO = 40.0 / CANVAS_H
SUBTITLE_FS_RATIO = 23.0 / CANVAS_H
STAGE_FS_RATIO = 28.0 / CANVAS_H
COUNTDOWN_FS_RATIO = 24.0 / CANVAS_H

# ── Colours ───────────────────────────────────────────────────────────────
BG_TOP = (0.52, 0.55, 0.63, 1.0)
BG_BOT = (0.45, 0.48, 0.56, 1.0)

COL_HEADLINE = (47 / 255, 47 / 255, 47 / 255, 1.0)       # #2F2F2F
COL_TEXT = (53 / 255, 57 / 255, 59 / 255, 1.0)           # #35393B
COL_MUTED = (53 / 255, 57 / 255, 59 / 255, 0.78)
COL_COUNTDOWN = (53 / 255, 57 / 255, 59 / 255, 0.70)
COL_PURPLE = (109 / 255, 72 / 255, 204 / 255, 1.0)       # #6D48CC

RING_TOP = (164 / 255, 143 / 255, 210 / 255, 1.0)        # #A48FD2
RING_BOT = (109 / 255, 73 / 255, 195 / 255, 1.0)         # #6D49C3
ORB_FILL = (1 / 255, 12 / 255, 37 / 255, 1.0)            # #010C25


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

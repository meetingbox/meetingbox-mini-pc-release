"""Meeting Summary screen layout — Figma ``659:838`` (VelsLhL4YHeVRZSCEmCrGw).

Canvas: 1260 × 800. Every value is the exact Figma absolute coordinate.

Layer reference (Figma node IDs)::

    659:839   back button (round)
    676:1730  "Meeting Summary" page title
    663:1373  meta card (file icon + title + date + chips + Export / Share)
    704:1402  AI Summary card
    700:1318  Action items card (with scrollbar)
    700:1358  Decisions Made card (with scrollbar)
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
    """Figma absolute px on 1260×800 → ratio box."""
    return dict(
        x=lx / CANVAS_W,
        y_top=ly / CANVAS_H,
        w=lw / CANVAS_W,
        h=lh / CANVAS_H,
    )


# ── Header ───────────────────────────────────────────────────────────────
BACK_BTN = canvas_box(38.0, 21.0, 76.278, 76.278)
PAGE_TITLE = canvas_box(150.0, 39.0, 360.0, 36.0)  # widened for safety


# ── Meta card (663:1373) at (38, 106) 1185×133 ───────────────────────────
META_CARD = canvas_box(38.0, 106.0, 1185.0, 133.0)

_M_X = META_CARD["x"] * CANVAS_W
_M_Y = META_CARD["y_top"] * CANVAS_H

META_FILE_ICON = canvas_box(_M_X + 24.0, _M_Y + 32.0, 70.628, 70.628)
META_TITLE = canvas_box(_M_X + 116.0, _M_Y + 7.0, 700.0, 36.0)
META_DATE = canvas_box(_M_X + 116.0, _M_Y + 50.0, 700.0, 30.0)
META_PARTICIPANTS = canvas_box(_M_X + 116.0, _M_Y + 94.0, 133.0, 32.0)
META_RECORDED = canvas_box(_M_X + 263.0, _M_Y + 94.0, 107.0, 32.0)
META_EXPORT = canvas_box(_M_X + 834.0, _M_Y + 36.0, 155.0, 57.797)
META_SHARE = canvas_box(_M_X + 1002.5, _M_Y + 36.34, 155.0, 57.797)


# ── AI Summary card (704:1402) at (38, 248) 1184×122 ─────────────────────
SUMMARY_CARD = canvas_box(38.0, 248.0, 1184.0, 122.0)
_S_X = SUMMARY_CARD["x"] * CANVAS_W
_S_Y = SUMMARY_CARD["y_top"] * CANVAS_H

SUMMARY_ICON = canvas_box(_S_X + 22.0, _S_Y + 11.0, 65.0, 65.0)
SUMMARY_TITLE = canvas_box(_S_X + 118.0, _S_Y + 10.0, 200.0, 30.0)
SUMMARY_TEXT = canvas_box(_S_X + 118.0, _S_Y + 40.0, 815.0, 72.0)
# ChatGPT preview overflows the card top by 6px (Figma css ``top:-6px``)
SUMMARY_IMAGE = canvas_box(_S_X + 939.0, _S_Y - 6.0, 208.765, 139.176)


# ── Action items card (700:1318) at (39, 381) 1184×202 ───────────────────
ACTIONS_CARD = canvas_box(39.0, 381.0, 1184.0, 202.0)
_A_X = ACTIONS_CARD["x"] * CANVAS_W
_A_Y = ACTIONS_CARD["y_top"] * CANVAS_H

ACTIONS_ICON = canvas_box(_A_X + 54.0, _A_Y + 5.0, 34.49, 34.49)
ACTIONS_TITLE = canvas_box(_A_X + 97.0, _A_Y + 4.0, 220.0, 36.0)

# 4 visible rows — y from card top (50, 87, 124, 159).
ACTION_ROW_YS = (50.0, 87.0, 124.0, 159.0)
ACTION_ROW_HEIGHT = 32.0

ACTION_X_CHECK = _A_X + 59.0
ACTION_X_TASK = _A_X + 169.59
ACTION_X_AVATAR = _A_X + 551.59
ACTION_X_NAME = _A_X + 673.59
ACTION_X_DATE = _A_X + 852.59

ACTION_CHECK_SIZE = 29.0
ACTION_AVATAR_SIZE = 30.0
ACTION_TASK_W = 360.0
ACTION_NAME_W = 160.0
ACTION_DATE_W = 110.0

ACTIONS_SCROLL_TRACK = canvas_box(_A_X + 1150.59, _A_Y + 17.59, 9.0, 169.0)
ACTIONS_SCROLL_THUMB = canvas_box(_A_X + 1150.59, _A_Y + 108.59, 9.0, 38.0)


# ── Decisions Made card (700:1358) at (38, 592) 1184×184 ─────────────────
DECISIONS_CARD = canvas_box(38.0, 592.0, 1184.0, 184.0)
_D_X = DECISIONS_CARD["x"] * CANVAS_W
_D_Y = DECISIONS_CARD["y_top"] * CANVAS_H

# The Figma metadata reports x=88.24 for the decision-solid icon, but the
# generated CSS overrides this via ``-scale-x-100`` + ``left:4.58% right:92.55%``
# which renders the icon at parent-local ~(53, 9) with a ~35px square. We use
# the CSS-derived position because the metadata value visually overlaps the
# adjacent "Decisions Made" title.
DECISIONS_ICON = canvas_box(_D_X + 53.0, _D_Y + 9.24, 35.0, 34.0)
DECISIONS_TITLE = canvas_box(_D_X + 108.59, _D_Y + 6.59, 280.0, 36.0)

# 4 visible decision rows — y from card top (42.59, 76.59, 109.59, 143.59).
DECISION_ROW_YS = (42.59, 76.59, 109.59, 143.59)
DECISION_ROW_HEIGHT = 30.0
DECISION_X_TICK = _D_X + 53.59
DECISION_X_TEXT = _D_X + 169.59
DECISION_TICK_SIZE = 30.0
DECISION_TEXT_W = 940.0

DECISIONS_SCROLL_TRACK = canvas_box(_D_X + 1150.59, _D_Y + 16.59, 9.0, 151.0)
DECISIONS_SCROLL_THUMB = canvas_box(_D_X + 1150.59, _D_Y + 32.59, 9.0, 38.0)


# ── Typography (Figma px on 800-tall canvas) ─────────────────────────────
PAGE_TITLE_FS_RATIO = 30.0 / CANVAS_H      # "Meeting Summary"
META_TITLE_FS_RATIO = 30.0 / CANVAS_H      # "Product Sync"
META_DATE_FS_RATIO = 25.0 / CANVAS_H       # "May 21, 11:00 AM  45 min"
SUMMARY_TITLE_FS_RATIO = 25.0 / CANVAS_H   # "AI Summary"
SUMMARY_TEXT_FS_RATIO = 20.0 / CANVAS_H    # summary body
SECTION_TITLE_FS_RATIO = 30.0 / CANVAS_H   # "Action items" / "Decisions Made"
ROW_TEXT_FS_RATIO = 25.0 / CANVAS_H        # row body text


# ── Colours (sampled from Figma) ─────────────────────────────────────────
BG_RGB = (1, 8, 26)  # #01081A

# Card surface gradient. Kivy can't easily paint a vertical gradient with a
# rounded mask without a custom shader, so we approximate with a single
# midtone between the two stops; the border + radius give the depth.
CARD_FILL = (0x01 / 255, 0x0E / 255, 0x31 / 255, 1.0)   # midpoint #010E31
CARD_BORDER = (0x3F / 255, 0x42 / 255, 0x53 / 255, 1.0)  # #3F4253
CARD_RADIUS = 22.601  # design px on a 800-tall canvas

# Inner pill / chip surface
CHIP_FILL = (0x01 / 255, 0x08 / 255, 0x17 / 255, 1.0)   # #010817

# Scrollbar
SCROLL_TRACK_FILL = (0x06 / 255, 0x16 / 255, 0x42 / 255, 1.0)  # #061642
SCROLL_THUMB_FILL = (0x00 / 255, 0x6B / 255, 0xF9 / 255, 1.0)  # #006BF9
SCROLL_RADIUS = 12.0

# Text colours
COL_WHITE = (1.0, 1.0, 1.0, 1.0)
COL_MUTED = (182 / 255, 186 / 255, 242 / 255, 1.0)   # #B6BAF2
COL_HINT = (155 / 255, 162 / 255, 178 / 255, 1.0)    # #9BA2B2


def scaled_canvas(screen_w: float, screen_h: float) -> tuple[float, float]:
    """Aspect-preserving canvas size for the current screen."""
    if screen_w <= 0 or screen_h <= 0:
        return CANVAS_W, CANVAS_H
    scale = min(screen_w / CANVAS_W, screen_h / CANVAS_H)
    return CANVAS_W * scale, CANVAS_H * scale


def kivy_hints(box: Box) -> dict:
    return {
        "size_hint": (box["w"], box["h"]),
        "pos_hint": {"x": box["x"], "y": 1.0 - box["y_top"] - box["h"]},
    }


_FONT_MIN_PX = 10
_FONT_MAX_PX = 96


def font_px(fs_ratio: float, canvas_height: float) -> int:
    raw = round(fs_ratio * canvas_height)
    return max(_FONT_MIN_PX, min(_FONT_MAX_PX, raw))


def row_box(row_x: float, card_y_top: float, row_y_rel: float, w: float, h: float) -> Box:
    """Helper for absolute action-item / decision row positions."""
    return canvas_box(row_x, card_y_top + row_y_rel, w, h)

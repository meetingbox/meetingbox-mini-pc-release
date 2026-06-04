"""Meeting Summary layout tokens.

Reworked layout with:
- topbar
- recording card
- main two-column area
- footer
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


# ── Topbar ───────────────────────────────────────────────────────────────
TOPBAR = canvas_box(0.0, 0.0, 1260.0, 56.0)
BACK_BTN = canvas_box(24.0, 10.0, 36.0, 36.0)
PAGE_TITLE = canvas_box(72.0, 14.0, 360.0, 30.0)
PAGE_TITLE_FS_RATIO = 22.0 / CANVAS_H
TOP_EXPORT = canvas_box(1030.0, 10.0, 96.0, 36.0)
TOP_SHARE = canvas_box(1134.0, 10.0, 96.0, 36.0)


# ── Recording card ───────────────────────────────────────────────────────
META_CARD = canvas_box(0.0, 56.0, 1260.0, 92.0)
_M_X = 24.0
_M_Y = 78.0

META_FILE_ICON = canvas_box(_M_X, _M_Y, 48.0, 48.0)
META_TITLE = canvas_box(_M_X + 64.0, _M_Y + 2.0, 620.0, 24.0)
META_DATE = canvas_box(_M_X + 64.0, _M_Y + 26.0, 620.0, 20.0)
META_PARTICIPANTS = canvas_box(_M_X + 900.0, _M_Y + 4.0, 332.0, 40.0)

META_TITLE_FS_RATIO = 17.0 / CANVAS_H
META_DATE_FS_RATIO = 15.0 / CANVAS_H


# ── Main area ────────────────────────────────────────────────────────────
SIDEBAR_CARD = canvas_box(24.0, 168.0, 200.0, 580.0)
_S_X = 24.0
_S_Y = 168.0

# Tab geometry (relative to canvas; each tab is a separate Box).
_TAB_X_OFFSET = 8.0
_TAB_Y_OFFSET = 8.0
_TAB_W = 184.0
_TAB_H = 40.0
_TAB_GAP = 4.0


def _tab(i: int) -> Box:
    return canvas_box(
        _S_X + _TAB_X_OFFSET,
        _S_Y + _TAB_Y_OFFSET + i * (_TAB_H + _TAB_GAP),
        _TAB_W,
        _TAB_H,
    )


TAB_OVERVIEW = _tab(0)
TAB_ACTION_ITEMS = _tab(1)
TAB_KEY_POINTS = _tab(2)
TAB_DECISIONS = _tab(3)
TAB_TRANSCRIPT = _tab(4)
TAB_PARTICIPANTS = _tab(5)
TAB_FS_RATIO = 15.0 / CANVAS_H

# Legacy slot kept for compatibility (now unused for player).
PLAY_RECORDING = canvas_box(
    _S_X + _TAB_X_OFFSET,
    _S_Y + 580.0 - 14.0 - 56.0,
    _TAB_W,
    56.0,
)
PLAY_RECORDING_FS_RATIO = 15.0 / CANVAS_H


# ── Content area (everything to the right of the sidebar) ────────────────
CONTENT_AREA = canvas_box(240.0, 168.0, 996.0, 580.0)
_C_X = 240.0
_C_Y = 168.0
_C_W = 996.0
_C_H = 580.0


# Overview tab — three rows:
#   Row 1: AI Summary card                 (full width, 140 tall)
#   Row 2: Key Topics card                 (full width, 158 tall — needs
#                                           enough room to vertically separate
#                                           topic names from progress bars)
#   Row 3: Action Items + Decisions Made   (side by side, fills remainder)
OV_GAP = 12.0
OV_AI_CARD = canvas_box(_C_X, _C_Y, _C_W, 140.0)

OV_KEY_CARD = canvas_box(_C_X, _C_Y + 140.0 + OV_GAP, _C_W, 158.0)

_R3_Y = _C_Y + 140.0 + OV_GAP + 158.0 + OV_GAP
_R3_H = _C_H - (_R3_Y - _C_Y)
_R3_HALF_W = (_C_W - OV_GAP) / 2
OV_ACTIONS_CARD = canvas_box(_C_X, _R3_Y, _R3_HALF_W, _R3_H)
OV_DECISIONS_CARD = canvas_box(_C_X + _R3_HALF_W + OV_GAP, _R3_Y, _R3_HALF_W, _R3_H)


# Full-tab cards (one card spanning the whole content area).
FULL_TAB_CARD = canvas_box(_C_X, _C_Y, _C_W, _C_H)


# ── Footer ───────────────────────────────────────────────────────────────
FOOTER_LEFT = canvas_box(24.0, 764.0, 540.0, 20.0)
FOOTER_RIGHT = canvas_box(924.0, 764.0, 312.0, 20.0)
FOOTER_FS_RATIO = 12.0 / CANVAS_H


# ── Typography ───────────────────────────────────────────────────────────
SECTION_TITLE_FS_RATIO = 13.0 / CANVAS_H   # section header label
SECTION_BODY_FS_RATIO = 15.0 / CANVAS_H    # row text, summary body
SECTION_HINT_FS_RATIO = 12.0 / CANVAS_H    # helper/date text


# ── Colours (sampled from the screenshot) ────────────────────────────────
BG_RGB = (242, 242, 247)  # #F2F2F7

# Cards
CARD_FILL = (1.0, 1.0, 1.0, 1.0)
CARD_BORDER = (229 / 255, 229 / 255, 234 / 255, 1.0)  # #E5E5EA
CARD_RADIUS = 16.0

# Sidebar
SIDEBAR_FILL = (1.0, 1.0, 1.0, 1.0)
SIDEBAR_BORDER = (229 / 255, 229 / 255, 234 / 255, 1.0)

# Active tab pill
TAB_ACTIVE_FILL = (0.0, 122 / 255, 1.0, 0.10)  # accent-soft
TAB_ACTIVE_BORDER = (0.0, 122 / 255, 1.0, 0.35)
TAB_ACTIVE_RADIUS = 10.0

# Play recording pill
PLAY_FILL = (1.0, 1.0, 1.0, 1.0)
PLAY_BORDER = (209 / 255, 209 / 255, 214 / 255, 1.0)
PLAY_RADIUS = 980.0

# Progress bar
PROG_TRACK_FILL = (229 / 255, 229 / 255, 234 / 255, 1.0)
PROG_FILL = (0.0, 122 / 255, 1.0, 1.0)
PROG_RADIUS = 4.0

# CTA accent button (used when a tab needs a "View all" link)
ACCENT_BLUE = (0.0, 122 / 255, 1.0, 1.0)

# Text
COL_WHITE = (28 / 255, 28 / 255, 30 / 255, 1.0)  # #1C1C1E
COL_MUTED = (28 / 255, 28 / 255, 30 / 255, 1.0)
COL_HINT = (142 / 255, 142 / 255, 147 / 255, 1.0)
COL_ACCENT = ACCENT_BLUE


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


_FONT_MIN_PX = 10
_FONT_MAX_PX = 96


def font_px(fs_ratio: float, canvas_height: float) -> int:
    raw = round(fs_ratio * canvas_height)
    return max(_FONT_MIN_PX, min(_FONT_MAX_PX, raw))


# ── Sub-card slots inside a single tab content area ──────────────────────
# Used by Key Points / Action Items / Decisions / Participants / Transcript
# full views. The content sits inside FULL_TAB_CARD with consistent padding.

CONTENT_PAD_X = 28.0    # horizontal padding from card edge
CONTENT_PAD_TOP = 24.0  # top padding from card edge
CONTENT_PAD_BOT = 24.0  # bottom padding from card edge

# Header row inside a full card (icon + section title).
def content_header(card: Box, icon_w: float = 36.0, title_w: float = 320.0) -> tuple[Box, Box]:
    x_canvas = card["x"] * CANVAS_W
    y_canvas = card["y_top"] * CANVAS_H
    icon = canvas_box(x_canvas + CONTENT_PAD_X, y_canvas + CONTENT_PAD_TOP, icon_w, icon_w)
    title = canvas_box(x_canvas + CONTENT_PAD_X + icon_w + 12.0, y_canvas + CONTENT_PAD_TOP + 2.0, title_w, icon_w - 4.0)
    return icon, title

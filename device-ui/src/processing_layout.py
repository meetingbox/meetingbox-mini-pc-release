"""Processing screen layout — Figma ``397:261`` (VelsLhL4YHeVRZSCEmCrGw).

Canvas: 1260 × 800.  Every value is the exact Figma absolute coordinate (or the
derived position for stroke layers that overflow their bounding box).

Layer reference (Figma node IDs)::

    414:1232  back button (round)
    415:53    settings button (round)
    399:447   green check badge
    399:432   "Recording complete" headline
    399:434   "Product Sync" meeting title
    399:438   separator dot
    399:436   "32min" duration
    399:456   Ellipse 17 — outer radial glow (orb)
    399:451   Ellipse 16 stroke — solid bright rim (no inset)
    399:477   "Summarizing your meeting…" headline
    399:480   "This may take a few seconds" subtitle
    399:466   3-stage step list card (composite container)
    407:639   "We'll notify you…" bottom pill (composite)

The latest design (Figma 397:261) drops the top-right ``Listening`` pill
and uses three explicit stage rows inside the steps card with loading /
tick icons that toggle as the backend pipeline progresses. The previous
``orb_glow.png`` / ``ring_glow.png`` / ``ring_lighten.png`` exports were
RGB-only with no alpha gradient (they paint as opaque dark rectangles on
top of the navy background — the "weird square" the user reported), so
those layers are dropped here and the orb is drawn from the working
``ring_solid.png`` + ``ring_outer.png`` + the ``glow_orb_outer.png``
soft halo only.
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


# ── Header (top row) ──────────────────────────────────────────────────────
BACK_BTN = canvas_box(24.013, 21.188, 76.278, 76.278)
SETTINGS_BTN = canvas_box(1159.708, 21.188, 76.278, 76.278)


# ── "Recording complete" status row (Group 45) ────────────────────────────
# TITLE_LABEL widened from 180 → 360 px so realistic meeting names ("Q3
# Planning · Engineering & Product") render without an ellipsis. The
# separator dot + duration label slide right by the same delta so the
# row keeps its Figma proportions.
CHECK_BADGE = canvas_box(100.291, 153.968, 46.614, 46.614)
HEADLINE_LABEL = canvas_box(159.617, 152.555, 360.0, 44.0)
TITLE_LABEL = canvas_box(159.617, 199.170, 360.0, 34.0)
DOT_SEPARATOR = canvas_box(528.900, 216.120, 5.65, 5.65)
DURATION_LABEL = canvas_box(550.088, 199.170, 120.0, 34.0)


# ── Centre orb (left half) ────────────────────────────────────────────────
# Only the two layers whose PNG exports actually have usable alpha
# channels are kept (``ring_solid`` + ``ring_outer``). A generous soft
# halo painted by ``glow_orb_outer.png`` sits behind them. The old
# ``orb_glow`` / ``ring_glow`` / ``ring_lighten`` boxes have been
# removed because their PNG exports rendered as opaque dark squares.
_RING_ORIGIN_X = 146.906
_RING_ORIGIN_Y = 292.399
_RING_SIZE = 298.049

# Soft outer halo — the exported PNG is 2676×2676, which we scale down
# to roughly the orb area + ~50 % padding for a soft glow. Anchored to
# the same Figma centre as the rings.
_HALO_SIZE = _RING_SIZE * 1.6
GLOW_OUTER = canvas_box(
    _RING_ORIGIN_X - (_HALO_SIZE - _RING_SIZE) / 2.0,
    _RING_ORIGIN_Y - (_HALO_SIZE - _RING_SIZE) / 2.0,
    _HALO_SIZE,
    _HALO_SIZE,
)
RING_SOLID = canvas_box(_RING_ORIGIN_X, _RING_ORIGIN_Y, _RING_SIZE, _RING_SIZE)
RING_OUTER = canvas_box(
    _RING_ORIGIN_X - _RING_SIZE * 0.019,
    _RING_ORIGIN_Y,
    _RING_SIZE * 1.038,
    _RING_SIZE * 1.0379,
)


# ── Bottom-left captions (under orb) ──────────────────────────────────────
HEADLINE_BOTTOM = canvas_box(49.439, 649.776, 540.0, 44.0)
SUBTITLE_BOTTOM = canvas_box(49.439, 707.691, 540.0, 34.0)


# ── Right-side cards ──────────────────────────────────────────────────────
# ``STEPS_CARD`` is the glass-card background (drawn with Kivy primitives
# below) that hosts the three live stage rows. The rows are positioned
# relative to the card's top-left corner. ``NOTIFY_BAR`` is the bottom
# pill that flips between "We'll notify you..." (still processing) and
# the bright "View Meeting Summary" CTA once the summary is ready.
STEPS_CARD = canvas_box(577.735, 261.323, 639.888, 251.435)
NOTIFY_BAR = canvas_box(569.260, 542.422, 658.251, 76.278)

# Stage rows inside ``STEPS_CARD`` — Figma 397:261 names them
# (top to bottom):
#   * Extracting key points
#   * Identifying action items
#   * Structuring summary
_STAGE_CARD_X = 577.735
_STAGE_CARD_Y = 261.323
_STAGE_CARD_W = 639.888
_STAGE_CARD_H = 251.435

_STAGE_PAD_TOP = 28.0
_STAGE_PAD_LEFT = 21.0
_STAGE_PAD_RIGHT = 28.0
_STAGE_ICON_W = 50.852
_STAGE_STATUS_W = 49.439
_STAGE_ROW_H = 51.0
_STAGE_ROW_GAP = (_STAGE_CARD_H - 2 * _STAGE_PAD_TOP - 3 * _STAGE_ROW_H) / 2.0
_STAGE_LABEL_X = _STAGE_PAD_LEFT + _STAGE_ICON_W + 28.0


def _stage_row(row_idx: int) -> tuple[Box, Box, Box]:
    """Return (icon_box, label_box, status_box) for a stage row inside the card."""
    y_top = _STAGE_CARD_Y + _STAGE_PAD_TOP + row_idx * (_STAGE_ROW_H + _STAGE_ROW_GAP)
    icon = canvas_box(
        _STAGE_CARD_X + _STAGE_PAD_LEFT,
        y_top,
        _STAGE_ICON_W,
        _STAGE_ROW_H,
    )
    label_w = _STAGE_CARD_W - _STAGE_LABEL_X - _STAGE_PAD_RIGHT - _STAGE_STATUS_W - 8.0
    label = canvas_box(
        _STAGE_CARD_X + _STAGE_LABEL_X,
        y_top,
        label_w,
        _STAGE_ROW_H,
    )
    status = canvas_box(
        _STAGE_CARD_X + _STAGE_CARD_W - _STAGE_PAD_RIGHT - _STAGE_STATUS_W,
        y_top + (_STAGE_ROW_H - _STAGE_STATUS_W) / 2.0,
        _STAGE_STATUS_W,
        _STAGE_STATUS_W,
    )
    return icon, label, status


STAGE_KEY_POINTS_ICON, STAGE_KEY_POINTS_LABEL, STAGE_KEY_POINTS_STATUS = _stage_row(0)
STAGE_ACTION_ITEMS_ICON, STAGE_ACTION_ITEMS_LABEL, STAGE_ACTION_ITEMS_STATUS = _stage_row(1)
STAGE_SUMMARY_ICON, STAGE_SUMMARY_LABEL, STAGE_SUMMARY_STATUS = _stage_row(2)

STAGE_FS_RATIO = 24.0 / CANVAS_H


# ── Typography (Figma px on 800-tall canvas) ──────────────────────────────
HEADLINE_FS_RATIO = 36.726 / CANVAS_H   # "Recording complete", "Summarizing…"
TITLE_FS_RATIO = 28.251 / CANVAS_H      # "Product Sync"
DURATION_FS_RATIO = 28.251 / CANVAS_H
SUBTITLE_FS_RATIO = 28.251 / CANVAS_H


# ── Colours (sampled from Figma) ──────────────────────────────────────────
BG_RGB = (1, 8, 26)  # #01081A

COL_WHITE = (1.0, 1.0, 1.0, 1.0)
COL_MUTED = (182 / 255, 186 / 255, 242 / 255, 1.0)   # #B6BAF2
COL_HINT = (155 / 255, 162 / 255, 178 / 255, 1.0)    # #9BA2B2 (notify bar text)
COL_BLUE = (0 / 255, 149 / 255, 255 / 255, 1.0)      # #0095FF (ring stroke)


def scaled_canvas(screen_w: float, screen_h: float) -> tuple[float, float]:
    """Aspect-preserving canvas size for the current screen.

    Uses ``min(sw/cw, sh/ch)`` so design proportions (circles, ring radii,
    composite aspect ratios) survive on any monitor. The remaining screen
    area is filled by the root background colour so the UI always covers
    the whole display.
    """
    if screen_w <= 0 or screen_h <= 0:
        return CANVAS_W, CANVAS_H
    scale = min(screen_w / CANVAS_W, screen_h / CANVAS_H)
    return CANVAS_W * scale, CANVAS_H * scale


def kivy_hints(box: Box) -> dict:
    return {
        "size_hint": (box["w"], box["h"]),
        "pos_hint": {"x": box["x"], "y": 1.0 - box["y_top"] - box["h"]},
    }


# Minimum/maximum font size guards. The min keeps text readable on tiny
# panels (e.g. 800×480) and the cap stops the headline from looking
# cartoonish on 4K displays where the canvas height is huge.
_FONT_MIN_PX = 10
_FONT_MAX_PX = 96


def font_px(fs_ratio: float, canvas_height: float) -> int:
    raw = round(fs_ratio * canvas_height)
    return max(_FONT_MIN_PX, min(_FONT_MAX_PX, raw))

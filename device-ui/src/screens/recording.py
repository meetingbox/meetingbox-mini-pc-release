"""Recording screen — Figma node ``408:657`` (file yJqcY4KovVjJ11vjysW533).

Design canvas: 1260 × 800 px.

ANCHORING SYSTEM
================
The Figma design is treated as a fixed 1260 × 800 canvas. A single uniform
scale ``S = min(DISPLAY_W / 1260, DISPLAY_H / 800)`` preserves the design
aspect ratio. The scaled canvas is then centred inside the actual display
(so any leftover space appears as background-coloured letterbox bars on the
short axis).

Every widget is placed with an ABSOLUTE pos and size computed directly from
its Figma coordinates via ``_pos()`` and ``_s()``. We never use ``pos_hint``
in the main layout, never nest layouts for grouping, and never rely on
"child of a button is centred via pos_hint" magic — which is what made
the earlier versions float around.

Coordinate helpers
------------------
* ``_s(v)``           — scale a length (px / font / radius) by ``S``.
* ``_pos(fx, fy,
        fw, fh)``     — turn Figma top-left (fx, fy) + Figma size (fw, fh)
                        into a Kivy bottom-left absolute (x, y).
* ``_ff(pt)``         — scale a font size.

Layout (top → bottom, Figma coords):
- Back button             : (24,     21.19, 76.278, 76.278)
- Recording status row    : dot (124.31, 36.73) + "Recording..." + sub
- Meeting info row        : people / title / participants / video / provider
- Listening pill          : (911.1,  21.19, 302.287, 76.278)
- Ring + waveform centre  : (601, 258.67)
- Timer                   : (496, 428, w=280, h=46)  – font 35
- "Recording in progress" : (454, 476, w=360, h=36)  – font 28.251
- Pause button (circle)   : centre (197.76, 712.58),  ⌀ 101.704
- Stop pill               : (285.33, 666.73, 646.951, 101.704)
- Settings button         : centre (1019.87, 712.58), ⌀ 101.704
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from datetime import datetime

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from async_helper import run_async
from config import (
    ASSETS_DIR,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    display_now,
)
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

_REC_ASSETS = ASSETS_DIR / "recording"

# ---------------------------------------------------------------------------
# Anchoring helpers — Figma 1260 × 800  →  device pixels
# ---------------------------------------------------------------------------
_FW = 1260.0
_FH = 800.0


def _scale() -> float:
    return min(DISPLAY_WIDTH / _FW, DISPLAY_HEIGHT / _FH)


def _ox() -> float:
    """Letterbox offset on the X axis (px from screen left to design left)."""
    return (DISPLAY_WIDTH - _FW * _scale()) / 2.0


def _oy() -> float:
    """Letterbox offset on the Y axis (px from screen bottom to design bot.)."""
    return (DISPLAY_HEIGHT - _FH * _scale()) / 2.0


def _s(v: float) -> int:
    """Scale a single dimension (width / height / radius / spacing)."""
    return max(1, int(round(v * _scale())))


def _pos(fx: float, fy: float, fw: float = 0.0, fh: float = 0.0) -> tuple:
    """Figma top-left (fx, fy) + Figma size (fw, fh)  →  Kivy bottom-left (x, y)."""
    s = _scale()
    x = _ox() + fx * s
    y = _oy() + (_FH - fy - fh) * s
    return (x, y)


def _ff(pt: float) -> int:
    return max(6, int(round(pt * _scale())))


# ---------------------------------------------------------------------------
# Exact Figma colours
# ---------------------------------------------------------------------------
_BG             = (0.004, 0.031, 0.102, 1.0)   # #01081A
_FILL_BTN       = (0.004, 0.043, 0.149, 1.0)   # #010B26
_FILL_STOP_T    = (0.008, 0.071, 0.235, 1.0)   # #02123C
_FILL_STOP_B    = (0.000, 0.039, 0.149, 1.0)   # #000A26
_FILL_LISTEN    = (0.000, 0.059, 0.200, 1.0)   # #000F33
_BORDER         = (0.247, 0.259, 0.325, 1.0)   # #3F4253
_BORDER_LISTEN  = (0.129, 0.157, 0.294, 1.0)   # #21284B
_MUTED          = (0.714, 0.729, 0.949, 1.0)   # #B6BAF2
_BLUE           = (0.000, 0.420, 0.976, 1.0)   # #006BF9
_RED            = (0.960, 0.270, 0.300, 1.0)
_WHITE          = (1.0, 1.0, 1.0, 1.0)
_RING_GLOW      = (0.000, 0.122, 0.404, 0.55)
_RING_GLOW_FAR  = (0.000, 0.122, 0.404, 0.25)
_RING_DEEP      = (0.000, 0.165, 0.506, 1.0)   # #002A81
_RING_BLUE      = (0.000, 0.350, 1.000, 1.0)   # #0059FF
_RING_CYAN      = (0.663, 0.929, 1.000, 0.90)  # #A9EDFF
_RING_DOT       = (0.275, 0.490, 0.996, 1.0)   # #467DFE


def _rec_png(name: str) -> str:
    p = _REC_ASSETS / name
    return str(p) if p.is_file() else ""


# ---------------------------------------------------------------------------
# Visual building blocks — all positioned by absolute pos / size by caller
# ---------------------------------------------------------------------------

class _CircleButton(ButtonBehavior, Widget):
    """A round dark-navy bordered circle button. No children. The icon that
    appears on top is a sibling widget placed at its own absolute position
    (so it cannot drift relative to the button)."""

    def __init__(self, fill=_FILL_BTN, border=_BORDER, **kw):
        kw.setdefault("size_hint", (None, None))
        super().__init__(**kw)
        with self.canvas.before:
            Color(*fill)
            self._bg = Ellipse(pos=self.pos, size=self.size)
            Color(*border)
            self._stroke = Line(
                circle=(self.center_x, self.center_y,
                        max(self.width, self.height) / 2),
                width=1.2,
            )
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._stroke.circle = (
            self.center_x, self.center_y,
            max(self.width, self.height) / 2,
        )


class _StopPill(ButtonBehavior, Widget):
    """Pill with darker bottom half + outer border. No children — the inner
    blue square and label are sibling widgets placed by the caller."""

    def __init__(self, fill_top, fill_bottom, border, radius, **kw):
        kw.setdefault("size_hint", (None, None))
        super().__init__(**kw)
        self._radius = radius
        with self.canvas.before:
            Color(*fill_top)
            self._bg_t = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[radius]
            )
            Color(*fill_bottom)
            self._bg_b = RoundedRectangle(
                pos=self.pos,
                size=(self.width, self.height * 0.5),
                radius=[0, 0, radius, radius],
            )
            Color(*border)
            self._stroke = Line(
                rounded_rectangle=(
                    self.x, self.y, self.width, self.height, radius
                ),
                width=1.4,
            )
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        r = self._radius
        self._bg_t.pos = self.pos
        self._bg_t.size = self.size
        self._bg_t.radius = [r]
        self._bg_b.pos = self.pos
        self._bg_b.size = (self.width, self.height * 0.5)
        self._bg_b.radius = [0, 0, r, r]
        self._stroke.rounded_rectangle = (
            self.x, self.y, self.width, self.height, r
        )


class _ListenPillBG(Widget):
    """Listening pill background (no button behaviour)."""

    def __init__(self, fill, border, radius, **kw):
        kw.setdefault("size_hint", (None, None))
        super().__init__(**kw)
        self._radius = radius
        with self.canvas.before:
            Color(*fill)
            self._bg = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[radius]
            )
            Color(*border)
            self._stroke = Line(
                rounded_rectangle=(
                    self.x, self.y, self.width, self.height, radius
                ),
                width=1.3,
            )
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        r = self._radius
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bg.radius = [r]
        self._stroke.rounded_rectangle = (
            self.x, self.y, self.width, self.height, r
        )


class _Waveform(Widget):
    NUM_BARS = 28

    def __init__(self, **kw):
        self.BAR_W = max(2, _s(4.6))
        self.BAR_S = max(1, _s(4.6))
        self.MAX_H = max(4, _s(68))
        total_w = self.NUM_BARS * self.BAR_W + (self.NUM_BARS - 1) * self.BAR_S
        kw.setdefault("size_hint", (None, None))
        kw.setdefault("size", (total_w, self.MAX_H * 2))
        super().__init__(**kw)
        self._levels = [2] * self.NUM_BARS
        self.bind(pos=self._draw, size=self._draw)
        # bind() above fires on FUTURE pos/size changes only — draw once now.
        self._draw()

    def set_levels(self, levels: list):
        self._levels = levels
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        total_w = self.NUM_BARS * self.BAR_W + (self.NUM_BARS - 1) * self.BAR_S
        sx = self.x + (self.width - total_w) / 2
        my = self.center_y
        with self.canvas:
            for i, h in enumerate(self._levels):
                half = max(1, h / 2)
                Color(*_BLUE)
                bx = sx + i * (self.BAR_W + self.BAR_S)
                RoundedRectangle(
                    pos=(bx, my - half),
                    size=(self.BAR_W, half * 2),
                    radius=[max(1, _s(2))],
                )


class _RingCanvas(Widget):
    """Orbital ring + glow + decorative dots, drawn directly in Kivy canvas.
    Centre is the widget's centre."""

    def __init__(self, **kw):
        kw.setdefault("size_hint", (None, None))
        super().__init__(**kw)
        self.bind(pos=self._draw, size=self._draw)
        # Force the initial render — pos/size set via kwargs do NOT fire bind.
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        cx = self.center_x
        cy = self.center_y
        radius = _s(108)
        glow_r = _s(143)

        with self.canvas:
            Color(*_RING_GLOW)
            Ellipse(pos=(cx - glow_r, cy - glow_r),
                    size=(glow_r * 2, glow_r * 2))

            Color(*_RING_GLOW_FAR)
            g2 = int(glow_r * 1.35)
            Ellipse(pos=(cx - g2, cy - g2), size=(g2 * 2, g2 * 2))

            Color(*_RING_DEEP)
            Line(circle=(cx, cy, radius), width=2.0)
            Color(*_RING_BLUE)
            Line(circle=(cx, cy, radius - 0.5), width=1.6)
            Color(*_RING_CYAN)
            Line(circle=(cx, cy, radius - 1.0), width=0.9)

            dot_specs = [
                (1.473, 0,    4.996),
                (1.424, 30,   2.998),
                (1.424, -30,  2.998),
                (1.369, 57,   1.999),
                (1.369, -57,  1.999),
                (1.263, 80,   0.999),
                (1.263, -80,  0.999),
                (1.473, 180,  4.996),
                (1.424, 150,  2.998),
                (1.424, -150, 2.998),
                (1.369, 123,  1.999),
                (1.369, -123, 1.999),
                (1.263, 100,  0.999),
                (1.263, -100, 0.999),
            ]
            Color(*_RING_DOT)
            for r_ratio, angle_deg, dot_fig_r in dot_specs:
                ang = math.radians(angle_deg)
                dx = cx + radius * r_ratio * math.cos(ang)
                dy = cy + radius * r_ratio * math.sin(ang)
                dr = max(1, _s(dot_fig_r))
                Ellipse(pos=(dx - dr, dy - dr), size=(dr * 2, dr * 2))


# ---------------------------------------------------------------------------
# Tiny helpers used during build
# ---------------------------------------------------------------------------

def _place_image(source, fx, fy, fw, fh, color=None):
    """Build an Image widget at absolute Figma rect."""
    x, y = _pos(fx, fy, fw, fh)
    img = Image(
        source=source,
        size=(_s(fw), _s(fh)),
        pos=(x, y),
        size_hint=(None, None),
        fit_mode="contain",
        allow_stretch=True,
    )
    if color is not None:
        img.color = color
    return img


def _place_label(text, fx, fy, fw, fh, *, font, bold=False,
                 color=_WHITE, halign="left"):
    x, y = _pos(fx, fy, fw, fh)
    w, h = _s(fw), _s(fh)
    lbl = Label(
        text=text,
        font_size=_ff(font),
        bold=bold,
        color=color,
        halign=halign,
        valign="middle",
        size_hint=(None, None),
        size=(w, h),
        pos=(x, y),
        text_size=(w, h),
        shorten=True,
        shorten_from="right",
    )
    return lbl


def _place_solid_rect(fx, fy, fw, fh, color, radius_fig=0.0):
    """A coloured rectangle (solid fill, optional rounded corners)."""
    x, y = _pos(fx, fy, fw, fh)
    w, h = _s(fw), _s(fh)
    widget = Widget(size=(w, h), pos=(x, y), size_hint=(None, None))
    r = _s(radius_fig) if radius_fig else 0
    with widget.canvas:
        Color(*color)
        if r:
            shape = RoundedRectangle(pos=widget.pos, size=widget.size,
                                     radius=[r])
        else:
            shape = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda w, _, s=shape: setattr(s, "pos", w.pos),
        size=lambda w, _, s=shape: setattr(s, "size", w.size),
    )
    return widget


# ===========================================================================
# RecordingScreen
# ===========================================================================

class RecordingScreen(BaseScreen):

    def __init__(self, **kw):
        super().__init__(**kw)
        self.elapsed_seconds = 0
        self.timer_event = None
        self.waveform_event = None
        self._is_paused = False
        self._level_history = deque(
            [0.0] * _Waveform.NUM_BARS, maxlen=_Waveform.NUM_BARS
        )
        self._last_audio_level_ts = 0.0
        self._rec_base_elapsed = 0.0
        self._rec_active_start = None
        self._meeting_title = "Recording"
        self._participant_count = 0
        self._meeting_provider = ""
        self._started_at_str = ""
        self._build_ui()

    # ------------------------------------------------------------------
    # BUILD — every element placed by absolute Figma (fx, fy, fw, fh)
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = FloatLayout()
        with root.canvas.before:
            Color(*_BG)
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, _: setattr(self._bg, "pos", w.pos),
            size=lambda w, _: setattr(self._bg, "size", w.size),
        )
        self.root_layout = root

        # ===== HEADER: back button =====
        bw = bh = 76.278
        self.back_btn = self._add(root, _CircleButton(
            size=(_s(bw), _s(bh)),
            pos=_pos(24, 21.19, bw, bh),
        ))
        self.back_btn.bind(on_release=lambda *_: self.go_back())

        # back arrow icon (sibling, centred inside the back button's rect)
        arrow_fig = 36.0
        arrow_fx = 24 + (bw - arrow_fig) / 2
        arrow_fy = 21.19 + (bh - arrow_fig) / 2
        arrow_src = _rec_png("icon_back_arrow.png")
        if arrow_src:
            self._add(root, _place_image(
                arrow_src, arrow_fx, arrow_fy, arrow_fig, arrow_fig,
            ))
        else:
            self._add(root, _place_label(
                "←", arrow_fx, arrow_fy, arrow_fig, arrow_fig,
                font=24, bold=True, color=_WHITE, halign="center",
            ))

        # ===== HEADER: "Recording..." status =====
        dot_src = _rec_png("icon_recording_dot.png")
        if dot_src:
            self._add(root, _place_image(
                dot_src, 124.31, 36.73, 19.776, 19.776,
            ))
        else:
            self._add(root, _place_solid_rect(
                124.31, 36.73, 19.776, 19.776,
                color=_RED, radius_fig=19.776 / 2,
            ))

        self.rec_state_label = self._add(root, _place_label(
            "Recording...", 151.14, 29.66, 290, 38,
            font=28.251, bold=True, color=_WHITE,
        ))

        self.started_at_label = self._add(root, _place_label(
            "Started at --:-- --", 124.31, 63.56, 260, 28,
            font=21.188, color=_MUTED,
        ))

        # ===== HEADER: meeting info (centre) =====
        ppl_src = _rec_png("icon_people.png")
        if ppl_src:
            self._add(root, _place_image(
                ppl_src, 484.51, 11.3, 48.027, 48.027,
            ))

        self.meeting_title_label = self._add(root, _place_label(
            "Recording", 535.36, 18.36, 380, 38,
            font=28.251, bold=True, color=_WHITE,
        ))

        self.participants_label = self._add(root, _place_label(
            "", 468.97, 63.57, 190, 28,
            font=21.188, bold=True, color=_BLUE,
        ))

        vid_src = _rec_png("icon_video.png")
        if vid_src:
            self._add(root, _place_image(
                vid_src, 632.83, 63.57, 25.426, 25.426,
            ))

        self.provider_label = self._add(root, _place_label(
            "", 666.73, 63.57, 200, 28,
            font=21.188, color=_MUTED,
        ))

        # ===== HEADER: Listening pill =====
        lp_fx, lp_fy = 911.1, 21.19
        lp_fw, lp_fh = 302.287, 76.278
        listen_radius = _s(76.278)
        self._add(root, _ListenPillBG(
            fill=_FILL_LISTEN, border=_BORDER_LISTEN,
            radius=listen_radius,
            size=(_s(lp_fw), _s(lp_fh)),
            pos=_pos(lp_fx, lp_fy, lp_fw, lp_fh),
        ))

        ldot_src = _rec_png("icon_listening_dot.png")
        ldot_fig = 19.776
        if ldot_src:
            ldot_fx = lp_fx + 36.73
            ldot_fy = lp_fy + (lp_fh - ldot_fig) / 2
            self._add(root, _place_image(
                ldot_src, ldot_fx, ldot_fy, ldot_fig, ldot_fig,
            ))

        listen_text_fx = lp_fx + 80.52
        listen_text_fy = lp_fy + (lp_fh - 36) / 2
        self._add(root, _place_label(
            "Listening", listen_text_fx, listen_text_fy, 140, 36,
            font=28.251, bold=True, color=_WHITE,
        ))

        sw_src = _rec_png("icon_soundwave.png")
        sw_fig = 45.202
        if sw_src:
            sw_fx = lp_fx + 224.6
            sw_fy = lp_fy + (lp_fh - sw_fig) / 2
            self._add(root, _place_image(
                sw_src, sw_fx, sw_fy, sw_fig, sw_fig, color=_BLUE,
            ))

        # ===== CENTRE: orbital ring + waveform =====
        ring_fig = 320.0
        ring_fx = 601 - ring_fig / 2
        ring_fy = 258.67 - ring_fig / 2
        ring_w = _s(ring_fig)
        ring_pos = _pos(ring_fx, ring_fy, ring_fig, ring_fig)
        self.ring = self._add(root, _RingCanvas(
            size=(ring_w, ring_w), pos=ring_pos,
        ))

        self.waveform = _Waveform()
        wf_x = ring_pos[0] + ring_w / 2 - self.waveform.width / 2
        wf_y = ring_pos[1] + ring_w / 2 - self.waveform.height / 2
        self.waveform.pos = (wf_x, wf_y)
        self._add(root, self.waveform)

        # ===== CENTRE: Timer =====
        self.timer_label = self._add(root, _place_label(
            "00 : 00 : 00", 496, 428, 280, 46,
            font=35, bold=True, color=_WHITE, halign="center",
        ))

        # ===== CENTRE: "Recording in progress" =====
        self.elapsed_sub = self._add(root, _place_label(
            "Recording in progress", 454, 476, 360, 36,
            font=28.251, bold=True, color=_MUTED, halign="center",
        ))

        # ===== BOTTOM: Pause button =====
        pb_size = 101.704
        pb_cx, pb_cy = 197.76, 712.58
        pb_fx = pb_cx - pb_size / 2
        pb_fy = pb_cy - pb_size / 2
        self.pause_btn = self._add(root, _CircleButton(
            size=(_s(pb_size), _s(pb_size)),
            pos=_pos(pb_fx, pb_fy, pb_size, pb_size),
        ))
        self.pause_btn.bind(on_release=self._on_pause)

        # pause icon: two vertical bars centred in the circle
        bar_fw = 11.3
        bar_fh = 35.314
        bar_gap = 9.89
        bars_total_w = bar_fw * 2 + bar_gap
        bar_fx_left = pb_cx - bars_total_w / 2
        bar_fy = pb_cy - bar_fh / 2

        self._add(root, _place_solid_rect(
            bar_fx_left, bar_fy, bar_fw, bar_fh,
            color=_BLUE, radius_fig=2.825,
        ))
        self._add(root, _place_solid_rect(
            bar_fx_left + bar_fw + bar_gap, bar_fy, bar_fw, bar_fh,
            color=_BLUE, radius_fig=2.825,
        ))

        # ===== BOTTOM: Stop pill =====
        sp_fx, sp_fy = 285.33, 666.73
        sp_fw, sp_fh = 646.951, 101.704
        sp_radius = _s(163.857)
        self.stop_pill = self._add(root, _StopPill(
            fill_top=_FILL_STOP_T, fill_bottom=_FILL_STOP_B,
            border=_BORDER, radius=sp_radius,
            size=(_s(sp_fw), _s(sp_fh)),
            pos=_pos(sp_fx, sp_fy, sp_fw, sp_fh),
        ))
        self.stop_pill.bind(on_release=self._on_stop)

        # stop icon: small blue rounded square (rel x=139.84 inside pill)
        sq_fig = 38.139
        sq_fx = sp_fx + 139.84
        sq_fy = sp_fy + (sp_fh - sq_fig) / 2
        self._add(root, _place_solid_rect(
            sq_fx, sq_fy, sq_fig, sq_fig,
            color=_BLUE, radius_fig=5.65,
        ))

        # "Stop recording" label (rel x=223.18 inside pill)
        st_lbl_fx = sp_fx + 223.18
        st_lbl_fy = sp_fy + (sp_fh - 56) / 2
        self._add(root, _place_label(
            "Stop recording", st_lbl_fx, st_lbl_fy, 380, 56,
            font=42.377, bold=True, color=_WHITE, halign="left",
        ))

        # ===== BOTTOM: Settings (gear) button =====
        gb_size = 101.704
        gb_cx, gb_cy = 1019.87, 712.58
        gb_fx = gb_cx - gb_size / 2
        gb_fy = gb_cy - gb_size / 2
        self.gear_btn = self._add(root, _CircleButton(
            size=(_s(gb_size), _s(gb_size)),
            pos=_pos(gb_fx, gb_fy, gb_size, gb_size),
        ))
        self.gear_btn.bind(
            on_release=lambda *_: self.goto(
                "settings", transition="slide_left")
        )

        gear_src = _rec_png("icon_settings_gear.png")
        if gear_src:
            gear_fig = 56.502
            gear_fx = gb_cx - gear_fig / 2
            gear_fy = gb_cy - gear_fig / 2
            self._add(root, _place_image(
                gear_src, gear_fx, gear_fy, gear_fig, gear_fig,
            ))

        # ===== PAUSED OVERLAY (full-screen card) =====
        self.paused_overlay = FloatLayout(
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
            opacity=0,
        )
        with self.paused_overlay.canvas.before:
            Color(0.004, 0.031, 0.102, 0.96)
            self._ov_bg = Rectangle(
                pos=self.paused_overlay.pos,
                size=self.paused_overlay.size,
            )
        self.paused_overlay.bind(
            pos=lambda w, _: setattr(self._ov_bg, "pos", w.pos),
            size=lambda w, _: setattr(self._ov_bg, "size", w.size),
        )

        ov_card = FloatLayout(
            size_hint=(None, None),
            size=(_s(560), _s(340)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        with ov_card.canvas.before:
            Color(0.012, 0.043, 0.169, 1.0)
            self._ov_card_bg = RoundedRectangle(
                pos=ov_card.pos, size=ov_card.size, radius=[_s(20)]
            )
            Color(*_BORDER)
            self._ov_card_stroke = Line(
                rounded_rectangle=(
                    ov_card.x, ov_card.y,
                    _s(560), _s(340), _s(20),
                ),
                width=1.0,
            )

        def _sync_ov(w, _):
            self._ov_card_bg.pos = w.pos
            self._ov_card_bg.size = w.size
            self._ov_card_bg.radius = [_s(20)]
            self._ov_card_stroke.rounded_rectangle = (
                w.x, w.y, w.width, w.height, _s(20)
            )

        ov_card.bind(pos=_sync_ov, size=_sync_ov)

        def _ovlbl(text, fs, color, bold=False):
            lbl = Label(
                text=text,
                font_size=_ff(fs),
                bold=bold,
                color=color,
                halign="center",
                valign="middle",
                size_hint=(0.9, None),
                height=_s(48 if bold else 32),
                pos_hint={"center_x": 0.5},
            )
            lbl.bind(size=lbl.setter("text_size"))
            return lbl

        self.paused_title     = _ovlbl("Paused at --:--", 38, _WHITE, bold=True)
        self.ov_meeting_label = _ovlbl("Recording", 22, _BLUE, bold=True)
        self.paused_duration  = _ovlbl("Meeting duration: 00:00", 18, _MUTED)
        self.ov_room_label    = _ovlbl("MeetingBox", 14, _MUTED)

        ov_inner = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            spacing=_s(10),
            padding=[_s(28), _s(28), _s(28), _s(28)],
        )
        ov_inner.add_widget(self.paused_title)
        ov_inner.add_widget(self.ov_meeting_label)
        ov_inner.add_widget(self.paused_duration)
        ov_inner.add_widget(Widget())
        ov_inner.add_widget(self.ov_room_label)
        ov_card.add_widget(ov_inner)
        self.paused_overlay.add_widget(ov_card)

        self.add_widget(root)

    # Small helper so we can do `var = self._add(parent, Widget(…))` inline
    @staticmethod
    def _add(parent, widget):
        parent.add_widget(widget)
        return widget

    # ------------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------------
    def on_enter(self):
        if self.timer_event:
            self.timer_event.cancel()
        if self.waveform_event:
            self.waveform_event.cancel()

        self._is_paused = False
        self.elapsed_seconds = 0
        self._rec_base_elapsed = 0.0
        self._rec_active_start = time.monotonic()
        self.timer_label.text = "00 : 00 : 00"
        self.elapsed_sub.text = "Recording in progress"
        self.rec_state_label.text = "Recording..."
        self.rec_state_label.color = _WHITE
        self._level_history = deque(
            [0.0] * _Waveform.NUM_BARS, maxlen=_Waveform.NUM_BARS
        )
        self._last_audio_level_ts = 0.0

        if self.paused_overlay.parent is self.root_layout:
            self.root_layout.remove_widget(self.paused_overlay)

        now = display_now()
        self._started_at_str = now.strftime("%I:%M %p").lstrip("0")
        self.started_at_label.text = f"Started at {self._started_at_str}"
        self.meeting_title_label.text = "Recording"
        self.participants_label.text = ""
        self.provider_label.text = ""

        sid = getattr(self.app, "current_session_id", None)
        if sid:
            self._fetch_meeting_metadata(sid)

        self.timer_event = Clock.schedule_interval(self._tick_timer, 0.5)
        self.waveform_event = Clock.schedule_interval(
            self._tick_waveform, 0.08
        )

    def on_leave(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None
        if self.waveform_event:
            self.waveform_event.cancel()
            self.waveform_event = None

    # ------------------------------------------------------------------
    # Meeting metadata
    # ------------------------------------------------------------------
    def _fetch_meeting_metadata(self, meeting_id: str):
        async def _run():
            try:
                detail = await self.backend.get_meeting_detail(meeting_id)
            except Exception as exc:
                logger.debug("recording: meeting detail fetch failed: %s", exc)
                return
            title = (detail.get("title") or "Recording").strip() or "Recording"
            try:
                participants = int(
                    detail.get("participant_count")
                    or detail.get("attendee_count")
                    or 0
                )
            except (TypeError, ValueError):
                participants = 0
            provider = (
                (detail.get("source") or "")
                or (detail.get("calendar_source") or "")
            ).strip()

            def _apply(_dt):
                self._meeting_title = title
                self._participant_count = participants
                self._meeting_provider = provider
                self.meeting_title_label.text = title
                if participants:
                    self.participants_label.text = (
                        f"{participants} Participants"
                        if participants != 1
                        else "1 Participant"
                    )
                else:
                    self.participants_label.text = ""
                self.provider_label.text = provider
                self.ov_meeting_label.text = title

            Clock.schedule_once(_apply, 0)

        run_async(_run())

    # ------------------------------------------------------------------
    # Timer
    # ------------------------------------------------------------------
    def _elapsed_from_monotonic(self) -> int:
        if self._is_paused or self._rec_active_start is None:
            return int(self._rec_base_elapsed)
        return int(
            self._rec_base_elapsed
            + (time.monotonic() - self._rec_active_start)
        )

    def _tick_timer(self, _dt):
        self.elapsed_seconds = self._elapsed_from_monotonic()
        self.timer_label.text = self._fmt_time(self.elapsed_seconds)

    @staticmethod
    def _fmt_time(secs: int) -> str:
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        return f"{h:02d} : {m:02d} : {s:02d}"

    # ------------------------------------------------------------------
    # Pause / Resume
    # ------------------------------------------------------------------
    def _on_pause(self, _inst):
        if self._is_paused:
            self.app.resume_recording()
        else:
            self.app.pause_recording()

    def on_paused(self):
        if self._is_paused:
            return
        self._is_paused = True
        if self._rec_active_start is not None:
            self._rec_base_elapsed += (
                time.monotonic() - self._rec_active_start
            )
            self._rec_active_start = None

        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None
        if self.waveform_event:
            self.waveform_event.cancel()
            self.waveform_event = None

        self.waveform.set_levels([2] * _Waveform.NUM_BARS)
        self.rec_state_label.text = "Paused"
        self.elapsed_sub.text = "Recording paused"

        now = display_now()
        self.paused_title.text = (
            f"Paused at {now.strftime('%I:%M %p').lstrip('0')}"
        )
        self.paused_duration.text = (
            f"Meeting duration: {self._fmt_time(self.elapsed_seconds)}"
        )
        self.ov_room_label.text = getattr(self.app, "device_name", "MeetingBox")
        self.ov_meeting_label.text = self._meeting_title or "Recording"

        if self.paused_overlay.parent is not self.root_layout:
            self.root_layout.add_widget(self.paused_overlay)
        self.paused_overlay.opacity = 0
        Animation(opacity=1, duration=0.25).start(self.paused_overlay)

    def on_resumed(self):
        if not self._is_paused:
            return
        self._is_paused = False
        self._rec_active_start = time.monotonic()

        Animation(opacity=0, duration=0.2).start(self.paused_overlay)
        Clock.schedule_once(self._hide_paused_overlay, 0.25)

        self.rec_state_label.text = "Recording..."
        self.elapsed_sub.text = "Recording in progress"
        if self.timer_event:
            self.timer_event.cancel()
        if self.waveform_event:
            self.waveform_event.cancel()
        self.timer_event = Clock.schedule_interval(self._tick_timer, 1.0)
        self.waveform_event = Clock.schedule_interval(
            self._tick_waveform, 0.08
        )

    def _hide_paused_overlay(self, _dt):
        if self.paused_overlay.parent is self.root_layout:
            self.root_layout.remove_widget(self.paused_overlay)

    # ------------------------------------------------------------------
    # Audio level → waveform
    # ------------------------------------------------------------------
    def on_audio_level(self, level: float):
        if self._is_paused:
            return
        gated = 0.0 if level < 0.015 else min(1.0, level)
        self._level_history.append(gated)
        self._last_audio_level_ts = datetime.now().timestamp()

    def _tick_waveform(self, _dt):
        if self._is_paused:
            return
        now_ts = datetime.now().timestamp()
        if now_ts - self._last_audio_level_ts > 0.25:
            self._level_history = deque(
                [v * 0.82 for v in self._level_history],
                maxlen=_Waveform.NUM_BARS,
            )
        levels = [
            max(2, int(v * self.waveform.MAX_H))
            for v in self._level_history
        ]
        self.waveform.set_levels(levels)

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------
    def _on_stop(self, _inst):
        logger.info(
            "End Meeting pressed (duration: %s)",
            self._fmt_time(self.elapsed_seconds),
        )
        self.app.stop_recording()

    # ------------------------------------------------------------------
    # External events from main.py
    # ------------------------------------------------------------------
    def on_audio_segment(self, segment_num: int):
        if self._participant_count == 0 and segment_num >= 0:
            pc = max(1, segment_num + 1)
            self._participant_count = pc
            self.participants_label.text = (
                f"{pc} Participants" if pc != 1 else "1 Participant"
            )

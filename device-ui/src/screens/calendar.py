"""Calendar screen — pixel-perfect from Figma 927:61 (1260 × 800 px).

Root cause of previous bugs:
  1. _DayCell._build_once fired via Clock.schedule_once *before* layout set actual
     widget sizes (Kivy default is 100 × 100), so every pos_hint fraction was
     computed against the wrong height → labels rendered outside the widget.
  2. The formula used a fixed 17 px inner-group offset that only applied to the
     WED (today) cell; all other cells had a 0 px offset.

Fix: completely flat layout — every element added directly to the root
FloatLayout with `pos_hint` fractions derived from exact Figma pixel data.
No nested FloatLayouts for day cells means no deferred-build timing issues.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from async_helper import run_async
from config import DISPLAY_HEIGHT, DISPLAY_WIDTH, display_now
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

# ── Design frame ──────────────────────────────────────────────────────────────
FW, FH = 1260.0, 800.0

# ── Colours (exact Figma hex) ─────────────────────────────────────────────────
_BG      = (1/255,   8/255,  26/255, 1.0)   # #01081A
_WHITE   = (1.0, 1.0, 1.0, 1.0)
_MUTED   = (182/255, 186/255, 242/255, 1.0)  # #B6BAF2
_BDOT    = (64/255,  152/255, 252/255, 1.0)  # #4098FC
_BLUE_A  = (0.0, 107/255, 249/255, 1.0)     # #006BF9  add-event label
_BTDAY   = (4/255,  132/255, 255/255, 1.0)  # #0484FF  today-border
_CARD_T  = (2/255,   18/255,  60/255, 1.0)  # #02123C  grid/free-card top
_CARD_B  = (0.0,    10/255,  38/255, 1.0)   # #000A26
_BORDER  = (63/255,  66/255,  83/255, 1.0)  # #3F4253
_MTG_T   = (1/255,   17/255,  55/255, 1.0)  # #011137
_MTG_B   = (0.0,    10/255,  38/255, 1.0)   # #000A26
_MTG_BDR = (33/255,  40/255,  75/255, 1.0)  # #21284B
_JOIN_T  = (0.0,    89/255, 220/255, 1.0)   # #0059DC
_JOIN_B  = (1/255,   61/255, 167/255, 1.0)  # #013DA7
_JOIN_BDR= (63/255, 140/255, 255/255, 1.0)  # #3F8CFF
_ICON_BG = (1/255,   11/255,  38/255, 1.0)  # #010B26

_FSB = "42dot-SB"   # SemiBold
_FB  = "42dot-Sans"  # Bold variant registered in main.py


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ph(fx: float, fy: float, fw: float, fh: float) -> dict:
    """Figma absolute px → Kivy size_hint + pos_hint for a 1260×800 root."""
    return {
        "size_hint": (fw / FW, fh / FH),
        "pos_hint": {"x": fx / FW, "y": (FH - fy - fh) / FH},
    }


def _ff(fs: float) -> int:
    scale = min(DISPLAY_WIDTH / FW, DISPLAY_HEIGHT / FH)
    return max(6, round(fs * scale))


_GC: dict = {}


def _grad(top: tuple, bot: tuple):
    from kivy.graphics.texture import Texture
    k = (top, bot)
    if k not in _GC:
        t = Texture.create(size=(1, 2), colorfmt="rgba")
        def _b(c):
            return [min(255, max(0, int(v * 255))) for v in c]
        t.blit_buffer(bytes(_b(bot) + _b(top)), colorfmt="rgba", bufferfmt="ubyte")
        t.mag_filter = t.min_filter = "linear"
        t.wrap = "clamp_to_edge"
        _GC[k] = t
    return _GC[k]


def _lbl(text: str, font: str, size: int, color: tuple,
         ha: str = "left", va: str = "top", **kw) -> Label:
    l = Label(text=text, font_name=font, font_size=size, color=color,
              halign=ha, valign=va, **kw)
    l.bind(size=l.setter("text_size"))
    return l


# ── Reusable card widget ──────────────────────────────────────────────────────

class _Card(FloatLayout):
    def __init__(self, ct: tuple, cb: tuple, bdr: tuple, r: float = 12, **kw):
        super().__init__(**kw)
        self._r = r
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[r], texture=_grad(ct, cb))
        with self.canvas.after:
            Color(*bdr, 0.8)
            self._ln = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, r),
                width=1.0)
        self.bind(pos=self._s, size=self._s)

    def _s(self, *_):
        r = self._r
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bg.radius = [r]
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


class _TapCard(ButtonBehavior, _Card):
    pass


# ── Day-cell highlight (today blue box / selected lighter box) ────────────────

class _Highlight(Widget):
    """Transparent overlay drawn on top of the grid background for one day."""

    def __init__(self, mode: str = "none", **kw):
        super().__init__(**kw)
        self._mode = mode
        with self.canvas:
            self._fc = Color(0, 0, 0, 0)
            self._bg = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[_ff(14.13)])
            self._bc = Color(0, 0, 0, 0)
            self._ln = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, _ff(14.13)),
                width=1.41)
        self.bind(pos=self._d, size=self._d)
        self._apply()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._apply()
        self._d()

    def _apply(self) -> None:
        if self._mode == "today":
            self._fc.rgba = (0.016, 0.082, 0.259, 0.38)
            self._bc.rgba = _BTDAY
        elif self._mode == "sel":
            self._fc.rgba = (*_BTDAY[:3], 0.14)
            self._bc.rgba = (*_BTDAY[:3], 0.55)
        else:
            self._fc.rgba = (0, 0, 0, 0)
            self._bc.rgba = (0, 0, 0, 0)

    def _d(self, *_) -> None:
        r = _ff(14.13)
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bg.radius = [r]
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


# ── Tap zone (invisible tap catcher over a day column) ───────────────────────

class _TapZone(ButtonBehavior, Widget):
    pass


# ── Column layout data from Figma ─────────────────────────────────────────────
#
# Grid frame: GX=24.02, GY=105.94, GW=1210.56, GH=151.14
#
# Each entry:
#   (outer_x, outer_y, outer_w, outer_h,   ← highlight-box pos relative to grid
#    inner_dx, inner_dy,                    ← content group offset within outer group
#    abbrev_dx, abbrev_dy, abbrev_w, abbrev_h,
#    date_dx,   date_dy,   date_w,  date_h,
#    [(dot_dx, dot_dy, filled), ...])        ← relative to inner group origin
#
# Positions are in Figma pixels (y measured from top of frame).
# inner_dx/dy = offset of the Group that holds text/dots within the outer group.
# For all columns except WED the inner group sits at (0,0) of the outer group.
# WED's inner group is inset by (38.14, 16.95) to create room for the glow box.

GX, GY = 24.02, 105.94

_COLS = [
    # MON — outer group 63.57,21.19 66×110.18 ; inner 0,0
    (63.57,   21.19,  66.0,   110.18, 0.00,  0.00,
     0.00,  0.00,  66.0, 34.0,   9.89, 38.14, 47.0, 51.0,
     [(15.54, 96.05, True), (38.14, 96.05, True)]),
    # TUE — outer 240.13,21.19 53×110.18
    (240.13,  21.19,  53.0,   110.18, 0.00,  0.00,
     0.00,  0.00,  53.0, 34.0,   1.41, 39.55, 51.0, 51.0,
     [(16.95, 96.05, True)]),
    # WED — outer 365.85,5.65 139.84×139.84 ; inner inset 38.14,16.95
    (365.85,   5.65, 139.84,  139.84, 38.14, 16.95,
     1.41,  0.00,  64.0, 34.0,  11.30, 38.14, 46.0, 51.0,
     [(0.00, 93.23, True), (22.60, 93.23, True), (45.20, 93.23, True)]),
    # THU — outer 577.73,22.6 57×107.35
    (577.73,  22.60,  57.0,   107.35, 0.00,  0.00,
     0.00,  0.00,  57.0, 34.0,   4.23, 38.14, 49.0, 51.0,
     [(21.19, 93.23, True), (43.79, 93.23, True)]),
    # FRI — outer 750.07,22.6 51×107.35
    (750.07,  22.60,  51.0,   107.35, 0.00,  0.00,
     2.82,  0.00,  47.0, 34.0,   0.00, 38.14, 51.0, 51.0,
     [(18.36, 93.23, True)]),
    # SAT — outer 919.58,22.6 51×107.35 ; dot is outline
    (919.58,  22.60,  51.0,   107.35, 0.00,  0.00,
     0.00,  0.00,  51.0, 34.0,   0.00, 38.14, 51.0, 51.0,
     [(18.37, 93.23, False)]),
    # SUN — outer 1084.84,22.6 58×107.35 ; dot is outline
    (1084.84, 22.60,  58.0,   107.35, 0.00,  0.00,
     0.00,  0.00,  58.0, 34.0,   4.24, 38.14, 51.0, 51.0,
     [(22.60, 93.23, False)]),
]

_DAY_ABBR  = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_DAY_FULL  = ["Monday", "Tuesday", "Wednesday", "Thursday",
              "Friday", "Saturday", "Sunday"]
_MONTHS    = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]


def _fmt_date(d: date) -> str:
    return f"{d.strftime('%a')} , {_MONTHS[d.month - 1]} {d.day}"


# ── CalendarScreen ────────────────────────────────────────────────────────────

class CalendarScreen(BaseScreen):
    """Calendar view — pixel-perfect flat layout from Figma 927:61."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._sel_date: date = display_now().date()
        self._heading_lbl: Label | None = None
        self._datestr_lbl: Label | None = None
        # per-column refs  (indexed 0=MON … 6=SUN)
        self._date_lbls: list[Label] = []
        self._highlights: list[_Highlight] = []
        self._col_dates: list[date] = []
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = FloatLayout(size_hint=(1, 1))

        with root.canvas.before:
            Color(*_BG)
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, v: setattr(self._bg_rect, "pos", v),
            size=lambda w, v: setattr(self._bg_rect, "size", v),
        )

        self._build_header(root)
        self._build_grid(root)
        self._build_free_card(root)
        self._build_timeline(root)
        self._build_meeting_cards(root)
        self._build_add_button(root)

        self.add_widget(root)

    # ── Header ─────────────────────────────────────────────────────────────────
    # back-btn 24.02,21.19 76.28×76.28
    # "Today"  118.66,14.13  108×46
    # date str 118.66,60.36  169×33
    # calendar icon 241.93,20.49 36.98×33
    # spark ✦  851.77,38.24  39.38×40.89
    # busy txt 905.91,19.78  299×29
    # free txt 905.91,55.46  207×29

    def _build_header(self, root: FloatLayout) -> None:
        # Back button
        back = _TapCard(ct=_ICON_BG, cb=_ICON_BG, bdr=_BORDER,
                        r=_ff(38), **_ph(24.02, 21.19, 76.28, 76.28))
        back.add_widget(_lbl("‹", _FB, _ff(36), _WHITE, ha="center", va="middle",
                             size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
        back.bind(on_release=lambda *_: self.go_back())
        root.add_widget(back)

        # "Today" heading
        self._heading_lbl = _lbl(
            "Today", _FSB, _ff(38.52), _WHITE,
            **_ph(118.66, 14.13, 200.0, 46.0))
        root.add_widget(self._heading_lbl)

        # Date string
        self._datestr_lbl = _lbl(
            _fmt_date(display_now().date()), _FSB, _ff(27.52), _WHITE,
            **_ph(118.66, 60.36, 250.0, 33.0))
        root.add_widget(self._datestr_lbl)

        # Calendar icon (unicode fallback)
        root.add_widget(_lbl(
            "📅", _FSB, _ff(28), _WHITE, ha="center", va="middle",
            **_ph(241.93, 20.49, 36.98, 33.0)))

        # Intelligence — spark icon
        root.add_widget(_lbl(
            "✦", _FSB, _ff(30), _MUTED, ha="center", va="middle",
            **_ph(851.77, 28.0, 42.0, 42.0)))

        # Busy text
        root.add_widget(_lbl(
            "This Week Busy: Wed, Thu", _FSB, _ff(24.61), _MUTED,
            **_ph(905.91, 19.78, 299.0, 29.0)))

        # Free text
        root.add_widget(_lbl(
            "Free: Fri afternoon", _FSB, _ff(24.61), _MUTED,
            **_ph(905.91, 55.46, 207.0, 29.0)))

    # ── Week grid ──────────────────────────────────────────────────────────────

    def _build_grid(self, root: FloatLayout) -> None:
        # Grid card background  24.02,105.94  1210.56×151.14  r=29.66
        root.add_widget(_Card(
            ct=_CARD_T, cb=_CARD_B, bdr=_BORDER,
            r=_ff(29.66),
            **_ph(GX, GY, 1210.56, 151.14)))

        today = display_now().date()
        week_mon = today - timedelta(days=today.weekday())
        self._col_dates = [week_mon + timedelta(days=i) for i in range(7)]

        # Six vertical dividers within grid  (y=33.9 in grid, h=84.75, w=2.83)
        # fill: linear-gradient that fades in/out → approximate with solid midpoint
        for div_x in (179.4, 348.91, 518.41, 687.91, 857.42, 1026.93):
            sx = GX + div_x
            sy = GY + 33.9
            dv = Widget(**_ph(sx, sy, 2.83, 84.75))
            with dv.canvas.before:
                Color(2/255, 23/255, 77/255, 0.85)
                _r = Rectangle(pos=dv.pos, size=dv.size)
            def _mk(r):
                def _s(w, *_): r.pos = w.pos; r.size = w.size
                return _s
            dv.bind(pos=_mk(_r), size=_mk(_r))
            root.add_widget(dv)

        # Per-column: highlight box, tap zone, abbrev label, date label, dots
        self._highlights.clear()
        self._date_lbls.clear()

        for col_idx, col_data in enumerate(_COLS):
            (ox, oy, ow, oh,
             idx_x, idy,
             adx, ady, aw, ah,
             ddx, ddy, dw, dh,
             dots) = col_data

            # Absolute screen positions
            outer_sx = GX + ox
            outer_sy = GY + oy
            inner_sx = outer_sx + idx_x
            inner_sy = outer_sy + idy

            # Column date
            col_date = self._col_dates[col_idx]

            # Highlight box (sized to outer group)
            is_today = (col_date == today)
            hl = _Highlight(
                mode="today" if is_today else "none",
                **_ph(outer_sx, outer_sy, ow, oh))
            root.add_widget(hl)
            self._highlights.append(hl)

            # Invisible tap zone over outer group
            tz = _TapZone(**_ph(outer_sx, outer_sy, ow, oh))
            _cd = col_date
            _idx = col_idx
            tz.bind(on_release=lambda inst, d=_cd, i=_idx: self._select_day(d, i))
            root.add_widget(tz)

            # Day abbreviation label
            root.add_widget(_lbl(
                _DAY_ABBR[col_idx], _FSB, _ff(28.25), _MUTED,
                ha="center", va="middle",
                **_ph(inner_sx + adx, inner_sy + ady, aw, ah)))

            # Date number label (dynamic)
            dl = _lbl(
                str(col_date.day), _FB, _ff(42.38), _WHITE,
                ha="center", va="middle",
                **_ph(inner_sx + ddx, inner_sy + ddy, dw, dh))
            root.add_widget(dl)
            self._date_lbls.append(dl)

            # Dots
            for dot_dx, dot_dy, filled in dots:
                dot_sx = inner_sx + dot_dx
                dot_sy = inner_sy + dot_dy
                dot_w = dot_h = 14.13
                d_wid = Widget(**_ph(dot_sx, dot_sy, dot_w, dot_h))
                if filled:
                    with d_wid.canvas:
                        Color(*_BDOT)
                        _e = Ellipse(pos=d_wid.pos, size=d_wid.size)
                    def _mk_e(e):
                        def _s(w, *_): e.pos = w.pos; e.size = w.size
                        return _s
                    d_wid.bind(pos=_mk_e(_e), size=_mk_e(_e))
                else:
                    with d_wid.canvas:
                        Color(*_MUTED, 0.8)
                        _el = Line(
                            ellipse=(d_wid.x, d_wid.y, d_wid.width, d_wid.height),
                            width=1.2)
                    def _mk_el(el):
                        def _s(w, *_):
                            el.ellipse = (w.x, w.y, w.width, w.height)
                        return _s
                    d_wid.bind(pos=_mk_el(_el), size=_mk_el(_el))
                root.add_widget(d_wid)

    # ── Free-time card ─────────────────────────────────────────────────────────
    # Frame '20': 25.43,268.39  1210.56×100.29  r=29.66
    # clock icon:  31.08,24.02  53.68×53.68  (unicode fallback)
    # free text:   97.47,31.08  356×39  Bold 32.49
    # sun icon:   884.26,28.25  49.44×49.44
    # meeting cnt: 943.59,35.32 236×37  Bold 31.08

    def _build_free_card(self, root: FloatLayout) -> None:
        CW, CH = 1210.56, 100.29
        CX, CY = 25.43, 268.39

        card = _Card(ct=_CARD_T, cb=_CARD_B, bdr=_BORDER,
                     r=_ff(29.66), **_ph(CX, CY, CW, CH))

        # Clock icon
        card.add_widget(_lbl(
            "⏱", _FSB, _ff(38), _MUTED, ha="center", va="middle",
            size_hint=(53.68 / CW, 53.68 / CH),
            pos_hint={"x": 31.08 / CW, "y": (CH - 24.02 - 53.68) / CH}))

        # Free-till text
        card.add_widget(_lbl(
            "You're free till 11:00 AM", _FB, _ff(32.49), _WHITE,
            va="middle",
            size_hint=(356 / CW, 39 / CH),
            pos_hint={"x": 97.47 / CW, "y": (CH - 31.08 - 39) / CH}))

        # Sun icon
        card.add_widget(_lbl(
            "☀", _FSB, _ff(34), _MUTED, ha="center", va="middle",
            size_hint=(49.44 / CW, 49.44 / CH),
            pos_hint={"x": 884.26 / CW, "y": (CH - 28.25 - 49.44) / CH}))

        # Meeting count
        card.add_widget(_lbl(
            "3 meeting today", _FB, _ff(31.08), _WHITE,
            va="middle",
            size_hint=(236 / CW, 37 / CH),
            pos_hint={"x": 943.59 / CW, "y": (CH - 35.32 - 37) / CH}))

        root.add_widget(card)

    # ── Timeline (separator + dots + time labels) ──────────────────────────────
    # Separator Rectangle 31: 203.41,377.15  2.83×355.96
    # Group 58 (large dot):   187.87,412.46  33.9×33.9   #0090FF
    # Group 59 (mid dot):     192.11,529.71  25.43×25.43 #0050FF
    # Group 60 (mid dot):     192.11,642.71  25.43×25.43 #0050FF
    # Group 61 (11:00 AM):    48.02,405.40   71×60.9
    # Group 62 (2:00 PM):     59.33,509.93   59×60.9
    # Group 63 (5:30 PM):     56.50,622.94   60.84×60.9

    def _build_timeline(self, root: FloatLayout) -> None:
        # Separator line
        sep = Widget(**_ph(203.41, 377.15, 2.83, 355.96))
        with sep.canvas.before:
            # Figma fill: linear-gradient fade-in/out → solid centre approximation
            Color(154/255, 189/255, 255/255, 0.75)
            _sr = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(
            pos=lambda w, v: setattr(_sr, "pos", v),
            size=lambda w, v: setattr(_sr, "size", v))
        root.add_widget(sep)

        # Timeline dots
        for (sx, sy, dw, dh, r, g, b) in [
            (187.87, 412.46, 33.9,  33.9,  0.0, 0.565, 1.0),   # large #0090FF
            (192.11, 529.71, 25.43, 25.43, 0.0, 0.314, 1.0),   # mid   #0050FF
            (192.11, 642.71, 25.43, 25.43, 0.0, 0.314, 1.0),   # mid   #0050FF
        ]:
            dw2 = Widget(**_ph(sx, sy, dw, dh))
            with dw2.canvas:
                Color(r, g, b, 1.0)
                _e2 = Ellipse(pos=dw2.pos, size=dw2.size)
            def _mk2(e):
                def _s(w, *_): e.pos = w.pos; e.size = w.size
                return _s
            dw2.bind(pos=_mk2(_e2), size=_mk2(_e2))
            root.add_widget(dw2)

        # Time labels
        # Group 61: 48.02,405.40 w=71 h=60.9
        #   11:00  at (0,0) w=71 h=34
        #   AM     at (35.31,33.9) w=35 h=27
        for (gx, gy, gw, gh, time_s, ampm_s, ampm_dx, ampm_dy) in [
            (48.02,  405.40, 71.0,  60.9, "11:00", "AM", 35.31, 33.90),
            (59.33,  509.93, 59.0,  60.9, "2:00",  "PM", 24.02, 33.90),
            (56.50,  622.94, 60.84, 60.9, "5:30",  "PM", 26.84, 33.90),
        ]:
            root.add_widget(_lbl(
                time_s, _FB, _ff(28.25), _WHITE,
                **_ph(gx, gy, gw, 34.0)))
            root.add_widget(_lbl(
                ampm_s, _FSB, _ff(22.6), _MUTED,
                **_ph(gx + ampm_dx, gy + ampm_dy, 35.0, 27.0)))

    # ── Meeting cards ──────────────────────────────────────────────────────────
    # Card '21' Product Sync:  276.86,377.15  954.89×104.53
    # Card '25' Client Call:   281.10,490.16  954.89×104.53
    # Card '22' Review:        281.10,603.16  954.89×104.53

    def _build_meeting_cards(self, root: FloatLayout) -> None:
        meetings = [
            (276.86, 377.15, "Product Sync", "30 min", True),
            (281.10, 490.16, "Client Call",  "45 min", False),
            (281.10, 603.16, "Review",       "30 min", False),
        ]
        for (cx, cy, title, dur, show_join) in meetings:
            self._add_meeting_card(root, cx, cy, 954.89, 104.53,
                                   title, dur, show_join)

    def _add_meeting_card(self, root: FloatLayout,
                          cx: float, cy: float, cw: float, ch: float,
                          title: str, dur: str, show_join: bool) -> None:
        card = _Card(ct=_MTG_T, cb=_MTG_B, bdr=_MTG_BDR,
                     r=_ff(25.43), **_ph(cx, cy, cw, ch))

        # Icon circle  32.49,16.95  70.63×70.63  r=16.21
        IW, IH, IX, IY = 70.63, 70.63, 32.49, 16.95
        ic = _Card(ct=_ICON_BG, cb=_ICON_BG, bdr=_BORDER, r=_ff(16.21),
                   size_hint=(IW / cw, IH / ch),
                   pos_hint={"x": IX / cw, "y": (ch - IY - IH) / ch})
        ic.add_widget(_lbl(
            title[0].upper(), _FSB, _ff(30), _BTDAY,
            ha="center", va="middle",
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
        card.add_widget(ic)

        # Title  129.95,16.95  176×34  Bold 28.25
        card.add_widget(_lbl(
            title, _FB, _ff(28.25), _WHITE,
            va="middle",
            size_hint=(300 / cw, 34 / ch),
            pos_hint={"x": 129.95 / cw, "y": (ch - 16.95 - 34) / ch}))

        # Duration  129.95,56.5  112.96×31.08
        card.add_widget(_lbl(
            f"⏱  {dur}", _FSB, _ff(22.6), _MUTED,
            va="middle",
            size_hint=(200 / cw, 31.08 / ch),
            pos_hint={"x": 129.95 / cw, "y": (ch - 56.50 - 31.08) / ch}))

        # Join button  607.4,24.01  144.08×56.5
        if show_join:
            jb = _TapCard(ct=_JOIN_T, cb=_JOIN_B, bdr=_JOIN_BDR,
                          r=_ff(12.71),
                          size_hint=(144.08 / cw, 56.5 / ch),
                          pos_hint={"x": 607.4 / cw, "y": (ch - 24.01 - 56.5) / ch})
            # video icon + "Join"
            jb.add_widget(_lbl(
                "▶  Join", _FB, _ff(26.84), _WHITE,
                ha="center", va="middle",
                size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
            card.add_widget(jb)

        # Details button  (778.32 with join, 607.4 without)
        det_x = 778.32 if show_join else 607.4
        db = _TapCard(ct=(0, 0, 0, 0), cb=(0, 0, 0, 0), bdr=_BORDER,
                      r=_ff(12.71),
                      size_hint=(144.08 / cw, 56.5 / ch),
                      pos_hint={"x": det_x / cw, "y": (ch - 24.01 - 56.5) / ch})
        db.add_widget(_lbl(
            "Details  ›", _FB, _ff(21.19), _WHITE,
            ha="center", va="middle",
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
        card.add_widget(db)

        root.add_widget(card)

    # ── Add-event button ───────────────────────────────────────────────────────
    # Frame '27': 440.72,716.16  378.57×60.74  r=16.95
    # gg:add icon at 98.88,9.89  42.38×42.38
    # "Add event"  146.91,14.13  133×34  Bold 28.25  #006BF9

    def _build_add_button(self, root: FloatLayout) -> None:
        BW, BH = 378.57, 60.74
        btn = _TapCard(ct=_MTG_T, cb=_MTG_B, bdr=_MTG_BDR,
                       r=_ff(16.95), **_ph(440.72, 716.16, BW, BH))

        btn.add_widget(_lbl(
            "+", _FB, _ff(34), _BLUE_A,
            ha="center", va="middle",
            size_hint=(42.38 / BW, 42.38 / BH),
            pos_hint={"x": 98.88 / BW, "y": (BH - 9.89 - 42.38) / BH}))

        btn.add_widget(_lbl(
            "Add event", _FB, _ff(28.25), _BLUE_A,
            va="middle",
            size_hint=(133 / BW, 34 / BH),
            pos_hint={"x": 146.91 / BW, "y": (BH - 14.13 - 34) / BH}))

        root.add_widget(btn)

    # ── Day selection ──────────────────────────────────────────────────────────

    def _select_day(self, d: date, col_idx: int) -> None:
        today = display_now().date()
        prev_sel = self._sel_date
        self._sel_date = d

        for i, (hl, col_date) in enumerate(
                zip(self._highlights, self._col_dates)):
            if col_date == today:
                hl.set_mode("today")
            elif col_date == d and col_date != today:
                hl.set_mode("sel")
            elif col_date == prev_sel and col_date != today:
                hl.set_mode("none")

        if self._heading_lbl:
            self._heading_lbl.text = (
                "Today" if d == today else _DAY_FULL[d.weekday()])
        if self._datestr_lbl:
            self._datestr_lbl.text = _fmt_date(d)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_enter(self) -> None:
        today = display_now().date()
        week_mon = today - timedelta(days=today.weekday())
        self._col_dates = [week_mon + timedelta(days=i) for i in range(7)]
        self._sel_date = today

        # Refresh date numbers (week may have changed since __init__)
        for i, lbl in enumerate(self._date_lbls):
            lbl.text = str(self._col_dates[i].day)

        # Reset highlights
        for i, hl in enumerate(self._highlights):
            hl.set_mode("today" if self._col_dates[i] == today else "none")

        # Header
        if self._heading_lbl:
            self._heading_lbl.text = "Today"
        if self._datestr_lbl:
            self._datestr_lbl.text = _fmt_date(today)

        Clock.schedule_once(lambda _dt: self._load_week(), 0)

    def _load_week(self) -> None:
        async def _fetch():
            try:
                await self.backend.get_calendar_week()
            except Exception as exc:
                logger.debug("CalendarScreen: get_calendar_week failed: %s", exc)
        run_async(_fetch())

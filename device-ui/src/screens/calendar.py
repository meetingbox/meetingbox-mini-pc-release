"""Calendar screen — pixel-perfect implementation based on Figma data.

Figma file: Cricket Champs (U3meTmbLWA67jhzCSyN8xA), node 927:61.
Frame: 1260 × 800 px. All coordinates are direct Figma pixel values.

Layout zones (Figma y from top-left):
  Header          y=14   h=93     Back btn · "Today" · date · calendar icon
  Intelligence    y=19   h=65     Spark icon · busy text · free text (no bg)
  Week grid       y=105  h=152    7 day columns, today highlighted with blue frame
  Daily summary   y=268  h=101    "You're free till X" + meeting count
  Meetings        y=377  h=423    Left timeline separator + scrollable meeting cards
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from async_helper import run_async
from config import ASSETS_DIR, DISPLAY_HEIGHT, DISPLAY_WIDTH, display_now, to_display_local
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

# ── Frame ─────────────────────────────────────────────────────────────────────
FW, FH = 1260.0, 800.0
_FIGMA_PROC = ASSETS_DIR / "processing" / "figma"
_FIGMA_HOME = ASSETS_DIR / "home" / "figma"
_FIGMA_IDLE = ASSETS_DIR / "idle"

# ── Colours (exact Figma hex values) ──────────────────────────────────────────
_BG         = (1/255,   8/255,  26/255, 1.0)   # #01081A
_WHITE      = (1.0, 1.0, 1.0, 1.0)
_MUTED      = (182/255, 186/255, 242/255, 1.0)  # #B6BAF2
_BLUE_DOT   = (64/255,  152/255, 252/255, 1.0)  # #4098FC
_BLUE_ADD   = (0.0, 107/255, 249/255, 1.0)      # #006BF9
_BLUE_TODAY = (4/255,  132/255, 255/255, 1.0)   # #0484FF
_CARD_T     = (2/255,   18/255,  60/255, 1.0)   # #02123C  (grid + free card top)
_CARD_B     = (0.0,    10/255,  38/255, 1.0)    # #000A26  (card bottom)
_BORDER_T   = (63/255,  66/255,  83/255, 1.0)   # #3F4253
_BORDER_B   = (22/255,  27/255,  53/255, 1.0)   # #161B35
_MTG_T      = (1/255,   17/255,  55/255, 1.0)   # #011137  (meeting card top)
_MTG_B      = (0.0,    10/255,  38/255, 1.0)    # #000A26
_MTG_BDR    = (33/255,  40/255,  75/255, 1.0)   # #21284B
_JOIN_T     = (0.0,    89/255, 220/255, 1.0)    # #0059DC
_JOIN_B     = (1/255,   61/255, 167/255, 1.0)   # #013DA7
_JOIN_BDR   = (63/255, 140/255, 255/255, 1.0)   # #3F8CFF
_ICON_BG    = (1/255,   11/255,  38/255, 1.0)   # #010B26
_SEP_C      = (154/255, 189/255, 255/255, 0.75) # #9ABDFF

_FONT    = "42dot-Sans"
_FONT_SB = "42dot-SB"
_FONT_MD = "42dot-Med"

_DAYS_S = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_DAYS_F = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# ── Grid layout (divider x positions within 1210.56-wide grid frame) ──────────
_GX, _GY, _GW, _GH = 24.02, 105.94, 1210.56, 151.14
_DIVS   = [179.4, 348.91, 518.41, 687.91, 857.42, 1026.93]
_COL_S  = [0.0] + _DIVS          # column start x within grid frame
_COL_E  = _DIVS + [_GW]          # column end x within grid frame

# ── Grid internal proportions ─────────────────────────────────────────────────
# Day abbreviation label: starts at y:22.6 from grid top, h:34
_DAY_LBL_TOP_FRAC   = 1.0 - 22.6 / _GH          # pos_hint "top" in FloatLayout
_DAY_LBL_H_FRAC     = 34.0 / _GH
# Date number center: ~y:80 from grid top → center_y from bottom
_DATE_CTR_FRAC      = (151.14 - 80.0) / 151.14   # ≈ 0.47
_DATE_H_FRAC        = 51.0 / _GH
# Dots: center y ~122px from grid top → from bottom ~29px
_DOT_CY_FRAC        = 29.0 / _GH                  # ≈ 0.19

# ── Meeting area constants ─────────────────────────────────────────────────────
_MA_Y   = 377.15    # meetings area top (Figma y from screen top)
_MA_H   = FH - _MA_Y                              # 422.85 px
_ROW_H  = 113.0     # meeting row height (from Figma spacing: 490.16-377.15)
_CARD_W = 954.89    # meeting card width
_CARD_H = 104.53    # meeting card height
_CARD_X = 276.86    # meeting card x on screen
_SEP_X  = 203.41    # separator line x
_TL_X   = 48.02     # time label x


# ── Coordinate helpers ─────────────────────────────────────────────────────────

def _ph(fx: float, fy: float, fw: float, fh: float) -> dict:
    """Figma (x, y_from_top, w, h) → Kivy size_hint + pos_hint."""
    return {
        "size_hint": (fw / FW, fh / FH),
        "pos_hint": {"x": fx / FW, "y": (FH - fy - fh) / FH},
    }


def _ff(fs: float) -> int:
    scale = min(DISPLAY_WIDTH / FW, DISPLAY_HEIGHT / FH)
    return max(6, round(fs * scale))


_GCACHE: dict = {}


def _grad(top: tuple, bot: tuple):
    from kivy.graphics.texture import Texture
    k = (top, bot)
    if k not in _GCACHE:
        t = Texture.create(size=(1, 2), colorfmt="rgba")
        def _b(c): return [min(255, max(0, int(v * 255))) for v in c]
        t.blit_buffer(bytes(_b(bot) + _b(top)), colorfmt="rgba", bufferfmt="ubyte")
        t.mag_filter = t.min_filter = "linear"
        t.wrap = "clamp_to_edge"
        _GCACHE[k] = t
    return _GCACHE[k]


def _fp(*names: str) -> str:
    for n in names:
        for d in (_FIGMA_PROC, _FIGMA_HOME, _FIGMA_IDLE):
            p = d / n
            if p.is_file():
                return str(p)
    return ""


def _lbl(text, font, size, color, halign="left", valign="middle", **kw) -> Label:
    l = Label(text=text, font_name=font, font_size=size, color=color,
              halign=halign, valign=valign, **kw)
    l.bind(size=l.setter("text_size"))
    return l


def _density(n: int) -> int:
    return 0 if n == 0 else (1 if n == 1 else (2 if n <= 3 else 3))


def _fmt_date(d: date) -> str:
    return f"{d.strftime('%a, %b')} {d.day}"


# ── Widget helpers ─────────────────────────────────────────────────────────────

class _GCard(FloatLayout):
    """Static gradient card with border."""
    def __init__(self, ct=None, cb=None, bdr=None, radius=12, **kw):
        ct = ct or _CARD_T; cb = cb or _CARD_B; bdr = bdr or _BORDER_T
        super().__init__(**kw)
        self._r = radius
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size,
                                        radius=[radius], texture=_grad(ct, cb))
        with self.canvas.after:
            Color(*bdr, 0.8)
            self._ln = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                width=1.0)
        self.bind(pos=self._s, size=self._s)

    def _s(self, *_):
        r = self._r
        self._bg.pos = self.pos; self._bg.size = self.size; self._bg.radius = [r]
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


class _Btn(ButtonBehavior, FloatLayout):
    """Solid gradient button."""
    def __init__(self, text, fg, ct, cb, bdr, radius, font_size, on_tap=None, **kw):
        super().__init__(**kw)
        self._r = radius
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size,
                                        radius=[radius], texture=_grad(ct, cb))
            Color(*bdr, 0.9)
            self._ln = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                width=1.0)
        self.bind(pos=self._s, size=self._s)
        self.add_widget(_lbl(text, _FONT_SB, font_size, fg,
                             halign="center", valign="middle",
                             size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
        if on_tap:
            self.bind(on_release=lambda *_: on_tap())

    def _s(self, *_):
        r = self._r
        self._bg.pos = self.pos; self._bg.size = self.size; self._bg.radius = [r]
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


class _OutlineBtn(ButtonBehavior, FloatLayout):
    """Transparent button with border only."""
    def __init__(self, text, fg, bdr, radius, font_size, on_tap=None, **kw):
        super().__init__(**kw)
        self._r = radius
        with self.canvas.after:
            Color(*bdr, 0.6)
            self._ln = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                width=1.0)
        self.bind(pos=self._s, size=self._s)
        self.add_widget(_lbl(text, _FONT_SB, font_size, fg,
                             halign="center", valign="middle",
                             size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
        if on_tap:
            self.bind(on_release=lambda *_: on_tap())

    def _s(self, *_):
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, self._r)


class _CircleBtn(ButtonBehavior, FloatLayout):
    """Circular icon button (back button)."""
    def __init__(self, src=None, on_tap=None, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*_ICON_BG)
            self._bg = Ellipse(pos=self.pos, size=self.size)
            Color(*_BORDER_T, 0.7)
            self._ln = Line(circle=(0, 0, 1), width=1.41)
        self.bind(pos=self._s, size=self._s)
        if src:
            self.add_widget(Image(source=src, size_hint=(0.55, 0.55),
                                  pos_hint={"center_x": 0.5, "center_y": 0.5},
                                  fit_mode="contain"))
        else:
            self.add_widget(_lbl("‹", _FONT_SB, _ff(36), _WHITE,
                                 halign="center", valign="middle",
                                 size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
        if on_tap:
            self.bind(on_release=lambda *_: on_tap())

    def _s(self, *_):
        cx, cy = self.center
        r = min(self.width, self.height) / 2
        self._bg.pos = self.pos; self._bg.size = self.size
        self._ln.circle = (cx, cy, r)


# ── Day cell ──────────────────────────────────────────────────────────────────

class _DayCell(ButtonBehavior, FloatLayout):
    """One tappable day column in the week grid."""

    def __init__(self, day_date: date, screen_ref, **kw):
        super().__init__(**kw)
        self._date = day_date
        self._screen_ref = screen_ref
        self._mtg_n = 0
        self._selected = False
        self._is_today = (day_date == display_now().date())
        idx = day_date.weekday()

        # Day abbreviation — uses FloatLayout geometry (size_hint + pos_hint)
        self._day_lbl = Label(
            text=_DAYS_S[idx],
            font_name=_FONT_SB, font_size=_ff(28.25),
            color=_MUTED, halign="center", valign="middle",
            size_hint=(1.0, _DAY_LBL_H_FRAC),
            pos_hint={"x": 0, "top": _DAY_LBL_TOP_FRAC})
        self._day_lbl.bind(size=self._day_lbl.setter("text_size"))
        self.add_widget(self._day_lbl)

        # Date number
        self._date_lbl = Label(
            text=str(day_date.day),
            font_name=_FONT_SB, font_size=_ff(42.38),
            color=_WHITE, halign="center", valign="middle",
            size_hint=(1.0, _DATE_H_FRAC),
            pos_hint={"x": 0, "center_y": _DATE_CTR_FRAC})
        self._date_lbl.bind(size=self._date_lbl.setter("text_size"))
        self.add_widget(self._date_lbl)

        # Canvas: today/selected highlight box + dots
        with self.canvas.before:
            self._hc  = Color(0, 0, 0, 0)
            self._hr  = RoundedRectangle(pos=(0, 0), size=(1, 1), radius=[_ff(14.13)])
            self._hlc = Color(0, 0, 0, 0)
            self._hrl = Line(rounded_rectangle=(0, 0, 1, 1, _ff(14.13)), width=1.41)
            self._dots: list[tuple] = []
            for _ in range(3):
                fc = Color(0, 0, 0, 0); fe = Ellipse(pos=(0, 0), size=(1, 1))
                rc = Color(0, 0, 0, 0); rl = Line(circle=(0, 0, 1), width=1.41)
                self._dots.append((fc, fe, rc, rl))

        self.bind(pos=self._sync, size=self._sync)
        self.bind(on_release=lambda *_: screen_ref._select_day(self._date))

    def _sync(self, *_) -> None:
        W, H = self.width, self.height
        bx, by = self.x, self.y
        if W < 2 or H < 2:
            return

        cx = bx + W / 2

        # Highlight box: 85% column width, 94% height, centred
        hw = W * 0.85
        hh = H * 0.94
        hx = bx + (W - hw) / 2
        hy = by + (H - hh) / 2
        radius = _ff(14.13)

        if self._is_today:
            self._hc.rgba  = (0.016, 0.082, 0.259, 0.38)
            self._hr.pos   = (hx, hy); self._hr.size = (hw, hh); self._hr.radius = [radius]
            self._hlc.rgba = _BLUE_TODAY
            self._hrl.rounded_rectangle = (hx, hy, hw, hh, radius)
        elif self._selected:
            self._hc.rgba  = (*_BLUE_TODAY[:3], 0.14)
            self._hr.pos   = (hx, hy); self._hr.size = (hw, hh); self._hr.radius = [radius]
            self._hlc.rgba = (*_BLUE_TODAY[:3], 0.55)
            self._hrl.rounded_rectangle = (hx, hy, hw, hh, radius)
        else:
            self._hc.rgba = (0, 0, 0, 0)
            self._hlc.rgba = (0, 0, 0, 0)

        # Dots — centre y at ~29 px from bottom of 151-px cell
        dot_r  = _ff(7.07)
        dot_cy = by + H * _DOT_CY_FRAC
        n      = self._mtg_n
        dens   = _density(n)
        gap    = dot_r * 2.9

        for i, (fc, fe, rc, rl) in enumerate(self._dots):
            dcx = cx + (i - 1) * gap
            fe.pos    = (dcx - dot_r, dot_cy - dot_r)
            fe.size   = (dot_r * 2,   dot_r * 2)
            rl.circle = (dcx, dot_cy, dot_r)
            if n == 0:
                fc.rgba = (0, 0, 0, 0)
                rc.rgba = (*_MUTED[:3], 0.55) if i == 1 else (0, 0, 0, 0)
            elif i < dens:
                fc.rgba = _BLUE_DOT; rc.rgba = (0, 0, 0, 0)
            else:
                fc.rgba = (0, 0, 0, 0); rc.rgba = (0, 0, 0, 0)

    def update(self, day_date: date, mtg_n: int, selected: bool) -> None:
        self._date     = day_date
        self._mtg_n    = mtg_n
        self._selected = selected
        self._is_today = (day_date == display_now().date())
        idx = day_date.weekday()
        self._day_lbl.text  = _DAYS_S[idx]
        self._date_lbl.text = str(day_date.day)
        self._date_lbl.color = _WHITE
        self._sync()


# ── Calendar screen ───────────────────────────────────────────────────────────

class CalendarScreen(BaseScreen):
    """Daily-view calendar matching Figma node 927:61 (1260 × 800 px)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        today = display_now().date()
        self._week_start   = today - timedelta(days=today.weekday())
        self._selected_day = today
        self._week_data: dict = {}
        self._day_cells: list[_DayCell] = []
        self._meet_list: BoxLayout | None = None
        self._intel_busy_lbl: Label | None = None
        self._intel_free_lbl: Label | None = None
        self._free_till_lbl:  Label | None = None
        self._mtg_count_lbl:  Label | None = None
        self._hdr_day_lbl:    Label | None = None
        self._hdr_date_lbl:   Label | None = None
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = FloatLayout(size_hint=(1, 1))

        with root.canvas.before:
            Color(*_BG)
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda w, v: setattr(self._bg, "pos", v),
                  size=lambda w, v: setattr(self._bg, "size", v))

        self._build_header(root)
        self._build_intelligence(root)
        self._build_week_grid(root)
        self._build_daily_summary(root)
        self._build_meetings_area(root)

        self.add_widget(root)

    # ── Header: back btn + "Today" + date + calendar icon ─────────────────────

    def _build_header(self, root: FloatLayout) -> None:
        # Back button — x:24.02, y:21.19, w:76.28, h:76.28 (circular)
        src = _fp("btn_back.png")
        back = _CircleBtn(src=src, on_tap=self.go_back,
                          **_ph(24.02, 21.19, 76.28, 76.28))
        root.add_widget(back)

        # "Today" heading — y:14.13, h:46
        self._hdr_day_lbl = _lbl(
            "Today", _FONT_SB, _ff(38.5), _WHITE,
            **_ph(118.66, 14.13, 200.0, 46.0))
        root.add_widget(self._hdr_day_lbl)

        # Date string — y:60.36, h:33
        self._hdr_date_lbl = _lbl(
            _fmt_date(display_now().date()), _FONT_SB, _ff(27.5), _WHITE,
            **_ph(118.66, 60.36, 250.0, 33.0))
        root.add_widget(self._hdr_date_lbl)

        # Calendar icon — x:241.93, y:20.49, w:36.98, h:33
        cal_src = _fp("icon_calendar.png", "uil_calender.png")
        if cal_src:
            root.add_widget(Image(source=cal_src, fit_mode="contain",
                                  **_ph(241.93, 20.49, 36.98, 33.0)))
        else:
            root.add_widget(_lbl(
                "📅", _FONT, _ff(26), _MUTED,
                halign="center", valign="middle",
                **_ph(241.93, 14.13, 40.0, 46.0)))

    # ── Intelligence: spark + busy/free text (no card background) ─────────────

    def _build_intelligence(self, root: FloatLayout) -> None:
        # Spark icon — x:851.77, y:38.24, ~39×41
        root.add_widget(_lbl(
            "✦", _FONT_SB, _ff(30), _MUTED,
            halign="center", valign="middle",
            **_ph(851.77, 28.0, 42.0, 42.0)))

        # "This Week Busy: ..." — x:905.91, y:19.78, w:299, h:29
        self._intel_busy_lbl = _lbl(
            "This Week Busy: —", _FONT_SB, _ff(24.6), _MUTED,
            **_ph(905.91, 19.78, 299.0, 29.0))
        root.add_widget(self._intel_busy_lbl)

        # "Free: ..." — x:905.91, y:55.46, w:207, h:29
        self._intel_free_lbl = _lbl(
            "Free: —", _FONT_SB, _ff(24.6), _MUTED,
            **_ph(905.91, 55.46, 280.0, 29.0))
        root.add_widget(self._intel_free_lbl)

    # ── Week grid ──────────────────────────────────────────────────────────────

    def _build_week_grid(self, root: FloatLayout) -> None:
        # Grid card background — x:24.02, y:105.94, w:1210.56, h:151.14
        root.add_widget(_GCard(
            ct=_CARD_T, cb=_CARD_B, bdr=_BORDER_T,
            radius=_ff(29.66),
            **_ph(_GX, _GY, _GW, _GH)))

        # 7 day columns
        self._day_cells = []
        for i in range(7):
            d     = self._week_start + timedelta(days=i)
            col_x = _GX + _COL_S[i]
            col_w = _COL_E[i] - _COL_S[i]
            cell  = _DayCell(
                d, self,
                size_hint=(col_w / FW, _GH / FH),
                pos_hint={"x": col_x / FW, "y": (FH - _GY - _GH) / FH})
            cell._selected = (d == self._selected_day)
            root.add_widget(cell)
            self._day_cells.append(cell)

        # Vertical dividers — 2.83 × 84.75, y:33.9 within grid
        for div_x in _DIVS:
            dw = Widget(**_ph(_GX + div_x, _GY + 33.9, 2.83, 84.75))
            with dw.canvas.before:
                Color(2/255, 23/255, 77/255, 0.85)
                _r = Rectangle(pos=dw.pos, size=dw.size)

            def _mk(r):
                def _s(w, *_): r.pos = w.pos; r.size = w.size
                return _s

            dw.bind(pos=_mk(_r), size=_mk(_r))
            root.add_widget(dw)

    # ── Daily summary card ─────────────────────────────────────────────────────

    def _build_daily_summary(self, root: FloatLayout) -> None:
        CW, CH = 1210.56, 100.29
        card = _GCard(
            ct=_CARD_T, cb=_CARD_B, bdr=_BORDER_T,
            radius=_ff(29.66),
            **_ph(25.43, 268.39, CW, CH))

        # Clock icon — x:31.08, y:24.02, 53.68×53.68
        clk = _fp("icon_clock.png", "mingcute_time.png")
        if clk:
            card.add_widget(Image(source=clk, fit_mode="contain",
                                  size_hint=(53.68/CW, 53.68/CH),
                                  pos_hint={"x": 31.08/CW,
                                            "y": (CH - 24.02 - 53.68)/CH}))
        else:
            card.add_widget(_lbl(
                "⏱", _FONT, _ff(38), _MUTED,
                halign="center", valign="middle",
                size_hint=(53.68/CW, 53.68/CH),
                pos_hint={"x": 31.08/CW, "y": (CH - 24.02 - 53.68)/CH}))

        # "You're free till X" — x:97.47, y:31.08, h:39
        self._free_till_lbl = _lbl(
            "Loading…", _FONT_SB, _ff(32.5), _WHITE,
            size_hint=(680/CW, 39/CH),
            pos_hint={"x": 97.47/CW, "y": (CH - 31.08 - 39)/CH})
        card.add_widget(self._free_till_lbl)

        # Sun icon — x:884.26, y:28.25, 49.44×49.44
        sun = _fp("icon_sun.png", "icon_sun_morning_brief.png")
        if sun:
            card.add_widget(Image(source=sun, fit_mode="contain",
                                  size_hint=(49.44/CW, 49.44/CH),
                                  pos_hint={"x": 884.26/CW,
                                            "y": (CH - 28.25 - 49.44)/CH}))
        else:
            card.add_widget(_lbl(
                "☀", _FONT, _ff(34), _MUTED,
                halign="center", valign="middle",
                size_hint=(49.44/CW, 49.44/CH),
                pos_hint={"x": 884.26/CW, "y": (CH - 28.25 - 49.44)/CH}))

        # "X meeting today" — x:943.59, y:35.32, w:236, h:37
        self._mtg_count_lbl = _lbl(
            "— meetings today", _FONT_SB, _ff(31.1), _WHITE,
            size_hint=(280/CW, 37/CH),
            pos_hint={"x": 943.59/CW, "y": (CH - 35.32 - 37)/CH})
        card.add_widget(self._mtg_count_lbl)

        root.add_widget(card)

    # ── Meetings area: separator line + scrollable rows ────────────────────────

    def _build_meetings_area(self, root: FloatLayout) -> None:
        # Vertical separator line — x:203.41, y:377.15, w:2.83, h:355.96
        sep = Widget(**_ph(_SEP_X, _MA_Y, 2.83, 355.96))
        with sep.canvas.before:
            Color(*_SEP_C)
            _sr = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(pos=lambda w, v: setattr(_sr, "pos", v),
                 size=lambda w, v: setattr(_sr, "size", v))
        root.add_widget(sep)

        # ScrollView — full width, from meetings area to screen bottom
        scroll = ScrollView(
            do_scroll_x=False,
            bar_width=3,
            bar_color=(*_BLUE_DOT[:3], 0.4),
            bar_inactive_color=(*_BLUE_DOT[:3], 0.1),
            size_hint=(1.0, _MA_H / FH),
            pos_hint={"x": 0, "y": 0})

        self._meet_list = BoxLayout(
            orientation="vertical",
            spacing=_ff(8),
            padding=[0, _ff(6), 0, _ff(24)],
            size_hint_y=None)
        self._meet_list.bind(minimum_height=self._meet_list.setter("height"))
        scroll.add_widget(self._meet_list)
        root.add_widget(scroll)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_enter(self) -> None:
        self._update_header()
        self._load_week()

    # ── Day selection ──────────────────────────────────────────────────────────

    def _select_day(self, d: date) -> None:
        self._selected_day = d
        self._update_header()
        self._refresh_cells()
        self._refresh_daily_summary()
        self._refresh_meetings()

    def _update_header(self) -> None:
        sel   = self._selected_day
        today = display_now().date()
        if self._hdr_day_lbl:
            self._hdr_day_lbl.text  = "Today" if sel == today else _DAYS_F[sel.weekday()]
        if self._hdr_date_lbl:
            self._hdr_date_lbl.text = _fmt_date(sel)

    # ── Data loading ───────────────────────────────────────────────────────────

    def _load_week(self) -> None:
        ws = self._week_start.isoformat()
        we = (self._week_start + timedelta(days=6)).isoformat()
        self._zero_cells()

        async def _fetch():
            try:
                data = await self.backend.get_calendar_week(ws, we)
                def _apply(_dt):
                    self._week_data = data.get("days", {})
                    self._refresh_cells()
                    self._refresh_intelligence()
                    self._refresh_daily_summary()
                    self._refresh_meetings()
                Clock.schedule_once(_apply, 0)
            except Exception as exc:
                logger.warning("get_calendar_week: %s", exc)
                Clock.schedule_once(lambda _dt: self._refresh_meetings(), 0)

        run_async(_fetch())

    def _zero_cells(self) -> None:
        for i, cell in enumerate(self._day_cells):
            d = self._week_start + timedelta(days=i)
            cell.update(d, 0, d == self._selected_day)

    def _refresh_cells(self) -> None:
        for i, cell in enumerate(self._day_cells):
            d = self._week_start + timedelta(days=i)
            n = len(self._week_data.get(d.isoformat(), {}).get("meetings", []))
            cell.update(d, n, d == self._selected_day)

    def _refresh_intelligence(self) -> None:
        busy: list[str] = []
        free: list[str] = []
        for i in range(7):
            d = self._week_start + timedelta(days=i)
            n = len(self._week_data.get(d.isoformat(), {}).get("meetings", []))
            if _density(n) >= 3:
                busy.append(_DAYS_S[i])
            if n == 0:
                free.append(_DAYS_S[i])

        if self._intel_busy_lbl:
            self._intel_busy_lbl.text = (
                "This Week Busy: " + ", ".join(busy) if busy
                else "This Week: Light schedule")
        if self._intel_free_lbl:
            self._intel_free_lbl.text = (
                f"Free: {free[0]} all day" if len(free) == 1
                else f"Free: {', '.join(free)}" if free
                else "Free: No free days")

    def _refresh_daily_summary(self) -> None:
        d = self._selected_day
        meetings = self._week_data.get(d.isoformat(), {}).get("meetings", [])
        n = len(meetings)

        if self._mtg_count_lbl:
            pl = "s" if n != 1 else ""
            self._mtg_count_lbl.text = f"{n} meeting{pl} today"

        if self._free_till_lbl:
            if not meetings:
                self._free_till_lbl.text = "You're free all day"
            else:
                t = self._fmt_time(meetings[0])
                self._free_till_lbl.text = f"You're free till {t}"

    def _refresh_meetings(self) -> None:
        if self._meet_list is None:
            return
        self._meet_list.clear_widgets()

        d        = self._selected_day
        meetings = self._week_data.get(d.isoformat(), {}).get("meetings", [])

        if not meetings:
            self._meet_list.add_widget(_lbl(
                "No meetings scheduled",
                _FONT_SB, _ff(24), _MUTED,
                halign="center", valign="middle",
                size_hint_y=None, height=_ff(100)))
        else:
            for mtg in meetings:
                self._meet_list.add_widget(self._meeting_row(mtg))

        # "Add event" button — matches Figma width/position
        self._meet_list.add_widget(self._add_event_row())

    # ── Meeting row widget ─────────────────────────────────────────────────────

    def _meeting_row(self, mtg: dict) -> Widget:
        """Full-width row: time label on left + meeting card on right."""
        row_h = _ff(_ROW_H)
        row   = FloatLayout(size_hint_y=None, height=row_h)

        # Time label (left of separator)
        t_str = self._fmt_time(mtg)
        parts = t_str.split(" ")
        hm    = parts[0] if parts else "—"
        ampm  = parts[1] if len(parts) > 1 else ""

        time_box = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            size=(_ff(70), _ff(58)),
            pos_hint={"x": _TL_X / FW, "center_y": 0.5})
        time_box.add_widget(_lbl(
            hm, _FONT_SB, _ff(28.25), _WHITE,
            halign="left", valign="bottom",
            size_hint=(1, 1)))
        time_box.add_widget(_lbl(
            ampm, _FONT_MD, _ff(22.6), _MUTED,
            halign="left", valign="top",
            size_hint=(1, 0.55)))
        row.add_widget(time_box)

        # Dot on separator line
        dot_w = Widget(
            size_hint=(None, None),
            size=(_ff(10), _ff(10)),
            pos_hint={"x": (_SEP_X - 4) / FW, "center_y": 0.5})
        with dot_w.canvas:
            Color(*_BLUE_TODAY)
            _de = Ellipse(pos=dot_w.pos, size=dot_w.size)
        dot_w.bind(pos=lambda w, v: setattr(_de, "pos", v),
                   size=lambda w, v: setattr(_de, "size", v))
        row.add_widget(dot_w)

        # Meeting card — x:276.86, y centred in row, w:954.89, h:104.53
        gap_y  = (_ROW_H - _CARD_H) / 2
        card_h = _ff(_CARD_H)
        card   = FloatLayout(
            size_hint=(None, None),
            size=(_ff(_CARD_W), card_h),
            pos_hint={"x": _CARD_X / FW, "y": gap_y / _ROW_H})

        with card.canvas.before:
            Color(1, 1, 1, 1)
            _cbg = RoundedRectangle(pos=card.pos, size=card.size,
                                    radius=[_ff(25.43)],
                                    texture=_grad(_MTG_T, _MTG_B))
            Color(*_MTG_BDR, 0.8)
            _cln = Line(rounded_rectangle=(card.x, card.y,
                                           card.width, card.height,
                                           _ff(25.43)), width=1.0)

        def _sc(w, *_):
            _cbg.pos = w.pos; _cbg.size = w.size; _cbg.radius = [_ff(25.43)]
            _cln.rounded_rectangle = (w.x, w.y, w.width, w.height, _ff(25.43))

        card.bind(pos=_sc, size=_sc)

        CW, CH = _CARD_W, _CARD_H

        # Icon circle — x:32.49, y:16.95, 70.63×70.63
        icon_f = FloatLayout(
            size_hint=(70.63/CW, 70.63/CH),
            pos_hint={"x": 32.49/CW, "y": (CH - 16.95 - 70.63)/CH})
        with icon_f.canvas.before:
            Color(*_ICON_BG)
            _ib = RoundedRectangle(pos=icon_f.pos, size=icon_f.size, radius=[_ff(16.21)])
            Color(*_BORDER_T, 0.5)
            _il = Line(rounded_rectangle=(icon_f.x, icon_f.y,
                                          icon_f.width, icon_f.height,
                                          _ff(16.21)), width=0.8)

        def _si(w, *_):
            _ib.pos = w.pos; _ib.size = w.size; _ib.radius = [_ff(16.21)]
            _il.rounded_rectangle = (w.x, w.y, w.width, w.height, _ff(16.21))

        icon_f.bind(pos=_si, size=_si)
        title = (mtg.get("title") or "M").strip() or "M"
        icon_f.add_widget(_lbl(
            title[0].upper(), _FONT_SB, _ff(30), _BLUE_TODAY,
            halign="center", valign="middle",
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
        card.add_widget(icon_f)

        # Title — x:129.95, y:16.95, h:34
        card.add_widget(_lbl(
            title, _FONT_SB, _ff(28.25), _WHITE,
            size_hint=(460/CW, 34/CH),
            pos_hint={"x": 129.95/CW, "y": (CH - 16.95 - 34)/CH}))

        # Duration — x:129.95, y:~56, h:31
        dur = self._dur_str(mtg)
        card.add_widget(_lbl(
            f"⏱  {dur}", _FONT_MD, _ff(22.6), _MUTED,
            size_hint=(320/CW, 31/CH),
            pos_hint={"x": 129.95/CW, "y": (CH - 57.0 - 31.0)/CH}))

        # "Join" button — x:607.4, y:24.01, 144.08×56.5
        join = _Btn(
            "Join", _WHITE, _JOIN_T, _JOIN_B, _JOIN_BDR,
            radius=_ff(12.71), font_size=_ff(26.84),
            size_hint=(144.08/CW, 56.5/CH),
            pos_hint={"x": 607.4/CW, "y": (CH - 24.01 - 56.5)/CH})
        card.add_widget(join)

        # "Details" button — x:778.32, y:24.01, 144.08×56.5
        details = _OutlineBtn(
            "Details", _WHITE, _BORDER_T,
            radius=_ff(12.71), font_size=_ff(21.19),
            size_hint=(144.08/CW, 56.5/CH),
            pos_hint={"x": 778.32/CW, "y": (CH - 24.01 - 56.5)/CH})
        card.add_widget(details)

        row.add_widget(card)
        return row

    # ── Add event row ──────────────────────────────────────────────────────────

    def _add_event_row(self) -> Widget:
        """Container row with the 'Add event' button centred at Figma x:440.72."""
        outer = FloatLayout(size_hint_y=None, height=_ff(80))

        btn = _Btn(
            "+ Add event", _BLUE_ADD, _MTG_T, _MTG_B, _MTG_BDR,
            radius=_ff(16.95), font_size=_ff(28.25),
            size_hint=(378.57/FW, 60.74/80),
            pos_hint={"x": 440.72/FW, "center_y": 0.5})
        outer.add_widget(btn)
        return outer

    # ── Intelligence + daily summary helpers ───────────────────────────────────

    def _compute_free_till(self, meetings: list) -> str:
        if not meetings:
            return "You're free all day"
        return f"You're free till {self._fmt_time(meetings[0])}"

    # ── Time / duration helpers ────────────────────────────────────────────────

    def _fmt_time(self, mtg: dict) -> str:
        start = mtg.get("start") or mtg.get("start_time") or ""
        try:
            if "T" in start:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                loc = to_display_local(dt)
                h   = loc.hour % 12 or 12
                m   = loc.minute
                ap  = "AM" if loc.hour < 12 else "PM"
                return f"{h}:{m:02d} {ap}"
        except Exception:
            pass
        if start and len(start) >= 5:
            return start[:5]
        return "—"

    def _dur_str(self, mtg: dict) -> str:
        dur = mtg.get("duration_minutes") or mtg.get("duration")
        if dur:
            try:
                d = int(dur)
                if d < 60:
                    return f"{d} min"
                h, m = divmod(d, 60)
                return f"{h}h {m}min" if m else f"{h}h"
            except Exception:
                pass
        start = mtg.get("start") or ""
        end   = mtg.get("end") or ""
        try:
            if "T" in start and "T" in end:
                s = datetime.fromisoformat(start.replace("Z", "+00:00"))
                e = datetime.fromisoformat(end.replace("Z", "+00:00"))
                d = int((e - s).total_seconds() / 60)
                if d < 60:
                    return f"{d} min"
                h, m = divmod(d, 60)
                return f"{h}h {m}min" if m else f"{h}h"
        except Exception:
            pass
        return "—"

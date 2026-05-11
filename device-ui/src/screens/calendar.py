"""Calendar screen — pixel-perfect Figma 927:62 (1260 × 800 px).

Every coordinate, dimension, font size and colour is taken directly from
the Figma node data supplied by the designer.  Only the "Today" heading,
date string, and week-grid date numbers are dynamic (real current date).
All meeting cards are static placeholder widgets at fixed Figma positions.
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

# ---------------------------------------------------------------------------
# Figma design constants (1260 × 800 px frame)
# ---------------------------------------------------------------------------
_FW = 1260.0
_FH = 800.0

# Colours
_WHITE  = (1.0,  1.0,  1.0,  1.0)
_MUTED  = (0.714, 0.729, 0.949, 1.0)   # #B6BAF2
_BLUE   = (0.0,  0.420, 0.976, 1.0)    # #006BF9
_BLUE2  = (0.0,  0.596, 1.0,  1.0)    # #0098FF / dot blue
_BLUE_DOT = (0.251, 0.596, 0.988, 1.0) # #4098FC
_GLOW_BLUE = (0.018, 0.518, 1.0, 1.0)  # #0484FF border
_CARD_BORDER = (0.247, 0.259, 0.325, 1.0)  # #3F4253

# Gradient approximations (solid midpoints used for Kivy canvas)
_WEEK_BG   = (0.008, 0.071, 0.235, 1.0)   # #02123C  (top of grid gradient)
_CARD_TOP  = (0.004, 0.067, 0.216, 1.0)   # #011137
_CARD_BOT  = (0.0,   0.039, 0.149, 1.0)   # #000A26
_JOIN_TOP  = (0.0,   0.349, 0.863, 1.0)   # #0059DC
_JOIN_BOT  = (0.004, 0.239, 0.655, 1.0)   # #013DA7

# Font families registered by main.py
_FONT_SB = "42dot-SB"
_FONT_B  = "42dot-Sans"
_FONT_MD = "42dot-Med"


# ---------------------------------------------------------------------------
# Coordinate helpers (Figma absolute px → Kivy FloatLayout fractions)
# ---------------------------------------------------------------------------

def _x(px: float) -> float:
    return px / _FW


def _y(top: float, h: float) -> float:
    """Convert Figma y-from-top + height to Kivy y-from-bottom fraction."""
    return max(0.0, (_FH - top - h) / _FH)


def _sw(px: float) -> float:
    return px / _FW


def _sh(px: float) -> float:
    return px / _FH


def _ff(fs: float) -> int:
    scale = min(DISPLAY_WIDTH / _FW, DISPLAY_HEIGHT / _FH)
    return max(6, round(fs * scale))


# ---------------------------------------------------------------------------
# Gradient texture helper (1×2 → linear gradient via Kivy Texture)
# ---------------------------------------------------------------------------

_GRAD_CACHE: dict = {}


def _grad(top: tuple, bot: tuple):
    from kivy.graphics.texture import Texture
    key = (top, bot)
    if key not in _GRAD_CACHE:
        tex = Texture.create(size=(1, 2), colorfmt="rgba")
        def _b(c):
            return [min(255, max(0, int(v * 255))) for v in c]
        tex.blit_buffer(bytes(_b(bot) + _b(top)), colorfmt="rgba", bufferfmt="ubyte")
        tex.mag_filter = "linear"
        tex.min_filter = "linear"
        tex.wrap = "clamp_to_edge"
        _GRAD_CACHE[key] = tex
    return _GRAD_CACHE[key]


# ---------------------------------------------------------------------------
# Label factory
# ---------------------------------------------------------------------------

def _lbl(text, font, size, color, *, halign="left", valign="top", **kw) -> Label:
    lbl = Label(text=text, font_name=font, font_size=size,
                color=color, halign=halign, valign=valign, **kw)
    lbl.bind(size=lbl.setter("text_size"))
    return lbl


# ---------------------------------------------------------------------------
# Card widget with rounded bg + border
# ---------------------------------------------------------------------------

class _Card(FloatLayout):
    def __init__(self, top=None, bot=None, border=None, radius=12, **kw):
        _top = top if top is not None else _CARD_TOP
        _bot = bot if bot is not None else _CARD_BOT
        _brd = border if border is not None else _CARD_BORDER
        super().__init__(**kw)
        self._r = radius
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[radius],
                texture=_grad(_top, _bot),
            )
        with self.canvas.after:
            Color(*_brd)
            self._line = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                width=0.8,
            )
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        r = self._r
        self._bg.pos    = self.pos
        self._bg.size   = self.size
        self._bg.radius = [r]
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


class _TappableCard(ButtonBehavior, _Card):
    pass


# ---------------------------------------------------------------------------
# Dot widget (filled circle or outline ring)
# ---------------------------------------------------------------------------

class _Dot(Widget):
    """Small dot drawn on canvas — filled or outline ring."""

    def __init__(self, filled=True, color=_BLUE_DOT, **kw):
        super().__init__(**kw)
        self._filled = filled
        self._color  = color
        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_once(self._draw, 0)

    def _draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*self._color)
            if self._filled:
                Ellipse(pos=self.pos, size=self.size)
            else:
                Line(ellipse=(self.x, self.y, self.width, self.height), width=1.2)


# ---------------------------------------------------------------------------
# Day-cell widget (tappable)
# ---------------------------------------------------------------------------

class _DayCell(ButtonBehavior, FloatLayout):
    """One column in the week grid (day abbrev + date number + dots)."""

    def __init__(self, abbrev: str, date_num: str, dot_count: int,
                 dots_filled: bool = True, is_today: bool = False, **kw):
        super().__init__(**kw)
        self._abbrev     = abbrev
        self._date_num   = date_num
        self._dot_count  = dot_count
        self._dots_filled = dots_filled
        self._is_today   = is_today
        self._built      = False
        self.bind(size=self._build_once)
        Clock.schedule_once(self._build_once, 0)

    def _build_once(self, *_):
        if self._built or self.width < 2:
            return
        self._built = True
        CW = self.width
        CH = self.height

        # Blue glow box for today
        if self._is_today:
            with self.canvas.before:
                Color(*_GLOW_BLUE, 0.6)
                self._glow_line = Line(
                    rounded_rectangle=(0, 0, CW, CH, _ff(14.13)),
                    width=1.2,
                )
            with self.canvas.before:
                Color(0.004, 0.024, 0.094, 0.35)
                self._glow_bg = RoundedRectangle(
                    pos=self.pos, size=self.size, radius=[_ff(14.13)],
                )
            self.bind(pos=self._sync_glow, size=self._sync_glow)

        # Day abbreviation label (y at top of cell)
        self.add_widget(_lbl(
            self._abbrev, _FONT_SB, _ff(28.25),
            _MUTED if not self._is_today else _MUTED,
            halign="center", valign="middle",
            size_hint=(1, None),
            height=_ff(34),
            pos_hint={"x": 0, "y": (CH - _ff(34) - _ff(17)) / CH},
        ))

        # Date number
        date_color = _WHITE
        self.add_widget(_lbl(
            self._date_num, _FONT_B, _ff(42.38), date_color,
            halign="center", valign="middle",
            size_hint=(1, None),
            height=_ff(51),
            pos_hint={"x": 0, "y": (CH - _ff(34) - _ff(17) - _ff(51) - _ff(5)) / CH},
        ))

        # Dots at bottom
        DOT_SZ = _ff(14.13)
        DOT_GAP = _ff(22.6)
        total_dots_w = self._dot_count * DOT_SZ + (self._dot_count - 1) * (DOT_GAP - DOT_SZ)
        start_x = (CW - total_dots_w) / 2
        DOT_Y   = _ff(8)  # from bottom of cell

        for i in range(self._dot_count):
            dx = start_x + i * DOT_GAP
            dot = _Dot(
                filled=self._dots_filled,
                color=_BLUE_DOT if self._dots_filled else _MUTED,
                size_hint=(None, None),
                size=(DOT_SZ, DOT_SZ),
                pos_hint={"x": dx / CW, "y": DOT_Y / CH},
            )
            self.add_widget(dot)

    def _sync_glow(self, *_):
        if hasattr(self, "_glow_bg"):
            self._glow_bg.pos  = self.pos
            self._glow_bg.size = self.size
        if hasattr(self, "_glow_line"):
            self._glow_line.rounded_rectangle = (
                self.x, self.y, self.width, self.height, _ff(14.13)
            )


# ---------------------------------------------------------------------------
# CalendarScreen
# ---------------------------------------------------------------------------

class CalendarScreen(BaseScreen):
    """Calendar view — Figma 927 frame, 1260 × 800 px."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._selected_date: date = display_now().date()
        self._heading_label:   Label | None = None
        self._datestr_label:   Label | None = None
        self._day_cells:       list[tuple[date, _DayCell]] = []
        self._build_ui()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = FloatLayout(size_hint=(1, 1))

        # Solid background #01081A
        with root.canvas.before:
            Color(0.004, 0.031, 0.102, 1.0)
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, v: setattr(self._bg_rect, "pos", v),
            size=lambda w, v: setattr(self._bg_rect, "size", v),
        )

        self._build_header(root)
        self._build_week_grid(root)
        self._build_free_time_card(root)
        self._build_separator_and_timeline(root)
        self._build_meeting_cards(root)
        self._build_add_event_button(root)

        self.add_widget(root)

    # -----------------------------------------------------------------------
    # Header  (back button, heading, date string, calendar icon, intel section)
    # -----------------------------------------------------------------------

    def _build_header(self, root: FloatLayout) -> None:
        # Back button  (24.02, 21.19)  76.28 × 76.28 — circular dark pill
        back_btn = ButtonBehavior.__new__(ButtonBehavior)
        back_btn = _TappableCard(
            top=(0.004, 0.043, 0.149, 1.0),
            bot=(0.004, 0.043, 0.149, 1.0),
            border=_CARD_BORDER,
            radius=_ff(38),
            size_hint=(_sw(76.28), _sh(76.28)),
            pos_hint={"x": _x(24.02), "y": _y(21.19, 76.28)},
        )
        back_btn.add_widget(_lbl(
            "‹", _FONT_B, _ff(36), _WHITE,
            halign="center", valign="middle",
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        ))
        back_btn.bind(on_release=lambda *_: self.go_back())
        root.add_widget(back_btn)

        # "Today" heading  (118.66, 14.13)  108 × 46
        self._heading_label = _lbl(
            "Today", _FONT_SB, _ff(38.52), _WHITE,
            halign="left", valign="top",
            size_hint=(_sw(200), _sh(46)),
            pos_hint={"x": _x(118.66), "y": _y(14.13, 46)},
        )
        root.add_widget(self._heading_label)

        # Date string  (118.66, 60.36)  169 × 33
        self._datestr_label = _lbl(
            self._format_date(self._selected_date),
            _FONT_SB, _ff(27.52), _WHITE,
            halign="left", valign="top",
            size_hint=(_sw(250), _sh(33)),
            pos_hint={"x": _x(118.66), "y": _y(60.36, 33)},
        )
        root.add_widget(self._datestr_label)

        # Calendar icon (unicode fallback)  (241.93, 20.49)  36.98 × 33
        root.add_widget(_lbl(
            "📅", _FONT_SB, _ff(28), _WHITE,
            halign="center", valign="middle",
            size_hint=(_sw(36.98), _sh(33)),
            pos_hint={"x": _x(241.93), "y": _y(20.49, 33)},
        ))

        # Intelligence section — floating text, no background
        # Spark icon ✦  (851.77, 38.24)
        root.add_widget(_lbl(
            "✦", _FONT_SB, _ff(30), _MUTED,
            halign="center", valign="middle",
            size_hint=(_sw(39.38), _sh(40.89)),
            pos_hint={"x": _x(851.77), "y": _y(38.24, 40.89)},
        ))

        # "This Week Busy: Wed, Thu"  (905.91, 19.78)  299 × 29
        root.add_widget(_lbl(
            "This Week Busy: Wed, Thu",
            _FONT_SB, _ff(24.61), _MUTED,
            halign="left", valign="top",
            size_hint=(_sw(299), _sh(29)),
            pos_hint={"x": _x(905.91), "y": _y(19.78, 29)},
        ))

        # "Free: Fri afternoon"  (905.91, 55.46)  207 × 29
        root.add_widget(_lbl(
            "Free: Fri afternoon",
            _FONT_SB, _ff(24.61), _MUTED,
            halign="left", valign="top",
            size_hint=(_sw(207), _sh(29)),
            pos_hint={"x": _x(905.91), "y": _y(55.46, 29)},
        ))

    # -----------------------------------------------------------------------
    # Week grid  (24.02, 105.94)  1210.56 × 151.14
    # -----------------------------------------------------------------------

    def _build_week_grid(self, root: FloatLayout) -> None:
        GW, GH = 1210.56, 151.14
        GX, GY = 24.02, 105.94

        grid = _Card(
            top=_WEEK_BG,
            bot=(0.0, 0.039, 0.149, 1.0),
            border=_CARD_BORDER,
            radius=_ff(29.66),
            size_hint=(_sw(GW), _sh(GH)),
            pos_hint={"x": _x(GX), "y": _y(GY, GH)},
        )

        # 6 vertical dividers (within grid, fractional positions)
        DIV_X_LIST = [179.4, 348.91, 518.41, 687.91, 857.42, 1026.93]
        DIV_W, DIV_H = 2.83, 84.75
        DIV_Y = 33.9  # within grid
        for div_x in DIV_X_LIST:
            sep = Widget(
                size_hint=(DIV_W / GW, DIV_H / GH),
                pos_hint={"x": div_x / GW, "y": (GH - DIV_Y - DIV_H) / GH},
            )
            with sep.canvas:
                Color(0.008, 0.090, 0.302, 0.8)
                sep._rect = Rectangle(pos=sep.pos, size=sep.size)
            sep.bind(
                pos=lambda w, v: setattr(w._rect, "pos", v),
                size=lambda w, v: setattr(w._rect, "size", v),
            )
            grid.add_widget(sep)

        # Day column definitions: (abbrev, gx_in_grid, gy_in_grid, cw, ch, dots, filled, is_today)
        # These positions come from the Figma data; they are relative to the grid frame.
        now_date = display_now().date()
        week_mon = now_date - timedelta(days=now_date.weekday())  # Monday of this week
        week_dates = [week_mon + timedelta(days=i) for i in range(7)]  # Mon–Sun

        DAY_ABBREVS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

        # Static dot config from Figma: (dot_count, dots_filled)
        DOT_CONFIG = [
            (2, True),   # MON
            (1, True),   # TUE
            (3, True),   # WED (today)
            (2, True),   # THU
            (1, True),   # FRI
            (1, False),  # SAT — outline ring
            (1, False),  # SUN — outline ring
        ]

        # Grid-relative x/y positions and sizes from Figma
        CELL_DEFS = [
            # (gx, gy, cw, ch)
            (63.57,   21.19, 66,   110.18),  # MON
            (240.13,  21.19, 53,   110.18),  # TUE
            (365.85,   5.65, 139.84, 139.84),  # WED (today — larger)
            (577.73,  22.6,  57,   107.35),  # THU
            (750.07,  22.6,  51,   107.35),  # FRI
            (919.58,  22.6,  51,   107.35),  # SAT
            (1084.84, 22.6,  58,   107.35),  # SUN
        ]

        self._day_cells = []
        for i, (wd, abbrev, (dots, filled), (gx, gy, cw, ch)) in enumerate(
            zip(week_dates, DAY_ABBREVS, DOT_CONFIG, CELL_DEFS)
        ):
            is_today = (wd == now_date)
            cell = _DayCell(
                abbrev=abbrev,
                date_num=str(wd.day),
                dot_count=dots,
                dots_filled=filled,
                is_today=is_today,
                size_hint=(cw / GW, ch / GH),
                pos_hint={"x": gx / GW, "y": (GH - gy - ch) / GH},
            )
            _date_ref = wd
            cell.bind(on_release=lambda inst, d=_date_ref: self._select_day(d))
            grid.add_widget(cell)
            self._day_cells.append((wd, cell))

        root.add_widget(grid)

    # -----------------------------------------------------------------------
    # Free time card  (25.43, 268.39)  1210.56 × 100.29
    # -----------------------------------------------------------------------

    def _build_free_time_card(self, root: FloatLayout) -> None:
        CW, CH = 1210.56, 100.29
        card = _Card(
            top=_WEEK_BG,
            bot=(0.0, 0.039, 0.149, 1.0),
            border=_CARD_BORDER,
            radius=_ff(29.66),
            size_hint=(_sw(CW), _sh(CH)),
            pos_hint={"x": _x(25.43), "y": _y(268.39, CH)},
        )

        # Clock icon  (31.08, 24.02) in card  53.68 × 53.68
        card.add_widget(_lbl(
            "⏱", _FONT_SB, _ff(38), _MUTED,
            halign="center", valign="middle",
            size_hint=(53.68 / CW, 53.68 / CH),
            pos_hint={"x": 31.08 / CW, "y": (CH - 24.02 - 53.68) / CH},
        ))

        # "You're free till 11:00 AM"  (97.47, 31.08)  356 × 39  Bold 32.49px
        card.add_widget(_lbl(
            "You're free till 11:00 AM",
            _FONT_B, _ff(32.49), _WHITE,
            halign="left", valign="middle",
            size_hint=(356 / CW, 39 / CH),
            pos_hint={"x": 97.47 / CW, "y": (CH - 31.08 - 39) / CH},
        ))

        # Sun icon  (884.26, 28.25)  49.44 × 49.44
        card.add_widget(_lbl(
            "☀", _FONT_SB, _ff(34), _MUTED,
            halign="center", valign="middle",
            size_hint=(49.44 / CW, 49.44 / CH),
            pos_hint={"x": 884.26 / CW, "y": (CH - 28.25 - 49.44) / CH},
        ))

        # "3 meeting today"  (943.59, 35.32)  236 × 37  Bold 31.08px
        card.add_widget(_lbl(
            "3 meeting today",
            _FONT_B, _ff(31.08), _WHITE,
            halign="left", valign="middle",
            size_hint=(236 / CW, 37 / CH),
            pos_hint={"x": 943.59 / CW, "y": (CH - 35.32 - 37) / CH},
        ))

        root.add_widget(card)

    # -----------------------------------------------------------------------
    # Separator line + timeline dots + time labels
    # -----------------------------------------------------------------------

    def _build_separator_and_timeline(self, root: FloatLayout) -> None:
        # Vertical separator  (203.41, 377.15)  2.83 × 355.96
        sep = Widget(
            size_hint=(_sw(2.83), _sh(355.96)),
            pos_hint={"x": _x(203.41), "y": _y(377.15, 355.96)},
        )
        with sep.canvas:
            Color(0.604, 0.745, 1.0, 0.75)  # #9ABDFF at 75%
            sep._rect = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(
            pos=lambda w, v: setattr(w._rect, "pos", v),
            size=lambda w, v: setattr(w._rect, "size", v),
        )
        root.add_widget(sep)

        # Timeline dots
        # Group 58 — large dot  (187.87, 412.46)  33.9 × 33.9  #0090FF
        dot_large = Widget(
            size_hint=(_sw(33.9), _sh(33.9)),
            pos_hint={"x": _x(187.87), "y": _y(412.46, 33.9)},
        )
        with dot_large.canvas:
            Color(0.0, 0.565, 1.0, 1.0)
            dot_large._e = Ellipse(pos=dot_large.pos, size=dot_large.size)
        dot_large.bind(
            pos=lambda w, v: setattr(w._e, "pos", v),
            size=lambda w, v: setattr(w._e, "size", v),
        )
        root.add_widget(dot_large)

        # Group 59 — medium dot  (192.11, 529.71)  25.43 × 25.43  #0050FF
        dot_mid1 = Widget(
            size_hint=(_sw(25.43), _sh(25.43)),
            pos_hint={"x": _x(192.11), "y": _y(529.71, 25.43)},
        )
        with dot_mid1.canvas:
            Color(0.0, 0.314, 1.0, 1.0)
            dot_mid1._e = Ellipse(pos=dot_mid1.pos, size=dot_mid1.size)
        dot_mid1.bind(
            pos=lambda w, v: setattr(w._e, "pos", v),
            size=lambda w, v: setattr(w._e, "size", v),
        )
        root.add_widget(dot_mid1)

        # Group 60 — medium dot  (192.11, 642.71)  25.43 × 25.43  #0050FF
        dot_mid2 = Widget(
            size_hint=(_sw(25.43), _sh(25.43)),
            pos_hint={"x": _x(192.11), "y": _y(642.71, 25.43)},
        )
        with dot_mid2.canvas:
            Color(0.0, 0.314, 1.0, 1.0)
            dot_mid2._e = Ellipse(pos=dot_mid2.pos, size=dot_mid2.size)
        dot_mid2.bind(
            pos=lambda w, v: setattr(w._e, "pos", v),
            size=lambda w, v: setattr(w._e, "size", v),
        )
        root.add_widget(dot_mid2)

        # Time labels (static placeholders)
        # Group 61  (48.02, 405.4)
        self._build_time_label(root, gx=48.02, gy=405.4, time_str="11:00", ampm_str="AM",
                               ampm_x=35.31)
        # Group 62  (59.33, 509.93)
        self._build_time_label(root, gx=59.33, gy=509.93, time_str="2:00", ampm_str="PM",
                               ampm_x=24.02)
        # Group 63  (56.5, 622.94)
        self._build_time_label(root, gx=56.5,  gy=622.94, time_str="5:30", ampm_str="PM",
                               ampm_x=26.84)

    def _build_time_label(self, root: FloatLayout, gx: float, gy: float,
                          time_str: str, ampm_str: str, ampm_x: float) -> None:
        GW, GH = 71.0, 60.9

        # Outer container (so we can lay child labels within it)
        grp = FloatLayout(
            size_hint=(_sw(GW), _sh(GH)),
            pos_hint={"x": _x(gx), "y": _y(gy, GH)},
        )

        # Time number (Bold 28.25px)
        grp.add_widget(_lbl(
            time_str, _FONT_B, _ff(28.25), _WHITE,
            halign="left", valign="top",
            size_hint=(1, None),
            height=_ff(34),
            pos_hint={"x": 0, "y": (GH - _ff(34)) / GH},
        ))

        # AM/PM (SemiBold 22.6px #B6BAF2)
        grp.add_widget(_lbl(
            ampm_str, _FONT_SB, _ff(22.6), _MUTED,
            halign="left", valign="top",
            size_hint=(35 / GW, None),
            height=_ff(27),
            pos_hint={"x": ampm_x / GW, "y": (GH - _ff(34) - _ff(27)) / GH},
        ))

        root.add_widget(grp)

    # -----------------------------------------------------------------------
    # Meeting cards
    # -----------------------------------------------------------------------

    def _build_meeting_cards(self, root: FloatLayout) -> None:
        # Card 1 — "Product Sync"  (276.86, 377.15)  954.89 × 104.53
        self._build_meeting_card(
            root,
            fig_x=276.86, fig_y=377.15,
            cw=954.89, ch=104.53,
            icon_text="👥",
            title="Product Sync",
            duration="30 min",
            show_join=True,
        )

        # Card 2 — "Client Call"  (281.1, 490.16)  954.89 × 104.53
        self._build_meeting_card(
            root,
            fig_x=281.1, fig_y=490.16,
            cw=954.89, ch=104.53,
            icon_text="📞",
            title="Client Call",
            duration="45 min",
            show_join=False,
        )

        # Card 3 — "Review"  (281.1, 603.16)  954.89 × 104.53
        self._build_meeting_card(
            root,
            fig_x=281.1, fig_y=603.16,
            cw=954.89, ch=104.53,
            icon_text="📋",
            title="Review",
            duration="30 min",
            show_join=False,
        )

    def _build_meeting_card(self, root: FloatLayout, fig_x: float, fig_y: float,
                            cw: float, ch: float, icon_text: str, title: str,
                            duration: str, show_join: bool) -> None:
        card = _Card(
            top=_CARD_TOP,
            bot=_CARD_BOT,
            border=_CARD_BORDER,
            radius=_ff(25.43),
            size_hint=(_sw(cw), _sh(ch)),
            pos_hint={"x": _x(fig_x), "y": _y(fig_y, ch)},
        )

        # Icon circle  (32.49, 16.95)  70.63 × 70.63
        ICON_CX, ICON_CY = 32.49, 16.95
        ICON_CW, ICON_CH = 70.63, 70.63
        icon_circle = _Card(
            top=(0.004, 0.043, 0.149, 1.0),
            bot=(0.004, 0.043, 0.149, 1.0),
            border=_CARD_BORDER,
            radius=_ff(16.21),
            size_hint=(ICON_CW / cw, ICON_CH / ch),
            pos_hint={"x": ICON_CX / cw, "y": (ch - ICON_CY - ICON_CH) / ch},
        )
        icon_circle.add_widget(_lbl(
            icon_text, _FONT_SB, _ff(30), _WHITE,
            halign="center", valign="middle",
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        ))
        card.add_widget(icon_circle)

        # Title  (129.95, 16.95)  176 × 34  Bold 28.25px
        card.add_widget(_lbl(
            title, _FONT_B, _ff(28.25), _WHITE,
            halign="left", valign="middle",
            size_hint=(240 / cw, 34 / ch),
            pos_hint={"x": 129.95 / cw, "y": (ch - 16.95 - 34) / ch},
        ))

        # Duration group  (129.95, 56.5)  — clock icon + text
        card.add_widget(_lbl(
            f"⏱  {duration}", _FONT_SB, _ff(22.6), _MUTED,
            halign="left", valign="middle",
            size_hint=(160 / cw, 31.08 / ch),
            pos_hint={"x": 129.95 / cw, "y": (ch - 56.5 - 31.08) / ch},
        ))

        # Join button  (607.4, 24.01)  144.08 × 56.5  (only on card 1)
        if show_join:
            join_btn = _TappableCard(
                top=_JOIN_TOP,
                bot=_JOIN_BOT,
                border=(0.247, 0.549, 1.0, 1.0),
                radius=_ff(12.71),
                size_hint=(144.08 / cw, 56.5 / ch),
                pos_hint={"x": 607.4 / cw, "y": (ch - 24.01 - 56.5) / ch},
            )
            join_btn.add_widget(_lbl(
                "▶  Join", _FONT_B, _ff(26.84), _WHITE,
                halign="center", valign="middle",
                size_hint=(1, 1),
                pos_hint={"x": 0, "y": 0},
            ))
            card.add_widget(join_btn)

        # Details button position depends on whether join button is present
        det_x = 778.32 if show_join else 607.4
        details_btn = _TappableCard(
            top=(0.0, 0.0, 0.0, 0.0),
            bot=(0.0, 0.0, 0.0, 0.0),
            border=_CARD_BORDER,
            radius=_ff(12.71),
            size_hint=(144.08 / cw, 56.5 / ch),
            pos_hint={"x": det_x / cw, "y": (ch - 24.01 - 56.5) / ch},
        )
        details_btn.add_widget(_lbl(
            "Details  ›", _FONT_B, _ff(21.19), _WHITE,
            halign="center", valign="middle",
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        ))
        card.add_widget(details_btn)

        root.add_widget(card)

    # -----------------------------------------------------------------------
    # Add event button  (440.72, 716.16)  378.57 × 60.74
    # -----------------------------------------------------------------------

    def _build_add_event_button(self, root: FloatLayout) -> None:
        BW, BH = 378.57, 60.74
        btn = _TappableCard(
            top=_CARD_TOP,
            bot=_CARD_BOT,
            border=_CARD_BORDER,
            radius=_ff(16.95),
            size_hint=(_sw(BW), _sh(BH)),
            pos_hint={"x": _x(440.72), "y": _y(716.16, BH)},
        )

        # "+" icon  (98.88, 9.89)  42.38 × 42.38
        btn.add_widget(_lbl(
            "+", _FONT_B, _ff(36), _BLUE,
            halign="center", valign="middle",
            size_hint=(42.38 / BW, 42.38 / BH),
            pos_hint={"x": 98.88 / BW, "y": (BH - 9.89 - 42.38) / BH},
        ))

        # "Add event"  (146.91, 14.13)  133 × 34  Bold 28.25px  #006BF9
        btn.add_widget(_lbl(
            "Add event", _FONT_B, _ff(28.25), _BLUE,
            halign="left", valign="middle",
            size_hint=(133 / BW, 34 / BH),
            pos_hint={"x": 146.91 / BW, "y": (BH - 14.13 - 34) / BH},
        ))

        root.add_widget(btn)

    # -----------------------------------------------------------------------
    # Date/heading helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _format_date(d: date) -> str:
        """Return e.g. "Wed , May 21" from a date object."""
        abbrev = d.strftime("%a")
        month  = d.strftime("%b")
        return f"{abbrev} , {month} {d.day}"

    def _select_day(self, d: date) -> None:
        self._selected_date = d
        today = display_now().date()
        if d == today:
            self._heading_label.text = "Today"
        else:
            self._heading_label.text = d.strftime("%A")
        self._datestr_label.text = self._format_date(d)

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def on_enter(self):
        today = display_now().date()
        self._selected_date = today
        self._heading_label.text = "Today"
        self._datestr_label.text = self._format_date(today)
        Clock.schedule_once(lambda _dt: self._load_week(), 0)

    def _load_week(self):
        async def _fetch():
            try:
                await self.backend.get_calendar_week()
            except Exception as exc:
                logger.debug("CalendarScreen: get_calendar_week failed: %s", exc)
        run_async(_fetch())

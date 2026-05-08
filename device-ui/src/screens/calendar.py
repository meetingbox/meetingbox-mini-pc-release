"""Calendar week-view screen — Figma node 395:204.

Layout (1260 × 800 landscape frame):
  • Header (y=21, h=76): back button · "Calendar" title · settings icon
  • Week nav (y=110, h=50): prev arrow · week label · next arrow
  • Day grid (y=170, h=148): 7 tappable day columns with density dots
  • Intelligence card (y=110, x=944, 292×210): busy days + free time
  • Meetings list (y=342, 1212×406): scrollable meeting rows for selected day
  • Footer
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List

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
from config import (
    ASSETS_DIR,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    display_now,
    to_display_local,
)
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Frame constants  (1260 × 800 landscape — same as HomeScreen)
# ---------------------------------------------------------------------------
_FW, _FH = 1260.0, 800.0

_FIGMA_HOME = ASSETS_DIR / "home" / "figma"
_FIGMA_PROC = ASSETS_DIR / "processing" / "figma"

# Colours (from home-screen Figma palette)
_WHITE       = (1.0, 1.0, 1.0, 1.0)
_MUTED       = (0.714, 0.729, 0.949, 1.0)   # #B6BAF2
_BLUE        = (0.0,   0.420, 0.976, 1.0)   # #006BF9
_BLUE2       = (0.204, 0.506, 0.945, 1.0)   # #3481F1
_GREY        = (0.643, 0.643, 0.675, 1.0)   # #A4A4AC
_BG          = (0.004, 0.031, 0.102, 1.0)   # #010820
_CARD_TOP    = (0.004, 0.067, 0.216, 1.0)   # #011137
_CARD_BOT    = (0.0,   0.039, 0.149, 1.0)   # #000A26
_CARD_BORDER = (0.247, 0.259, 0.325, 1.0)   # #3F4253
_ROW_BG      = (0.004, 0.043, 0.149, 1.0)   # #010B26
_ROW_BORDER  = (0.106, 0.137, 0.212, 1.0)   # #1B2336
_INTEL_BG    = (0.004, 0.051, 0.161, 1.0)   # #010D29

_FONT    = "42dot-Sans"
_FONT_SB = "42dot-SB"
_FONT_MD = "42dot-Med"

_DAY_SHORT  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_DAY_FULL   = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTH_ABB  = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Layout coordinates (Figma top-left origin, pixels)
_COL_LEFT = 24.0    # left edge of first day column
_COL_W    = 128.0   # each column width  (7 × 128 = 896, ends at x=920)
_COL_TOP  = 170.0   # top of day grid
_COL_H    = 148.0   # height of day grid

_INTEL_X  = 944.0   # intelligence card
_INTEL_Y  = 110.0
_INTEL_W  = 292.0
_INTEL_H  = 210.0

_MEET_X   = 24.0    # meetings section  (full-width below grid)
_MEET_Y   = 342.0
_MEET_W   = 1212.0
_MEET_H   = 406.0


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def _x(px: float) -> float:  return px / _FW
def _y(top: float, h: float) -> float:  return max(0.0, (_FH - top - h) / _FH)
def _sw(px: float) -> float: return px / _FW
def _sh(px: float) -> float: return px / _FH


def _ff(fs: float) -> int:
    scale = min(DISPLAY_WIDTH / _FW, DISPLAY_HEIGHT / _FH)
    return max(6, round(fs * scale))


_GRAD_CACHE: dict = {}


def _grad(top: tuple, bot: tuple):
    from kivy.graphics.texture import Texture
    key = (top, bot)
    if key not in _GRAD_CACHE:
        tex = Texture.create(size=(1, 2), colorfmt="rgba")
        def _b(c):
            return [min(255, max(0, int(v * 255))) for v in c]
        tex.blit_buffer(bytes(_b(bot) + _b(top)), colorfmt="rgba", bufferfmt="ubyte")
        tex.mag_filter = tex.min_filter = "linear"
        tex.wrap = "clamp_to_edge"
        _GRAD_CACHE[key] = tex
    return _GRAD_CACHE[key]


def _fp(*names: str) -> str:
    """Return the path of the first existing asset found in home or processing figma dirs."""
    for name in names:
        for d in (_FIGMA_HOME, _FIGMA_PROC):
            p = d / name
            if p.is_file():
                return str(p)
    return ""


def _lbl(text, font, size, color, *, bold=False, halign="left", valign="top", **kw) -> Label:
    lbl = Label(text=text, font_name=font, font_size=size, bold=bold,
                color=color, halign=halign, valign=valign, **kw)
    lbl.bind(size=lbl.setter("text_size"))
    return lbl


def _meeting_density(count: int) -> int:
    """Map meeting count → dot count: 0=none, 1=light, 2=moderate, 3=busy."""
    if count == 0:  return 0
    if count == 1:  return 1
    if count <= 3:  return 2
    return 3


# ---------------------------------------------------------------------------
# Card helpers
# ---------------------------------------------------------------------------

class _Card(FloatLayout):
    def __init__(self, top=None, bot=None, border=None, radius=12, **kw):
        _top = kw.pop("bg", top) or _CARD_TOP
        if bot is None:
            bot = _CARD_BOT
        _brd = border if border is not None else _CARD_BORDER
        super().__init__(**kw)
        self._r = radius
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size,
                                        radius=[radius], texture=_grad(_top, bot))
        with self.canvas.after:
            Color(*_brd)
            self._line = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                width=0.8)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        r = self._r
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bg.radius = [r]
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


class _TappableCard(ButtonBehavior, FloatLayout):
    def __init__(self, top=None, bot=None, border=None, radius=12, draw_bg=True, **kw):
        _top = kw.pop("bg", top) or _CARD_TOP
        if bot is None:
            bot = _CARD_BOT
        _brd = border if border is not None else _CARD_BORDER
        super().__init__(**kw)
        self._r = radius
        if draw_bg:
            with self.canvas.before:
                Color(1, 1, 1, 1)
                self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size,
                                                 radius=[radius], texture=_grad(_top, bot))
            with self.canvas.after:
                Color(*_brd)
                self._line = Line(
                    rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                    width=0.8)
            self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        if not hasattr(self, "_bg_rect"):
            return
        r = self._r
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._bg_rect.radius = [r]
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


# ---------------------------------------------------------------------------
# Day cell widget
# ---------------------------------------------------------------------------

class _DayCell(ButtonBehavior, FloatLayout):
    """One tappable column in the week calendar grid.

    Shows: day abbreviation, date circle (highlighted for today / selected),
    and 1-3 meeting-density dots at the bottom.
    """

    def __init__(self, day_date: date, screen_ref, **kw):
        super().__init__(**kw)
        self._date         = day_date
        self._screen_ref   = screen_ref
        self._meeting_count = 0
        self._selected     = False
        self._is_today     = (day_date == display_now().date())

        idx = day_date.weekday()

        # Day abbreviation label
        self._day_lbl = Label(
            text=_DAY_SHORT[idx],
            font_name=_FONT_MD, font_size=_ff(14),
            color=_MUTED, halign="center", valign="middle",
        )
        self._day_lbl.bind(size=self._day_lbl.setter("text_size"))
        self.add_widget(self._day_lbl)

        # Date number label (rendered on top of the circle)
        self._date_num_lbl = Label(
            text=str(day_date.day),
            font_name=_FONT_SB, font_size=_ff(19),
            color=_WHITE, halign="center", valign="middle",
        )
        self._date_num_lbl.bind(size=self._date_num_lbl.setter("text_size"))
        self.add_widget(self._date_num_lbl)

        # Persistent canvas instructions (updated in-place — no full clear)
        with self.canvas.before:
            # Circle fill (today = solid blue, selected = translucent blue)
            self._circ_fill   = Color(0, 0, 0, 0)
            self._circ_ell    = Ellipse(pos=(0, 0), size=(1, 1))
            # Circle ring (selected day outline)
            self._ring_color  = Color(0, 0, 0, 0)
            self._ring_line   = Line(circle=(0, 0, 0.5), width=1.5)
            # 3 dot slots: (fill Color, fill Ellipse, ring Color, ring Line)
            self._dots: list[tuple] = []
            for _ in range(3):
                fc = Color(0, 0, 0, 0)
                fe = Ellipse(pos=(0, 0), size=(1, 1))
                rc = Color(0, 0, 0, 0)
                rl = Line(circle=(0, 0, 0.5), width=1.0)
                self._dots.append((fc, fe, rc, rl))

        self.bind(pos=self._sync, size=self._sync)
        self.bind(on_release=lambda *_: screen_ref._select_day(self._date))

    # ------------------------------------------------------------------

    def _sync(self, *_):
        W, H = self.width, self.height
        bx, by = self.x, self.y
        if W < 2 or H < 2:
            return

        # Day label — top 20 % of cell
        lbl_h = H * 0.20
        self._day_lbl.pos  = (bx, by + H - lbl_h)
        self._day_lbl.size = (W, lbl_h)

        # Date circle — centered at 60 % from bottom
        cr  = min(W * 0.22, H * 0.20)   # radius
        cx  = bx + W / 2
        cy  = by + H * 0.60

        self._circ_ell.pos  = (cx - cr, cy - cr)
        self._circ_ell.size = (cr * 2, cr * 2)
        self._ring_line.circle = (cx, cy, cr)

        if self._is_today:
            self._circ_fill.rgba  = _BLUE
            self._ring_color.rgba = (0, 0, 0, 0)
            self._date_num_lbl.color = _WHITE
        elif self._selected:
            self._circ_fill.rgba  = (*_BLUE[:3], 0.22)
            self._ring_color.rgba = _BLUE
            self._date_num_lbl.color = _WHITE
        else:
            self._circ_fill.rgba  = (0, 0, 0, 0)
            self._ring_color.rgba = (0, 0, 0, 0)
            # Weekend numbers slightly muted
            self._date_num_lbl.color = _MUTED if self._date.weekday() >= 5 else _WHITE

        # Date label occupies the circle area
        self._date_num_lbl.pos  = (bx, cy - cr)
        self._date_num_lbl.size = (W, cr * 2)

        # Dots — bottom 18 % of cell
        n      = self._meeting_count
        dot_r  = max(3.0, cr * 0.20)
        gap    = dot_r * 3.5
        dot_cy = by + H * 0.13

        for i, (fc, fe, rc, rl) in enumerate(self._dots):
            dcx = bx + W / 2 + (i - 1) * gap
            fe.pos    = (dcx - dot_r, dot_cy - dot_r)
            fe.size   = (dot_r * 2, dot_r * 2)
            rl.circle = (dcx, dot_cy, dot_r)

            if n == 0:
                # 1 centred unfilled ring
                fc.rgba = (0, 0, 0, 0)
                rc.rgba = (*_MUTED[:3], 0.50) if i == 1 else (0, 0, 0, 0)
            else:
                density = _meeting_density(n)
                if i < density:
                    fc.rgba = _BLUE
                    rc.rgba = (0, 0, 0, 0)
                else:
                    fc.rgba = (0, 0, 0, 0)
                    rc.rgba = (0, 0, 0, 0)

    def update(self, day_date: date, meeting_count: int, selected: bool) -> None:
        self._date          = day_date
        self._meeting_count = meeting_count
        self._selected      = selected
        self._is_today      = (day_date == display_now().date())
        self._date_num_lbl.text = str(day_date.day)
        self._day_lbl.text      = _DAY_SHORT[day_date.weekday()]
        self._sync()


# ---------------------------------------------------------------------------
# CalendarScreen
# ---------------------------------------------------------------------------

class CalendarScreen(BaseScreen):
    """Week-view calendar screen, opened from the home-screen calendar widget."""

    def __init__(self, **kw):
        super().__init__(**kw)
        today = display_now().date()
        self._week_start:   date  = today - timedelta(days=today.weekday())
        self._selected_day: date  = today
        self._week_data:    dict  = {}   # ISO date str → {"meetings": [...]}

        self._day_cells:    list[_DayCell] = []
        self._meet_list:    BoxLayout | None = None
        self._day_hdr_lbl:  Label | None = None
        self._intel_busy:   Label | None = None
        self._intel_free:   Label | None = None
        self._week_lbl:     Label | None = None

        self._build_ui()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = FloatLayout(size_hint=(1, 1))

        with root.canvas.before:
            Color(*_BG)
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda w, v: setattr(self._bg_rect, "pos", v),
                  size=lambda w, v: setattr(self._bg_rect, "size", v))

        self._build_header(root)
        self._build_week_nav(root)
        self._build_calendar_grid(root)
        self._build_intelligence_card(root)
        self._build_separator(root)
        self._build_meetings_section(root)

        root.add_widget(self.build_footer())
        self.add_widget(root)

    # ---- Header -----------------------------------------------------------

    def _build_header(self, root: FloatLayout) -> None:
        # Back button
        back = _TappableCard(draw_bg=False,
                             size_hint=(_sw(76), _sh(76)),
                             pos_hint={"x": _x(24), "y": _y(21, 76)})
        back_src = _fp("btn_back.png")
        if back_src:
            back.add_widget(Image(source=back_src, size_hint=(1, 1), fit_mode="contain"))
        else:
            back.add_widget(_lbl("←", _FONT, _ff(34), _WHITE,
                                 halign="center", valign="middle",
                                 size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
        back.bind(on_release=lambda *_: self.go_back())
        root.add_widget(back)

        # Title
        root.add_widget(_lbl(
            "Calendar", _FONT_SB, _ff(38), _WHITE,
            size_hint=(_sw(400), _sh(50)),
            pos_hint={"x": _x(120), "y": _y(33, 50)},
        ))

        # Settings icon
        sg = _TappableCard(draw_bg=False,
                           size_hint=(_sw(76), _sh(76)),
                           pos_hint={"x": _x(1160), "y": _y(21, 76)})
        sg_src = _fp("icon_settings.png", "btn_settings.png")
        if sg_src:
            sg.add_widget(Image(source=sg_src, size_hint=(1, 1), fit_mode="contain"))
        sg.bind(on_release=lambda *_: self.goto("settings"))
        root.add_widget(sg)

    # ---- Week navigation bar ---------------------------------------------

    def _build_week_nav(self, root: FloatLayout) -> None:
        NAV_Y, NAV_H = 110.0, 50.0

        # Previous-week arrow
        prev_btn = _TappableCard(draw_bg=False,
                                 size_hint=(_sw(44), _sh(44)),
                                 pos_hint={"x": _x(24), "y": _y(NAV_Y + 3, 44)})
        prev_btn.add_widget(_lbl("‹", _FONT, _ff(32), _MUTED,
                                 halign="center", valign="middle",
                                 size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
        prev_btn.bind(on_release=self._go_prev_week)
        root.add_widget(prev_btn)

        # Week range label
        self._week_lbl = _lbl(
            self._format_week_label(),
            _FONT_SB, _ff(20), _WHITE,
            halign="center", valign="middle",
            size_hint=(_sw(760), _sh(NAV_H)),
            pos_hint={"x": _x(76), "y": _y(NAV_Y, NAV_H)},
        )
        root.add_widget(self._week_lbl)

        # Next-week arrow
        next_btn = _TappableCard(draw_bg=False,
                                 size_hint=(_sw(44), _sh(44)),
                                 pos_hint={"x": _x(848), "y": _y(NAV_Y + 3, 44)})
        next_btn.add_widget(_lbl("›", _FONT, _ff(32), _MUTED,
                                 halign="center", valign="middle",
                                 size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
        next_btn.bind(on_release=self._go_next_week)
        root.add_widget(next_btn)

    # ---- 7-day calendar grid ---------------------------------------------

    def _build_calendar_grid(self, root: FloatLayout) -> None:
        self._day_cells = []
        for i in range(7):
            d = self._week_start + timedelta(days=i)
            cell_x = _COL_LEFT + i * _COL_W
            cell = _DayCell(
                d, self,
                size_hint=(_sw(_COL_W - 8), _sh(_COL_H)),
                pos_hint={"x": _x(cell_x + 4), "y": _y(_COL_TOP, _COL_H)},
            )
            cell._selected = (d == self._selected_day)
            root.add_widget(cell)
            self._day_cells.append(cell)

    # ---- Intelligence card (top-right) -----------------------------------

    def _build_intelligence_card(self, root: FloatLayout) -> None:
        card = _Card(
            bg=_INTEL_BG, bot=_INTEL_BG,
            border=_CARD_BORDER,
            radius=_ff(16),
            size_hint=(_sw(_INTEL_W), _sh(_INTEL_H)),
            pos_hint={"x": _x(_INTEL_X), "y": _y(_INTEL_Y, _INTEL_H)},
        )

        IW, IH = _INTEL_W, _INTEL_H

        # Header
        card.add_widget(_lbl(
            "✦  This Week", _FONT_SB, _ff(15), _MUTED,
            size_hint=((IW - 40) / IW, 20 / IH),
            pos_hint={"x": 20 / IW, "y": (IH - 30 - 20) / IH},
        ))

        # Thin divider after header
        div = Widget(size_hint=((IW - 40) / IW, 1 / IH),
                     pos_hint={"x": 20 / IW, "y": (IH - 56) / IH})
        with div.canvas.before:
            Color(*_CARD_BORDER)
            div_r = Rectangle(pos=div.pos, size=div.size)
        div.bind(pos=lambda w, v: setattr(div_r, "pos", v),
                 size=lambda w, v: setattr(div_r, "size", v))
        card.add_widget(div)

        # Busy days
        card.add_widget(_lbl(
            "Busy Days", _FONT_MD, _ff(13), _GREY,
            size_hint=((IW - 40) / IW, 16 / IH),
            pos_hint={"x": 20 / IW, "y": (IH - 74 - 16) / IH},
        ))
        self._intel_busy = _lbl(
            "—", _FONT_SB, _ff(16), _WHITE,
            size_hint=((IW - 40) / IW, 24 / IH),
            pos_hint={"x": 20 / IW, "y": (IH - 74 - 16 - 28) / IH},
        )
        card.add_widget(self._intel_busy)

        # Free time
        card.add_widget(_lbl(
            "Free Time", _FONT_MD, _ff(13), _GREY,
            size_hint=((IW - 40) / IW, 16 / IH),
            pos_hint={"x": 20 / IW, "y": (IH - 136 - 16) / IH},
        ))
        self._intel_free = _lbl(
            "—", _FONT_SB, _ff(16), _WHITE,
            size_hint=((IW - 40) / IW, 24 / IH),
            pos_hint={"x": 20 / IW, "y": (IH - 136 - 16 - 28) / IH},
        )
        card.add_widget(self._intel_free)

        root.add_widget(card)

    # ---- Horizontal separator --------------------------------------------

    def _build_separator(self, root: FloatLayout) -> None:
        sep = Widget(size_hint=(_sw(896), _sh(2)),
                     pos_hint={"x": _x(24), "y": _y(330, 2)})
        with sep.canvas.before:
            Color(*_CARD_BORDER)
            sep_r = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(pos=lambda w, v: setattr(sep_r, "pos", v),
                 size=lambda w, v: setattr(sep_r, "size", v))
        root.add_widget(sep)

    # ---- Meetings section (scrollable list for selected day) --------------

    def _build_meetings_section(self, root: FloatLayout) -> None:
        card = _Card(
            radius=_ff(16),
            size_hint=(_sw(_MEET_W), _sh(_MEET_H)),
            pos_hint={"x": _x(_MEET_X), "y": _y(_MEET_Y, _MEET_H)},
        )
        MW, MH = _MEET_W, _MEET_H

        # Day header
        self._day_hdr_lbl = _lbl(
            "—", _FONT_SB, _ff(18), _WHITE,
            size_hint=((MW - 40) / MW, 28 / MH),
            pos_hint={"x": 20 / MW, "y": (MH - 20 - 28) / MH},
        )
        card.add_widget(self._day_hdr_lbl)

        # Scrollable meeting list
        scroll = ScrollView(
            do_scroll_x=False,
            size_hint=(1, (MH - 60) / MH),
            pos_hint={"x": 0, "y": 0},
            bar_width=4,
            bar_color=(*_BLUE[:3], 0.4),
            bar_inactive_color=(*_BLUE[:3], 0.15),
        )
        self._meet_list = BoxLayout(
            orientation="vertical",
            spacing=int(8 * DISPLAY_HEIGHT / _FH),
            padding=[int(20 * DISPLAY_WIDTH / _FW), int(8 * DISPLAY_HEIGHT / _FH)],
            size_hint_y=None,
        )
        self._meet_list.bind(minimum_height=self._meet_list.setter("height"))
        scroll.add_widget(self._meet_list)
        card.add_widget(scroll)

        root.add_widget(card)

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def on_enter(self) -> None:
        self._load_week()

    # -----------------------------------------------------------------------
    # Week / day navigation
    # -----------------------------------------------------------------------

    def _go_prev_week(self, *_) -> None:
        self._week_start   -= timedelta(weeks=1)
        self._selected_day  = self._week_start
        self._load_week()

    def _go_next_week(self, *_) -> None:
        self._week_start   += timedelta(weeks=1)
        self._selected_day  = self._week_start
        self._load_week()

    def _select_day(self, d: date) -> None:
        self._selected_day = d
        self._refresh_day_cells()
        self._refresh_meetings()

    # -----------------------------------------------------------------------
    # Data loading
    # -----------------------------------------------------------------------

    def _load_week(self) -> None:
        start = self._week_start.isoformat()
        end   = (self._week_start + timedelta(days=6)).isoformat()

        if self._week_lbl:
            self._week_lbl.text = self._format_week_label()

        self._rebuild_day_cells()

        async def _fetch():
            try:
                data = await self.backend.get_calendar_week(start, end)
                def _apply(_dt):
                    self._week_data = data.get("days", {})
                    self._refresh_day_cells()
                    self._refresh_intelligence()
                    self._refresh_meetings()
                Clock.schedule_once(_apply, 0)
            except Exception as exc:
                logger.warning("get_calendar_week failed: %s", exc)
                Clock.schedule_once(lambda _dt: self._refresh_meetings(), 0)

        run_async(_fetch())

    def _rebuild_day_cells(self) -> None:
        """Reassign dates when week changes (zeroes meeting counts until data arrives)."""
        for i, cell in enumerate(self._day_cells):
            d   = self._week_start + timedelta(days=i)
            sel = (d == self._selected_day)
            cell.update(d, 0, sel)

    def _refresh_day_cells(self) -> None:
        """Update dot density and selection highlight from current week_data."""
        for i, cell in enumerate(self._day_cells):
            d    = self._week_start + timedelta(days=i)
            ds   = d.isoformat()
            n    = len(self._week_data.get(ds, {}).get("meetings", []))
            sel  = (d == self._selected_day)
            cell.update(d, n, sel)

    def _refresh_intelligence(self) -> None:
        busy_text, free_text = self._compute_intelligence()
        if self._intel_busy:
            self._intel_busy.text = busy_text
        if self._intel_free:
            self._intel_free.text = free_text

    def _refresh_meetings(self) -> None:
        if self._meet_list is None:
            return
        self._meet_list.clear_widgets()

        d   = self._selected_day
        ds  = d.isoformat()
        idx = d.weekday()
        meetings = self._week_data.get(ds, {}).get("meetings", [])
        n = len(meetings)

        if self._day_hdr_lbl:
            plural = "s" if n != 1 else ""
            self._day_hdr_lbl.text = (
                f"{_DAY_FULL[idx]}, {_MONTH_ABB[d.month - 1]} {d.day}"
                f"  ·  {n} meeting{plural}"
            )

        if not meetings:
            lbl = _lbl(
                "No meetings scheduled", _FONT_MD, _ff(18), _GREY,
                halign="center", valign="middle",
                size_hint_y=None,
                height=int(64 * DISPLAY_HEIGHT / _FH),
            )
            lbl.bind(size=lbl.setter("text_size"))
            self._meet_list.add_widget(lbl)
            return

        for mtg in meetings:
            self._meet_list.add_widget(self._build_meeting_row(mtg))

    # -----------------------------------------------------------------------
    # Meeting row builder
    # -----------------------------------------------------------------------

    def _build_meeting_row(self, mtg: dict) -> Widget:
        RH = int(64 * DISPLAY_HEIGHT / _FH)
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=RH,
            spacing=int(16 * DISPLAY_WIDTH / _FW),
            padding=[int(16 * DISPLAY_WIDTH / _FW), int(10 * DISPLAY_HEIGHT / _FH)],
        )

        with row.canvas.before:
            Color(*_ROW_BG)
            row_bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[_ff(12)])
            Color(*_ROW_BORDER)
            row_ln = Line(rounded_rectangle=(row.x, row.y, row.width, row.height, _ff(12)), width=0.7)

        def _sync_row(w, *_):
            row_bg.pos  = w.pos
            row_bg.size = w.size
            row_ln.rounded_rectangle = (w.x, w.y, w.width, w.height, _ff(12))

        row.bind(pos=_sync_row, size=_sync_row)

        # Time column
        time_str = self._format_meeting_time(mtg)
        time_lbl = Label(
            text=time_str,
            font_name=_FONT_SB, font_size=_ff(15),
            color=_BLUE2,
            halign="right", valign="middle",
            size_hint=(None, 1),
            width=int(84 * DISPLAY_WIDTH / _FW),
        )
        time_lbl.bind(size=time_lbl.setter("text_size"))
        row.add_widget(time_lbl)

        # Divider pip
        pip = Widget(size_hint=(None, 1), width=int(2 * DISPLAY_WIDTH / _FW))
        with pip.canvas.before:
            Color(*_CARD_BORDER)
            pip_r = Rectangle(pos=pip.pos, size=pip.size)
        pip.bind(pos=lambda w, v: setattr(pip_r, "pos", v),
                 size=lambda w, v: setattr(pip_r, "size", v))
        row.add_widget(pip)

        # Title column
        title = (mtg.get("title") or "Calendar event").strip() or "Calendar event"
        title_lbl = Label(
            text=title,
            font_name=_FONT_SB, font_size=_ff(17),
            color=_WHITE,
            halign="left", valign="middle",
            size_hint=(1, 1),
        )
        title_lbl.bind(size=title_lbl.setter("text_size"))
        row.add_widget(title_lbl)

        return row

    # -----------------------------------------------------------------------
    # Intelligence computation
    # -----------------------------------------------------------------------

    def _compute_intelligence(self) -> tuple[str, str]:
        busy_days: list[str] = []
        free_days: list[str] = []
        max_free_n  = -1
        best_free   = ""

        for i in range(7):
            d  = self._week_start + timedelta(days=i)
            ds = d.isoformat()
            n  = len(self._week_data.get(ds, {}).get("meetings", []))

            if _meeting_density(n) == 3:
                busy_days.append(_DAY_SHORT[i])
            if n == 0:
                free_days.append(_DAY_SHORT[i])

        busy_text = ", ".join(busy_days) if busy_days else "No busy days"

        if free_days:
            free_text = f"{free_days[0]} · open all day"
        elif busy_days:
            free_text = "Schedule is packed"
        else:
            free_text = "Light week ahead"

        return busy_text, free_text

    # -----------------------------------------------------------------------
    # Formatting helpers
    # -----------------------------------------------------------------------

    def _format_week_label(self) -> str:
        ws = self._week_start
        we = ws + timedelta(days=6)
        if ws.month == we.month:
            return (
                f"{_DAY_SHORT[0]} {ws.day} – {_DAY_SHORT[6]} {we.day} "
                f"{_MONTH_ABB[ws.month - 1]} {ws.year}"
            )
        return (
            f"{_MONTH_ABB[ws.month - 1]} {ws.day} – "
            f"{_MONTH_ABB[we.month - 1]} {we.day}, {ws.year}"
        )

    def _format_meeting_time(self, mtg: dict) -> str:
        start = mtg.get("start") or mtg.get("start_time") or ""
        try:
            if "T" in start:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                return to_display_local(dt).strftime("%I:%M %p").lstrip("0")
        except Exception:
            pass
        return start[:5] if start else "—"

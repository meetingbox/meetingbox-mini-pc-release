"""Calendar week-view screen — Figma node 395:204.

Device and Figma frame: 1260 × 800 px (landscape). All coordinates are direct
Figma pixel values — no scaling is needed because the device matches exactly.

Layout zones (all values in Figma / device pixels, y measured from top):
  Header      y=20,  h=72    back btn · "Calendar" · settings
  Week nav    y=108, h=48    prev · week-range label · next
  Day grid    y=168, h=164   7 tappable day columns (Mon–Sun)
  Intel card  y=108, x=940, w=296, h=224   busy-days + free-time
  Separator   y=340, h=2
  Meetings    y=356, h=392   scrollable meeting rows for selected day
  Footer      y=760, h=40

Day column internal layout (col_h = 164 px):
  0–22px    day abbreviation label   (Mon / Tue / …)
  22–50px   gap
  50–102px  date circle (52 px ⌀)   blue-filled = today, ring = selected
  102–144px gap
  144–154px meeting-density dots     3 = busy, 2 = moderate, 1 = light, 1 ring = none
  154–164px bottom padding
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
from config import (
    ASSETS_DIR,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    display_now,
    to_display_local,
)
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

# ── Frame ────────────────────────────────────────────────────────────────────
_FW, _FH = 1260.0, 800.0
_FIGMA_HOME = ASSETS_DIR / "home" / "figma"
_FIGMA_PROC = ASSETS_DIR / "processing" / "figma"

# ── Colours (Figma palette, shared with home.py) ─────────────────────────────
_WHITE       = (1.0, 1.0, 1.0, 1.0)
_MUTED       = (0.714, 0.729, 0.949, 1.0)   # #B6BAF2
_BLUE        = (0.0,   0.420, 0.976, 1.0)   # #006BF9
_BLUE2       = (0.204, 0.506, 0.945, 1.0)   # #3481F1
_GREY        = (0.643, 0.643, 0.675, 1.0)   # #A4A4AC
_BG          = (0.004, 0.031, 0.102, 1.0)   # #010820
_CARD_TOP    = (0.004, 0.067, 0.216, 1.0)
_CARD_BOT    = (0.0,   0.039, 0.149, 1.0)
_CARD_BORDER = (0.247, 0.259, 0.325, 1.0)
_ROW_BG      = (0.004, 0.043, 0.149, 1.0)
_ROW_BORDER  = (0.106, 0.137, 0.212, 1.0)
_INTEL_BG    = (0.004, 0.051, 0.161, 1.0)

_FONT    = "42dot-Sans"
_FONT_SB = "42dot-SB"
_FONT_MD = "42dot-Med"

_DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_DAY_FULL  = ["Monday", "Tuesday", "Wednesday", "Thursday",
               "Friday", "Saturday", "Sunday"]
_MONTH_ABB = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]

# ── Layout constants (Figma px = device px on 1260 × 800) ───────────────────
_COL_LEFT = 24.0     # x of first column slot
_COL_W    = 128.0    # slot width  (7 × 128 = 896, ends at x = 920)
_COL_TOP  = 168.0    # grid top
_COL_H    = 164.0    # grid height

# Day column internal proportions (fractions of _COL_H)
_CIRC_CY_FRAC  = 1.0 - 76.0  / _COL_H   # circle-center y from BOTTOM fraction
_CIRC_R        = 26            # radius in px (52 px ⌀)
_DOT_CY_FRAC   = 1.0 - 149.0 / _COL_H   # dot-centre y from BOTTOM fraction
_DOT_R         = 5             # dot radius in px

# Intelligence card
_INTEL_X = 940.0
_INTEL_Y = 108.0
_INTEL_W = 296.0
_INTEL_H = 224.0

# Meetings section (below the separator at y=340)
_MEET_X   = 24.0
_MEET_Y   = 356.0
_MEET_W   = 1212.0
_MEET_H   = 392.0

# Footer
_FOOT_Y = 760.0
_FOOT_H = 40.0


# ── Coordinate helpers ────────────────────────────────────────────────────────

def _x(px: float) -> float:   return px / _FW
def _y(top: float, h: float) -> float:  return max(0.0, (_FH - top - h) / _FH)
def _sw(px: float) -> float:  return px / _FW
def _sh(px: float) -> float:  return px / _FH


def _ff(fs: float) -> int:
    """Font size in screen pixels (scale=1 on 1260×800, proportional otherwise)."""
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
    """First existing file across home-figma and processing-figma dirs."""
    for name in names:
        for d in (_FIGMA_HOME, _FIGMA_PROC):
            p = d / name
            if p.is_file():
                return str(p)
    return ""


def _lbl(text, font, size, color, *, bold=False,
         halign="left", valign="top", **kw) -> Label:
    lbl = Label(text=text, font_name=font, font_size=size, bold=bold,
                color=color, halign=halign, valign=valign, **kw)
    lbl.bind(size=lbl.setter("text_size"))
    return lbl


def _meeting_density(count: int) -> int:
    """0=none · 1=light (1 mtg) · 2=moderate (2–3) · 3=busy (4+)."""
    if count == 0: return 0
    if count == 1: return 1
    if count <= 3: return 2
    return 3


# ── Card helpers ──────────────────────────────────────────────────────────────

class _Card(FloatLayout):
    def __init__(self, top=None, bot=None, border=None, radius=12, **kw):
        _top = kw.pop("bg", top) or _CARD_TOP
        if bot    is None: bot    = _CARD_BOT
        if border is None: border = _CARD_BORDER
        super().__init__(**kw)
        self._r = radius
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[radius],
                texture=_grad(_top, bot))
        with self.canvas.after:
            Color(*border)
            self._ln = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                width=0.8)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        r = self._r
        self._bg.pos = self.pos;  self._bg.size = self.size;  self._bg.radius = [r]
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


class _TappableCard(ButtonBehavior, FloatLayout):
    def __init__(self, top=None, bot=None, border=None, radius=12, draw_bg=True, **kw):
        _top = kw.pop("bg", top) or _CARD_TOP
        if bot    is None: bot    = _CARD_BOT
        if border is None: border = _CARD_BORDER
        super().__init__(**kw)
        self._r = radius
        if draw_bg:
            with self.canvas.before:
                Color(1, 1, 1, 1)
                self._bg = RoundedRectangle(
                    pos=self.pos, size=self.size, radius=[radius],
                    texture=_grad(_top, bot))
            with self.canvas.after:
                Color(*border)
                self._ln = Line(
                    rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                    width=0.8)
            self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        if not hasattr(self, "_bg"): return
        r = self._r
        self._bg.pos = self.pos;  self._bg.size = self.size;  self._bg.radius = [r]
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


# ── Day cell ─────────────────────────────────────────────────────────────────

class _DayCell(ButtonBehavior, FloatLayout):
    """One tappable column in the 7-day week grid.

    IMPORTANT: Every child label uses explicit size_hint + pos_hint so Kivy's
    FloatLayout manages their geometry — we never set .pos/.size manually on
    label children (that would conflict with the layout engine).

    Canvas circle and dots are drawn via canvas.before with persistent
    Color/Ellipse/Line instructions updated in _sync_canvas().
    """

    # Internal proportions (fractions of column height)
    _DAY_LBL_H   = 22.0 / _COL_H   # top   0–22 px
    _CIRC_CTR    = 1.0 - 76.0 / _COL_H    # circle centre as fraction from BOTTOM
    _CIRC_DIAM   = 52.0 / _COL_H   # date-label height matches circle diameter
    _DOT_CTR     = 1.0 - 149.0 / _COL_H   # dot centre as fraction from BOTTOM

    def __init__(self, day_date: date, screen_ref, **kw):
        super().__init__(**kw)
        self._date         = day_date
        self._screen_ref   = screen_ref
        self._meeting_count = 0
        self._selected     = False
        self._is_today     = (day_date == display_now().date())

        idx = day_date.weekday()   # 0=Mon … 6=Sun

        # ── Day abbreviation label (top 22 px of column) ─────────────────
        # Uses size_hint + pos_hint so FloatLayout owns its geometry.
        self._day_lbl = Label(
            text=_DAY_SHORT[idx],
            font_name=_FONT_MD, font_size=_ff(14),
            color=_MUTED,
            halign="center", valign="middle",
            size_hint=(1.0, self._DAY_LBL_H),
            pos_hint={"x": 0, "top": 1.0},
        )
        self._day_lbl.bind(size=self._day_lbl.setter("text_size"))
        self.add_widget(self._day_lbl)

        # ── Date number label (overlaid on top of the circle) ────────────
        self._date_lbl = Label(
            text=str(day_date.day),
            font_name=_FONT_SB, font_size=_ff(20),
            color=_WHITE,
            halign="center", valign="middle",
            size_hint=(1.0, self._CIRC_DIAM),
            pos_hint={"x": 0, "center_y": self._CIRC_CTR},
        )
        self._date_lbl.bind(size=self._date_lbl.setter("text_size"))
        self.add_widget(self._date_lbl)

        # ── Persistent canvas instructions for circle + dots ─────────────
        with self.canvas.before:
            # Circle fill (today = solid blue, selected = translucent blue)
            self._cc  = Color(0, 0, 0, 0)
            self._ce  = Ellipse(pos=(0, 0), size=(1, 1))
            # Circle ring (selected state outline)
            self._rc  = Color(0, 0, 0, 0)
            self._rl  = Line(circle=(0, 0, 0.5), width=1.5)
            # Three dot slots: fill Color, fill Ellipse, ring Color, ring Line
            self._dots: list[tuple] = []
            for _ in range(3):
                fc = Color(0, 0, 0, 0);  fe = Ellipse(pos=(0,0), size=(1,1))
                rc = Color(0, 0, 0, 0);  rl = Line(circle=(0,0,0.5), width=1.0)
                self._dots.append((fc, fe, rc, rl))

        # Bind canvas update to layout changes
        self.bind(pos=self._sync_canvas, size=self._sync_canvas)
        self.bind(on_release=lambda *_: screen_ref._select_day(self._date))

    # ── Canvas drawing ────────────────────────────────────────────────────

    def _sync_canvas(self, *_) -> None:
        W, H = self.width, self.height
        bx, by = self.x, self.y
        if W < 2 or H < 2:
            return

        cx  = bx + W / 2
        # Scale circle radius proportionally if column isn't the design size
        cr  = _CIRC_R * (H / _COL_H)
        cy  = by + H * self._CIRC_CTR

        # Circle fill / ring
        self._ce.pos  = (cx - cr, cy - cr)
        self._ce.size = (cr * 2, cr * 2)
        self._rl.circle = (cx, cy, cr)

        if self._is_today:
            self._cc.rgba = _BLUE
            self._rc.rgba = (0, 0, 0, 0)
            self._date_lbl.color = _WHITE
        elif self._selected:
            self._cc.rgba = (*_BLUE[:3], 0.20)
            self._rc.rgba = _BLUE
            self._date_lbl.color = _WHITE
        else:
            self._cc.rgba = (0, 0, 0, 0)
            self._rc.rgba = (0, 0, 0, 0)
            # Slightly mute weekends
            self._date_lbl.color = _MUTED if self._date.weekday() >= 5 else _WHITE

        # Dots
        n       = self._meeting_count
        density = _meeting_density(n)
        dot_r   = _DOT_R * (H / _COL_H)
        gap     = dot_r * 2.6          # centre-to-centre spacing
        dot_cy  = by + H * self._DOT_CTR

        for i, (fc, fe, rc, rl) in enumerate(self._dots):
            dcx = cx + (i - 1) * gap
            fe.pos    = (dcx - dot_r, dot_cy - dot_r)
            fe.size   = (dot_r * 2, dot_r * 2)
            rl.circle = (dcx, dot_cy, dot_r)

            if n == 0:
                # Single centred unfilled ring
                fc.rgba = (0, 0, 0, 0)
                rc.rgba = (*_MUTED[:3], 0.55) if i == 1 else (0, 0, 0, 0)
            else:
                if i < density:
                    fc.rgba = _BLUE;  rc.rgba = (0, 0, 0, 0)
                else:
                    fc.rgba = (0, 0, 0, 0);  rc.rgba = (0, 0, 0, 0)

    # ── Public update API ─────────────────────────────────────────────────

    def update(self, day_date: date, meeting_count: int, selected: bool) -> None:
        self._date          = day_date
        self._meeting_count = meeting_count
        self._selected      = selected
        self._is_today      = (day_date == display_now().date())

        idx = day_date.weekday()
        self._day_lbl.text  = _DAY_SHORT[idx]
        self._date_lbl.text = str(day_date.day)

        # Refresh text colour (canvas will be redrawn by _sync_canvas if pos/size unchanged)
        self._date_lbl.color = (
            _WHITE if (self._is_today or self._selected)
            else (_MUTED if idx >= 5 else _WHITE)
        )
        # Force canvas redraw
        self._sync_canvas()


# ── Calendar screen ───────────────────────────────────────────────────────────

class CalendarScreen(BaseScreen):
    """Full week-view calendar — Figma node 395:204, 1260 × 800 px."""

    def __init__(self, **kw):
        super().__init__(**kw)
        today = display_now().date()
        self._week_start:    date       = today - timedelta(days=today.weekday())
        self._selected_day:  date       = today
        self._week_data:     dict       = {}

        self._day_cells:    list[_DayCell] = []
        self._meet_list:    BoxLayout | None = None
        self._day_hdr_lbl:  Label | None = None
        self._intel_busy:   Label | None = None
        self._intel_free:   Label | None = None
        self._week_lbl:     Label | None = None

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = FloatLayout(size_hint=(1, 1))

        # Solid background
        with root.canvas.before:
            Color(*_BG)
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda w, v: setattr(self._bg_rect, "pos", v),
                  size=lambda w, v: setattr(self._bg_rect, "size", v))

        self._build_header(root)
        self._build_week_nav(root)
        self._build_day_grid(root)
        self._build_intelligence_card(root)
        self._build_separator(root)
        self._build_meetings_section(root)

        root.add_widget(self.build_footer())
        self.add_widget(root)

    # ── Header (y=20, h=72) ───────────────────────────────────────────────

    def _build_header(self, root: FloatLayout) -> None:
        HY, HH = 20.0, 72.0

        # Back button
        back = _TappableCard(
            draw_bg=False,
            size_hint=(_sw(72), _sh(HH)),
            pos_hint={"x": _x(24), "y": _y(HY, HH)},
        )
        src = _fp("btn_back.png")
        if src:
            back.add_widget(Image(source=src, size_hint=(1, 1), fit_mode="contain"))
        else:
            back.add_widget(_lbl(
                "‹", _FONT, _ff(40), _WHITE,
                halign="center", valign="middle",
                size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            ))
        back.bind(on_release=lambda *_: self.go_back())
        root.add_widget(back)

        # Title
        root.add_widget(_lbl(
            "Calendar", _FONT_SB, _ff(36), _WHITE,
            size_hint=(_sw(420), _sh(44)),
            pos_hint={"x": _x(116), "y": _y(HY + 14, 44)},
        ))

        # Settings icon
        sg = _TappableCard(
            draw_bg=False,
            size_hint=(_sw(72), _sh(HH)),
            pos_hint={"x": _x(1164), "y": _y(HY, HH)},
        )
        sg_src = _fp("icon_settings.png", "btn_settings.png")
        if sg_src:
            sg.add_widget(Image(source=sg_src, size_hint=(1, 1), fit_mode="contain"))
        sg.bind(on_release=lambda *_: self.goto("settings"))
        root.add_widget(sg)

    # ── Week navigation bar (y=108, h=48) ────────────────────────────────

    def _build_week_nav(self, root: FloatLayout) -> None:
        NY, NH = 108.0, 48.0
        BTN_SZ = 40.0

        prev = _TappableCard(
            draw_bg=False,
            size_hint=(_sw(BTN_SZ), _sh(BTN_SZ)),
            pos_hint={"x": _x(24), "y": _y(NY + (NH - BTN_SZ) / 2, BTN_SZ)},
        )
        prev.add_widget(_lbl(
            "‹", _FONT, _ff(28), _MUTED,
            halign="center", valign="middle",
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
        ))
        prev.bind(on_release=self._go_prev_week)
        root.add_widget(prev)

        self._week_lbl = _lbl(
            self._format_week_label(),
            _FONT_SB, _ff(18), _WHITE,
            halign="center", valign="middle",
            size_hint=(_sw(840), _sh(NH)),
            pos_hint={"x": _x(72), "y": _y(NY, NH)},
        )
        root.add_widget(self._week_lbl)

        nxt = _TappableCard(
            draw_bg=False,
            size_hint=(_sw(BTN_SZ), _sh(BTN_SZ)),
            pos_hint={"x": _x(880), "y": _y(NY + (NH - BTN_SZ) / 2, BTN_SZ)},
        )
        nxt.add_widget(_lbl(
            "›", _FONT, _ff(28), _MUTED,
            halign="center", valign="middle",
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
        ))
        nxt.bind(on_release=self._go_next_week)
        root.add_widget(nxt)

    # ── Day grid: 7 _DayCell columns (y=_COL_TOP, h=_COL_H) ─────────────

    def _build_day_grid(self, root: FloatLayout) -> None:
        # Thin card background behind the day grid for visual separation
        grid_card = _Card(
            radius=_ff(16),
            size_hint=(_sw(_COL_W * 7), _sh(_COL_H + 16)),
            pos_hint={"x": _x(_COL_LEFT), "y": _y(_COL_TOP - 8, _COL_H + 16)},
        )
        root.add_widget(grid_card)

        self._day_cells = []
        for i in range(7):
            d      = self._week_start + timedelta(days=i)
            cell_x = _COL_LEFT + i * _COL_W
            # Each cell has 4 px padding on each side within the 128-px slot
            cell = _DayCell(
                d, self,
                size_hint=(_sw(_COL_W - 8), _sh(_COL_H)),
                pos_hint={"x": _x(cell_x + 4), "y": _y(_COL_TOP, _COL_H)},
            )
            cell._selected = (d == self._selected_day)
            root.add_widget(cell)
            self._day_cells.append(cell)

        # Vertical dividers between columns
        for i in range(1, 7):
            div_x = _COL_LEFT + i * _COL_W
            div = Widget(
                size_hint=(_sw(1), _sh(_COL_H - 24)),
                pos_hint={"x": _x(div_x), "y": _y(_COL_TOP + 12, _COL_H - 24)},
            )
            with div.canvas.before:
                Color(*_CARD_BORDER, 0.6)
                _dr = Rectangle(pos=div.pos, size=div.size)

            def _make_sync(r):
                def _s(w, *_):
                    r.pos = w.pos; r.size = w.size
                return _s

            div.bind(pos=_make_sync(_dr), size=_make_sync(_dr))
            root.add_widget(div)

    # ── Intelligence card (top-right, y=108, x=940) ───────────────────────

    def _build_intelligence_card(self, root: FloatLayout) -> None:
        IW, IH = _INTEL_W, _INTEL_H

        card = _Card(
            bg=_INTEL_BG, bot=_INTEL_BG,
            border=_CARD_BORDER,
            radius=_ff(16),
            size_hint=(_sw(IW), _sh(IH)),
            pos_hint={"x": _x(_INTEL_X), "y": _y(_INTEL_Y, IH)},
        )

        # "This Week" header
        card.add_widget(_lbl(
            "✦  This Week", _FONT_SB, _ff(14), _MUTED,
            halign="left", valign="middle",
            size_hint=((IW - 40) / IW, 20 / IH),
            pos_hint={"x": 20 / IW, "y": (IH - 30 - 20) / IH},
        ))

        # Thin divider
        div = Widget(
            size_hint=((IW - 40) / IW, 1 / IH),
            pos_hint={"x": 20 / IW, "y": (IH - 56) / IH},
        )
        with div.canvas.before:
            Color(*_CARD_BORDER)
            div_r = Rectangle(pos=div.pos, size=div.size)
        div.bind(pos=lambda w, v: setattr(div_r, "pos", v),
                 size=lambda w, v: setattr(div_r, "size", v))
        card.add_widget(div)

        # Busy Days
        card.add_widget(_lbl(
            "Busy Days", _FONT_MD, _ff(12), _GREY,
            halign="left", valign="middle",
            size_hint=((IW - 40) / IW, 16 / IH),
            pos_hint={"x": 20 / IW, "y": (IH - 72 - 16) / IH},
        ))
        self._intel_busy = _lbl(
            "—", _FONT_SB, _ff(15), _WHITE,
            halign="left", valign="middle",
            size_hint=((IW - 40) / IW, 24 / IH),
            pos_hint={"x": 20 / IW, "y": (IH - 72 - 16 - 28) / IH},
        )
        card.add_widget(self._intel_busy)

        # Free Time
        card.add_widget(_lbl(
            "Free Time", _FONT_MD, _ff(12), _GREY,
            halign="left", valign="middle",
            size_hint=((IW - 40) / IW, 16 / IH),
            pos_hint={"x": 20 / IW, "y": (IH - 136 - 16) / IH},
        ))
        self._intel_free = _lbl(
            "—", _FONT_SB, _ff(15), _WHITE,
            halign="left", valign="middle",
            size_hint=((IW - 40) / IW, 24 / IH),
            pos_hint={"x": 20 / IW, "y": (IH - 136 - 16 - 28) / IH},
        )
        card.add_widget(self._intel_free)

        root.add_widget(card)

    # ── Separator (y=340) ─────────────────────────────────────────────────

    def _build_separator(self, root: FloatLayout) -> None:
        sep = Widget(
            size_hint=(_sw(896), _sh(1)),
            pos_hint={"x": _x(24), "y": _y(340, 1)},
        )
        with sep.canvas.before:
            Color(*_CARD_BORDER)
            sep_r = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(pos=lambda w, v: setattr(sep_r, "pos", v),
                 size=lambda w, v: setattr(sep_r, "size", v))
        root.add_widget(sep)

    # ── Meetings section (y=356, h=392) ──────────────────────────────────

    def _build_meetings_section(self, root: FloatLayout) -> None:
        MW, MH = _MEET_W, _MEET_H
        card = _Card(
            radius=_ff(16),
            size_hint=(_sw(MW), _sh(MH)),
            pos_hint={"x": _x(_MEET_X), "y": _y(_MEET_Y, MH)},
        )

        # Day header
        self._day_hdr_lbl = _lbl(
            "—", _FONT_SB, _ff(17), _WHITE,
            halign="left", valign="middle",
            size_hint=((MW - 40) / MW, 28 / MH),
            pos_hint={"x": 20 / MW, "y": (MH - 18 - 28) / MH},
        )
        card.add_widget(self._day_hdr_lbl)

        # Thin rule below day header
        hr = Widget(
            size_hint=((MW - 40) / MW, 1 / MH),
            pos_hint={"x": 20 / MW, "y": (MH - 52) / MH},
        )
        with hr.canvas.before:
            Color(*_CARD_BORDER)
            hr_r = Rectangle(pos=hr.pos, size=hr.size)
        hr.bind(pos=lambda w, v: setattr(hr_r, "pos", v),
                size=lambda w, v: setattr(hr_r, "size", v))
        card.add_widget(hr)

        # Scrollable meeting list
        scroll = ScrollView(
            do_scroll_x=False,
            size_hint=(1, (MH - 60) / MH),
            pos_hint={"x": 0, "y": 0},
            bar_width=3,
            bar_color=(*_BLUE[:3], 0.4),
            bar_inactive_color=(*_BLUE[:3], 0.15),
        )
        self._meet_list = BoxLayout(
            orientation="vertical",
            spacing=int(8 * DISPLAY_HEIGHT / _FH),
            padding=[int(20 * DISPLAY_WIDTH / _FW), int(10 * DISPLAY_HEIGHT / _FH)],
            size_hint_y=None,
        )
        self._meet_list.bind(minimum_height=self._meet_list.setter("height"))
        scroll.add_widget(self._meet_list)
        card.add_widget(scroll)

        root.add_widget(card)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def on_enter(self) -> None:
        self._load_week()

    # ── Navigation ────────────────────────────────────────────────────────

    def _go_prev_week(self, *_) -> None:
        self._week_start  -= timedelta(weeks=1)
        self._selected_day = self._week_start
        self._load_week()

    def _go_next_week(self, *_) -> None:
        self._week_start  += timedelta(weeks=1)
        self._selected_day = self._week_start
        self._load_week()

    def _select_day(self, d: date) -> None:
        self._selected_day = d
        self._refresh_cells()
        self._refresh_meetings()

    # ── Data loading ──────────────────────────────────────────────────────

    def _load_week(self) -> None:
        start = self._week_start.isoformat()
        end   = (self._week_start + timedelta(days=6)).isoformat()

        if self._week_lbl:
            self._week_lbl.text = self._format_week_label()
        self._zero_cells()

        async def _fetch():
            try:
                data = await self.backend.get_calendar_week(start, end)
                def _apply(_dt):
                    self._week_data = data.get("days", {})
                    self._refresh_cells()
                    self._refresh_intelligence()
                    self._refresh_meetings()
                Clock.schedule_once(_apply, 0)
            except Exception as exc:
                logger.warning("get_calendar_week: %s", exc)
                Clock.schedule_once(lambda _dt: self._refresh_meetings(), 0)

        run_async(_fetch())

    def _zero_cells(self) -> None:
        """Reset all cells to current week's dates with 0 meetings while data loads."""
        for i, cell in enumerate(self._day_cells):
            d   = self._week_start + timedelta(days=i)
            sel = (d == self._selected_day)
            cell.update(d, 0, sel)

    def _refresh_cells(self) -> None:
        for i, cell in enumerate(self._day_cells):
            d   = self._week_start + timedelta(days=i)
            n   = len(self._week_data.get(d.isoformat(), {}).get("meetings", []))
            sel = (d == self._selected_day)
            cell.update(d, n, sel)

    def _refresh_intelligence(self) -> None:
        busy, free = self._compute_intelligence()
        if self._intel_busy: self._intel_busy.text = busy
        if self._intel_free:  self._intel_free.text  = free

    def _refresh_meetings(self) -> None:
        if self._meet_list is None:
            return
        self._meet_list.clear_widgets()

        d        = self._selected_day
        idx      = d.weekday()
        meetings = self._week_data.get(d.isoformat(), {}).get("meetings", [])
        n        = len(meetings)

        if self._day_hdr_lbl:
            pl = "s" if n != 1 else ""
            self._day_hdr_lbl.text = (
                f"{_DAY_FULL[idx]}, {_MONTH_ABB[d.month - 1]} {d.day}"
                f"  ·  {n} meeting{pl}"
            )

        if not meetings:
            lbl = _lbl(
                "No meetings scheduled",
                _FONT_MD, _ff(16), _GREY,
                halign="center", valign="middle",
                size_hint_y=None,
                height=int(60 * DISPLAY_HEIGHT / _FH),
            )
            lbl.bind(size=lbl.setter("text_size"))
            self._meet_list.add_widget(lbl)
            return

        for mtg in meetings:
            self._meet_list.add_widget(self._meeting_row(mtg))

    # ── Meeting row ───────────────────────────────────────────────────────

    def _meeting_row(self, mtg: dict) -> Widget:
        RH = int(60 * DISPLAY_HEIGHT / _FH)
        pad_h = int(16 * DISPLAY_WIDTH  / _FW)
        pad_v = int(10 * DISPLAY_HEIGHT / _FH)

        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=RH,
            spacing=int(14 * DISPLAY_WIDTH / _FW),
            padding=[pad_h, pad_v],
        )

        with row.canvas.before:
            Color(*_ROW_BG)
            rr = RoundedRectangle(pos=row.pos, size=row.size, radius=[_ff(12)])
            Color(*_ROW_BORDER)
            rl = Line(rounded_rectangle=(row.x, row.y, row.width, row.height, _ff(12)), width=0.7)

        def _rs(w, *_):
            rr.pos  = w.pos; rr.size = w.size
            rl.rounded_rectangle = (w.x, w.y, w.width, w.height, _ff(12))

        row.bind(pos=_rs, size=_rs)

        # Blue dot
        dot = Label(
            text="●", font_size=_ff(10), color=_BLUE,
            size_hint=(None, 1), width=int(18 * DISPLAY_WIDTH / _FW),
            halign="center", valign="middle",
        )
        dot.bind(size=dot.setter("text_size"))
        row.add_widget(dot)

        # Time
        time_lbl = Label(
            text=self._format_time(mtg),
            font_name=_FONT_SB, font_size=_ff(15),
            color=_BLUE2,
            halign="left", valign="middle",
            size_hint=(None, 1),
            width=int(88 * DISPLAY_WIDTH / _FW),
        )
        time_lbl.bind(size=time_lbl.setter("text_size"))
        row.add_widget(time_lbl)

        # Title
        title = (mtg.get("title") or "Calendar event").strip() or "Calendar event"
        title_lbl = Label(
            text=title,
            font_name=_FONT_SB, font_size=_ff(16),
            color=_WHITE,
            halign="left", valign="middle",
            size_hint=(1, 1),
        )
        title_lbl.bind(size=title_lbl.setter("text_size"))
        row.add_widget(title_lbl)

        return row

    # ── Intelligence computation ──────────────────────────────────────────

    def _compute_intelligence(self) -> tuple[str, str]:
        busy: list[str] = []
        free: list[str] = []
        for i in range(7):
            d = self._week_start + timedelta(days=i)
            n = len(self._week_data.get(d.isoformat(), {}).get("meetings", []))
            if _meeting_density(n) == 3:
                busy.append(_DAY_SHORT[i])
            if n == 0:
                free.append(_DAY_SHORT[i])

        busy_text = ", ".join(busy) if busy else "No busy days"
        if free:
            free_text = f"{free[0]} · open all day"
        elif busy:
            free_text = "Schedule is packed"
        else:
            free_text = "Light week ahead"
        return busy_text, free_text

    # ── Helpers ───────────────────────────────────────────────────────────

    def _format_week_label(self) -> str:
        ws = self._week_start
        we = ws + timedelta(days=6)
        if ws.month == we.month:
            return (f"{_DAY_SHORT[0]} {ws.day} – "
                    f"{_DAY_SHORT[6]} {we.day} "
                    f"{_MONTH_ABB[ws.month - 1]} {ws.year}")
        return (f"{_MONTH_ABB[ws.month - 1]} {ws.day} – "
                f"{_MONTH_ABB[we.month - 1]} {we.day}, {ws.year}")

    def _format_time(self, mtg: dict) -> str:
        start = mtg.get("start") or mtg.get("start_time") or ""
        try:
            if "T" in start:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                return to_display_local(dt).strftime("%I:%M %p").lstrip("0")
        except Exception:
            pass
        return start[:5] if start else "—"

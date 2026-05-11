"""Calendar screen — pixel-perfect from Figma 927:61 (1260 × 800 px).

All visual assets are downloaded directly from Figma and referenced by path.
Layout uses a fully flat FloatLayout so every pos_hint is computed at
construction time (no deferred _build_once timing issues).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from async_helper import run_async
from config import ASSETS_DIR, DISPLAY_HEIGHT, DISPLAY_WIDTH, display_now
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

# ── Design frame ──────────────────────────────────────────────────────────────
FW, FH = 1260.0, 800.0

# ── Figma-downloaded asset paths ──────────────────────────────────────────────
_CAL = ASSETS_DIR / "calendar" / "figma"

def _asset(name: str) -> str:
    p = _CAL / name
    return str(p) if p.is_file() else ""


# ── Colours (exact Figma hex) ─────────────────────────────────────────────────
_BG      = (1/255,   8/255,  26/255, 1.0)   # #01081A  background
_WHITE   = (1.0, 1.0, 1.0, 1.0)
_MUTED   = (182/255, 186/255, 242/255, 1.0)  # #B6BAF2
_BDOT    = (64/255,  152/255, 252/255, 1.0)  # #4098FC  dots filled
_BLUE_A  = (0.0, 107/255, 249/255, 1.0)     # #006BF9  add-event label
_BTDAY   = (4/255,  132/255, 255/255, 1.0)  # #0484FF  today-border

# Card fill gradients
_CARD_T  = (2/255,   18/255,  60/255, 1.0)  # #02123C  top
_CARD_B  = (0.0,    10/255,  38/255, 1.0)   # #000A26  bottom

# Border colours (start colour of Figma gradient strokes)
# fill_RDXD5N → #3F4253 (grid card, free card)
_BDR_CARD = (63/255,  66/255,  83/255, 1.0)  # #3F4253
# fill_QE1YKH → #21284B (meeting cards, add-event)
_BDR_MTG  = (33/255,  40/255,  75/255, 1.0)  # #21284B
# fill_X3J4FE → #3F8CFF (Join button AND Details button — same Figma stroke)
_BDR_BTN  = (63/255, 140/255, 255/255, 1.0)  # #3F8CFF
# fill_JNFIQY → #3F4253 (icon circles inside meeting cards)
_BDR_ICON = (63/255,  66/255,  83/255, 1.0)  # #3F4253

# Meeting card fill
_MTG_T   = (1/255,   17/255,  55/255, 1.0)  # #011137
_MTG_B   = (0.0,    10/255,  38/255, 1.0)   # #000A26

# Join button fill  fill_6LSSN6 → #0059DC → #013DA7
_JOIN_T  = (0.0,    89/255, 220/255, 1.0)   # #0059DC
_JOIN_B  = (1/255,   61/255, 167/255, 1.0)  # #013DA7

# Icon-circle background
_ICON_BG = (1/255,   11/255,  38/255, 1.0)  # #010B26

_FSB = "42dot-SB"   # SemiBold
_FB  = "42dot-Sans"  # Bold weight


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


# ── Tappable image button ─────────────────────────────────────────────────────

class _ImgBtn(ButtonBehavior, Image):
    """An Image widget that fires on_release when tapped."""
    pass


# ── Gradient card ─────────────────────────────────────────────────────────────

class _Card(FloatLayout):
    def __init__(self, ct: tuple, cb: tuple, bdr: tuple, r: float = 12,
                 bdr_alpha: float = 0.9, **kw):
        super().__init__(**kw)
        self._r = r
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[r], texture=_grad(ct, cb))
        with self.canvas.after:
            # bdr is a 4-tuple (r,g,b,a); passing *bdr + bdr_alpha = 5 args
            # which Kivy's Color silently ignores.  Slice to RGB then add alpha.
            Color(*bdr[:3], bdr_alpha)
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


# ── Day-cell highlight overlay ────────────────────────────────────────────────

class _Highlight(Widget):
    """Highlight box drawn on top of the grid background for one day cell."""

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


class _TapZone(ButtonBehavior, Widget):
    pass


# ── Column layout data (from Figma dev mode) ──────────────────────────────────
#
# Grid frame: GX=24.02, GY=105.94, GW=1210.56, GH=151.14
#
# Each tuple:
#   outer_x, outer_y, outer_w, outer_h  ← outer group in grid (for tap zone)
#   inner_dx, inner_dy                  ← inner content offset within outer group
#   abbrev_dx, abbrev_dy, aw, ah        ← day-abbreviation label (within inner)
#   date_dx,   date_dy,  dw, dh         ← date-number label (within inner)
#   [(dot_dx, dot_dy, filled), ...]      ← dots (within inner group)

GX, GY = 24.02, 105.94

_COLS = [
    # MON — 63.57,21.19 66×110.18
    (63.57,   21.19,  66.0,   110.18, 0.00,  0.00,
     0.00,  0.00,  66.0, 34.0,   9.89, 38.14, 47.0, 51.0,
     [(15.54, 96.05, True), (38.14, 96.05, True)]),
    # TUE — 240.13,21.19 53×110.18
    (240.13,  21.19,  53.0,   110.18, 0.00,  0.00,
     0.00,  0.00,  53.0, 34.0,   1.41, 39.55, 51.0, 51.0,
     [(16.95, 96.05, True)]),
    # WED — 365.85,5.65 139.84×139.84 (today in Figma); inner offset 38.14,16.95
    (365.85,   5.65, 139.84,  139.84, 38.14, 16.95,
     1.41,  0.00,  64.0, 34.0,  11.30, 38.14, 46.0, 51.0,
     [(0.00, 93.23, True), (22.60, 93.23, True), (45.20, 93.23, True)]),
    # THU — 577.73,22.6 57×107.35
    (577.73,  22.60,  57.0,   107.35, 0.00,  0.00,
     0.00,  0.00,  57.0, 34.0,   4.23, 38.14, 49.0, 51.0,
     [(21.19, 93.23, True), (43.79, 93.23, True)]),
    # FRI — 750.07,22.6 51×107.35
    (750.07,  22.60,  51.0,   107.35, 0.00,  0.00,
     2.82,  0.00,  47.0, 34.0,   0.00, 38.14, 51.0, 51.0,
     [(18.36, 93.23, True)]),
    # SAT — 919.58,22.6 51×107.35  (outline dot)
    (919.58,  22.60,  51.0,   107.35, 0.00,  0.00,
     0.00,  0.00,  51.0, 34.0,   0.00, 38.14, 51.0, 51.0,
     [(18.37, 93.23, False)]),
    # SUN — 1084.84,22.6 58×107.35  (outline dot)
    (1084.84, 22.60,  58.0,   107.35, 0.00,  0.00,
     0.00,  0.00,  58.0, 34.0,   4.24, 38.14, 51.0, 51.0,
     [(22.60, 93.23, False)]),
]

# WED-style highlight dimensions: the Figma "today" box is 139.84×139.84
# starting at grid y=5.65 (nearly flush with grid top).  We apply these same
# fixed dimensions to whichever column is "today" so the highlight always looks
# like the Figma's WED treatment.
_HL_H  = 139.84   # highlight height (matches WED outer group)
_HL_Y  = GY + 5.65  # screen y of highlight top-edge

_DAY_ABBR = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_DAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]
_MONTHS   = ["Jan","Feb","Mar","Apr","May","Jun",
             "Jul","Aug","Sep","Oct","Nov","Dec"]


def _fmt_date(d: date) -> str:
    return f"{d.strftime('%a')} , {_MONTHS[d.month - 1]} {d.day}"


# ── CalendarScreen ────────────────────────────────────────────────────────────

class CalendarScreen(BaseScreen):
    """Calendar view — Figma 927:61, pixel-perfect flat layout."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._sel_date: date = display_now().date()
        self._heading_lbl: Label | None = None
        self._datestr_lbl: Label | None = None
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
    # Figma nodes referenced (all screen-absolute):
    #   927:62  back button     24.02, 21.19  76.28×76.28
    #   927:65  "Today"        118.66, 14.13  108×46
    #   927:66  date string    118.66, 60.36  169×33
    #   927:67  calendar icon  241.93, 20.49  36.98×33
    #   927:71  spark icon     851.77, 38.24  39.38×40.89
    #   927:69  busy text      905.91, 19.78  299×29
    #   927:70  free text      905.91, 55.46  207×29

    def _build_header(self, root: FloatLayout) -> None:
        # Back button — use exact Figma PNG (includes circle bg + gradient stroke)
        back_src = _asset("btn_back.png")
        if back_src:
            back = _ImgBtn(source=back_src, fit_mode="contain",
                           **_ph(24.02, 21.19, 76.28, 76.28))
            back.bind(on_release=lambda *_: self.go_back())
        else:
            back = _TapCard(ct=_ICON_BG, cb=_ICON_BG, bdr=_BDR_CARD,
                            r=_ff(38), **_ph(24.02, 21.19, 76.28, 76.28))
            back.add_widget(_lbl("‹", _FB, _ff(36), _WHITE,
                                 ha="center", va="middle",
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

        # Calendar icon  241.93, 20.49  36.98×33
        root.add_widget(_lbl(
            "📅", _FSB, _ff(28), _WHITE, ha="center", va="middle",
            **_ph(241.93, 20.49, 36.98, 33.0)))

        # Spark / intelligence icon  851.77, 38.24  39.38×40.89
        spark_src = _asset("icon_spark.png")
        if spark_src:
            root.add_widget(Image(source=spark_src, fit_mode="contain",
                                  **_ph(851.77, 28.0, 39.38, 40.89)))
        else:
            root.add_widget(_lbl(
                "✦", _FSB, _ff(30), _MUTED, ha="center", va="middle",
                **_ph(851.77, 28.0, 42.0, 42.0)))

        # Busy text  905.91, 19.78  299×29
        root.add_widget(_lbl(
            "This Week Busy: Wed, Thu", _FSB, _ff(24.61), _MUTED,
            **_ph(905.91, 19.78, 299.0, 29.0)))

        # Free text  905.91, 55.46  207×29
        root.add_widget(_lbl(
            "Free: Fri afternoon", _FSB, _ff(24.61), _MUTED,
            **_ph(905.91, 55.46, 207.0, 29.0)))

    # ── Week grid ──────────────────────────────────────────────────────────────

    def _build_grid(self, root: FloatLayout) -> None:
        # Grid background card  24.02, 105.94  1210.56×151.14  r=29.66
        root.add_widget(_Card(
            ct=_CARD_T, cb=_CARD_B, bdr=_BDR_CARD,
            r=_ff(29.66),
            **_ph(GX, GY, 1210.56, 151.14)))

        today = display_now().date()
        week_mon = today - timedelta(days=today.weekday())
        self._col_dates = [week_mon + timedelta(days=i) for i in range(7)]

        # Six vertical dividers  w=2.83, h=84.75, y=33.9 within grid
        for div_x in (179.4, 348.91, 518.41, 687.91, 857.42, 1026.93):
            sx, sy = GX + div_x, GY + 33.9
            dv = Widget(**_ph(sx, sy, 2.83, 84.75))
            with dv.canvas.before:
                Color(2/255, 23/255, 77/255, 0.85)
                _r = Rectangle(pos=dv.pos, size=dv.size)
            def _mk(r):
                def _s(w, *_): r.pos = w.pos; r.size = w.size
                return _s
            dv.bind(pos=_mk(_r), size=_mk(_r))
            root.add_widget(dv)

        # Per-column: WED-style highlight, tap zone, abbrev label, date label, dots
        self._highlights.clear()
        self._date_lbls.clear()

        for col_idx, col_data in enumerate(_COLS):
            (ox, oy, ow, oh,
             idx_x, idy,
             adx, ady, aw, ah,
             ddx, ddy, dw, dh,
             dots) = col_data

            outer_sx = GX + ox
            inner_sx = outer_sx + idx_x
            inner_sy = GY + oy + idy
            col_date = self._col_dates[col_idx]
            is_today = (col_date == today)

            # Today highlight — always WED-style: 139.84px tall, centered on
            # the outer-group x centre, starting at _HL_Y (grid top + 5.65).
            hl_cx  = outer_sx + ow / 2         # outer group horizontal centre
            hl_x   = hl_cx - _HL_H / 2         # highlight left edge
            hl     = _Highlight(
                mode="today" if is_today else "none",
                **_ph(hl_x, _HL_Y, _HL_H, _HL_H))   # square 139.84×139.84
            root.add_widget(hl)
            self._highlights.append(hl)

            # Tap zone covers the outer group
            tz = _TapZone(**_ph(outer_sx, GY + oy, ow, oh))
            tz.bind(on_release=lambda inst, d=col_date, i=col_idx:
                    self._select_day(d, i))
            root.add_widget(tz)

            # Day abbreviation
            root.add_widget(_lbl(
                _DAY_ABBR[col_idx], _FSB, _ff(28.25), _MUTED,
                ha="center", va="middle",
                **_ph(inner_sx + adx, inner_sy + ady, aw, ah)))

            # Date number (dynamic)
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
                dw2 = Widget(**_ph(dot_sx, dot_sy, 14.13, 14.13))
                if filled:
                    with dw2.canvas:
                        Color(*_BDOT)
                        _e = Ellipse(pos=dw2.pos, size=dw2.size)
                    def _mk_e(e):
                        def _s(w, *_): e.pos = w.pos; e.size = w.size
                        return _s
                    dw2.bind(pos=_mk_e(_e), size=_mk_e(_e))
                else:
                    with dw2.canvas:
                        Color(*_MUTED, 0.8)
                        _el = Line(
                            ellipse=(dw2.x, dw2.y, dw2.width, dw2.height),
                            width=1.2)
                    def _mk_el(el):
                        def _s(w, *_):
                            el.ellipse = (w.x, w.y, w.width, w.height)
                        return _s
                    dw2.bind(pos=_mk_el(_el), size=_mk_el(_el))
                root.add_widget(dw2)

    # ── Free-time card ─────────────────────────────────────────────────────────
    # Frame '20':  25.43, 268.39  1210.56×100.29  r=29.66
    #   clock icon 927:131  31.08, 24.02  53.68×53.68
    #   free text  927:130  97.47, 31.08  356×39   Bold 32.49
    #   sun icon   927:135 884.26, 28.25  49.44×49.44
    #   mtg count  927:136 943.59, 35.32  236×37   Bold 31.08

    def _build_free_card(self, root: FloatLayout) -> None:
        CW, CH = 1210.56, 100.29
        CX, CY = 25.43, 268.39

        card = _Card(ct=_CARD_T, cb=_CARD_B, bdr=_BDR_CARD,
                     r=_ff(29.66), **_ph(CX, CY, CW, CH))

        # Clock icon — use Figma asset, fall back to emoji
        clock_src = _asset("icon_clock.png")
        if clock_src:
            card.add_widget(Image(
                source=clock_src, fit_mode="contain",
                size_hint=(53.68 / CW, 53.68 / CH),
                pos_hint={"x": 31.08 / CW, "y": (CH - 24.02 - 53.68) / CH}))
        else:
            card.add_widget(_lbl(
                "⏱", _FSB, _ff(38), _MUTED, ha="center", va="middle",
                size_hint=(53.68 / CW, 53.68 / CH),
                pos_hint={"x": 31.08 / CW, "y": (CH - 24.02 - 53.68) / CH}))

        # "You're free till …" text
        card.add_widget(_lbl(
            "You're free till 11:00 AM", _FB, _ff(32.49), _WHITE,
            va="middle",
            size_hint=(356 / CW, 39 / CH),
            pos_hint={"x": 97.47 / CW, "y": (CH - 31.08 - 39) / CH}))

        # Sun icon — use Figma asset
        sun_src = _asset("icon_sun.png")
        if sun_src:
            card.add_widget(Image(
                source=sun_src, fit_mode="contain",
                size_hint=(49.44 / CW, 49.44 / CH),
                pos_hint={"x": 884.26 / CW, "y": (CH - 28.25 - 49.44) / CH}))
        else:
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

    # ── Timeline ───────────────────────────────────────────────────────────────
    # Rectangle 31 separator:  203.41, 377.15  2.83×355.96  fill #9ABDFF
    # Group 58 large dot:       187.87, 412.46  33.9×33.9   #0090FF
    # Group 59 mid dot:         192.11, 529.71  25.43×25.43 #0050FF
    # Group 60 mid dot:         192.11, 642.71  25.43×25.43 #0050FF
    # Group 61  11:00 AM:        48.02, 405.40  71×60.9
    # Group 62   2:00 PM:        59.33, 509.93  59×60.9
    # Group 63   5:30 PM:        56.50, 622.94  60.84×60.9

    def _build_timeline(self, root: FloatLayout) -> None:
        sep = Widget(**_ph(203.41, 377.15, 2.83, 355.96))
        with sep.canvas.before:
            Color(154/255, 189/255, 255/255, 0.75)  # #9ABDFF
            _sr = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(
            pos=lambda w, v: setattr(_sr, "pos", v),
            size=lambda w, v: setattr(_sr, "size", v))
        root.add_widget(sep)

        for (sx, sy, dw, dh, r, g, b) in [
            (187.87, 412.46, 33.9,  33.9,  0.0, 0.565, 1.0),
            (192.11, 529.71, 25.43, 25.43, 0.0, 0.314, 1.0),
            (192.11, 642.71, 25.43, 25.43, 0.0, 0.314, 1.0),
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

        for (gx, gy, gw, time_s, ampm_s, ampm_dx, ampm_dy) in [
            (48.02,  405.40, 71.0,  "11:00", "AM", 35.31, 33.90),
            (59.33,  509.93, 59.0,  "2:00",  "PM", 24.02, 33.90),
            (56.50,  622.94, 60.84, "5:30",  "PM", 26.84, 33.90),
        ]:
            root.add_widget(_lbl(time_s, _FB, _ff(28.25), _WHITE,
                                 **_ph(gx, gy, gw, 34.0)))
            root.add_widget(_lbl(ampm_s, _FSB, _ff(22.6), _MUTED,
                                 **_ph(gx + ampm_dx, gy + ampm_dy, 35.0, 27.0)))

    # ── Meeting cards ──────────────────────────────────────────────────────────
    # Card '21' Product Sync  276.86, 377.15  954.89×104.53
    # Card '25' Client Call   281.10, 490.16  954.89×104.53
    # Card '22' Review        281.10, 603.16  954.89×104.53

    def _build_meeting_cards(self, root: FloatLayout) -> None:
        for (cx, cy, title, dur, show_join) in [
            (276.86, 377.15, "Product Sync", "30 min", True),
            (281.10, 490.16, "Client Call",  "45 min", False),
            (281.10, 603.16, "Review",       "30 min", False),
        ]:
            self._add_meeting_card(root, cx, cy, 954.89, 104.53,
                                   title, dur, show_join)

    def _add_meeting_card(self, root: FloatLayout,
                          cx: float, cy: float, cw: float, ch: float,
                          title: str, dur: str, show_join: bool) -> None:
        card = _Card(ct=_MTG_T, cb=_MTG_B, bdr=_BDR_MTG,
                     r=_ff(25.43), **_ph(cx, cy, cw, ch))

        # Icon circle  32.49, 16.95  70.63×70.63
        IW, IH, IX, IY = 70.63, 70.63, 32.49, 16.95
        mtg_src = _asset("icon_meeting.png")
        if mtg_src:
            card.add_widget(Image(
                source=mtg_src, fit_mode="contain",
                size_hint=(IW / cw, IH / ch),
                pos_hint={"x": IX / cw, "y": (ch - IY - IH) / ch}))
        else:
            ic = _Card(ct=_ICON_BG, cb=_ICON_BG, bdr=_BDR_ICON,
                       r=_ff(16.21),
                       size_hint=(IW / cw, IH / ch),
                       pos_hint={"x": IX / cw, "y": (ch - IY - IH) / ch})
            ic.add_widget(_lbl(
                title[0].upper(), _FSB, _ff(30), _BTDAY,
                ha="center", va="middle",
                size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
            card.add_widget(ic)

        # Title  129.95, 16.95  176×34
        card.add_widget(_lbl(
            title, _FB, _ff(28.25), _WHITE,
            va="middle",
            size_hint=(300 / cw, 34 / ch),
            pos_hint={"x": 129.95 / cw, "y": (ch - 16.95 - 34) / ch}))

        # Duration row: small clock icon + text.
        # Emoji / special chars don't render in the 42dot custom font, so use
        # icon_clock.png as a separate Image widget.
        clock_src = _asset("icon_clock.png")
        # Vertical centre of the duration text row (Figma top = 56.5, h = 31.08)
        dur_row_cy_kivy = (ch - 56.50 - 31.08) / ch + (31.08 / ch) / 2  # centre
        ICON_SZ = 20.0
        icon_y_kivy = dur_row_cy_kivy - (ICON_SZ / ch) / 2
        if clock_src:
            card.add_widget(Image(
                source=clock_src, fit_mode="contain",
                size_hint=(ICON_SZ / cw, ICON_SZ / ch),
                pos_hint={"x": 129.95 / cw, "y": icon_y_kivy}))
        dur_x = 155.0 if clock_src else 129.95
        card.add_widget(_lbl(
            dur, _FSB, _ff(22.6), _MUTED,
            va="middle",
            size_hint=(175 / cw, 31.08 / ch),
            pos_hint={"x": dur_x / cw, "y": (ch - 56.50 - 31.08) / ch}))

        # Join button  607.4, 24.01  144.08×56.5
        if show_join:
            JW, JH = 144.08, 56.5
            jb = _TapCard(
                ct=_JOIN_T, cb=_JOIN_B, bdr=_BDR_BTN,
                r=_ff(12.71),
                size_hint=(JW / cw, JH / ch),
                pos_hint={"x": 607.4 / cw, "y": (ch - 24.01 - JH) / ch})

            vid_src = _asset("icon_video.png")
            if vid_src:
                jb.add_widget(Image(
                    source=vid_src, fit_mode="contain",
                    size_hint=(33.9 / JW, 33.9 / JH),
                    pos_hint={"x": 21.19 / JW, "y": (JH - 11.3 - 33.9) / JH}))
            else:
                jb.add_widget(_lbl(
                    "▶", _FB, _ff(20), _WHITE,
                    ha="center", va="middle",
                    size_hint=(33.9 / JW, 33.9 / JH),
                    pos_hint={"x": 21.19 / JW, "y": (JH - 11.3 - 33.9) / JH}))

            jb.add_widget(_lbl(
                "Join", _FB, _ff(26.84), _WHITE,
                va="middle",
                size_hint=(53 / JW, 32 / JH),
                pos_hint={"x": 69.21 / JW, "y": (JH - 11.3 - 32) / JH}))
            card.add_widget(jb)

        # Details button — always at the right slot (778.32), regardless of
        # whether the Join button is present.  Figma shows all three Details
        # buttons right-aligned at the same horizontal position.
        DW, DH = 144.08, 56.5
        db = _TapCard(
            ct=(0, 0, 0, 0), cb=(0, 0, 0, 0),
            bdr=_BDR_BTN,
            r=_ff(12.71),
            size_hint=(DW / cw, DH / ch),
            pos_hint={"x": 778.32 / cw, "y": (ch - 24.01 - DH) / ch})

        db.add_widget(_lbl(
            "Details", _FB, _ff(21.19), _WHITE,
            va="middle",
            size_hint=(68 / DW, 25 / DH),
            pos_hint={"x": 24.02 / DW, "y": (DH - 15.54 - 25) / DH}))

        # Arrow icon — "›" is not in the 42dot font; use icon_arrow.png from
        # home assets (already downloaded) or fall back to ASCII ">".
        arr_src = _asset("icon_arrow.png")
        if not arr_src:
            _home_arr = ASSETS_DIR / "home" / "figma" / "icon_arrow.png"
            if _home_arr.is_file():
                arr_src = str(_home_arr)
        if arr_src:
            AW, AH = 19.78, 19.78
            arr_y_kivy = (DH / 2 - AH / 2) / DH
            db.add_widget(Image(
                source=arr_src, fit_mode="contain",
                size_hint=(AW / DW, AH / DH),
                pos_hint={"x": 110.18 / DW, "y": arr_y_kivy}))
        else:
            db.add_widget(_lbl(
                ">", _FB, _ff(22), _WHITE,
                ha="center", va="middle",
                size_hint=(22 / DW, 30 / DH),
                pos_hint={"x": 110.18 / DW, "y": (DH - 13 - 30) / DH}))

        card.add_widget(db)
        root.add_widget(card)

    # ── Add-event button ───────────────────────────────────────────────────────
    # Frame '27':  440.72, 716.16  378.57×60.74  r=16.95
    # gg:add icon   98.88,  9.89   42.38×42.38
    # "Add event"  146.91, 14.13  133×34  Bold 28.25  #006BF9

    def _build_add_button(self, root: FloatLayout) -> None:
        BW, BH = 378.57, 60.74
        btn = _TapCard(ct=_MTG_T, cb=_MTG_B, bdr=_BDR_MTG,
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

        for col_date, hl in zip(self._col_dates, self._highlights):
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

        for i, lbl in enumerate(self._date_lbls):
            lbl.text = str(self._col_dates[i].day)

        for col_date, hl in zip(self._col_dates, self._highlights):
            hl.set_mode("today" if col_date == today else "none")

        if self._heading_lbl:
            self._heading_lbl.text = "Today"
        if self._datestr_lbl:
            self._datestr_lbl.text = _fmt_date(today)

        Clock.schedule_once(lambda _dt: self._load_week(), 0)

    def _load_week(self) -> None:
        async def _fetch():
            try:
                today = display_now().date()
                week_mon = today - timedelta(days=today.weekday())
                end_d = week_mon + timedelta(days=6)
                await self.backend.get_calendar_week(
                    week_mon.isoformat(),
                    end_d.isoformat(),
                )
            except Exception as exc:
                logger.debug("CalendarScreen: get_calendar_week failed: %s", exc)
        run_async(_fetch())

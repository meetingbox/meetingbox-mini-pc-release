"""Morning Brief screen — pixel-perfect from Figma 927:220 (1260 × 800 px).

Layout mirrors the Figma node tree exactly:
  • Header / greeting (Group 65)
  • Weather card  (Frame 19 — full-width, 1214.8 × 185.04)
  • Today's Schedule card  (Frame 22 — 639.89 × 327.71, left)
  • Tasks Overview card    (Frame 22 — 553.72 × 327.71, right)
  • Recent Emails card     (Frame 23 — full-width, 1214.8 × 113)

All coordinates are Figma absolute px, converted with _ph() to Kivy fractions.
"""

from __future__ import annotations

import logging

from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from config import ASSETS_DIR, DISPLAY_HEIGHT, DISPLAY_WIDTH, display_now
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

# ── Design frame ──────────────────────────────────────────────────────────────
FW, FH = 1260.0, 800.0

# ── Asset paths ───────────────────────────────────────────────────────────────
_BRIEF   = ASSETS_DIR / "brief"   / "figma"
_CAL_DIR = ASSETS_DIR / "calendar" / "figma"


def _asset(name: str) -> str:
    p = _BRIEF / name
    return str(p) if p.is_file() else ""


def _cal_asset(name: str) -> str:
    p = _CAL_DIR / name
    return str(p) if p.is_file() else ""


# ── Colours ───────────────────────────────────────────────────────────────────
_BG      = (1/255,   8/255,  26/255, 1.0)    # #01081A  background
_WHITE   = (1.0, 1.0, 1.0, 1.0)
_MUTED   = (182/255, 186/255, 242/255, 1.0)  # #B6BAF2
_DIM     = (155/255, 162/255, 178/255, 1.0)  # #9BA2B2  "partly cloudy"
_BLUE    = (0.0,    107/255, 249/255, 1.0)   # #006BF9  links / times
_BLUE2   = (52/255, 129/255, 241/255, 1.0)   # #3481F1  greeting
_GREEN   = (25/255, 211/255, 133/255, 1.0)   # #19D385
_PURPLE  = (169/255, 113/255, 212/255, 1.0)  # #A971D4

# Card fill gradients
_CARD_T  = (2/255,  18/255,  60/255, 1.0)   # #02123C
_CARD_B  = (0.0,   10/255,  38/255, 1.0)    # #000A26
_SCH_T   = (1/255,  17/255,  55/255, 1.0)   # #011137
_SCH_B   = (0.0,   10/255,  38/255, 1.0)    # #000A26

# Border (fill_9NEWTX first colour: #3F4253)
_BDR     = (63/255,  66/255,  83/255, 1.0)

# Dot gradient (simplified to top colour; gradient not supported in Kivy Ellipse)
_DOT_C   = (70/255, 125/255, 254/255, 1.0)  # #467DFE

# Font names (registered in main.py)
_FSB = "42dot-SB"    # SemiBold
_FB  = "42dot-Sans"  # Bold
_FMD = "42dot-Med"   # Medium


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ph(fx: float, fy: float, fw: float, fh: float) -> dict:
    """Figma absolute px → Kivy size_hint + pos_hint (1260 × 800 root)."""
    return {
        "size_hint": (fw / FW, fh / FH),
        "pos_hint":  {"x": fx / FW, "y": (FH - fy - fh) / FH},
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
        def _b(c): return [min(255, max(0, int(v * 255))) for v in c]
        t.blit_buffer(bytes(_b(bot) + _b(top)), colorfmt="rgba", bufferfmt="ubyte")
        t.mag_filter = t.min_filter = "linear"
        t.wrap = "clamp_to_edge"
        _GC[k] = t
    return _GC[k]


def _lbl(text: str, font: str, size: int, color: tuple,
         ha: str = "left", va: str = "top", **kw) -> Label:
    lw = Label(text=text, font_name=font, font_size=size, color=color,
               halign=ha, valign=va, **kw)
    lw.bind(size=lw.setter("text_size"))
    return lw


def _mlbl(text: str, font: str, size: int, color: tuple,
          ha: str = "left", va: str = "top", **kw) -> Label:
    """Label with Kivy markup enabled (for mixed colours)."""
    lw = Label(text=text, font_name=font, font_size=size, color=color,
               markup=True, halign=ha, valign=va, **kw)
    lw.bind(size=lw.setter("text_size"))
    return lw


def _img(src: str, CW: float, CH: float,
         rel_x: float, rel_y: float, iw: float, ih: float) -> Image:
    return Image(source=src, fit_mode="contain",
                 size_hint=(iw / CW, ih / CH),
                 pos_hint={"x": rel_x / CW, "y": (CH - rel_y - ih) / CH})


# ── Gradient card ─────────────────────────────────────────────────────────────

class _Card(FloatLayout):
    def __init__(self, ct: tuple, cb: tuple, bdr: tuple, r: float = 12,
                 bdr_alpha: float = 0.9, **kw):
        super().__init__(**kw)
        self._r = r
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[r],
                texture=_grad(ct, cb))
        with self.canvas.after:
            Color(*bdr[:3], bdr_alpha)
            self._ln = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, r),
                width=1.0)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        r = self._r
        self._bg.pos  = self.pos
        self._bg.size = self.size
        self._bg.radius = [r]
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


class _ImgBtn(ButtonBehavior, Image):
    pass


# ── Small reusable builders ───────────────────────────────────────────────────

def _add_divider(parent: FloatLayout, CW: float, CH: float,
                 rel_x: float, rel_y: float,
                 rel_w: float, rel_h: float) -> None:
    """Horizontal/vertical separator line (dark fade-through blue)."""
    dv = Widget(size_hint=(rel_w / CW, rel_h / CH),
                pos_hint={"x": rel_x / CW,
                          "y": (CH - rel_y - rel_h) / CH})
    with dv.canvas.before:
        Color(2/255, 23/255, 77/255, 0.85)
        _r = Rectangle(pos=dv.pos, size=dv.size)
    def _mk(r):
        def _s(w, *_): r.pos = w.pos; r.size = w.size
        return _s
    dv.bind(pos=_mk(_r), size=_mk(_r))
    parent.add_widget(dv)


def _add_dot(parent: FloatLayout, CW: float, CH: float,
             rel_x: float, rel_y: float, d: float = 11.3) -> None:
    """Small blue circle dot."""
    dw = Widget(size_hint=(d / CW, d / CH),
                pos_hint={"x": rel_x / CW,
                          "y": (CH - rel_y - d) / CH})
    with dw.canvas:
        Color(*_DOT_C)
        _e = Ellipse(pos=dw.pos, size=dw.size)
    def _mk(e):
        def _s(w, *_): e.pos = w.pos; e.size = w.size
        return _s
    dw.bind(pos=_mk(_e), size=_mk(_e))
    parent.add_widget(dw)


# ── Screen ────────────────────────────────────────────────────────────────────

class MorningBriefScreen(BaseScreen):
    """Morning Brief page — full-screen Figma 927:220 render."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._build_ui()

    # ── Top-level build ────────────────────────────────────────────────────────

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
        self._build_weather_card(root)
        self._build_schedule_card(root)
        self._build_tasks_card(root)
        self._build_email_card(root)
        self.add_widget(root)

    # ── Header (Group 65) ──────────────────────────────────────────────────────
    # Figma: Group at (22.6, 21.19), 381 × 104.11
    #   "Morning Brief"          (0, 0)     238 × 45   SemiBold 38.14  #FFFFFF
    #   "Good morning, J.K"      (0, 43.79) 193 × 27   SemiBold 22.6   #3481F1
    #   "Here's your overview…"  (0, 79.11) 381 × 25   SemiBold 21.19  #B6BAF2
    # Back button added at (24.02, 21.19); header texts shifted to x=118.66.

    def _build_header(self, root: FloatLayout) -> None:
        back_src = _cal_asset("btn_back.png")
        if back_src:
            btn = _ImgBtn(source=back_src, fit_mode="contain",
                          **_ph(24.02, 21.19, 76.28, 76.28))
            btn.bind(on_release=lambda *_: self.go_back())
            root.add_widget(btn)

        root.add_widget(_lbl(
            "Morning Brief", _FSB, _ff(38.14), _WHITE,
            **_ph(118.66, 21.19, 320.0, 45.0)))

        root.add_widget(_lbl(
            "Good morning, J.K", _FSB, _ff(22.6), _BLUE2,
            **_ph(118.66, 65.0, 280.0, 27.0)))

        root.add_widget(_lbl(
            "Here's your overview for today, 20 May",
            _FSB, _ff(21.19), _MUTED,
            **_ph(118.66, 100.3, 500.0, 25.0)))

    # ── Weather card (Frame 19) ────────────────────────────────────────────────
    # Figma: (22.6, 132.78)  1214.8 × 185.04  r=22.6
    # Gradient fill: #02123C → #000A26
    # 4 vertical dividers at x = 387.04, 591.86, 796.68, 1001.5 (relative)
    # Columns: main temp | High/Low | Humidity | Wind | AQI

    def _build_weather_card(self, root: FloatLayout) -> None:
        CX, CY = 22.6, 132.78
        CW, CH = 1214.8, 185.04

        card = _Card(ct=_CARD_T, cb=_CARD_B, bdr=_BDR,
                     r=_ff(22.6), **_ph(CX, CY, CW, CH))

        # ── Header label
        card.add_widget(_lbl(
            "Weather Update", _FSB, _ff(21.19), _WHITE,
            size_hint=(159 / CW, 25 / CH),
            pos_hint={"x": 35.31 / CW, "y": (CH - 24.02 - 25) / CH}))

        # ── Sun / cloud image  (29.66, 72.04)  79.1 × 79.1
        cloud_src = _asset("weather_cloud.png")
        if cloud_src:
            card.add_widget(_img(cloud_src, CW, CH, 29.66, 72.04, 79.1, 79.1))

        # ── Main temperature  (128.54, 62.15)  58 × 42  Bold 35.31
        card.add_widget(_lbl(
            "24°", _FB, _ff(35.31), _WHITE,
            size_hint=(80 / CW, 42 / CH),
            pos_hint={"x": 128.54 / CW, "y": (CH - 62.15 - 42) / CH}))

        # ── "partly cloudy"  (128.54, 104.53)
        card.add_widget(_lbl(
            "partly cloudy", _FSB, _ff(21.19), _DIM,
            size_hint=(129 / CW, 25 / CH),
            pos_hint={"x": 128.54 / CW, "y": (CH - 104.53 - 25) / CH}))

        # ── Location icon + city  (128.54, 137.01)
        loc_src = _asset("icon_location.png")
        if loc_src:
            card.add_widget(_img(loc_src, CW, CH, 128.54, 137.01, 19.78, 19.78))
        card.add_widget(_lbl(
            "Hyderabad, India", _FSB, _ff(21.19), _MUTED,
            size_hint=(171 / CW, 25 / CH),
            pos_hint={"x": 151.14 / CW, "y": (CH - 134.19 - 25) / CH}))

        # ── Four vertical dividers
        for div_x in (387.04, 591.86, 796.68, 1001.5):
            dv = Widget(size_hint=(2.83 / CW, 115.83 / CH),
                        pos_hint={"x": div_x / CW,
                                  "y": (CH - 35.32 - 115.83) / CH})
            with dv.canvas.before:
                Color(2/255, 23/255, 77/255, 0.85)
                _r = Rectangle(pos=dv.pos, size=dv.size)
            def _mk(r):
                def _s(w, *_): r.pos = w.pos; r.size = w.size
                return _s
            dv.bind(pos=_mk(_r), size=_mk(_r))
            card.add_widget(dv)

        # ── High / Low column  (group at 413.88, 63.57)
        tmp_src = _asset("icon_temperature.png")
        if tmp_src:
            card.add_widget(_img(tmp_src, CW, CH, 413.88, 64.98, 31.08, 31.08))
        card.add_widget(_lbl(
            "28° / 18°", _FB, _ff(26.84), _WHITE,
            size_hint=(109 / CW, 32 / CH),
            pos_hint={"x": 450.61 / CW, "y": (CH - 63.57 - 32) / CH}))
        card.add_widget(_lbl(
            "High / Low", _FSB, _ff(16.95), _MUTED,
            size_hint=(83 / CW, 20 / CH),
            pos_hint={"x": 463.32 / CW, "y": (CH - 103.12 - 20) / CH}))

        # ── Humidity column  (group at 644.13, 63.57)
        hum_src = _asset("icon_humidity.png")
        if hum_src:
            card.add_widget(_img(hum_src, CW, CH, 644.13, 66.39, 28.25, 28.25))
        card.add_widget(_lbl(
            "62%", _FB, _ff(26.84), _WHITE,
            size_hint=(56 / CW, 32 / CH),
            pos_hint={"x": 678.03 / CW, "y": (CH - 63.57 - 32) / CH}))
        card.add_widget(_lbl(
            "Humidity", _FSB, _ff(16.95), _MUTED,
            size_hint=(71 / CW, 20 / CH),
            pos_hint={"x": 658.26 / CW, "y": (CH - 103.12 - 20) / CH}))

        # ── Wind column  (group at 827.76, 63.57)
        wind_src = _asset("icon_wind.png")
        if wind_src:
            card.add_widget(_img(wind_src, CW, CH, 827.76, 64.28, 35.31, 35.31))
        card.add_widget(_lbl(
            "12 km/h", _FB, _ff(26.84), _WHITE,
            size_hint=(100 / CW, 32 / CH),
            pos_hint={"x": 875.08 / CW, "y": (CH - 63.57 - 32) / CH}))
        card.add_widget(_lbl(
            "Wind", _FSB, _ff(16.95), _MUTED,
            size_hint=(41 / CW, 20 / CH),
            pos_hint={"x": 896.27 / CW, "y": (CH - 103.12 - 20) / CH}))

        # ── AQI column  (group at 1063.66, 66.39)
        # "42" rendered in #19D385 via Kivy markup
        card.add_widget(_mlbl(
            'AQl   [color=#19D385]42[/color]',
            _FB, _ff(26.84), _WHITE,
            size_hint=(110 / CW, 32 / CH),
            pos_hint={"x": 1063.66 / CW, "y": (CH - 66.39 - 32) / CH}))
        card.add_widget(_lbl(
            "Good", _FSB, _ff(16.95), _MUTED,
            size_hint=(42 / CW, 20 / CH),
            pos_hint={"x": 1091.91 / CW, "y": (CH - 105.94 - 20) / CH}))

        root.add_widget(card)

    # ── Today's Schedule card (Frame 22, left) ─────────────────────────────────
    # Figma: (29.66, 324.89)  639.89 × 327.71  r=16.95
    # Gradient fill: #011137 → #000A26
    # 3 horizontal dividers at card-relative y = 81.93, 162.44, 242.96

    def _build_schedule_card(self, root: FloatLayout) -> None:
        CX, CY = 29.66, 324.89
        CW, CH = 639.89, 327.71

        card = _Card(ct=_SCH_T, cb=_SCH_B, bdr=_BDR,
                     r=_ff(16.95), **_ph(CX, CY, CW, CH))

        # Calendar icon  (24.02, 25.43)  36.98 × 33.39
        cal_src = _asset("icon_calendar.png")
        if cal_src:
            card.add_widget(_img(cal_src, CW, CH, 24.02, 25.43, 36.98, 33.39))

        # "Today's Schedule"  (70.63, 29.66)
        card.add_widget(_lbl(
            "Today's Schedule", _FSB, _ff(21.19), _WHITE,
            size_hint=(172 / CW, 25 / CH),
            pos_hint={"x": 70.63 / CW, "y": (CH - 29.66 - 25) / CH}))

        # "View full calender"  (402.58, 29.66)  + arrow  (597.51, 22.6)
        card.add_widget(_lbl(
            "View full calender", _FSB, _ff(21.19), _BLUE,
            size_hint=(175 / CW, 25 / CH),
            pos_hint={"x": 402.58 / CW, "y": (CH - 29.66 - 25) / CH}))
        arr_src = _asset("icon_arrow_right.png")
        if arr_src:
            card.add_widget(_img(arr_src, CW, CH, 597.51, 22.6, 19.78, 39.55))

        # Horizontal dividers
        for div_y in (81.93, 162.44, 242.96):
            _add_divider(card, CW, CH, 24.02, div_y, 593.27, 2.83)

        # Schedule rows
        # Each row: time (left, blue) · dot (centre) · title · duration (right)
        for (time_s, title_s, dur_s, row_y, dot_y) in [
            ("10:00 AM", "Product Roadmap Sync",  "45 min", 111.59, 118.65),
            ("1:00 PM",  "Client Review Meeting", "60 min", 193.52, 200.58),
            ("4:00 PM",  "Design Discussion",     "30 min", 271.21, 278.27),
        ]:
            card.add_widget(_lbl(
                time_s, _FMD, _ff(21.19), _BLUE,
                size_hint=(125 / CW, 25 / CH),
                pos_hint={"x": 15.0 / CW, "y": (CH - row_y - 25) / CH}))
            _add_dot(card, CW, CH, 158.2, dot_y)
            card.add_widget(_lbl(
                title_s, _FSB, _ff(21.19), _WHITE,
                size_hint=(350 / CW, 25 / CH),
                pos_hint={"x": 182.22 / CW, "y": (CH - row_y - 25) / CH}))
            card.add_widget(_lbl(
                dur_s, _FSB, _ff(21.19), _MUTED,
                size_hint=(68 / CW, 25 / CH),
                pos_hint={"x": 548.07 / CW, "y": (CH - row_y - 25) / CH}))

        root.add_widget(card)

    # ── Tasks Overview card (Frame 22, right) ──────────────────────────────────
    # Figma: (676.62, 324.89)  553.72 × 327.71  r=16.95
    # Same gradient as schedule card.
    # 3 task rows — each with icon card, count badge, label, sub-label.

    def _build_tasks_card(self, root: FloatLayout) -> None:
        CX, CY = 676.62, 324.89
        CW, CH = 553.72, 327.71

        card = _Card(ct=_SCH_T, cb=_SCH_B, bdr=_BDR,
                     r=_ff(16.95), **_ph(CX, CY, CW, CH))

        # Tick / tasks icon  (21.19, 21.19)  42.38 × 42.38
        tick_src = _asset("icon_tick.png")
        if tick_src:
            card.add_widget(_img(tick_src, CW, CH, 21.19, 21.19, 42.38, 42.38))

        # "Tasks Overview"  (70.63, 29.66)
        card.add_widget(_lbl(
            "Tasks Overview", _FSB, _ff(21.19), _WHITE,
            size_hint=(152 / CW, 25 / CH),
            pos_hint={"x": 70.63 / CW, "y": (CH - 29.66 - 25) / CH}))

        # "View full tasks"  (360.2, 29.66) + arrow  (512.76, 22.6)
        card.add_widget(_lbl(
            "View full tasks", _FSB, _ff(21.19), _BLUE,
            size_hint=(141 / CW, 25 / CH),
            pos_hint={"x": 360.2 / CW, "y": (CH - 29.66 - 25) / CH}))
        arr_src = _asset("icon_arrow_right.png")
        if arr_src:
            card.add_widget(_img(arr_src, CW, CH, 512.76, 22.6, 19.78, 39.55))

        # Horizontal dividers (width capped to card interior)
        for div_y in (81.93, 162.44, 242.96):
            _add_divider(card, CW, CH, 24.02, div_y, 505.68, 2.83)

        # Task rows
        #   icon_file, count, count_colour, label, sub-label,
        #   icon_top, count_top, group_top
        for (icon_file, num_s, num_col, label_s, sub_s,
             icon_y, num_y, grp_y) in [
            ("icon_task_1.png", "2", _BLUE,   "Due Today", "2 high priority",
             93.23,  103.12, 98.88),
            ("icon_task_2.png", "1", _PURPLE, "Due Today", "Next: Tomorrow",
             173.74, 183.63, 179.39),
            ("icon_task_3.png", "2", _GREEN,  "Due Today", "In Inbox",
             252.85, 262.73, 259.91),
        ]:
            task_src = _asset(icon_file)
            if task_src:
                card.add_widget(_img(
                    task_src, CW, CH, 31.08, icon_y, 70.63, 62.15))
            card.add_widget(_lbl(
                num_s, _FB, _ff(35.31), num_col,
                ha="center", va="middle",
                size_hint=(26 / CW, 42 / CH),
                pos_hint={"x": 131.37 / CW, "y": (CH - num_y - 42) / CH}))
            card.add_widget(_lbl(
                label_s, _FSB, _ff(21.19), _WHITE,
                size_hint=(140 / CW, 25 / CH),
                pos_hint={"x": 217.53 / CW, "y": (CH - grp_y - 25) / CH}))
            card.add_widget(_lbl(
                sub_s, _FMD, _ff(16.95), _MUTED,
                size_hint=(180 / CW, 20 / CH),
                pos_hint={"x": 217.53 / CW,
                          "y": (CH - grp_y - 31.07 - 20) / CH}))

        root.add_widget(card)

    # ── Recent Emails card (Frame 23) ──────────────────────────────────────────
    # Figma: (22.6, 659.66)  1214.8 × 113  r=24.01
    # Single email preview row.

    def _build_email_card(self, root: FloatLayout) -> None:
        CX, CY = 22.6, 659.66
        CW, CH = 1214.8, 113.0

        card = _Card(ct=_CARD_T, cb=_CARD_B, bdr=_BDR,
                     r=_ff(24.01), **_ph(CX, CY, CW, CH))

        # Email icon  (46.62, 14.13)  33.9 × 33.9
        em_src = _asset("icon_email.png")
        if em_src:
            card.add_widget(_img(em_src, CW, CH, 46.62, 14.13, 33.9, 33.9))

        # Section header label  (87.58, 18.37)
        card.add_widget(_lbl(
            "Recent Emails", _FSB, _ff(21.19), _WHITE,
            size_hint=(172 / CW, 25 / CH),
            pos_hint={"x": 87.58 / CW, "y": (CH - 18.37 - 25) / CH}))

        # "Go to emails" link  (1001.5, 15.54) + arrow  (1148.41, 8.48)
        card.add_widget(_lbl(
            "Go to emails", _FSB, _ff(21.19), _BLUE,
            size_hint=(121 / CW, 25 / CH),
            pos_hint={"x": 1001.5 / CW, "y": (CH - 15.54 - 25) / CH}))
        arr_src = _asset("icon_arrow_right.png")
        if arr_src:
            card.add_widget(_img(arr_src, CW, CH, 1148.41, 8.48, 19.78, 39.55))

        # Horizontal divider  (29.66, 55.09)  1155.47 × 2.83
        _add_divider(card, CW, CH, 29.66, 55.09, 1155.47, 2.83)

        # Sender dot  at (59.33, 80.51)  11.3 × 11.3
        _add_dot(card, CW, CH, 59.33, 80.51)

        # Sender name  (93.23, 73.45)
        card.add_widget(_lbl(
            "Neha Sharma", _FSB, _ff(21.19), _WHITE,
            size_hint=(131 / CW, 25 / CH),
            pos_hint={"x": 93.23 / CW, "y": (CH - 73.45 - 25) / CH}))

        # Email subject  (372.91, 76.28)  291 × 22
        card.add_widget(_lbl(
            "Client follow-up from Product Sync",
            _FMD, _ff(18.36), _MUTED,
            size_hint=(291 / CW, 22 / CH),
            pos_hint={"x": 372.91 / CW, "y": (CH - 76.28 - 22) / CH}))

        # Timestamp  (1084.84, 76.28)  81 × 22
        card.add_widget(_lbl(
            "10:45 AM", _FMD, _ff(18.36), _MUTED,
            size_hint=(81 / CW, 22 / CH),
            pos_hint={"x": 1084.84 / CW, "y": (CH - 76.28 - 22) / CH}))

        root.add_widget(card)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_enter(self) -> None:
        pass

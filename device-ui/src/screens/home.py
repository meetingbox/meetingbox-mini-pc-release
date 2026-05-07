"""Home screen — Figma frame 390:187 (yJqcY4KovVjJ11vjysW533).

Pixel-perfect implementation using 42dot Sans font and FloatLayout with
pos_hint / size_hint derived from Figma absolute coordinates.
All backend data (meetings, weather, email counts) is fetched live.
"""

from __future__ import annotations

import logging
from datetime import datetime

from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from async_helper import run_async
from components.modal_dialog import ModalDialog
from components.text_input_dialog import TextInputDialog
from config import (
    ASSETS_DIR,
    DASHBOARD_URL,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    FONTS_DIR,
    display_now,
    to_display_local,
)
from local_network import get_primary_ipv4
from network_util import linux_ethernet_ready
from screens.base_screen import BaseScreen
from weather_client import get_weather_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Figma frame baseline
# ---------------------------------------------------------------------------
_FW: float = 892.0
_FH: float = 573.0
_SCALE: float = min(DISPLAY_WIDTH / _FW, DISPLAY_HEIGHT / _FH)

_FIGMA_DIR = ASSETS_DIR / "home" / "figma"
_IDLE_DIR  = ASSETS_DIR / "idle"


# ---------------------------------------------------------------------------
# Font registration
# ---------------------------------------------------------------------------
_FONT    = "42dotSans"
_FONT_SB = "42dotSansSB"
_FONT_MD = "42dotSansMD"

try:
    LabelBase.register(
        "42dotSans",
        fn_regular=str(FONTS_DIR / "42dotSans-Regular.ttf"),
        fn_bold=str(FONTS_DIR / "42dotSans-Bold.ttf"),
    )
    LabelBase.register("42dotSansSB", fn_regular=str(FONTS_DIR / "42dotSans-SemiBold.ttf"))
    LabelBase.register("42dotSansMD", fn_regular=str(FONTS_DIR / "42dotSans-Medium.ttf"))
except Exception as _fe:  # noqa: BLE001
    logger.warning("42dot Sans not found (%s); using system font", _fe)
    _FONT = _FONT_SB = _FONT_MD = "Roboto"


# ---------------------------------------------------------------------------
# Figma colors
# ---------------------------------------------------------------------------
_C_BG        = (0.004, 0.031, 0.102, 1.0)   # #01081A
_C_CARD_BG   = (0.004, 0.047, 0.145, 1.0)   # #010C25
_C_CARD_MID  = (0.004, 0.067, 0.216, 0.96)  # #011137 top gradient
_C_CARD_BOT  = (0.000, 0.039, 0.149, 0.98)  # #000A26
_C_CARD_BORDER = (0.247, 0.259, 0.325, 1.0) # #3F4253
_C_WHITE     = (1.000, 1.000, 1.000, 1.0)
_C_MUTED     = (0.714, 0.729, 0.949, 1.0)   # #B6BAF2
_C_BLUE      = (0.000, 0.420, 0.976, 1.0)   # #006BF9
_C_BLUE2     = (0.204, 0.506, 0.945, 1.0)   # #3481F1
_C_BLUE3     = (0.000, 0.435, 1.000, 1.0)   # #006FFF
_C_GRAY      = (0.643, 0.643, 0.675, 1.0)   # #A4A4AC
_C_REC_TOP   = (0.000, 0.220, 0.714, 1.0)   # #0038B6
_C_REC_BOT   = (0.000, 0.137, 0.463, 1.0)   # #002376


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fs(px: float) -> int:
    """Scale Figma font-size to display pixels."""
    return max(6, round(px * _SCALE))


def _ph_sh(fx: float, fy: float, fw: float, fh: float) -> tuple[dict, dict]:
    """Figma (x, y, w, h) → Kivy (pos_hint, size_hint). Kivy y is bottom-up."""
    return (
        {"x": fx / _FW, "y": 1.0 - (fy + fh) / _FH},
        {"x": fw / _FW, "y": fh / _FH},
    )


def _figma_png(name: str) -> str:
    p = _FIGMA_DIR / name
    return str(p) if p.is_file() else ""


def _lbl(text: str, fn: str, fs: float, color: tuple, bold: bool = False,
         halign: str = "left", **kw) -> Label:
    l = Label(
        text=text, font_name=fn, font_size=_fs(fs), bold=bold, color=color,
        halign=halign, valign="middle", **kw,
    )
    l.bind(size=l.setter("text_size"))
    return l


def _greeting(name: str | None) -> str:
    h = display_now().hour
    head = "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"
    nm = (name or "").strip()
    if nm:
        parts = nm.split()
        initials = ".".join(p[0].upper() for p in parts[:2])
        return f"{head}, {initials}"
    return head


def _format_next(nxt: dict | None) -> tuple[str, str]:
    if not nxt:
        return ("--:--", "No meetings today")
    title = (nxt.get("title") or "Calendar event").strip()
    start = (nxt.get("start") or "").strip()
    if not start:
        return ("Time not set", title)
    try:
        if "T" in start:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            ts = to_display_local(dt).strftime("%I:%M %p").lstrip("0")
        else:
            d = datetime.strptime(start[:10], "%Y-%m-%d")
            ts = d.strftime("%b %d · all day")
        return (ts, title)
    except (TypeError, ValueError):
        return (start, title)


# ---------------------------------------------------------------------------
# Avatar circle widget (photo or initials)
# ---------------------------------------------------------------------------

# Color palette for initials avatars, indexed by first char code
_AVATAR_COLORS = [
    (0.18, 0.42, 0.93, 1),  # blue
    (0.58, 0.18, 0.90, 1),  # purple
    (0.13, 0.67, 0.45, 1),  # teal
    (0.93, 0.42, 0.18, 1),  # orange
    (0.18, 0.58, 0.93, 1),  # sky
    (0.78, 0.18, 0.43, 1),  # rose
]


def _initials(name: str) -> str:
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _avatar_color(name: str) -> tuple:
    if not name:
        return _AVATAR_COLORS[0]
    return _AVATAR_COLORS[ord(name[0].upper()) % len(_AVATAR_COLORS)]


class _AvatarCircle(FloatLayout):
    """Circular avatar: photo if available, else colored initials circle."""

    def __init__(self, name: str = "", photo_path: str = "",
                 border_gradient: bool = False, **kw):
        super().__init__(**kw)
        self._name = name
        self._photo_path = photo_path
        self._has_border = border_gradient
        with self.canvas.before:
            if border_gradient:
                Color(0.247, 0.259, 0.325, 1)
                self._border_ring = Ellipse(pos=self.pos, size=self.size)
            else:
                self._border_ring = None
            if photo_path:
                Color(0.004, 0.039, 0.102, 1)
            else:
                r, g, b, a = _avatar_color(name)
                Color(r, g, b, a)
            self._circle = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=self._sync, size=self._sync)

        if photo_path:
            self.add_widget(Image(
                source=photo_path,
                size_hint=(1, 1),
                fit_mode="cover",
                allow_stretch=True,
                keep_ratio=False,
            ))
        else:
            self._initials_label = Label(
                text=_initials(name),
                font_name=_FONT_SB,
                font_size=max(8, _fs(14)),
                color=_C_WHITE,
                halign="center",
                valign="middle",
                size_hint=(1, 1),
            )
            self.add_widget(self._initials_label)

    def set_name(self, name: str) -> None:
        """Update initials without rebuilding the widget."""
        self._name = name
        lbl = getattr(self, "_initials_label", None)
        if lbl is not None:
            lbl.text = _initials(name)

    def _sync(self, *_):
        pad = 0
        if self._border_ring is not None:
            self._border_ring.pos  = self.pos
            self._border_ring.size = self.size
            pad = max(2, round(min(self.width, self.height) * 0.05))
        self._circle.pos  = (self.x + pad, self.y + pad)
        self._circle.size = (max(1, self.width - pad*2), max(1, self.height - pad*2))


# ---------------------------------------------------------------------------
# Rounded card background
# ---------------------------------------------------------------------------

class _CardBg(FloatLayout):
    """A FloatLayout with a rounded dark-navy background and gradient border."""

    def __init__(self, radius: float = 12, fill=None, **kw):
        super().__init__(**kw)
        self._radius = radius
        with self.canvas.before:
            # Subtle shadow
            Color(0, 0, 0, 0.25)
            self._shadow = RoundedRectangle(
                pos=(self.x + 1, self.y - 3), size=self.size, radius=[radius]
            )
            # Main fill (bottom gradient tone)
            Color(*(fill or _C_CARD_BOT))
            self._bg_bot = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            # Upper tone for gradient feel
            Color(*_C_CARD_MID)
            self._bg_top = RoundedRectangle(
                pos=(self.x, self.y + self.height * 0.48),
                size=(self.width, self.height * 0.52),
                radius=[radius, radius, 0, 0],
            )
            # Border
            Color(*_C_CARD_BORDER)
            self._stroke = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                width=1,
            )
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        r = self._radius
        self._shadow.pos  = (self.x + 1, self.y - 3)
        self._shadow.size = self.size
        self._bg_bot.pos  = self.pos
        self._bg_bot.size = self.size
        self._bg_top.pos  = (self.x, self.y + self.height * 0.48)
        self._bg_top.size = (self.width, self.height * 0.52)
        self._stroke.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


class _RecordingCard(ButtonBehavior, FloatLayout):
    """Blue gradient Start Recording card."""

    def __init__(self, radius: float = 14, **kw):
        super().__init__(**kw)
        self._radius = radius
        with self.canvas.before:
            Color(0, 0.502, 1, 0.34)
            self._glow = Ellipse(pos=self.pos, size=self.size)
            Color(*_C_REC_BOT)
            self._bg_b = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            Color(*_C_REC_TOP)
            self._bg_t = RoundedRectangle(
                pos=(self.x, self.y + self.height * 0.5),
                size=(self.width, self.height * 0.5),
                radius=[radius, radius, 0, 0],
            )
            Color(0.012, 0.306, 0.886, 1)
            self._border = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, radius), width=1.5,
            )
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        r = self._radius
        self._glow.pos  = (self.x - 2, self.y - 4)
        self._glow.size = (self.width + 4, self.height + 8)
        self._bg_b.pos  = self.pos
        self._bg_b.size = self.size
        self._bg_t.pos  = (self.x, self.y + self.height * 0.5)
        self._bg_t.size = (self.width, self.height * 0.5)
        self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


# ---------------------------------------------------------------------------
# HomeScreen
# ---------------------------------------------------------------------------

class HomeScreen(BaseScreen):
    """Figma 390:187 — main AI home dashboard."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._clock_event       = None
        self._voice_state_event = None
        self._latest_meeting_id = None
        self._health_label_offline = False
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    @property
    def _user_name(self) -> str:
        try:
            return getattr(self.app, "current_display_name", None) or "Vivek Reddy"
        except Exception:  # noqa: BLE001
            return "Vivek Reddy"

    def _build_ui(self) -> None:
        root = FloatLayout(size_hint=(1, 1))

        # ── Background #01081A ────────────────────────────────────────
        with root.canvas.before:
            Color(*_C_BG)
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, _: setattr(self._bg_rect, "pos", w.pos),
            size=lambda w, _: setattr(self._bg_rect, "size", w.size),
        )

        # ── Top bar ──────────────────────────────────────────────────
        # User avatar  (17, 15)  54×54
        user_name   = self._user_name
        try:
            avatar_path = getattr(self.app, "user_avatar_path", "") or ""
        except Exception:  # noqa: BLE001
            avatar_path = ""
        ph, sh = _ph_sh(17, 15, 54, 54)
        self._user_avatar = _AvatarCircle(
            name=user_name, photo_path=avatar_path,
            size_hint=sh, pos_hint=ph,
        )
        root.add_widget(self._user_avatar)

        # "Good morning, J.K"  (87, 24)  256×36
        ph, sh = _ph_sh(87, 24, 350, 36)
        self.greeting_label = _lbl(
            _greeting(user_name), _FONT_SB, 30, _C_WHITE,
            size_hint=sh, pos_hint=ph,
        )
        root.add_widget(self.greeting_label)

        # Listening pill  (570, 15)  214×54  radius 54
        ph, sh = _ph_sh(570, 15, 214, 54)
        self._listening_pill = _CardBg(
            radius=27, fill=_C_CARD_BOT,
            size_hint=sh, pos_hint=ph,
        )
        self._listening_pill.bind(on_touch_up=self._on_listening_pill_touch)
        # Green pulsing dot  (0, 9)  14×14
        self._voice_dot = FloatLayout(
            size_hint=(14/214, 14/54),
            pos_hint={"x": 0/214, "y": 1 - (9+14)/54},
        )
        with self._voice_dot.canvas.before:
            Color(0.275, 0.490, 0.996, 1)
            self._vdot_circle = Ellipse(pos=self._voice_dot.pos, size=self._voice_dot.size)
        self._voice_dot.bind(
            pos=lambda w, _: setattr(self._vdot_circle, "pos", w.pos),
            size=lambda w, _: setattr(self._vdot_circle, "size", w.size),
        )
        self._listening_pill.add_widget(self._voice_dot)
        # "Listening" text  (31, 4)  84×24
        self.voice_state_label = Label(
            text="Listening",
            font_name=_FONT_SB, font_size=_fs(20),
            color=_C_WHITE, halign="left", valign="middle",
            size_hint=(84/214, 24/54),
            pos_hint={"x": 31/214, "y": 1 - (4+24)/54},
        )
        self.voice_state_label.bind(size=self.voice_state_label.setter("text_size"))
        self._listening_pill.add_widget(self.voice_state_label)
        # Soundwave icon  (133, 0)  32×32
        sw = _figma_png("icon_soundwave.png")
        if sw:
            self._listening_pill.add_widget(Image(
                source=sw, size_hint=(32/214, 32/54),
                pos_hint={"x": 133/214, "y": 1-(0+32)/54},
                fit_mode="contain",
            ))
        root.add_widget(self._listening_pill)

        # Settings icon  (821, 15)  54×54
        ph, sh = _ph_sh(821, 15, 54, 54)
        sg = _figma_png("icon_settings.png")
        if sg:
            from kivy.uix.button import Button
            settings_btn = Button(
                background_normal=sg, background_down=sg, border=[0, 0, 0, 0],
                size_hint=sh, pos_hint=ph,
            )
        else:
            settings_btn = Label(
                text="⚙", font_size=_fs(28), color=_C_MUTED,
                halign="center", valign="middle",
                size_hint=sh, pos_hint=ph,
            )
        settings_btn.bind(on_release=lambda *_: self.goto("settings", transition="slide_left"))
        root.add_widget(settings_btn)

        # ── Mini widget card (390:188)  (17, 81)  410×263 ────────────
        self._build_mini_widget(root)

        # ── Product Sync / Last Meeting card (412:967)  (433, 81)  218×263 ─
        self._build_last_meeting_card(root)

        # ── Morning Brief card (412:893)  (657, 81)  218×263 ─────────
        self._build_morning_brief_card(root)

        # ── Middle row cards ─────────────────────────────────────────
        self._build_schedule_card(root)   # (17, 359) 361×102
        self._build_email_card(root)      # (384, 359) 237×102
        self._build_tasks_card(root)      # (627, 359) 248×102

        # ── Bottom voice bar (412:1040)  (27, 476)  838×71 ───────────
        self._build_voice_bar(root)

        self.add_widget(root)

    # ------------------------------------------------------------------
    # Mini widget card (390:188)
    # ------------------------------------------------------------------
    def _build_mini_widget(self, root: FloatLayout) -> None:
        """Top-left card with background photo + clock/weather/recording."""
        # Card background (nested FloatLayout)
        ph, sh = _ph_sh(17, 81, 410, 263)
        card = _CardBg(radius=14, fill=_C_CARD_BG, size_hint=sh, pos_hint=ph)

        # Background photo fills card
        bg_photo = str(ASSETS_DIR / "home" / "figma" / "hero_background.png")
        card.add_widget(Image(
            source=bg_photo, size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            fit_mode="cover", allow_stretch=True, keep_ratio=False,
        ))

        # ── Time group (21, 24) within card ──────────────────────────
        # "11:01"  (0, 0)  109×55  46px Bold
        self._mini_clock = Label(
            text="--:--", font_name=_FONT, font_size=_fs(46), bold=True,
            color=_C_WHITE, halign="left", valign="middle",
            size_hint=(109/410, 55/263),
            pos_hint={"x": 21/410, "y": 1 - (24+55)/263},
        )
        self._mini_clock.bind(size=self._mini_clock.setter("text_size"))
        card.add_widget(self._mini_clock)

        # "AM"  (122+21, 28.5+24)  25×19  16px #B6BAF2
        self._mini_ampm = Label(
            text="AM", font_name=_FONT_SB, font_size=_fs(16),
            color=_C_MUTED, halign="left", valign="middle",
            size_hint=(30/410, 20/263),
            pos_hint={"x": (21+122)/410, "y": 1 - (24+28.5+20)/263},
        )
        self._mini_ampm.bind(size=self._mini_ampm.setter("text_size"))
        card.add_widget(self._mini_ampm)

        # "Tuesday, May 21"  (21, 24+54.7)  106×16  14px SemiBold
        self._mini_date = Label(
            text="", font_name=_FONT_SB, font_size=_fs(14),
            color=_C_WHITE, halign="left", valign="middle",
            size_hint=(150/410, 16/263),
            pos_hint={"x": 21/410, "y": 1 - (24+54.7+16)/263},
        )
        self._mini_date.bind(size=self._mini_date.setter("text_size"))
        card.add_widget(self._mini_date)

        # ── Weather group (311+17, 81+31) within card: (311, 31) ─────
        # Sun icon  (0, 0)  29×29
        sun_src = str(_IDLE_DIR / "icon_sun.png")
        card.add_widget(Image(
            source=sun_src, size_hint=(29/410, 29/263),
            pos_hint={"x": 311/410, "y": 1 - (31+29)/263},
            fit_mode="contain",
        ))
        # "28°C"  (37.7, 5) within group  38×19  16px Bold
        self._mini_temp = Label(
            text="--°C", font_name=_FONT, font_size=_fs(16), bold=True,
            color=_C_WHITE, halign="left", valign="middle",
            size_hint=(50/410, 19/263),
            pos_hint={"x": (311+37.7)/410, "y": 1 - (31+5+19)/263},
        )
        self._mini_temp.bind(size=self._mini_temp.setter("text_size"))
        card.add_widget(self._mini_temp)
        # "Sunny"  (37.7, 27) within group  40×16  14px Medium
        self._mini_cond = Label(
            text="--", font_name=_FONT_MD, font_size=_fs(14),
            color=_C_MUTED, halign="left", valign="middle",
            size_hint=(60/410, 16/263),
            pos_hint={"x": (311+37.7)/410, "y": 1 - (31+27+16)/263},
        )
        self._mini_cond.bind(size=self._mini_cond.setter("text_size"))
        card.add_widget(self._mini_cond)

        # ── Schedule group (21, 153) within card  130×90 ─────────────
        # "Next up"  (0, 0)  46×15  12.9px SemiBold  #3481F1
        card.add_widget(_lbl(
            "Next up", _FONT_SB, 13, _C_BLUE2,
            size_hint=(80/410, 15/263),
            pos_hint={"x": 21/410, "y": 1 - (153+15)/263},
        ))
        # Calendar icon  (0, 27.6)  15.6×15.6
        cal_src = _figma_png("icon_calendar.png") or str(_IDLE_DIR / "icon_calendar.png")
        card.add_widget(Image(
            source=cal_src, size_hint=(16/410, 16/263),
            pos_hint={"x": 21/410, "y": 1 - (153+27.6+16)/263},
            fit_mode="contain",
        ))
        # "11:00 AM"  (24.4, 28.5)  55×15  12.9px SemiBold  #3481F1
        self._mini_next_time = _lbl(
            "--:-- --", _FONT_SB, 13, _C_BLUE2,
            size_hint=(80/410, 15/263),
            pos_hint={"x": (21+24.4)/410, "y": 1 - (153+28.5+15)/263},
        )
        card.add_widget(self._mini_next_time)
        # "Now : Product Sync"  (0, 51.94)  130×17  14.2px Bold  white
        self._mini_next_title = Label(
            text="--", font_name=_FONT, font_size=_fs(14), bold=True,
            color=_C_WHITE, halign="left", valign="middle",
            shorten=True, shorten_from="right",
            size_hint=(160/410, 17/263),
            pos_hint={"x": 21/410, "y": 1 - (153+51.94+17)/263},
        )
        self._mini_next_title.bind(size=self._mini_next_title.setter("text_size"))
        card.add_widget(self._mini_next_title)
        # "+2 more"  (0, 75.4)  49×15  12.9px Bold  #3481F1
        self._mini_more = _lbl(
            "", _FONT_SB, 13, _C_BLUE2, bold=True,
            size_hint=(80/410, 15/263),
            pos_hint={"x": 21/410, "y": 1 - (153+75.4+15)/263},
        )
        card.add_widget(self._mini_more)

        # ── Start Recording mini card (196, 167) 190×76.6  radius 13.8 ─
        rec_ph = {"x": 196/410, "y": 1 - (167+76.6)/263}
        rec_sh = {"x": 190/410, "y": 76.6/263}
        rec_card = _RecordingCard(radius=14, size_hint=rec_sh, pos_hint=rec_ph)
        rec_card.bind(on_release=self._on_start_recording)
        # Mic orb  (12.4, 14.7)  46.4×46.4
        mic_src = str(_IDLE_DIR / "mic_orb.png")
        rec_card.add_widget(Image(
            source=mic_src, size_hint=(46.4/190, 46.4/76.6),
            pos_hint={"x": 12.4/190, "y": 1 - (14.7+46.4)/76.6},
            fit_mode="contain",
        ))
        # "Start Recording"  (75.7, 22.5)  101×16  14px Bold
        rec_card.add_widget(Label(
            text="Start Recording", font_name=_FONT, font_size=_fs(14), bold=True,
            color=_C_WHITE, halign="left", valign="middle",
            size_hint=(101/190, 16/76.6),
            pos_hint={"x": 75.7/190, "y": 1 - (22.5+16)/76.6},
            text_size=(1, None),
        ))
        # 'Tap or say "start recording"'  (67.9, 43.1)
        rec_card.add_widget(Label(
            text='Tap or say "start recording"', font_name=_FONT_SB, font_size=_fs(9),
            color=_C_WHITE, halign="left", valign="middle",
            size_hint=(117/190, 11/76.6),
            pos_hint={"x": 67.9/190, "y": 1 - (43.1+11)/76.6},
            text_size=(1, None),
        ))
        card.add_widget(rec_card)

        root.add_widget(card)

    # ------------------------------------------------------------------
    # Last Meeting card (412:967)  — "Product Sync" style
    # ------------------------------------------------------------------
    def _build_last_meeting_card(self, root: FloatLayout) -> None:
        ph, sh = _ph_sh(433, 81, 218, 263)
        card = _CardBg(radius=12, size_hint=sh, pos_hint=ph)

        # "Last Meeting Summary" + icon  (15, 36)
        fd = _figma_png("icon_file_document.png")
        if fd:
            card.add_widget(Image(
                source=fd, size_hint=(28/218, 28/263),
                pos_hint={"x": 15/218, "y": 1 - (36+28)/263},
                fit_mode="contain",
            ))
        self.last_actions_label = _lbl(
            "Last Meeting Summary", _FONT_SB, 15, _C_GRAY,
            size_hint=(158/218, 18/263),
            pos_hint={"x": (15+29)/218, "y": 1 - (36+5+18)/263},
        )
        card.add_widget(self.last_actions_label)

        # Meeting title  (20, 74)
        self.last_title_label = Label(
            text="Loading...", font_name=_FONT_SB, font_size=_fs(23),
            color=_C_WHITE, halign="left", valign="middle",
            shorten=True, shorten_from="right",
            size_hint=(178/218, 27/263),
            pos_hint={"x": 20/218, "y": 1 - (74+27)/263},
        )
        self.last_title_label.bind(size=self.last_title_label.setter("text_size"))
        card.add_widget(self.last_title_label)

        # "Today, 10:00 AM"  (20, 109)
        self._meeting_time_label = _lbl(
            "—", _FONT_SB, 15, _C_MUTED,
            size_hint=(140/218, 18/263),
            pos_hint={"x": 20/218, "y": 1 - (109+18)/263},
        )
        card.add_widget(self._meeting_time_label)

        # "30 min"  (20, 129)
        self._meeting_dur_label = _lbl(
            "—", _FONT_SB, 15, _C_MUTED,
            size_hint=(80/218, 18/263),
            pos_hint={"x": 20/218, "y": 1 - (129+18)/263},
        )
        card.add_widget(self._meeting_dur_label)

        # "2 action items"  (20, 169)
        self.last_meta_label = _lbl(
            "—", _FONT_SB, 15, _C_BLUE3,
            size_hint=(140/218, 18/263),
            pos_hint={"x": 20/218, "y": 1 - (169+18)/263},
        )
        card.add_widget(self.last_meta_label)

        # Two attendee avatar circles  at (20, 194) and (60, 194)
        self._attendee_avatars: list[_AvatarCircle] = []
        for i, ax in enumerate([20, 60]):
            av = _AvatarCircle(
                name="", photo_path="",
                size_hint=(32.7/218, 32.6/263),
                pos_hint={"x": ax/218, "y": 1 - (194+32.6)/263},
            )
            self._attendee_avatars.append(av)
            card.add_widget(av)

        # "+2" counter bubble  (100.7, 194)
        self._plus2_bubble = Label(
            text="+2", font_name=_FONT, font_size=_fs(15),
            color=_C_WHITE, halign="center", valign="middle",
            size_hint=(32.3/218, 32.3/263),
            pos_hint={"x": 100.7/218, "y": 1 - (194+32.3)/263},
        )
        with self._plus2_bubble.canvas.before:
            Color(0.004, 0.039, 0.106, 1)
            self._plus2_bg = Ellipse(pos=self._plus2_bubble.pos, size=self._plus2_bubble.size)
        self._plus2_bubble.bind(
            pos=lambda w, _: setattr(self._plus2_bg, "pos", w.pos),
            size=lambda w, _: setattr(self._plus2_bg, "size", w.size),
        )
        card.add_widget(self._plus2_bubble)

        card.bind(on_touch_up=lambda inst, touch: (
            self._open_latest_meeting() if inst.collide_point(*touch.pos) else None
        ))
        root.add_widget(card)

    # ------------------------------------------------------------------
    # Morning Brief card (412:893)
    # ------------------------------------------------------------------
    def _build_morning_brief_card(self, root: FloatLayout) -> None:
        ph, sh = _ph_sh(657, 81, 218, 263)
        card = _CardBg(radius=12, size_hint=sh, pos_hint=ph)

        # "Morning Brief" + sun  (21, 10)
        sun_src = _figma_png("icon_sun_morning_brief.png")
        if sun_src:
            card.add_widget(Image(
                source=sun_src, size_hint=(20/218, 20/263),
                pos_hint={"x": 21/218, "y": 1 - (10+20)/263},
                fit_mode="contain",
            ))
        card.add_widget(_lbl(
            "Morning Brief", _FONT_SB, 17, _C_GRAY,
            size_hint=(120/218, 20/263),
            pos_hint={"x": (21+30)/218, "y": 1 - (10+20)/263},
        ))

        # ── Calendar mini-card  (7, 41) 204×52 ───────────────────────
        bm_cal = _CardBg(
            radius=12, fill=(0.004, 0.067, 0.196, 0.9),
            size_hint=(204/218, 52/263),
            pos_hint={"x": 7/218, "y": 1 - (41+52)/263},
        )
        ci_src = _figma_png("icon_calendar_brief.png")
        if ci_src:
            bm_cal.add_widget(Image(
                source=ci_src, size_hint=(33/204, 30/52),
                pos_hint={"x": 14/204, "y": 1 - (10.8+30)/52},
                fit_mode="contain",
            ))
        self.brief_cal_title = _lbl(
            "3 meetings today", _FONT, 15, _C_GRAY, bold=True,
            size_hint=(135/204, 18/52),
            pos_hint={"x": 57/204, "y": 1 - (9.75+18)/52},
        )
        bm_cal.add_widget(self.brief_cal_title)
        self.brief_cal_sub = _lbl(
            "First at 11:00 AM", _FONT_SB, 12, _C_MUTED,
            size_hint=(102/204, 14/52),
            pos_hint={"x": 57/204, "y": 1 - (29.25+14)/52},
        )
        bm_cal.add_widget(self.brief_cal_sub)
        card.add_widget(bm_cal)

        # ── Weather mini-card  (7, 97) 204×52 ────────────────────────
        bm_wx = _CardBg(
            radius=12, fill=(0.004, 0.067, 0.196, 0.9),
            size_hint=(204/218, 52/263),
            pos_hint={"x": 7/218, "y": 1 - (97+52)/263},
        )
        wx_src = _figma_png("icon_weather.png")
        if wx_src:
            bm_wx.add_widget(Image(
                source=wx_src, size_hint=(36/204, 36/52),
                pos_hint={"x": 9/204, "y": 1 - (7.6+36)/52},
                fit_mode="contain",
            ))
        self.brief_wx_title = _lbl(
            "Weather: --°C", _FONT, 15, _C_GRAY, bold=True,
            size_hint=(111/204, 15/52),
            pos_hint={"x": 58/204, "y": 1 - (11+15)/52},
        )
        bm_wx.add_widget(self.brief_wx_title)
        self.brief_wx_sub = _lbl(
            "--", _FONT_SB, 12, _C_MUTED,
            size_hint=(60/204, 13/52),
            pos_hint={"x": 57/204, "y": 1 - (28+13)/52},
        )
        bm_wx.add_widget(self.brief_wx_sub)
        card.add_widget(bm_wx)

        # ── Email mini-card  (7, 153) 204×89 ─────────────────────────
        bm_em = _CardBg(
            radius=12, fill=(0.004, 0.067, 0.196, 0.9),
            size_hint=(204/218, 89/263),
            pos_hint={"x": 7/218, "y": 1 - (153+89)/263},
        )
        em_src = _figma_png("icon_email.png")
        if em_src:
            bm_em.add_widget(Image(
                source=em_src, size_hint=(32/204, 32/89),
                pos_hint={"x": 9.7/204, "y": 1 - (26+32)/89},
                fit_mode="contain",
            ))
        self.brief_email_title = _lbl(
            "email:  From:", _FONT, 15, _C_WHITE, bold=True,
            size_hint=(100/204, 18/89),
            pos_hint={"x": 57/204, "y": 1 - (15.2+18)/89},
        )
        bm_em.add_widget(self.brief_email_title)
        self.brief_email_sub = _lbl(
            "Connect Gmail", _FONT_SB, 12, _C_MUTED,
            size_hint=(120/204, 13/89),
            pos_hint={"x": 57/204, "y": 1 - (35+13)/89},
        )
        bm_em.add_widget(self.brief_email_sub)
        bm_em.bind(on_touch_up=lambda inst, touch: (
            self._show_gmail_dialog() if inst.collide_point(*touch.pos) else None
        ))
        card.add_widget(bm_em)

        # "View all" + arrow  (81, 245)
        card.add_widget(_lbl(
            "View all  ›", _FONT_SB, 11, _C_BLUE,
            size_hint=(80/218, 13/263),
            pos_hint={"x": 81/218, "y": 1 - (245+13)/263},
        ))
        card.bind(on_touch_up=lambda inst, touch: (
            self.goto("briefing", transition="slide_left") if inst.collide_point(*touch.pos) else None
        ))
        root.add_widget(card)

    # ------------------------------------------------------------------
    # Schedule card (414:1153)  (17, 359)  361×102
    # ------------------------------------------------------------------
    def _build_schedule_card(self, root: FloatLayout) -> None:
        ph, sh = _ph_sh(17, 359, 361, 102)
        card = _CardBg(radius=16, size_hint=sh, pos_hint=ph)
        # Avatar circle  (0, 7)  66×66
        card.add_widget(_AvatarCircle(
            name=self._user_name, border_gradient=True,
            size_hint=(66/361, 66/102), pos_hint={"x": 0/361, "y": 1-(7+66)/102},
        ))
        # "11:00"  (82, 0)  67×32  27px SemiBold
        self.schedule_time_label = _lbl(
            "--:--", _FONT_SB, 27, _C_WHITE,
            size_hint=(80/361, 32/102),
            pos_hint={"x": 82/361, "y": 1-(0+32)/102},
        )
        card.add_widget(self.schedule_time_label)
        # "Now: Product Sync"  (82, 36)
        self.schedule_title_label = _lbl(
            "Now: Loading…", _FONT_SB, 16, _C_MUTED,
            size_hint=(200/361, 19/102),
            pos_hint={"x": 82/361, "y": 1-(36+19)/102},
        )
        card.add_widget(self.schedule_title_label)
        # "+2 more"  (82, 60)
        self.schedule_more_label = _lbl(
            "+2 more", _FONT_SB, 15, _C_BLUE,
            size_hint=(100/361, 18/102),
            pos_hint={"x": 82/361, "y": 1-(60+18)/102},
        )
        card.add_widget(self.schedule_more_label)
        # Arrow  (289, 32)
        arr = _figma_png("icon_arrow.png")
        if arr:
            card.add_widget(Image(
                source=arr, size_hint=(14/361, 28/102),
                pos_hint={"x": 289/361, "y": 1-(32+28)/102},
                fit_mode="contain",
            ))
        card.bind(on_touch_up=lambda inst, touch: (
            self.goto("meetings", transition="slide_left") if inst.collide_point(*touch.pos) else None
        ))
        root.add_widget(card)

    # ------------------------------------------------------------------
    # New Emails card (414:1111)  (384, 359)  237×102
    # ------------------------------------------------------------------
    def _build_email_card(self, root: FloatLayout) -> None:
        ph, sh = _ph_sh(384, 359, 237, 102)
        card = _CardBg(radius=16, size_hint=sh, pos_hint=ph)
        card.add_widget(_AvatarCircle(
            name=self._user_name, border_gradient=True,
            size_hint=(66/237, 66/102), pos_hint={"x": 0/237, "y": 1-(0+66)/102},
        ))
        self.email_count_label = _lbl(
            "—", _FONT_SB, 27, _C_WHITE,
            size_hint=(60/237, 32/102),
            pos_hint={"x": 82/237, "y": 1-(8+32)/102},
        )
        card.add_widget(self.email_count_label)
        card.add_widget(_lbl(
            "New emails", _FONT_SB, 18, _C_MUTED,
            size_hint=(120/237, 21/102),
            pos_hint={"x": 82/237, "y": 1-(43+21)/102},
        ))
        arr = _figma_png("icon_arrow.png")
        if arr:
            card.add_widget(Image(
                source=arr, size_hint=(14/237, 28/102),
                pos_hint={"x": 191/237, "y": 1-(22+28)/102},
                fit_mode="contain",
            ))
        card.bind(on_touch_up=lambda inst, touch: (
            self.goto("briefing", transition="slide_left") if inst.collide_point(*touch.pos) else None
        ))
        root.add_widget(card)

    # ------------------------------------------------------------------
    # Tasks Due card (414:1101)  (627, 359)  248×102
    # ------------------------------------------------------------------
    def _build_tasks_card(self, root: FloatLayout) -> None:
        ph, sh = _ph_sh(627, 359, 248, 102)
        card = _CardBg(radius=16, size_hint=sh, pos_hint=ph)
        card.add_widget(_AvatarCircle(
            name=self._user_name, border_gradient=True,
            size_hint=(66/248, 66/102), pos_hint={"x": 0/248, "y": 1-(0+66)/102},
        ))
        self.tasks_count_label = _lbl(
            "—", _FONT_SB, 27, _C_WHITE,
            size_hint=(60/248, 32/102),
            pos_hint={"x": 82/248, "y": 1-(5+32)/102},
        )
        card.add_widget(self.tasks_count_label)
        card.add_widget(_lbl(
            "Tasks due", _FONT_SB, 18, _C_MUTED,
            size_hint=(100/248, 21/102),
            pos_hint={"x": 82/248, "y": 1-(40+21)/102},
        ))
        arr = _figma_png("icon_arrow.png")
        if arr:
            card.add_widget(Image(
                source=arr, size_hint=(14/248, 28/102),
                pos_hint={"x": 182/248, "y": 1-(15+28)/102},
                fit_mode="contain",
            ))
        card.bind(on_touch_up=lambda inst, touch: (
            self.goto("briefing", transition="slide_left") if inst.collide_point(*touch.pos) else None
        ))
        root.add_widget(card)

    # ------------------------------------------------------------------
    # Bottom voice bar (412:1040)  (27, 476)  838×71  radius 21
    # ------------------------------------------------------------------
    def _build_voice_bar(self, root: FloatLayout) -> None:
        ph, sh = _ph_sh(27, 476, 838, 71)
        bar = _CardBg(
            radius=21,
            fill=(0.004, 0.067, 0.216, 0.95),
            size_hint=sh, pos_hint=ph,
        )

        # Voice/mic orb left side  Group 17 at (16, 20) 26×31 approx
        orb_src = _figma_png("icon_sparkle_layer.png")
        if orb_src:
            bar.add_widget(Image(
                source=orb_src, size_hint=(40/838, 0.7),
                pos_hint={"x": 16/838, "y": 0.15},
                fit_mode="contain",
            ))

        # "Try saying"  (41, 8)  19px SemiBold #006BF9
        bar.add_widget(_lbl(
            "Try saying", _FONT_SB, 19, _C_BLUE,
            size_hint=(120/838, 23/71),
            pos_hint={"x": 41/838, "y": 1-(8+23)/71},
        ))

        # '"Schedule a meeting tomorrow at 4 PM"'  (41, 37)
        bar.add_widget(_lbl(
            '"Schedule a meeting tomorrow at 4 PM"', _FONT_SB, 16, _C_MUTED,
            size_hint=(340/838, 19/71),
            pos_hint={"x": 41/838, "y": 1-(37+19)/71},
        ))

        # Mic orb  (403, 0)  65×65 (center)
        orb_src2 = _figma_png("icon_voice_orb_bar.png")
        if orb_src2:
            bar.add_widget(Image(
                source=orb_src2, size_hint=(65/838, 1.0),
                pos_hint={"x": 403/838, "y": 0},
                fit_mode="contain",
            ))

        # User avatar  (752, 9)  54×48
        bar.add_widget(_AvatarCircle(
            name=self._user_name,
            size_hint=(54/838, 48/71),
            pos_hint={"x": 752/838, "y": 1-(9+48)/71},
        ))

        # Keyboard icon  (right edge)
        kb_src = _figma_png("icon_keyboard.png")
        if kb_src:
            from kivy.uix.button import Button  # noqa: PLC0415
            kb = Button(
                background_normal=kb_src, background_down=kb_src,
                border=[0, 0, 0, 0],
                size_hint=(54/838, 48/71),
                pos_hint={"x": (838-60)/838, "y": 1-(10+48)/71},
            )
            kb.bind(on_release=lambda *_: self.goto("briefing", transition="slide_left"))
            bar.add_widget(kb)

        # "+" button  (voice orb expand)
        self._plus_label = Label(
            text="+", font_name=_FONT, font_size=_fs(19), bold=True,
            color=_C_BLUE, halign="center", valign="middle",
            size_hint=(20/838, 30/71),
            pos_hint={"x": 0/838, "y": 1-(20+30)/71},
        )
        bar.add_widget(self._plus_label)

        bar.bind(on_touch_up=lambda inst, touch: (
            self.goto("briefing", transition="slide_left") if inst.collide_point(*touch.pos) else None
        ))
        root.add_widget(bar)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_enter(self):
        self._update_clock()
        if self._clock_event:
            self._clock_event.cancel()
        self._clock_event = Clock.schedule_interval(lambda _: self._update_clock(), 1.0)
        if self._voice_state_event:
            self._voice_state_event.cancel()
        self._voice_state_event = Clock.schedule_interval(
            lambda _: self._refresh_voice_pill(), 2.0
        )
        self._load_home_summary()
        self._load_system_status()
        self._refresh_voice_pill()
        try:
            get_weather_client().subscribe(self._on_weather_snapshot)
        except Exception:  # noqa: BLE001
            pass

    def on_leave(self):
        if self._clock_event:
            self._clock_event.cancel()
            self._clock_event = None
        if self._voice_state_event:
            self._voice_state_event.cancel()
            self._voice_state_event = None
        try:
            get_weather_client().unsubscribe(self._on_weather_snapshot)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Live data updates
    # ------------------------------------------------------------------
    def _update_clock(self) -> None:
        now = display_now()
        self.greeting_label.text = _greeting(self._user_name)
        t = now.strftime("%I:%M").lstrip("0") or "12:00"
        self._mini_clock.text = t
        self._mini_ampm.text  = now.strftime("%p")
        self._mini_date.text  = now.strftime("%A, %B ") + str(now.day)

    def _on_weather_snapshot(self, snap) -> None:
        if getattr(self, "_health_label_offline", False):
            return
        try:
            temp  = float(snap.temp_c)
            label = (snap.label or "--").strip()
            self._mini_temp.text    = f"{temp:.0f}°C"
            self._mini_cond.text    = label
            self.brief_wx_title.text = f"Weather: {temp:.0f}°C"
            self.brief_wx_sub.text   = label
        except Exception:  # noqa: BLE001
            pass

    def _refresh_voice_pill(self) -> None:
        assistant = getattr(self.app, "voice_assistant", None)
        should_listen = getattr(self.app, "_voice_assistant_should_listen", lambda: False)()
        if assistant and getattr(assistant, "available", False) and should_listen:
            self.voice_state_label.text = "Listening"
            with self._voice_dot.canvas.before:
                Color(0.275, 0.490, 0.996, 1)
                self._vdot_circle.pos  = self._voice_dot.pos
                self._vdot_circle.size = self._voice_dot.size
        else:
            self.voice_state_label.text = "Voice paused"

    def _load_home_summary(self) -> None:
        async def _fetch():
            try:
                data     = await self.backend.get_home_summary()
                meetings = await self.backend.get_meetings(limit=1)
            except Exception as exc:  # noqa: BLE001
                logger.debug("home: summary fetch failed: %s", exc)
                return

            latest     = meetings[0] if meetings else None
            today_n    = int(data.get("pending_actions_today") or 0)
            total_n    = int(data.get("pending_actions_total") or 0)
            unread_n   = data.get("unread_email_count")
            next_time, next_title = _format_next(data.get("next_meeting"))

            def _apply(_dt):
                # Mini widget
                self._mini_next_time.text  = next_time
                self._mini_next_title.text = f"Now : {next_title}"
                self._mini_more.text       = f"+{max(0,today_n)} more" if today_n else ""
                # Schedule card
                self.schedule_time_label.text  = next_time.split(" ")[0] if next_time else "--:--"
                self.schedule_title_label.text = f"Now: {next_title}"
                self.schedule_more_label.text  = f"+{max(0, today_n)} more" if today_n else ""
                # Counters
                self.email_count_label.text = str(unread_n) if unread_n is not None else "—"
                self.tasks_count_label.text = str(total_n)
                # Last meeting card
                if latest:
                    self._latest_meeting_id = latest.get("id")
                    self.last_title_label.text = latest.get("title") or "Untitled meeting"
                    try:
                        raw = latest.get("start_time") or latest.get("created_at") or ""
                        dt  = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        when = to_display_local(dt).strftime("%b %d · %I:%M %p").replace(" 0", " ")
                    except Exception:  # noqa: BLE001
                        when = "Recent meeting"
                    dur = int(latest.get("duration") or 0) // 60
                    self._meeting_time_label.text = when
                    self._meeting_dur_label.text  = f"{dur} min" if dur else "—"
                    pa = int(latest.get("pending_actions") or 0)
                    self.last_meta_label.text = f"{pa} action items" if pa else "Last Meeting Summary"
                    self.last_actions_label.text  = "Last Meeting Summary"
                    # Update attendee avatar initials
                    attendees = latest.get("attendees") or []
                    for i, av in enumerate(self._attendee_avatars):
                        if i < len(attendees):
                            aname = attendees[i].get("name") or attendees[i].get("email") or "?"
                            av.set_name(aname)
                    self._plus2_bubble.text = f"+{max(0, len(attendees)-2)}" if len(attendees) > 2 else ""
                else:
                    self._latest_meeting_id = None
                    self.last_title_label.text    = "No meetings yet"
                    self._meeting_time_label.text = "Start a recording"
                    self._meeting_dur_label.text  = "to build memory"
                    self.last_meta_label.text     = "Open meeting library"
                # Brief card
                self.brief_cal_title.text = (
                    f"{max(0,today_n)} actions today" if today_n else "Briefing ready"
                )
                self.brief_cal_sub.text   = (
                    f"First at {next_time}" if next_time != "Time not set" else "Ask Tony for focus"
                )
                self.brief_email_title.text = "email:  From:"
                self.brief_email_sub.text   = (
                    "Connect Gmail for updates" if unread_n is None else f"{unread_n} new messages"
                )

            Clock.schedule_once(_apply, 0)

        run_async(_fetch())

    def _load_system_status(self) -> None:
        async def _fetch():
            try:
                info    = await self.backend.get_system_info()
                wifi_ok = bool(info.get("wifi_ssid"))
                wired_ok = linux_ethernet_ready()
                def _apply(_dt):
                    online = wifi_ok or wired_ok
                    self._health_label_offline = not online
                    if online:
                        snap = get_weather_client().snapshot
                        if snap is not None:
                            self._on_weather_snapshot(snap)
                Clock.schedule_once(_apply, 0)
            except Exception:  # noqa: BLE001
                def _offline(_dt):
                    self._health_label_offline = True
                Clock.schedule_once(_offline, 0)

        run_async(_fetch())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_start_recording(self, _inst) -> None:
        try:
            self.app.start_recording()
        except Exception:  # noqa: BLE001
            logger.exception("home: start_recording failed")

    def _on_listening_pill_touch(self, inst, touch):
        if not inst.collide_point(*touch.pos):
            return
        assistant = getattr(self.app, "voice_assistant", None)
        if not assistant or not getattr(assistant, "available", False):
            self.add_widget(ModalDialog(
                title="Voice unavailable",
                message="No microphone is available. Run a Microphone Test from Settings.",
                confirm_text="OK", cancel_text="",
            ))
            return
        self.app.user_voice_paused = not getattr(self.app, "user_voice_paused", False)
        try:
            self.app._sync_voice_assistant_state()
        except Exception:  # noqa: BLE001
            pass
        self._refresh_voice_pill()

    def _open_latest_meeting(self) -> None:
        if self._latest_meeting_id:
            detail = self.app.screen_manager.get_screen("meeting_detail")
            detail.set_meeting_id(self._latest_meeting_id)
            self.goto("meeting_detail", transition="slide_left")
        else:
            self.goto("meetings", transition="slide_left")

    def _show_gmail_dialog(self) -> None:
        self.add_widget(ModalDialog(
            title="Connect Gmail",
            message=(f"To see unread email here, open\n{DASHBOARD_URL}\n"
                     "on your phone or laptop and connect Gmail."),
            confirm_text="OK", cancel_text="",
        ))

    def _show_weather_location_dialog(self) -> None:
        wc = get_weather_client()
        cur = wc.location
        cur_city = (cur and cur.get("city")) or ""
        self.add_widget(TextInputDialog(
            title="Weather Location",
            message='Enter a city name (e.g. "Bangalore" or "London, UK").',
            initial_value=cur_city,
            placeholder="City name",
            on_confirm=self._apply_weather_location,
        ))

    def _apply_weather_location(self, value: str) -> None:
        text = (value or "").strip()
        if not text:
            return
        wc = get_weather_client()
        async def _resolve():
            resolved = await wc.set_city(text)
            if resolved is None:
                Clock.schedule_once(
                    lambda _dt: self.add_widget(ModalDialog(
                        title="City not found",
                        message=f'Could not find weather data for "{text}".',
                        confirm_text="OK", cancel_text="",
                    )), 0,
                )
        run_async(_resolve())

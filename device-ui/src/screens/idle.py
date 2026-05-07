"""Idle screen — Figma frame 338:60 (yJqcY4KovVjJ11vjysW533).

Pixel-perfect Figma implementation. Uses 42dot Sans font.
Tapping anywhere → home; tapping the Start Recording card → starts recording.
Time, date, greeting, weather, and next-meeting data update live.
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
from config import (
    ASSETS_DIR,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    FONTS_DIR,
    display_now,
    to_display_local,
)
from screens.base_screen import BaseScreen
from weather_client import get_weather_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Figma frame baseline
# ---------------------------------------------------------------------------
_FW: float = 892.0   # Figma frame width
_FH: float = 573.0   # Figma frame height

# Scale factor: map Figma px → display px (uniform to preserve proportions)
_SCALE: float = min(DISPLAY_WIDTH / _FW, DISPLAY_HEIGHT / _FH)

# Asset directories
_IDLE_DIR = ASSETS_DIR / "idle"


# ---------------------------------------------------------------------------
# Font registration (42dot Sans)
# ---------------------------------------------------------------------------
def _register_fonts() -> None:
    """Register 42dot Sans weights with Kivy's LabelBase (idempotent)."""
    try:
        reg  = str(FONTS_DIR / "42dotSans-Regular.ttf")
        bold = str(FONTS_DIR / "42dotSans-Bold.ttf")
        semi = str(FONTS_DIR / "42dotSans-SemiBold.ttf")
        med  = str(FONTS_DIR / "42dotSans-Medium.ttf")
        # Register base (Regular + Bold)
        LabelBase.register("42dotSans", fn_regular=reg, fn_bold=bold)
        # Register SemiBold as its own name so we can reference by font_name
        LabelBase.register("42dotSansSB", fn_regular=semi)
        # Register Medium
        LabelBase.register("42dotSansMD", fn_regular=med)
        logger.debug("42dot Sans fonts registered")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not register 42dot Sans: %s — falling back to system font", exc)


_register_fonts()


# ---------------------------------------------------------------------------
# Colors (exact Figma hex values)
# ---------------------------------------------------------------------------
_C_BG       = (0.004, 0.047, 0.145, 1.0)      # #010C25
_C_WHITE    = (1.000, 1.000, 1.000, 1.0)      # #FFFFFF
_C_MUTED    = (0.714, 0.729, 0.949, 1.0)      # #B6BAF2
_C_BLUE     = (0.000, 0.420, 0.976, 1.0)      # #006BF9  (calendar / "Next up")
_C_CARD_TOP = (0.012, 0.306, 0.886, 1.0)      # #0338E2  (card border / highlight)
_C_CARD_MID = (0.000, 0.220, 0.714, 1.0)      # #0038B6  (card top gradient)
_C_CARD_BOT = (0.000, 0.137, 0.463, 1.0)      # #002376  (card bottom gradient)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fs(px: float) -> int:
    """Scale Figma font-size (px) to display pixels."""
    return max(6, round(px * _SCALE))


def _ph_sh(fx: float, fy: float, fw: float, fh: float) -> tuple[dict, dict]:
    """Convert Figma (x, y, w, h) → Kivy (pos_hint, size_hint).

    Figma y is top-down; Kivy y is bottom-up.
    """
    return (
        {"x": fx / _FW, "y": 1.0 - (fy + fh) / _FH},
        {"x": fw / _FW, "y": fh / _FH},
    )


def _lbl(
    text: str,
    font_name: str,
    font_size: float,
    color: tuple,
    bold: bool = False,
    halign: str = "left",
    **kw,
) -> Label:
    l = Label(
        text=text,
        font_name=font_name,
        font_size=_fs(font_size),
        bold=bold,
        color=color,
        halign=halign,
        valign="middle",
        **kw,
    )
    l.bind(size=l.setter("text_size"))
    return l


def _greeting(name: str | None) -> str:
    hour = display_now().hour
    head = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    nm = (name or "").strip()
    if nm:
        parts = nm.split()
        initials = ".".join(p[0].upper() for p in parts[:2])
        return f"{head}, {initials}"
    return head


def _format_next_meeting(next_meeting: dict | None) -> tuple[str, str, int]:
    """Return (time_str, title_str, more_count)."""
    if not next_meeting:
        return ("--:-- --", "No meetings today", 0)
    title = (next_meeting.get("title") or "Calendar event").strip() or "Calendar event"
    start = (next_meeting.get("start") or "").strip()
    if not start:
        return ("Time not set", title, 0)
    try:
        if "T" in start:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            time_str = to_display_local(dt).strftime("%I:%M %p").lstrip("0")
        else:
            d = datetime.strptime(start[:10], "%Y-%m-%d")
            time_str = d.strftime("%b %d · all day")
    except (TypeError, ValueError):
        time_str = start
    return (time_str, title, 0)


# ---------------------------------------------------------------------------
# Start Recording card
# ---------------------------------------------------------------------------

class _RecordingCard(ButtonBehavior, FloatLayout):
    """Blue gradient card — Figma Group 12 at (427, 356), 414×167, radius 30."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            # Glow / shadow: offset blue ellipse
            Color(0.000, 0.502, 1.000, 0.34)
            self._glow = Ellipse(pos=(self.x - 4, self.y - 8), size=(self.width + 8, self.height + 12))
            # Gradient bottom (#002376)
            Color(*_C_CARD_BOT)
            self._bg_bot = RoundedRectangle(pos=self.pos, size=self.size, radius=[_fs(30)])
            # Gradient top (#0038B6) — upper half only
            Color(*_C_CARD_MID)
            self._bg_top = RoundedRectangle(
                pos=(self.x, self.y + self.height * 0.50),
                size=(self.width, self.height * 0.50),
                radius=[_fs(30), _fs(30), 0, 0],
            )
            # Border
            Color(*_C_CARD_TOP)
            self._border = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, _fs(30)),
                width=max(1.5, _fs(3)),
            )
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        r = _fs(30)
        self._glow.pos  = (self.x - 4, self.y - 8)
        self._glow.size = (self.width + 8, self.height + 12)
        self._bg_bot.pos  = self.pos
        self._bg_bot.size = self.size
        self._bg_bot.radius = [r]
        self._bg_top.pos  = (self.x, self.y + self.height * 0.50)
        self._bg_top.size = (self.width, self.height * 0.50)
        self._bg_top.radius = [r, r, 0, 0]
        self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, r)
        self._border.width = max(1.5, _fs(3))


# ---------------------------------------------------------------------------
# IdleScreen
# ---------------------------------------------------------------------------

class IdleScreen(BaseScreen):
    """Figma 338:60 — lock-screen-style idle UI."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._clock_event = None
        self._summary_event = None
        self._weather = get_weather_client()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = FloatLayout(size_hint=(1, 1))

        # Solid dark-navy fallback
        with root.canvas.before:
            Color(*_C_BG)
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, _: setattr(self._bg_rect, "pos", w.pos),
            size=lambda w, _: setattr(self._bg_rect, "size", w.size),
        )

        # ── Background photo ─────────────────────────────────────────
        bg_path = str(_IDLE_DIR / "background_landscape.png")
        root.add_widget(Image(
            source=bg_path,
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
            fit_mode="cover",
            allow_stretch=True,
            keep_ratio=False,
        ))

        # ── Greeting  (346:81)  "Good morning, J.K"  46,35 ────────
        ph, sh = _ph_sh(46, 35, 250, 28)
        self.greeting_label = _lbl(
            "—", "42dotSansSB", 20, _C_WHITE,
            size_hint=sh, pos_hint=ph,
        )
        root.add_widget(self.greeting_label)

        # ── Clock "11:01"  (348:84)  46,59 ──────────────────────────
        ph, sh = _ph_sh(46, 59, 268, 119)
        self.time_label = _lbl(
            "--:--", "42dotSans", 100, _C_WHITE, bold=True,
            size_hint=sh, pos_hint=ph,
        )
        root.add_widget(self.time_label)

        # ── "AM"  (348:89)  312,121 ───────────────────────────────
        ph, sh = _ph_sh(312, 121, 72, 42)
        self.ampm_label = _lbl(
            "AM", "42dotSansSB", 35, _C_MUTED,
            size_hint=sh, pos_hint=ph,
        )
        root.add_widget(self.ampm_label)

        # ── Date  (348:91)  "Tuesday, May 21"  46,178 ───────────────
        ph, sh = _ph_sh(46, 178, 300, 36)
        self.date_label = _lbl(
            "", "42dotSansSB", 30, _C_WHITE,
            size_hint=sh, pos_hint=ph,
        )
        root.add_widget(self.date_label)

        # ── Sun icon  (342:72)  677,75  64×64 ────────────────────────
        ph, sh = _ph_sh(677, 75, 64, 64)
        self.weather_icon = Image(
            source=str(_IDLE_DIR / "icon_sun.png"),
            size_hint=sh, pos_hint=ph,
            fit_mode="contain", allow_stretch=True,
        )
        root.add_widget(self.weather_icon)

        # ── Temperature "28°C"  (351:96)  759,86 ──────────────────
        ph, sh = _ph_sh(759, 86, 100, 42)
        self.temp_label = _lbl(
            "--°C", "42dotSans", 35, _C_WHITE, bold=True,
            size_hint=sh, pos_hint=ph,
        )
        root.add_widget(self.temp_label)

        # ── Condition "Sunny"  (351:97)  759,134 ──────────────────
        ph, sh = _ph_sh(759, 134, 120, 36)
        self.condition_label = _lbl(
            "--", "42dotSansMD", 30, _C_MUTED,
            size_hint=sh, pos_hint=ph,
        )
        root.add_widget(self.condition_label)

        # ── Schedule block  (Group 13)  origin (46, 333) ─────────────

        # "Next up"  355:113  (46, 333)
        ph, sh = _ph_sh(46, 333, 120, 33)
        self.next_label = _lbl(
            "Next up", "42dotSansSB", 28, _C_BLUE,
            size_hint=sh, pos_hint=ph,
        )
        root.add_widget(self.next_label)

        # Calendar icon  342:78  (46, 333+60=393)  34×34
        ph, sh = _ph_sh(46, 393, 34, 34)
        cal_path = str(_IDLE_DIR / "icon_calendar.png")
        root.add_widget(Image(
            source=cal_path, size_hint=sh, pos_hint=ph,
            fit_mode="contain", allow_stretch=True,
        ))

        # "11:00 AM"  355:115  (99, 395)
        ph, sh = _ph_sh(99, 395, 200, 33)
        self.next_time_label = _lbl(
            "--:-- --", "42dotSansSB", 28, _C_BLUE,
            size_hint=sh, pos_hint=ph,
        )
        root.add_widget(self.next_time_label)

        # "Now : Product Sync"  355:116  (46, 446)
        ph, sh = _ph_sh(46, 446, 340, 37)
        self.next_title_label = Label(
            text="--",
            font_name="42dotSans",
            font_size=_fs(31),
            bold=True,
            color=_C_WHITE,
            halign="left",
            valign="middle",
            shorten=True,
            shorten_from="right",
            size_hint=sh,
            pos_hint=ph,
        )
        self.next_title_label.bind(size=self.next_title_label.setter("text_size"))
        root.add_widget(self.next_title_label)

        # "+2 more"  355:117  (46, 497)
        ph, sh = _ph_sh(46, 497, 150, 33)
        self.more_label = _lbl(
            "", "42dotSans", 28, _C_BLUE, bold=True,
            size_hint=sh, pos_hint=ph,
        )
        root.add_widget(self.more_label)

        # ── Start Recording card  (Group 12)  427,356  414×167 ───────
        ph, sh = _ph_sh(427, 356, 414, 167)
        card = _RecordingCard(size_hint=sh, pos_hint=ph)
        card.bind(on_release=self._on_start_recording)

        # Mic orb  Group 16  (27,32) rel to card  101×101
        mic_path = str(_IDLE_DIR / "mic_orb.png")
        card.add_widget(Image(
            source=mic_path,
            size_hint=(101 / 414, 101 / 167),
            pos_hint={"x": 27 / 414, "y": 1.0 - (32 + 101) / 167},
            fit_mode="contain",
            allow_stretch=True,
        ))

        # "Start Recording"  395:171  (165, 49) rel card  219×36
        card.add_widget(Label(
            text="Start Recording",
            font_name="42dotSans",
            font_size=_fs(30),
            bold=True,
            color=_C_WHITE,
            halign="left",
            valign="middle",
            size_hint=(219 / 414, 36 / 167),
            pos_hint={"x": 165 / 414, "y": 1.0 - (49 + 36) / 167},
            text_size=(1, None),
        ))

        # 'Tap or say "start recording"'  395:172  (148, 94) rel card
        card.add_widget(Label(
            text='Tap or say "start recording"',
            font_name="42dotSansSB",
            font_size=_fs(20),
            color=_C_WHITE,
            halign="left",
            valign="middle",
            size_hint=(253 / 414, 28 / 167),
            pos_hint={"x": 148 / 414, "y": 1.0 - (94 + 28) / 167},
            text_size=(1, None),
        ))

        self._cta_card = card
        root.add_widget(card)

        self.add_widget(root)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_enter(self):
        self._update_clock()
        self._update_weather(self._weather.snapshot)
        self._weather.subscribe(self._update_weather)
        self._refresh_home_summary()
        if self._clock_event:
            self._clock_event.cancel()
        self._clock_event = Clock.schedule_interval(lambda _dt: self._update_clock(), 1.0)
        if self._summary_event:
            self._summary_event.cancel()
        self._summary_event = Clock.schedule_interval(
            lambda _dt: self._refresh_home_summary(), 60.0
        )

    def on_leave(self):
        if self._clock_event:
            self._clock_event.cancel()
            self._clock_event = None
        if self._summary_event:
            self._summary_event.cancel()
            self._summary_event = None
        self._weather.unsubscribe(self._update_weather)

    # ------------------------------------------------------------------
    # Touch: tap anywhere → home; tap card → start recording
    # ------------------------------------------------------------------
    def on_touch_up(self, touch):
        if super().on_touch_up(touch):
            return True
        lx, ly = self.to_widget(touch.x, touch.y)
        if not self.collide_point(lx, ly):
            return False
        cc = getattr(self, "_cta_card", None)
        if cc is not None:
            cx, cy = cc.to_widget(touch.x, touch.y)
            if cc.collide_point(cx, cy):
                self._on_start_recording(None)
                return True
        try:
            self.goto("home", transition="fade")
        except Exception:  # noqa: BLE001
            logger.debug("idle: goto(home) failed", exc_info=True)
        return True

    # ------------------------------------------------------------------
    # Live data
    # ------------------------------------------------------------------
    def _update_clock(self) -> None:
        now = display_now()
        name = getattr(self.app, "current_display_name", None)
        self.greeting_label.text = _greeting(name)
        self.time_label.text = now.strftime("%I:%M").lstrip("0") or "12:00"
        self.ampm_label.text = now.strftime("%p")
        self.date_label.text = now.strftime("%A, %B ") + str(now.day)

    def _update_weather(self, snapshot) -> None:
        if snapshot is None:
            return
        try:
            self.temp_label.text = f"{float(snapshot.temp_c):.0f}°C"
            self.condition_label.text = snapshot.label or "--"
            self._set_weather_icon(snapshot.icon)
        except Exception:  # noqa: BLE001
            logger.debug("idle: bad weather snapshot %r", snapshot, exc_info=True)

    def _set_weather_icon(self, key: str) -> None:
        sun_path = _IDLE_DIR / "icon_sun.png"
        cloud_path = ASSETS_DIR / "home" / "figma" / "icon_weather.png"
        if key == "sun" and sun_path.is_file():
            self.weather_icon.source = str(sun_path)
        elif cloud_path.is_file():
            self.weather_icon.source = str(cloud_path)
        elif sun_path.is_file():
            self.weather_icon.source = str(sun_path)

    def _refresh_home_summary(self) -> None:
        async def _fetch():
            try:
                data = await self.backend.get_home_summary()
            except Exception as exc:  # noqa: BLE001
                logger.debug("idle: home summary failed: %s", exc)
                return
            time_str, title, _ = _format_next_meeting(data.get("next_meeting"))
            today_n = int(data.get("pending_actions_today") or 0)

            def _apply(_dt):
                self.next_time_label.text = time_str
                self.next_title_label.text = title or "--"
                self.more_label.text = f"+{max(0, today_n)} more" if today_n else ""

            Clock.schedule_once(_apply, 0)

        run_async(_fetch())

    # ------------------------------------------------------------------
    def _on_start_recording(self, _inst) -> None:
        try:
            self.app.start_recording()
        except Exception:  # noqa: BLE001
            logger.exception("idle: start_recording failed")

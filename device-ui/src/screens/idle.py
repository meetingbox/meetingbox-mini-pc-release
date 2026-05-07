"""Idle screen — Figma `338:60` (yJqcY4KovVjJ11vjysW533).

Shown after the configurable inactivity period (default 30 s) when the device
is on home/non-recording screens. Tapping anywhere returns to home; the Start
Recording card on the lower-right starts a new meeting in place. Time, date,
greeting, weather and "next up" all refresh live so the screen never looks
stale.

Layout follows the Figma frame: full-bleed landscape background, top-left
greeting + clock, top-right weather, bottom-left "Next up" stack, bottom-right
Start Recording card. Positions are expressed as fractions of the 1024×600
Figma baseline so the screen scales cleanly to any panel size.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from async_helper import run_async
from config import (
    ASSETS_DIR,
    COLORS,
    display_now,
    home_layout_horizontal_scale,
    home_layout_vertical_scale,
    to_display_local,
)
from screens.base_screen import BaseScreen
from weather_client import get_weather_client

logger = logging.getLogger(__name__)

_IDLE_DIR = ASSETS_DIR / "idle"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Figma reference frame.
_REF_W = 1024
_REF_H = 600


def _hf(fs):
    """Font size scaled by the home vertical scale."""
    return max(6, int(round(float(fs) * home_layout_vertical_scale())))


def _hh(px):
    return max(1, int(round(float(px) * home_layout_horizontal_scale())))


def _hv(px):
    return max(1, int(round(float(px) * home_layout_vertical_scale())))


def _idle_png(name: str) -> str:
    p = _IDLE_DIR / name
    return str(p) if p.is_file() else ""


def _phint(left_px: float, top_px: float) -> dict:
    """Convert Figma top-left pixel position to a Kivy ``pos_hint``.

    Figma uses top-down coordinates within a 1024×600 reference frame. Kivy
    uses bottom-up. ``pos_hint['x']`` and ``'top'`` are fractions of the
    parent, so the layout scales with the panel automatically.
    """
    return {"x": float(left_px) / _REF_W, "top": float(_REF_H - top_px) / _REF_H}


def _greeting(name: str | None) -> str:
    hour = display_now().hour
    if hour < 12:
        head = "Good morning"
    elif hour < 17:
        head = "Good afternoon"
    else:
        head = "Good evening"
    nm = (name or "").strip()
    if nm:
        first = nm.split()[0]
        return f"{head}, {first}"
    return head


def _format_meeting_line(next_meeting: dict | None) -> tuple[str, str, int]:
    """Return ``(time_str, title_str, more_count)`` for the Next Up block.

    ``more_count`` is reserved for future use — backend ``get_home_summary``
    only ships pending action counts today, so we surface the upcoming title
    and time and leave "+N more" to mirror today's outstanding actions.
    """
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
# Start Recording card (image-driven, tappable)
# ---------------------------------------------------------------------------

class _StartRecordingCard(ButtonBehavior, FloatLayout):
    """Gradient blue card with mic orb + label + subtitle.

    The Figma artwork is composed of three layers (radial gradient body,
    bordered rounded rect, mic orb PNG). We draw the body with Kivy's
    canvas instructions so it stays crisp at any scale, and overlay the
    mic-orb PNG plus two labels.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        super().__init__(**kwargs)
        with self.canvas.before:
            # Approximate the Figma gradient (#0038b6 → #002376) with a flat
            # mid-blue plus a slight overlay; Kivy doesn't ship a built-in
            # vertical gradient on RoundedRectangle, and a 2-tone mid-blue
            # reads close enough at thumb size.
            Color(0.000, 0.220, 0.715, 1.0)  # ~#0038b6
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[_hv(30)])
            Color(0.000, 0.137, 0.460, 0.55)  # ~#002376 darker overlay
            self._bg_dark = RoundedRectangle(
                pos=(self.x, self.y),
                size=(self.width, self.height * 0.55),
                radius=[0, 0, _hv(30), _hv(30)],
            )
            # 3-px solid border #034ee2
            Color(0.012, 0.306, 0.886, 1.0)
            self._border = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, _hv(30)),
                width=max(1.5, float(_hv(3))),
            )
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_args):
        radius = _hv(30)
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bg.radius = [radius]
        self._bg_dark.pos = (self.x, self.y)
        self._bg_dark.size = (self.width, self.height * 0.55)
        self._bg_dark.radius = [0, 0, radius, radius]
        self._border.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            radius,
        )
        self._border.width = max(1.5, float(_hv(3)))


# ---------------------------------------------------------------------------
# Idle Screen
# ---------------------------------------------------------------------------

class IdleScreen(BaseScreen):
    """Lock-screen-style idle UI shown after inactivity (see ``main.py`` timer)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._clock_event = None
        self._home_summary_event = None
        self._weather = get_weather_client()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = FloatLayout(size_hint=(1, 1))
        # Solid #010c25 fallback in case the background image fails to load.
        with root.canvas.before:
            Color(0.004, 0.047, 0.145, 1)
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._sync_bg, size=self._sync_bg)

        bg_path = _idle_png("background_landscape.png")
        if bg_path:
            root.add_widget(
                Image(
                    source=bg_path,
                    size_hint=(1, 1),
                    pos_hint={"x": 0, "y": 0},
                    fit_mode="cover",
                    allow_stretch=True,
                    keep_ratio=False,
                )
            )

        # ---- Top-left: greeting / clock / date ----
        self.greeting_label = Label(
            text=_greeting(getattr(self.app, "current_display_name", None)),
            font_size=_hf(20),
            bold=True,
            color=COLORS["white"],
            halign="left",
            valign="top",
            size_hint=(None, None),
            size=(_hh(420), _hv(28)),
            pos_hint=_phint(46, 35),
        )
        self.greeting_label.bind(size=self.greeting_label.setter("text_size"))
        root.add_widget(self.greeting_label)

        self.time_label = Label(
            text="--:--",
            font_size=_hf(100),
            bold=True,
            color=COLORS["white"],
            halign="left",
            valign="top",
            size_hint=(None, None),
            size=(_hh(290), _hv(120)),
            pos_hint=_phint(40, 55),
        )
        self.time_label.bind(size=self.time_label.setter("text_size"))
        root.add_widget(self.time_label)

        self.ampm_label = Label(
            text="",
            font_size=_hf(35),
            bold=True,
            color=(0.714, 0.729, 0.949, 1),  # #b6baf2
            halign="left",
            valign="middle",
            size_hint=(None, None),
            size=(_hh(80), _hv(40)),
            pos_hint=_phint(312, 121),
        )
        self.ampm_label.bind(size=self.ampm_label.setter("text_size"))
        root.add_widget(self.ampm_label)

        self.date_label = Label(
            text="",
            font_size=_hf(30),
            bold=True,
            color=COLORS["white"],
            halign="left",
            valign="top",
            size_hint=(None, None),
            size=(_hh(420), _hv(36)),
            pos_hint=_phint(46, 178),
        )
        self.date_label.bind(size=self.date_label.setter("text_size"))
        root.add_widget(self.date_label)

        # ---- Top-right: weather block ----
        self.weather_icon = Image(
            source=_idle_png("icon_sun.png"),
            size_hint=(None, None),
            size=(_hv(64), _hv(64)),
            pos_hint=_phint(677, 75),
            fit_mode="contain",
            allow_stretch=True,
        )
        root.add_widget(self.weather_icon)

        self.temp_label = Label(
            text="--°C",
            font_size=_hf(35),
            bold=True,
            color=COLORS["white"],
            halign="left",
            valign="middle",
            size_hint=(None, None),
            size=(_hh(170), _hv(40)),
            pos_hint=_phint(770, 75),
        )
        self.temp_label.bind(size=self.temp_label.setter("text_size"))
        root.add_widget(self.temp_label)

        self.condition_label = Label(
            text="--",
            font_size=_hf(28),
            color=(0.714, 0.729, 0.949, 1),
            halign="left",
            valign="middle",
            size_hint=(None, None),
            size=(_hh(170), _hv(34)),
            pos_hint=_phint(770, 122),
        )
        self.condition_label.bind(size=self.condition_label.setter("text_size"))
        root.add_widget(self.condition_label)

        # ---- Bottom-left: "Next up" stack ----
        self.next_label = Label(
            text="Next up",
            font_size=_hf(28),
            bold=True,
            color=(0, 0.420, 0.976, 1),  # #006bf9
            halign="left",
            valign="middle",
            size_hint=(None, None),
            size=(_hh(220), _hv(36)),
            pos_hint=_phint(46, 333),
        )
        self.next_label.bind(size=self.next_label.setter("text_size"))
        root.add_widget(self.next_label)

        cal_path = _idle_png("icon_calendar.png")
        if cal_path:
            root.add_widget(
                Image(
                    source=cal_path,
                    size_hint=(None, None),
                    size=(_hv(34), _hv(34)),
                    pos_hint=_phint(46, 397),
                    fit_mode="contain",
                    allow_stretch=True,
                )
            )

        self.next_time_label = Label(
            text="--:-- --",
            font_size=_hf(28),
            bold=True,
            color=(0, 0.420, 0.976, 1),
            halign="left",
            valign="middle",
            size_hint=(None, None),
            size=(_hh(280), _hv(36)),
            pos_hint=_phint(99, 395),
        )
        self.next_time_label.bind(size=self.next_time_label.setter("text_size"))
        root.add_widget(self.next_time_label)

        self.next_title_label = Label(
            text="--",
            font_size=_hf(28),
            bold=True,
            color=COLORS["white"],
            halign="left",
            valign="middle",
            size_hint=(None, None),
            size=(_hh(370), _hv(40)),
            text_size=(_hh(370), _hv(40)),
            pos_hint=_phint(46, 446),
            shorten=True,
            shorten_from="right",
            split_str=" ",
        )
        self.next_title_label.bind(size=self.next_title_label.setter("text_size"))
        root.add_widget(self.next_title_label)

        self.more_label = Label(
            text="",
            font_size=_hf(28),
            bold=True,
            color=(0, 0.420, 0.976, 1),
            halign="left",
            valign="middle",
            size_hint=(None, None),
            size=(_hh(220), _hv(36)),
            pos_hint=_phint(46, 497),
        )
        self.more_label.bind(size=self.more_label.setter("text_size"))
        root.add_widget(self.more_label)

        # ---- Bottom-right: Start Recording card ----
        card = _StartRecordingCard(
            size=(_hh(414), _hv(167)),
            pos_hint=_phint(427, 356),
        )
        card.bind(on_release=self._on_start_recording)

        mic_path = _idle_png("mic_orb.png")
        if mic_path:
            card.add_widget(
                Image(
                    source=mic_path,
                    size_hint=(None, None),
                    size=(_hv(101), _hv(101)),
                    pos_hint={"x": 27 / 414, "center_y": 0.5},
                    fit_mode="contain",
                    allow_stretch=True,
                )
            )

        text_box = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            size=(_hh(248), _hv(90)),
            pos_hint={"x": 148 / 414, "center_y": 0.5},
            spacing=_hv(4),
        )
        cta_title = Label(
            text="Start Recording",
            font_size=_hf(30),
            bold=True,
            color=COLORS["white"],
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=_hv(40),
        )
        cta_title.bind(size=cta_title.setter("text_size"))
        text_box.add_widget(cta_title)
        cta_sub = Label(
            text='Tap or say "start recording"',
            font_size=_hf(18),
            color=COLORS["white"],
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=_hv(28),
        )
        cta_sub.bind(size=cta_sub.setter("text_size"))
        text_box.add_widget(cta_sub)
        card.add_widget(text_box)

        root.add_widget(card)
        self._cta_card = card

        self.add_widget(root)

    def _sync_bg(self, widget, *_args):
        self._bg_rect.pos = widget.pos
        self._bg_rect.size = widget.size

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_enter(self):
        self._update_clock()
        self._update_weather(self._weather.snapshot)
        self._weather.subscribe(self._update_weather)
        # Idle screen typically lives long; refresh the home summary on enter
        # and once a minute so "Next up" stays correct.
        self._refresh_home_summary()
        if self._clock_event:
            self._clock_event.cancel()
        self._clock_event = Clock.schedule_interval(lambda _dt: self._update_clock(), 1.0)
        if self._home_summary_event:
            self._home_summary_event.cancel()
        self._home_summary_event = Clock.schedule_interval(
            lambda _dt: self._refresh_home_summary(), 60.0
        )

    def on_leave(self):
        if self._clock_event:
            self._clock_event.cancel()
            self._clock_event = None
        if self._home_summary_event:
            self._home_summary_event.cancel()
            self._home_summary_event = None
        self._weather.unsubscribe(self._update_weather)

    # ------------------------------------------------------------------
    # Touch anywhere → home (Start Recording card consumes its own tap)
    # ------------------------------------------------------------------
    def on_touch_up(self, touch):
        # Let children process the touch first (e.g. Start Recording button).
        if super().on_touch_up(touch):
            return True
        if self.collide_point(*touch.pos):
            try:
                self.goto("home", transition="fade")
            except Exception:  # noqa: BLE001
                logger.debug("idle: goto(home) failed", exc_info=True)
            return True
        return False

    # ------------------------------------------------------------------
    # Live data
    # ------------------------------------------------------------------
    def _update_clock(self):
        now = display_now()
        self.greeting_label.text = _greeting(getattr(self.app, "current_display_name", None))
        self.time_label.text = now.strftime("%I:%M").lstrip("0") or "12:00"
        self.ampm_label.text = now.strftime("%p")
        self.date_label.text = now.strftime("%A, %B ") + str(now.day)

    def _update_weather(self, snapshot) -> None:
        if snapshot is None:
            return
        # snapshot is a WeatherSnapshot dataclass
        try:
            temp = float(snapshot.temp_c)
            self.temp_label.text = f"{temp:.0f}°C"
            self.condition_label.text = snapshot.label or "--"
            self._set_weather_icon(snapshot.icon)
        except Exception:  # noqa: BLE001
            logger.debug("idle: bad weather snapshot %r", snapshot, exc_info=True)

    def _set_weather_icon(self, key: str) -> None:
        # Today we only ship a sun PNG in the idle bundle. Other codes fall
        # back to the cloud icon shipped with the home assets so we never end
        # up with a blank tile. Adding more icons later is a drop-in.
        cloud_path = ASSETS_DIR / "home" / "figma" / "icon_weather.png"
        sun_path = _IDLE_DIR / "icon_sun.png"
        if key == "sun" and sun_path.is_file():
            self.weather_icon.source = str(sun_path)
        elif cloud_path.is_file():
            self.weather_icon.source = str(cloud_path)
        elif sun_path.is_file():
            self.weather_icon.source = str(sun_path)

    def _refresh_home_summary(self):
        async def _fetch():
            try:
                data = await self.backend.get_home_summary()
            except Exception as exc:  # noqa: BLE001
                logger.debug("idle: home summary fetch failed: %s", exc)
                return
            time_str, title, _ = _format_meeting_line(data.get("next_meeting"))
            today_n = int(data.get("pending_actions_today") or 0)

            def _apply(_dt):
                self.next_time_label.text = time_str
                self.next_title_label.text = title or "--"
                self.more_label.text = f"+{max(0, today_n)} more" if today_n else ""

            Clock.schedule_once(_apply, 0)

        run_async(_fetch())

    # ------------------------------------------------------------------
    # Start Recording CTA
    # ------------------------------------------------------------------
    def _on_start_recording(self, _inst):
        try:
            self.app.start_recording()
        except Exception:  # noqa: BLE001
            logger.exception("idle: start_recording failed")

"""Summary-ready notification card.

Lives at app level (mounted on ``App.root_layout``) rather than inside a single
screen, so a summary that finishes while the user is on Tasks, Calendar, Emails
— anywhere — still surfaces. Previously this was built inside HomeScreen and
polled only while Home was the visible screen, so summaries completing
elsewhere were silently missed until the user went back Home.
"""

from __future__ import annotations

from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Line, RoundedRectangle

from config import DISPLAY_WIDTH, DISPLAY_HEIGHT

# Figma reference frame (System States_1, 1260 x 800).
_FW, _FH = 1260.0, 800.0

_TEXT = (0.227, 0.231, 0.239, 1.0)      # #3A3B3D
_SUBTLE = (0.45, 0.45, 0.50, 1.0)
_PILL_BG = (0.980, 0.980, 0.980, 1.0)   # #FAFAFA — app surface
_PURPLE = (0.427, 0.282, 0.800, 1.0)    # #6D48CC accent
_SHADOW = (0.463, 0.506, 0.498, 1.0)    # rgb of rgba(118,129,127,*)
_EDGE = (0.84, 0.85, 0.87, 0.9)

_FONT_SB = "42dot-SB"

# Screens where the card would be intrusive or redundant: the setup/boot flow,
# and places already dedicated to this content (processing shows the progress,
# summary_review shows the summary itself). Everywhere else — home, tasks,
# calendar, emails, meetings, settings, brief, voice — shows it.
NOTIFY_BLOCKED_SCREENS = frozenset({
    "splash", "welcome", "room_name", "network_choice", "wifi_setup",
    "wifi_connected", "setup_progress", "pair_device", "meetingbox_ready",
    "all_set", "complete", "connectivity_check", "update_check",
    "update_install", "error",
    "recording", "processing", "summary_review", "idle",
})


def _x(px: float) -> float:
    return px / _FW


def _y(top: float, h: float) -> float:
    return max(0.0, (_FH - top - h) / _FH)


def _sw(px: float) -> float:
    return px / _FW


def _sh(px: float) -> float:
    return px / _FH


def _ff(fs: float) -> int:
    s = min(DISPLAY_WIDTH / _FW, DISPLAY_HEIGHT / _FH)
    return max(6, round(fs * s))


class SummaryCard(FloatLayout):
    """Rounded notification container with a soft, layered drop shadow.

    Kivy cannot blur, so the Figma shadow ("0 6 19 rgba(118,129,127,0.3)") is
    approximated by stacking translucent rounded rects with growing spread and
    falling alpha — a soft falloff rather than one hard offset slab.
    """

    # (outset px, downward drop px, alpha) — widest/faintest drawn first.
    _SHADOW_LAYERS = (
        (13.0, 9.0, 0.028),
        (9.5, 7.0, 0.040),
        (6.0, 5.0, 0.055),
        (3.2, 3.2, 0.070),
        (1.4, 1.6, 0.085),
    )

    def __init__(self, **kw):
        super().__init__(**kw)
        sr, sg, sb, _ = _SHADOW
        with self.canvas.before:
            self._shadows = []
            for _spread, _drop, alpha in self._SHADOW_LAYERS:
                Color(sr, sg, sb, alpha)
                self._shadows.append(
                    RoundedRectangle(pos=(0, 0), size=(1, 1), radius=[30])
                )
            Color(*_PILL_BG)
            self._bg = RoundedRectangle(pos=(0, 0), size=(1, 1), radius=[28])
            Color(*_EDGE)
            self._border = Line(rounded_rectangle=(0, 0, 0, 0, 28), width=1.2)
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        x, y = self.pos
        w, h = self.size
        if w <= 0 or h <= 0:
            return
        r = min(w, h) / 2
        for rect, (spread, drop, _alpha) in zip(self._shadows, self._SHADOW_LAYERS):
            rect.pos = (x - spread, y - spread - drop)
            rect.size = (w + spread * 2, h + spread * 2)
            rect.radius = [r + spread]
        self._bg.pos = (x, y)
        self._bg.size = (w, h)
        self._bg.radius = [r]
        self._border.rounded_rectangle = (x + 1, y + 1, w - 2, h - 2, max(2, r - 1))


class PopupButton(ButtonBehavior, FloatLayout):
    """Rounded button with a press state so the control feels physical."""

    _PRESS_SHADE = 0.88

    def __init__(self, fill, border=None, shadow=False, **kw):
        super().__init__(**kw)
        self._fill = fill
        self._pressed_fill = (
            max(0.0, fill[0] * self._PRESS_SHADE),
            max(0.0, fill[1] * self._PRESS_SHADE),
            max(0.0, fill[2] * self._PRESS_SHADE),
            fill[3],
        )
        sr, sg, sb, _ = _SHADOW
        with self.canvas.before:
            self._shadow_rect = None
            if shadow:
                Color(sr, sg, sb, 0.16)
                self._shadow_rect = RoundedRectangle(pos=(0, 0), size=(1, 1), radius=[22])
            self._color = Color(*fill)
            self._bg = RoundedRectangle(pos=(0, 0), size=(1, 1), radius=[22])
            self._border_line = None
            if border is not None:
                Color(*border)
                self._border_line = Line(rounded_rectangle=(0, 0, 0, 0, 22), width=1.1)
        self.bind(pos=self._draw, size=self._draw, state=self._draw)

    def _draw(self, *_):
        x, y = self.pos
        w, h = self.size
        if w <= 0 or h <= 0:
            return
        r = min(w, h) / 2
        held = self.state == "down"
        self._color.rgba = self._pressed_fill if held else self._fill
        if self._shadow_rect is not None:
            drop = 1.0 if held else 2.6
            self._shadow_rect.pos = (x - 1.0, y - drop)
            self._shadow_rect.size = (w + 2.0, h + 2.0)
            self._shadow_rect.radius = [r + 1.0]
        self._bg.pos = (x, y)
        self._bg.size = (w, h)
        self._bg.radius = [r]
        if self._border_line is not None:
            self._border_line.rounded_rectangle = (
                x + 0.5, y + 0.5, w - 1, h - 1, max(2, r - 0.5)
            )


def summary_title(summary: dict) -> tuple[str, bool]:
    """Return (display title, is_note) for a summary payload."""
    title = "Your meeting"
    mode = "meeting"
    if isinstance(summary, dict):
        mode = str(
            summary.get("recording_mode") or summary.get("content_type") or "meeting"
        ).strip().lower()
        for key in ("title", "report_title", "meeting_title", "name"):
            value = str(summary.get(key) or "").strip()
            if value:
                title = value
                break
    is_note = mode in {"note", "notes"}
    if is_note and title == "Your meeting":
        title = "Notes"
    return title, is_note


def build_summary_notification(summary: dict, on_view, on_close) -> SummaryCard:
    """Build the summary-ready card. Caller mounts it and owns dismissal."""
    title, is_note = summary_title(summary)

    card = SummaryCard(
        size_hint=(_sw(760), _sh(88)),
        pos_hint={"x": _x((_FW - 760) / 2), "y": _y(96, 88)},
    )

    headline = Label(
        text="Notes are ready" if is_note else "Meeting summary is ready",
        font_name=_FONT_SB,
        font_size=_ff(22),
        color=_TEXT,
        halign="left",
        valign="middle",
        size_hint=(0.56, 0.34),
        pos_hint={"x": 0.045, "center_y": 0.63},
    )
    headline.bind(size=headline.setter("text_size"))
    card.add_widget(headline)

    subtitle = Label(
        text=title,
        font_name=_FONT_SB,
        font_size=_ff(17),
        color=_SUBTLE,
        halign="left",
        valign="middle",
        shorten=True,
        shorten_from="right",
        max_lines=1,
        size_hint=(0.56, 0.30),
        pos_hint={"x": 0.045, "center_y": 0.34},
    )
    subtitle.bind(size=subtitle.setter("text_size"))
    card.add_widget(subtitle)

    view_btn = PopupButton(
        fill=_PURPLE,
        shadow=True,
        size_hint=(0.1447, 0.59),
        pos_hint={"x": 0.687, "center_y": 0.5},
    )
    view_label = Label(
        text="View",
        font_name=_FONT_SB,
        font_size=_ff(20),
        color=(1, 1, 1, 1),
        halign="center",
        valign="middle",
        size_hint=(1, 1),
        pos_hint={"x": 0, "y": 0},
    )
    view_label.bind(size=view_label.setter("text_size"))
    view_btn.add_widget(view_label)
    view_btn.bind(on_release=lambda *_a: on_view())
    card.add_widget(view_btn)

    close_btn = PopupButton(
        fill=(0.955, 0.957, 0.965, 1.0),
        border=(0.84, 0.85, 0.87, 1.0),
        size_hint=(0.126, 0.59),
        pos_hint={"x": 0.847, "center_y": 0.5},
    )
    close_label = Label(
        text="Close",
        font_name=_FONT_SB,
        font_size=_ff(18),
        color=_TEXT,
        halign="center",
        valign="middle",
        size_hint=(1, 1),
        pos_hint={"x": 0, "y": 0},
    )
    close_label.bind(size=close_label.setter("text_size"))
    close_btn.add_widget(close_label)
    close_btn.bind(on_release=lambda *_a: on_close())
    card.add_widget(close_btn)

    return card

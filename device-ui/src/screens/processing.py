"""Processing / "Summarizing" screen — Figma ``1036:16``
(dvqlN0JtWQODt6jYbTrbDG, "Copy").

Shown immediately after a recording stops. Drawn entirely with Kivy primitives:

  * "Recording Complete" + "Meeting Name · 32 min" header
  * a centre orb with a calm, breathing concentric-ring animation
  * "Summarizing your meeting..." / "This may take a few seconds" captions
  * a rotating stage line
  * a bottom countdown — "Back to home screen in N seconds" — that returns to
    the home screen after 3 s. The "summary ready" notification is surfaced on
    the home screen (see ``home.py``); the summary keeps generating in the
    background via the app's existing summary poll.

Public API preserved for ``main.py`` (all safe to call while hidden):
on_enter / on_leave, on_processing_started, set_processing_status,
on_backend_progress, on_transcription_ready, on_summary_ready,
on_summary_failed.
"""

from __future__ import annotations

import logging
from typing import Optional

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from processing_layout import (
    BG_BOT,
    BG_TOP,
    COL_COUNTDOWN,
    COL_HEADLINE,
    COL_MUTED,
    COL_PURPLE,
    COL_TEXT,
    COUNTDOWN,
    COUNTDOWN_FS_RATIO,
    HEADLINE,
    HEADLINE_FS_RATIO,
    META,
    META_FS_RATIO,
    ORB,
    ORB_FILL,
    RING_BOT,
    RING_TOP,
    STAGE,
    STAGE_FS_RATIO,
    STATUS_BAR,
    SUBTITLE,
    SUBTITLE_FS_RATIO,
    SUMMARIZING,
    SUMMARIZING_FS_RATIO,
    font_px,
    kivy_hints,
    scaled_canvas,
)
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

_FONT = "42dot-Sans"

# Seconds the user stays on this screen before being returned home.
_RETURN_COUNTDOWN_S = 3

_DEFAULT_STAGES = (
    "Extracting key points...",
    "Identifying action items...",
    "Structuring summary...",
)


class _PulseOrb(Widget):
    """Navy disc + a steady purple rim and three calm sonar rings.

    The rings expand smoothly from the centre and fade out, phased a third of a
    cycle apart, giving a gentle "thinking" pulse without any bitmap/GIF asset.
    """

    _PERIOD_S = 2.6

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._phase = 0.0
        self._event = None
        with self.canvas:
            Color(*ORB_FILL)
            self._disc = Ellipse(pos=self.pos, size=self.size)
            self._rim_color = Color(RING_BOT[0], RING_BOT[1], RING_BOT[2], 0.9)
            self._rim = Line(circle=(0, 0, 0), width=2.0)
            self._ring_colors = []
            self._rings = []
            for _ in range(3):
                c = Color(RING_TOP[0], RING_TOP[1], RING_TOP[2], 0.0)
                self._ring_colors.append(c)
                self._rings.append(Line(circle=(0, 0, 0), width=2.0))
        self.bind(pos=self._redraw, size=self._redraw)

    def start(self) -> None:
        if self._event is None:
            self._event = Clock.schedule_interval(self._tick, 1 / 30.0)

    def stop(self) -> None:
        if self._event is not None:
            self._event.cancel()
            self._event = None

    def _tick(self, dt: float) -> None:
        self._phase = (self._phase + dt / self._PERIOD_S) % 1.0
        self._redraw()

    def _redraw(self, *_):
        x, y, w, h = self.x, self.y, self.width, self.height
        if w <= 0 or h <= 0:
            return
        cx, cy = x + w / 2.0, y + h / 2.0
        R = min(w, h) / 2.0
        self._disc.pos = self.pos
        self._disc.size = self.size
        rim_w = max(1.5, w * 0.012)
        self._rim.width = rim_w
        self._rim.circle = (cx, cy, R - rim_w / 2.0)
        for i, (col, ring) in enumerate(zip(self._ring_colors, self._rings)):
            p = (self._phase + i / 3.0) % 1.0
            r = (0.12 + 0.84 * p) * R
            col.a = max(0.0, (1.0 - p) * 0.55)
            ring.width = max(1.2, w * 0.01)
            ring.circle = (cx, cy, r)


class ProcessingScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._meeting_id: Optional[str] = None
        self._meeting_title = "Meeting"
        self._meeting_duration_seconds = 0
        self._stage_index = 0
        self._countdown_event = None
        self._stage_event = None
        self._countdown_left = _RETURN_COUNTDOWN_S
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self._root = FloatLayout(size_hint=(1, 1))
        from ui_bg import attach_gradient_bg

        attach_gradient_bg(self._root, BG_TOP, BG_BOT)
        self._root.bind(size=self._on_root_resize)

        anchor = AnchorLayout(anchor_x="center", anchor_y="center", size_hint=(1, 1))
        self._root.add_widget(anchor)
        self._canvas = FloatLayout(size_hint=(None, None))
        anchor.add_widget(self._canvas)

        self.orb = _PulseOrb(**kivy_hints(ORB))
        self._canvas.add_widget(self.orb)

        self.headline_status = self._add_label(
            "Recording Complete", HEADLINE, HEADLINE_FS_RATIO, COL_HEADLINE, bold=True,
        )
        self.meta_label = self._add_label("Meeting", META, META_FS_RATIO, COL_TEXT)
        self.summarizing_label = self._add_label(
            "Summarizing your meeting...", SUMMARIZING, SUMMARIZING_FS_RATIO, COL_HEADLINE, bold=True,
        )
        self.subtitle_label = self._add_label(
            "This may take a few seconds", SUBTITLE, SUBTITLE_FS_RATIO, COL_MUTED,
        )
        self.stage_label = self._add_label(
            _DEFAULT_STAGES[0], STAGE, STAGE_FS_RATIO, COL_PURPLE,
        )
        self.countdown_label = self._add_label(
            "Back to home screen in 3 seconds", COUNTDOWN, COUNTDOWN_FS_RATIO, COL_COUNTDOWN,
        )

        self.add_widget(self._root)
        Clock.schedule_once(lambda _dt: self._on_root_resize(self._root, self._root.size), 0)

    # --------------------------------------------------------------- helpers
    def _add_label(self, text, box, fs_ratio, color, *, bold=False):
        lbl = Label(
            text=text,
            font_name=_FONT,
            bold=bold,
            color=color,
            halign="center",
            valign="middle",
            shorten=True,
            shorten_from="right",
            max_lines=1,
            **kivy_hints(box),
        )
        lbl.bind(size=lbl.setter("text_size"))
        lbl._fs_ratio = fs_ratio  # noqa: SLF001
        self._canvas.add_widget(lbl)
        return lbl

    def _on_root_resize(self, _root, size):
        w, h = scaled_canvas(size[0], size[1])
        self._canvas.size = (w, h)
        for lbl in (
            self.headline_status,
            self.meta_label,
            self.summarizing_label,
            self.subtitle_label,
            self.stage_label,
            self.countdown_label,
        ):
            if lbl is not None:
                lbl.font_size = font_px(lbl._fs_ratio, h)  # noqa: SLF001

    # ------------------------------------------------------------- lifecycle
    def on_enter(self):
        self._meeting_id = getattr(self.app, "current_session_id", None)
        self.headline_status.text = "Recording Complete"
        self.summarizing_label.text = "Summarizing your meeting..."
        self.subtitle_label.text = "This may take a few seconds"
        self._stage_index = 0
        self.stage_label.text = _DEFAULT_STAGES[0]
        self.meta_label.text = self._meta_text()

        self.orb.start()
        self._stage_event = Clock.schedule_interval(self._rotate_stage, 0.9)

        self._countdown_left = _RETURN_COUNTDOWN_S
        self._update_countdown_label()
        self._countdown_event = Clock.schedule_interval(self._tick_countdown, 1.0)

    def on_leave(self):
        self.orb.stop()
        for ev_name in ("_countdown_event", "_stage_event"):
            ev = getattr(self, ev_name, None)
            if ev is not None:
                ev.cancel()
                setattr(self, ev_name, None)

    # ------------------------------------------------------------- countdown
    def _update_countdown_label(self) -> None:
        n = max(0, self._countdown_left)
        unit = "second" if n == 1 else "seconds"
        self.countdown_label.text = f"Back to home screen in {n} {unit}"

    def _tick_countdown(self, _dt) -> None:
        self._countdown_left -= 1
        if self._countdown_left <= 0:
            self._update_countdown_label()
            ev = self._countdown_event
            if ev is not None:
                ev.cancel()
                self._countdown_event = None
            self.goto("home", transition="fade")
            return
        self._update_countdown_label()

    def _rotate_stage(self, _dt) -> None:
        self._stage_index = (self._stage_index + 1) % len(_DEFAULT_STAGES)
        self.stage_label.text = _DEFAULT_STAGES[self._stage_index]

    # ------------------------------------------------------------------
    # Public API — called from main.py (kept compatible; the screen still
    # auto-returns home, the summary surfaces there when ready)
    # ------------------------------------------------------------------
    def on_processing_started(self, data):
        title = str((data or {}).get("title") or self._meeting_title or "Meeting").strip() or "Meeting"
        duration = int((data or {}).get("duration") or 0)
        self._meeting_title = title
        self._meeting_duration_seconds = duration
        self.meta_label.text = self._meta_text()

    def set_processing_status(self, text: str) -> None:
        msg = (text or "").strip()
        if msg and getattr(self, "stage_label", None) is not None:
            self.stage_label.text = msg

    def on_backend_progress(self, progress: int, status: str, eta: int, stage: str | None = None):
        del progress, eta
        label = (stage or status or "").strip()
        if label:
            self.set_processing_status(label.replace("_", " ").capitalize())

    def on_transcription_ready(self, meeting_id: str):
        if meeting_id:
            self._meeting_id = meeting_id

    def on_summary_ready(self, meeting_id: str, summary_data: dict):
        del summary_data
        if meeting_id:
            self._meeting_id = meeting_id

    def on_summary_failed(self, meeting_id: str, detail: str):
        del detail
        if meeting_id:
            self._meeting_id = meeting_id

    # ------------------------------------------------------------------
    def _meta_text(self) -> str:
        parts = [self._meeting_title or "Meeting"]
        dur = self._format_duration(self._meeting_duration_seconds)
        if dur != "--":
            parts.append(dur)
        return "    ·    ".join(parts)

    @staticmethod
    def _format_duration(seconds_value: int) -> str:
        total = max(0, int(seconds_value or 0))
        if total <= 0:
            return "--"
        minutes = total // 60
        if minutes >= 1:
            return f"{minutes} min"
        return f"{total} sec"

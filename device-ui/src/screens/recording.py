"""Recording screen — Figma Frame 19 / `863:635` inside `863:626` (yJqcY4KovVjJ11vjysW533).

Only Frame 19 is rendered: side dot vectors, elapsed timer, and status caption
on the #01081A background. Recording state (timer, pause/resume hooks) is kept
for ``main.py``; controls are voice / backend driven until later frames are added.
"""

from __future__ import annotations

import logging
import time

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from config import ASSETS_DIR, DISPLAY_HEIGHT, DISPLAY_WIDTH
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

# Figma Frame 18 root (parent of Frame 19)
_FW = 1260.0
_FH = 800.0

# Frame 19 — `863:635`
_F19_X = 392.0
_F19_Y = 104.0
_F19_W = 423.0
_F19_H = 438.0

_FIGMA_DIR = ASSETS_DIR / "recording" / "figma"

_BG = (1 / 255, 8 / 255, 26 / 255, 1.0)       # #01081A
_WHITE = (1.0, 1.0, 1.0, 1.0)
_MUTED = (182 / 255, 186 / 255, 242 / 255, 1.0)  # #B6BAF2

_FONT_BOLD = "42dot-Sans"


def _ph(fx: float, fy: float, fw: float, fh: float) -> dict:
    """Figma absolute px → Kivy size_hint + pos_hint for the 1260×800 root."""
    return {
        "size_hint": (fw / _FW, fh / _FH),
        "pos_hint": {"x": fx / _FW, "y": (_FH - fy - fh) / _FH},
    }


def _ph_f19(fx: float, fy: float, fw: float, fh: float) -> dict:
    """Figma px relative to Frame 19 origin → Kivy hints inside the frame."""
    return {
        "size_hint": (fw / _F19_W, fh / _F19_H),
        "pos_hint": {"x": fx / _F19_W, "y": (_F19_H - fy - fh) / _F19_H},
    }


def _ff(fs: float) -> int:
    scale = min(DISPLAY_WIDTH / _FW, DISPLAY_HEIGHT / _FH)
    return max(6, round(fs * scale))


def _asset(name: str) -> str:
    p = _FIGMA_DIR / name
    return str(p) if p.is_file() else ""


def _lbl(
    text: str,
    *,
    fs: float,
    color: tuple,
    ha: str = "left",
    va: str = "top",
    **kw,
) -> Label:
    label = Label(
        text=text,
        font_name=_FONT_BOLD,
        font_size=_ff(fs),
        bold=True,
        color=color,
        halign=ha,
        valign=va,
        **kw,
    )
    label.bind(size=label.setter("text_size"))
    return label


class RecordingScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.elapsed_seconds = 0
        self.timer_event = None
        self._is_paused = False
        self._rec_base_elapsed = 0.0
        self._rec_active_start = None
        self._build_ui()

    def _build_ui(self):
        root = FloatLayout()
        with root.canvas.before:
            Color(*_BG)
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, _v: setattr(self._bg, "pos", w.pos),
            size=lambda w, _v: setattr(self._bg, "size", w.size),
        )

        frame = FloatLayout(**_ph(_F19_X, _F19_Y, _F19_W, _F19_H))
        root.add_widget(frame)

        left_src = _asset("frame19_vector_left.svg")
        if left_src:
            frame.add_widget(Image(
                source=left_src,
                allow_stretch=True,
                fit_mode="contain",
                **_ph_f19(52.0, 67.47, 36.97, 173.32),
            ))

        right_src = _asset("frame19_vector_right.svg")
        if right_src:
            frame.add_widget(Image(
                source=right_src,
                allow_stretch=True,
                fit_mode="contain",
                **_ph_f19(335.8, 67.47, 36.97, 173.32),
            ))

        self.timer_label = _lbl(
            "00 : 12 : 45",
            fs=35,
            color=_WHITE,
            ha="left",
            va="top",
            **_ph_f19(104.0, 298.0, 178.0, 42.0),
        )
        frame.add_widget(self.timer_label)

        self.status_label = _lbl(
            "Recording in progress",
            fs=28.251121520996094,
            color=_MUTED,
            ha="left",
            va="top",
            **_ph_f19(62.0, 346.0, 290.0, 34.0),
        )
        frame.add_widget(self.status_label)

        self.add_widget(root)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_enter(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

        self._is_paused = False
        self.elapsed_seconds = 0
        self._rec_base_elapsed = 0.0
        self._rec_active_start = time.monotonic()
        self.timer_label.text = "00 : 00 : 00"
        self.status_label.text = "Recording in progress"
        self.timer_event = Clock.schedule_interval(self._tick_timer, 0.5)

    def on_leave(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

    # ------------------------------------------------------------------
    # Timer
    # ------------------------------------------------------------------
    def _elapsed_from_monotonic(self) -> int:
        if self._is_paused or self._rec_active_start is None:
            return int(self._rec_base_elapsed)
        return int(self._rec_base_elapsed + (time.monotonic() - self._rec_active_start))

    def _tick_timer(self, _dt):
        self.elapsed_seconds = self._elapsed_from_monotonic()
        self.timer_label.text = self._fmt_time(self.elapsed_seconds)

    @staticmethod
    def _fmt_time(secs: int) -> str:
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        return f"{h:02d} : {m:02d} : {s:02d}"

    # ------------------------------------------------------------------
    # Pause / resume (called from main.py)
    # ------------------------------------------------------------------
    def on_paused(self):
        if self._is_paused:
            return
        self._is_paused = True
        if self._rec_active_start is not None:
            self._rec_base_elapsed += time.monotonic() - self._rec_active_start
            self._rec_active_start = None
        self.status_label.text = "Recording paused"

    def on_resumed(self):
        if not self._is_paused:
            return
        self._is_paused = False
        self._rec_active_start = time.monotonic()
        self.status_label.text = "Recording in progress"

    def on_audio_level(self, level: float):
        del level

    def on_audio_segment(self, segment_num: int):
        del segment_num

"""Recording screen — Frame 19 only (`863:635`).  Layout = pure ratios (see frame19_layout)."""

from __future__ import annotations

import logging
import time

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from config import ASSETS_DIR, DISPLAY_HEIGHT
from frame19_layout import (
    BG_RGB,
    LEFT_VEC,
    RIGHT_VEC,
    STATUS,
    STATUS_FS_RATIO,
    TIMER,
    TIMER_FS_RATIO,
    font_px,
    kivy_hints,
)
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

_FIGMA_DIR = ASSETS_DIR / "recording" / "figma"
_BG = (BG_RGB[0] / 255, BG_RGB[1] / 255, BG_RGB[2] / 255, 1.0)
_WHITE = (1.0, 1.0, 1.0, 1.0)
_MUTED = (182 / 255, 186 / 255, 242 / 255, 1.0)
_FONT_BOLD = "42dot-Sans"


def _png(name: str) -> str:
    p = _FIGMA_DIR / name
    return str(p) if p.is_file() else ""


def _lbl(text: str, *, fs_ratio: float, color: tuple, box, **kw) -> Label:
    label = Label(
        text=text,
        font_name=_FONT_BOLD,
        font_size=font_px(fs_ratio, DISPLAY_HEIGHT),
        bold=True,
        color=color,
        halign="left",
        valign="middle",
        **kivy_hints(box),
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
        root = FloatLayout(size_hint=(1, 1))
        with root.canvas.before:
            Color(*_BG)
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, _v: setattr(self._bg, "pos", w.pos),
            size=lambda w, _v: setattr(self._bg, "size", w.size),
        )

        left = _png("frame19_vector_left.png")
        if left:
            root.add_widget(Image(
                source=left,
                allow_stretch=True,
                keep_ratio=True,
                fit_mode="contain",
                **kivy_hints(LEFT_VEC),
            ))

        right = _png("frame19_vector_right.png")
        if right:
            root.add_widget(Image(
                source=right,
                allow_stretch=True,
                keep_ratio=True,
                fit_mode="contain",
                **kivy_hints(RIGHT_VEC),
            ))

        self.timer_label = _lbl("00 : 12 : 45", fs_ratio=TIMER_FS_RATIO, color=_WHITE, box=TIMER)
        root.add_widget(self.timer_label)

        self.status_label = _lbl(
            "Recording in progress",
            fs_ratio=STATUS_FS_RATIO,
            color=_MUTED,
            box=STATUS,
        )
        root.add_widget(self.status_label)

        self.add_widget(root)

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

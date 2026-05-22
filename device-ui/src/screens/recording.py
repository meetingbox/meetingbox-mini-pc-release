"""Recording screen — Frame 19 only (`863:635`).

Coordinate system: Figma 1260×800 parent screen.
Frame 19 sits inside that at (392, 104) / 423×438 — exact Figma position.
The whole 1260×800 canvas is scaled uniformly to fit any real device screen.
"""

from __future__ import annotations

import logging
import time

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from config import ASSETS_DIR
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
    scaled_canvas,
)
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

_FIGMA_DIR = ASSETS_DIR / "recording" / "figma"
_BG    = (BG_RGB[0] / 255, BG_RGB[1] / 255, BG_RGB[2] / 255, 1.0)
_WHITE = (1.0, 1.0, 1.0, 1.0)
_MUTED = (182 / 255, 186 / 255, 242 / 255, 1.0)
_FONT  = "42dot-Sans"


def _png(name: str) -> str:
    p = _FIGMA_DIR / name
    return str(p) if p.is_file() else ""


class RecordingScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.elapsed_seconds   = 0
        self.timer_event       = None
        self._is_paused        = False
        self._rec_base_elapsed = 0.0
        self._rec_active_start = None
        self._canvas           = None
        self.timer_label       = None
        self.status_label      = None
        self._bg_rect          = None
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = FloatLayout(size_hint=(1, 1))

        with root.canvas.before:
            Color(*_BG)
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos =lambda w, _: setattr(self._bg_rect, "pos",  w.pos),
            size=self._on_resize,
        )

        # Centred canvas: the scaled 1260×800 reference frame
        anchor = AnchorLayout(anchor_x="center", anchor_y="center", size_hint=(1, 1))
        root.add_widget(anchor)

        self._canvas = FloatLayout(size_hint=(None, None))
        anchor.add_widget(self._canvas)

        # ── Frame 19 children ──────────────────────────────────────────
        for name, box in (
            ("frame19_vector_left.png",  LEFT_VEC),
            ("frame19_vector_right.png", RIGHT_VEC),
        ):
            src = _png(name)
            if src:
                self._canvas.add_widget(Image(
                    source=src,
                    allow_stretch=True,
                    keep_ratio=True,
                    fit_mode="contain",
                    **kivy_hints(box),
                ))

        self.timer_label = Label(
            text="00 : 12 : 45",
            font_name=_FONT, bold=True, color=_WHITE,
            halign="left", valign="middle",
            **kivy_hints(TIMER),
        )
        self.timer_label.bind(size=self.timer_label.setter("text_size"))
        self._canvas.add_widget(self.timer_label)

        self.status_label = Label(
            text="Recording in progress",
            font_name=_FONT, bold=True, color=_MUTED,
            halign="left", valign="middle",
            **kivy_hints(STATUS),
        )
        self.status_label.bind(size=self.status_label.setter("text_size"))
        self._canvas.add_widget(self.status_label)

        self.add_widget(root)
        Clock.schedule_once(lambda _: self._on_resize(root, root.size), 0)

    def _on_resize(self, widget, size):
        self._bg_rect.size = size
        cw, ch = scaled_canvas(size[0], size[1])
        self._canvas.size          = (cw, ch)
        self.timer_label.font_size  = font_px(TIMER_FS_RATIO,  ch)
        self.status_label.font_size = font_px(STATUS_FS_RATIO, ch)

    # ------------------------------------------------------------------
    def on_enter(self):
        if self.timer_event:
            self.timer_event.cancel()
        self._is_paused        = False
        self.elapsed_seconds   = 0
        self._rec_base_elapsed = 0.0
        self._rec_active_start = time.monotonic()
        self.timer_label.text  = "00 : 00 : 00"
        self.status_label.text = "Recording in progress"
        self.timer_event = Clock.schedule_interval(self._tick_timer, 0.5)

    def on_leave(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

    # ------------------------------------------------------------------
    def _elapsed_from_monotonic(self) -> int:
        if self._is_paused or self._rec_active_start is None:
            return int(self._rec_base_elapsed)
        return int(self._rec_base_elapsed + (time.monotonic() - self._rec_active_start))

    def _tick_timer(self, _dt):
        self.elapsed_seconds  = self._elapsed_from_monotonic()
        self.timer_label.text = self._fmt_time(self.elapsed_seconds)

    @staticmethod
    def _fmt_time(s: int) -> str:
        return f"{s // 3600:02d} : {(s % 3600) // 60:02d} : {s % 60:02d}"

    # ------------------------------------------------------------------
    def on_paused(self):
        if self._is_paused:
            return
        self._is_paused = True
        if self._rec_active_start is not None:
            self._rec_base_elapsed += time.monotonic() - self._rec_active_start
            self._rec_active_start  = None
        self.status_label.text = "Recording paused"

    def on_resumed(self):
        if not self._is_paused:
            return
        self._is_paused        = False
        self._rec_active_start = time.monotonic()
        self.status_label.text = "Recording in progress"

    def on_audio_level(self, level: float):    del level
    def on_audio_segment(self, segment: int):  del segment

"""Recording screen — Frame 19 (`863:635`) + top-left status pill on `863:626`.

Scaled 1260×800 canvas; Frame 19 center + header status indicator.
"""

from __future__ import annotations

import logging
import time

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from config import ASSETS_DIR
from frame19_layout import (
    BACK_BTN,
    BG_RGB,
    ELLIPSE17,
    LEFT_VEC,
    RING_DARK,
    RING_GLOW,
    RING_GRADIENT,
    RIGHT_VEC,
    STATUS,
    STATUS_FS_RATIO,
    STATUS_PILL_PAUSED,
    STATUS_PILL_RECORDING,
    TIMER,
    TIMER_FS_RATIO,
    font_px,
    kivy_hints,
    scaled_canvas,
)
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

_FIGMA_DIR = ASSETS_DIR / "recording" / "figma"
_BG = (BG_RGB[0] / 255, BG_RGB[1] / 255, BG_RGB[2] / 255, 1.0)
_WHITE = (1.0, 1.0, 1.0, 1.0)
_MUTED = (182 / 255, 186 / 255, 242 / 255, 1.0)
_FONT_BOLD = "42dot-Sans"

# (asset filename, layout box) — back → front
_IMAGES: tuple[tuple[str, dict], ...] = (
    ("frame19_ellipse17.png", ELLIPSE17),
    ("frame19_ring_glow.png", RING_GLOW),
    ("frame19_ring_dark.png", RING_DARK),
    ("frame19_ring_gradient.png", RING_GRADIENT),
    ("frame19_vector_left.png", LEFT_VEC),
    ("frame19_vector_right.png", RIGHT_VEC),
)

_STATUS_PILLS: dict[bool, tuple[str, dict]] = {
    False: ("rec_status_recording.png", STATUS_PILL_RECORDING),
    True: ("rec_status_paused.png", STATUS_PILL_PAUSED),
}


def _png(name: str) -> str:
    p = _FIGMA_DIR / name
    return str(p) if p.is_file() else ""


class _ImgBtn(ButtonBehavior, Image):
    """Tappable PNG button (matches calendar screen pattern)."""


class RecordingScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.elapsed_seconds = 0
        self.timer_event = None
        self._is_paused = False
        self._rec_base_elapsed = 0.0
        self._rec_active_start = None
        self._root = None
        self._canvas = None
        self._back_btn = None
        self._status_pill = None
        self.timer_label = None
        self.status_label = None
        self._build_ui()

    def _build_ui(self):
        self._root = FloatLayout(size_hint=(1, 1))
        with self._root.canvas.before:
            Color(*_BG)
            self._bg = Rectangle(pos=self._root.pos, size=self._root.size)
        self._root.bind(
            pos=lambda w, _v: setattr(self._bg, "pos", w.pos),
            size=self._on_root_resize,
        )

        anchor = AnchorLayout(anchor_x="center", anchor_y="center", size_hint=(1, 1))
        self._root.add_widget(anchor)

        self._canvas = FloatLayout(size_hint=(None, None))
        anchor.add_widget(self._canvas)

        back_src = _png("btn_back.png")
        if back_src:
            self._back_btn = _ImgBtn(
                source=back_src,
                fit_mode="contain",
                allow_stretch=True,
                keep_ratio=True,
                **kivy_hints(BACK_BTN),
            )
            self._back_btn.bind(on_release=lambda *_: self.go_back())
            self._canvas.add_widget(self._back_btn)

        for filename, box in _IMAGES:
            src = _png(filename)
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
            font_name=_FONT_BOLD,
            bold=True,
            color=_WHITE,
            halign="center",
            valign="middle",
            **kivy_hints(TIMER),
        )
        self.timer_label.bind(size=self.timer_label.setter("text_size"))
        self._canvas.add_widget(self.timer_label)

        self.status_label = Label(
            text="Recording in progress",
            font_name=_FONT_BOLD,
            bold=True,
            color=_MUTED,
            halign="center",
            valign="middle",
            **kivy_hints(STATUS),
        )
        self.status_label.bind(size=self.status_label.setter("text_size"))
        self._canvas.add_widget(self.status_label)

        self._status_pill = self._make_status_pill(paused=False)
        if self._status_pill is not None:
            self._canvas.add_widget(self._status_pill)

        self.add_widget(self._root)
        Clock.schedule_once(lambda _dt: self._on_root_resize(self._root, self._root.size), 0)

    def _make_status_pill(self, *, paused: bool) -> Image | None:
        filename, box = _STATUS_PILLS[paused]
        src = _png(filename)
        if not src:
            return None
        return Image(
            source=src,
            allow_stretch=True,
            keep_ratio=True,
            fit_mode="contain",
            **kivy_hints(box),
        )

    def _set_status_pill(self, paused: bool) -> None:
        if self._canvas is None:
            return
        if self._status_pill is not None:
            self._canvas.remove_widget(self._status_pill)
            self._status_pill = None
        pill = self._make_status_pill(paused=paused)
        if pill is not None:
            self._canvas.add_widget(pill)
            self._status_pill = pill

    def _on_root_resize(self, _root, size):
        self._bg.size = size
        w, h = scaled_canvas(size[0], size[1])
        self._canvas.size = (w, h)
        self.timer_label.font_size = font_px(TIMER_FS_RATIO, h)
        self.status_label.font_size = font_px(STATUS_FS_RATIO, h)

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
        self._set_status_pill(paused=False)
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
        self._set_status_pill(paused=True)

    def on_resumed(self):
        if not self._is_paused:
            return
        self._is_paused = False
        self._rec_active_start = time.monotonic()
        self.status_label.text = "Recording in progress"
        self._set_status_pill(paused=False)

    def on_audio_level(self, level: float):
        del level

    def on_audio_segment(self, segment_num: int):
        del segment_num

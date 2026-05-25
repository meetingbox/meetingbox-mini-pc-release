"""Recording screen — Figma `863:626` (VelsLhL4YHeVRZSCEmCrGw).

Composes the screen from PNG assets exported from Figma + Kivy Labels for the
dynamic text (timer, start time, meeting title).  Layout lives in
``frame19_layout.py`` and matches the Figma absolute coordinates 1:1.

Lifecycle hooks (called from main.py): on_enter / on_leave, on_paused /
on_resumed, on_audio_level, on_audio_segment.
"""

from __future__ import annotations

import logging
import time

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from async_helper import run_async
from config import ASSETS_DIR, display_now
from frame19_layout import (
    BACK_BTN,
    BG_RGB,
    BTN_PAUSE,
    BTN_SETTINGS,
    COL_BLUE,
    COL_MUTED,
    COL_WHITE,
    LEFT_VEC,
    LISTENING_PILL,
    PARTICIPANTS_FS_RATIO,
    PARTICIPANTS_LABEL,
    PEOPLE_ICON,
    PROVIDER_FS_RATIO,
    PROVIDER_LABEL,
    REC_DOT,
    REC_LABEL,
    REC_LABEL_FS_RATIO,
    RIGHT_VEC,
    RING_DARK,
    RING_GLOW,
    RING_GRADIENT,
    STARTED_FS_RATIO,
    STARTED_LABEL,
    STATUS,
    STATUS_FS_RATIO,
    STOP_PILL,
    TIMER,
    TIMER_FS_RATIO,
    TITLE_FS_RATIO,
    TITLE_LABEL,
    VIDEO_ICON,
    font_px,
    kivy_hints,
    scaled_canvas,
)
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

_FIGMA = ASSETS_DIR / "recording" / "figma"
_BG = (BG_RGB[0] / 255, BG_RGB[1] / 255, BG_RGB[2] / 255, 1.0)
_FONT_BOLD = "42dot-Sans"

# Centre Frame 19 image layers (back → front)
_FRAME19_IMAGES: tuple[tuple[str, dict], ...] = (
    ("frame19_ring_glow.png", RING_GLOW),
    ("frame19_ring_dark.png", RING_DARK),
    ("frame19_ring_gradient.png", RING_GRADIENT),
    ("frame19_vector_left.png", LEFT_VEC),
    ("frame19_vector_right.png", RIGHT_VEC),
)


def _png(name: str) -> str:
    p = _FIGMA / name
    return str(p) if p.is_file() else ""


class _ImgBtn(ButtonBehavior, Image):
    """Tappable PNG button."""


class RecordingScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.elapsed_seconds = 0
        self.timer_event = None
        self._is_paused = False
        self._rec_base_elapsed = 0.0
        self._rec_active_start = None
        self._meeting_title = "Recording"
        self._participant_count = 0
        self._meeting_provider = ""
        self._build_ui()

    # ------------------------------------------------------------------ UI
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

        # Centre — Frame 19 graphic (back → front)
        for filename, box in _FRAME19_IMAGES:
            self._add_image(filename, box)

        # Timer + status caption (centred in Frame 19)
        self.timer_label = self._add_label(
            "00 : 00 : 00", TIMER, TIMER_FS_RATIO, COL_WHITE, bold=True,
        )
        self.status_label = self._add_label(
            "Recording in progress", STATUS, STATUS_FS_RATIO, COL_MUTED, bold=True,
        )

        # Top-left — back button (composite PNG)
        self._add_img_btn("btn_back.png", BACK_BTN, on_release=lambda *_: self.go_back())

        # Top-left — recording status group (red dot + Recording... + Started at ...)
        self._add_image("icon_rec_dot_red.png", REC_DOT)
        self.rec_label = self._add_label(
            "Recording...", REC_LABEL, REC_LABEL_FS_RATIO, COL_WHITE, bold=True, halign="left",
        )
        self.started_label = self._add_label(
            "Started at --:-- --", STARTED_LABEL, STARTED_FS_RATIO, COL_MUTED, halign="left",
        )

        # Top centre — meeting title group
        self._add_image("icon_people.png", PEOPLE_ICON)
        self.title_label = self._add_label(
            "Recording", TITLE_LABEL, TITLE_FS_RATIO, COL_WHITE, bold=True, halign="left",
        )
        self.participants_label = self._add_label(
            "", PARTICIPANTS_LABEL, PARTICIPANTS_FS_RATIO, COL_BLUE, halign="left",
        )
        self._add_image("icon_video.png", VIDEO_ICON)
        self.provider_label = self._add_label(
            "", PROVIDER_LABEL, PROVIDER_FS_RATIO, COL_MUTED, halign="left",
        )

        # Top-right — Listening pill (composite PNG)
        self._add_image("listening_pill.png", LISTENING_PILL)

        # Bottom row — pause | stop recording pill | settings
        self._add_img_btn("btn_pause.png", BTN_PAUSE, on_release=self._on_pause)
        self._add_img_btn("stop_recording_pill.png", STOP_PILL, on_release=self._on_stop)
        self._add_img_btn(
            "btn_settings.png",
            BTN_SETTINGS,
            on_release=lambda *_: self.goto("settings", transition="slide_left"),
        )

        self.add_widget(self._root)
        Clock.schedule_once(lambda _dt: self._on_root_resize(self._root, self._root.size), 0)

    # --------------------------------------------------------------- helpers
    def _add_image(self, filename: str, box: dict) -> Image | None:
        src = _png(filename)
        if not src:
            return None
        img = Image(
            source=src,
            allow_stretch=True,
            keep_ratio=True,
            fit_mode="contain",
            **kivy_hints(box),
        )
        self._canvas.add_widget(img)
        return img

    def _add_img_btn(self, filename: str, box: dict, *, on_release) -> _ImgBtn | None:
        src = _png(filename)
        if not src:
            return None
        btn = _ImgBtn(
            source=src,
            allow_stretch=True,
            keep_ratio=True,
            fit_mode="contain",
            **kivy_hints(box),
        )
        btn.bind(on_release=on_release)
        self._canvas.add_widget(btn)
        return btn

    def _add_label(
        self,
        text: str,
        box: dict,
        fs_ratio: float,
        color: tuple,
        *,
        bold: bool = False,
        halign: str = "center",
    ) -> Label:
        lbl = Label(
            text=text,
            font_name=_FONT_BOLD,
            bold=bold,
            color=color,
            halign=halign,
            valign="middle",
            **kivy_hints(box),
        )
        lbl.bind(size=lbl.setter("text_size"))
        lbl._fs_ratio = fs_ratio  # noqa: SLF001 — resize hook
        self._canvas.add_widget(lbl)
        return lbl

    def _on_root_resize(self, _root, size):
        self._bg.size = size
        w, h = scaled_canvas(size[0], size[1])
        self._canvas.size = (w, h)
        for lbl in (
            self.timer_label,
            self.status_label,
            self.rec_label,
            self.started_label,
            self.title_label,
            self.participants_label,
            self.provider_label,
        ):
            if lbl is not None:
                lbl.font_size = font_px(lbl._fs_ratio, h)  # noqa: SLF001

    # ------------------------------------------------------------- lifecycle
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
        self.rec_label.text = "Recording..."

        now = display_now()
        self.started_label.text = f"Started at {now.strftime('%I:%M %p').lstrip('0')}"

        self.title_label.text = "Recording"
        self.participants_label.text = ""
        self.provider_label.text = ""

        sid = getattr(self.app, "current_session_id", None)
        if sid:
            self._fetch_meeting_metadata(sid)

        self.timer_event = Clock.schedule_interval(self._tick_timer, 0.5)

    def on_leave(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

    # ---------------------------------------------------------------- timer
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

    # ------------------------------------------------------------ pause/stop
    def _on_pause(self, _inst):
        if self._is_paused:
            self.app.resume_recording()
        else:
            self.app.pause_recording()

    def _on_stop(self, _inst):
        logger.info("Stop recording pressed (duration: %s)", self._fmt_time(self.elapsed_seconds))
        self.app.stop_recording()

    def on_paused(self):
        if self._is_paused:
            return
        self._is_paused = True
        if self._rec_active_start is not None:
            self._rec_base_elapsed += time.monotonic() - self._rec_active_start
            self._rec_active_start = None
        self.rec_label.text = "Paused"
        self.status_label.text = "Recording paused"

    def on_resumed(self):
        if not self._is_paused:
            return
        self._is_paused = False
        self._rec_active_start = time.monotonic()
        self.rec_label.text = "Recording..."
        self.status_label.text = "Recording in progress"

    def on_audio_level(self, level: float):
        del level

    def on_audio_segment(self, segment_num: int):
        del segment_num

    # -------------------------------------------------------------- metadata
    def _fetch_meeting_metadata(self, meeting_id: str):
        async def _run():
            try:
                detail = await self.backend.get_meeting_detail(meeting_id)
            except Exception as exc:  # noqa: BLE001
                logger.debug("recording: meeting detail fetch failed: %s", exc)
                return
            title = (detail.get("title") or "Recording").strip() or "Recording"
            try:
                participants = int(
                    detail.get("participant_count") or detail.get("attendee_count") or 0
                )
            except (TypeError, ValueError):
                participants = 0
            provider = (
                (detail.get("source") or "")
                or (detail.get("calendar_source") or "")
                or ""
            ).strip()

            def _apply(_dt):
                self._meeting_title = title
                self._participant_count = participants
                self._meeting_provider = provider
                self.title_label.text = title
                if participants:
                    self.participants_label.text = (
                        f"{participants} Participants" if participants != 1 else "1 Participant"
                    )
                else:
                    self.participants_label.text = ""
                self.provider_label.text = provider

            Clock.schedule_once(_apply, 0)

        run_async(_run())

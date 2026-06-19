"""
VoiceControlBar — Global root-level overlay for voice session controls.

Shown whenever a realtime voice session is active; hidden at idle and on
recording/processing screens (where the voice session is suspended).

Layout (left → right):
    [exit pill — Frame 22.png]  [Listening / Thinking / Talking pill + waveform]

The exit pill exits the current voice session and returns the user to the home
screen.  Tapping it triggers a subtle scale-down press animation.

Added to ``root_layout`` in main.py (above the ScreenManager, below the
QuickPanel) so it floats on every screen.  Touch events pass through to the
screen below except when the user taps directly on the pill container.
"""

from __future__ import annotations

import logging
import math

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import (
    Color, Ellipse, PopMatrix, PushMatrix, RoundedRectangle, Scale,
)
from kivy.properties import NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from config import ASSETS_DIR, DISPLAY_WIDTH, DISPLAY_HEIGHT

logger = logging.getLogger(__name__)

# ── Design constants (Figma 1260×800 coordinate space) ───────────────────────
_FW, _FH = 1260.0, 800.0

# Voice pill visual constants (matching home.py / _VoiceStatePill)
_PILL_BG = (0.980, 0.980, 0.980, 1.0)   # #FAFAFA
_PURPLE  = (0.427, 0.282, 0.800, 1.0)   # #6D48CC
_TEXT    = (0.227, 0.231, 0.239, 1.0)   # #3A3B3D
_SHADOW  = (0.463, 0.506, 0.498, 0.18)
_FONT_SB = "42dot-SB"

# Screens where the bar must stay hidden (voice session suspended)
_HIDDEN_SCREENS: frozenset[str] = frozenset({"recording", "processing"})

# Figma coordinates of the original voice pill (home.py)
_PILL_X_FIG  = 867.0   # left edge of original voice pill in Figma px
_PILL_Y_FIG  = 17.0    # top edge in Figma px (from the Figma top)
_PILL_W_FIG  = 222.0
_PILL_H_FIG  = 47.0
_PILL_GAP    = 8.0     # gap between exit pill and voice pill (Figma px)

# Image natural size  (236 × 61 px RGBA — measured at asset-copy time)
_IMG_W, _IMG_H = 236.0, 61.0


def _scale() -> float:
    """Uniform Figma→display scale factor."""
    return min(DISPLAY_WIDTH / _FW, DISPLAY_HEIGHT / _FH)


def _ff(fs: float) -> int:
    return max(6, round(fs * _scale()))


# ─────────────────────────────────────────────────────────────────────────────
# Animated 7-bar waveform  (self-contained copy matching home.py proportions)
# ─────────────────────────────────────────────────────────────────────────────
class _Waveform(Widget):
    _BAR_DATA = [
        (7.185,  8.625),
        (12.935, 14.375),
        (18.685, 22.999),
        (24.435, 34.499),
        (30.185, 22.999),
        (35.935, 14.375),
        (41.685, 8.625),
    ]
    _BAR_W  = 2.875
    _VB     = 46.0
    _CY_VB  = 23.0
    _PHASES = [3.0, 2.2, 1.4, 0.0, 1.4, 2.2, 3.0]

    def __init__(self, **kw):
        super().__init__(**kw)
        self._bar_cxy: list = []
        self._s = 1.0
        self._bw = 1.0
        with self.canvas:
            self._ci = Color(*_TEXT)
            self._bars = [
                RoundedRectangle(pos=(0, 0), size=(1, 1), radius=[0.5])
                for _ in self._BAR_DATA
            ]
        self.bind(pos=self._rebuild, size=self._rebuild)
        Clock.schedule_once(self._rebuild, 0)

    def _rebuild(self, *_):
        w, h = self.size
        px, py = self.pos
        if w <= 0 or h <= 0:
            return
        s  = min(w / self._VB, h / self._VB)
        ox = px + (w - self._VB * s) / 2
        oy = py + (h - self._VB * s) / 2
        self._s  = s
        self._bw = self._BAR_W * s
        self._bar_cxy = [(ox + cx * s, oy + self._CY_VB * s) for cx, _ in self._BAR_DATA]
        r = self._bw / 2
        for i, bar in enumerate(self._bars):
            cx, cy = self._bar_cxy[i]
            bh = self._BAR_DATA[i][1] * s
            bar.pos    = (cx - self._bw / 2, cy - bh / 2)
            bar.size   = (self._bw, bh)
            bar.radius = [r]

    def tick(self, t: float, amp: float) -> None:
        if not self._bars or not self._bar_cxy:
            return
        s, bw = self._s, self._bw
        r   = bw / 2
        amp = max(0.0, min(1.0, amp))
        for i, bar in enumerate(self._bars):
            cx, cy = self._bar_cxy[i]
            bh  = self._BAR_DATA[i][1] * s
            ph  = self._PHASES[i]
            idle  = 1.0 + 0.10 * math.sin(t * 3.0 + ph)
            spd   = 5.0 + amp * 12.0
            voice = amp * 1.2 * abs(math.sin(t * spd + ph))
            h_px  = bh * idle * (1.0 + voice)
            bar.pos    = (cx - bw / 2, cy - h_px / 2)
            bar.size   = (bw, h_px)
            bar.radius = [r]


# ─────────────────────────────────────────────────────────────────────────────
# Voice-state pill  (white capsule with dot + state text + waveform)
# ─────────────────────────────────────────────────────────────────────────────
class _VoicePill(FloatLayout):
    _PW, _PH = 222.0, 47.0

    def __init__(self, **kw):
        super().__init__(**kw)
        PW, PH = self._PW, self._PH
        with self.canvas.before:
            Color(*_SHADOW)
            self._shad = RoundedRectangle(pos=(0, 0), size=(1, 1), radius=[24])
            Color(*_PILL_BG)
            self._bg   = RoundedRectangle(pos=(0, 0), size=(1, 1), radius=[24])
        self.bind(pos=self._draw_bg, size=self._draw_bg)

        dot = Widget(size_hint=(17 / PW, 17 / PH), pos_hint={"x": 13 / PW, "y": 15 / PH})
        with dot.canvas:
            Color(*_PURPLE)
            _dot_ell = Ellipse(pos=dot.pos, size=dot.size)
        dot.bind(
            pos=lambda w, *_: setattr(_dot_ell, "pos",  w.pos),
            size=lambda w, *_: setattr(_dot_ell, "size", w.size),
        )
        self.add_widget(dot)

        self._lbl = Label(
            text="Listening",
            font_name=_FONT_SB,
            font_size=_ff(24.24),
            color=_TEXT,
            halign="left",
            valign="middle",
            size_hint=(102 / PW, 29 / PH),
            pos_hint={"x": 42 / PW, "y": 9 / PH},
        )
        self._lbl.bind(size=self._lbl.setter("text_size"))
        self.add_widget(self._lbl)

        self._wave = _Waveform(
            size_hint=(39 / PW, 29 / PH),
            pos_hint={"x": 170 / PW, "y": 9 / PH},
        )
        self.add_widget(self._wave)

    def _draw_bg(self, *_):
        x, y = self.pos
        w, h = self.size
        if w <= 0 or h <= 0:
            return
        r = min(w, h) / 2
        self._shad.pos    = (x + 1, y - 4)
        self._shad.size   = (w + 2, h + 5)
        self._shad.radius = [r + 2]
        self._bg.pos    = (x, y)
        self._bg.size   = (w, h)
        self._bg.radius = [r]

    def set_state(self, state: str) -> None:
        text_map = {
            "listening": "Listening",
            "thinking":  "Thinking",
            "speaking":  "Talking",
        }
        self._lbl.text = text_map.get(state.lower(), "Listening")

    def tick(self, t: float, amp: float) -> None:
        self._wave.tick(t, amp)


# ─────────────────────────────────────────────────────────────────────────────
# Exit pill  (Frame 22.png rendered as-is, with a press scale animation)
# ─────────────────────────────────────────────────────────────────────────────
class _ExitPill(ButtonBehavior, Widget):
    """Tappable image pill; tapping exits the voice session."""

    btn_scale = NumericProperty(1.0)

    def __init__(self, source: str, on_tap=None, **kw):
        super().__init__(**kw)
        self._on_tap = on_tap
        self._tex = None
        try:
            img = CoreImage(source)
            self._tex = img.texture
        except Exception as exc:
            logger.warning("_ExitPill: could not load %s: %s", source, exc)

        with self.canvas:
            PushMatrix()
            self._sc = Scale(1.0, 1.0, 1.0)
            Color(1, 1, 1, 1)
            from kivy.graphics import Rectangle
            self._rect = Rectangle(pos=self.pos, size=self.size, texture=self._tex)
            PopMatrix()

        self.bind(pos=self._sync, size=self._sync, btn_scale=self._sync_scale)

    def _sync_scale(self, *_):
        cx, cy = self.center
        self._sc.origin = (cx, cy, 0)
        self._sc.x = self.btn_scale
        self._sc.y = self.btn_scale

    def _sync(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size
        self._sync_scale()

    def on_press(self):
        Animation.cancel_all(self, "btn_scale")
        Animation(btn_scale=0.88, duration=0.08).start(self)

    def on_release(self):
        Animation.cancel_all(self, "btn_scale")
        Animation(btn_scale=1.0, duration=0.18, t="out_back").start(self)
        if self._on_tap:
            self._on_tap()


# ─────────────────────────────────────────────────────────────────────────────
# VoiceControlBar  (the public overlay widget)
# ─────────────────────────────────────────────────────────────────────────────
class VoiceControlBar(FloatLayout):
    """Full-screen FloatLayout overlay; only the pill row is interactive.

    Usage in main.py::

        self._voice_control_bar = VoiceControlBar(app=self)
        self.root_layout.add_widget(self._voice_control_bar)

        # When voice state changes:
        self._voice_control_bar.notify_state(new_state)

        # When screen changes:
        self._voice_control_bar.notify_screen(screen_name)

        # When audio amplitude arrives:
        self._voice_control_bar.update_amplitude(amp)
    """

    def __init__(self, app=None, **kw):
        super().__init__(**kw)
        self._app      = app
        self._visible  = False
        self._state    = "idle"
        self._screen   = ""
        self._t        = 0.0
        self._amp      = 0.0
        self._anim_ev  = None
        self.opacity   = 0.0

        s = _scale()

        # ── Voice state pill ────────────────────────────────────────────────
        # Keep both pills at the same rendered height.
        common_h = round(_IMG_H * s)
        voice_h = common_h
        voice_w = round((_PILL_W_FIG / _PILL_H_FIG) * voice_h)
        self._voice_pill = _VoicePill(
            size_hint=(None, None),
            size=(voice_w, voice_h),
        )

        # ── Exit image pill ─────────────────────────────────────────────────
        # Render the image at the same height as the voice pill, preserving aspect.
        img_h  = common_h
        img_w  = round(img_h * (_IMG_W / _IMG_H))
        _src   = str(ASSETS_DIR / "frame22_exit.png")
        self._exit_pill = _ExitPill(
            source=_src,
            on_tap=self._on_exit_tapped,
            size_hint=(None, None),
            size=(img_w, img_h),
        )

        # ── Row container ───────────────────────────────────────────────────
        gap = round(_PILL_GAP * s)
        self._row = BoxLayout(
            orientation="horizontal",
            spacing=gap,
            size_hint=(None, None),
            size=(img_w + gap + voice_w, voice_h),
        )
        self._row.add_widget(self._exit_pill)
        self._row.add_widget(self._voice_pill)
        self.add_widget(self._row)

        # Position the row after the layout pass so Window size is known.
        Clock.schedule_once(self._place_row, 0)

    # ── Positioning ──────────────────────────────────────────────────────────

    def _place_row(self, *_):
        """Pin the row's right edge to the same x as the home-screen voice pill's right edge."""
        s = _scale()
        # Right edge of the original voice pill in actual display pixels.
        right_px = round((_PILL_X_FIG + _PILL_W_FIG) * s)
        # Top edge → Kivy y-from-bottom.
        top_y_px = DISPLAY_HEIGHT - round(_PILL_Y_FIG * s)
        row_h = self._row.height
        self._row.x = right_px - self._row.width
        self._row.y = top_y_px - row_h

    # ── Touch pass-through ───────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if self._visible and self._row.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        return False

    def on_touch_move(self, touch):
        if self._visible and self._row.collide_point(*touch.pos):
            return super().on_touch_move(touch)
        return False

    def on_touch_up(self, touch):
        if self._visible and self._row.collide_point(*touch.pos):
            return super().on_touch_up(touch)
        return False

    # ── Public API ───────────────────────────────────────────────────────────

    def notify_state(self, state: str) -> None:
        """Called from main.py whenever the realtime voice runtime state changes."""
        self._state = (state or "idle").strip().lower()
        self._refresh()
        self._suppress_current_screen_local_pill()
        if self._visible and self._state not in ("idle", ""):
            self._voice_pill.set_state(self._state)

    def notify_screen(self, screen_name: str) -> None:
        """Called from main.py whenever the ScreenManager switches screens."""
        self._screen = screen_name or ""
        self._refresh()
        self._suppress_current_screen_local_pill()

    def update_amplitude(self, amp: float) -> None:
        """Receive audio amplitude (0.0–1.0) from the voice pipeline."""
        self._amp = max(0.0, min(1.0, amp))

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _refresh(self) -> None:
        active       = self._state not in ("idle", "")
        hidden_screen = self._screen in _HIDDEN_SCREENS
        should_show  = active and not hidden_screen

        if should_show and not self._visible:
            self._show()
        elif not should_show and self._visible:
            self._hide()

    def _show(self) -> None:
        self._visible = True
        Animation.cancel_all(self, "opacity")
        Animation(opacity=1.0, duration=0.25).start(self)
        self._start_waveform()

    def _hide(self) -> None:
        self._visible = False
        Animation.cancel_all(self, "opacity")
        Animation(opacity=0.0, duration=0.20).start(self)
        self._stop_waveform()

    def _start_waveform(self) -> None:
        if self._anim_ev is None:
            self._anim_ev = Clock.schedule_interval(self._tick, 1.0 / 30.0)

    def _stop_waveform(self) -> None:
        if self._anim_ev is not None:
            self._anim_ev.cancel()
            self._anim_ev = None

    def _tick(self, dt: float) -> None:
        self._t += dt
        self._voice_pill.tick(self._t, self._amp)

    def _on_exit_tapped(self) -> None:
        app = self._app
        if app is None:
            return
        try:
            app._end_realtime_voice_session()
        except Exception:
            logger.debug("VoiceControlBar: end session error", exc_info=True)
        try:
            app.goto_screen("home")
        except Exception:
            logger.debug("VoiceControlBar: goto_screen error", exc_info=True)

    # ── Public hit-test helper for top-edge controls ────────────────────────

    def is_touch_on_controls(self, x: float, y: float) -> bool:
        """Return True when a touch is directly on the visible pill row."""
        return self._visible and self._row.collide_point(x, y)

    # ── Local pill suppression (avoid double-render with legacy per-screen UI) ──

    def _suppress_current_screen_local_pill(self) -> None:
        """Hide any screen-local `_voice_pill` while this global bar is active."""
        if not self._visible:
            return
        app = self._app
        if app is None:
            return
        sm = getattr(app, "screen_manager", None)
        if sm is None:
            return
        try:
            scr = sm.get_screen(sm.current)
        except Exception:
            return
        pill = getattr(scr, "_voice_pill", None)
        if pill is None:
            return
        try:
            pill.opacity = 0.0
        except Exception:
            logger.debug("VoiceControlBar: failed to hide local voice pill", exc_info=True)

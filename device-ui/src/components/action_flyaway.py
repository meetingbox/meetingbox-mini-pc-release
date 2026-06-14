"""Action fly-away overlay.

Reproduces the "send / save-as-draft / discard" card animations (see the
reference GIFs): when the user commits an action on the email-draft,
calendar-event or task-creation card, the card itself shrinks, tilts and flies
off the bottom of the screen while fading out — revealing whatever screen we
navigate to behind it (the live transcription page for email/discard, or the
Tasks / Calendar screen showing the freshly-added item).

The animation is reproduced procedurally on a snapshot of the *real* card
(captured with ``export_as_image``) so it always shows the actual on-screen
content rather than a canned recording.

Public API
----------
capture_card(screen, card) -> (texture, (x, y, w, h)) | None
    Snapshot the card region of *screen* in window coordinates. Call this while
    the card is still visible (i.e. before navigating away).

ActionFlyAway.play(texture, rect, action, on_done=None)
    Fly the captured snapshot off-screen with the motion for *action*
    ("send" | "save" | "discard").
"""

from __future__ import annotations

import logging

from kivy.animation import Animation
from kivy.core.window import Window
from kivy.graphics import PopMatrix, PushMatrix, Rotate, Scale
from kivy.properties import NumericProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image

logger = logging.getLogger(__name__)


def capture_card(screen, card):
    """Return ``(texture, (x, y, w, h))`` for *card* rendered inside *screen*.

    The rectangle is in window coordinates so the snapshot can be replayed by a
    root-level overlay. Returns ``None`` if anything goes wrong (callers then
    simply skip the flourish and navigate directly).
    """
    if screen is None or card is None:
        return None
    try:
        core_img = screen.export_as_image()
        tex = getattr(core_img, "texture", None)
        if tex is None:
            return None
        x, y = card.to_window(card.x, card.y)
        w, h = int(round(card.width)), int(round(card.height))
        if w <= 0 or h <= 0:
            return None
        region = tex.get_region(int(round(x)), int(round(y)), w, h)
        return region, (x, y, w, h)
    except Exception:
        logger.debug("capture_card failed", exc_info=True)
        return None


class _FlyCard(Image):
    """An image of the captured card that can be scaled + rotated about its
    centre via animatable properties."""

    fly_scale = NumericProperty(1.0)
    fly_angle = NumericProperty(0.0)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.allow_stretch = True
        self.keep_ratio = False
        with self.canvas.before:
            PushMatrix()
            self._rot = Rotate(angle=0, origin=self.center)
            self._scale = Scale(x=1.0, y=1.0, z=1.0, origin=self.center)
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=self._apply_tx, size=self._apply_tx,
                  fly_scale=self._apply_tx, fly_angle=self._apply_tx)

    def _apply_tx(self, *_):
        cx, cy = self.center
        self._rot.origin = (cx, cy)
        self._rot.angle = self.fly_angle
        self._scale.origin = (cx, cy)
        self._scale.x = self.fly_scale
        self._scale.y = self.fly_scale


class ActionFlyAway(FloatLayout):
    """Root-level transient overlay that plays the card fly-away animation."""

    # dx/dy are fractions of the window size (the card flies down & off-screen);
    # angle is the final tilt in degrees; scale is the final shrink factor.
    _PARAMS = {
        "send":    {"dx":  0.18, "dy": -0.95, "angle": -15.0, "scale": 0.32, "dur": 0.62, "t": "in_cubic"},
        "save":    {"dx":  0.00, "dy": -0.95, "angle":   5.0, "scale": 0.30, "dur": 0.66, "t": "in_cubic"},
        "discard": {"dx": -0.16, "dy": -0.95, "angle":  18.0, "scale": 0.22, "dur": 0.56, "t": "in_cubic"},
    }

    def __init__(self, **kw):
        super().__init__(size_hint=(1, 1), **kw)
        self.opacity = 1.0
        self._fly: _FlyCard | None = None

    def play(self, texture, rect, action: str, on_done=None) -> None:
        """Fly *texture* (captured at *rect*) off-screen for *action*."""
        if texture is None or rect is None:
            self._invoke(on_done)
            return
        # A new animation supersedes any in-flight one.
        self._cleanup()
        params = self._PARAMS.get(action, self._PARAMS["send"])
        try:
            x, y, w, h = rect
            fly = _FlyCard(texture=texture, size_hint=(None, None),
                           size=(w, h), pos=(x, y))
            self.add_widget(fly)
            self._fly = fly

            win_w = Window.width or 1
            win_h = Window.height or 1
            target_x = x + params["dx"] * win_w
            target_y = y + params["dy"] * win_h

            anim = Animation(
                x=target_x, y=target_y,
                fly_scale=params["scale"], fly_angle=params["angle"],
                opacity=0.0, duration=params["dur"], t=params["t"],
            )
            anim.bind(on_complete=lambda *_: self._finish(on_done))
            anim.start(fly)
        except Exception:
            logger.debug("ActionFlyAway.play failed", exc_info=True)
            self._finish(on_done)

    # ── internals ────────────────────────────────────────────────────────────

    def _finish(self, on_done) -> None:
        self._cleanup()
        self._invoke(on_done)

    def _cleanup(self) -> None:
        if self._fly is not None:
            try:
                Animation.cancel_all(self._fly)
                self.remove_widget(self._fly)
            except Exception:
                pass
        self._fly = None

    @staticmethod
    def _invoke(cb) -> None:
        if cb:
            try:
                cb()
            except Exception:
                logger.debug("flyaway on_done failed", exc_info=True)

    # Transient visual only — never intercept touches meant for the screen below.
    def on_touch_down(self, touch):
        return False

    def on_touch_move(self, touch):
        return False

    def on_touch_up(self, touch):
        return False

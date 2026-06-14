"""Action fly-away overlay.

Reproduces the "send / save-as-draft / discard" card animations: when the user
commits an action on the email-draft, calendar-event or task-creation card, a
snapshot of the *real* card (so all of its content is preserved exactly) glides
smoothly off toward a target while shrinking and dissolving — revealing the
screen we navigate to behind it (the live transcription page for email/discard,
or the Tasks / Calendar screen showing the freshly-added item).

The motion is deliberately macOS-like: a single ease-in-out glide (no rotation,
no snapping), the card stays fully opaque while it travels and only dissolves at
the very tail, so the eye can follow it the whole way.

Public API
----------
capture_card(screen, card) -> (texture, (x, y, w, h)) | None
    Snapshot the card region of *screen* in window coordinates. Call this while
    the card is still visible (i.e. before navigating away).

ActionFlyAway.play(texture, rect, action, on_done=None)
    Glide the captured snapshot toward the target for *action*
    ("send" | "save" | "discard").
"""

from __future__ import annotations

import logging

from kivy.animation import Animation
from kivy.core.window import Window
from kivy.graphics import PopMatrix, PushMatrix, Scale
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
    """An image of the captured card that scales about its centre via an
    animatable property. No rotation — the card stays upright the whole time."""

    fly_scale = NumericProperty(1.0)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.allow_stretch = True
        self.keep_ratio = False
        with self.canvas.before:
            PushMatrix()
            self._scale = Scale(x=1.0, y=1.0, z=1.0, origin=self.center)
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=self._apply_tx, size=self._apply_tx, fly_scale=self._apply_tx)

    def _apply_tx(self, *_):
        cx, cy = self.center
        self._scale.origin = (cx, cy)
        self._scale.x = self.fly_scale
        self._scale.y = self.fly_scale


class ActionFlyAway(FloatLayout):
    """Root-level transient overlay that plays the card fly-away animation.

    Per action we glide the card's *centre* to a target point (expressed as a
    fraction of the window) while shrinking it. ``send`` heads to the top-right
    corner; ``save`` files down toward the bottom; ``discard`` collapses gently
    in place.
    """

    _PARAMS = {
        "send":    {"cx": 0.99, "cy": 0.97, "scale": 0.10, "dur": 1.30},
        "save":    {"cx": 0.50, "cy": 0.02, "scale": 0.12, "dur": 1.35},
        "discard": {"cx": 0.50, "cy": 0.46, "scale": 0.05, "dur": 1.20},
    }
    # Apple's default UIView curve is ease-in-out; in_out_cubic is the closest
    # smooth, symmetric match and reads as calm/premium rather than snappy.
    _EASE = "in_out_cubic"

    def __init__(self, **kw):
        super().__init__(size_hint=(1, 1), **kw)
        self.opacity = 1.0
        self._fly: _FlyCard | None = None

    def play(self, texture, rect, action: str, on_done=None) -> None:
        """Glide *texture* (captured at *rect*) toward the target for *action*."""
        if texture is None or rect is None:
            self._invoke(on_done)
            return
        # A new animation supersedes any in-flight one.
        self._cleanup()
        cfg = self._PARAMS.get(action, self._PARAMS["send"])
        try:
            x, y, w, h = rect
            fly = _FlyCard(texture=texture, size_hint=(None, None),
                           size=(w, h), pos=(x, y))
            self.add_widget(fly)
            self._fly = fly

            win_w = Window.width or 1
            win_h = Window.height or 1
            # Move the card's CENTRE to the target point; convert to bottom-left
            # pos (size is fixed; the visual shrink happens via fly_scale about
            # the centre, so the centre is what the eye tracks).
            target_cx = cfg["cx"] * win_w
            target_cy = cfg["cy"] * win_h
            target_x = target_cx - w / 2.0
            target_y = target_cy - h / 2.0
            dur = cfg["dur"]

            # Glide + shrink, perfectly synced on one ease-in-out curve.
            glide = Animation(
                x=target_x, y=target_y, fly_scale=cfg["scale"],
                duration=dur, t=self._EASE,
            )
            glide.bind(on_complete=lambda *_: self._finish(on_done))
            glide.start(fly)

            # Stay fully opaque for most of the journey, then dissolve softly so
            # the card never "blinks" out — the fade only covers the final ~35%.
            fade = (Animation(opacity=1.0, duration=dur * 0.62)
                    + Animation(opacity=0.0, duration=dur * 0.38, t="in_out_sine"))
            fade.start(fly)
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

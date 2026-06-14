"""Genie action animation.

When the user commits an action on the email-draft / calendar-event / task card
we play a macOS-style *genie* effect: a snapshot of the real card is mapped onto
a deforming triangle mesh and "sucked" toward a target point (the top-right
corner for Send/Confirm, or the relevant CTA button for Save / Discard) along a
curved, phased funnel — the edge nearest the target leads, the body follows and
tapers into a neck, then dissolves.

The motion is procedural (a snapshot warped on a ``Mesh``) so the card's content
is preserved exactly and bends smoothly along the genie path with no jerks.

Public API
----------
capture_card(screen, card) -> (texture, (x,y,w,h), (umin,vmin,umax,vmax)) | None
    Snapshot *card* (rendered inside *screen*) while it is still visible.

GenieOverlay.play(texture, rect, uv, target, on_done=None, duration=...)
    Run the genie warp of the snapshot toward *target* (window coords).
"""

from __future__ import annotations

import logging

from kivy.animation import Animation
from kivy.graphics import Color, Mesh
from kivy.properties import NumericProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget

logger = logging.getLogger(__name__)

# Mesh resolution. More rows (NY, along the flow) → smoother funnel curve; a
# handful of columns (NX, across) is enough for the side taper.
_NX = 14
_NY = 30
# How much the rows lag behind one another (the "flow"). Higher = longer tail.
_SPREAD = 0.6


def capture_card(screen, card):
    """Return ``(texture, (x,y,w,h), (umin,vmin,umax,vmax))`` for *card*.

    Geometry is in window coordinates; the uv bounds locate the card inside the
    full-screen snapshot texture so the mesh can sample just the card. Returns
    ``None`` on failure (caller then skips the flourish)."""
    if screen is None or card is None:
        return None
    try:
        core_img = screen.export_as_image()
        tex = getattr(core_img, "texture", None)
        if tex is None:
            return None
        tw, th = tex.size
        if not tw or not th:
            return None
        x, y = card.to_window(card.x, card.y)
        w, h = float(card.width), float(card.height)
        if w <= 0 or h <= 0:
            return None
        umin = max(0.0, min(1.0, x / tw))
        umax = max(0.0, min(1.0, (x + w) / tw))
        vmin = max(0.0, min(1.0, y / th))
        vmax = max(0.0, min(1.0, (y + h) / th))
        return tex, (x, y, w, h), (umin, vmin, umax, vmax)
    except Exception:
        logger.debug("capture_card failed", exc_info=True)
        return None


def _smoothstep(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


class _GenieMesh(Widget):
    """A full-window widget that draws the card snapshot on a mesh and warps it
    toward a target as ``progress`` animates 0 → 1."""

    progress = NumericProperty(0.0)

    def __init__(self, texture, rect, uv, target, **kw):
        super().__init__(**kw)
        self._tex = texture
        self._rect = rect            # (x, y, w, h) window coords
        self._uv = uv                # (umin, vmin, umax, vmax)
        self._target = target        # (tx, ty) window coords
        x0, y0, w, h = rect
        tx, ty = target
        # Whichever edge of the card is nearest the target leads the genie.
        self._target_above = ty >= (y0 + h / 2.0)

        self._verts: list[float] = [0.0] * ((_NX + 1) * (_NY + 1) * 4)
        self._indices: list[int] = []
        self._mesh: Mesh | None = None
        self._build()
        self.bind(progress=lambda *_: self._update())

    def _tex_coords(self):
        """The texture's 4 corner texcoords (BL, BR, TR, TL), each (u, v).

        Falls back to an upright unit quad if the texture doesn't expose them."""
        tc = getattr(self._tex, "tex_coords", None)
        if tc is not None and len(tc) >= 8:
            return ((tc[0], tc[1]), (tc[2], tc[3]), (tc[4], tc[5]), (tc[6], tc[7]))
        return ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))

    @staticmethod
    def _interp_uv(tc, gx: float, gy: float):
        """Bilinearly interpolate the texcoord at screen fraction (gx, gy),
        gy measured from the bottom. ``tc`` = corners (BL, BR, TR, TL)."""
        (blu, blv), (bru, brv), (tru, trv), (tlu, tlv) = tc
        bu = blu + (bru - blu) * gx
        bv = blv + (brv - blv) * gx
        tu = tlu + (tru - tlu) * gx
        tv = tlv + (trv - tlv) * gx
        return bu + (tu - bu) * gy, bv + (tv - bv) * gy

    def _build(self) -> None:
        umin, vmin, umax, vmax = self._uv
        # A texture produced by ``export_as_image`` is rendered through an Fbo and
        # is therefore vertically flipped relative to a plain texture. Its true
        # orientation (plus any atlas offset) is baked into ``texture.tex_coords``;
        # ignoring it and using a naive [0,1] bottom-up mapping paints the snapshot
        # upside-down for the very first frame — the "widget replaced with
        # something" pop. So we sample the actual tex_coords corners and bilinearly
        # interpolate to get each vertex's true texcoord, which is flip-safe.
        tc = self._tex_coords()
        for j in range(_NY + 1):
            v = j / _NY
            gy = vmin + v * (vmax - vmin)
            for i in range(_NX + 1):
                u = i / _NX
                gx = umin + u * (umax - umin)
                tu, tv = self._interp_uv(tc, gx, gy)
                k = (j * (_NX + 1) + i) * 4
                # texcoords are constant; positions are recomputed per frame
                self._verts[k + 2] = tu
                self._verts[k + 3] = tv
        for j in range(_NY):
            for i in range(_NX):
                a = j * (_NX + 1) + i
                b = a + 1
                c = a + (_NX + 1)
                d = c + 1
                self._indices += [a, b, c, b, d, c]
        self._compute(0.0)
        with self.canvas:
            Color(1, 1, 1, 1)
            self._mesh = Mesh(
                vertices=self._verts,
                indices=self._indices,
                mode="triangles",
                texture=self._tex,
            )

    def _compute(self, s: float) -> None:
        x0, y0, w, h = self._rect
        tx, ty = self._target
        above = self._target_above
        verts = self._verts
        for j in range(_NY + 1):
            v = j / _NY
            lead = v if above else (1.0 - v)
            oy = y0 + v * h
            for i in range(_NX + 1):
                u = i / _NX
                ox = x0 + u * w
                # Phased progress: rows near the target start (and finish) first,
                # producing the flowing tail and the tapering neck.
                t = s * (1.0 + _SPREAD) - (1.0 - lead) * _SPREAD
                t = _smoothstep(t)
                omt = 1.0 - t
                # Quadratic Bézier with control point (ox, ty): the card first
                # moves along its lead axis toward the target's row, then slides
                # across to the target's column — the classic genie funnel curve.
                px = ox * (1.0 - t * t) + tx * (t * t)
                py = oy * omt * omt + ty * (1.0 - omt * omt)
                k = (j * (_NX + 1) + i) * 4
                verts[k] = px
                verts[k + 1] = py
        if self._mesh is not None:
            self._mesh.vertices = verts

    def _update(self) -> None:
        s = self.progress
        self._compute(s)
        # Stay solid while it travels; dissolve only over the last fifth.
        if s <= 0.8:
            self.opacity = 1.0
        else:
            self.opacity = max(0.0, 1.0 - (s - 0.8) / 0.2)


class GenieOverlay(FloatLayout):
    """Root-level transient overlay that plays the genie warp."""

    def __init__(self, **kw):
        super().__init__(size_hint=(1, 1), **kw)
        self.opacity = 1.0
        self._mesh_w: _GenieMesh | None = None

    def play(self, texture, rect, uv, target, on_done=None, duration: float = 1.0) -> None:
        if texture is None or rect is None or target is None:
            self._invoke(on_done)
            return
        self._cleanup()
        try:
            mesh = _GenieMesh(texture, rect, uv, target,
                              size_hint=(None, None), pos=(0, 0))
            self.add_widget(mesh)
            self._mesh_w = mesh
            # Ease-in-out so it starts gently, flows, and settles — no snap.
            anim = Animation(progress=1.0, duration=duration, t="in_out_cubic")
            anim.bind(on_complete=lambda *_: self._finish(on_done))
            anim.start(mesh)
        except Exception:
            logger.debug("GenieOverlay.play failed", exc_info=True)
            self._finish(on_done)

    # ── internals ────────────────────────────────────────────────────────────

    def _finish(self, on_done) -> None:
        self._cleanup()
        self._invoke(on_done)

    def _cleanup(self) -> None:
        if self._mesh_w is not None:
            try:
                Animation.cancel_all(self._mesh_w)
                self.remove_widget(self._mesh_w)
            except Exception:
                pass
        self._mesh_w = None

    @staticmethod
    def _invoke(cb) -> None:
        if cb:
            try:
                cb()
            except Exception:
                logger.debug("genie on_done failed", exc_info=True)

    # Transient visual only — never intercept touches.
    def on_touch_down(self, touch):
        return False

    def on_touch_move(self, touch):
        return False

    def on_touch_up(self, touch):
        return False

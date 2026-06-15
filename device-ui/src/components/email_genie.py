"""Apple-style Genie animation for the Email Compose widget.

A premium, self-contained transition for the email-draft screen only (calendar /
task screens keep their own ``action_flyaway`` minimize). It reproduces the macOS
window-minimize *genie* feel using a real snapshot warped on a deforming
triangle ``Mesh`` — content is masked by the deformation rather than naively
scaled — plus iOS-style spring press feedback and a natively-drawn completion
state.

Interaction timeline (driven by :func:`play_email_genie`):

    1. CTA press feedback     spring scale → 0.94 → 1.0          (~210 ms)
    2. Widget lock            disable CTAs, compose opacity 0.97  (80 ms)
    3. Genie warp             3-stage mesh deformation toward the
                              destination point                  (550 ms)
         A · initial pull     120 ms   width 100→92 %, move begins
         B · organic squeeze  220 ms   width 92→40 %, height →75 %
         C · final funnel     210 ms   width 40→8 %, height →8 %, fade
    4. Completion             natively-drawn confirmation         (~850 ms)
         SEND  → checkmark "Sent"      top-right
         SAVE  → "Draft Saved"         at the Save CTA
         DISCARD → clean, no flourish

The first warp frame is pixel-identical to the resting card (identity
transform), and the live card is hidden on the same frame the mesh appears, so
there is no snapshot "pop" — the hand-off is seamless.

Public API
----------
play_email_genie(app, screen, action, on_navigate) -> None
    Run the full press → lock → warp → completion sequence, calling
    ``on_navigate`` exactly once when the card has funneled into its
    destination. Degrades to an immediate ``on_navigate`` if anything is
    unavailable.
"""

from __future__ import annotations

import logging

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.event import EventDispatcher
from kivy.graphics import (Color, Ellipse, Line, Mesh, PopMatrix, PushMatrix,
                           RoundedRectangle, Scale)
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from config import DISPLAY_HEIGHT, DISPLAY_WIDTH

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Timing  (seconds) — matches the interaction spec exactly
# ──────────────────────────────────────────────────────────────────────────────
PRESS_IN   = 0.090     # CTA scales down
PRESS_OUT  = 0.120     # CTA springs back
LOCK_DUR   = 0.080     # widget lock handoff

STAGE_A = 0.120        # initial pull
STAGE_B = 0.220        # organic compression
STAGE_C = 0.210        # final funnel
WARP_DUR = STAGE_A + STAGE_B + STAGE_C   # 0.550

CONF_IN   = 0.150
CONF_HOLD = 0.500
CONF_OUT  = 0.200

# Press spring (iOS/macOS control feel)
SPRING_K = 650.0
SPRING_C = 28.0
SPRING_M = 1.0

# Mesh resolution: rows run along the genie flow (smoother funnel), a few
# columns across handle the side taper. Light enough for 60 FPS on the mini-PC.
_NX = 12
_NY = 24
# How far successive rows lag (the "flow"): higher → longer, more elastic tail.
_SPREAD = 0.55

_FONT_SB = "42dot-SB"
_C_SEND = (0.063, 0.780, 0.427, 1.0)   # #10C76D
_C_TEXT = (0.118, 0.129, 0.149, 1.0)   # near-black toast text


def _scale_factor() -> float:
    return min(DISPLAY_WIDTH / 1260.0, DISPLAY_HEIGHT / 800.0)


def _fs(px: float) -> int:
    return max(6, round(px * _scale_factor()))


# ──────────────────────────────────────────────────────────────────────────────
# CSS-accurate cubic-bezier easing  (P0=(0,0), P3=(1,1))
# ──────────────────────────────────────────────────────────────────────────────
def cubic_bezier(p1x: float, p1y: float, p2x: float, p2y: float):
    """Return an easing function ``f(x)->y`` for ``cubic-bezier(p1x,p1y,p2x,p2y)``.

    Solves for the curve parameter via Newton-Raphson (then returns the eased y),
    which is what browsers do — so the motion matches the spec's curves exactly.
    """
    cx = 3.0 * p1x
    bx = 3.0 * (p2x - p1x) - cx
    ax = 1.0 - cx - bx
    cy = 3.0 * p1y
    by = 3.0 * (p2y - p1y) - cy
    ay = 1.0 - cy - by

    def _bx(t: float) -> float:
        return ((ax * t + bx) * t + cx) * t

    def _bxp(t: float) -> float:
        return (3.0 * ax * t + 2.0 * bx) * t + cx

    def _by(t: float) -> float:
        return ((ay * t + by) * t + cy) * t

    def f(x: float) -> float:
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        t = x
        for _ in range(6):
            err = _bx(t) - x
            if abs(err) < 1e-4:
                break
            d = _bxp(t)
            if abs(d) < 1e-6:
                break
            t -= err / d
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        return _by(t)

    return f


# Spec easings
_EASE_PULL_AB = cubic_bezier(0.22, 1.0, 0.36, 1.0)   # stages A & B (smooth ease-out)
_EASE_FUNNEL  = cubic_bezier(0.40, 0.0, 0.20, 1.0)   # stage C (standard ease)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def _smoothstep(t: float) -> float:
    t = _clamp01(t)
    return t * t * (3.0 - 2.0 * t)


# ──────────────────────────────────────────────────────────────────────────────
# Spring integrator  (mass-spring-damper, semi-implicit Euler with substeps)
# ──────────────────────────────────────────────────────────────────────────────
class _Spring(EventDispatcher):
    """Drives a scalar toward ``target`` with real spring physics."""

    def __init__(self, value=1.0, stiffness=SPRING_K, damping=SPRING_C,
                 mass=SPRING_M, on_update=None, on_rest=None):
        super().__init__()
        self.value = float(value)
        self.target = float(value)
        self.vel = 0.0
        self.k = float(stiffness)
        self.c = float(damping)
        self.m = float(mass)
        self._on_update = on_update
        self._on_rest = on_rest
        self._ev = None

    def set_target(self, target: float) -> None:
        self.target = float(target)
        if self._ev is None:
            self._ev = Clock.schedule_interval(self._tick, 0)

    def _tick(self, dt: float) -> None:
        dt = min(dt, 1.0 / 30.0)
        steps = max(1, int(dt / 0.004) + 1)
        h = dt / steps
        for _ in range(steps):
            f = -self.k * (self.value - self.target) - self.c * self.vel
            self.vel += (f / self.m) * h
            self.value += self.vel * h
        if self._on_update:
            self._on_update(self.value)
        if abs(self.value - self.target) < 0.001 and abs(self.vel) < 0.02:
            self.value = self.target
            if self._on_update:
                self._on_update(self.value)
            self.stop()
            if self._on_rest:
                self._on_rest()

    def stop(self) -> None:
        if self._ev is not None:
            self._ev.cancel()
            self._ev = None


# ──────────────────────────────────────────────────────────────────────────────
# CTA press transform  (scale about the button centre + slight shadow lift)
# ──────────────────────────────────────────────────────────────────────────────
class _PressTransform:
    """Wraps a widget's canvas in a scale matrix so the whole button (incl. its
    label) scales as one piece about its centre — the native press feel."""

    def __init__(self, widget):
        self.widget = widget
        cx = widget.center_x
        cy = widget.center_y
        self._push = PushMatrix()
        self._scale = Scale(1.0, 1.0, 1.0)
        self._scale.origin = (cx, cy)
        self._pop = PopMatrix()
        try:
            widget.canvas.before.insert(0, self._scale)
            widget.canvas.before.insert(0, self._push)
            widget.canvas.after.add(self._pop)
            self._ok = True
        except Exception:
            self._ok = False

    def apply(self, s: float) -> None:
        if not self._ok:
            return
        self._scale.x = s
        self._scale.y = s
        self._scale.origin = (self.widget.center_x, self.widget.center_y)
        # Slight shadow lift as it presses in (1→0.94 maps to a small bump).
        depth = _clamp01((1.0 - s) / 0.06)
        bump = getattr(self.widget, "set_press_shadow", None)
        if callable(bump):
            try:
                bump(depth)
            except Exception:
                pass

    def remove(self) -> None:
        if not self._ok:
            return
        for grp, ins in ((self.widget.canvas.before, self._push),
                         (self.widget.canvas.before, self._scale),
                         (self.widget.canvas.after, self._pop)):
            try:
                grp.remove(ins)
            except Exception:
                pass
        bump = getattr(self.widget, "set_press_shadow", None)
        if callable(bump):
            try:
                bump(0.0)
            except Exception:
                pass
        self._ok = False


# ──────────────────────────────────────────────────────────────────────────────
# Snapshot
# ──────────────────────────────────────────────────────────────────────────────
def _snapshot(screen, card):
    """Return ``(texture, (x,y,w,h), (umin,vmin,umax,vmax))`` for *card* rendered
    inside *screen*, or ``None`` on failure."""
    if screen is None or card is None:
        return None
    try:
        core = screen.export_as_image()
        tex = getattr(core, "texture", None)
        if tex is None:
            return None
        tw, th = tex.size
        if not tw or not th:
            return None
        x, y = card.to_window(card.x, card.y)
        w, h = float(card.width), float(card.height)
        if w <= 0 or h <= 0:
            return None
        umin = _clamp01(x / tw)
        umax = _clamp01((x + w) / tw)
        vmin = _clamp01(y / th)
        vmax = _clamp01((y + h) / th)
        return tex, (float(x), float(y), w, h), (umin, vmin, umax, vmax)
    except Exception:
        logger.debug("email genie snapshot failed", exc_info=True)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Genie warp widget
# ──────────────────────────────────────────────────────────────────────────────
class _GenieWarp(Widget):
    """Draws the card snapshot on a triangle mesh and warps it toward *target*
    over the 3-stage spec timeline. Clock-driven for precise per-stage control."""

    def __init__(self, texture, rect, uv, target, **kw):
        super().__init__(size_hint=(None, None),
                         pos=(0, 0), size=Window.size, **kw)
        self._tex = texture
        self._rect = rect
        self._uv = uv
        self._target = (float(target[0]), float(target[1]))
        x0, y0, w, h = rect
        cx0, cy0 = x0 + w / 2.0, y0 + h / 2.0
        self._center = (cx0, cy0)
        # Whichever edge of the card faces the target leads the genie.
        self._target_above = self._target[1] >= cy0

        self._verts = [0.0] * ((_NX + 1) * (_NY + 1) * 4)
        self._indices: list[int] = []
        self._mesh: Mesh | None = None
        self._elapsed = 0.0
        self._ev = None
        self._on_done = None
        self._build()

    # — texture handling (flip-safe via the texture's real tex_coords) —
    def _tex_coords(self):
        tc = getattr(self._tex, "tex_coords", None)
        if tc is not None and len(tc) >= 8:
            return ((tc[0], tc[1]), (tc[2], tc[3]), (tc[4], tc[5]), (tc[6], tc[7]))
        return ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))

    @staticmethod
    def _interp_uv(tc, gx, gy):
        (blu, blv), (bru, brv), (tru, trv), (tlu, tlv) = tc
        bu = blu + (bru - blu) * gx
        bv = blv + (brv - blv) * gx
        tu = tlu + (tru - tlu) * gx
        tv = tlv + (trv - tlv) * gx
        return bu + (tu - bu) * gy, bv + (tv - bv) * gy

    def _build(self) -> None:
        umin, vmin, umax, vmax = self._uv
        tc = self._tex_coords()
        for j in range(_NY + 1):
            v = j / _NY
            gy = vmin + v * (vmax - vmin)
            for i in range(_NX + 1):
                u = i / _NX
                gx = umin + u * (umax - umin)
                tu, tv = self._interp_uv(tc, gx, gy)
                k = (j * (_NX + 1) + i) * 4
                self._verts[k + 2] = tu
                self._verts[k + 3] = tv
        for j in range(_NY):
            for i in range(_NX):
                a = j * (_NX + 1) + i
                b = a + 1
                c = a + (_NX + 1)
                d = c + 1
                self._indices += [a, b, c, b, d, c]
        self._compute(0.0)  # identity → first frame == resting card
        with self.canvas:
            Color(1, 1, 1, 1)
            self._mesh = Mesh(vertices=self._verts, indices=self._indices,
                              mode="triangles", texture=self._tex)

    @staticmethod
    def _envelope(t: float):
        """Return ``(W, H, O)`` — width / height fractions and opacity at time t."""
        if t < STAGE_A:
            p = _EASE_PULL_AB(t / STAGE_A)
            return _lerp(1.0, 0.92, p), 1.0, 1.0
        if t < STAGE_A + STAGE_B:
            p = _EASE_PULL_AB((t - STAGE_A) / STAGE_B)
            return _lerp(0.92, 0.40, p), _lerp(1.0, 0.75, p), 1.0
        tc = _clamp01((t - STAGE_A - STAGE_B) / STAGE_C)
        p = _EASE_FUNNEL(tc)
        return _lerp(0.40, 0.08, p), _lerp(0.75, 0.08, p), _lerp(1.0, 0.0, p)

    def _compute(self, t: float) -> None:
        x0, y0, w, h = self._rect
        cx0, cy0 = self._center
        tx, ty = self._target
        above = self._target_above
        W, H, O = self._envelope(t)
        # Translation toward the destination — back-loaded so it eases in during
        # the pull and accelerates into the destination near completion.
        pull = (min(1.0, t / WARP_DUR)) ** 1.55
        verts = self._verts
        for j in range(_NY + 1):
            v = j / _NY
            lead = v if above else (1.0 - v)
            # Per-row phase: the edge nearest the target advances first, forming
            # the funnel neck and the flowing tail.
            ph = _smoothstep(_clamp01(pull * (1.0 + _SPREAD) - (1.0 - lead) * _SPREAD))
            oy = y0 + v * h
            sy = cy0 + (oy - cy0) * H          # height envelope about centre
            py = sy + (ty - sy) * ph           # funnel toward target row
            for i in range(_NX + 1):
                u = i / _NX
                ox = x0 + u * w
                sx = cx0 + (ox - cx0) * W       # width envelope about centre
                px = sx + (tx - sx) * ph        # funnel toward target column
                k = (j * (_NX + 1) + i) * 4
                verts[k] = px
                verts[k + 1] = py
        if self._mesh is not None:
            self._mesh.vertices = verts
        self.opacity = O

    def start(self, on_done=None) -> None:
        self._on_done = on_done
        self._elapsed = 0.0
        self._ev = Clock.schedule_interval(self._tick, 0)

    def _tick(self, dt: float) -> None:
        self._elapsed += dt
        t = self._elapsed
        if t >= WARP_DUR:
            self._compute(WARP_DUR)
            self._stop()
            cb, self._on_done = self._on_done, None
            if cb:
                try:
                    cb()
                except Exception:
                    logger.debug("genie on_done failed", exc_info=True)
            return
        self._compute(t)

    def _stop(self) -> None:
        if self._ev is not None:
            self._ev.cancel()
            self._ev = None


# ──────────────────────────────────────────────────────────────────────────────
# Completion confirmation toast  (natively drawn — no Figma asset required)
# ──────────────────────────────────────────────────────────────────────────────
class _ConfirmToast(Widget):
    """A small rounded pill with an optional checkmark and a label, centred on a
    point and clamped to the screen. Fades in → holds → fades out."""

    def __init__(self, text: str, point, show_check: bool = True,
                 accent=_C_SEND, **kw):
        super().__init__(size_hint=(None, None), **kw)
        self.opacity = 0.0
        pad_x = _fs(34)
        gap = _fs(16)
        check_d = _fs(34) if show_check else 0.0
        fs = _fs(30)

        self._lbl = Label(text=text, font_name=_FONT_SB, font_size=fs,
                          color=_C_TEXT, halign="left", valign="middle",
                          size_hint=(None, None))
        self._lbl.bind(texture_size=lambda l, ts: setattr(l, "size", ts))
        self._lbl.texture_update()
        lw, lh = self._lbl.texture_size

        height = max(_fs(64), lh + _fs(26))
        width = pad_x * 2 + (check_d + gap if show_check else 0.0) + lw
        self.size = (width, height)
        cx, cy = float(point[0]), float(point[1])
        x = min(max(cx - width / 2.0, _fs(16)), Window.width - width - _fs(16))
        y = min(max(cy - height / 2.0, _fs(16)), Window.height - height - _fs(16))
        self.pos = (x, y)

        r = height / 2.0
        with self.canvas.before:
            # soft shadow
            Color(0, 0, 0, 0.16)
            self._sh = RoundedRectangle(radius=[r])
            # white pill
            Color(1, 1, 1, 0.98)
            self._bg = RoundedRectangle(radius=[r])
            if show_check:
                Color(*accent)
                self._dot = Ellipse()
                Color(1, 1, 1, 1)
                self._check = Line(width=_fs(3.0), cap="round", joint="round")
        self._check_d = check_d
        self._pad_x = pad_x
        self._gap = gap
        self.bind(pos=self._sync, size=self._sync)
        self.add_widget(self._lbl)
        self._sync()

    def _sync(self, *_):
        x, y = self.pos
        w, h = self.size
        self._sh.pos = (x, y - _fs(3))
        self._sh.size = (w, h)
        self._bg.pos = (x, y)
        self._bg.size = (w, h)
        cy = y + h / 2.0
        cursor = x + self._pad_x
        if self._check_d:
            d = self._check_d
            dy = cy - d / 2.0
            self._dot.pos = (cursor, dy)
            self._dot.size = (d, d)
            # checkmark inside the dot
            self._check.points = [
                cursor + d * 0.27, cy + d * 0.02,
                cursor + d * 0.43, cy - d * 0.16,
                cursor + d * 0.74, cy + d * 0.22,
            ]
            cursor += d + self._gap
        self._lbl.pos = (cursor, cy - self._lbl.height / 2.0)

    def play(self, on_done=None) -> None:
        from kivy.animation import Animation
        anim = (Animation(opacity=1.0, duration=CONF_IN, t="out_quad")
                + Animation(opacity=1.0, duration=CONF_HOLD)
                + Animation(opacity=0.0, duration=CONF_OUT, t="in_quad"))
        if on_done:
            anim.bind(on_complete=lambda *_: on_done())
        anim.start(self)


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────────────────
def _btn_for(screen, action):
    return {"send": getattr(screen, "_send_btn", None),
            "save": getattr(screen, "_save_btn", None),
            "discard": getattr(screen, "_discard_btn", None)}.get(action)


def _fade(widget, target, duration, after=None):
    from kivy.animation import Animation
    if widget is None:
        if after:
            after()
        return
    Animation.cancel_all(widget, "opacity")
    anim = Animation(opacity=target, duration=duration, t="out_quad")
    if after:
        anim.bind(on_complete=lambda *_: after())
    anim.start(widget)


def play_email_genie(app, screen, action: str, on_navigate) -> None:
    """Run the full email-genie sequence then call ``on_navigate`` once.

    *app* must expose ``root_layout``; *screen* is the ``EmailDraftScreen``.
    Falls back to an immediate ``on_navigate`` if essentials are missing.
    """
    def _go():
        if callable(on_navigate):
            try:
                on_navigate()
            except Exception:
                logger.debug("genie navigate failed", exc_info=True)

    root = getattr(app, "root_layout", None)
    card = getattr(screen, "_card", None)
    if screen is None or root is None or card is None:
        _go()
        return

    try:
        target = screen.genie_target(action)
    except Exception:
        target = None
    if target is None:
        _go()
        return

    # ── 1 · CTA press feedback (spring scale 1 → 0.94 → 1) ────────────────────
    btn = _btn_for(screen, action)
    press = _PressTransform(btn) if btn is not None else None
    spring = None
    if press is not None:
        spring = _Spring(value=1.0, on_update=press.apply,
                         on_rest=press.remove)
        spring.set_target(0.94)
        Clock.schedule_once(lambda _dt: spring.set_target(1.0), PRESS_IN)

    sink = btn if action in ("save", "discard") else None  # CTA the card sinks into

    # ── 2 · Widget lock (disable CTAs, dim compose to 97%) ────────────────────
    def _lock(_dt):
        try:
            if hasattr(screen, "_set_buttons_enabled"):
                screen._set_buttons_enabled(False)
        except Exception:
            pass
        _fade(card, 0.97, LOCK_DUR)

    Clock.schedule_once(_lock, PRESS_IN + PRESS_OUT)

    # ── 3 · Genie warp ────────────────────────────────────────────────────────
    def _warp(_dt):
        snap = _snapshot(screen, card)
        # Fade every CTA except the sink (save/discard collapse into their CTA).
        for b in (getattr(screen, "_send_btn", None),
                  getattr(screen, "_save_btn", None),
                  getattr(screen, "_discard_btn", None)):
            if b is not None and b is not sink:
                _fade(b, 0.0, STAGE_A + STAGE_B)
        if snap is None:
            # No snapshot → skip the warp but keep the rest of the experience.
            card.opacity = 0.0
            _after_warp()
            return
        tex, rect, uv = snap
        warp = _GenieWarp(tex, rect, uv, target)
        root.add_widget(warp)
        card.opacity = 0.0          # same frame as the (identical) mesh appears
        screen._genie_warp = warp

        def _done():
            try:
                root.remove_widget(warp)
            except Exception:
                pass
            screen._genie_warp = None
            _after_warp()

        warp.start(on_done=_done)

    def _after_warp():
        # Hand the screen back to the app (instant swap behind the overlay).
        _go()
        # Restore the compose screen's visuals for its next use.
        try:
            if hasattr(screen, "restore_action_visuals"):
                screen.restore_action_visuals()
        except Exception:
            logger.debug("genie restore failed", exc_info=True)
        _completion(app, action, target)

    Clock.schedule_once(_warp, PRESS_IN + PRESS_OUT + LOCK_DUR)


def _completion(app, action: str, target) -> None:
    """Natively-drawn completion state, layered on the root above everything."""
    root = getattr(app, "root_layout", None)
    if root is None:
        return
    if action == "discard":
        return  # clean completion, no celebratory feedback

    if action == "send":
        # Top-right corner, where a sent message logically leaves the interface.
        point = (Window.width * 0.84, Window.height * 0.84)
        toast = _ConfirmToast("Sent", point, show_check=True, accent=_C_SEND)
    else:  # save
        try:
            point = (float(target[0]), float(target[1]) + _fs(70))
        except Exception:
            point = (Window.width / 2.0, Window.height / 2.0)
        toast = _ConfirmToast("Draft Saved", point, show_check=True, accent=_C_SEND)

    root.add_widget(toast)

    def _remove():
        try:
            root.remove_widget(toast)
        except Exception:
            pass

    toast.play(on_done=_remove)

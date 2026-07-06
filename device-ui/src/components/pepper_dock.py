"""Always-on-top Pepper navigation dock (Windows desktop companion).

A small floating Pepper logo lives at the top-centre of the primary display,
above every other application. Hovering expands it — with a smooth spring — into
a horizontal capsule holding four shortcuts, in this exact order:

    Tasks · Record Meeting · Pepper (voice) · Calendar

Clicking a shortcut opens the matching existing screen on a fixed 7" surface that
floats over the desktop; clicking outside that surface (or the already-active
icon) collapses everything back to the lone logo. The currently active screen's
icon is always highlighted, and wake-word activation keeps that highlight in sync.

Visuals are taken pixel-for-pixel from Figma (Meeting BOX AI, nodes 1253:67 /
1252:36 / 1250:35): a #F7F7F7 capsule, 2px #CFC5E7 border, ~76px radius, soft
purple-grey shadow, with the exported glyph PNGs in ``assets/dock``.

The heavy Win32 plumbing (transparency, top-most, click-through) lives in
``dock_win_overlay``; this module owns the Kivy rendering, the spring
animations, and the interaction state machine (:class:`DockController`).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Callable, Optional

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.properties import NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.scatterlayout import ScatterLayout
from kivy.uix.widget import Widget

import dock_win_overlay as winov
from config import ASSETS_DIR, DISPLAY_HEIGHT, DISPLAY_WIDTH

logger = logging.getLogger(__name__)

# ── Figma spec (Meeting BOX AI dock) ─────────────────────────────────────────
_FIG_PILL_W, _FIG_PILL_H = 217.0, 54.0
_PILL_FILL = (0.969, 0.969, 0.969, 1.0)      # #F7F7F7
_PILL_BORDER = (0.812, 0.773, 0.906, 1.0)    # #CFC5E7
_SHADOW = (0.537, 0.514, 0.604, 0.30)        # rgba(137,131,154,0.3)
_HIGHLIGHT = (0.929, 0.902, 0.976, 1.0)      # soft lavender behind active icon

# Rendered dock scale (Figma capsule is tiny within its 1260px artboard; scale it
# up to a comfortable, menu-bar-like size on a full desktop). Reduced 25% from the
# original 1.55 per design feedback — the dock should feel light, not chunky.
_SCALE = 1.1625
PILL_W = _FIG_PILL_W * _SCALE
PILL_H = _FIG_PILL_H * _SCALE
LOGO_D = PILL_H * 1.06                        # idle badge diameter
_TOP_MARGIN = 16.0                            # gap from top of display
_GAP = 12.0                                   # gap between dock strip and 7" panel
_RADIUS = 76.278 * _SCALE
_BORDER_W = 2.0 * _SCALE
_HL_D = 54.0 * _SCALE                          # highlight circle diameter

# Physical size of the summoned screen ("7 inch": 15.01 cm x 9.53 cm). Rendered at
# the monitor's true pixel density so it is that real-world size on any display.
_PANEL_CM_W = 15.01
_PANEL_CM_H = 9.53

_DOCK = ASSETS_DIR / "dock"

# Shortcut definition: key, asset, Figma icon size, x-centre fraction within pill.
# Fractions come straight from the Figma layout (node 1250:35): the icons are not
# evenly spaced — they sit at these exact positions inside the 217px capsule.
_ITEMS = [
    ("tasks", "ic_tasks.png", 24.0, 0.124),
    ("record", "ic_record.png", 32.0, 0.373),
    ("voice", "ic_pepper.png", 31.0, 0.601),
    ("calendar", "ic_calendar.png", 38.0, 0.876),
]

# Expand/collapse animation timing (spec: expand 220–280ms, collapse 180–220ms).
_EXPAND_DUR = 0.26
_COLLAPSE_DUR = 0.20
# Panel open/close (scale + fade) timing.
_PANEL_IN_DUR = 0.28
_PANEL_OUT_DUR = 0.18
# Cursor travel (px) before a press on the dock becomes a drag rather than a tap.
_DRAG_THRESH = 8.0


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def _smoothstep(v: float) -> float:
    v = _clamp01(v)
    return v * v * (3.0 - 2.0 * v)


def _asset(name: str) -> str:
    p = _DOCK / name
    return str(p) if p.is_file() else ""


class _Pill(Widget):
    """The capsule background: soft shadow, #F7F7F7 fill, lavender border."""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas:
            self._sc = Color(*_SHADOW)
            self._shadow = RoundedRectangle(radius=[_RADIUS])
            self._fc = Color(*_PILL_FILL)
            self._fill = RoundedRectangle(radius=[_RADIUS])
            self._bc = Color(*_PILL_BORDER)
            self._border = Line(width=_BORDER_W, rounded_rectangle=(0, 0, 0, 0, _RADIUS))
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        x, y = self.pos
        w, h = self.size
        if w <= 0 or h <= 0:
            return
        r = min(_RADIUS, h / 2.0)
        self._shadow.pos = (x + 1.5 * _SCALE, y - 6.0 * _SCALE)
        self._shadow.size = (w, h)
        self._shadow.radius = [r]
        self._fill.pos = (x, y)
        self._fill.size = (w, h)
        self._fill.radius = [r]
        self._border.rounded_rectangle = (x + 1, y + 1, w - 2, h - 2, max(2.0, r - 1))


class _Highlight(Widget):
    """Soft circular highlight drawn behind the active icon."""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas:
            self._c = Color(*_HIGHLIGHT[:3], 0.0)
            self._ell = Ellipse()
        self.bind(pos=self._draw, size=self._draw)

    def set_alpha(self, a: float) -> None:
        self._c.a = _clamp01(a)

    def _draw(self, *_):
        self._ell.pos = self.pos
        self._ell.size = self.size


class _IconButton(ButtonBehavior, Image):
    """A tappable dock glyph that reports releases back to the controller."""

    def __init__(self, key: str, on_tap: Callable[[str], None], **kw):
        super().__init__(**kw)
        self._key = key
        self._on_tap = on_tap
        self.allow_stretch = True
        self.keep_ratio = True
        self.mipmap = True

    def on_release(self):
        if self._on_tap:
            self._on_tap(self._key)


class PepperDock(FloatLayout):
    """Root-level overlay widget that renders the logo + expandable dock.

    ``expand`` (0 collapsed → 1 fully open) drives every geometry/opacity value so
    the whole interaction is a single, cheap, spring-animated property.
    """

    expand = NumericProperty(0.0)
    # Horizontal park position along the top edge: 0 = far left, 1 = far right,
    # 0.5 = centred (default). The dock only ever moves along the top edge.
    park = NumericProperty(0.5)
    # Idle "breathing" scale of the collapsed logo (1.0 = rest).
    breathe = NumericProperty(1.0)
    # Voice "listening" pulse (0 = rest, 1 = peak) applied to the active highlight.
    pulse = NumericProperty(0.0)

    def __init__(self, on_tap: Callable[[str], None], **kw):
        super().__init__(**kw)
        self.size_hint = (1, 1)
        self._active: Optional[str] = None
        self._pulsing = False

        self._pill = _Pill(size_hint=(None, None), size=(PILL_H, PILL_H))
        self._pill.opacity = 0.0
        self.add_widget(self._pill)

        self._highlight = _Highlight(size_hint=(None, None), size=(_HL_D, _HL_D))
        self.add_widget(self._highlight)

        self._icons: dict[str, _IconButton] = {}
        for key, asset, fsize, _frac in _ITEMS:
            d = fsize * _SCALE
            ic = _IconButton(
                key,
                on_tap,
                source=_asset(asset),
                size_hint=(None, None),
                size=(d, d),
            )
            ic.opacity = 0.0
            self._icons[key] = ic
            self.add_widget(ic)

        # Idle badge (its own light circle + glyph); tapping it activates voice.
        self._logo = _IconButton(
            "voice",
            on_tap,
            source=_asset("pepper_logo.png"),
            size_hint=(None, None),
            size=(LOGO_D, LOGO_D),
        )
        self.add_widget(self._logo)

        self.bind(
            expand=lambda *_: self._apply(),
            park=lambda *_: self._apply(),
            breathe=lambda *_: self._apply(),
            pulse=lambda *_: self._apply(),
            size=lambda *_: self._apply(),
        )
        Window.bind(size=lambda *_: self._apply())
        Clock.schedule_once(lambda *_: self._apply(), 0)

    # ── active highlight ──────────────────────────────────────────────────────
    def set_active(self, key: Optional[str]) -> None:
        self._active = key if key in self._icons else None
        self._apply()

    def set_pulsing(self, on: bool) -> None:
        self._pulsing = bool(on)
        self._apply()

    @property
    def active(self) -> Optional[str]:
        return self._active

    # ── geometry ──────────────────────────────────────────────────────────────
    def _cx_range(self) -> tuple[float, float]:
        """Min/max dock centre-x that keep the full capsule on-screen."""
        half = PILL_W / 2.0 + _HL_D * 0.25
        lo = half
        hi = max(half, Window.width - half)
        return lo, hi

    def _center(self) -> tuple[float, float]:
        lo, hi = self._cx_range()
        cx = lo + _clamp01(self.park) * (hi - lo)
        cy = Window.height - _TOP_MARGIN - PILL_H / 2.0
        return cx, cy

    def _icon_target_x(self, frac: float, cx: float) -> float:
        return (cx - PILL_W / 2.0) + frac * PILL_W

    def _apply(self, *_):
        e = _clamp01(self.expand)
        we = _smoothstep(e)
        cx, cy = self._center()

        # Logo fades out quickly as the capsule takes over. A gentle breathing
        # scale gives the idle badge a subtle, calm presence.
        b = self.breathe if e < 0.02 else 1.0
        ld = LOGO_D * b
        self._logo.size = (ld, ld)
        self._logo.center = (cx, cy)
        self._logo.opacity = _clamp01(1.0 - e * 1.8)

        # Capsule grows from a circle (collapsed) to the full pill width.
        pw = PILL_H + (PILL_W - PILL_H) * we
        self._pill.size = (pw, PILL_H)
        self._pill.center = (cx, cy)
        self._pill.opacity = _clamp01(e * 2.2)

        # Icons fade + slide outward only after the capsule has grown a bit.
        icon_op = _smoothstep((e - 0.35) / 0.65)
        frac_by_key = {k: f for k, _a, _s, f in _ITEMS}
        for key, ic in self._icons.items():
            tx = self._icon_target_x(frac_by_key[key], cx)
            ic.center = (cx + (tx - cx) * e, cy)
            ic.opacity = icon_op

        # Highlight tracks the active icon; when Pepper is listening it breathes
        # a soft, growing ring around the active glyph.
        if self._active in self._icons:
            tx = self._icon_target_x(frac_by_key[self._active], cx)
            grow = 1.0 + (0.28 * self.pulse if self._pulsing else 0.0)
            d = _HL_D * grow
            self._highlight.size = (d, d)
            self._highlight.center = (cx + (tx - cx) * e, cy)
            alpha = icon_op * (1.0 - 0.35 * self.pulse if self._pulsing else 1.0)
            self._highlight.set_alpha(alpha)
        else:
            self._highlight.set_alpha(0.0)

    # ── hit-test rectangles (Kivy coords) ─────────────────────────────────────
    def logo_rect(self, pad: float = 6.0) -> tuple[float, float, float, float]:
        cx, cy = self._center()
        d = LOGO_D + pad * 2
        return (cx - d / 2, cy - d / 2, d, d)

    def pill_rect(self, pad: float = 8.0) -> tuple[float, float, float, float]:
        cx, cy = self._center()
        w = PILL_W + pad * 2
        h = PILL_H + pad * 2
        return (cx - w / 2, cy - h / 2, w, h)


class DockController:
    """Owns the dock widget, the overlay window, and the interaction machine."""

    _WINDOW_TITLE = "MeetingBox Pepper Dock"

    # screen_name → (dock key). Only these four ever highlight.
    _SCREEN_TO_KEY = {
        "tasks": "tasks",
        "recording": "record",
        "voice_session": "voice",
        "calendar": "calendar",
    }
    _KEY_TO_SCREEN = {v: k for k, v in _SCREEN_TO_KEY.items()}

    def __init__(self, app):
        self.app = app
        self.dock = PepperDock(on_tap=self._on_icon)
        self.dock.opacity = 0.0
        self.state = "hidden"           # hidden | collapsed | expanded | screen_open
        self._engaged = False
        self._hwnd = 0
        self._vrect = (0, 0, 0, 0)
        self._poll_ev = None
        self._topmost_accum = 0.0
        # 7" panel surface: the ScreenManager rendered inside a scaling holder so
        # it is a true physical size regardless of monitor resolution/density.
        self._holder: Optional[ScatterLayout] = None
        self._surface_scale = 1.0
        # Drag-to-park state (the dock only slides along the top edge).
        self._btn_prev = False
        self._maybe_drag = False
        self._drag_active = False
        self._drag_start = (0.0, 0.0)
        self._suppress_tap = False
        self._pulse_on = False
        self._park_path = self._park_store_path()
        self.dock.park = self._load_park()

    # ── installation ──────────────────────────────────────────────────────────
    def install(self) -> None:
        """Add the dock overlay to the app root (kept hidden until engaged)."""
        try:
            self.app.root_layout.add_widget(self.dock)
        except Exception:
            logger.exception("PepperDock: failed to add dock widget")

    def engage(self) -> None:
        """Turn the app window into the transparent overlay and show the dock."""
        if self._engaged:
            return
        self._engaged = True
        logger.info("PepperDock: engaging desktop overlay mode")
        # Set a unique title so the Win32 layer can locate this SDL window.
        try:
            Window.title = self._WINDOW_TITLE
        except Exception:
            pass
        try:
            Window.clearcolor = (0, 0, 0, 0)
        except Exception:
            pass
        # Constrain the ScreenManager to a fixed 7" surface, centred, hidden.
        self._layout_surface()
        # Defer the Win32 overlay setup until the SDL window exists. Retry a few
        # times because the HWND is not always resolvable on the very first tick.
        for _delay in (0.0, 0.2, 0.5, 1.0, 2.0):
            Clock.schedule_once(self._setup_overlay, _delay)
        self.dock.opacity = 1.0
        self.state = "collapsed"
        self.dock.expand = 0.0
        self.dock.set_active(None)
        self._start_breathing()
        if self._poll_ev is None:
            self._poll_ev = Clock.schedule_interval(self._poll, 1.0 / 60.0)

    def _start_breathing(self) -> None:
        """Gentle, endless idle pulse for the collapsed logo (calm presence)."""
        try:
            Animation.cancel_all(self.dock, "breathe")
            anim = (Animation(breathe=1.045, duration=1.9, t="in_out_sine")
                    + Animation(breathe=1.0, duration=1.9, t="in_out_sine"))
            anim.repeat = True
            anim.start(self.dock)
        except Exception:
            logger.debug("PepperDock: breathing animation failed", exc_info=True)

    def _update_pulse(self) -> None:
        """Run a listening ring-pulse only while the Voice screen is active."""
        want = (self.state == "screen_open" and self.dock.active == "voice")
        if want and not self._pulse_on:
            self._pulse_on = True
            self.dock.set_pulsing(True)
            try:
                Animation.cancel_all(self.dock, "pulse")
                anim = (Animation(pulse=1.0, duration=0.9, t="in_out_sine")
                        + Animation(pulse=0.0, duration=0.9, t="in_out_sine"))
                anim.repeat = True
                anim.start(self.dock)
            except Exception:
                logger.debug("PepperDock: pulse animation failed", exc_info=True)
        elif not want and self._pulse_on:
            self._pulse_on = False
            Animation.cancel_all(self.dock, "pulse")
            self.dock.pulse = 0.0
            self.dock.set_pulsing(False)

    def _setup_overlay(self, *_):
        if self._hwnd:
            return
        try:
            hwnd = winov.find_own_hwnd() or winov.find_hwnd(self._WINDOW_TITLE)
            if not hwnd:
                logger.warning("PepperDock: overlay HWND not found yet")
                return
            self._hwnd = hwnd
            self._vrect = winov.virtual_screen_rect()
            winov.make_overlay(hwnd)
            logger.info(
                "PepperDock: overlay engaged (hwnd=%s, Window.size=%s, vrect=%s)",
                hwnd, tuple(Window.size), self._vrect,
            )
        except Exception:
            logger.exception("PepperDock: overlay setup failed")

    def _layout_surface(self) -> None:
        """Render the ScreenManager as a real-physical-size 7" panel.

        The overlay window's Kivy coordinates are the monitor's *physical* pixels,
        while the screens are laid out against the logical ``DISPLAY_WIDTH`` design.
        We therefore wrap the ScreenManager in a ScatterLayout scaled so the panel
        measures exactly 15.01 x 9.53 cm on-screen (a 7" panel), preserving the
        design pixel-for-pixel — just magnified — so fonts/spacing stay correct.
        """
        sm = getattr(self.app, "screen_manager", None)
        root = getattr(self.app, "root_layout", None)
        if sm is None or root is None:
            return

        # Scale = target physical pixels / design pixels. Prefer the monitor's
        # true density (EDID); fall back to the display-scale factor.
        ppcm = winov.physical_ppcm()
        if ppcm and DISPLAY_WIDTH > 0:
            self._surface_scale = (_PANEL_CM_W * ppcm[0]) / float(DISPLAY_WIDTH)
        else:
            self._surface_scale = winov.system_scale() or 1.0

        sm.size_hint = (None, None)
        sm.size = (DISPLAY_WIDTH, DISPLAY_HEIGHT)
        sm.pos = (0, 0)

        if self._holder is None:
            holder = ScatterLayout(
                size_hint=(None, None),
                size=(DISPLAY_WIDTH, DISPLAY_HEIGHT),
                do_rotation=False,
                do_scale=False,
                do_translation=False,
                auto_bring_to_front=False,
            )
            try:
                root.remove_widget(sm)
            except Exception:
                pass
            holder.add_widget(sm)
            # Keep the panel behind the dock and other overlays (back of the stack).
            root.add_widget(holder, index=len(root.children))
            self._holder = holder

        self._holder.scale = self._surface_scale
        self._reposition_surface()
        self._holder.opacity = 0.0
        self._holder.disabled = True
        Window.bind(size=lambda *_: self._reposition_surface())

    def _panel_px(self) -> tuple[float, float]:
        # Full-scale footprint (the ScatterLayout scales about its centre during
        # the open/close animation, so the centred position stays valid).
        s = self._surface_scale
        return (DISPLAY_WIDTH * s, DISPLAY_HEIGHT * s)

    def _reposition_surface(self, *_):
        if self._holder is None:
            return
        cx, _cy = self.dock._center()
        pw, ph = self._panel_px()
        top = Window.height - (_TOP_MARGIN + PILL_H + _GAP)
        # Keep the panel fully on-screen even when the dock is parked near an edge.
        center_x = max(pw / 2.0, min(cx, Window.width - pw / 2.0))
        # ScatterLayout scales about its centre, so position by centre.
        self._holder.center = (center_x, top - ph / 2.0)

    # ── surface visibility (scale + fade, per the motion mock) ────────────────
    def _show_surface(self) -> None:
        h = self._holder
        if h is None:
            return
        already_open = (not h.disabled) and h.opacity > 0.01
        h.disabled = False
        self._reposition_surface()
        if already_open:
            # Switching screens while already open — the ScreenManager fade
            # handles it; keep the panel steady at full size.
            return
        Animation.cancel_all(h, "scale", "opacity")
        s = self._surface_scale
        h.opacity = 0.0
        h.scale = s * 0.92
        anim = (Animation(opacity=1.0, duration=_PANEL_IN_DUR * 0.8, t="out_cubic")
                & Animation(scale=s, duration=_PANEL_IN_DUR, t="out_back"))
        anim.start(h)

    def _hide_surface(self) -> None:
        h = self._holder
        if h is None:
            return
        if h.disabled and h.opacity <= 0.01:
            return
        Animation.cancel_all(h, "scale", "opacity")

        def _done(*_):
            h.opacity = 0.0
            h.disabled = True
            h.scale = self._surface_scale

        anim = (Animation(opacity=0.0, duration=_PANEL_OUT_DUR, t="in_cubic")
                & Animation(scale=self._surface_scale * 0.94,
                            duration=_PANEL_OUT_DUR, t="in_cubic"))
        anim.bind(on_complete=_done)
        anim.start(h)

    # ── interaction: icon taps ────────────────────────────────────────────────
    def _on_icon(self, key: str) -> None:
        if not self._engaged:
            return
        # A drag just ended — Kivy still fires the button release; ignore it so a
        # reposition never doubles as a screen open.
        if self._suppress_tap:
            self._suppress_tap = False
            return
        # Re-tapping the active shortcut collapses back to the lone logo.
        if self.state == "screen_open" and key == self.dock.active:
            self.collapse()
            return
        self.open_screen(key)

    def open_screen(self, key: str) -> None:
        screen = self._KEY_TO_SCREEN.get(key)
        if not screen:
            return
        self._show_surface()
        self.dock.set_active(key)
        if self.state != "expanded":
            self._animate_expand()
        self.state = "screen_open"

        if key == "record":
            self._open_recording_ready()
        elif key == "voice":
            self._activate_voice()
        else:
            try:
                self.app.goto_screen(screen, transition="fade")
            except Exception:
                logger.exception("PepperDock: goto_screen %s failed", screen)
        self._update_pulse()

    def _open_recording_ready(self) -> None:
        try:
            rec = self.app.screen_manager.get_screen("recording")
            rec.enter_ready_next = True
        except Exception:
            logger.debug("PepperDock: recording ready flag failed", exc_info=True)
        try:
            self.app.goto_screen("recording", transition="fade")
        except Exception:
            logger.exception("PepperDock: goto recording failed")

    def _activate_voice(self) -> None:
        app = self.app
        va = getattr(app, "voice_assistant", None)
        try:
            if va is not None and getattr(va, "available", False):
                va.simulate_wake()
            app._handle_voice_wake_phrase("")
        except Exception:
            logger.exception("PepperDock: voice activation failed")
            try:
                app.goto_screen("voice_session", transition="fade")
            except Exception:
                pass

    # ── interaction: expand / collapse ────────────────────────────────────────
    def _animate_expand(self) -> None:
        Animation.cancel_all(self.dock, "expand")
        Animation(expand=1.0, duration=_EXPAND_DUR, t="out_back").start(self.dock)

    def _animate_collapse(self) -> None:
        Animation.cancel_all(self.dock, "expand")
        Animation(expand=0.0, duration=_COLLAPSE_DUR, t="in_out_cubic").start(self.dock)

    def expand_hover(self) -> None:
        if self.state == "collapsed":
            self.state = "expanded"
            self._animate_expand()

    def collapse(self) -> None:
        """Collapse to the lone floating logo and hide any open surface."""
        if self.state in ("hidden", "collapsed"):
            return
        self.state = "collapsed"
        self.dock.set_active(None)
        self._animate_collapse()
        self._hide_surface()
        self._update_pulse()

    # ── active highlight sync (navigation + wake word) ────────────────────────
    def notify_screen(self, screen_name: str) -> None:
        if not self._engaged:
            return
        key = self._SCREEN_TO_KEY.get(screen_name)
        if key is None:
            return
        # A navigation landed on one of our four screens (e.g. wake word →
        # voice_session). Surface it and sync the highlight smoothly.
        self.dock.set_active(key)
        if self.state != "screen_open":
            self._show_surface()
            self.state = "screen_open"
            self._animate_expand()
        self._update_pulse()

    # ── per-frame cursor polling (hover / click-through / click-away) ──────────
    def _poll(self, dt: float) -> None:
        if not self._engaged:
            return
        self._topmost_accum += dt
        if self._topmost_accum >= 1.0:
            self._topmost_accum = 0.0
            winov.reassert_topmost(self._hwnd)

        cur = winov.get_cursor_pos()
        if cur is None:
            return
        vx, vy, _vw, _vh = self._vrect
        kx = cur[0] - vx
        ky = Window.height - (cur[1] - vy)
        btn = winov.left_button_down()

        # Drag-to-park takes precedence: while dragging, the dock stays interactive
        # and no hover/collapse logic runs.
        if self._handle_drag(kx, ky, btn):
            winov.set_click_through(self._hwnd, False)
            self._btn_prev = btn
            return

        interactive = False
        if self.state == "collapsed":
            interactive = self._point_in(kx, ky, self.dock.logo_rect())
            if interactive:
                self.expand_hover()
        elif self.state == "expanded":
            interactive = self._point_in(kx, ky, self.dock.pill_rect())
            if not interactive:
                self.collapse()
        elif self.state == "screen_open":
            in_pill = self._point_in(kx, ky, self.dock.pill_rect())
            in_surface = self._point_in(kx, ky, self._surface_rect())
            interactive = in_pill or in_surface
            if btn and not interactive:
                self.collapse()

        winov.set_click_through(self._hwnd, not interactive)
        self._btn_prev = btn

    # ── drag-to-park (top edge only) ──────────────────────────────────────────
    def _handle_drag(self, kx: float, ky: float, btn: bool) -> bool:
        """Move the dock along the top edge. Returns True while a drag is active."""
        press = btn and not self._btn_prev
        release = (not btn) and self._btn_prev
        in_dock = (self._point_in(kx, ky, self.dock.logo_rect(10))
                   or self._point_in(kx, ky, self.dock.pill_rect(6)))

        if press and in_dock:
            self._maybe_drag = True
            self._drag_start = (kx, ky)

        if self._maybe_drag and btn:
            if (self._drag_active
                    or abs(kx - self._drag_start[0]) > _DRAG_THRESH
                    or abs(ky - self._drag_start[1]) > _DRAG_THRESH):
                self._drag_active = True
                lo, hi = self.dock._cx_range()
                ncx = max(lo, min(hi, kx))
                self.dock.park = 0.5 if hi <= lo else (ncx - lo) / (hi - lo)
                self._reposition_surface()

        if release:
            was = self._drag_active
            if was:
                self._save_park(self.dock.park)
                # Swallow the click Kivy will synthesise from this release so a
                # drag never accidentally opens a screen.
                self._suppress_tap = True
                Clock.schedule_once(self._clear_suppress_tap, 0.35)
            self._maybe_drag = False
            self._drag_active = False
            self._btn_prev = btn
            return was
        return self._drag_active

    def _clear_suppress_tap(self, *_):
        self._suppress_tap = False

    # ── parked-position persistence ───────────────────────────────────────────
    @staticmethod
    def _park_store_path() -> Path:
        base = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "MeetingBox" / "data" / "config"
        return base / "dock.json"

    def _load_park(self) -> float:
        try:
            data = json.loads(self._park_path.read_text(encoding="utf-8"))
            return _clamp01(float(data.get("park", 0.5)))
        except Exception:
            return 0.5

    def _save_park(self, frac: float) -> None:
        try:
            self._park_path.parent.mkdir(parents=True, exist_ok=True)
            self._park_path.write_text(
                json.dumps({"park": round(float(frac), 4)}), encoding="utf-8"
            )
        except Exception:
            logger.debug("PepperDock: could not persist park position", exc_info=True)

    def _surface_rect(self) -> tuple[float, float, float, float]:
        if self._holder is None:
            return (0, 0, 0, 0)
        pw, ph = self._panel_px()
        return (self._holder.x, self._holder.y, pw, ph)

    @staticmethod
    def _point_in(x: float, y: float, rect: tuple[float, float, float, float]) -> bool:
        rx, ry, rw, rh = rect
        return rx <= x <= rx + rw and ry <= y <= ry + rh

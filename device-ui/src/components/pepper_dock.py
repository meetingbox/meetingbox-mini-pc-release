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

import logging
from typing import Callable, Optional

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.properties import NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.widget import Widget

import dock_win_overlay as winov
from config import ASSETS_DIR

logger = logging.getLogger(__name__)

# ── Figma spec (Meeting BOX AI dock) ─────────────────────────────────────────
_FIG_PILL_W, _FIG_PILL_H = 217.0, 54.0
_PILL_FILL = (0.969, 0.969, 0.969, 1.0)      # #F7F7F7
_PILL_BORDER = (0.812, 0.773, 0.906, 1.0)    # #CFC5E7
_SHADOW = (0.537, 0.514, 0.604, 0.30)        # rgba(137,131,154,0.3)
_HIGHLIGHT = (0.929, 0.902, 0.976, 1.0)      # soft lavender behind active icon

# Rendered dock scale (Figma capsule is tiny within its 1260px artboard; scale it
# up to a comfortable, menu-bar-like size on a full desktop).
_SCALE = 1.55
PILL_W = _FIG_PILL_W * _SCALE
PILL_H = _FIG_PILL_H * _SCALE
LOGO_D = PILL_H * 1.06                        # idle badge diameter
_TOP_MARGIN = 16.0                            # gap from top of display
_RADIUS = 76.278 * _SCALE
_BORDER_W = 2.0 * _SCALE
_HL_D = 54.0 * _SCALE                          # highlight circle diameter

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

    def __init__(self, on_tap: Callable[[str], None], **kw):
        super().__init__(**kw)
        self.size_hint = (1, 1)
        self._active: Optional[str] = None

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

        self.bind(expand=lambda *_: self._apply(), size=lambda *_: self._apply())
        Window.bind(size=lambda *_: self._apply())
        Clock.schedule_once(lambda *_: self._apply(), 0)

    # ── active highlight ──────────────────────────────────────────────────────
    def set_active(self, key: Optional[str]) -> None:
        self._active = key if key in self._icons else None
        self._apply()

    @property
    def active(self) -> Optional[str]:
        return self._active

    # ── geometry ──────────────────────────────────────────────────────────────
    def _center(self) -> tuple[float, float]:
        cx = Window.width / 2.0
        cy = Window.height - _TOP_MARGIN - PILL_H / 2.0
        return cx, cy

    def _icon_target_x(self, frac: float, cx: float) -> float:
        return (cx - PILL_W / 2.0) + frac * PILL_W

    def _apply(self, *_):
        e = _clamp01(self.expand)
        we = _smoothstep(e)
        cx, cy = self._center()

        # Logo fades out quickly as the capsule takes over.
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

        # Highlight tracks the active icon.
        if self._active in self._icons:
            tx = self._icon_target_x(frac_by_key[self._active], cx)
            self._highlight.center = (cx + (tx - cx) * e, cy)
            self._highlight.set_alpha(icon_op)
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
        # Defer the Win32 overlay setup until the retitled SDL window exists.
        Clock.schedule_once(self._setup_overlay, 0)
        Clock.schedule_once(self._setup_overlay, 0.4)
        self.dock.opacity = 1.0
        self.state = "collapsed"
        self.dock.expand = 0.0
        self.dock.set_active(None)
        if self._poll_ev is None:
            self._poll_ev = Clock.schedule_interval(self._poll, 1.0 / 60.0)

    def _setup_overlay(self, *_):
        try:
            hwnd = winov.find_hwnd(self._WINDOW_TITLE)
            if not hwnd:
                logger.warning("PepperDock: overlay HWND not found yet")
                return
            self._hwnd = hwnd
            self._vrect = winov.virtual_screen_rect()
            winov.make_overlay(hwnd)
        except Exception:
            logger.exception("PepperDock: overlay setup failed")

    def _layout_surface(self) -> None:
        """Pin the ScreenManager to a fixed 7" box, centred just below the dock."""
        sm = getattr(self.app, "screen_manager", None)
        if sm is None:
            return
        from config import DISPLAY_HEIGHT, DISPLAY_WIDTH
        sm.size_hint = (None, None)
        sm.size = (DISPLAY_WIDTH, DISPLAY_HEIGHT)
        self._reposition_surface()
        sm.opacity = 0.0
        sm.disabled = True
        Window.bind(size=lambda *_: self._reposition_surface())

    def _reposition_surface(self, *_):
        sm = getattr(self.app, "screen_manager", None)
        if sm is None:
            return
        top = Window.height - (_TOP_MARGIN + PILL_H + 12.0)
        sm.x = (Window.width - sm.width) / 2.0
        sm.top = top

    # ── surface visibility ────────────────────────────────────────────────────
    def _show_surface(self) -> None:
        sm = getattr(self.app, "screen_manager", None)
        if sm is None:
            return
        self._reposition_surface()
        sm.opacity = 1.0
        sm.disabled = False

    def _hide_surface(self) -> None:
        sm = getattr(self.app, "screen_manager", None)
        if sm is not None:
            sm.opacity = 0.0
            sm.disabled = True

    # ── interaction: icon taps ────────────────────────────────────────────────
    def _on_icon(self, key: str) -> None:
        if not self._engaged:
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
            if winov.left_button_down() and not interactive:
                self.collapse()

        winov.set_click_through(self._hwnd, not interactive)

    def _surface_rect(self) -> tuple[float, float, float, float]:
        sm = getattr(self.app, "screen_manager", None)
        if sm is None:
            return (0, 0, 0, 0)
        return (sm.x, sm.y, sm.width, sm.height)

    @staticmethod
    def _point_in(x: float, y: float, rect: tuple[float, float, float, float]) -> bool:
        rx, ry, rw, rh = rect
        return rx <= x <= rx + rw and ry <= y <= ry + rh

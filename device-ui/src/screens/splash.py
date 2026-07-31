"""
Splash Screen – Brand introduction during boot

Deep-navy background, centred wordmark with a soft blue glow, a tagline,
and three pulsing dots so the 3–5s cold-start feels intentional rather
than frozen. Auto-advances to Welcome or Home after ``SPLASH_DURATION``.
"""

from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, Rectangle, Ellipse
from kivy.animation import Animation
from kivy.clock import Clock

from screens.base_screen import BaseScreen
from async_helper import run_async
from config import COLORS, FONT_SIZES, SPLASH_DURATION, USE_MOCK_BACKEND


# Deep navy — richer than pure black without competing with the wordmark.
_BG_TOP = (0.05, 0.07, 0.13, 1)      # #0D1221
_BG_BOTTOM = (0.02, 0.03, 0.07, 1)   # #050812
_GLOW = (0.22, 0.55, 0.98, 0.18)     # primary_start at low alpha


class _LoadingDots(Widget):
    """Three horizontally-spaced dots that pulse in sequence."""

    _DOT_COUNT = 3

    def __init__(self, dot_radius=6, spacing=14, color=None, **kwargs):
        super().__init__(**kwargs)
        self.dot_radius = dot_radius
        self.spacing = spacing
        self._color = color or (1, 1, 1, 0.55)
        self._dot_alphas = [0.25] * self._DOT_COUNT
        self._instrs = []
        with self.canvas:
            for _ in range(self._DOT_COUNT):
                col = Color(*self._color)
                ell = Ellipse(pos=(0, 0), size=(dot_radius * 2, dot_radius * 2))
                self._instrs.append((col, ell))
        self.bind(pos=lambda *_: self._layout(), size=lambda *_: self._layout())
        self._tick = 0
        self._event = Clock.schedule_interval(self._pulse, 0.18)

    def _layout(self):
        d = self.dot_radius * 2
        total_w = self._DOT_COUNT * d + (self._DOT_COUNT - 1) * self.spacing
        x0 = self.center_x - total_w / 2
        y = self.center_y - self.dot_radius
        for i, (_col, ell) in enumerate(self._instrs):
            ell.pos = (x0 + i * (d + self.spacing), y)
            ell.size = (d, d)

    def _pulse(self, _dt):
        self._tick = (self._tick + 1) % self._DOT_COUNT
        for i, (col, _ell) in enumerate(self._instrs):
            # Bright active dot, dim others.
            col.a = 0.9 if i == self._tick else 0.25

    def on_parent(self, _widget, parent):
        if parent is None and self._event is not None:
            self._event.cancel()
            self._event = None


class SplashScreen(BaseScreen):
    """Splash screen shown on every boot."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()

    def _build_ui(self):
        root = FloatLayout()

        # Deep-navy background with a subtle top-to-bottom shade so the screen
        # doesn't read as flat black.  Two stacked rectangles is enough — a
        # real gradient shader isn't worth the cost for a 2s splash.
        with root.canvas.before:
            Color(*_BG_BOTTOM)
            self._bg_bottom = Rectangle(pos=root.pos, size=root.size)
            Color(*_BG_TOP)
            self._bg_top = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._resize_bg, size=self._resize_bg)

        # Radial-ish glow behind the wordmark — an oversized primary-blue
        # label at very low alpha reads as a soft halo without needing a
        # real blur shader.
        self._glow_label = Label(
            text='Nexa',
            font_size=self.suf(96),
            bold=True,
            color=(_GLOW[0], _GLOW[1], _GLOW[2], _GLOW[3]),
            halign='center',
            valign='middle',
            size_hint=(None, None),
            size=(self.suf(600), self.suf(180)),
            pos_hint={'center_x': 0.5, 'center_y': 0.55},
            opacity=0,
        )
        self._glow_label.bind(size=self._sync_text_size)

        # The actual wordmark.
        self._logo_label = Label(
            text='Nexa',
            font_size=self.suf(64),
            bold=True,
            color=COLORS['white'],
            halign='center',
            valign='middle',
            size_hint=(None, None),
            size=(self.suf(600), self.suf(120)),
            pos_hint={'center_x': 0.5, 'center_y': 0.55},
            opacity=0,
        )
        self._logo_label.bind(size=self._sync_text_size)

        # Tagline.
        self._tagline_label = Label(
            text='AI Meeting Assistant',
            font_size=self.suf(FONT_SIZES['medium']),
            color=COLORS['gray_400'],
            halign='center',
            valign='middle',
            size_hint=(None, None),
            size=(self.suf(400), self.suf(30)),
            pos_hint={'center_x': 0.5, 'center_y': 0.44},
            opacity=0,
        )
        self._tagline_label.bind(size=self._sync_text_size)

        # Loading dots below the tagline.
        self._dots = _LoadingDots(
            dot_radius=self.suf(5),
            spacing=self.suf(12),
            color=(1, 1, 1, 0.55),
            size_hint=(None, None),
            size=(self.suf(80), self.suf(20)),
            pos_hint={'center_x': 0.5, 'center_y': 0.32},
            opacity=0,
        )

        root.add_widget(self._glow_label)
        root.add_widget(self._logo_label)
        root.add_widget(self._tagline_label)
        root.add_widget(self._dots)
        self.add_widget(root)

    @staticmethod
    def _sync_text_size(label, size):
        label.text_size = size

    def _resize_bg(self, widget, _value):
        # Top half of the screen gets the lighter navy, bottom half the
        # deeper one — cheap linear gradient made of two rectangles.
        w, h = widget.size
        x, y = widget.pos
        self._bg_bottom.pos = (x, y)
        self._bg_bottom.size = (w, h)
        self._bg_top.pos = (x, y + h * 0.35)
        self._bg_top.size = (w, h * 0.65)

    # ------------------------------------------------------------------
    def on_enter(self):
        # Reset opacities so re-entering the splash re-plays the intro.
        for w in (self._glow_label, self._logo_label, self._tagline_label, self._dots):
            w.opacity = 0

        # Wordmark + glow fade in together, tagline + dots follow slightly
        # later so the eye lands on the name first.
        Animation(opacity=1, duration=0.55, t='out_quad').start(self._glow_label)
        Animation(opacity=1, duration=0.55, t='out_quad').start(self._logo_label)
        (
            Animation(duration=0.35)
            + Animation(opacity=1, duration=0.45, t='out_quad')
        ).start(self._tagline_label)
        (
            Animation(duration=0.55)
            + Animation(opacity=1, duration=0.35, t='out_quad')
        ).start(self._dots)

        Clock.schedule_once(self._advance, SPLASH_DURATION)

    def on_leave(self):
        Clock.unschedule(self._advance)

    def _advance(self, _dt):
        """Move to next screen based on setup state (server marker is authoritative)."""
        if USE_MOCK_BACKEND:
            if self.app.needs_setup():
                self.goto('welcome', transition='fade')
            else:
                self.goto('home', transition='fade')
            return
        run_async(self._advance_with_backend())

    async def _advance_with_backend(self):
        need = self.app.needs_setup()
        try:
            info = await self.backend.get_system_info()
            if info.get('setup_complete') is False:
                self.app.clear_local_setup_markers_best_effort()
                need = True
            elif info.get('setup_complete') is True:
                need = False
        except Exception:
            pass

        def _go(_clk):
            if self.manager.current != 'splash':
                return
            if need:
                self.goto('welcome', transition='fade')
            else:
                self.goto('home', transition='fade')

        Clock.schedule_once(_go, 0)

"""Premium MeetingBox home screen — command-center layout."""

from __future__ import annotations

from datetime import datetime

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from async_helper import run_async
from components.button import PrimaryButton, SecondaryButton
from config import COLORS, DISPLAY_WIDTH, FONT_SIZES, SPACING, display_now, to_display_local
from local_network import get_primary_ipv4
from network_util import linux_ethernet_ready
from screens.base_screen import BaseScreen


_DATEISH_TAIL_RE = None  # kept only to make old imports/state irrelevant after redesign


def _format_home_next_meeting(next_meeting) -> str:
    if not next_meeting:
        return 'No calendar focus loaded yet'
    title = (next_meeting.get('title') or 'Calendar event').strip() or 'Calendar event'
    start = (next_meeting.get('start') or '').strip()
    if not start:
        return title
    try:
        if 'T' in start:
            dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            line = to_display_local(dt).strftime('%a %b %d · %I:%M %p')
        else:
            d = datetime.strptime(start[:10], '%Y-%m-%d')
            line = d.strftime('%a %b %d · all day')
        return f'{title}\n{line}'
    except Exception:
        return f'{title}\n{start}'


class _TonyOrb(FloatLayout):
    """Large calm assistant orb on the home screen."""

    def __init__(self, **kwargs):
        kwargs.setdefault('size_hint', (None, None))
        super().__init__(**kwargs)
        self._phase = 0.0
        with self.canvas.before:
            self._glow_color = Color(0.10, 0.45, 0.95, 0.18)
            self._glow = Ellipse(pos=self.pos, size=self.size)
            self._ring_color = Color(0.55, 0.78, 1.0, 0.38)
            self._ring = Line(circle=(self.center_x, self.center_y, self.width / 2.25), width=2)
            self._inner_color = Color(0.18, 0.50, 0.95, 0.94)
            self._inner = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=self._sync, size=self._sync)
        Clock.schedule_interval(self._tick, 1 / 24)

    def _sync(self, *_args):
        pad = min(self.width, self.height) * 0.28
        self._glow.pos = self.pos
        self._glow.size = self.size
        self._inner.pos = (self.x + pad, self.y + pad)
        self._inner.size = (max(1, self.width - pad * 2), max(1, self.height - pad * 2))
        self._ring.circle = (self.center_x, self.center_y, max(1, self.width / 2.35))

    def _tick(self, dt):
        self._phase = (self._phase + dt) % 2.0
        pulse = 0.5 + 0.5 * abs(1.0 - self._phase)
        self._glow_color.a = 0.12 + pulse * 0.14
        self._ring_color.a = 0.24 + pulse * 0.20


class _GlassCard(BoxLayout):
    def __init__(self, radius=24, fill=(0.10, 0.14, 0.22, 0.86), **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0, 0, 0, 0.18)
            self._shadow = RoundedRectangle(pos=(self.x + 1, self.y - 3), size=self.size, radius=[radius])
            Color(*fill)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            Color(1, 1, 1, 0.08)
            self._stroke = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, radius), width=1)
        self._radius = radius
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_args):
        self._shadow.pos = (self.x + 1, self.y - 3)
        self._shadow.size = self.size
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._stroke.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)


class HomeScreen(BaseScreen):
    """Touch-first home command center."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._clock_event = None
        self._footer_ip_event = None
        self._footer_kwargs = {}
        self._wifi_ok = False
        self._mic_connected = True
        self._build_ui()

    def _build_ui(self):
        sv = self.suv
        sf = self.suf
        root = BoxLayout(orientation='vertical')
        with root.canvas.before:
            Color(0.025, 0.035, 0.060, 1)
            self._bg = Rectangle(pos=root.pos, size=root.size)
            Color(0.08, 0.32, 0.72, 0.22)
            self._glow_a = Ellipse(pos=(-120, 260), size=(520, 520))
            Color(0.55, 0.30, 0.95, 0.12)
            self._glow_b = Ellipse(pos=(DISPLAY_WIDTH - 260, -180), size=(500, 500))
        root.bind(pos=self._sync_bg, size=self._sync_bg)

        top = BoxLayout(orientation='horizontal', size_hint=(1, None), height=sv(70), padding=[sv(22), sv(12)], spacing=sv(12))
        left = BoxLayout(orientation='vertical', spacing=0)
        self.room_label = Label(text='MeetingBox', font_size=sf(FONT_SIZES['title']), color=COLORS['white'], bold=True, halign='left', valign='bottom', size_hint=(1, .6))
        self.room_label.bind(size=self.room_label.setter('text_size'))
        left.add_widget(self.room_label)
        self.connection_label = Label(text='Checking appliance health…', font_size=sf(FONT_SIZES['tiny']), color=COLORS['gray_400'], halign='left', valign='top', size_hint=(1, .4))
        self.connection_label.bind(size=self.connection_label.setter('text_size'))
        left.add_widget(self.connection_label)
        top.add_widget(left)
        settings_btn = SecondaryButton(text='Settings', size_hint=(None, None), width=sv(128), height=sv(46), font_size=sf(FONT_SIZES['small']))
        settings_btn.bind(on_release=lambda *_: self.goto('settings', transition='slide_left'))
        top.add_widget(settings_btn)
        root.add_widget(top)

        body = BoxLayout(orientation='horizontal', padding=[sv(22), sv(6), sv(22), sv(10)], spacing=sv(16))

        left_panel = _GlassCard(orientation='vertical', size_hint=(0.52, 1), padding=[sv(22), sv(18)], spacing=sv(10), radius=sv(30), fill=(0.07, 0.11, 0.19, 0.88))
        orb_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=sv(110), spacing=sv(14))
        orb_row.add_widget(_TonyOrb(size=(sv(96), sv(96))))
        orb_text = BoxLayout(orientation='vertical')
        kicker = Label(text='TONY ASSISTANT', font_size=sf(FONT_SIZES['tiny']), bold=True, color=COLORS['blue'], halign='left', valign='bottom', size_hint=(1, .34))
        kicker.bind(size=kicker.setter('text_size'))
        orb_text.add_widget(kicker)
        self.assistant_status = Label(text='Ready to brief, record, and recall.', font_size=sf(FONT_SIZES['medium']), bold=True, color=COLORS['white'], halign='left', valign='top', size_hint=(1, .66))
        self.assistant_status.bind(size=self.assistant_status.setter('text_size'))
        orb_text.add_widget(self.assistant_status)
        orb_row.add_widget(orb_text)
        left_panel.add_widget(orb_row)

        clock_card = _GlassCard(orientation='vertical', size_hint=(1, None), height=sv(138), padding=[sv(18), sv(10)], spacing=0, radius=sv(26), fill=(0.11, 0.16, 0.25, 0.92))
        self._big_clock_hm = Label(text='--:--', font_size=sf(60), bold=True, color=COLORS['white'], halign='left', valign='bottom', size_hint=(1, .68))
        self._big_clock_hm.bind(size=self._big_clock_hm.setter('text_size'))
        clock_card.add_widget(self._big_clock_hm)
        self.date_label = Label(text='', font_size=sf(FONT_SIZES['body']), color=COLORS['gray_300'], halign='left', valign='top', size_hint=(1, .32))
        self.date_label.bind(size=self.date_label.setter('text_size'))
        clock_card.add_widget(self.date_label)
        left_panel.add_widget(clock_card)

        self.upcoming_label = Label(text='Loading next focus…', font_size=sf(FONT_SIZES['body']), color=COLORS['gray_300'], halign='left', valign='top', size_hint=(1, None), height=sv(64), line_height=1.18)
        self.upcoming_label.bind(size=self.upcoming_label.setter('text_size'))
        left_panel.add_widget(self.upcoming_label)
        body.add_widget(left_panel)

        right_panel = BoxLayout(orientation='vertical', size_hint=(0.48, 1), spacing=sv(12))
        self.start_btn = PrimaryButton(text='Start Meeting', size_hint=(1, None), height=sv(82), font_size=sf(FONT_SIZES['large']))
        self.start_btn.bind(on_release=self._on_start_recording)
        right_panel.add_widget(self.start_btn)

        self.briefing_btn = SecondaryButton(text='Tony Assistant\n[size=12]Briefing · Calendar · Inbox · Memory[/size]', markup=True, size_hint=(1, None), height=sv(76), font_size=sf(FONT_SIZES['medium']))
        self.briefing_btn.bind(on_release=lambda *_: self.goto('briefing', transition='slide_left'))
        right_panel.add_widget(self.briefing_btn)

        quick = _GlassCard(orientation='vertical', size_hint=(1, 1), padding=[sv(16), sv(14)], spacing=sv(10), radius=sv(28), fill=(0.10, 0.14, 0.22, 0.84))
        quick_title = Label(text='Quick access', font_size=sf(FONT_SIZES['medium']), bold=True, color=COLORS['white'], halign='left', valign='middle', size_hint=(1, None), height=sv(30))
        quick_title.bind(size=quick_title.setter('text_size'))
        quick.add_widget(quick_title)
        row1 = BoxLayout(orientation='horizontal', spacing=sv(10))
        meetings_btn = SecondaryButton(text='Meetings', font_size=sf(FONT_SIZES['small']))
        meetings_btn.bind(on_release=lambda *_: self.goto('meetings', transition='slide_left'))
        row1.add_widget(meetings_btn)
        system_btn = SecondaryButton(text='System', font_size=sf(FONT_SIZES['small']))
        system_btn.bind(on_release=lambda *_: self.goto('system', transition='slide_left'))
        row1.add_widget(system_btn)
        quick.add_widget(row1)
        row2 = BoxLayout(orientation='horizontal', spacing=sv(10))
        wifi_btn = SecondaryButton(text='Network', font_size=sf(FONT_SIZES['small']))
        wifi_btn.bind(on_release=lambda *_: self.goto('wifi', transition='slide_left'))
        row2.add_widget(wifi_btn)
        mic_btn = SecondaryButton(text='Mic Test', font_size=sf(FONT_SIZES['small']))
        mic_btn.bind(on_release=lambda *_: self.goto('mic_test', transition='slide_left'))
        row2.add_widget(mic_btn)
        quick.add_widget(row2)
        self.pending_today_label = Label(text='Today: — pending actions', font_size=sf(FONT_SIZES['small']), color=COLORS['gray_300'], halign='left', valign='middle', size_hint=(1, None), height=sv(30))
        self.pending_today_label.bind(size=self.pending_today_label.setter('text_size'))
        quick.add_widget(self.pending_today_label)
        self.pending_total_label = Label(text='All open: — pending actions', font_size=sf(FONT_SIZES['small']), color=COLORS['gray_500'], halign='left', valign='middle', size_hint=(1, None), height=sv(28))
        self.pending_total_label.bind(size=self.pending_total_label.setter('text_size'))
        quick.add_widget(self.pending_total_label)
        right_panel.add_widget(quick)
        body.add_widget(right_panel)
        root.add_widget(body)
        root.add_widget(self.build_footer())
        self.add_widget(root)

    def _sync_bg(self, widget, *_args):
        self._bg.pos = widget.pos
        self._bg.size = widget.size
        self._glow_a.pos = (widget.x - 120, widget.y + widget.height - 360)
        self._glow_b.pos = (widget.x + widget.width - 300, widget.y - 180)

    def on_enter(self):
        self.room_label.text = getattr(self.app, 'device_name', 'MeetingBox')
        self._update_clock_labels()
        if self._clock_event:
            self._clock_event.cancel()
        self._clock_event = Clock.schedule_interval(lambda _dt: self._update_clock_labels(), 1.0)
        if self._footer_ip_event:
            self._footer_ip_event.cancel()
        self._footer_ip_event = Clock.schedule_interval(self._refresh_footer_ip, 30.0)
        Clock.schedule_once(lambda _dt: self._refresh_footer_ip(_dt), 3.0)
        self._load_system_status()
        self._load_home_summary()

    def on_leave(self):
        if self._clock_event:
            self._clock_event.cancel()
            self._clock_event = None
        if self._footer_ip_event:
            self._footer_ip_event.cancel()
            self._footer_ip_event = None

    def _refresh_footer_ip(self, _dt):
        if not self._footer_kwargs:
            return
        kw = self._footer_kwargs
        self.update_footer(wifi_ok=kw['wifi_ok'], free_gb=kw['free_gb'], privacy_mode=kw['privacy_mode'], wired_lan_ok=kw['wired_lan_ok'], local_ip=get_primary_ipv4())

    def _on_start_recording(self, _inst):
        self.app.start_recording()

    def _update_clock_labels(self):
        now = display_now()
        self._big_clock_hm.text = now.strftime('%I:%M %p').lstrip('0')
        self.date_label.text = now.strftime('%A, %B ') + str(now.day)

    def _load_system_status(self):
        async def _fetch():
            try:
                info = await self.backend.get_system_info()
                free_gb = (info['storage_total'] - info['storage_used']) / (1024 ** 3)
                wifi_ok = bool(info.get('wifi_ssid'))
                wired_ok = linux_ethernet_ready()
                privacy = getattr(self.app, 'privacy_mode', False)

                def _apply(_dt):
                    online = wifi_ok or wired_ok
                    self.connection_label.text = 'Online · Ready' if online else 'Offline · Check network'
                    self.connection_label.color = COLORS['green'] if online else COLORS['red']
                    self._footer_kwargs = {'wifi_ok': wifi_ok, 'free_gb': free_gb, 'privacy_mode': privacy, 'wired_lan_ok': wired_ok}
                    self.update_footer(wifi_ok=wifi_ok, free_gb=free_gb, privacy_mode=privacy, wired_lan_ok=wired_ok, local_ip=get_primary_ipv4())

                Clock.schedule_once(_apply, 0)
            except Exception:
                Clock.schedule_once(lambda _dt: setattr(self.connection_label, 'text', 'Backend unavailable'), 0)
        run_async(_fetch())

    def _load_home_summary(self):
        async def _fetch():
            try:
                data = await self.backend.get_home_summary()
                today_n = int(data.get('pending_actions_today') or 0)
                total_n = int(data.get('pending_actions_total') or 0)
                upcoming = _format_home_next_meeting(data.get('next_meeting'))

                def _apply(_dt):
                    self.upcoming_label.text = f'Next focus\n{upcoming}'
                    self.pending_today_label.text = f'Today: {today_n} pending action' + ('' if today_n == 1 else 's')
                    self.pending_total_label.text = f'All open: {total_n} pending action' + ('' if total_n == 1 else 's')

                Clock.schedule_once(_apply, 0)
            except Exception:
                Clock.schedule_once(lambda _dt: setattr(self.upcoming_label, 'text', 'Next focus\nAsk Tony for a briefing when online.'), 0)
        run_async(_fetch())

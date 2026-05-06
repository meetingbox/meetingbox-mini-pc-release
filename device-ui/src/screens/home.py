"""Premium MeetingBox home screen — reference-style AI dashboard."""

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


def _format_home_next_meeting(next_meeting) -> tuple[str, str]:
    if not next_meeting:
        return 'No focus loaded', 'Ask Tony for a briefing'
    title = (next_meeting.get('title') or 'Calendar event').strip() or 'Calendar event'
    start = (next_meeting.get('start') or '').strip()
    if not start:
        return title, 'Time not set'
    try:
        if 'T' in start:
            dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            line = to_display_local(dt).strftime('%I:%M %p').lstrip('0')
        else:
            d = datetime.strptime(start[:10], '%Y-%m-%d')
            line = d.strftime('%b %d · all day')
        return title, line
    except Exception:
        return title, start


def _greeting_name(name: str) -> str:
    hour = display_now().hour
    greet = 'Good morning' if hour < 12 else 'Good afternoon' if hour < 17 else 'Good evening'
    return f'{greet}, {name or "Stark"}'


class _VoiceOrb(FloatLayout):
    def __init__(self, **kwargs):
        kwargs.setdefault('size_hint', (None, None))
        super().__init__(**kwargs)
        self._phase = 0.0
        with self.canvas.before:
            self._glow_color = Color(0.12, 0.42, 1.0, 0.24)
            self._glow = Ellipse(pos=self.pos, size=self.size)
            self._ring_color = Color(0.28, 0.60, 1.0, 0.70)
            self._ring = Line(circle=(self.center_x, self.center_y, self.width / 2.2), width=2)
            self._inner_color = Color(0.04, 0.10, 0.22, 1)
            self._inner = Ellipse(pos=self.pos, size=self.size)
        self.label = Label(text='🎙', font_size=28, color=COLORS['white'], halign='center', valign='middle')
        self.label.bind(size=self.label.setter('text_size'))
        self.add_widget(self.label)
        self.bind(pos=self._sync, size=self._sync)
        Clock.schedule_interval(self._tick, 1 / 24)

    def _sync(self, *_args):
        pad = min(self.width, self.height) * 0.18
        self._glow.pos = self.pos
        self._glow.size = self.size
        self._inner.pos = (self.x + pad, self.y + pad)
        self._inner.size = (max(1, self.width - pad * 2), max(1, self.height - pad * 2))
        self._ring.circle = (self.center_x, self.center_y, max(1, self.width / 2.35))
        self.label.pos = self.pos
        self.label.size = self.size

    def _tick(self, dt):
        self._phase = (self._phase + dt) % 2.0
        pulse = 0.5 + 0.5 * abs(1.0 - self._phase)
        self._glow_color.a = 0.15 + pulse * 0.20
        self._ring_color.a = 0.45 + pulse * 0.30


class _GlassCard(BoxLayout):
    def __init__(self, radius=24, fill=(0.035, 0.075, 0.14, 0.88), **kwargs):
        super().__init__(**kwargs)
        self._radius = radius
        with self.canvas.before:
            Color(0, 0, 0, 0.20)
            self._shadow = RoundedRectangle(pos=(self.x + 1, self.y - 3), size=self.size, radius=[radius])
            Color(*fill)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            Color(0.22, 0.48, 0.95, 0.20)
            self._stroke = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, radius), width=1)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_args):
        self._shadow.pos = (self.x + 1, self.y - 3)
        self._shadow.size = self.size
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._stroke.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)


class HomeScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._clock_event = None
        self._footer_ip_event = None
        self._voice_state_event = None
        self._footer_kwargs = {}
        self._build_ui()

    def _build_ui(self):
        sv = self.suv
        sf = self.suf
        root = BoxLayout(orientation='vertical', padding=[sv(26), sv(18), sv(26), sv(14)], spacing=sv(12))
        with root.canvas.before:
            Color(0.008, 0.015, 0.035, 1)
            self._bg = Rectangle(pos=root.pos, size=root.size)
            Color(0.00, 0.18, 0.55, 0.22)
            self._glow_a = Ellipse(pos=(-160, 160), size=(620, 620))
            Color(0.00, 0.42, 1.00, 0.14)
            self._glow_b = Ellipse(pos=(DISPLAY_WIDTH - 360, 40), size=(620, 420))
        root.bind(pos=self._sync_bg, size=self._sync_bg)

        # Header: greeting + listening pill + gear
        header = BoxLayout(orientation='horizontal', size_hint=(1, None), height=sv(58), spacing=sv(12))
        self.greeting_label = Label(text='Good morning, Stark', font_size=sf(FONT_SIZES['large']), bold=True, color=COLORS['white'], halign='left', valign='middle', size_hint=(1, 1))
        self.greeting_label.bind(size=self.greeting_label.setter('text_size'))
        header.add_widget(self.greeting_label)
        self.listening_pill = _GlassCard(orientation='horizontal', size_hint=(None, None), width=sv(214), height=sv(52), padding=[sv(18), 0], spacing=sv(10), radius=sv(28), fill=(0.035, 0.070, 0.14, 0.92))
        self.voice_dot = Label(text='●', font_size=sf(FONT_SIZES['small']), color=COLORS['gray_300'], size_hint=(None, 1), width=sv(22))
        self.listening_pill.add_widget(self.voice_dot)
        self.voice_state_label = Label(text='Voice checking', font_size=sf(FONT_SIZES['medium']), bold=True, color=COLORS['white'], halign='left', valign='middle')
        self.voice_state_label.bind(size=self.voice_state_label.setter('text_size'))
        self.listening_pill.add_widget(self.voice_state_label)
        header.add_widget(self.listening_pill)
        settings = SecondaryButton(text='⚙', size_hint=(None, None), width=sv(54), height=sv(52), font_size=sf(FONT_SIZES['title']))
        settings.bind(on_release=lambda *_: self.goto('settings', transition='slide_left'))
        header.add_widget(settings)
        root.add_widget(header)

        # Main dashboard grid
        main = BoxLayout(orientation='horizontal', size_hint=(1, 1), spacing=sv(12))
        left_col = BoxLayout(orientation='vertical', size_hint=(0.49, 1), spacing=sv(12))
        right_col = BoxLayout(orientation='vertical', size_hint=(0.51, 1), spacing=sv(12))

        hero = _GlassCard(orientation='vertical', size_hint=(1, 1), padding=[sv(20), sv(16)], spacing=sv(8), radius=sv(24), fill=(0.018, 0.055, 0.125, 0.93))
        time_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=sv(86))
        clock_box = BoxLayout(orientation='vertical', size_hint=(1, 1))
        self._big_clock_hm = Label(text='--:--', font_size=sf(56), bold=True, color=COLORS['white'], halign='left', valign='bottom', size_hint=(1, .70))
        self._big_clock_hm.bind(size=self._big_clock_hm.setter('text_size'))
        clock_box.add_widget(self._big_clock_hm)
        self.date_label = Label(text='', font_size=sf(FONT_SIZES['body']), color=COLORS['white'], halign='left', valign='top', size_hint=(1, .30))
        self.date_label.bind(size=self.date_label.setter('text_size'))
        clock_box.add_widget(self.date_label)
        time_row.add_widget(clock_box)
        self.health_label = Label(text='Ready\nOnline', font_size=sf(FONT_SIZES['small']), color=COLORS['gray_300'], bold=True, halign='right', valign='middle', size_hint=(None, 1), width=sv(110))
        self.health_label.bind(size=self.health_label.setter('text_size'))
        time_row.add_widget(self.health_label)
        hero.add_widget(time_row)

        hero.add_widget(Widget(size_hint=(1, None), height=sv(8)))
        next_label = Label(text='Next up', font_size=sf(FONT_SIZES['medium']), color=COLORS['blue'], halign='left', valign='middle', size_hint=(1, None), height=sv(34))
        next_label.bind(size=next_label.setter('text_size'))
        hero.add_widget(next_label)
        self.next_time_label = Label(text='📅  —', font_size=sf(FONT_SIZES['medium']), color=COLORS['blue'], halign='left', valign='middle', size_hint=(1, None), height=sv(32))
        self.next_time_label.bind(size=self.next_time_label.setter('text_size'))
        hero.add_widget(self.next_time_label)
        self.next_title_label = Label(text='Now: No meeting selected', font_size=sf(FONT_SIZES['large']), bold=True, color=COLORS['white'], halign='left', valign='middle', size_hint=(1, None), height=sv(42), shorten=True)
        self.next_title_label.bind(size=self.next_title_label.setter('text_size'))
        hero.add_widget(self.next_title_label)
        self.more_label = Label(text='+0 more', font_size=sf(FONT_SIZES['medium']), bold=True, color=COLORS['blue'], halign='left', valign='middle', size_hint=(1, None), height=sv(30))
        self.more_label.bind(size=self.more_label.setter('text_size'))
        hero.add_widget(self.more_label)
        hero.add_widget(Widget(size_hint=(1, 1)))
        start_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=sv(86))
        start_row.add_widget(Widget(size_hint=(0.38, 1)))
        self.start_btn = PrimaryButton(text='🎙  Start Recording\n[size=12]Tap or say “start recording”[/size]', markup=True, size_hint=(0.62, 1), font_size=sf(FONT_SIZES['medium']))
        self.start_btn.bind(on_release=self._on_start_recording)
        start_row.add_widget(self.start_btn)
        hero.add_widget(start_row)
        left_col.add_widget(hero)

        # Top right: real navigation cards, no fabricated meeting/email data.
        top_cards = BoxLayout(orientation='horizontal', size_hint=(1, 0.52), spacing=sv(12))
        summary = _GlassCard(orientation='vertical', size_hint=(0.48, 1), padding=[sv(16), sv(14)], spacing=sv(8), radius=sv(22))
        summary.add_widget(Label(text='📄  Meeting Library', font_size=sf(FONT_SIZES['small']), color=COLORS['gray_300'], halign='left', valign='middle', size_hint=(1, None), height=sv(28)))
        self.last_title_label = Label(text='Open saved meetings', font_size=sf(FONT_SIZES['large']), bold=True, color=COLORS['white'], halign='left', valign='middle', size_hint=(1, None), height=sv(48), shorten=True)
        self.last_title_label.bind(size=self.last_title_label.setter('text_size'))
        summary.add_widget(self.last_title_label)
        self.last_meta_label = Label(text='Summaries, transcripts, decisions', font_size=sf(FONT_SIZES['small']), color=COLORS['gray_300'], halign='left', valign='middle', size_hint=(1, None), height=sv(34))
        self.last_meta_label.bind(size=self.last_meta_label.setter('text_size'))
        summary.add_widget(self.last_meta_label)
        self.last_actions_label = Label(text='Tap to browse  ›', font_size=sf(FONT_SIZES['small']), color=COLORS['blue'], halign='left', valign='middle', size_hint=(1, None), height=sv(30))
        self.last_actions_label.bind(size=self.last_actions_label.setter('text_size'))
        summary.add_widget(self.last_actions_label)
        summary.add_widget(Widget())
        summary.bind(on_touch_up=lambda inst, touch: self.goto('meetings', transition='slide_left') if inst.collide_point(*touch.pos) else None)
        top_cards.add_widget(summary)

        brief = _GlassCard(orientation='vertical', size_hint=(0.52, 1), padding=[sv(16), sv(14)], spacing=sv(8), radius=sv(22))
        brief.add_widget(Label(text='☀  Morning Brief', font_size=sf(FONT_SIZES['medium']), color=COLORS['white'], bold=True, halign='left', valign='middle', size_hint=(1, None), height=sv(30)))
        self.brief_calendar_label = Label(text='📅  — meetings today', font_size=sf(FONT_SIZES['small']), color=COLORS['gray_300'], halign='left', valign='middle', size_hint=(1, None), height=sv(34))
        self.brief_calendar_label.bind(size=self.brief_calendar_label.setter('text_size'))
        brief.add_widget(self.brief_calendar_label)
        self.brief_email_label = Label(text='🤖  Runs real assistant actions', font_size=sf(FONT_SIZES['small']), color=COLORS['gray_300'], halign='left', valign='middle', size_hint=(1, None), height=sv(34))
        self.brief_email_label.bind(size=self.brief_email_label.setter('text_size'))
        brief.add_widget(self.brief_email_label)
        brief.add_widget(Widget())
        view = SecondaryButton(text='View all  ›', size_hint=(1, None), height=sv(40), font_size=sf(FONT_SIZES['small']))
        view.bind(on_release=lambda *_: self.goto('briefing', transition='slide_left'))
        brief.add_widget(view)
        top_cards.add_widget(brief)
        right_col.add_widget(top_cards)

        bottom_cards = BoxLayout(orientation='horizontal', size_hint=(1, 0.25), spacing=sv(12))
        self.schedule_card = self._mini_card('📅', '—', 'Now: Loading', lambda *_: self.goto('meetings', transition='slide_left'))
        bottom_cards.add_widget(self.schedule_card)
        self.assistant_card = self._mini_card('🤖', 'Tony', 'Assistant commands', lambda *_: self.goto('briefing', transition='slide_left'))
        bottom_cards.add_widget(self.assistant_card)
        self.tasks_card = self._mini_card('✓', '0', 'Tasks due', lambda *_: self.goto('briefing', transition='slide_left'))
        bottom_cards.add_widget(self.tasks_card)
        right_col.add_widget(bottom_cards)

        say = _GlassCard(orientation='horizontal', size_hint=(1, 0.23), padding=[sv(18), sv(12)], spacing=sv(14), radius=sv(24), fill=(0.018, 0.055, 0.125, 0.92))
        say.add_widget(Label(text='✦', font_size=sf(28), color=COLORS['blue'], size_hint=(None, 1), width=sv(36)))
        say_text = BoxLayout(orientation='vertical')
        t1 = Label(text='Try saying', font_size=sf(FONT_SIZES['medium']), bold=True, color=COLORS['blue'], halign='left', valign='bottom', size_hint=(1, .45))
        t1.bind(size=t1.setter('text_size'))
        say_text.add_widget(t1)
        t2 = Label(text='“Schedule a meeting tomorrow at 4 PM”', font_size=sf(FONT_SIZES['body']), color=COLORS['gray_300'], halign='left', valign='top', size_hint=(1, .55))
        t2.bind(size=t2.setter('text_size'))
        say_text.add_widget(t2)
        say.add_widget(say_text)
        say.add_widget(_VoiceOrb(size=(sv(64), sv(64))))
        keyboard = SecondaryButton(text='Ask', size_hint=(None, None), width=sv(58), height=sv(50), font_size=sf(FONT_SIZES['title']))
        keyboard.bind(on_release=lambda *_: self.goto('briefing', transition='slide_left'))
        say.add_widget(keyboard)
        right_col.add_widget(say)

        main.add_widget(left_col)
        main.add_widget(right_col)
        root.add_widget(main)
        root.add_widget(self.build_footer())
        self.add_widget(root)

    def _mini_card(self, icon, value, label, callback):
        card = _GlassCard(orientation='horizontal', padding=[self.suv(14), self.suv(10)], spacing=self.suv(10), radius=self.suv(22))
        card.add_widget(Label(text=icon, font_size=self.suf(28), color=COLORS['blue'], size_hint=(None, 1), width=self.suv(42)))
        txt = BoxLayout(orientation='vertical')
        v = Label(text=value, font_size=self.suf(FONT_SIZES['large']), bold=True, color=COLORS['white'], halign='left', valign='bottom', size_hint=(1, .55))
        v.bind(size=v.setter('text_size'))
        setattr(card, 'value_label', v)
        txt.add_widget(v)
        l = Label(text=label, font_size=self.suf(FONT_SIZES['small']), color=COLORS['gray_300'], halign='left', valign='top', size_hint=(1, .45), shorten=True)
        l.bind(size=l.setter('text_size'))
        setattr(card, 'text_label', l)
        txt.add_widget(l)
        card.add_widget(txt)
        card.add_widget(Label(text='›', font_size=self.suf(FONT_SIZES['large']), color=COLORS['gray_300'], size_hint=(None, 1), width=self.suv(22)))
        card.bind(on_touch_up=lambda inst, touch: callback() if inst.collide_point(*touch.pos) else None)
        return card

    def _sync_bg(self, widget, *_args):
        self._bg.pos = widget.pos
        self._bg.size = widget.size
        self._glow_a.pos = (widget.x - 160, widget.y + widget.height - 460)
        self._glow_b.pos = (widget.x + widget.width - 390, widget.y + 20)

    def on_enter(self):
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
        self._refresh_voice_pill()
        if self._voice_state_event:
            self._voice_state_event.cancel()
        self._voice_state_event = Clock.schedule_interval(lambda _dt: self._refresh_voice_pill(), 2.0)

    def on_leave(self):
        if self._clock_event:
            self._clock_event.cancel()
            self._clock_event = None
        if self._footer_ip_event:
            self._footer_ip_event.cancel()
            self._footer_ip_event = None
        if self._voice_state_event:
            self._voice_state_event.cancel()
            self._voice_state_event = None

    def _refresh_footer_ip(self, _dt):
        if not self._footer_kwargs:
            return
        kw = self._footer_kwargs
        self.update_footer(wifi_ok=kw['wifi_ok'], free_gb=kw['free_gb'], privacy_mode=kw['privacy_mode'], wired_lan_ok=kw['wired_lan_ok'], local_ip=get_primary_ipv4())

    def _on_start_recording(self, _inst):
        self.app.start_recording()

    def _refresh_voice_pill(self):
        assistant = getattr(self.app, 'voice_assistant', None)
        should_listen = getattr(self.app, '_voice_assistant_should_listen', lambda: False)()
        if assistant and getattr(assistant, 'available', False) and should_listen:
            self.voice_dot.color = COLORS['blue']
            self.voice_state_label.text = 'Say “Hey Tony”'
        elif assistant and not getattr(assistant, 'available', False):
            self.voice_dot.color = COLORS['gray_300']
            self.voice_state_label.text = 'Voice offline'
        else:
            self.voice_dot.color = COLORS['gray_300']
            self.voice_state_label.text = 'Voice paused'

    def _update_clock_labels(self):
        now = display_now()
        self.greeting_label.text = _greeting_name(getattr(self.app, 'user_name', '') or 'Stark')
        self._big_clock_hm.text = now.strftime('%I:%M').lstrip('0') + '  ' + now.strftime('%p')
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
                    self.health_label.text = 'Ready\nOnline' if online else 'Offline\nNetwork'
                    self.health_label.color = COLORS['gray_300'] if online else COLORS['red']
                    self._footer_kwargs = {'wifi_ok': wifi_ok, 'free_gb': free_gb, 'privacy_mode': privacy, 'wired_lan_ok': wired_ok}
                    self.update_footer(wifi_ok=wifi_ok, free_gb=free_gb, privacy_mode=privacy, wired_lan_ok=wired_ok, local_ip=get_primary_ipv4())
                Clock.schedule_once(_apply, 0)
            except Exception:
                Clock.schedule_once(lambda _dt: setattr(self.health_label, 'text', 'Backend\nOffline'), 0)
        run_async(_fetch())

    def _load_home_summary(self):
        async def _fetch():
            try:
                data = await self.backend.get_home_summary()
                today_n = int(data.get('pending_actions_today') or 0)
                total_n = int(data.get('pending_actions_total') or 0)
                next_title, next_time = _format_home_next_meeting(data.get('next_meeting'))
                def _apply(_dt):
                    self.next_time_label.text = f'📅  {next_time}'
                    self.next_title_label.text = f'Now: {next_title}'
                    self.more_label.text = f'+{max(0, today_n)} more'
                    self.schedule_card.value_label.text = next_time.split(' ')[0] if next_time else '—'
                    self.schedule_card.text_label.text = f'Now: {next_title}'
                    self.assistant_card.value_label.text = 'Tony'
                    self.assistant_card.text_label.text = 'Assistant commands'
                    self.tasks_card.value_label.text = str(total_n)
                    self.tasks_card.text_label.text = 'Pending approvals'
                    self.brief_calendar_label.text = f'📅  {today_n} pending actions today'
                    self.brief_email_label.text = '🤖  Calendar, inbox, and memory via Tony'
                Clock.schedule_once(_apply, 0)
            except Exception:
                Clock.schedule_once(lambda _dt: setattr(self.next_title_label, 'text', 'Now: Ask Tony for briefing'), 0)
        run_async(_fetch())

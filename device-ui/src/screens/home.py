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
from config import (
    ASSETS_DIR,
    COLORS,
    DISPLAY_WIDTH,
    FONT_SIZES,
    SPACING,
    display_now,
    home_layout_horizontal_scale,
    home_layout_vertical_scale,
    to_display_local,
)
from local_network import get_primary_ipv4
from network_util import linux_ethernet_ready
from screens.base_screen import BaseScreen

_FIGMA_HERO_IMAGE = ASSETS_DIR / 'home' / 'figma_home_hero.png'
_NAVY_BG = (0.004, 0.030, 0.102, 1)       # #01081A
_CARD_TOP = (0.004, 0.067, 0.216, 0.96)   # #011137
_CARD_BOTTOM = (0.000, 0.039, 0.149, 0.98)
_CARD_INNER = (0.004, 0.043, 0.149, 0.94)
_FIGMA_BORDER = (0.247, 0.259, 0.325, 1)  # #3F4253
_FIGMA_TEXT_MUTED = (0.714, 0.729, 0.949, 1)  # #B6BAF2


def _hv(px):
    return max(1, int(round(float(px) * home_layout_vertical_scale())))


def _hh(px):
    return max(1, int(round(float(px) * home_layout_horizontal_scale())))


def _hf(fs):
    return max(6, int(round(float(fs) * home_layout_vertical_scale())))


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
    def __init__(
        self,
        radius=24,
        fill=None,
        bg_image=None,
        image_opacity=0.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._radius = radius
        self._bg_image = str(bg_image) if bg_image else ''
        with self.canvas.before:
            Color(0, 0, 0, 0.20)
            self._shadow = RoundedRectangle(pos=(self.x + 1, self.y - 3), size=self.size, radius=[radius])
            Color(*(fill or _CARD_BOTTOM))
            self._bg_bottom = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            Color(*_CARD_TOP)
            self._bg_top = RoundedRectangle(pos=(self.x, self.y + self.height * 0.48), size=(self.width, self.height * 0.52), radius=[radius, radius, 0, 0])
            if self._bg_image:
                Color(1, 1, 1, image_opacity)
                self._image = Rectangle(pos=self.pos, size=self.size, source=self._bg_image)
                Color(0, 0, 0, 0.18)
                self._image_scrim = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            else:
                self._image = None
                self._image_scrim = None
            Color(*_FIGMA_BORDER)
            self._stroke = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, radius), width=1)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_args):
        self._shadow.pos = (self.x + 1, self.y - 3)
        self._shadow.size = self.size
        self._bg_bottom.pos = self.pos
        self._bg_bottom.size = self.size
        self._bg_top.pos = (self.x, self.y + self.height * 0.48)
        self._bg_top.size = (self.width, self.height * 0.52)
        if self._image is not None:
            self._image.pos = self.pos
            self._image.size = self.size
        if self._image_scrim is not None:
            self._image_scrim.pos = self.pos
            self._image_scrim.size = self.size
        self._stroke.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)


class HomeScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._clock_event = None
        self._footer_ip_event = None
        self._voice_state_event = None
        self._footer_kwargs = {}
        self._latest_meeting_id = None
        self._build_ui()

    def _build_ui(self):
        sv = _hv
        sh = _hh
        sf = _hf
        root = BoxLayout(
            orientation='vertical',
            padding=[sh(17), sv(15), sh(17), sv(8)],
            spacing=sv(12),
        )
        with root.canvas.before:
            Color(*_NAVY_BG)
            self._bg = Rectangle(pos=root.pos, size=root.size)
            Color(0.00, 0.18, 0.55, 0.22)
            self._glow_a = Ellipse(pos=(-160, 160), size=(620, 620))
            Color(0.00, 0.42, 1.00, 0.14)
            self._glow_b = Ellipse(pos=(DISPLAY_WIDTH - 360, 40), size=(620, 420))
        root.bind(pos=self._sync_bg, size=self._sync_bg)

        header = BoxLayout(orientation='horizontal', size_hint=(1, None), height=sv(54), spacing=sh(14))
        self.greeting_label = Label(
            text='Good morning, Stark',
            font_size=sf(30),
            bold=True,
            color=COLORS['white'],
            halign='left',
            valign='middle',
            size_hint=(1, 1),
        )
        self.greeting_label.bind(size=self.greeting_label.setter('text_size'))
        header.add_widget(self.greeting_label)
        self.listening_pill = _GlassCard(
            orientation='horizontal',
            size_hint=(None, None),
            width=sh(214),
            height=sv(54),
            padding=[sh(24), 0],
            spacing=sh(10),
            radius=sv(28),
            fill=_CARD_INNER,
        )
        self.voice_dot = Label(text='●', font_size=sf(14), color=COLORS['gray_300'], size_hint=(None, 1), width=sh(22))
        self.listening_pill.add_widget(self.voice_dot)
        self.voice_state_label = Label(text='Listening', font_size=sf(20), bold=True, color=COLORS['white'], halign='left', valign='middle')
        self.voice_state_label.bind(size=self.voice_state_label.setter('text_size'))
        self.listening_pill.add_widget(self.voice_state_label)
        self.listening_pill.add_widget(Label(text='▥', font_size=sf(22), color=COLORS['blue'], size_hint=(None, 1), width=sh(30)))
        header.add_widget(self.listening_pill)
        settings = SecondaryButton(text='⚙', size_hint=(None, None), width=sv(54), height=sv(54), font_size=sf(26))
        settings.bind(on_release=lambda *_: self.goto('settings', transition='slide_left'))
        header.add_widget(settings)
        root.add_widget(header)

        top_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=sv(263), spacing=sh(7))

        hero = _GlassCard(
            orientation='vertical',
            size_hint=(0.48, 1),
            padding=[sh(20), sv(22), sh(20), sv(18)],
            spacing=sv(4),
            radius=sv(14),
            fill=(0.000, 0.031, 0.086, 0.94),
            bg_image=_FIGMA_HERO_IMAGE if _FIGMA_HERO_IMAGE.exists() else None,
            image_opacity=0.72,
        )
        time_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=sv(105))
        clock_box = BoxLayout(orientation='vertical', size_hint=(1, 1), spacing=0)
        clock_line = BoxLayout(orientation='horizontal', size_hint=(1, .72), spacing=sh(8))
        self._big_clock_hm = Label(text='--:--', font_size=sf(46), bold=True, color=COLORS['white'], halign='left', valign='bottom', size_hint=(None, 1), width=sh(118))
        self._big_clock_hm.bind(size=self._big_clock_hm.setter('text_size'))
        clock_line.add_widget(self._big_clock_hm)
        self._clock_ampm = Label(text='AM', font_size=sf(16), bold=True, color=_FIGMA_TEXT_MUTED, halign='left', valign='bottom', size_hint=(1, 1))
        self._clock_ampm.bind(size=self._clock_ampm.setter('text_size'))
        clock_line.add_widget(self._clock_ampm)
        clock_box.add_widget(clock_line)
        self.date_label = Label(text='', font_size=sf(14), bold=True, color=COLORS['white'], halign='left', valign='top', size_hint=(1, .28))
        self.date_label.bind(size=self.date_label.setter('text_size'))
        clock_box.add_widget(self.date_label)
        time_row.add_widget(clock_box)
        self.health_label = Label(text='☀  28°C\nSunny', font_size=sf(15), color=COLORS['white'], bold=True, halign='right', valign='middle', size_hint=(None, 1), width=sh(118))
        self.health_label.bind(size=self.health_label.setter('text_size'))
        time_row.add_widget(self.health_label)
        hero.add_widget(time_row)

        hero.add_widget(Widget(size_hint=(1, 1)))
        next_label = Label(text='Next up', font_size=sf(13), color=COLORS['blue'], halign='left', valign='middle', size_hint=(1, None), height=sv(24))
        next_label.bind(size=next_label.setter('text_size'))
        hero.add_widget(next_label)
        self.next_time_label = Label(text='▣  —', font_size=sf(13), color=COLORS['blue'], halign='left', valign='middle', size_hint=(1, None), height=sv(24))
        self.next_time_label.bind(size=self.next_time_label.setter('text_size'))
        hero.add_widget(self.next_time_label)
        bottom_hero = BoxLayout(orientation='horizontal', size_hint=(1, None), height=sv(78), spacing=sh(8))
        next_stack = BoxLayout(orientation='vertical', size_hint=(0.48, 1), spacing=sv(2))
        self.next_title_label = Label(text='Now: No meeting selected', font_size=sf(15), bold=True, color=COLORS['white'], halign='left', valign='middle', size_hint=(1, .50), shorten=True)
        self.next_title_label.bind(size=self.next_title_label.setter('text_size'))
        next_stack.add_widget(self.next_title_label)
        self.more_label = Label(text='+0 more', font_size=sf(13), bold=True, color=COLORS['blue'], halign='left', valign='top', size_hint=(1, .50))
        self.more_label.bind(size=self.more_label.setter('text_size'))
        next_stack.add_widget(self.more_label)
        bottom_hero.add_widget(next_stack)
        self.start_btn = PrimaryButton(
            text='🎙  Start Recording\n[size=10]Tap or say “start recording”[/size]',
            markup=True,
            size_hint=(None, None),
            width=sh(190),
            height=sv(77),
            font_size=sf(14),
        )
        self.start_btn.bind(on_release=self._on_start_recording)
        bottom_hero.add_widget(self.start_btn)
        hero.add_widget(bottom_hero)
        top_row.add_widget(hero)

        summary = _GlassCard(orientation='vertical', size_hint=(0.255, 1), padding=[sh(19), sv(35), sh(14), sv(18)], spacing=sv(8), radius=sv(12))
        summary.add_widget(Label(text='▣  Last Meeting Summary', font_size=sf(15), color=COLORS['gray_400'], bold=True, halign='left', valign='middle', size_hint=(1, None), height=sv(34)))
        self.last_title_label = Label(text='Loading recent meeting…', font_size=sf(23), bold=True, color=COLORS['white'], halign='left', valign='middle', size_hint=(1, None), height=sv(42), shorten=True)
        self.last_title_label.bind(size=self.last_title_label.setter('text_size'))
        summary.add_widget(self.last_title_label)
        self.last_meta_label = Label(text='Summaries, transcripts, decisions', font_size=sf(15), color=_FIGMA_TEXT_MUTED, halign='left', valign='top', size_hint=(1, None), height=sv(48))
        self.last_meta_label.bind(size=self.last_meta_label.setter('text_size'))
        summary.add_widget(self.last_meta_label)
        summary.add_widget(Widget(size_hint=(1, 1)))
        self.last_actions_label = Label(text='Open summary  ›', font_size=sf(15), color=COLORS['blue'], halign='left', valign='middle', size_hint=(1, None), height=sv(28))
        self.last_actions_label.bind(size=self.last_actions_label.setter('text_size'))
        summary.add_widget(self.last_actions_label)
        summary.bind(on_touch_up=lambda inst, touch: self._open_latest_meeting() if inst.collide_point(*touch.pos) else None)
        top_row.add_widget(summary)

        brief = _GlassCard(orientation='vertical', size_hint=(0.255, 1), padding=[sh(10), sv(9), sh(10), sv(8)], spacing=sv(6), radius=sv(12))
        brief.add_widget(Label(text='☀  Morning Brief', font_size=sf(17), color=COLORS['gray_400'], bold=True, halign='center', valign='middle', size_hint=(1, None), height=sv(27)))
        self.brief_calendar_label = self._brief_item('▣', '3 meetings today', 'First at 11:00 AM')
        brief.add_widget(self.brief_calendar_label)
        self.brief_weather_label = self._brief_item('☁', 'Weather: 32°C', 'Sunny')
        brief.add_widget(self.brief_weather_label)
        self.brief_email_label = self._brief_item('✉', 'email:  From:', 'Connect Gmail for updates')
        brief.add_widget(self.brief_email_label)
        view = SecondaryButton(text='View all   ›', size_hint=(1, None), height=sv(24), font_size=sf(11))
        view.bind(on_release=lambda *_: self.goto('briefing', transition='slide_left'))
        brief.add_widget(view)
        top_row.add_widget(brief)
        root.add_widget(top_row)

        bottom_cards = BoxLayout(orientation='horizontal', size_hint=(1, None), height=sv(102), spacing=sh(7))
        self.schedule_card = self._mini_card('▣', '—', 'Now: Loading', lambda *_: self.goto('meetings', transition='slide_left'), width_hint=0.43)
        bottom_cards.add_widget(self.schedule_card)
        self.email_card = self._mini_card('✉', '—', 'New emails', lambda *_: self.goto('briefing', transition='slide_left'), width_hint=0.285)
        bottom_cards.add_widget(self.email_card)
        self.tasks_card = self._mini_card('✓', '0', 'Tasks due', lambda *_: self.goto('briefing', transition='slide_left'), width_hint=0.285)
        bottom_cards.add_widget(self.tasks_card)
        root.add_widget(bottom_cards)

        say = _GlassCard(
            orientation='horizontal',
            size_hint=(1, None),
            height=sv(71),
            padding=[sh(18), sv(10), sh(14), sv(10)],
            spacing=sh(14),
            radius=sv(21),
            fill=_CARD_INNER,
        )
        say.add_widget(Label(text='✦\n+', font_size=sf(24), color=COLORS['blue'], size_hint=(None, 1), width=sh(38), halign='center', valign='middle'))
        say_text = BoxLayout(orientation='vertical')
        t1 = Label(text='Try saying', font_size=sf(19), bold=True, color=COLORS['blue'], halign='left', valign='bottom', size_hint=(1, .42))
        t1.bind(size=t1.setter('text_size'))
        say_text.add_widget(t1)
        t2 = Label(text='“Schedule a meeting tomorrow at 4 PM”', font_size=sf(16), color=_FIGMA_TEXT_MUTED, halign='left', valign='top', size_hint=(1, .58))
        t2.bind(size=t2.setter('text_size'))
        say_text.add_widget(t2)
        say.add_widget(say_text)
        say.add_widget(_VoiceOrb(size=(sv(66), sv(66))))
        keyboard = SecondaryButton(text='⌨', size_hint=(None, None), width=sh(54), height=sv(48), font_size=sf(24))
        keyboard.bind(on_release=lambda *_: self.goto('briefing', transition='slide_left'))
        say.add_widget(keyboard)
        root.add_widget(say)
        root.add_widget(self.build_footer())
        self.add_widget(root)

    def _mini_card(self, icon, value, label, callback, width_hint=0.33):
        card = _GlassCard(
            orientation='horizontal',
            size_hint=(width_hint, 1),
            padding=[_hh(30), _hv(16), _hh(15), _hv(16)],
            spacing=_hh(16),
            radius=_hv(16),
        )
        icon_box = _GlassCard(
            orientation='vertical',
            size_hint=(None, None),
            width=_hv(66),
            height=_hv(66),
            radius=_hv(36),
            fill=_CARD_INNER,
        )
        icon_box.add_widget(Label(text=icon, font_size=_hf(31), color=COLORS['blue'], halign='center', valign='middle'))
        card.add_widget(icon_box)
        txt = BoxLayout(orientation='vertical')
        v = Label(text=value, font_size=_hf(27), bold=True, color=COLORS['white'], halign='left', valign='bottom', size_hint=(1, .48))
        v.bind(size=v.setter('text_size'))
        setattr(card, 'value_label', v)
        txt.add_widget(v)
        l = Label(text=label, font_size=_hf(18), color=_FIGMA_TEXT_MUTED, halign='left', valign='top', size_hint=(1, .52), shorten=True)
        l.bind(size=l.setter('text_size'))
        setattr(card, 'text_label', l)
        txt.add_widget(l)
        card.add_widget(txt)
        card.add_widget(Label(text='›', font_size=_hf(36), color=_FIGMA_TEXT_MUTED, size_hint=(None, 1), width=_hh(24)))
        card.bind(on_touch_up=lambda inst, touch: callback() if inst.collide_point(*touch.pos) else None)
        return card

    def _brief_item(self, icon, title, subtitle):
        row = _GlassCard(
            orientation='horizontal',
            size_hint=(1, None),
            height=_hv(52),
            padding=[_hh(10), _hv(6), _hh(8), _hv(6)],
            spacing=_hh(9),
            radius=_hv(12),
            fill=_CARD_INNER,
        )
        row.add_widget(Label(text=icon, font_size=_hf(27), color=COLORS['blue'], halign='center', valign='middle', size_hint=(None, 1), width=_hh(38)))
        text = BoxLayout(orientation='vertical', spacing=0)
        title_label = Label(text=title, font_size=_hf(15), bold=True, color=COLORS['gray_400'], halign='left', valign='bottom', size_hint=(1, .55), shorten=True)
        title_label.bind(size=title_label.setter('text_size'))
        subtitle_label = Label(text=subtitle, font_size=_hf(12), bold=True, color=_FIGMA_TEXT_MUTED, halign='left', valign='top', size_hint=(1, .45), shorten=True)
        subtitle_label.bind(size=subtitle_label.setter('text_size'))
        setattr(row, 'title_label', title_label)
        setattr(row, 'subtitle_label', subtitle_label)
        text.add_widget(title_label)
        text.add_widget(subtitle_label)
        row.add_widget(text)
        return row

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

    def _open_latest_meeting(self):
        if self._latest_meeting_id:
            detail = self.app.screen_manager.get_screen('meeting_detail')
            detail.set_meeting_id(self._latest_meeting_id)
            self.goto('meeting_detail', transition='slide_left')
        else:
            self.goto('meetings', transition='slide_left')

    def _refresh_voice_pill(self):
        assistant = getattr(self.app, 'voice_assistant', None)
        should_listen = getattr(self.app, '_voice_assistant_should_listen', lambda: False)()
        if assistant and getattr(assistant, 'available', False) and should_listen:
            self.voice_dot.color = COLORS['blue']
            self.voice_state_label.text = 'Listening'
        elif assistant and not getattr(assistant, 'available', False):
            self.voice_dot.color = COLORS['gray_300']
            self.voice_state_label.text = 'Voice offline'
        else:
            self.voice_dot.color = COLORS['gray_300']
            self.voice_state_label.text = 'Voice paused'

    def _update_clock_labels(self):
        now = display_now()
        self.greeting_label.text = _greeting_name(getattr(self.app, 'user_name', '') or 'Stark')
        self._big_clock_hm.text = now.strftime('%I:%M').lstrip('0')
        self._clock_ampm.text = now.strftime('%p')
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
                    if not online:
                        self.health_label.text = 'Offline\nNetwork'
                        self.health_label.color = COLORS['red']
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
                meetings = []
                try:
                    meetings = await self.backend.get_meetings(limit=1)
                except Exception:
                    meetings = []
                latest = meetings[0] if meetings else None
                today_n = int(data.get('pending_actions_today') or 0)
                total_n = int(data.get('pending_actions_total') or 0)
                unread_n = data.get('unread_email_count')
                next_title, next_time = _format_home_next_meeting(data.get('next_meeting'))
                def _apply(_dt):
                    self.next_time_label.text = f'▣  {next_time}'
                    self.next_title_label.text = f'Now: {next_title}'
                    self.more_label.text = f'+{max(0, today_n)} more'
                    self.schedule_card.value_label.text = next_time.split(' ')[0] if next_time else '—'
                    self.schedule_card.text_label.text = f'Now: {next_title}'
                    if latest:
                        self._latest_meeting_id = latest.get('id')
                        self.last_title_label.text = latest.get('title') or 'Untitled meeting'
                        try:
                            raw = latest.get('start_time') or latest.get('created_at') or ''
                            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                            when = to_display_local(dt).strftime('%b %d · %I:%M %p').replace(' 0', ' ')
                        except Exception:
                            when = 'Recent meeting'
                        dur = int(latest.get('duration') or 0) // 60
                        self.last_meta_label.text = f'{when} · {dur} min' if dur else when
                        pa = int(latest.get('pending_actions') or 0)
                        self.last_actions_label.text = f'{pa} pending actions  ›' if pa else 'Open summary  ›'
                    else:
                        self._latest_meeting_id = None
                        self.last_title_label.text = 'No saved meetings yet'
                        self.last_meta_label.text = 'Start a recording to build memory'
                        self.last_actions_label.text = 'Open meeting library  ›'
                    self.email_card.value_label.text = str(unread_n) if unread_n is not None else '—'
                    self.email_card.text_label.text = 'New emails'
                    self.tasks_card.value_label.text = str(total_n)
                    self.tasks_card.text_label.text = 'Tasks due'
                    self.brief_calendar_label.title_label.text = f'{max(0, today_n)} actions today' if today_n else 'Briefing ready'
                    self.brief_calendar_label.subtitle_label.text = f'First at {next_time}' if next_time and next_time != 'Time not set' else 'Ask Tony for focus'
                    self.brief_email_label.title_label.text = 'email:  From:'
                    self.brief_email_label.subtitle_label.text = 'Connect Gmail for updates' if unread_n is None else f'{unread_n} new messages'
                Clock.schedule_once(_apply, 0)
            except Exception:
                Clock.schedule_once(lambda _dt: setattr(self.next_title_label, 'text', 'Now: Ask Tony for briefing'), 0)
        run_async(_fetch())

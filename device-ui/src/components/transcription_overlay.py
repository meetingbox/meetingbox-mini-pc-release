"""
Transcription Overlay

Two display modes:

  full (used on the home screen)
    Whole-screen WhatsApp-style chat with a scrollable history of every
    user / AI turn since the voice session started. Tap ✕ to dismiss.

  compact (used on every other screen)
    A small floating strip at the bottom of the screen showing only the
    most recent line of dialog so the user can still see what the assistant
    said while reading the current screen. Touches outside the strip pass
    through to the screen below.

The full conversation history is always retained internally — switching
between modes is purely a presentation change.

AI transcripts arrive as a stream of deltas; `stream_ai_message(item_id,
accumulated_text)` upserts the active assistant bubble in place so the
text grows word-by-word in sync with the audio playback.
"""

from __future__ import annotations

import logging
import time

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from config import COLORS, FONT_SIZES, DISPLAY_WIDTH, DISPLAY_HEIGHT

logger = logging.getLogger(__name__)

# ── Bubble geometry ──────────────────────────────────────────────────────────
_BUBBLE_MAX_FRACTION = 0.70
_BUBBLE_PADDING_H = 14
_BUBBLE_PADDING_V = 10
_BUBBLE_RADIUS = 16
_ROW_GAP = 8                  # vertical gap below each bubble row
_ROW_SIDE_PAD = 12            # horizontal padding inside a row

# ── Colours ───────────────────────────────────────────────────────────────────
_BG_COLOR       = (0.04, 0.04, 0.06, 0.93)
_AI_BUBBLE      = (0.20, 0.20, 0.22, 1.0)
_USER_BUBBLE    = (0.13, 0.56, 0.34, 1.0)
_HEADER_BG      = (0.08, 0.08, 0.10, 1.0)
_COMPACT_BG     = (0.06, 0.06, 0.08, 0.92)
_TEXT_COLOR     = COLORS['white']
_HEADER_TEXT    = COLORS['white']
_CLOSE_COLOR    = COLORS['gray_400']
_SPEAKER_COLOR  = COLORS['gray_500']

# ── Typography ────────────────────────────────────────────────────────────────
_FONT_BUBBLE  = FONT_SIZES.get('medium', 16)
_FONT_SPEAKER = FONT_SIZES.get('tiny', 10) + 1
_FONT_HEADER  = FONT_SIZES.get('title', 18)
_FONT_COMPACT = FONT_SIZES.get('medium', 16)
_HEADER_H     = 52
_COMPACT_H    = 78

# Fallback speaking rate (words/sec) used only while audio is still streaming
# in and the true total duration isn't known yet. Typical TTS cadence is
# ~2.5-3 words/sec. Mirrors the home say-bar reveal pacing.
_AI_DEFAULT_WPS = 2.6


def _attach_bg(widget, color: tuple, radius: int = 0):
    """Attach a canvas.before background (rounded if radius > 0)."""
    with widget.canvas.before:
        Color(*color)
        if radius:
            rect = RoundedRectangle(pos=widget.pos, size=widget.size,
                                    radius=[radius])
        else:
            rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda w, _: setattr(rect, 'pos', w.pos),
        size=lambda w, _: setattr(rect, 'size', w.size),
    )


# ── Bubble ────────────────────────────────────────────────────────────────────

class _Bubble(BoxLayout):
    """A single chat bubble that auto-sizes to its text content."""

    def __init__(self, text: str, is_user: bool, overlay_width: float, **kw):
        super().__init__(
            orientation='vertical',
            size_hint=(None, None),
            padding=[_BUBBLE_PADDING_H, _BUBBLE_PADDING_V,
                     _BUBBLE_PADDING_H, _BUBBLE_PADDING_V],
            spacing=0,
            **kw,
        )
        self._is_user = is_user
        max_w = (overlay_width or DISPLAY_WIDTH) * _BUBBLE_MAX_FRACTION
        self.width = max_w
        # Initial height is irrelevant — _sync_height resets it as soon
        # as the label has measured its texture. Set something non-zero
        # so the surrounding BoxLayout reserves a sensible slot until then.
        self.height = _BUBBLE_PADDING_V * 2 + _FONT_BUBBLE * 2

        _attach_bg(self, _USER_BUBBLE if is_user else _AI_BUBBLE,
                   radius=_BUBBLE_RADIUS)

        lbl = Label(
            text=text,
            font_size=_FONT_BUBBLE,
            color=_TEXT_COLOR,
            halign='left',
            valign='top',
            size_hint=(1, None),
            text_size=(max_w - _BUBBLE_PADDING_H * 2, None),
        )
        lbl.bind(texture_size=lambda l, ts: self._sync_height(l, ts))
        self.add_widget(lbl)
        self._label = lbl

    def _sync_height(self, lbl, ts):
        lbl.height = ts[1]
        self.height = ts[1] + _BUBBLE_PADDING_V * 2

    def update_text(self, text: str):
        """Replace the visible text. Triggers a height recompute via texture_size."""
        self._label.text = text


class _BubbleRow(BoxLayout):
    """Horizontal row that aligns a bubble left (AI) or right (user) using
    a transparent flex spacer Widget. This is far more reliable than the
    FloatLayout + pos_hint approach for chat-style layouts inside a
    vertical BoxLayout (which is how _chat_box stacks rows)."""

    def __init__(self, bubble: _Bubble, **kw):
        super().__init__(
            orientation='horizontal',
            size_hint=(1, None),
            padding=[_ROW_SIDE_PAD, 0, _ROW_SIDE_PAD, 0],
            spacing=0,
            **kw,
        )
        self._bubble = bubble
        if bubble._is_user:
            # User: spacer absorbs left side, bubble hugs the right edge
            self.add_widget(Widget(size_hint=(1, 1)))
            self.add_widget(bubble)
        else:
            # AI: bubble hugs left edge, spacer absorbs the right side
            self.add_widget(bubble)
            self.add_widget(Widget(size_hint=(1, 1)))

        # Row height tracks the bubble height (plus a small gap below).
        bubble.bind(height=self._on_bubble_height)
        self.height = bubble.height + _ROW_GAP

    def _on_bubble_height(self, _bubble, h):
        self.height = h + _ROW_GAP

    def update_text(self, text: str):
        self._bubble.update_text(text)


class _SpeakerLabel(BoxLayout):
    """Tiny 'You' / 'AI' label aligned to the same side as its bubble."""

    def __init__(self, is_user: bool, **kw):
        super().__init__(
            orientation='horizontal',
            size_hint=(1, None),
            height=18,
            padding=[14, 0, 14, 0],
            **kw,
        )
        lbl = Label(
            text='You' if is_user else 'AI',
            font_size=_FONT_SPEAKER,
            color=_SPEAKER_COLOR,
            halign='right' if is_user else 'left',
            valign='middle',
            size_hint=(1, 1),
        )
        lbl.bind(size=lbl.setter('text_size'))
        self.add_widget(lbl)


# ── Main overlay ──────────────────────────────────────────────────────────────

class TranscriptionOverlay(FloatLayout):
    """
    Persistent transcript panel with two display modes (full / compact).

    Public API
    ----------
    show()                                — fade in
    hide()                                — fade out
    clear_session()                       — wipe all messages (call at session start)
    add_user_message(text) -> str         — append user bubble
    add_ai_message(text) -> str           — append AI bubble (non-streaming)
    stream_ai_message(item_id, accumulated_text) -> str
                                          — upsert the active AI bubble for this item_id
    update_user_message(msg_id, text)     — replace user bubble text (grammar fix)
    set_compact(bool)                     — full-screen vs bottom-strip
    """

    def __init__(self, **kw):
        super().__init__(size_hint=(1, 1), **kw)
        self._visible = False
        self._compact = False
        self._messages: dict[str, _BubbleRow] = {}
        self._msg_counter = 0
        # item_id (from realtime API) -> msg_id of the AI bubble currently
        # being streamed for that response. Cleared whenever a new user
        # message lands or a response ends.
        self._active_ai_msg_ids: dict[str, str] = {}

        # ── Audio-paced AI reveal (movie-subtitle style, same as home) ──────
        # The realtime transcript deltas arrive in a fast burst — far ahead of
        # the spoken audio. To match the home say-bar, we accumulate the full
        # transcript but only REVEAL words proportional to how much audio has
        # actually played, and we FREEZE on barge-in.
        self._ai_stream_item_id: str | None = None
        self._ai_bubble_msg_id: str | None = None
        self._ai_words: list[str] = []
        self._ai_revealed: int = 0
        self._ai_audio_total_s: float = 0.0
        self._ai_speak_start_mono: float = 0.0
        self._ai_response_done: bool = False
        self._ai_reveal_active: bool = False
        self._ai_tick_ev = None

        self.opacity = 0
        # When True, new messages do NOT auto-show the overlay (used on the
        # home screen where the say bar handles transcription display).
        self.suppress_auto_show = False
        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── FULL view container (dark backdrop + header + scroll list) ────
        self._full_view = FloatLayout(size_hint=(1, 1))
        _attach_bg(self._full_view, _BG_COLOR)

        # ScrollView added first so the header (added later) paints on top
        self._scroll = ScrollView(
            size_hint=(1, 1),
            pos_hint={'x': 0, 'y': 0},
            do_scroll_x=False,
            do_scroll_y=True,
            scroll_type=['bars', 'content'],
            bar_width=4,
            bar_color=list(COLORS['gray_700']),
            bar_inactive_color=list(COLORS['gray_800']),
        )
        self._chat_box = BoxLayout(
            orientation='vertical',
            size_hint=(1, None),
            spacing=4,
            padding=[0, _HEADER_H + 12, 0, 20],
        )
        self._chat_box.bind(minimum_height=self._chat_box.setter('height'))
        self._scroll.add_widget(self._chat_box)
        self._full_view.add_widget(self._scroll)

        # Header bar
        header = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=_HEADER_H,
            pos_hint={'top': 1},
            padding=[20, 0, 16, 0],
            spacing=8,
        )
        _attach_bg(header, _HEADER_BG)

        title = Label(
            text='Live Transcript',
            font_size=_FONT_HEADER,
            bold=True,
            color=_HEADER_TEXT,
            halign='left',
            valign='middle',
            size_hint=(1, 1),
        )
        title.bind(size=title.setter('text_size'))
        header.add_widget(title)

        close_btn = Label(
            text='✕',
            font_size=_FONT_HEADER + 2,
            color=_CLOSE_COLOR,
            size_hint=(None, 1),
            width=44,
            halign='center',
            valign='middle',
        )
        close_btn.bind(size=close_btn.setter('text_size'))
        close_btn.bind(on_touch_down=self._on_close_touch)
        header.add_widget(close_btn)
        self._full_view.add_widget(header)

        self.add_widget(self._full_view)

        # ── COMPACT view (bottom strip, no full backdrop) ─────────────────
        self._compact_view = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=_COMPACT_H,
            pos_hint={'x': 0, 'y': 0},
            padding=[16, 10, 16, 12],
            spacing=10,
        )
        _attach_bg(self._compact_view, _COMPACT_BG)

        self._compact_speaker = Label(
            text='AI',
            font_size=_FONT_SPEAKER,
            bold=True,
            color=_SPEAKER_COLOR,
            size_hint=(None, 1),
            width=36,
            halign='left',
            valign='top',
        )
        self._compact_speaker.bind(
            size=self._compact_speaker.setter('text_size')
        )
        self._compact_view.add_widget(self._compact_speaker)

        self._compact_label = Label(
            text='',
            font_size=_FONT_COMPACT,
            color=_TEXT_COLOR,
            size_hint=(1, 1),
            halign='left',
            valign='top',
            shorten=False,
        )
        self._compact_label.bind(
            size=lambda w, _s: setattr(w, 'text_size', (w.width, w.height))
        )
        self._compact_view.add_widget(self._compact_label)

        self._compact_view.opacity = 0
        self.add_widget(self._compact_view)

    # ── Public API ────────────────────────────────────────────────────────────

    def show(self):
        if self._visible:
            return
        self._visible = True
        Animation.cancel_all(self)
        Animation(opacity=1, duration=0.25, t='out_quad').start(self)

    def hide(self):
        if not self._visible:
            return
        self._visible = False
        Animation.cancel_all(self)
        Animation(opacity=0, duration=0.2, t='in_quad').start(self)

    def clear_session(self):
        self._chat_box.clear_widgets()
        self._messages.clear()
        self._active_ai_msg_ids.clear()
        self._reset_ai_reveal()
        self._msg_counter = 0
        self._compact_label.text = ''
        self._compact_speaker.text = 'AI'

    def add_user_message(self, text: str) -> str:
        # A new user turn ends any in-flight AI bubble streaming.
        self._active_ai_msg_ids.clear()
        self._reset_ai_reveal()
        return self._add_message(text, is_user=True)

    def add_ai_message(self, text: str) -> str:
        """Append a one-shot AI bubble (no streaming)."""
        return self._add_message(text, is_user=False)

    def stream_ai_message(self, item_id: str, accumulated_text: str) -> str:
        """Accumulate the AI transcript for `item_id`.

        The transcript arrives in a fast burst, well ahead of the spoken
        audio. We DON'T paint it all at once; instead we store the target
        words and let `_ai_tick` reveal them in sync with audio playback
        (see `note_ai_audio_progress`), exactly like the home say-bar. This
        gives the same movie-subtitle effect on every screen and lets a
        barge-in freeze the reveal mid-sentence.
        """
        if not accumulated_text:
            return ""
        words = accumulated_text.split()
        if not words:
            return ""

        # New response (different item, or a shorter accumulation than before
        # which means the model started over) → start a fresh bubble + reveal.
        is_new = (
            item_id != self._ai_stream_item_id
            or len(words) < len(self._ai_words)
        )
        if is_new:
            self._reset_ai_reveal()
            self._ai_stream_item_id = item_id
            msg_id = self._add_message("", is_user=False)
            if msg_id:
                self._active_ai_msg_ids[item_id] = msg_id
                self._ai_bubble_msg_id = msg_id

        self._ai_words = words
        self._ensure_ai_tick()
        # Repaint the already-revealed window against the new word list.
        self._render_ai_reveal()
        return self._ai_bubble_msg_id or ""

    def note_ai_audio_progress(self, audio_seconds: float) -> None:
        """Cumulative *played* audio seconds from the realtime session.

        First call marks the wall-clock start of playback; the tick then
        reveals words proportional to (elapsed / total_audio_duration)."""
        if self._ai_speak_start_mono <= 0.0:
            self._ai_speak_start_mono = time.monotonic()
            self._ai_reveal_active = True
            self._ensure_ai_tick()
        try:
            self._ai_audio_total_s = max(
                self._ai_audio_total_s, float(audio_seconds)
            )
        except (TypeError, ValueError):
            pass

    def finalize_ai_message(self, item_id: str, final_text: str) -> None:
        """End-of-response marker. Does NOT jump to the end — the paced tick
        finishes the reveal in sync with playback. If there was no audio
        timing at all (text-only), reveal everything immediately."""
        words = (final_text or "").strip().split()
        if words:
            self._ai_words = words
        self._ai_response_done = True
        if self._ai_speak_start_mono <= 0.0:
            self._ai_revealed = len(self._ai_words)
            self._render_ai_reveal()
            self._ai_reveal_active = False
            self._stop_ai_tick()

    def freeze_ai_stream(self) -> None:
        """Barge-in: the AI audio was cut, so stop revealing further words.
        Whatever is already on screen stays until the next turn clears it."""
        if not self._ai_reveal_active:
            return
        self._ai_reveal_active = False
        self._ai_response_done = True
        self._stop_ai_tick()

    def update_user_message(self, msg_id: str, corrected: str):
        row = self._messages.get(msg_id)
        if row is not None:
            row.update_text(corrected)
        if self._compact_speaker.text == 'You':
            self._compact_label.text = corrected

    def set_compact(self, compact: bool):
        """Switch between full-screen and bottom-strip presentation."""
        if compact == self._compact:
            return
        self._compact = compact
        Animation.cancel_all(self._full_view, 'opacity')
        Animation.cancel_all(self._compact_view, 'opacity')
        if compact:
            self._full_view.opacity = 0
            self._full_view.disabled = True
            self._compact_view.opacity = 1
        else:
            self._full_view.opacity = 1
            self._full_view.disabled = False
            self._compact_view.opacity = 0

    # ── Internals ─────────────────────────────────────────────────────────────

    def _reset_ai_reveal(self) -> None:
        self._stop_ai_tick()
        self._ai_stream_item_id = None
        self._ai_bubble_msg_id = None
        self._ai_words = []
        self._ai_revealed = 0
        self._ai_audio_total_s = 0.0
        self._ai_speak_start_mono = 0.0
        self._ai_response_done = False
        self._ai_reveal_active = False

    def _ensure_ai_tick(self) -> None:
        if self._ai_tick_ev is None:
            self._ai_tick_ev = Clock.schedule_interval(self._ai_tick, 0.1)

    def _stop_ai_tick(self) -> None:
        if self._ai_tick_ev is not None:
            self._ai_tick_ev.cancel()
            self._ai_tick_ev = None

    def _render_ai_reveal(self) -> None:
        shown = " ".join(self._ai_words[: max(0, self._ai_revealed)])
        self._compact_speaker.text = 'AI'
        self._compact_label.text = shown
        if self._ai_bubble_msg_id is not None:
            row = self._messages.get(self._ai_bubble_msg_id)
            if row is not None:
                row.update_text(shown)
        Clock.schedule_once(
            lambda _dt: setattr(self._scroll, 'scroll_y', 0), 0.02
        )

    def _ai_tick(self, _dt) -> None:
        if not self._ai_reveal_active:
            return
        total = len(self._ai_words)
        if total <= 0:
            return
        # Reveal clock starts when the first audio chunk begins playing.
        if self._ai_speak_start_mono <= 0.0:
            return
        elapsed = time.monotonic() - self._ai_speak_start_mono
        dur = self._ai_audio_total_s
        complete = False
        if self._ai_response_done and dur > 0.05:
            # True total audio duration known — pace so the last word lands
            # as the speaker finishes (playback is 1x realtime).
            frac = elapsed / dur
            frac = 1.0 if frac > 1.0 else (0.0 if frac < 0.0 else frac)
            target = int(round(frac * total))
            complete = frac >= 1.0
        else:
            # Audio still streaming — true duration unknown, so pace by the
            # default cadence to avoid racing ahead of the audio.
            target = int(elapsed * _AI_DEFAULT_WPS)
        # Monotonic; clamp to the words we actually have.
        if target < self._ai_revealed:
            target = self._ai_revealed
        if target > total:
            target = total
        if target != self._ai_revealed:
            self._ai_revealed = target
            self._render_ai_reveal()
        if complete and self._ai_revealed >= total:
            self._ai_reveal_active = False
            self._stop_ai_tick()

    def _add_message(self, text: str, is_user: bool) -> str:
        try:
            self._msg_counter += 1
            msg_id = f"msg_{self._msg_counter}"

            self._chat_box.add_widget(_SpeakerLabel(is_user=is_user))
            bubble = _Bubble(
                text=text,
                is_user=is_user,
                overlay_width=self.width or DISPLAY_WIDTH,
            )
            row = _BubbleRow(bubble=bubble)
            self._chat_box.add_widget(row)
            self._messages[msg_id] = row

            # Update compact strip to show this newest message
            self._compact_speaker.text = 'You' if is_user else 'AI'
            self._compact_label.text = text

            # Scroll to bottom (full-mode list)
            Clock.schedule_once(
                lambda _dt: setattr(self._scroll, 'scroll_y', 0), 0.12
            )

            # Auto-show unless suppressed (e.g. on home screen where the
            # say bar handles transcription display instead).
            if not self.suppress_auto_show:
                self.show()

            logger.info(
                "TranscriptionOverlay: added %s bubble #%d (compact=%s, "
                "total_msgs=%d, chat_children=%d)",
                "USER" if is_user else "AI",
                self._msg_counter,
                self._compact,
                len(self._messages),
                len(self._chat_box.children),
            )
            return msg_id
        except Exception:
            logger.exception("TranscriptionOverlay._add_message failed")
            return ""

    def _on_close_touch(self, widget, touch):
        if widget.collide_point(*touch.pos):
            self.hide()
            return True
        return False

    def on_touch_down(self, touch):
        """Consume touches only over the visible chrome so the underlying
        screen stays interactive everywhere else (especially in compact mode
        where most of the screen should remain usable)."""
        if self.opacity < 0.05:
            return False
        if self._compact:
            if self._compact_view.collide_point(*touch.pos):
                super().on_touch_down(touch)
                return True
            return False
        super().on_touch_down(touch)
        return True

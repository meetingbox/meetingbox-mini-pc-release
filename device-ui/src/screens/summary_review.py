"""Meeting Summary screen — dashboard layout (v2).

Replaces the older single-page Figma 659:838 layout with a sidebar-driven
dashboard from the user's reference screenshot. Six tabs in the left rail
(Overview, Key Points, Action Items, Decisions Made, Participants,
Transcript) swap the right-hand content. All tab content is hydrated from
the existing meeting-detail response (``api_client.get_meeting_detail``):

    summary.summary         -> AI Summary card body
    summary.topics          -> Key Topics card / Key Points tab
    summary.action_items    -> Action Items (compact + full)
    summary.decisions       -> Decisions Made (compact + full)
    detail.segments         -> Transcript tab
    meeting.attendees / action_items[*].assignee
                            -> Participants tab (with fallbacks)

The view is uniformly scaled (``scaled_canvas``) so it works on any
display resolution and never overflows text — labels use ``shorten=True``
with multi-line wrapping where appropriate.

Public API preserved for ``main.py`` + ``processing.py``:

- ``__init__``
- ``set_meeting_data(meeting_id, summary_data)``
- ``on_enter`` / ``on_leave``
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle, Triangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from async_helper import run_async
from config import ASSETS_DIR
from screens.base_screen import BaseScreen
from summary_layout import (
    ACCENT_BLUE,
    BACK_BTN,
    BG_RGB,
    CANVAS_H,
    CANVAS_W,
    CARD_BORDER,
    CARD_FILL,
    CARD_RADIUS,
    COL_ACCENT,
    COL_HINT,
    COL_MUTED,
    COL_WHITE,
    CONTENT_AREA,
    FOOTER_FS_RATIO,
    FOOTER_LEFT,
    FOOTER_RIGHT,
    FULL_TAB_CARD,
    META_CARD,
    META_DATE,
    META_DATE_FS_RATIO,
    META_EXPORT,
    META_FILE_ICON,
    META_PARTICIPANTS,
    META_SHARE,
    META_TITLE,
    META_TITLE_FS_RATIO,
    PAGE_TITLE,
    PAGE_TITLE_FS_RATIO,
    PLAY_BORDER,
    PLAY_FILL,
    PLAY_RADIUS,
    PLAY_RECORDING,
    PLAY_RECORDING_FS_RATIO,
    PROG_FILL,
    PROG_RADIUS,
    PROG_TRACK_FILL,
    SECTION_BODY_FS_RATIO,
    SECTION_HINT_FS_RATIO,
    SECTION_TITLE_FS_RATIO,
    SIDEBAR_BORDER,
    SIDEBAR_CARD,
    SIDEBAR_FILL,
    TAB_ACTION_ITEMS,
    TAB_ACTIVE_BORDER,
    TAB_ACTIVE_FILL,
    TAB_ACTIVE_RADIUS,
    TAB_DECISIONS,
    TAB_FS_RATIO,
    TAB_KEY_POINTS,
    TAB_OVERVIEW,
    TAB_PARTICIPANTS,
    TAB_TRANSCRIPT,
    canvas_box,
    content_header,
    font_px,
    kivy_hints,
    scaled_canvas,
)

logger = logging.getLogger(__name__)

_FIGMA = ASSETS_DIR / "summary" / "figma"
_BG = (BG_RGB[0] / 255, BG_RGB[1] / 255, BG_RGB[2] / 255, 1.0)
_FONT_BOLD = "42dot-Sans"

_TAB_IDS: tuple[str, ...] = (
    "overview",
    "key_points",
    "action_items",
    "decisions",
    "participants",
    "transcript",
)

_TAB_BOXES = {
    "overview": TAB_OVERVIEW,
    "key_points": TAB_KEY_POINTS,
    "action_items": TAB_ACTION_ITEMS,
    "decisions": TAB_DECISIONS,
    "participants": TAB_PARTICIPANTS,
    "transcript": TAB_TRANSCRIPT,
}

_TAB_LABELS = {
    "overview": "Overview",
    "key_points": "Key Points",
    "action_items": "Action Items",
    "decisions": "Decisions Made",
    "participants": "Participants",
    "transcript": "Transcript",
}


def _png(name: str) -> str:
    p = _FIGMA / name
    return str(p) if p.is_file() else ""


# Section markers emitted by the backend (``_compose_stored_report_body``)
# and the Claude prompt. The device only renders the "overview" portion in
# the AI Summary card, so the trailing ``DETAILED ACCOUNT`` / ``OPEN
# QUESTIONS`` / ``RISKS / CONCERNS`` sections are stripped before display.
# Mirrors ``frontend/src/utils/parseSummaryReport.ts``.
_DETAILED_SPLIT = re.compile(
    r"(?:^|\r?\n(?:\r?\n)?)\*{0,2}DETAILED ACCOUNT\*{0,2}\s*\r?\n",
    re.IGNORECASE,
)
_OPEN_MARKER = re.compile(
    r"\r?\n\r?\n(?:---\r?\n)?\*{0,2}OPEN QUESTIONS\*{0,2}\s*\r?\n",
    re.IGNORECASE,
)
_RISKS_MARKER = re.compile(
    r"\r?\n\r?\n(?:---\r?\n)?\*{0,2}RISKS\s*/\s*CONCERNS\*{0,2}\s*\r?\n",
    re.IGNORECASE,
)


def _split_on_last_marker(text: str, marker: re.Pattern) -> tuple[str, str]:
    last = None
    for m in marker.finditer(text):
        last = m
    if last is None:
        return text, ""
    return text[: last.start()], text[last.end():]


def _strip_summary_markers(full_text: str) -> str:
    """Return only the narrative overview portion of a composed report.

    The backend stores the AI summary as one long string containing
    ``DETAILED ACCOUNT`` / ``OPEN QUESTIONS`` / ``RISKS / CONCERNS``
    markers. The device's AI Summary card shows the overview narrative
    only — everything after the first detail-account header (or any of
    the trailing markers) is dropped. Also normalises stray surrounding
    whitespace and collapses 3+ blank lines so the text reads cleanly.
    """
    t = (full_text or "").strip()
    if not t:
        return ""
    before_risks, _ = _split_on_last_marker(t, _RISKS_MARKER)
    before_open, _ = _split_on_last_marker(before_risks, _OPEN_MARKER)
    m = _DETAILED_SPLIT.search(before_open)
    if m is not None:
        before_open = before_open[: m.start()]
    out = before_open.strip()
    # Collapse runs of 3+ blank lines to a single blank line.
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def _summary_card_text(full_text: str) -> str:
    """Return text for the Overview AI Summary card.

    Mirrors the web parser's section split. Prefer the leading overview
    narrative when the model provides one, but fall back to the Detailed
    account body when the report starts directly with ``DETAILED ACCOUNT``.
    Without this fallback, short reports that only contain a detailed-account
    section render as the empty "Summary will appear..." placeholder on device.
    """
    t = (full_text or "").strip()
    if not t:
        return ""
    before_risks, _ = _split_on_last_marker(t, _RISKS_MARKER)
    main_part, _ = _split_on_last_marker(before_risks, _OPEN_MARKER)
    m = _DETAILED_SPLIT.search(main_part)
    if m is None:
        out = main_part.strip()
    else:
        overview = main_part[: m.start()].strip()
        detailed = main_part[m.end():].strip()
        out = overview or detailed
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


# ─────────────────────────────────────────────────────────────────────────
# Reusable widgets
# ─────────────────────────────────────────────────────────────────────────


class _ImgBtn(ButtonBehavior, Image):
    """Tappable PNG button."""


class _GradientCard(Widget):
    """Rounded card surface with subtle border."""

    def __init__(
        self,
        *,
        fill: tuple = CARD_FILL,
        border: tuple = CARD_BORDER,
        radius: float = CARD_RADIUS,
        border_width: float = 1.4,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._fill = fill
        self._border = border
        self._radius = radius
        self._border_width = border_width
        with self.canvas:
            Color(*fill)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            Color(*border)
            self._line = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                width=border_width,
            )
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [self._radius]
        self._line.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            self._radius,
        )


class _SidebarTab(ButtonBehavior, Widget):
    """A tab row in the sidebar — rounded pill when active, transparent otherwise.

    Visual layout:

        +--------------------------------------+
        | [glyph]  Label                       |
        +--------------------------------------+

    ``set_active`` toggles the pill background and bold/white text.
    """

    def __init__(
        self,
        *,
        label_text: str,
        on_click,
        glyph: Optional[str] = None,
        fs_ratio: float = TAB_FS_RATIO,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._fs_ratio = fs_ratio
        self._active = False
        with self.canvas.before:
            self._bg_color = Color(*TAB_ACTIVE_FILL)
            self._bg_color.a = 0.0  # invisible until active
            self._bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[TAB_ACTIVE_RADIUS]
            )
            self._border_color = Color(*TAB_ACTIVE_BORDER)
            self._border_color.a = 0.0
            self._border_line = Line(
                rounded_rectangle=(
                    self.x,
                    self.y,
                    self.width,
                    self.height,
                    TAB_ACTIVE_RADIUS,
                ),
                width=1.2,
            )

        # Optional small glyph dot at the left edge — rendered as a small
        # filled circle if no PNG is available. Keeps the layout minimal
        # and avoids extra asset deps.
        self._glyph_label = Label(
            text=glyph or "",
            color=COL_MUTED,
            font_name=_FONT_BOLD,
            bold=True,
            halign="center",
            valign="middle",
            size_hint=(None, None),
        )
        self._glyph_label.bind(size=self._glyph_label.setter("text_size"))

        self._label = Label(
            text=label_text,
            color=COL_MUTED,
            font_name=_FONT_BOLD,
            bold=False,
            halign="left",
            valign="middle",
            shorten=True,
            shorten_from="right",
            size_hint=(None, None),
        )
        self._label.bind(size=self._label.setter("text_size"))

        self.add_widget(self._glyph_label)
        self.add_widget(self._label)
        self.bind(pos=self._sync, size=self._sync)
        if on_click:
            self.bind(on_release=lambda *_: on_click())

    def _sync(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._bg_rect.radius = [TAB_ACTIVE_RADIUS]
        self._border_line.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            TAB_ACTIVE_RADIUS,
        )
        pad_x = max(8, int(self.width * 0.06))
        glyph_w = max(10, int(self.height * 0.42))
        self._glyph_label.pos = (self.x + pad_x, self.y)
        self._glyph_label.size = (glyph_w, self.height)
        self._label.pos = (self.x + pad_x + glyph_w + 8, self.y)
        self._label.size = (max(1, self.width - pad_x - glyph_w - 16), self.height)

    def set_active(self, active: bool) -> None:
        if active == self._active:
            return
        self._active = active
        self._bg_color.a = 1.0 if active else 0.0
        self._border_color.a = 1.0 if active else 0.0
        self._label.color = COL_WHITE if active else COL_MUTED
        self._label.bold = bool(active)


class _PlayRecordingPill(ButtonBehavior, Widget):
    """Bottom-of-sidebar pill: ▶ Play Recording  + duration string.

    Acts as a play/pause toggle button. The leading glyph swaps between
    a play triangle (idle / paused) and two pause bars (playing). The
    text label also updates to "Pause"/"Play Recording" based on state.
    """

    def __init__(self, *, duration_text: str = "", fs_ratio: float = PLAY_RECORDING_FS_RATIO, **kwargs):
        super().__init__(**kwargs)
        self._fs_ratio = fs_ratio
        self._is_playing = False
        with self.canvas.before:
            Color(*PLAY_FILL)
            self._rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[PLAY_RADIUS]
            )
            Color(*PLAY_BORDER)
            self._line = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, PLAY_RADIUS),
                width=1.2,
            )
            self._tri_color = Color(*ACCENT_BLUE)
            self._triangle = Triangle(points=[0, 0, 0, 0, 0, 0])
            self._pause_color = Color(*ACCENT_BLUE)
            # Two pause bars — drawn but kept zero-size while idle so
            # only the triangle is visible.
            self._pause_bar_l = Rectangle(pos=self.pos, size=(0, 0))
            self._pause_bar_r = Rectangle(pos=self.pos, size=(0, 0))
        self._label_main = Label(
            text="Play Recording",
            color=COL_WHITE,
            font_name=_FONT_BOLD,
            bold=True,
            halign="left",
            valign="middle",
            size_hint=(None, None),
            shorten=True,
            shorten_from="right",
        )
        self._label_main.bind(size=self._label_main.setter("text_size"))
        self._label_dur = Label(
            text=duration_text,
            color=COL_HINT,
            font_name=_FONT_BOLD,
            bold=False,
            halign="right",
            valign="middle",
            size_hint=(None, None),
        )
        self._label_dur.bind(size=self._label_dur.setter("text_size"))
        self.add_widget(self._label_main)
        self.add_widget(self._label_dur)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [PLAY_RADIUS]
        self._line.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            PLAY_RADIUS,
        )
        # Play triangle / pause bars on the left side. Only one of
        # them is visible at any time (driven by ``set_playing``).
        tri_h = self.height * 0.4
        tri_w = tri_h * 0.85
        cx = self.x + max(16, self.width * 0.08)
        cy = self.y + self.height / 2
        if self._is_playing:
            self._triangle.points = [0, 0, 0, 0, 0, 0]
            bar_w = tri_w * 0.35
            gap = tri_w * 0.30
            self._pause_bar_l.pos = (cx, cy - tri_h / 2)
            self._pause_bar_l.size = (bar_w, tri_h)
            self._pause_bar_r.pos = (cx + bar_w + gap, cy - tri_h / 2)
            self._pause_bar_r.size = (bar_w, tri_h)
        else:
            self._triangle.points = [
                cx, cy + tri_h / 2,
                cx, cy - tri_h / 2,
                cx + tri_w, cy,
            ]
            self._pause_bar_l.size = (0, 0)
            self._pause_bar_r.size = (0, 0)
        # Labels — give the main label more horizontal share so the
        # full "Play Recording" / "Pause" text fits without ellipsising
        # on the device. The duration string ("12:34") only needs ~35 %.
        label_x = cx + tri_w + 10
        label_w = self.width - (label_x - self.x) - 8
        main_share = 0.66
        self._label_main.pos = (label_x, self.y)
        self._label_main.size = (max(1, label_w * main_share), self.height)
        self._label_dur.pos = (label_x + label_w * main_share, self.y)
        self._label_dur.size = (max(1, label_w * (1.0 - main_share)) - 4, self.height)

    def set_duration(self, text: str) -> None:
        self._label_dur.text = text or ""

    def set_playing(self, playing: bool) -> None:
        self._is_playing = bool(playing)
        self._label_main.text = "Pause" if self._is_playing else "Play Recording"
        # Re-layout the glyph to switch triangle ↔ pause bars.
        self._sync()


class _ProgressBar(Widget):
    """Thin horizontal progress bar with a rounded track + filled portion."""

    def __init__(self, *, value: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        self._value = max(0.0, min(1.0, value))
        with self.canvas:
            Color(*PROG_TRACK_FILL)
            self._track = RoundedRectangle(pos=self.pos, size=self.size, radius=[PROG_RADIUS])
            Color(*PROG_FILL)
            self._fill = RoundedRectangle(pos=self.pos, size=(0, 0), radius=[PROG_RADIUS])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._track.pos = self.pos
        self._track.size = self.size
        self._track.radius = [PROG_RADIUS]
        fw = max(0.0, min(self.width, self.width * self._value))
        self._fill.pos = self.pos
        self._fill.size = (fw, self.height)
        self._fill.radius = [PROG_RADIUS]

    def set_value(self, v: float) -> None:
        self._value = max(0.0, min(1.0, v))
        self._sync()


class _Dot(Widget):
    """Small filled circle used as a row bullet."""

    def __init__(self, *, color: tuple = COL_ACCENT, **kwargs):
        super().__init__(**kwargs)
        self._color = color
        with self.canvas:
            Color(*color)
            self._ell = RoundedRectangle(pos=self.pos, size=self.size, radius=[999])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        d = min(self.width, self.height)
        cx = self.x + (self.width - d) / 2
        cy = self.y + (self.height - d) / 2
        self._ell.pos = (cx, cy)
        self._ell.size = (d, d)
        self._ell.radius = [d / 2]


class _AccentLink(ButtonBehavior, Label):
    """Clickable blue text link (used for "View all" jumps)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("color", COL_ACCENT)
        kwargs.setdefault("font_name", _FONT_BOLD)
        kwargs.setdefault("bold", True)
        kwargs.setdefault("halign", "right")
        kwargs.setdefault("valign", "middle")
        super().__init__(**kwargs)
        self.bind(size=self.setter("text_size"))


class _ScrollText(ScrollView):
    """Wrapping multi-line text label inside a vertical ScrollView.

    Replaces the single ``Label`` previously used for the AI Summary
    body — that label was hard-capped at ``max_lines=3`` so realistic
    summaries truncated with an ellipsis on the device. The new
    behaviour wraps the text to the card width and lets the user scroll
    within the card when the body exceeds the visible height.

    Public API:
      * ``text`` property — set/get the body string.
      * ``color`` property — text colour (passed through to the label).
      * ``font_size`` property — kept for the resize loop. We treat the
        ``_fs_ratio`` attribute the same way as other helpers do.
    """

    def __init__(self, *, fs_ratio: float, color, font_name: str, **kwargs):
        super().__init__(
            do_scroll_x=False, do_scroll_y=True,
            bar_width=2, bar_color=(1, 1, 1, 0.25),
            bar_inactive_color=(1, 1, 1, 0.10),
            scroll_type=["bars", "content"],
            **kwargs,
        )
        self._label = Label(
            text="",
            font_name=font_name,
            color=color,
            halign="left",
            valign="top",
            markup=False,
            size_hint=(1, None),
        )
        self._fs_ratio = fs_ratio
        self._label._fs_ratio = fs_ratio  # noqa: SLF001
        self.add_widget(self._label)
        self.bind(size=self._sync_width)
        self._label.bind(texture_size=self._sync_height)

    def _sync_width(self, *_args):
        self._label.text_size = (self.width, None)

    def _sync_height(self, *_args):
        self._label.height = max(self._label.texture_size[1], self.height)

    @property
    def text(self) -> str:
        return self._label.text

    @text.setter
    def text(self, value: str) -> None:
        self._label.text = value or ""

    @property
    def color(self):
        return self._label.color

    @color.setter
    def color(self, value):
        self._label.color = value

    @property
    def font_size(self):
        return self._label.font_size

    @font_size.setter
    def font_size(self, value):
        self._label.font_size = value


class _OverviewCard(BoxLayout):
    """Auto-height card used by the scrollable Overview dashboard."""

    def __init__(self, *, min_height: float = 96.0, **kwargs):
        super().__init__(
            orientation="vertical",
            size_hint_y=None,
            padding=(24, 18, 24, 18),
            spacing=10,
            **kwargs,
        )
        self._min_height = min_height
        with self.canvas.before:
            Color(*CARD_FILL)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[CARD_RADIUS])
            Color(*CARD_BORDER)
            self._line = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, CARD_RADIUS),
                width=1.2,
            )
        self.bind(pos=self._sync_canvas, size=self._sync_canvas)
        self.bind(minimum_height=self._sync_height)
        self._sync_height()

    def _sync_canvas(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [CARD_RADIUS]
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, CARD_RADIUS)

    def _sync_height(self, *_):
        self.height = max(self._min_height, self.minimum_height)


# ─────────────────────────────────────────────────────────────────────────
# Screen
# ─────────────────────────────────────────────────────────────────────────


class SummaryReviewScreen(BaseScreen):
    """Dashboard-style meeting summary review."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.meeting_id: Optional[str] = None
        self._summary_data: dict = {}
        self._segments: list[dict] = []
        self._meeting_title = "Meeting"
        self._duration_min = 0
        self._participant_count = 0
        self._attendees: list[str] = []
        self._action_items: list[dict] = []
        # Agentic "follow-ups" — actions persisted in the backend
        # ``actions`` table with stable IDs that can be executed via
        # ``execute_action``. Fetched alongside the meeting detail and
        # rendered as Send-email / Add-to-calendar rows in the Action
        # Items tab.
        self._agentic_actions: list[dict] = []
        self._rendered_agentic_action_ids: set[str] = set()
        self._selected_agentic_action_ids: set[str] = set()
        self._decisions: list[str] = []
        self._topics: list[dict] = []
        self._sidebar_tabs: dict[str, _SidebarTab] = {}
        self._tab_widgets: dict[str, list[Widget]] = {tid: [] for tid in _TAB_IDS}
        self._active_tab = "overview"
        # Resize-time font scaling: a list of (label, fs_ratio) pairs that
        # we apply on every layout pass.
        self._scaled_labels: list[tuple[Label, float]] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------
    def _build_ui(self):
        self._root = FloatLayout(size_hint=(1, 1))
        with self._root.canvas.before:
            Color(*_BG)
            self._bg = Rectangle(pos=self._root.pos, size=self._root.size)
        self._root.bind(
            pos=lambda w, _v: setattr(self._bg, "pos", w.pos),
            size=self._on_root_resize,
        )

        anchor = AnchorLayout(anchor_x="center", anchor_y="center", size_hint=(1, 1))
        self._root.add_widget(anchor)
        self._canvas = FloatLayout(size_hint=(None, None))
        anchor.add_widget(self._canvas)

        self._build_header()
        self._build_meta_card()
        self._build_sidebar()
        self._build_footer()

        # Build the Overview tab eagerly so the first paint shows real content.
        self._show_tab("overview")

        self.add_widget(self._root)
        Clock.schedule_once(lambda _dt: self._on_root_resize(self._root, self._root.size), 0)

    def _build_header(self):
        self._add_img_btn("btn_back.png", BACK_BTN, on_release=lambda *_: self._on_back())
        self._add_label(
            "Meeting Summary",
            PAGE_TITLE,
            PAGE_TITLE_FS_RATIO,
            COL_WHITE,
            bold=True,
            halign="left",
        )

    def _build_meta_card(self):
        self._canvas.add_widget(_GradientCard(**kivy_hints(META_CARD)))
        self._add_image("icon_file_box.png", META_FILE_ICON)
        self.meta_title_label = self._add_label(
            "Product Sync",
            META_TITLE,
            META_TITLE_FS_RATIO,
            COL_WHITE,
            bold=True,
            halign="left",
        )
        self.meta_date_label = self._add_label(
            "—",
            META_DATE,
            META_DATE_FS_RATIO,
            COL_MUTED,
            halign="left",
        )
        self._chip_participants_widget = self._add_image(
            "chip_participants.png", META_PARTICIPANTS,
        )
        self._add_img_btn("btn_export.png", META_EXPORT, on_release=lambda *_: self._on_export())
        self._add_img_btn("btn_share.png", META_SHARE, on_release=lambda *_: self._on_share())

    def _build_sidebar(self):
        self._canvas.add_widget(
            _GradientCard(
                fill=SIDEBAR_FILL,
                border=SIDEBAR_BORDER,
                radius=CARD_RADIUS,
                **kivy_hints(SIDEBAR_CARD),
            )
        )

        for tid in _TAB_IDS:
            tab = _SidebarTab(
                label_text=_TAB_LABELS[tid],
                glyph="•",
                on_click=lambda tid=tid: self._show_tab(tid),
                **kivy_hints(_TAB_BOXES[tid]),
            )
            self._scaled_labels.append((tab._label, TAB_FS_RATIO))
            self._scaled_labels.append((tab._glyph_label, TAB_FS_RATIO))
            self._sidebar_tabs[tid] = tab
            self._canvas.add_widget(tab)

        self.play_pill = _PlayRecordingPill(
            duration_text="",
            **kivy_hints(PLAY_RECORDING),
        )
        self._scaled_labels.append((self.play_pill._label_main, PLAY_RECORDING_FS_RATIO))
        self._scaled_labels.append((self.play_pill._label_dur, SECTION_HINT_FS_RATIO))
        self.play_pill.bind(on_release=lambda *_: self._on_play_recording())
        self._canvas.add_widget(self.play_pill)

    def _build_footer(self):
        self.footer_left_label = self._add_label(
            "Created: —",
            FOOTER_LEFT,
            FOOTER_FS_RATIO,
            COL_HINT,
            halign="left",
        )
        self.footer_right_label = self._add_label(
            "Generated by AI",
            FOOTER_RIGHT,
            FOOTER_FS_RATIO,
            COL_HINT,
            halign="right",
        )

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------
    def _show_tab(self, tab_id: str) -> None:
        if tab_id not in _TAB_IDS:
            return
        # Remove currently-shown tab widgets (defensively skip None / unparented).
        for w in self._tab_widgets[self._active_tab]:
            if w is not None and w.parent is self._canvas:
                self._canvas.remove_widget(w)
        self._active_tab = tab_id

        widgets = self._tab_widgets[tab_id]
        if not widgets:
            widgets = [w for w in self._build_tab(tab_id) if w is not None]
            self._tab_widgets[tab_id] = widgets
        for w in widgets:
            if w is not None and w.parent is None:
                self._canvas.add_widget(w)

        for tid, tab in self._sidebar_tabs.items():
            tab.set_active(tid == tab_id)

        Clock.schedule_once(
            lambda _dt: self._on_root_resize(self._root, self._root.size), 0
        )

    def _build_tab(self, tab_id: str) -> list[Widget]:
        builder = {
            "overview": self._build_overview,
            "key_points": self._build_key_points,
            "action_items": self._build_action_items_full,
            "decisions": self._build_decisions_full,
            "participants": self._build_participants,
            "transcript": self._build_transcript,
        }[tab_id]
        return builder()

    # ------------------------------------------------------------------
    # Overview tab
    # ------------------------------------------------------------------
    def _overview_label(
        self,
        text: str,
        *,
        ratio: float = SECTION_BODY_FS_RATIO,
        color: tuple = COL_MUTED,
        bold: bool = False,
        halign: str = "left",
    ) -> Label:
        lbl = Label(
            text=text or "",
            color=color,
            font_name=_FONT_BOLD,
            bold=bold,
            halign=halign,
            valign="top",
            markup=False,
            shorten=False,
            size_hint_y=None,
            size_hint_x=1,
            font_hinting="light",
            font_kerning=True,
        )
        lbl.bind(
            width=lambda w, *_: setattr(w, "text_size", (max(1, w.width), None)),
            texture_size=lambda w, ts: setattr(w, "height", max(24, ts[1] + 4)),
        )
        self._scaled_labels.append((lbl, ratio))
        return lbl

    def _overview_card(
        self,
        title: str,
        *,
        glyph: str = "◆",
        min_height: float = 96.0,
        tab_id: Optional[str] = None,
    ) -> _OverviewCard:
        card = _OverviewCard(min_height=min_height)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=34, spacing=10)
        icon = Label(
            text=glyph,
            color=COL_ACCENT,
            font_name=_FONT_BOLD,
            bold=True,
            halign="center",
            valign="middle",
            size_hint=(None, 1),
            width=28,
        )
        icon.bind(size=icon.setter("text_size"))
        self._scaled_labels.append((icon, SECTION_TITLE_FS_RATIO))
        header.add_widget(icon)
        header.add_widget(
            self._overview_label(
                title,
                ratio=SECTION_TITLE_FS_RATIO,
                color=COL_WHITE,
                bold=True,
            )
        )
        if tab_id:
            link = _AccentLink(
                text="View all",
                size_hint=(None, 1),
                width=110,
                halign="right",
            )
            self._scaled_labels.append((link, SECTION_HINT_FS_RATIO))
            link.bind(on_release=lambda *_args, tid=tab_id: self._show_tab(tid))
            header.add_widget(link)
        card.add_widget(header)
        return card

    def _overview_summary_text(self) -> str:
        data = self._summary_data or {}
        summary = data.get("summary")
        if isinstance(summary, dict):
            summary_text = (summary.get("summary") or "").strip()
        else:
            summary_text = (summary or "").strip()
        return _summary_card_text(summary_text)

    def _build_overview(self) -> list[Widget]:
        widgets: list[Widget] = []
        scroll = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            scroll_type=["bars", "content"],
            bar_width=6,
            **kivy_hints(CONTENT_AREA),
        )
        container = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            spacing=12,
            padding=(0, 0, 8, 0),
        )
        container.bind(minimum_height=container.setter("height"))
        scroll.bind(width=lambda sv, width: setattr(container, "width", max(1, width - 8)))
        scroll.add_widget(container)
        widgets.append(scroll)

        summary_text = self._overview_summary_text()
        ai_card = self._overview_card("AI Summary", glyph="✧", min_height=116.0)
        ai_card.add_widget(
            self._overview_label(
                summary_text or "Summary will appear here once processing finishes.",
                color=COL_HINT,
            )
        )
        container.add_widget(ai_card)

        if self._topics:
            key_card = self._overview_card(
                "Key Topics",
                glyph="◆",
                min_height=112.0,
                tab_id="key_points",
            )
            for t in self._topics:
                row = BoxLayout(orientation="vertical", size_hint_y=None, height=52, spacing=6)
                top = BoxLayout(orientation="horizontal", size_hint_y=None, height=26)
                top.add_widget(
                    self._overview_label(
                        (t.get("name") or "—").strip(),
                        color=COL_WHITE,
                        bold=True,
                    )
                )
                pct = self._overview_label(
                    f"{max(0, min(100, int(t.get('value', 0))))}%",
                    ratio=SECTION_HINT_FS_RATIO,
                    color=COL_HINT,
                    halign="right",
                )
                pct.size_hint_x = None
                pct.width = 76
                top.add_widget(pct)
                row.add_widget(top)
                bar_wrap = BoxLayout(size_hint_y=None, height=8)
                bar_wrap.add_widget(
                    _ProgressBar(value=max(0, min(100, int(t.get("value", 0)))) / 100.0)
                )
                row.add_widget(bar_wrap)
                key_card.add_widget(row)
            container.add_widget(key_card)

        if self._action_items:
            actions_card = self._overview_card(
                "Action Items",
                glyph="✓",
                min_height=112.0,
                tab_id="action_items",
            )
            for item in self._action_items:
                task = (item.get("task") or "").strip()
                if not task:
                    continue
                actions_card.add_widget(
                    self._overview_label("• " + task, color=COL_WHITE, bold=True)
                )
                meta = "  ·  ".join(
                    s for s in (
                        item.get("assignee") or "",
                        self._format_short_date(item.get("due_date") or ""),
                    )
                    if s
                )
                if meta:
                    actions_card.add_widget(
                        self._overview_label(meta, ratio=SECTION_HINT_FS_RATIO, color=COL_HINT)
                    )
            container.add_widget(actions_card)

        if self._decisions:
            decisions_card = self._overview_card(
                "Decisions Made",
                glyph="⌁",
                min_height=112.0,
                tab_id="decisions",
            )
            for decision in self._decisions:
                decisions_card.add_widget(
                    self._overview_label("• " + decision, color=COL_MUTED)
                )
            container.add_widget(decisions_card)
        return widgets

    def _render_overview_data(self) -> None:
        # Overview is now rebuilt as a dynamic scrollable panel whenever
        # meeting data changes, so there are no fixed card labels to update
        # in place.
        return

    # ------------------------------------------------------------------
    # Full-card tabs (Key Points / Action Items / Decisions / Participants / Transcript)
    # ------------------------------------------------------------------
    def _build_full_card(
        self,
        *,
        icon_filename: Optional[str],
        title_text: str,
    ) -> tuple[list[Widget], ScrollView, BoxLayout]:
        widgets: list[Widget] = []
        widgets.append(_GradientCard(**kivy_hints(FULL_TAB_CARD)))
        icon_box, title_box = content_header(FULL_TAB_CARD, icon_w=32.0, title_w=400.0)
        if icon_filename:
            img = self._make_image(icon_filename, icon_box)
            if img is not None:
                widgets.append(img)
        widgets.append(
            self._make_label(
                title_text,
                title_box,
                SECTION_TITLE_FS_RATIO,
                COL_WHITE,
                bold=True,
                halign="left",
            )
        )

        # ScrollView spans the card interior below the header.
        sv_box = canvas_box(
            FULL_TAB_CARD["x"] * CANVAS_W + 20.0,
            FULL_TAB_CARD["y_top"] * CANVAS_H + 72.0,
            FULL_TAB_CARD["w"] * CANVAS_W - 40.0,
            FULL_TAB_CARD["h"] * CANVAS_H - 92.0,
        )
        scroll = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            scroll_type=["bars", "content"],
            bar_width=6,
            **kivy_hints(sv_box),
        )
        container = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=8,
            padding=(4, 4, 4, 4),
        )
        container.bind(minimum_height=container.setter("height"))
        scroll.add_widget(container)
        widgets.append(scroll)
        return widgets, scroll, container

    def _make_row_label(
        self,
        text: str,
        *,
        bold: bool = False,
        color: tuple = COL_MUTED,
        halign: str = "left",
    ) -> Label:
        lbl = Label(
            text=text,
            color=color,
            font_name=_FONT_BOLD,
            bold=bold,
            halign=halign,
            valign="middle",
            shorten=False,
            size_hint_y=None,
            size_hint_x=1,
        )
        lbl.bind(
            width=lambda w, *_: setattr(w, "text_size", (w.width - 8, None)),
            texture_size=lambda w, ts: setattr(w, "height", max(28, ts[1] + 6)),
        )
        return lbl

    def _build_key_points(self) -> list[Widget]:
        widgets, _scroll, container = self._build_full_card(
            icon_filename=None,
            title_text="Key Points",
        )
        if not self._topics:
            ph = self._make_row_label(
                "Key topics will appear here once the AI report finishes generating.",
                color=COL_HINT,
            )
            container.add_widget(ph)
        else:
            for t in self._topics:
                row = BoxLayout(orientation="horizontal", size_hint_y=None, height=58)
                left = BoxLayout(orientation="vertical", spacing=4)
                name = self._make_row_label((t.get("name") or "—").strip(), bold=True, color=COL_WHITE)
                left.add_widget(name)
                bar_wrap = BoxLayout(size_hint_y=None, height=10)
                pb = _ProgressBar(value=max(0, min(100, int(t.get("value", 0)))) / 100.0)
                bar_wrap.add_widget(pb)
                left.add_widget(bar_wrap)
                row.add_widget(left)
                pct = self._make_row_label(
                    f"{int(t.get('value', 0))}%",
                    halign="right",
                    color=COL_HINT,
                )
                pct.size_hint_x = None
                pct.width = 80
                row.add_widget(pct)
                container.add_widget(row)
        return widgets

    def _build_action_items_full(self) -> list[Widget]:
        widgets, scroll, container = self._build_full_card(
            icon_filename="action_items_icon.png",
            title_text="Action Items",
        )
        # Leave room for the bulk action buttons at the bottom-right of
        # the Action Items card.
        scroll_box = canvas_box(
            FULL_TAB_CARD["x"] * CANVAS_W + 20.0,
            FULL_TAB_CARD["y_top"] * CANVAS_H + 72.0,
            FULL_TAB_CARD["w"] * CANVAS_W - 40.0,
            FULL_TAB_CARD["h"] * CANVAS_H - 154.0,
        )
        scroll.size_hint = (scroll_box["w"], scroll_box["h"])
        scroll.pos_hint = {"x": scroll_box["x"], "y": 1.0 - scroll_box["y_top"] - scroll_box["h"]}
        if not self._action_items and not self._agentic_actions:
            container.add_widget(
                self._make_row_label("No action items captured for this meeting.", color=COL_HINT)
            )
            return widgets
        rendered_action_ids: set[str] = set()
        for i, item in enumerate(self._action_items):
            linked_action = self._match_agentic_action_for_item(item, rendered_action_ids)
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=72,
                padding=(4, 6, 4, 6),
                spacing=10,
            )
            action_id = str((linked_action or {}).get("id") or "")
            selected = bool(action_id and action_id in self._selected_agentic_action_ids)
            check = _ImgBtn(
                source=_png(
                    "action_check_done.png" if selected or (not action_id and item.get("completed")) else "action_check_pending.png"
                ),
                allow_stretch=True,
                keep_ratio=True,
                fit_mode="contain",
                size_hint=(None, None),
                size=(32, 32),
                pos_hint={"center_y": 0.5},
            )
            if action_id:
                check.bind(on_release=lambda _w, aid=action_id: self._toggle_action_selection(aid))
            else:
                check.bind(on_release=lambda _w, idx=i: self._toggle_action(idx))
            row.add_widget(check)
            row.add_widget(
                _Dot(
                    color=COL_ACCENT,
                    size_hint=(None, None),
                    size=(10, 10),
                    pos_hint={"center_y": 0.5},
                )
            )

            mid = BoxLayout(orientation="vertical", spacing=2)
            task = self._make_row_label(item.get("task", ""), bold=True, color=COL_WHITE)
            sub_parts: list[str] = []
            if item.get("assignee"):
                sub_parts.append(str(item["assignee"]))
            if item.get("due_date"):
                sd = self._format_short_date(str(item["due_date"]))
                if sd:
                    sub_parts.append(sd)
            if item.get("type"):
                sub_parts.append(str(item["type"]).replace("_", " ").title())
            sub = self._make_row_label("  ·  ".join(sub_parts), color=COL_HINT)
            mid.add_widget(task)
            mid.add_widget(sub)
            row.add_widget(mid)
            if linked_action is not None:
                rendered_action_ids.add(action_id)
                btn = self._make_execute_button(linked_action)
                if btn is not None:
                    row.add_widget(btn)
            elif self._item_connector(item) == "calendar":
                btn = self._make_summary_calendar_button(item)
                if btn is not None:
                    row.add_widget(btn)
            container.add_widget(row)

        # ── Follow-ups sub-list ───────────────────────────────────
        # Agentic actions persisted server-side with stable IDs are
        # rendered below the LLM-extracted items, with per-row draft /
        # calendar buttons that execute via the backend.
        if self._agentic_actions:
            remaining = [
                action for action in self._agentic_actions
                if str(action.get("id") or "") not in rendered_action_ids
            ]
            if remaining:
                container.add_widget(
                    self._make_row_label("Follow-ups", bold=True, color=COL_WHITE)
                )
            for action in remaining:
                container.add_widget(self._build_followup_row(action))
        self._rendered_agentic_action_ids = rendered_action_ids
        bulk = self._make_bulk_action_buttons()
        if bulk is not None:
            widgets.append(bulk)
        return widgets

    @staticmethod
    def _action_connector(action: dict) -> str:
        connector = (action.get("connector_target") or "").strip().lower()
        kind = (action.get("kind") or action.get("type") or "").strip().lower()
        if connector in {"gmail", "calendar"}:
            return connector
        if kind in {"followup_email", "email_draft", "email", "send_email"}:
            return "gmail"
        if kind in {
            "schedule_followup", "calendar_invite", "calendar", "calendar_event", "schedule",
        }:
            return "calendar"
        return ""

    @staticmethod
    def _item_connector(item: dict) -> str:
        typ = (item.get("type") or "").strip().lower()
        task = (item.get("task") or "").strip().lower()
        haystack = f"{typ} {task}"
        if typ in {"email_draft", "followup_email", "email", "send_email"}:
            return "gmail"
        if typ in {"calendar_invite", "schedule_followup", "calendar", "calendar_event", "schedule"}:
            return "calendar"
        if "calendar" in haystack or "schedule" in haystack or "meeting invite" in haystack:
            return "calendar"
        if "email" in haystack or "mail" in haystack:
            return "gmail"
        return ""

    def _match_agentic_action_for_item(self, item: dict, used_ids: set[str]) -> Optional[dict]:
        target = self._item_connector(item)
        if not target:
            return None
        task = (item.get("task") or "").strip().lower()
        candidates = [
            action for action in self._agentic_actions
            if str(action.get("id") or "") not in used_ids
            and self._action_connector(action) == target
        ]
        if not candidates:
            return None
        for action in candidates:
            title = str(action.get("title") or action.get("description") or "").strip().lower()
            if task and (task in title or title in task):
                return action
        return candidates[0]

    def _make_summary_calendar_button(self, item: dict):
        from kivy.uix.button import Button

        btn = Button(
            text="Add to calendar",
            size_hint=(None, None),
            size=(160, 40),
            pos_hint={"center_y": 0.5},
            background_normal="",
            background_color=ACCENT_BLUE,
            color=COL_WHITE,
            font_name=_FONT_BOLD,
            bold=True,
        )
        btn.bind(on_release=lambda _w, b=btn, it=dict(item): self._execute_summary_calendar_item(it, b))
        return btn

    def _execute_summary_calendar_item(self, item: dict, btn) -> None:
        if not self.meeting_id:
            return
        try:
            btn.disabled = True
            btn.text = "Working..."
        except Exception:  # noqa: BLE001
            pass

        async def _run():
            ok = False
            error_text = ""
            action: Optional[dict] = None
            try:
                generated = await self.backend.generate_actions(self.meeting_id)
                if isinstance(generated, list):
                    self._agentic_actions = [
                        a for a in generated if isinstance(a, dict) and a.get("id")
                    ]
                    self._sync_default_action_selection()
                    action = self._match_agentic_action_for_item(item, set())
                if action is None:
                    due_date = (item.get("due_date") or "").strip()
                    if not due_date:
                        raise RuntimeError("Calendar action needs a due date.")
                    action = await self.backend.create_manual_action(
                        self.meeting_id,
                        {
                            "connector": "calendar",
                            "title": item.get("task") or "Follow-up",
                            "description": item.get("task") or "",
                            "event_title": item.get("task") or "Follow-up",
                            "suggested_date": due_date,
                            "suggested_time": "10:00",
                            "duration_minutes": 30,
                            "attendees": [],
                        },
                    )
                    if isinstance(action, dict) and action.get("id"):
                        self._agentic_actions.append(action)
                action_id = str((action or {}).get("id") or "")
                if not action_id:
                    raise RuntimeError("Calendar action could not be prepared.")
                await self.backend.execute_action(action_id)
                self._mark_action_executed(action_id)
                ok = True
            except Exception as exc:  # noqa: BLE001
                logger.exception("summary calendar action failed")
                error_text = str(exc) or "Retry"

            def _apply(_dt):
                try:
                    if ok:
                        btn.text = "Added"
                        btn.background_color = (0.16, 0.66, 0.30, 1)
                    else:
                        btn.text = "Need date" if "due date" in error_text.lower() else "Retry"
                        btn.disabled = False
                except Exception:  # noqa: BLE001
                    pass
                if ok and self._active_tab == "action_items":
                    self._refresh_after_data_change()

            Clock.schedule_once(_apply, 0)

        run_async(_run())

    def _make_execute_button(self, action: dict):
        from kivy.uix.button import Button

        connector = self._action_connector(action)
        if connector not in {"gmail", "calendar"}:
            return None
        executed = bool(action.get("executed_at") or action.get("status") == "executed")
        is_email = connector == "gmail"
        if executed:
            return Button(
                text="Done" if is_email else "Added",
                disabled=True,
                size_hint=(None, None),
                size=(130 if is_email else 160, 40),
                pos_hint={"center_y": 0.5},
                background_normal="",
                background_color=(0.16, 0.66, 0.30, 1),
                color=COL_WHITE,
                font_name=_FONT_BOLD,
                bold=True,
            )
        action_id = str(action.get("id") or "")

        def _button(text: str, width: int, *, create_draft: bool, success_text: str) -> Button:
            btn = Button(
                text=text,
                size_hint=(None, None),
                size=(width, 40),
                pos_hint={"center_y": 0.5},
                background_normal="",
                background_color=ACCENT_BLUE,
                color=COL_WHITE,
                font_name=_FONT_BOLD,
                bold=True,
            )
            btn.bind(
                on_release=lambda _w, aid=action_id, b=btn: self._execute_followup(
                    aid, b, create_draft=create_draft, success_text=success_text,
                )
            )
            return btn

        if is_email:
            buttons = BoxLayout(
                orientation="horizontal",
                size_hint=(None, None),
                size=(230, 40),
                spacing=8,
                pos_hint={"center_y": 0.5},
            )
            buttons.add_widget(_button("Send", 96, create_draft=False, success_text="Sent"))
            buttons.add_widget(_button("Draft", 118, create_draft=True, success_text="Draft saved"))
            return buttons
        return _button("Add to calendar", 160, create_draft=False, success_text="Added")

    def _make_bulk_action_buttons(self) -> Optional[Widget]:
        from kivy.uix.button import Button

        if not self._pending_executable_actions():
            return None
        box = BoxLayout(
            orientation="horizontal",
            spacing=10,
            **kivy_hints(canvas_box(
                FULL_TAB_CARD["x"] * CANVAS_W + FULL_TAB_CARD["w"] * CANVAS_W - 398.0,
                FULL_TAB_CARD["y_top"] * CANVAS_H + FULL_TAB_CARD["h"] * CANVAS_H - 66.0,
                360.0,
                44.0,
            )),
        )

        def _button(text: str, *, selected_only: bool) -> Button:
            btn = Button(
                text=text,
                background_normal="",
                background_color=ACCENT_BLUE,
                color=COL_WHITE,
                font_name=_FONT_BOLD,
                bold=True,
            )
            btn.bind(
                on_release=lambda _w, b=btn: self._execute_bulk_actions(
                    selected_only=selected_only,
                    source_button=b,
                )
            )
            return btn

        box.add_widget(_button("Execute selected", selected_only=True))
        box.add_widget(_button("Execute all", selected_only=False))
        return box

    def _pending_executable_actions(self) -> list[dict]:
        actions: list[dict] = []
        seen: set[str] = set()
        for action in self._agentic_actions:
            aid = str(action.get("id") or "")
            if not aid or aid in seen:
                continue
            if self._action_connector(action) not in {"gmail", "calendar"}:
                continue
            if action.get("executed_at") or action.get("status") == "executed":
                continue
            seen.add(aid)
            actions.append(action)
        return actions

    def _sync_default_action_selection(self) -> None:
        pending_ids = {str(a.get("id") or "") for a in self._pending_executable_actions()}
        pending_ids.discard("")
        self._selected_agentic_action_ids.intersection_update(pending_ids)
        for aid in pending_ids:
            if aid not in self._selected_agentic_action_ids:
                self._selected_agentic_action_ids.add(aid)

    def _toggle_action_selection(self, action_id: str) -> None:
        if not action_id:
            return
        if action_id in self._selected_agentic_action_ids:
            self._selected_agentic_action_ids.remove(action_id)
        else:
            self._selected_agentic_action_ids.add(action_id)
        if self._active_tab == "action_items":
            self._refresh_after_data_change()

    def _mark_action_executed(self, action_id: str) -> None:
        self._selected_agentic_action_ids.discard(action_id)
        for action in self._agentic_actions:
            if str(action.get("id") or "") == action_id:
                action["status"] = "executed"
                action["executed_at"] = action.get("executed_at") or "now"
                break

    def _execute_bulk_actions(self, *, selected_only: bool, source_button) -> None:
        pending = self._pending_executable_actions()
        if selected_only:
            pending = [
                action for action in pending
                if str(action.get("id") or "") in self._selected_agentic_action_ids
            ]
        if not pending:
            try:
                source_button.text = "None selected"
            except Exception:  # noqa: BLE001
                pass
            return
        try:
            source_button.disabled = True
            source_button.text = "Working..."
        except Exception:  # noqa: BLE001
            pass

        async def _run():
            ok_count = 0
            for action in pending:
                action_id = str(action.get("id") or "")
                if not action_id:
                    continue
                create_draft = self._action_connector(action) == "gmail"
                try:
                    await self.backend.execute_action(action_id, create_draft=create_draft)
                    ok_count += 1
                    self._mark_action_executed(action_id)
                except Exception:  # noqa: BLE001
                    logger.exception("bulk execute_action failed for %s", action_id)

            def _apply(_dt):
                try:
                    source_button.text = f"Done {ok_count}/{len(pending)}"
                    source_button.background_color = (0.16, 0.66, 0.30, 1)
                    source_button.disabled = False
                except Exception:  # noqa: BLE001
                    pass
                self._refresh_after_data_change()

            Clock.schedule_once(_apply, 0)

        run_async(_run())

    def _build_followup_row(self, action: dict) -> Widget:
        """One Follow-ups row: title + sub + draft/calendar pill button."""

        connector = self._action_connector(action)
        is_email = connector == "gmail"
        is_cal = connector == "calendar"
        title = (
            action.get("title")
            or action.get("description")
            or action.get("task")
            or "Follow-up"
        )
        executed = bool(action.get("executed_at") or action.get("status") == "executed")

        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=64,
            padding=(4, 6, 4, 6),
            spacing=10,
        )
        action_id = str(action.get("id") or "")
        if action_id and not executed and (is_email or is_cal):
            selected = action_id in self._selected_agentic_action_ids
            check = _ImgBtn(
                source=_png("action_check_done.png" if selected else "action_check_pending.png"),
                allow_stretch=True,
                keep_ratio=True,
                fit_mode="contain",
                size_hint=(None, None),
                size=(30, 30),
                pos_hint={"center_y": 0.5},
            )
            check.bind(on_release=lambda _w, aid=action_id: self._toggle_action_selection(aid))
            row.add_widget(check)
        row.add_widget(
            _Dot(
                color=COL_ACCENT,
                size_hint=(None, None),
                size=(10, 10),
                pos_hint={"center_y": 0.5},
            )
        )
        mid = BoxLayout(orientation="vertical", spacing=2)
        mid.add_widget(self._make_row_label(str(title), bold=True, color=COL_WHITE))
        sub_parts: list[str] = []
        if is_email:
            sub_parts.append("Email follow-up")
        elif is_cal:
            sub_parts.append("Calendar event")
        else:
            sub_parts.append("Task")
        if executed:
            sub_parts.append("Draft saved" if is_email else "Scheduled" if is_cal else "Done")
        mid.add_widget(self._make_row_label("  ·  ".join(sub_parts), color=COL_HINT))
        row.add_widget(mid)

        if not executed and (is_email or is_cal):
            btn = self._make_execute_button(action)
            if btn is not None:
                row.add_widget(btn)
        return row

    def _execute_followup(
        self,
        action_id: str,
        btn,
        *,
        create_draft: bool = False,
        success_text: str = "Done",
    ) -> None:
        if not action_id:
            return
        try:
            btn.disabled = True
            btn.text = "Working…"
        except Exception:  # noqa: BLE001
            pass

        async def _run():
            try:
                await self.backend.execute_action(action_id, create_draft=create_draft)
                ok = True
            except Exception:  # noqa: BLE001
                logger.exception("execute_action failed")
                ok = False

            def _apply(_dt):
                try:
                    if ok:
                        self._mark_action_executed(action_id)
                        btn.text = success_text
                        btn.background_color = (0.16, 0.66, 0.30, 1)
                    else:
                        btn.text = "Retry"
                        btn.disabled = False
                except Exception:  # noqa: BLE001
                    pass
                if ok and self._active_tab == "action_items":
                    self._refresh_after_data_change()

            Clock.schedule_once(_apply, 0)

        run_async(_run())

    def _build_decisions_full(self) -> list[Widget]:
        widgets, _scroll, container = self._build_full_card(
            icon_filename="decisions_icon.png",
            title_text="Decisions Made",
        )
        if not self._decisions:
            container.add_widget(
                self._make_row_label("No decisions were recorded for this meeting.", color=COL_HINT)
            )
            return widgets
        for d in self._decisions:
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                padding=(2, 6, 2, 6),
                spacing=10,
            )
            row.bind(minimum_height=row.setter("height"))
            tick_src = _png("decision_tick.png")
            if tick_src:
                tick = Image(
                    source=tick_src,
                    allow_stretch=True,
                    keep_ratio=True,
                    fit_mode="contain",
                    size_hint=(None, None),
                    size=(22, 22),
                    pos_hint={"top": 1},
                )
                row.add_widget(tick)
            else:
                row.add_widget(_Dot(color=COL_ACCENT, size_hint=(None, None), size=(10, 10)))
            text = self._make_row_label(d, color=COL_WHITE)
            row.add_widget(text)
            container.add_widget(row)
        return widgets

    def _build_participants(self) -> list[Widget]:
        widgets, _scroll, container = self._build_full_card(
            icon_filename=None,
            title_text="Participants",
        )
        names = self._resolve_participants()
        if not names:
            container.add_widget(
                self._make_row_label(
                    f"{self._participant_count or 0} participants — names unavailable.",
                    color=COL_HINT,
                )
            )
            return widgets
        for name in names:
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=58,
                padding=(2, 6, 2, 6),
                spacing=12,
            )
            avatar_src = _png("action_avatar.png")
            if avatar_src:
                avatar = Image(
                    source=avatar_src,
                    allow_stretch=True,
                    keep_ratio=True,
                    fit_mode="contain",
                    size_hint=(None, None),
                    size=(40, 40),
                    pos_hint={"center_y": 0.5},
                )
                row.add_widget(avatar)
            row.add_widget(self._make_row_label(name, bold=True, color=COL_WHITE))
            container.add_widget(row)
        return widgets

    def _build_transcript(self) -> list[Widget]:
        widgets, _scroll, container = self._build_full_card(
            icon_filename=None,
            title_text="Transcript",
        )
        if not self._segments:
            container.add_widget(
                self._make_row_label(
                    "Transcript is not available yet.",
                    color=COL_HINT,
                )
            )
            return widgets
        for seg in self._segments:
            try:
                start = float(seg.get("start_time", 0))
            except (TypeError, ValueError):
                start = 0.0
            mm = int(start) // 60
            ss = int(start) % 60
            speaker = seg.get("speaker_id") or "Speaker"
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            line = f"[{mm:02d}:{ss:02d}] {speaker}: {text}"
            container.add_widget(self._make_row_label(line, color=COL_MUTED))
        return widgets

    # ------------------------------------------------------------------
    # Helpers — image/label adders on the fixed canvas
    # ------------------------------------------------------------------
    def _add_image(self, filename: str, box: dict) -> Image | None:
        img = self._make_image(filename, box)
        if img is not None:
            self._canvas.add_widget(img)
        return img

    def _make_image(self, filename: str, box: dict) -> Image | None:
        src = _png(filename)
        if not src:
            return None
        return Image(
            source=src,
            allow_stretch=True,
            keep_ratio=True,
            fit_mode="contain",
            **kivy_hints(box),
        )

    def _add_img_btn(self, filename: str, box: dict, *, on_release) -> _ImgBtn | None:
        src = _png(filename)
        if not src:
            return None
        btn = _ImgBtn(
            source=src,
            allow_stretch=True,
            keep_ratio=True,
            fit_mode="contain",
            **kivy_hints(box),
        )
        btn.bind(on_release=on_release)
        self._canvas.add_widget(btn)
        return btn

    def _add_label(
        self,
        text: str,
        box: dict,
        fs_ratio: float,
        color: tuple,
        *,
        bold: bool = False,
        halign: str = "center",
        max_lines: int = 1,
        shorten: bool = True,
    ) -> Label:
        lbl = self._make_label(text, box, fs_ratio, color, bold=bold, halign=halign, max_lines=max_lines, shorten=shorten)
        self._canvas.add_widget(lbl)
        return lbl

    def _make_label(
        self,
        text: str,
        box: dict,
        fs_ratio: float,
        color: tuple,
        *,
        bold: bool = False,
        halign: str = "center",
        max_lines: int = 1,
        shorten: bool = True,
    ) -> Label:
        lbl = Label(
            text=text,
            font_name=_FONT_BOLD,
            bold=bold,
            color=color,
            halign=halign,
            valign="middle" if max_lines == 1 else "top",
            markup=False,
            shorten=shorten,
            shorten_from="right",
            max_lines=max_lines,
            # ``font_hinting='light'`` + ``font_kerning=True`` give
            # noticeably crisper glyph edges on the device's screen.
            font_hinting="light",
            font_kerning=True,
            **kivy_hints(box),
        )
        lbl.bind(size=lbl.setter("text_size"))
        self._scaled_labels.append((lbl, fs_ratio))
        return lbl

    def _on_root_resize(self, _root, size):
        self._bg.size = size
        w, h = scaled_canvas(size[0], size[1])
        self._canvas.size = (w, h)
        for lbl, ratio in self._scaled_labels:
            if lbl is None:
                continue
            try:
                lbl.font_size = font_px(ratio, h)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_meeting_data(self, meeting_id: str, summary_data: dict):
        """Bind summary content + trigger backend hydration for missing fields."""
        new_meeting = meeting_id and meeting_id != self.meeting_id
        self.meeting_id = meeting_id
        self._summary_data = dict(summary_data or {})
        # For a new meeting always start the user on the Overview tab.
        if new_meeting and self._active_tab != "overview":
            self._show_tab("overview")
        self._apply_local_data()
        self._fetch_meeting_detail()

    def on_enter(self):
        self._apply_local_data()

    def on_leave(self):
        # Stop any in-flight audio playback so it doesn't keep
        # playing on the home screen / settings / etc.
        sound = getattr(self, "_audio_sound", None)
        if sound is not None:
            try:
                sound.stop()
            except Exception:  # noqa: BLE001
                pass
            self._audio_sound = None
        if hasattr(self, "play_pill") and self.play_pill is not None:
            self.play_pill.set_playing(False)

    # ------------------------------------------------------------------
    # Data binding
    # ------------------------------------------------------------------
    def _apply_local_data(self):
        data = self._summary_data or {}
        title = (data.get("title") or self._meeting_title or "Meeting").strip() or "Meeting"
        self._meeting_title = title
        self.meta_title_label.text = title

        summary = data.get("summary")
        if isinstance(summary, dict):
            summary_text = summary.get("summary") or ""
        else:
            summary_text = summary or ""

        # Date / duration in the meta sub-line
        self.meta_date_label.text = self._format_meta_line(data)
        # Footer "Created: …"
        self.footer_left_label.text = "Created: " + self._format_created_line(data)
        # Play Recording pill — show duration like "12:34" if we have one.
        if hasattr(self, "play_pill") and self.play_pill is not None:
            duration_seconds = 0
            try:
                duration_seconds = max(0, int(float(data.get("duration") or 0)))
            except (TypeError, ValueError):
                duration_seconds = 0
            if duration_seconds > 0:
                mm = duration_seconds // 60
                ss = duration_seconds % 60
                self.play_pill.set_duration(f"{mm:02d}:{ss:02d}")
            else:
                self.play_pill.set_duration("")

        # Action items
        raw_actions = data.get("action_items") or data.get("actions") or []
        self._action_items = list(self._coerce_action_items(raw_actions))

        # Decisions
        raw_decisions = data.get("decisions") or []
        self._decisions = [str(d).strip() for d in raw_decisions if str(d).strip()]

        # Topics
        self._topics = list(self._coerce_topics(data.get("topics") or []))

        # Toggle Participants chip + sidebar tab now that we know
        # whether the merged data actually contains diarization info.
        self._apply_participants_visibility()

        # Refresh the on-screen content. Overview is rebuilt too because it
        # now hides empty sections and sizes cards dynamically.
        self._refresh_after_data_change()

    def _refresh_after_data_change(self) -> None:
        """Apply the latest ``_summary_data`` to existing widgets.

        All tab contents depend on the latest fetched meeting detail, so
        cached widget trees are invalidated and the active tab is rebuilt.
        """
        active = self._active_tab
        # Invalidate every tab so the next visit rebuilds with
        # fresh data. Detach them from the canvas first if they happen to
        # be attached (shouldn't normally happen, but guards against the
        # rare case of multiple refreshes interleaving).
        for tid in _TAB_IDS:
            for w in self._tab_widgets.get(tid, ()):
                if w is not None and w.parent is self._canvas:
                    self._canvas.remove_widget(w)
            self._tab_widgets[tid] = []

        try:
            widgets = [w for w in self._build_tab(active) if w is not None]
        except Exception:  # noqa: BLE001
            logger.exception("Tab %s rebuild failed", active)
            widgets = []
        self._tab_widgets[active] = widgets
        for w in widgets:
            if w.parent is None:
                self._canvas.add_widget(w)

        Clock.schedule_once(
            lambda _dt: self._on_root_resize(self._root, self._root.size), 0
        )

    def _fetch_meeting_detail(self):
        if not self.meeting_id:
            return

        async def _run():
            try:
                detail = await self.backend.get_meeting_detail(self.meeting_id)
            except Exception as exc:  # noqa: BLE001
                logger.debug("get_meeting_detail failed: %s", exc)
                return
            if not isinstance(detail, dict):
                return
            # Fetch persisted agentic actions in parallel — these are
            # the only items that can be auto-executed (each has a
            # stable id that ``execute_action`` accepts). Failures are
            # non-fatal; the action items tab simply doesn't show the
            # follow-up sub-list when this list is empty.
            try:
                actions = await self.backend.get_actions(self.meeting_id)
                if isinstance(actions, list):
                    self._agentic_actions = [
                        a for a in actions if isinstance(a, dict) and a.get("id")
                    ]
                    self._sync_default_action_selection()
            except Exception as exc:  # noqa: BLE001
                logger.debug("get_actions failed: %s", exc)
                self._agentic_actions = []
            self._segments = list(detail.get("segments") or [])
            # The flattened detail merges meeting + summary fields, but the
            # summary block may also live under .summary. Try both shapes.
            block = detail.get("summary")
            if isinstance(block, dict):
                merged = {**(self._summary_data or {}), **block}
            else:
                merged = dict(self._summary_data or {})
            for k in (
                "title",
                "duration",
                "started_at",
                "participant_count",
                "attendee_count",
                "attendees",
                "generated_at",
            ):
                if detail.get(k) is not None and merged.get(k) in (None, ""):
                    merged[k] = detail[k]
            self._summary_data = merged
            if not self._agentic_actions and self._summary_has_executable_actions(merged):
                try:
                    generated = await self.backend.generate_actions(self.meeting_id)
                    if isinstance(generated, list):
                        self._agentic_actions = [
                            a for a in generated if isinstance(a, dict) and a.get("id")
                        ]
                        self._sync_default_action_selection()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("generate_actions fallback failed: %s", exc)

            def _apply(_dt):
                self._apply_local_data()

            Clock.schedule_once(_apply, 0)

        run_async(_run())

    # ------------------------------------------------------------------
    # Coercions
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_action_items(raw):
        for a in raw or []:
            if isinstance(a, dict):
                task = (a.get("task") or a.get("description") or "").strip()
                if not task:
                    continue
                yield {
                    "task": task,
                    "assignee": (a.get("assignee") or "").strip(),
                    "due_date": (a.get("due_date") or "").strip(),
                    "type": (a.get("type") or "").strip(),
                    "completed": bool(a.get("completed", False)),
                }
            else:
                s = str(a).strip()
                if s:
                    yield {
                        "task": s,
                        "assignee": "",
                        "due_date": "",
                        "type": "",
                        "completed": False,
                    }

    @classmethod
    def _summary_has_executable_actions(cls, data: dict) -> bool:
        for item in cls._coerce_action_items(data.get("action_items") or data.get("actions") or []):
            if cls._item_connector(item) in {"gmail", "calendar"}:
                return True
        return False

    @staticmethod
    def _coerce_topics(raw):
        for t in raw or []:
            if isinstance(t, dict):
                name = (t.get("name") or t.get("topic") or "").strip()
                if not name:
                    continue
                try:
                    value = int(round(float(t.get("value") or t.get("percentage") or 0)))
                except (TypeError, ValueError):
                    value = 0
                yield {"name": name, "value": max(0, min(100, value))}
            elif isinstance(t, str) and t.strip():
                yield {"name": t.strip(), "value": 0}

    def _resolve_participants(self) -> list[str]:
        """Real participants from diarization or attendees only.

        We deliberately do NOT fall back to action-item assignees here:
        action-item assignees are who is responsible for a task, not
        who spoke in the meeting. Showing assignees as "participants"
        was misleading the user. The Participants tab/chip is now only
        shown when diarization or an attendee list is actually present
        (see :meth:`_has_diarization`).
        """
        data = self._summary_data or {}
        attendees = data.get("attendees")
        if isinstance(attendees, list):
            names: list[str] = []
            for a in attendees:
                if isinstance(a, dict):
                    n = (a.get("name") or a.get("email") or "").strip()
                else:
                    n = str(a).strip()
                if n:
                    names.append(n)
            if names:
                return names
        # Diarization: distinct non-empty speaker labels in segments
        seen: set[str] = set()
        out: list[str] = []
        for seg in self._segments:
            spk = (seg.get("speaker_id") or "")
            if isinstance(spk, str) and spk.strip():
                key = spk.strip()
                if key.lower() not in seen:
                    seen.add(key.lower())
                    out.append(key)
        return out

    def _has_diarization(self) -> bool:
        """Whether we have enough data to populate the Participants tab.

        True only if either:
          * the merged summary data contains an attendee/speaker list, or
          * any transcript segment carries a non-empty ``speaker_id``.
        """
        data = self._summary_data or {}
        attendees = data.get("attendees")
        if isinstance(attendees, list) and attendees:
            return True
        speakers = data.get("speakers")
        if isinstance(speakers, list) and speakers:
            return True
        for seg in self._segments:
            spk = seg.get("speaker_id")
            if isinstance(spk, str) and spk.strip():
                return True
        return False

    def _apply_participants_visibility(self) -> None:
        """Hide the Participants chip + sidebar tab when there's no
        diarization data, otherwise show them. Called from
        ``_apply_local_data`` after the merged data lands."""
        visible = self._has_diarization()
        chip = getattr(self, "_chip_participants_widget", None)
        if chip is not None:
            chip.opacity = 1.0 if visible else 0.0
        tab = self._sidebar_tabs.get("participants")
        if tab is not None:
            tab.opacity = 1.0 if visible else 0.0
            tab.disabled = not visible
        transcript_tab = self._sidebar_tabs.get("transcript")
        if transcript_tab is not None:
            compact_box = TAB_TRANSCRIPT if visible else TAB_PARTICIPANTS
            transcript_tab.size_hint = (compact_box["w"], compact_box["h"])
            transcript_tab.pos_hint = {
                "x": compact_box["x"],
                "y": 1.0 - compact_box["y_top"] - compact_box["h"],
            }
        # If the user is currently on the Participants tab and we just
        # hid it, fall back to Overview.
        if not visible and self._active_tab == "participants":
            self._show_tab("overview")

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    def _format_meta_line(self, data: dict) -> str:
        date_part = ""
        started = data.get("started_at") or data.get("start_time")
        if started:
            try:
                if isinstance(started, (int, float)):
                    dt = datetime.fromtimestamp(float(started))
                else:
                    dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
                date_part = dt.strftime("%b %d, %I:%M %p").lstrip("0").replace(" 0", " ")
            except Exception:  # noqa: BLE001
                date_part = str(started)
        duration_min = 0
        if data.get("duration"):
            try:
                duration_min = max(0, int(float(data["duration"]) / 60))
            except Exception:  # noqa: BLE001
                duration_min = 0
        self._duration_min = duration_min
        duration_part = f"{duration_min} min" if duration_min else ""
        return "  ·  ".join(p for p in (date_part, duration_part) if p) or "—"

    def _format_created_line(self, data: dict) -> str:
        raw = data.get("generated_at") or data.get("started_at")
        if not raw:
            return "—"
        try:
            if isinstance(raw, (int, float)):
                dt = datetime.fromtimestamp(float(raw))
            else:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return dt.strftime("%b %d, %I:%M %p").lstrip("0").replace(" 0", " ")
        except Exception:  # noqa: BLE001
            return str(raw)

    @staticmethod
    def _format_short_date(raw: str) -> str:
        raw = (raw or "").strip()
        if not raw:
            return ""
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.strftime("%b %d").lstrip("0").replace(" 0", " ")
        except Exception:  # noqa: BLE001
            return raw[:14]

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def _on_back(self):
        self.goto("home", transition="fade")

    def _on_export(self):
        logger.info("Export pressed for meeting %s", self.meeting_id)

    def _on_share(self):
        logger.info("Share pressed for meeting %s", self.meeting_id)

    def _on_play_recording(self):
        """Toggle audio playback of the meeting's saved recording.

        Streams the audio file from the backend to a temp file on first
        press, then loads it with Kivy's ``SoundLoader`` and toggles
        play/pause on subsequent presses. The pill's glyph + text are
        kept in sync via ``_PlayRecordingPill.set_playing``.
        """
        if not self.meeting_id:
            logger.info("Play Recording pressed without a meeting id")
            return
        sound = getattr(self, "_audio_sound", None)
        if sound is not None:
            try:
                if sound.state == "play":
                    sound.stop()
                    self.play_pill.set_playing(False)
                else:
                    sound.play()
                    self.play_pill.set_playing(True)
            except Exception:  # noqa: BLE001
                logger.exception("Audio toggle failed")
            return
        # First press — fetch the audio file in the background, then
        # load + play it. Keep the pill in the "playing" state from the
        # moment the user tapped so the UI feels responsive.
        self.play_pill.set_playing(True)

        async def _run():
            import os
            import tempfile

            from kivy.core.audio import SoundLoader

            tmp_dir = tempfile.gettempdir()
            tmp_path = os.path.join(tmp_dir, f"meetingbox_{self.meeting_id}.audio")
            try:
                downloaded = await self.backend.download_meeting_audio(
                    self.meeting_id, tmp_path
                )
            except Exception:  # noqa: BLE001
                logger.exception("download_meeting_audio failed")
                downloaded = None

            def _apply(_dt):
                if not downloaded:
                    self.play_pill.set_playing(False)
                    return
                snd = SoundLoader.load(downloaded)
                if snd is None:
                    self.play_pill.set_playing(False)
                    return
                self._audio_sound = snd
                # When playback finishes naturally, flip back to play.
                snd.bind(on_stop=lambda *_: self.play_pill.set_playing(False))
                snd.play()

            Clock.schedule_once(_apply, 0)

        run_async(_run())

    def _toggle_action(self, idx: int):
        if 0 <= idx < len(self._action_items):
            item = self._action_items[idx]
            item["completed"] = not bool(item.get("completed"))
            # Re-render the action_items tab so the checkbox icon swaps.
            if self._active_tab == "action_items":
                self._refresh_after_data_change()

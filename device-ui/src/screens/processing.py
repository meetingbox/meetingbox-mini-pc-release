"""Processing screen — Figma ``397:261`` (VelsLhL4YHeVRZSCEmCrGw).

Composed entirely from PNG assets exported from Figma + Kivy ``Label`` widgets
for the dynamic text (meeting title, duration, headline, subtitle). Layout
lives in ``processing_layout.py`` and mirrors the Figma absolute coordinates
1:1 on a 1260×800 reference canvas.

Public API preserved for ``main.py`` to call:

- ``on_enter`` / ``on_leave``
- ``on_processing_started(data)``
- ``on_backend_progress(progress, status, eta)``
- ``on_transcription_ready(meeting_id)``
- ``on_summary_ready(meeting_id, summary_data)``
- ``on_summary_failed(meeting_id, detail)``
- ``set_processing_status(text)``
"""

from __future__ import annotations

import logging
from typing import Optional

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from config import ASSETS_DIR
from processing_layout import (
    BACK_BTN,
    BG_RGB,
    CHECK_BADGE,
    COL_MUTED,
    COL_WHITE,
    DOT_SEPARATOR,
    DURATION_FS_RATIO,
    DURATION_LABEL,
    GLOW_OUTER,
    HEADLINE_BOTTOM,
    HEADLINE_FS_RATIO,
    HEADLINE_LABEL,
    NOTIFY_BAR,
    RING_OUTER,
    RING_SOLID,
    SETTINGS_BTN,
    STAGE_ACTION_ITEMS_ICON,
    STAGE_ACTION_ITEMS_LABEL,
    STAGE_ACTION_ITEMS_STATUS,
    STAGE_FS_RATIO,
    STAGE_KEY_POINTS_ICON,
    STAGE_KEY_POINTS_LABEL,
    STAGE_KEY_POINTS_STATUS,
    STAGE_SUMMARY_ICON,
    STAGE_SUMMARY_LABEL,
    STAGE_SUMMARY_STATUS,
    STEPS_CARD,
    SUBTITLE_BOTTOM,
    SUBTITLE_FS_RATIO,
    TITLE_FS_RATIO,
    TITLE_LABEL,
    font_px,
    kivy_hints,
    scaled_canvas,
)
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

_FIGMA = ASSETS_DIR / "processing" / "figma"
_BG = (BG_RGB[0] / 255, BG_RGB[1] / 255, BG_RGB[2] / 255, 1.0)
_FONT_BOLD = "42dot-Sans"


def _png(name: str) -> str:
    p = _FIGMA / name
    return str(p) if p.is_file() else ""


class _ImgBtn(ButtonBehavior, Image):
    """Tappable PNG button."""


# Stage states for ``_StageRow``.
_STAGE_PENDING = "pending"
_STAGE_LOADING = "loading"
_STAGE_DONE = "done"


class _StageCard(Widget):
    """Translucent glass card behind the three live stage rows."""

    _FILL = (1.0, 1.0, 1.0, 0.05)
    _BORDER = (1.0, 1.0, 1.0, 0.10)
    _RADIUS = 28.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(*self._FILL)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self._RADIUS])
            Color(*self._BORDER)
            self._line = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, self._RADIUS),
                width=1.2,
            )
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [self._RADIUS]
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, self._RADIUS)


class _StageRow:
    """Three-icon row: left icon + label + status (pending/loading/done).

    Not a Widget — the three pieces are independent ``_canvas`` children
    so they keep their Figma absolute positions. The class is just the
    state machine that swaps the status icon source as the backend
    pipeline progresses.
    """

    def __init__(
        self,
        *,
        canvas_parent,
        figma_dir,
        icon_box: dict,
        label_box: dict,
        status_box: dict,
        title: str,
        left_icon: str,
        fs_ratio: float,
    ):
        self._figma_dir = figma_dir
        self._title = title

        def _png(name: str) -> str:
            p = figma_dir / name
            return str(p) if p.is_file() else ""

        self.icon = Image(
            source=_png(left_icon),
            allow_stretch=True, keep_ratio=True, fit_mode="contain",
            **kivy_hints(icon_box),
        )
        self.label = Label(
            text=title,
            font_name=_FONT_BOLD,
            bold=False,
            color=COL_WHITE,
            halign="left",
            valign="middle",
            markup=False,
            shorten=True,
            shorten_from="right",
            max_lines=1,
            **kivy_hints(label_box),
        )
        self.label.bind(size=self.label.setter("text_size"))
        self.label._fs_ratio = fs_ratio  # noqa: SLF001
        self.status = Image(
            source=_png("icon_step_pending.png"),
            allow_stretch=True, keep_ratio=True, fit_mode="contain",
            **kivy_hints(status_box),
        )
        self._png_pending = _png("icon_step_pending.png")
        self._png_loading = _png("icon_loading.png") or _png("icon_step_pending.png")
        self._png_done = _png("icon_step_done.png") or _png("icon_check_tick.png")
        self._state = _STAGE_PENDING

        canvas_parent.add_widget(self.icon)
        canvas_parent.add_widget(self.label)
        canvas_parent.add_widget(self.status)

    def set_state(self, state: str) -> None:
        if state == self._state:
            return
        if state == _STAGE_LOADING:
            self.status.source = self._png_loading
            self.label.color = COL_WHITE
        elif state == _STAGE_DONE:
            self.status.source = self._png_done
            self.label.color = COL_WHITE
        else:
            self.status.source = self._png_pending
            self.label.color = COL_MUTED
        self._state = state


class _ViewSummaryButton(ButtonBehavior, Widget):
    """Bright blue CTA button shown when the meeting summary is ready.

    Lives at the same canvas slot as the ``notify_bar`` informational pill
    — when the summary lands we hide the pill (opacity 0) and reveal this
    button (opacity 1, ``disabled=False``) so the user has an obvious
    "View Meeting Summary" action that opens the summary review screen.

    Drawn with Kivy primitives (no Figma asset for this state) so the
    button is fully responsive and integrates with the rest of the
    processing-screen canvas.
    """

    _FILL = (0 / 255, 107 / 255, 249 / 255, 1.0)        # #006BF9
    _BORDER = (0x3F / 255, 0x42 / 255, 0x53 / 255, 1.0)  # #3F4253
    _BORDER_W = 1.4
    _RADIUS = 38.139  # matches the notify_bar pill radius
    _LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)

    def __init__(self, *, label_text: str = "View Meeting Summary", fs_ratio: float = 28.251 / 800.0, **kwargs):
        super().__init__(**kwargs)
        self._fs_ratio = fs_ratio
        with self.canvas:
            self._fill_color = Color(*self._FILL)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self._RADIUS])
            self._border_color = Color(*self._BORDER)
            self._line = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, self._RADIUS),
                width=self._BORDER_W,
            )
        self._label = Label(
            text=label_text,
            color=self._LABEL_COLOR,
            font_name="42dot-Sans",
            bold=True,
            halign="center",
            valign="middle",
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        )
        self._label.bind(size=self._label.setter("text_size"))
        self.add_widget(self._label)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [self._RADIUS]
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, self._RADIUS)
        self._label.pos = self.pos
        self._label.size = self.size

    def set_pressed(self, pressed: bool) -> None:
        """Slight dim while held down for tactile feedback."""
        a = 0.85 if pressed else 1.0
        r, g, b, _ = self._FILL
        self._fill_color.rgba = (r, g, b, a)

    def on_press(self):  # ButtonBehavior hook
        self.set_pressed(True)

    def on_release(self):  # ButtonBehavior hook
        self.set_pressed(False)


class ProcessingScreen(BaseScreen):
    """Right-side cards + animated centre orb + dynamic header text."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._meeting_id: Optional[str] = None
        self._meeting_title = "Meeting"
        self._meeting_duration_min = 0
        self._summary_data: Optional[dict] = None
        self._summary_ready = False
        self._transcript_ready = False
        self._failed_summary_message = ""

        # Three live stage rows — populated in ``_build_ui`` and driven
        # by ``on_backend_progress`` via ``_apply_stage``. The keys
        # match the ``stage`` field the backend emits in events.
        self._stage_rows: dict[str, _StageRow] = {}
        # Stage order used to mark earlier stages as done when a later
        # one arrives.
        self._stage_order: tuple[str, ...] = (
            "extracting_key_points",
            "identifying_action_items",
            "structuring_summary",
        )

        self._build_ui()

    # ------------------------------------------------------------------ UI
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

        # Centre orb — back-to-front: soft halo (single PNG with a real
        # alpha gradient), the solid bright ring, then the outer rim
        # highlight (now static — the previous spin animation is gone
        # because the new Figma 397:261 design isn't rotating).
        self.glow_orb = self._add_image("glow_orb_outer.png", GLOW_OUTER)
        self._add_image("ring_solid.png", RING_SOLID)
        self.ring_outer = self._add_image("ring_outer.png", RING_OUTER)

        # Header — back button + settings button (the right-side
        # "Listening" pill from the previous Figma version is removed
        # per the 397:261 update).
        self._add_img_btn("btn_back.png", BACK_BTN, on_release=lambda *_: self._on_back())
        self._add_img_btn("btn_settings.png", SETTINGS_BTN, on_release=lambda *_: self._on_settings())

        # "Recording complete" status row
        self._add_image("check_badge.png", CHECK_BADGE)
        self.headline_status_label = self._add_label(
            "Recording complete",
            HEADLINE_LABEL,
            HEADLINE_FS_RATIO,
            COL_WHITE,
            bold=True,
            halign="left",
        )
        self.meeting_title_label = self._add_label(
            "Meeting",
            TITLE_LABEL,
            TITLE_FS_RATIO,
            COL_MUTED,
            halign="left",
        )
        self._add_image("dot_separator.png", DOT_SEPARATOR)
        self.duration_label = self._add_label(
            "--",
            DURATION_LABEL,
            DURATION_FS_RATIO,
            COL_MUTED,
            halign="left",
        )

        # Bottom-left captions
        self.headline_label = self._add_label(
            "Summarizing your meeting...",
            HEADLINE_BOTTOM,
            HEADLINE_FS_RATIO,
            COL_WHITE,
            bold=True,
            halign="left",
        )
        self.subtitle_label = self._add_label(
            "This may take a few seconds",
            SUBTITLE_BOTTOM,
            SUBTITLE_FS_RATIO,
            COL_MUTED,
            halign="left",
        )

        # Right-side card — glass background + 3 live stage rows. The
        # static ``steps_card.png`` composite is gone; instead each row
        # is independently driven so we can show pending / loading /
        # done state as the backend pipeline reports progress.
        stage_card = _StageCard(**kivy_hints(STEPS_CARD))
        self._canvas.add_widget(stage_card)
        self._stage_rows = {
            "extracting_key_points": _StageRow(
                canvas_parent=self._canvas, figma_dir=_FIGMA,
                icon_box=STAGE_KEY_POINTS_ICON,
                label_box=STAGE_KEY_POINTS_LABEL,
                status_box=STAGE_KEY_POINTS_STATUS,
                title="Extracting key points",
                left_icon="icon_edit_note.png",
                fs_ratio=STAGE_FS_RATIO,
            ),
            "identifying_action_items": _StageRow(
                canvas_parent=self._canvas, figma_dir=_FIGMA,
                icon_box=STAGE_ACTION_ITEMS_ICON,
                label_box=STAGE_ACTION_ITEMS_LABEL,
                status_box=STAGE_ACTION_ITEMS_STATUS,
                title="Identifying action items",
                left_icon="icon_tick_circle.png",
                fs_ratio=STAGE_FS_RATIO,
            ),
            "structuring_summary": _StageRow(
                canvas_parent=self._canvas, figma_dir=_FIGMA,
                icon_box=STAGE_SUMMARY_ICON,
                label_box=STAGE_SUMMARY_LABEL,
                status_box=STAGE_SUMMARY_STATUS,
                title="Structuring summary",
                left_icon="icon_soundwave.png",
                fs_ratio=STAGE_FS_RATIO,
            ),
        }

        self.notify_pill = self._add_img_btn(
            "notify_bar.png", NOTIFY_BAR, on_release=lambda *_: self._open_summary()
        )

        # "View Meeting Summary" CTA — sits in the same slot as the
        # notify_bar. We start it hidden + disabled and only reveal it
        # when on_summary_ready fires (see _set_summary_cta_visible).
        self.view_summary_btn = _ViewSummaryButton(
            label_text="View Meeting Summary",
            fs_ratio=HEADLINE_FS_RATIO,
            **kivy_hints(NOTIFY_BAR),
        )
        self.view_summary_btn.bind(on_release=lambda *_: self._open_summary())
        self._canvas.add_widget(self.view_summary_btn)
        self._set_summary_cta_visible(False)

        self.add_widget(self._root)
        Clock.schedule_once(lambda _dt: self._on_root_resize(self._root, self._root.size), 0)

    # --------------------------------------------------------------- helpers
    def _add_image(self, filename: str, box: dict) -> Image | None:
        src = _png(filename)
        if not src:
            return None
        img = Image(
            source=src,
            allow_stretch=True,
            keep_ratio=True,
            fit_mode="contain",
            **kivy_hints(box),
        )
        self._canvas.add_widget(img)
        return img

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
        """Build a Kivy Label sized via Figma ratios.

        Defaults to ``shorten=True`` + ``max_lines=1`` so that long dynamic
        text (meeting titles, error messages, progress strings) never
        overflows its bounding box on any screen resolution. Callers can
        opt into wrapping with ``max_lines > 1, shorten=False``.
        """
        lbl = Label(
            text=text,
            font_name=_FONT_BOLD,
            bold=bold,
            color=color,
            halign=halign,
            valign="middle",
            markup=False,
            shorten=shorten,
            shorten_from="right",
            max_lines=max_lines,
            **kivy_hints(box),
        )
        lbl.bind(size=lbl.setter("text_size"))
        lbl._fs_ratio = fs_ratio  # noqa: SLF001 — resize hook
        self._canvas.add_widget(lbl)
        return lbl

    def _on_root_resize(self, _root, size):
        self._bg.size = size
        w, h = scaled_canvas(size[0], size[1])
        self._canvas.size = (w, h)
        for lbl in (
            getattr(self, "headline_status_label", None),
            getattr(self, "meeting_title_label", None),
            getattr(self, "duration_label", None),
            getattr(self, "headline_label", None),
            getattr(self, "subtitle_label", None),
        ):
            if lbl is not None:
                lbl.font_size = font_px(lbl._fs_ratio, h)  # noqa: SLF001
        for row in getattr(self, "_stage_rows", {}).values():
            row.label.font_size = font_px(row.label._fs_ratio, h)  # noqa: SLF001
        btn = getattr(self, "view_summary_btn", None)
        if btn is not None:
            btn._label.font_size = font_px(btn._fs_ratio, h)  # noqa: SLF001

    def _set_summary_cta_visible(self, ready: bool) -> None:
        """Swap between the informational notify pill (still processing) and
        the bright "View Meeting Summary" CTA (summary ready).
        """
        btn = getattr(self, "view_summary_btn", None)
        pill = getattr(self, "notify_pill", None)
        if btn is not None:
            btn.opacity = 1.0 if ready else 0.0
            btn.disabled = not ready
        if pill is not None:
            pill.opacity = 0.0 if ready else 1.0
            pill.disabled = ready

    def _summary_payload_ready(self) -> bool:
        """Whether ``self._summary_data`` is actually complete enough to
        render the summary screen — text + at least one of (action items,
        decisions) + at least one topic. Used to gate the CTA so we only
        flip the bright button once the data is genuinely there."""
        data = self._summary_data or {}
        text = (data.get("summary_text") or data.get("text") or "").strip()
        if not text:
            return False
        topics = data.get("topics") or data.get("key_points") or []
        actions = data.get("actions") or data.get("action_items") or []
        decisions = data.get("decisions") or data.get("decisions_made") or []
        return bool(topics) and bool(actions or decisions)

    def _apply_stage(self, stage: str | None) -> None:
        """Mark the row matching ``stage`` as loading and all previous
        rows as done. Unknown / empty stages are ignored."""
        rows = self._stage_rows
        if not stage or stage not in rows:
            return
        order = self._stage_order
        try:
            idx = order.index(stage)
        except ValueError:
            return
        for i, key in enumerate(order):
            row = rows.get(key)
            if row is None:
                continue
            if i < idx:
                row.set_state(_STAGE_DONE)
            elif i == idx:
                row.set_state(_STAGE_LOADING)
            else:
                row.set_state(_STAGE_PENDING)

    def _mark_all_stages_done(self) -> None:
        for row in self._stage_rows.values():
            row.set_state(_STAGE_DONE)

    def _reset_stages(self) -> None:
        for key, row in self._stage_rows.items():
            row.set_state(_STAGE_LOADING if key == self._stage_order[0] else _STAGE_PENDING)

    # ------------------------------------------------------------- lifecycle
    def on_enter(self):
        self._summary_data = None
        self._summary_ready = False
        mid = getattr(self.app, "current_session_id", None)
        self._meeting_id = mid

        cache = {}
        try:
            cache = getattr(self.app, "_processing_summary_cache", {}) or {}
        except Exception:  # noqa: BLE001
            cache = {}
        cached = cache.get(mid) if mid else None
        if isinstance(cached, dict) and cached.get("ok") is True and mid:
            self._summary_data = cached.get("summary") or {}
            self._summary_ready = True
        elif isinstance(cached, dict) and cached.get("ok") is False and mid:
            self._failed_summary_message = str(cached.get("error") or "")
        else:
            self._failed_summary_message = ""

        done_for = getattr(self.app, "_transcription_done_for_session", None)
        self._transcript_ready = bool(mid and done_for == mid)

        # Reset visuals to the initial Figma state.
        self.headline_label.text = "Summarizing your meeting..."
        self.subtitle_label.text = "This may take a few seconds"
        self.duration_label.text = self._format_duration(self._meeting_duration_min)
        self.meeting_title_label.text = self._meeting_title or "Meeting"

        if self._summary_ready:
            self.headline_label.text = "Analysis complete!"
            self.subtitle_label.text = (
                "Your meeting highlights, transcript, and action items are ready."
            )
            self._mark_all_stages_done()
        elif self._failed_summary_message and self._transcript_ready:
            self.on_summary_failed(mid, self._failed_summary_message)
        elif self._transcript_ready:
            self.subtitle_label.text = "Transcription done. Building meeting report..."
            self._reset_stages()
        else:
            self._reset_stages()

        self._set_summary_cta_visible(self._summary_ready and self._summary_payload_ready())

    def on_leave(self):
        pass

    # ------------------------------------------------------------------
    # Public API — called from main.py WS dispatchers + summary poller
    # ------------------------------------------------------------------

    def on_processing_started(self, data):
        title = (data or {}).get("title") or self._meeting_title or "Meeting"
        title = str(title).strip() or "Meeting"
        duration = int(((data or {}).get("duration") or 0) / 60)
        self._meeting_title = title
        self._meeting_duration_min = duration
        self.meeting_title_label.text = title
        self.duration_label.text = self._format_duration(duration)

    def set_processing_status(self, text: str) -> None:
        """Update the subtitle line under the headline. Called from main.py
        for backend ``progress``, ``summary_progress`` and
        ``transcription_complete`` events. Safe to call before the subtitle
        widget is built (no-op in that case)."""
        msg = (text or "").strip()
        if not msg:
            return
        label = getattr(self, "subtitle_label", None)
        if label is None:
            return
        try:
            label.text = msg
        except Exception:  # noqa: BLE001
            logger.debug("set_processing_status: subtitle update failed", exc_info=True)

    def on_backend_progress(self, progress: int, status: str, eta: int, stage: str | None = None):
        """Drive the subtitle from a 0-100 progress value and advance the
        live stage rows when the backend reports a recognised stage."""
        del eta
        if status:
            self.set_processing_status(status)
        if stage:
            self._apply_stage(stage)
        else:
            # Some backend events still report progress without an
            # explicit stage field — infer best-effort from progress.
            if progress >= 95:
                self._mark_all_stages_done()
            elif progress >= 70:
                self._apply_stage("structuring_summary")
            elif progress >= 40:
                self._apply_stage("identifying_action_items")
            elif progress >= 10:
                self._apply_stage("extracting_key_points")

    def on_transcription_ready(self, meeting_id: str):
        """Transcript saved server-side — summary is still being built."""
        try:
            if meeting_id:
                self.app._transcript_cta_satisfied_meeting_id = meeting_id  # noqa: SLF001
        except Exception:  # noqa: BLE001
            pass
        if meeting_id:
            self._meeting_id = meeting_id
        self._transcript_ready = True
        self.subtitle_label.text = "Transcription done. Building meeting report..."
        try:
            cache = getattr(self.app, "_processing_summary_cache", {}) or {}
            ent = cache.get(meeting_id)
            if isinstance(ent, dict) and ent.get("ok") is False:
                self.on_summary_failed(meeting_id, str(ent.get("error") or ""))
        except Exception:  # noqa: BLE001
            pass

    def on_summary_ready(self, meeting_id: str, summary_data: dict):
        self._meeting_id = meeting_id
        self._summary_data = summary_data or {}
        self._summary_ready = True
        self.headline_label.text = "Analysis complete!"
        self.subtitle_label.text = (
            "Your meeting highlights, transcript, and action items are ready."
        )
        self._mark_all_stages_done()
        # Only reveal the bright "View Meeting Summary" CTA once the
        # payload actually contains enough data to populate the summary
        # screen — otherwise the user can tap through to an empty page
        # while the backend is still streaming fields in.
        self._set_summary_cta_visible(self._summary_payload_ready())

    def on_summary_failed(self, meeting_id: str, detail: str):
        """Full report failed — keep transcript path usable."""
        if meeting_id:
            self._meeting_id = meeting_id
        self._summary_ready = False
        self._summary_data = {}
        self.headline_label.text = "Transcript ready"
        self.subtitle_label.text = (detail or "Full report could not be generated.")[:240]
        self._set_summary_cta_visible(False)

    # ------------------------------------------------------------------
    # Helpers — interaction
    # ------------------------------------------------------------------

    def _on_back(self):
        self.goto("home", transition="fade")

    def _on_settings(self):
        self.goto("settings", transition="fade")

    def _open_summary(self):
        if not self._meeting_id:
            logger.info("Summary CTA pressed but meeting_id is not set")
            return
        if not (self._transcript_ready or self._summary_ready):
            logger.info(
                "Summary CTA pressed before transcript was ready (meeting_id=%s)",
                self._meeting_id,
            )
            return
        try:
            scr = self.app.screen_manager.get_screen("summary_review")
        except Exception as e:  # noqa: BLE001
            logger.warning("summary_review screen missing: %s", e)
            return
        payload = self._summary_data if self._summary_ready else {}
        if hasattr(scr, "set_meeting_data"):
            try:
                scr.set_meeting_data(self._meeting_id, payload or {})
            except Exception as e:  # noqa: BLE001
                logger.warning("set_meeting_data failed: %s", e)
        self.goto("summary_review", transition="fade")

    @staticmethod
    def _format_duration(min_value: int) -> str:
        m = max(0, int(min_value or 0))
        if m <= 0:
            return "--"
        return f"{m} min"

    # (Previous outer-ring spin and orb-pulse animations were removed
    # because the new Figma 397:261 design has a static orb.)

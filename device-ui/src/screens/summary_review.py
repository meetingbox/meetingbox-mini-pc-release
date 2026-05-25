"""Meeting Summary screen — Figma ``659:838`` (VelsLhL4YHeVRZSCEmCrGw).

Shown after the user taps "View Summary" from the Processing screen.

Composed from PNG assets exported from Figma + Kivy primitives for the card
surfaces / scrollbars + Kivy ``Label`` widgets for every piece of dynamic
text (meeting title, date, summary body, action items, decisions). Layout
constants live in ``summary_layout.py`` and mirror the Figma absolute
coordinates 1:1 on a 1260×800 reference canvas.

Public API preserved for ``main.py`` + ``processing.py`` to call:

- ``__init__``
- ``set_meeting_data(meeting_id, summary_data)``
- ``on_enter`` / ``on_leave``
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from async_helper import run_async
from config import ASSETS_DIR
from screens.base_screen import BaseScreen
from summary_layout import (
    ACTION_AVATAR_SIZE,
    ACTION_CHECK_SIZE,
    ACTION_DATE_W,
    ACTION_NAME_W,
    ACTION_ROW_HEIGHT,
    ACTION_ROW_YS,
    ACTION_TASK_W,
    ACTION_X_AVATAR,
    ACTION_X_CHECK,
    ACTION_X_DATE,
    ACTION_X_NAME,
    ACTION_X_TASK,
    ACTIONS_CARD,
    ACTIONS_ICON,
    ACTIONS_SCROLL_THUMB,
    ACTIONS_SCROLL_TRACK,
    ACTIONS_TITLE,
    BACK_BTN,
    BG_RGB,
    CANVAS_H,
    CANVAS_W,
    CARD_BORDER,
    CARD_FILL,
    CARD_RADIUS,
    COL_HINT,
    COL_MUTED,
    COL_WHITE,
    DECISION_ROW_HEIGHT,
    DECISION_ROW_YS,
    DECISION_TEXT_W,
    DECISION_TICK_SIZE,
    DECISION_X_TEXT,
    DECISION_X_TICK,
    DECISIONS_CARD,
    DECISIONS_ICON,
    DECISIONS_SCROLL_THUMB,
    DECISIONS_SCROLL_TRACK,
    DECISIONS_TITLE,
    META_CARD,
    META_DATE,
    META_DATE_FS_RATIO,
    META_EXPORT,
    META_FILE_ICON,
    META_PARTICIPANTS,
    META_RECORDED,
    META_SHARE,
    META_TITLE,
    META_TITLE_FS_RATIO,
    PAGE_TITLE,
    PAGE_TITLE_FS_RATIO,
    ROW_TEXT_FS_RATIO,
    SCROLL_RADIUS,
    SCROLL_THUMB_FILL,
    SCROLL_TRACK_FILL,
    SECTION_TITLE_FS_RATIO,
    SUMMARY_CARD,
    SUMMARY_ICON,
    SUMMARY_IMAGE,
    SUMMARY_TEXT,
    SUMMARY_TEXT_FS_RATIO,
    SUMMARY_TITLE,
    SUMMARY_TITLE_FS_RATIO,
    canvas_box,
    font_px,
    kivy_hints,
    row_box,
    scaled_canvas,
)

logger = logging.getLogger(__name__)

_FIGMA = ASSETS_DIR / "summary" / "figma"
_BG = (BG_RGB[0] / 255, BG_RGB[1] / 255, BG_RGB[2] / 255, 1.0)
_FONT_BOLD = "42dot-Sans"


def _png(name: str) -> str:
    p = _FIGMA / name
    return str(p) if p.is_file() else ""


class _ImgBtn(ButtonBehavior, Image):
    """Tappable PNG button."""


class _GradientCard(Widget):
    """Card-style surface: rounded fill + 1.5px border.

    Figma uses a vertical gradient #02123c → #000a26; Kivy ``RoundedRectangle``
    only supports a single colour, so we paint the midtone and rely on the
    border + bg to communicate depth. This visually reads identical to the
    design on the kiosk.
    """

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


class _ScrollPill(Widget):
    """Decorative rounded pill (used for scrollbar track + thumb)."""

    def __init__(self, *, fill: tuple, radius: float = SCROLL_RADIUS, **kwargs):
        super().__init__(**kwargs)
        self._fill = fill
        self._radius = radius
        with self.canvas:
            Color(*fill)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [self._radius]


class SummaryReviewScreen(BaseScreen):
    """Meeting summary, action items and decisions — rendered from Figma 659:838."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.meeting_id: Optional[str] = None
        self._summary_data: dict = {}
        self._meeting_title = "Meeting"
        self._meeting_date_str = "—"
        self._participant_count = 0
        self._duration_min = 0
        self._action_items: list[dict] = []
        self._decisions: list[str] = []

        # Pre-built row widgets (4 each as per Figma); _refresh_rows binds
        # them to live data.
        self._action_row_widgets: list[dict] = []
        self._decision_row_widgets: list[dict] = []

        self._build_ui()

    # ----------------------------------------------------------- UI build
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

        # Header
        self._add_img_btn("btn_back.png", BACK_BTN, on_release=lambda *_: self._on_back())
        self.page_title_label = self._add_label(
            "Meeting Summary",
            PAGE_TITLE,
            PAGE_TITLE_FS_RATIO,
            COL_WHITE,
            bold=True,
            halign="left",
        )

        self._build_meta_card()
        self._build_summary_card()
        self._build_actions_card()
        self._build_decisions_card()

        self.add_widget(self._root)
        Clock.schedule_once(lambda _dt: self._on_root_resize(self._root, self._root.size), 0)

    # ------------------------------------------------------------------
    # Card builders
    # ------------------------------------------------------------------
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
        # Participant chip is a composite PNG; if we need a dynamic count we
        # overlay the number in a label that sits on top of the chip.
        self._add_image("chip_participants.png", META_PARTICIPANTS)
        self._add_image("chip_recorded.png", META_RECORDED)
        self._add_img_btn("btn_export.png", META_EXPORT, on_release=lambda *_: self._on_export())
        self._add_img_btn("btn_share.png", META_SHARE, on_release=lambda *_: self._on_share())

    def _build_summary_card(self):
        self._canvas.add_widget(_GradientCard(**kivy_hints(SUMMARY_CARD)))
        self._add_image("ai_summary_icon.png", SUMMARY_ICON)
        self.summary_title_label = self._add_label(
            "AI Summary",
            SUMMARY_TITLE,
            SUMMARY_TITLE_FS_RATIO,
            COL_WHITE,
            bold=True,
            halign="left",
        )
        # Multi-line body — allow up to 3 lines and shorten with "…" if even
        # 3 lines don't fit (Figma shows 3 lines for the placeholder text).
        self.summary_text_label = self._add_label(
            "—",
            SUMMARY_TEXT,
            SUMMARY_TEXT_FS_RATIO,
            COL_HINT,
            halign="left",
            max_lines=3,
            shorten=True,
        )
        self._add_image("ai_summary_image.png", SUMMARY_IMAGE)

    def _build_actions_card(self):
        self._canvas.add_widget(_GradientCard(**kivy_hints(ACTIONS_CARD)))
        self._add_image("action_items_icon.png", ACTIONS_ICON)
        self._add_label(
            "Action items",
            ACTIONS_TITLE,
            SECTION_TITLE_FS_RATIO,
            COL_WHITE,
            halign="left",
        )
        # Pre-build 4 visible rows. _refresh_rows binds these to live data
        # and hides any that don't have data.
        card_y_top = ACTIONS_CARD["y_top"] * CANVAS_H
        for idx, row_y in enumerate(ACTION_ROW_YS):
            check_box = row_box(
                ACTION_X_CHECK, card_y_top, row_y, ACTION_CHECK_SIZE, ACTION_CHECK_SIZE
            )
            check = _ImgBtn(
                source=_png("action_check_pending.png"),
                allow_stretch=True,
                keep_ratio=True,
                fit_mode="contain",
                **kivy_hints(check_box),
            )
            # Bind once with the row index closure so toggles always target
            # the correct underlying action_items entry, regardless of how
            # many times _refresh_action_rows runs.
            check.bind(on_release=lambda _w, i=idx: self._toggle_action(i))
            self._canvas.add_widget(check)

            task_lbl = self._add_label(
                "",
                row_box(ACTION_X_TASK, card_y_top, row_y, ACTION_TASK_W, ACTION_ROW_HEIGHT),
                ROW_TEXT_FS_RATIO,
                COL_HINT,
                halign="left",
            )

            avatar = self._add_image(
                "action_avatar.png",
                row_box(
                    ACTION_X_AVATAR,
                    card_y_top,
                    row_y,
                    ACTION_AVATAR_SIZE,
                    ACTION_AVATAR_SIZE + 1.0,
                ),
            )
            name_lbl = self._add_label(
                "",
                row_box(ACTION_X_NAME, card_y_top, row_y, ACTION_NAME_W, ACTION_ROW_HEIGHT),
                ROW_TEXT_FS_RATIO,
                COL_HINT,
                halign="left",
            )
            date_lbl = self._add_label(
                "",
                row_box(ACTION_X_DATE, card_y_top, row_y, ACTION_DATE_W, ACTION_ROW_HEIGHT),
                ROW_TEXT_FS_RATIO,
                COL_HINT,
                halign="left",
            )
            self._action_row_widgets.append(
                dict(check=check, task=task_lbl, avatar=avatar, name=name_lbl, date=date_lbl)
            )

        # Scrollbar (decorative — visible when the underlying list has > 4
        # entries; otherwise hidden via opacity=0 in _refresh_action_rows).
        self.actions_scroll_track = _ScrollPill(
            fill=SCROLL_TRACK_FILL, **kivy_hints(ACTIONS_SCROLL_TRACK)
        )
        self.actions_scroll_thumb = _ScrollPill(
            fill=SCROLL_THUMB_FILL, **kivy_hints(ACTIONS_SCROLL_THUMB)
        )
        self._canvas.add_widget(self.actions_scroll_track)
        self._canvas.add_widget(self.actions_scroll_thumb)

    def _build_decisions_card(self):
        self._canvas.add_widget(_GradientCard(**kivy_hints(DECISIONS_CARD)))
        self._add_image("decisions_icon.png", DECISIONS_ICON)
        self._add_label(
            "Decisions Made",
            DECISIONS_TITLE,
            SECTION_TITLE_FS_RATIO,
            COL_WHITE,
            halign="left",
        )

        card_y_top = DECISIONS_CARD["y_top"] * CANVAS_H
        for row_y in DECISION_ROW_YS:
            tick = self._add_image(
                "decision_tick.png",
                row_box(
                    DECISION_X_TICK, card_y_top, row_y, DECISION_TICK_SIZE, DECISION_TICK_SIZE
                ),
            )
            text_lbl = self._add_label(
                "",
                row_box(
                    DECISION_X_TEXT, card_y_top, row_y, DECISION_TEXT_W, DECISION_ROW_HEIGHT
                ),
                ROW_TEXT_FS_RATIO,
                COL_HINT,
                halign="left",
            )
            self._decision_row_widgets.append(dict(tick=tick, text=text_lbl))

        self.decisions_scroll_track = _ScrollPill(
            fill=SCROLL_TRACK_FILL, **kivy_hints(DECISIONS_SCROLL_TRACK)
        )
        self.decisions_scroll_thumb = _ScrollPill(
            fill=SCROLL_THUMB_FILL, **kivy_hints(DECISIONS_SCROLL_THUMB)
        )
        self._canvas.add_widget(self.decisions_scroll_track)
        self._canvas.add_widget(self.decisions_scroll_thumb)

    # ----------------------------------------------------------- helpers
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
        for child in self._canvas.children:
            ratio = getattr(child, "_fs_ratio", None)
            if ratio is not None:
                child.font_size = font_px(ratio, h)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_meeting_data(self, meeting_id: str, summary_data: dict):
        """Bind summary content + trigger backend hydration for missing fields."""
        self.meeting_id = meeting_id
        self._summary_data = summary_data or {}
        self._apply_local_data()
        self._fetch_meeting_detail()

    def on_enter(self):
        # Re-render in case set_meeting_data was called before the screen
        # was first shown.
        self._apply_local_data()

    def on_leave(self):
        pass

    # ------------------------------------------------------------------
    # Data binding
    # ------------------------------------------------------------------
    def _apply_local_data(self):
        data = self._summary_data or {}
        title = (data.get("title") or self._meeting_title or "Meeting").strip() or "Meeting"
        self._meeting_title = title
        self.meta_title_label.text = title

        # Summary body — accept either a flat string or a structured block.
        summary = data.get("summary")
        if isinstance(summary, dict):
            summary_text = (summary.get("summary") or "").strip()
        else:
            summary_text = (summary or "").strip()
        self.summary_text_label.text = summary_text or "No summary available yet."

        # Date / duration
        self.meta_date_label.text = self._format_meta_line(data)

        # Action items
        raw_actions = data.get("action_items") or data.get("actions") or []
        self._action_items = list(self._coerce_action_items(raw_actions))
        self._refresh_action_rows()

        # Decisions
        raw_decisions = data.get("decisions") or []
        self._decisions = [str(d).strip() for d in raw_decisions if str(d).strip()]
        self._refresh_decision_rows()

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
            block = detail.get("summary")
            if isinstance(block, dict):
                merged = {**(self._summary_data or {}), **block}
                if "title" not in merged and detail.get("title"):
                    merged["title"] = detail.get("title")
            else:
                merged = dict(self._summary_data or {})
                if detail.get("title"):
                    merged["title"] = detail["title"]
            for k in ("duration", "started_at", "participant_count", "attendee_count"):
                if detail.get(k) is not None and merged.get(k) is None:
                    merged[k] = detail[k]
            self._summary_data = merged
            Clock.schedule_once(lambda _dt: self._apply_local_data(), 0)

        run_async(_run())

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
                    "completed": bool(a.get("completed", False)),
                }
            else:
                s = str(a).strip()
                if s:
                    yield {"task": s, "assignee": "", "due_date": "", "completed": False}

    def _refresh_action_rows(self):
        items = self._action_items
        visible_count = min(len(items), len(self._action_row_widgets))
        for idx, widgets in enumerate(self._action_row_widgets):
            if idx < visible_count:
                item = items[idx]
                widgets["check"].source = _png(
                    "action_check_done.png" if item.get("completed") else "action_check_pending.png"
                )
                widgets["check"].opacity = 1.0
                widgets["check"].disabled = False
                widgets["task"].text = item.get("task", "")
                widgets["task"].opacity = 1.0
                widgets["avatar"].opacity = 1.0 if item.get("assignee") else 0.0
                widgets["name"].text = item.get("assignee", "")
                widgets["name"].opacity = 1.0
                widgets["date"].text = self._format_short_date(item.get("due_date", ""))
                widgets["date"].opacity = 1.0
            else:
                for key in ("check", "task", "avatar", "name", "date"):
                    widgets[key].opacity = 0.0
                widgets["check"].disabled = True
        overflow = len(items) > len(self._action_row_widgets)
        op = 1.0 if overflow else 0.0
        self.actions_scroll_track.opacity = op
        self.actions_scroll_thumb.opacity = op

    def _refresh_decision_rows(self):
        items = self._decisions
        visible_count = min(len(items), len(self._decision_row_widgets))
        for idx, widgets in enumerate(self._decision_row_widgets):
            if idx < visible_count:
                widgets["tick"].opacity = 1.0
                widgets["text"].text = items[idx]
                widgets["text"].opacity = 1.0
            else:
                widgets["tick"].opacity = 0.0
                widgets["text"].opacity = 0.0
        overflow = len(items) > len(self._decision_row_widgets)
        op = 1.0 if overflow else 0.0
        self.decisions_scroll_track.opacity = op
        self.decisions_scroll_thumb.opacity = op

    def _toggle_action(self, idx: int):
        if idx >= len(self._action_items):
            return
        item = self._action_items[idx]
        item["completed"] = not bool(item.get("completed"))
        widgets = self._action_row_widgets[idx]
        widgets["check"].source = _png(
            "action_check_done.png" if item["completed"] else "action_check_pending.png"
        )

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    def _format_meta_line(self, data: dict) -> str:
        """Build the "May 21, 11:00 AM  45 min" sub-title."""
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
        return "  ".join(p for p in (date_part, duration_part) if p) or "—"

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

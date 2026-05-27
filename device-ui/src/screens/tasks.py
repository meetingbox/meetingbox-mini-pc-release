"""Tasks screen — Figma node 569:193 (1260 × 800 px).

Displays the user's commitments/tasks, grouped by Due Today / Upcoming /
Unplanned, with filter tabs (All · Today · Upcoming · Unplanned) and a
scrollable task list.  Data is loaded from the backend commitments API on
every on_enter.

Layout mirrors the Figma device-UI design:
  HEADER    : back button + "Tasks" title + count badge
  FILTER BAR: four tab pills — All · Today · Upcoming · Unplanned
  TASK LIST : scrollable, section headers (TODAY/UPCOMING/UNPLANNED) + rows
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.graphics.texture import Texture
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from async_helper import run_async
from config import ASSETS_DIR, DISPLAY_HEIGHT, DISPLAY_WIDTH, display_now
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)

# ── Design frame ───────────────────────────────────────────────────────────────
FW, FH = 1260.0, 800.0

# ── Asset directories ──────────────────────────────────────────────────────────
_BRIEF_DIR = ASSETS_DIR / "brief"   / "figma"
_CAL_DIR   = ASSETS_DIR / "calendar" / "figma"
_HOME_DIR  = ASSETS_DIR / "home"    / "figma"


def _brief_asset(name: str) -> str:
    p = _BRIEF_DIR / name
    return str(p) if p.is_file() else ""


def _cal_asset(name: str) -> str:
    p = _CAL_DIR / name
    return str(p) if p.is_file() else ""


def _home_asset(name: str) -> str:
    p = _HOME_DIR / name
    return str(p) if p.is_file() else ""


# ── Colours ────────────────────────────────────────────────────────────────────
_BG        = (1/255,   8/255,  26/255, 1.0)   # #01081A  background
_WHITE     = (1.0, 1.0, 1.0, 1.0)
_MUTED     = (182/255, 186/255, 242/255, 1.0)  # #B6BAF2
_BLUE      = (0.0,   107/255, 249/255, 1.0)   # #006BF9  Today / active
_PURPLE    = (169/255, 113/255, 212/255, 1.0)  # #A971D4  Upcoming
_ORANGE    = (241/255, 137/255,   3/255, 1.0)  # #F18903  Unplanned
_GREEN     = ( 25/255, 211/255, 133/255, 1.0)  # #19D385  completed (unused)

# Card / panel gradient stops
_CARD_T    = (1/255,  17/255,  55/255, 1.0)   # #011137
_CARD_B    = (0.0,   10/255,  38/255, 1.0)    # #000A26
_ROW_T     = (2/255,  18/255,  60/255, 1.0)   # #02123C
_ROW_B     = _CARD_B

# Border
_BDR       = (63/255,  66/255,  83/255, 1.0)  # #3F4253

# Section-header background
_SEC_BG    = (4/255,   16/255,  44/255, 0.85)  # #04102C 85%

# Divider
_DIV_COL   = (2/255,   23/255,  77/255, 0.7)

# Font names (registered in main.py)
_FSB = "42dot-SB"    # SemiBold
_FB  = "42dot-Sans"  # Regular/Bold
_FMD = "42dot-Med"   # Medium


# ── Coordinate helpers ─────────────────────────────────────────────────────────

def _ph(fx: float, fy: float, fw: float, fh: float) -> dict:
    """Figma absolute px → Kivy size_hint + pos_hint for a 1260×800 root."""
    return {
        "size_hint": (fw / FW, fh / FH),
        "pos_hint":  {"x": fx / FW, "y": (FH - fy - fh) / FH},
    }


def _ff(fs: float) -> int:
    """Scale a Figma font/pixel value by the display scale factor."""
    scale = min(DISPLAY_WIDTH / FW, DISPLAY_HEIGHT / FH)
    return max(6, round(fs * scale))


# ── Gradient texture cache ─────────────────────────────────────────────────────
_GC: dict = {}


def _grad(top: tuple, bot: tuple) -> Texture:
    key = (top, bot)
    if key not in _GC:
        tex = Texture.create(size=(1, 2), colorfmt="rgba")
        def _b(c):
            return [min(255, max(0, int(v * 255))) for v in c]
        tex.blit_buffer(bytes(_b(bot) + _b(top)), colorfmt="rgba", bufferfmt="ubyte")
        tex.mag_filter = tex.min_filter = "linear"
        tex.wrap = "clamp_to_edge"
        _GC[key] = tex
    return _GC[key]


# ── Widget helpers ─────────────────────────────────────────────────────────────

def _lbl(text: str, font: str, size: int | float, color: tuple,
         ha: str = "left", va: str = "top", **kw) -> Label:
    lw = Label(text=text, font_name=font, font_size=size, color=color,
               halign=ha, valign=va, **kw)
    lw.bind(size=lw.setter("text_size"))
    return lw


class _ImgBtn(ButtonBehavior, Image):
    pass


class _Card(FloatLayout):
    """Gradient-filled rounded card with border line."""

    def __init__(self, ct: tuple, cb: tuple, bdr: tuple,
                 r: float = 12, bdr_alpha: float = 0.9, **kw):
        super().__init__(**kw)
        self._r = r
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[r],
                texture=_grad(ct, cb))
        with self.canvas.after:
            Color(*bdr[:3], bdr_alpha)
            self._ln = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, r),
                width=1.0)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        r = self._r
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bg.radius = [r]
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, r)


class _TapCard(ButtonBehavior, _Card):
    pass


class _DotWidget(Widget):
    """Coloured circular status dot."""

    def __init__(self, color: tuple, **kw):
        super().__init__(**kw)
        self._color = color
        with self.canvas:
            Color(*color)
            self._e = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._e.pos = self.pos
        self._e.size = self.size


# ── Bucket helpers ─────────────────────────────────────────────────────────────

_BUCKET_COLOR = {
    "due_today": _BLUE,
    "upcoming":  _PURPLE,
    "unplanned": _ORANGE,
}

_BUCKET_LABEL = {
    "due_today": "TODAY",
    "upcoming":  "UPCOMING",
    "unplanned": "UNPLANNED",
}

_BUCKET_ICONS = {
    "due_today": "icon_task_1.png",
    "upcoming":  "icon_task_2.png",
    "unplanned": "icon_task_3.png",
}


def _categorize(row: dict) -> str | None:
    """Return 'due_today', 'upcoming', or 'unplanned'; None if done/cancelled."""
    status = (row.get("status") or "").lower()
    if status in ("completed", "cancelled"):
        return None
    due_at    = row.get("due_at")    or ""
    remind_at = row.get("remind_at") or ""
    raw = (due_at or remind_at).strip()
    if not raw:
        return "unplanned"
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        today_end = display_now().replace(hour=23, minute=59, second=59, microsecond=0)
        # Make both offset-naive for comparison
        if hasattr(d, 'tzinfo') and d.tzinfo is not None:
            try:
                from config import to_display_local
                d = to_display_local(d).replace(tzinfo=None)
            except Exception:
                d = d.replace(tzinfo=None)
        today_end_naive = today_end.replace(tzinfo=None)
        return "due_today" if d <= today_end_naive else "upcoming"
    except Exception:
        return "unplanned"


def _fmt_due(row: dict, bucket: str) -> str:
    if bucket == "unplanned":
        return "No date"
    raw = (row.get("due_at") or row.get("remind_at") or "").strip()
    if not raw:
        return "—"
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if hasattr(d, 'tzinfo') and d.tzinfo is not None:
            try:
                from config import to_display_local
                d = to_display_local(d).replace(tzinfo=None)
            except Exception:
                d = d.replace(tzinfo=None)
        now = display_now()
        if bucket == "due_today":
            return d.strftime("%-I:%M %p") if hasattr(d, 'strftime') else str(d)
        delta = (d.date() - now.date()).days
        if delta == 1:
            return "Tomorrow"
        return d.strftime("%b %-d")
    except Exception:
        return "—"


def _source_label(row: dict) -> str:
    src = (row.get("source") or "").lower()
    if "calendar" in src or "event" in src:
        return "calendar"
    if "email" in src or "gmail" in src:
        return "email"
    return "profile"


# ── Tasks Screen ───────────────────────────────────────────────────────────────

class TasksScreen(BaseScreen):
    """Tasks / commitments screen — Figma 569:193 (1260 × 800 px)."""

    def __init__(self, **kw):
        super().__init__(**kw)

        # Active filter tab: 'all' | 'due_today' | 'upcoming' | 'unplanned'
        self._active_tab: str = "all"

        # Raw rows from API, keyed by bucket
        self._rows: dict[str, list] = {
            "due_today": [],
            "upcoming":  [],
            "unplanned": [],
        }

        # Loading / empty state
        self._loading: bool = False

        # Tab label widgets (so we can re-colour on selection)
        self._tab_labels: dict[str, Label] = {}
        self._tab_underlines: dict[str, Widget] = {}

        # Count badge labels per tab
        self._count_labels: dict[str, Label] = {}

        # The BoxLayout inside the ScrollView — rebuilt on filter change or data load
        self._list_box: BoxLayout | None = None

        # Header task-count label (total active)
        self._header_count_lbl: Label | None = None

        # Status label (loading / empty)
        self._status_lbl: Label | None = None

        # Root layout reference (held so we can add/remove the status label)
        self._root_layout: FloatLayout | None = None

        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = FloatLayout(size_hint=(1, 1))
        self._root_layout = root

        # Solid background
        with root.canvas.before:
            Color(*_BG)
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, v: setattr(self._bg_rect, "pos", v),
            size=lambda w, v: setattr(self._bg_rect, "size", v),
        )

        self._build_header(root)
        self._build_filter_bar(root)
        self._build_scroll_area(root)

        self.add_widget(root)

    # ── Header (Figma top: 0 → ~100 px) ───────────────────────────────────────
    # Back btn : (24, 21)   76 × 76
    # Icon tick: (118, 28)  42 × 42
    # Title    : (170, 28)  ~300 × 46
    # Count    : (right)

    def _build_header(self, root: FloatLayout) -> None:
        # Back button
        back_src = _cal_asset("btn_back.png")
        if back_src:
            back = _ImgBtn(source=back_src, fit_mode="contain",
                           **_ph(24.02, 21.19, 76.28, 76.28))
            back.bind(on_release=lambda *_: self.go_back())
        else:
            back = _TapCard(ct=_CARD_T, cb=_CARD_B, bdr=_BDR,
                            r=_ff(38), **_ph(24.02, 21.19, 76.28, 76.28))
            back.add_widget(_lbl("‹", _FSB, _ff(36), _WHITE,
                                 ha="center", va="middle",
                                 size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
            back.bind(on_release=lambda *_: self.go_back())
        root.add_widget(back)

        # Task icon (reuse tick icon from brief assets)
        tick_src = _brief_asset("icon_tick.png")
        if tick_src:
            root.add_widget(Image(
                source=tick_src, fit_mode="contain",
                **_ph(118.0, 27.0, 42.0, 42.0)))

        # "Tasks" title
        root.add_widget(_lbl(
            "Tasks", _FSB, _ff(38.52), _WHITE,
            va="middle",
            **_ph(170.0, 14.0, 300.0, 56.0)))

        # Total count badge (e.g.  "12 tasks")
        self._header_count_lbl = _lbl(
            "", _FMD, _ff(22.0), _MUTED,
            ha="right", va="middle",
            **_ph(800.0, 14.0, 420.0, 56.0))
        root.add_widget(self._header_count_lbl)

        # Horizontal divider under header
        div = Widget(**_ph(22.6, 100.0, 1214.8, 2.0))
        with div.canvas.before:
            Color(*_DIV_COL)
            _r = Rectangle(pos=div.pos, size=div.size)
        div.bind(pos=lambda w, v: setattr(_r, "pos", v),
                 size=lambda w, v: setattr(_r, "size", v))
        root.add_widget(div)

    # ── Filter bar (Figma top: ~104 → ~165 px) ────────────────────────────────
    # Four tab pills with counts.  Active tab gets blue text + blue underline.

    def _build_filter_bar(self, root: FloatLayout) -> None:
        TABS = [
            ("all",       "All"),
            ("due_today", "Today"),
            ("upcoming",  "Upcoming"),
            ("unplanned", "Unplanned"),
        ]
        # Container card for the filter bar
        bar = _Card(ct=_CARD_T, cb=_CARD_B, bdr=_BDR,
                    r=_ff(18.0),
                    **_ph(22.6, 109.0, 1214.8, 62.0))
        root.add_widget(bar)

        # Tab widths: distribute evenly inside the 1214.8 bar
        # Figma: 4 equal slots in a 1214.8-wide bar, pad 24 each side
        TAB_W = (1214.8 - 48) / 4   # ≈ 291.7
        TAB_H = 62.0
        PAD_L = 24.0

        for i, (tab_id, tab_lbl) in enumerate(TABS):
            tx = PAD_L + i * TAB_W
            # Tap area (full tab cell)
            tap = _TapCard(
                ct=(0, 0, 0, 0), cb=(0, 0, 0, 0),
                bdr=(0, 0, 0, 0), bdr_alpha=0.0,
                size_hint=(TAB_W / 1214.8, 1.0),
                pos_hint={"x": tx / 1214.8, "y": 0.0})

            is_active = (tab_id == self._active_tab)
            lbl_col = _BLUE if is_active else _MUTED

            # Tab label
            lbl = _lbl(tab_lbl, _FSB, _ff(22.0), lbl_col,
                       ha="center", va="middle",
                       size_hint=(0.65, 0.7),
                       pos_hint={"x": 0.05, "y": 0.15})
            tap.add_widget(lbl)
            self._tab_labels[tab_id] = lbl

            # Count badge
            cnt = _lbl("", _FMD, _ff(18.0),
                       _BLUE if is_active else _WHITE,
                       ha="left", va="middle",
                       size_hint=(0.3, 0.7),
                       pos_hint={"x": 0.65, "y": 0.15})
            tap.add_widget(cnt)
            self._count_labels[tab_id] = cnt

            # Blue underline indicator (visible only on active tab)
            underline = Widget(
                size_hint=(0.7, None),
                height=_ff(3),
                pos_hint={"x": 0.15, "y": 0.0})
            with underline.canvas.before:
                Color(*(_BLUE if is_active else (0, 0, 0, 0)))
                _rl = Rectangle(pos=underline.pos, size=underline.size)
            underline.bind(
                pos=lambda w, v, r=_rl: setattr(r, "pos", v),
                size=lambda w, v, r=_rl: setattr(r, "size", v))
            tap.add_widget(underline)
            self._tab_underlines[tab_id] = underline

            # Bind tap
            _tid = tab_id
            tap.bind(on_release=lambda *_, tid=_tid: self._on_tab(tid))
            bar.add_widget(tap)

    # ── Scroll area (Figma top: ~179 → ~778 px) ───────────────────────────────

    def _build_scroll_area(self, root: FloatLayout) -> None:
        # Outer card
        outer = _Card(ct=_CARD_T, cb=_CARD_B, bdr=_BDR,
                      r=_ff(22.6),
                      **_ph(22.6, 179.0, 1214.8, 600.0))
        root.add_widget(outer)

        # ScrollView fills the outer card
        sv = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=_ff(6),
            scroll_type=["bars", "content"],
        )

        # BoxLayout — content container
        box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[_ff(14), _ff(8), _ff(14), _ff(8)],
            spacing=0,
        )
        box.bind(minimum_height=box.setter("height"))
        self._list_box = box

        sv.add_widget(box)
        outer.add_widget(sv)

        # Status label (loading / empty) — placed inside box
        self._status_lbl = _lbl(
            "Loading tasks…", _FMD, _ff(22.0), _MUTED,
            ha="center", va="middle",
            size_hint=(1, None), height=_ff(60))
        box.add_widget(self._status_lbl)

    # ── Tab interaction ────────────────────────────────────────────────────────

    def _on_tab(self, tab_id: str) -> None:
        if tab_id == self._active_tab:
            return
        self._active_tab = tab_id
        self._refresh_tab_styles()
        self._rebuild_task_list()

    def _refresh_tab_styles(self) -> None:
        for tid, lbl in self._tab_labels.items():
            lbl.color = _BLUE if tid == self._active_tab else _MUTED
        for tid, lbl in self._count_labels.items():
            lbl.color = _BLUE if tid == self._active_tab else _WHITE
        # Redraw underlines by toggling color via canvas — simpler: rebuild all
        for tid, ul in self._tab_underlines.items():
            ul.canvas.before.clear()
            with ul.canvas.before:
                Color(*(_BLUE if tid == self._active_tab else (0, 0, 0, 0)))
                _rl = Rectangle(pos=ul.pos, size=ul.size)
            ul.bind(
                pos=lambda w, v, r=_rl: setattr(r, "pos", v),
                size=lambda w, v, r=_rl: setattr(r, "size", v))

    # ── Task list builder ──────────────────────────────────────────────────────

    def _rebuild_task_list(self) -> None:
        if self._list_box is None:
            return
        self._list_box.clear_widgets()

        # Decide which buckets to show
        if self._active_tab == "all":
            buckets = ["due_today", "upcoming", "unplanned"]
        else:
            buckets = [self._active_tab]

        any_tasks = False
        for bucket in buckets:
            rows = self._rows.get(bucket, [])
            if not rows:
                continue
            any_tasks = True
            self._add_section_header(bucket, len(rows))
            for row in rows:
                self._add_task_row(row, bucket)

        if not any_tasks:
            msg = "No tasks" if not self._loading else "Loading tasks…"
            empty = _lbl(msg, _FMD, _ff(22.0), _MUTED,
                         ha="center", va="middle",
                         size_hint=(1, None), height=_ff(80))
            self._list_box.add_widget(empty)

    def _add_section_header(self, bucket: str, count: int) -> None:
        """Add a coloured section header row (e.g. "TODAY  3")."""
        col = _BUCKET_COLOR[bucket]
        label_text = _BUCKET_LABEL[bucket]
        H = _ff(44)

        hdr = FloatLayout(size_hint=(1, None), height=H)
        with hdr.canvas.before:
            Color(*_SEC_BG)
            _r = RoundedRectangle(pos=hdr.pos, size=hdr.size, radius=[_ff(8)])
        hdr.bind(
            pos=lambda w, v, r=_r: setattr(r, "pos", v),
            size=lambda w, v, r=_r: (setattr(r, "size", v) or
                                     setattr(r, "radius", [_ff(8)])))

        # Colour accent bar (left edge)
        accent = Widget(size_hint=(None, 1), width=_ff(4))
        accent.pos_hint = {"x": 0, "y": 0}
        with accent.canvas:
            Color(*col)
            _ea = Rectangle(pos=accent.pos, size=accent.size)
        accent.bind(pos=lambda w, v, r=_ea: setattr(r, "pos", v),
                    size=lambda w, v, r=_ea: setattr(r, "size", v))
        hdr.add_widget(accent)

        # Bucket icon
        icon_src = _brief_asset(_BUCKET_ICONS[bucket])
        if icon_src:
            hdr.add_widget(Image(
                source=icon_src, fit_mode="contain",
                size_hint=(None, 0.65), width=_ff(28),
                pos_hint={"x": _ff(12) / 1200, "y": 0.175}))

        # Label
        hdr.add_widget(_lbl(
            label_text, _FSB, _ff(20.0), col,
            ha="left", va="middle",
            size_hint=(0.55, 1),
            pos_hint={"x": _ff(50) / 1200, "y": 0}))

        # Count
        hdr.add_widget(_lbl(
            str(count), _FSB, _ff(20.0), col,
            ha="left", va="middle",
            size_hint=(0.1, 1),
            pos_hint={"x": 0.6, "y": 0}))

        self._list_box.add_widget(hdr)
        # Thin spacing
        self._list_box.add_widget(Widget(size_hint=(1, None), height=_ff(4)))

    def _add_task_row(self, row: dict, bucket: str) -> None:
        """Add a single task row card."""
        ROW_H = _ff(70)
        col = _BUCKET_COLOR[bucket]
        title = (row.get("title") or "Untitled task").strip()
        due_lbl = _fmt_due(row, bucket)
        src_type = _source_label(row)

        card = _Card(ct=_ROW_T, cb=_ROW_B, bdr=_BDR,
                     r=_ff(14),
                     size_hint=(1, None), height=ROW_H)

        # Status dot
        dot = _DotWidget(
            color=col,
            size_hint=(None, None),
            size=(_ff(12), _ff(12)),
            pos_hint={"x": _ff(20) / 1200, "y": 0.5 - _ff(6) / ROW_H})
        card.add_widget(dot)

        # Task title
        card.add_widget(_lbl(
            title, _FSB, _ff(22.0), _WHITE,
            ha="left", va="middle",
            size_hint=(0.6, 1),
            pos_hint={"x": _ff(44) / 1200, "y": 0}))

        # Source icon (small)
        src_img_map = {
            "calendar": "icon_calendar.png",
            "email":    "icon_email.png",
            "profile":  "icon_sparkle.png",
        }
        src_img = _brief_asset(src_img_map.get(src_type, "icon_tick.png"))
        if src_img:
            card.add_widget(Image(
                source=src_img, fit_mode="contain",
                size_hint=(None, 0.5), width=_ff(22),
                pos_hint={"x": 0.72, "y": 0.25}))

        # Source label text
        src_txt = src_type.capitalize()
        card.add_widget(_lbl(
            src_txt, _FMD, _ff(16.0), _MUTED,
            ha="left", va="middle",
            size_hint=(0.12, 1),
            pos_hint={"x": 0.76, "y": 0}))

        # Due date
        card.add_widget(_lbl(
            due_lbl, _FMD, _ff(18.0), col,
            ha="right", va="middle",
            size_hint=(0.15, 1),
            pos_hint={"x": 0.84, "y": 0}))

        self._list_box.add_widget(card)
        # Row spacing
        self._list_box.add_widget(Widget(size_hint=(1, None), height=_ff(6)))

    # ── Count badge updater ────────────────────────────────────────────────────

    def _update_counts(self) -> None:
        counts = {
            "due_today": len(self._rows["due_today"]),
            "upcoming":  len(self._rows["upcoming"]),
            "unplanned": len(self._rows["unplanned"]),
        }
        total = sum(counts.values())
        counts["all"] = total

        for tab_id, lbl in self._count_labels.items():
            n = counts.get(tab_id, 0)
            lbl.text = str(n) if n > 0 else ""

        if self._header_count_lbl is not None:
            self._header_count_lbl.text = (
                f"{total} task{'s' if total != 1 else ''}" if total > 0 else "No tasks"
            )

    # ── Data loading ───────────────────────────────────────────────────────────

    def _load_tasks(self) -> None:
        async def _go():
            try:
                result = await self.backend.get_commitments(status="", limit=80)
            except Exception as exc:
                logger.warning("tasks: get_commitments failed: %s", exc)
                result = {"commitments": [], "count": 0}

            rows = result.get("commitments") or []
            bucketed: dict[str, list] = {
                "due_today": [],
                "upcoming":  [],
                "unplanned": [],
            }
            for r in rows:
                bucket = _categorize(r)
                if bucket is not None:
                    bucketed[bucket].append(r)

            def _apply(_dt):
                self._loading = False
                self._rows = bucketed
                self._update_counts()
                self._rebuild_task_list()

            Clock.schedule_once(_apply, 0)

        run_async(_go())

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_enter(self) -> None:
        self._loading = True
        # Show loading state
        if self._list_box is not None:
            self._list_box.clear_widgets()
            self._list_box.add_widget(
                _lbl("Loading tasks…", _FMD, _ff(22.0), _MUTED,
                     ha="center", va="middle",
                     size_hint=(1, None), height=_ff(80)))
        Clock.schedule_once(lambda _dt: self._load_tasks(), 0)

    def on_leave(self) -> None:
        pass

"""Tasks screen — Figma node 569:193 (1260 × 800 px).

Displays the user's commitments/tasks, grouped by Due Today / Upcoming /
Unplanned, with filter tabs (All · Today · Upcoming · Unplanned) and a
scrollable task list.  Data is loaded from the backend commitments API on
every on_enter and auto-refreshed every 60 s while the screen is active.

Layout mirrors the Figma device-UI design:
  BACK BTN  : (24.02, 21.19)  76.28 × 76.28   — reuses calendar/figma/btn_back.png
  TITLE     : (170, 14)        "Tasks"  38.52 px SemiBold
  FILTER BAR: (22.6, 109)      1214.8 × 62      four tabs All/Today/Upcoming/Unplanned
  LIST AREA : (22.6, 179)      1214.8 × 600     ScrollView → BoxLayout

Font sizes use the established Figma measurement system from morning_brief.py:
  _ff(38.52)  heading
  _ff(21.19)  tab labels / task titles / sub-headings
  _ff(16.95)  secondary text / due labels / count badges
  _ff(14.13)  micro labels (source type)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

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

# Auto-refresh interval while screen is open (seconds)
_REFRESH_INTERVAL = 60.0

# ── Asset directories ──────────────────────────────────────────────────────────
_BRIEF_DIR = ASSETS_DIR / "brief"    / "figma"
_CAL_DIR   = ASSETS_DIR / "calendar" / "figma"
_HOME_DIR  = ASSETS_DIR / "home"     / "figma"


def _brief_asset(name: str) -> str:
    p = _BRIEF_DIR / name
    return str(p) if p.is_file() else ""


def _cal_asset(name: str) -> str:
    p = _CAL_DIR / name
    return str(p) if p.is_file() else ""


def _home_asset(name: str) -> str:
    p = _HOME_DIR / name
    return str(p) if p.is_file() else ""


# ── Colours — exact Figma hex values from morning_brief.py ────────────────────
_BG      = (1/255,   8/255,  26/255, 1.0)   # #01081A  screen background
_WHITE   = (1.0, 1.0, 1.0, 1.0)
_MUTED   = (182/255, 186/255, 242/255, 1.0) # #B6BAF2  secondary text
_DIM     = (155/255, 162/255, 178/255, 1.0) # #9BA2B2  meta / source label
_BLUE    = (0.0,   107/255, 249/255, 1.0)   # #006BF9  Today / active tab
_PURPLE  = (169/255, 113/255, 212/255, 1.0) # #A971D4  Upcoming
_ORANGE  = (241/255, 137/255,   3/255, 1.0) # #F18903  Unplanned

# Card gradient stops  (same as morning_brief.py _SCH_T / _SCH_B)
_CARD_T  = (1/255,  17/255,  55/255, 1.0)   # #011137
_CARD_B  = (0.0,   10/255,  38/255, 1.0)    # #000A26
# Row gradient stops  (slightly lighter top)
_ROW_T   = (2/255,  18/255,  60/255, 1.0)   # #02123C
_ROW_B   = _CARD_B

# Border / divider colours
_BDR     = (63/255,  66/255,  83/255, 1.0)  # #3F4253  (same as morning_brief _BDR)
_DIV_COL = (2/255,   23/255,  77/255, 0.7)  # subtle section divider

# Section-header tint
_SEC_BG  = (4/255,   15/255,  44/255, 0.90) # #040F2C 90 %

# Font names (registered in main.py via _register_asta_fonts)
_FSB = "42dot-SB"    # SemiBold  — headings / tab labels / task titles
_FB  = "42dot-Sans"  # Regular+Bold weight
_FMD = "42dot-Med"   # Medium    — secondary text


# ── Coordinate helpers  (Figma absolute px → Kivy FloatLayout fractions) ──────

def _ph(fx: float, fy: float, fw: float, fh: float) -> dict:
    """Figma absolute px → Kivy size_hint + pos_hint for a 1260×800 root."""
    return {
        "size_hint": (fw / FW, fh / FH),
        "pos_hint":  {"x": fx / FW, "y": (FH - fy - fh) / FH},
    }


def _ff(fs: float) -> int:
    """Scale a Figma font/pixel value by the display scale factor → int px."""
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


# ── Widget factories ───────────────────────────────────────────────────────────

def _lbl(text: str, font: str, size: int | float, color: tuple,
         ha: str = "left", va: str = "top", **kw) -> Label:
    lw = Label(text=text, font_name=font, font_size=size, color=color,
               halign=ha, valign=va, **kw)
    lw.bind(size=lw.setter("text_size"))
    return lw


class _ImgBtn(ButtonBehavior, Image):
    pass


class _Card(FloatLayout):
    """Gradient card with rounded border line — matches morning_brief._Card."""

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


class _Dot(Widget):
    """Solid-colour circular dot (status indicator)."""

    def __init__(self, color: tuple, **kw):
        super().__init__(**kw)
        with self.canvas:
            Color(*color)
            self._e = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=self._s, size=self._s)

    def _s(self, *_):
        self._e.pos = self.pos
        self._e.size = self.size


# ── Date / time helpers ────────────────────────────────────────────────────────

def _parse_dt(raw: str) -> datetime | None:
    """Parse an ISO-8601 datetime string, stripping tz for local comparison."""
    if not raw:
        return None
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if d.tzinfo is not None:
            try:
                from config import to_display_local
                d = to_display_local(d).replace(tzinfo=None)
            except Exception:
                d = d.replace(tzinfo=None)
        return d
    except Exception:
        return None


def _fmt_time(d: datetime) -> str:
    """Format a datetime as a 12-hour time string, cross-platform."""
    h = d.hour % 12 or 12
    ampm = "AM" if d.hour < 12 else "PM"
    return f"{h}:{d.minute:02d} {ampm}"


def _fmt_due(row: dict, bucket: str) -> str:
    """Return a human-readable due label for a task row."""
    if bucket == "unplanned":
        return "No date"
    raw = (row.get("due_at") or row.get("remind_at") or "").strip()
    d = _parse_dt(raw)
    if d is None:
        return "—"
    now = display_now()
    if bucket == "due_today":
        delta_min = int((d - now).total_seconds() / 60)
        if -5 <= delta_min <= 0:
            return "Now"
        if 0 < delta_min < 60:
            return f"in {delta_min} min"
        if delta_min < 0:
            return f"{-delta_min} min ago"
        return _fmt_time(d)
    # upcoming
    days = (d.date() - now.date()).days
    if days == 0:
        return _fmt_time(d)
    if days == 1:
        return "Tomorrow"
    MONTHS = ("Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec")
    return f"{MONTHS[d.month - 1]} {d.day}"


def _categorize(row: dict) -> str | None:
    """Bucket a commitment into 'due_today' / 'upcoming' / 'unplanned'; None if inactive."""
    status = (row.get("status") or "").lower()
    if status in ("completed", "cancelled"):
        return None
    raw = (row.get("due_at") or row.get("remind_at") or "").strip()
    if not raw:
        return "unplanned"
    d = _parse_dt(raw)
    if d is None:
        return "unplanned"
    today_end = display_now().replace(hour=23, minute=59, second=59, microsecond=0)
    return "due_today" if d <= today_end else "upcoming"


def _source_kind(row: dict) -> str:
    src = (row.get("source") or "").lower()
    if "calendar" in src or "event" in src:
        return "calendar"
    if "email" in src or "gmail" in src:
        return "email"
    return "profile"


# ── Bucket metadata ────────────────────────────────────────────────────────────

_BUCKET_COLOR = {"due_today": _BLUE, "upcoming": _PURPLE, "unplanned": _ORANGE}
_BUCKET_LABEL = {"due_today": "TODAY", "upcoming": "UPCOMING", "unplanned": "UNPLANNED"}
_BUCKET_ICONS = {
    "due_today": "icon_task_1.png",
    "upcoming":  "icon_task_2.png",
    "unplanned": "icon_task_3.png",
}
_SRC_ICONS = {
    "calendar": "icon_calendar.png",
    "email":    "icon_email.png",
    "profile":  "icon_sparkle.png",
}


# ── TasksScreen ────────────────────────────────────────────────────────────────

class TasksScreen(BaseScreen):
    """Tasks / commitments screen — Figma 569:193 (1260 × 800 px).

    Real-time behaviour:
      • Data is fetched from GET /api/commitments on every on_enter.
      • A 60 s Clock interval re-fetches while the screen is active.
      • Due-time labels are regenerated from live display_now() on each reload.
    """

    def __init__(self, **kw):
        super().__init__(**kw)

        self._active_tab: str = "all"
        self._rows: dict[str, list] = {
            "due_today": [], "upcoming": [], "unplanned": []
        }
        self._loading: bool = False
        self._refresh_ev = None           # Clock interval handle

        # Widget references
        self._tab_labels:    dict[str, Label]  = {}
        self._tab_underlines: dict[str, Widget] = {}
        self._count_labels:  dict[str, Label]  = {}
        self._list_box:      BoxLayout | None   = None
        self._header_count_lbl: Label | None    = None
        self._last_updated_lbl: Label | None    = None
        self._last_fetch_dt:    datetime | None = None

        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = FloatLayout(size_hint=(1, 1))
        with root.canvas.before:
            Color(*_BG)
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, v: setattr(self._bg_rect, "pos", v),
            size=lambda w, v: setattr(self._bg_rect, "size", v),
        )
        self._build_header(root)
        self._build_filter_bar(root)
        self._build_list_area(root)
        self.add_widget(root)

    # ── Header ─────────────────────────────────────────────────────────────────
    # Figma reference values mirrored from calendar.py header:
    #   Back button : (24.02, 21.19)  76.28 × 76.28
    #   Title       : (170, 14)        font 38.52 SemiBold  → _ff(38.52)
    #   Count badge : right-aligned    font 21.19 Medium

    def _build_header(self, root: FloatLayout) -> None:
        # Back button (identical to calendar.py / emails.py)
        back_src = _cal_asset("btn_back.png")
        if back_src:
            back = _ImgBtn(source=back_src, fit_mode="contain",
                           **_ph(24.02, 21.19, 76.28, 76.28))
            back.bind(on_release=lambda *_: self.go_back())
        else:
            back = _TapCard(ct=_CARD_T, cb=_CARD_B, bdr=_BDR,
                            r=_ff(38.14), **_ph(24.02, 21.19, 76.28, 76.28))
            back.add_widget(_lbl("‹", _FSB, _ff(36), _WHITE,
                                 ha="center", va="middle",
                                 size_hint=(1, 1), pos_hint={"x": 0, "y": 0}))
            back.bind(on_release=lambda *_: self.go_back())
        root.add_widget(back)

        # Tasks icon — reuse brief asset (icon_tick.png = checkmark)
        tick_src = _brief_asset("icon_tick.png")
        if tick_src:
            root.add_widget(Image(source=tick_src, fit_mode="contain",
                                  **_ph(118.0, 27.0, 42.38, 42.38)))

        # "Tasks" heading — font 38.52 px (matches "Today" heading in calendar.py)
        root.add_widget(_lbl(
            "Tasks", _FSB, _ff(38.52), _WHITE,
            va="middle",
            **_ph(170.0, 14.0, 280.0, 56.0)))

        # Task count  (e.g. "14 tasks")
        self._header_count_lbl = _lbl(
            "", _FMD, _ff(21.19), _MUTED,
            ha="right", va="middle",
            **_ph(750.0, 14.0, 468.0, 56.0))
        root.add_widget(self._header_count_lbl)

        # "Updated X ago" — right-aligned, smaller, dim colour
        self._last_updated_lbl = _lbl(
            "", _FMD, _ff(14.13), _DIM,
            ha="right", va="middle",
            **_ph(750.0, 52.0, 468.0, 30.0))
        root.add_widget(self._last_updated_lbl)

        # Horizontal divider (same position as morning_brief bottom of header)
        div = Widget(**_ph(22.6, 100.0, 1214.8, 1.89))
        with div.canvas.before:
            Color(*_DIV_COL)
            _r = Rectangle(pos=div.pos, size=div.size)
        div.bind(pos=lambda w, v: setattr(_r, "pos", v),
                 size=lambda w, v: setattr(_r, "size", v))
        root.add_widget(div)

    # ── Filter bar ─────────────────────────────────────────────────────────────
    # Figma: (22.6, 109)  1214.8 × 62   radius 16.95
    # 4 equal-width tab cells.  Active: blue text + blue 3 px underline.
    # Font: 21.19 px SemiBold (tab label) + 16.95 px Medium (count badge).

    def _build_filter_bar(self, root: FloatLayout) -> None:
        TABS = [
            ("all",       "All"),
            ("due_today", "Today"),
            ("upcoming",  "Upcoming"),
            ("unplanned", "Unplanned"),
        ]
        bar = _Card(ct=_CARD_T, cb=_CARD_B, bdr=_BDR,
                    r=_ff(16.95), **_ph(22.6, 109.0, 1214.8, 62.0))
        root.add_widget(bar)

        # Each tab occupies 25 % of the bar width
        for i, (tab_id, tab_text) in enumerate(TABS):
            tap = _TapCard(
                ct=(0, 0, 0, 0), cb=(0, 0, 0, 0),
                bdr=(0, 0, 0, 0), bdr_alpha=0.0,
                size_hint=(0.25, 1.0),
                pos_hint={"x": i * 0.25, "y": 0.0})

            is_active = (tab_id == self._active_tab)

            # Tab label — 21.19 px SemiBold (Figma morning_brief section size)
            lbl = _lbl(tab_text, _FSB, _ff(21.19),
                       _BLUE if is_active else _MUTED,
                       ha="center", va="middle",
                       size_hint=(0.65, 0.72),
                       pos_hint={"x": 0.04, "y": 0.14})
            tap.add_widget(lbl)
            self._tab_labels[tab_id] = lbl

            # Count badge — 16.95 px Medium
            cnt = _lbl("", _FMD, _ff(16.95),
                       _BLUE if is_active else _WHITE,
                       ha="left", va="middle",
                       size_hint=(0.28, 0.72),
                       pos_hint={"x": 0.68, "y": 0.14})
            tap.add_widget(cnt)
            self._count_labels[tab_id] = cnt

            # Active-tab underline (3 px blue bar at bottom)
            ul = Widget(size_hint=(0.72, None), height=_ff(3.0),
                        pos_hint={"x": 0.14, "y": 0.0})
            with ul.canvas.before:
                Color(*(_BLUE if is_active else (0, 0, 0, 0)))
                _rl = Rectangle(pos=ul.pos, size=ul.size)
            ul.bind(pos=lambda w, v, r=_rl: setattr(r, "pos", v),
                    size=lambda w, v, r=_rl: setattr(r, "size", v))
            tap.add_widget(ul)
            self._tab_underlines[tab_id] = ul

            _tid = tab_id
            tap.bind(on_release=lambda *_, tid=_tid: self._on_tab(tid))
            bar.add_widget(tap)

    # ── Scrollable task list area ───────────────────────────────────────────────
    # Figma: (22.6, 179)  1214.8 × 600   radius 22.6

    def _build_list_area(self, root: FloatLayout) -> None:
        outer = _Card(ct=_CARD_T, cb=_CARD_B, bdr=_BDR,
                      r=_ff(22.6), **_ph(22.6, 179.0, 1214.8, 600.0))
        root.add_widget(outer)

        sv = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=_ff(5),
            bar_color=[*_BLUE[:3], 0.6],
            bar_inactive_color=[*_MUTED[:3], 0.2],
            scroll_type=["bars", "content"],
        )
        box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[_ff(14), _ff(10), _ff(14), _ff(10)],
            spacing=0,
        )
        box.bind(minimum_height=box.setter("height"))
        self._list_box = box

        sv.add_widget(box)
        outer.add_widget(sv)

        # Initial "loading" placeholder
        box.add_widget(_lbl(
            "Loading tasks…", _FMD, _ff(21.19), _MUTED,
            ha="center", va="middle",
            size_hint=(1, None), height=_ff(80)))

    # ── Tab selection ──────────────────────────────────────────────────────────

    def _on_tab(self, tab_id: str) -> None:
        if tab_id == self._active_tab:
            return
        self._active_tab = tab_id
        self._sync_tab_styles()
        self._rebuild_task_list()

    def _sync_tab_styles(self) -> None:
        for tid, lbl in self._tab_labels.items():
            lbl.color = _BLUE if tid == self._active_tab else _MUTED
        for tid, lbl in self._count_labels.items():
            lbl.color = _BLUE if tid == self._active_tab else _WHITE
        for tid, ul in self._tab_underlines.items():
            ul.canvas.before.clear()
            with ul.canvas.before:
                Color(*(_BLUE if tid == self._active_tab else (0, 0, 0, 0)))
                _rl = Rectangle(pos=ul.pos, size=ul.size)
            ul.bind(pos=lambda w, v, r=_rl: setattr(r, "pos", v),
                    size=lambda w, v, r=_rl: setattr(r, "size", v))

    # ── Task list builder ──────────────────────────────────────────────────────

    def _rebuild_task_list(self) -> None:
        if self._list_box is None:
            return
        self._list_box.clear_widgets()

        buckets = (["due_today", "upcoming", "unplanned"]
                   if self._active_tab == "all"
                   else [self._active_tab])

        has_any = False
        for bucket in buckets:
            rows = self._rows.get(bucket, [])
            if not rows:
                continue
            has_any = True
            self._add_section_header(bucket, len(rows))
            for row in rows:
                self._add_task_row(row, bucket)
            # Gap between sections
            self._list_box.add_widget(Widget(size_hint=(1, None), height=_ff(8)))

        if not has_any:
            msg = "Loading tasks…" if self._loading else "No tasks to show"
            self._list_box.add_widget(_lbl(
                msg, _FMD, _ff(21.19), _MUTED,
                ha="center", va="middle",
                size_hint=(1, None), height=_ff(100)))

    # Figma section header row height: ~50 px (morning_brief dividers at ~81 px spacing)
    def _add_section_header(self, bucket: str, count: int) -> None:
        col = _BUCKET_COLOR[bucket]
        H = _ff(50.0)

        hdr = FloatLayout(size_hint=(1, None), height=H)
        with hdr.canvas.before:
            Color(*_SEC_BG)
            _rbg = RoundedRectangle(pos=hdr.pos, size=hdr.size, radius=[_ff(10)])
        hdr.bind(
            pos=lambda w, v, r=_rbg: setattr(r, "pos", v),
            size=lambda w, v, r=_rbg: (setattr(r, "size", v) or
                                       setattr(r, "radius", [_ff(10)])))

        # Left colour accent bar (4 px wide)
        accent = Widget(size_hint=(None, 1), width=_ff(4),
                        pos_hint={"x": 0.0, "y": 0.0})
        with accent.canvas:
            Color(*col)
            _ra = Rectangle(pos=accent.pos, size=accent.size)
        accent.bind(pos=lambda w, v, r=_ra: setattr(r, "pos", v),
                    size=lambda w, v, r=_ra: setattr(r, "size", v))
        hdr.add_widget(accent)

        # Bucket icon (31.08 px, as per morning_brief icon row: icon_y offset)
        icon_src = _brief_asset(_BUCKET_ICONS[bucket])
        if icon_src:
            hdr.add_widget(Image(source=icon_src, fit_mode="contain",
                                 size_hint=(None, 0.60), width=_ff(31.08),
                                 pos_hint={"x": _ff(12) / 1200, "y": 0.20}))

        # Section label — 16.95 px SemiBold (morning_brief sub-label size)
        hdr.add_widget(_lbl(
            _BUCKET_LABEL[bucket], _FSB, _ff(16.95), col,
            ha="left", va="middle",
            size_hint=(0.50, 1.0),
            pos_hint={"x": _ff(55) / 1200, "y": 0.0}))

        # Count
        hdr.add_widget(_lbl(
            str(count), _FSB, _ff(16.95), col,
            ha="left", va="middle",
            size_hint=(0.08, 1.0),
            pos_hint={"x": 0.60, "y": 0.0}))

        self._list_box.add_widget(hdr)
        self._list_box.add_widget(Widget(size_hint=(1, None), height=_ff(5)))

    # Task row height: _ff(80) — wider than morning_brief rows to allow title + meta
    def _add_task_row(self, row: dict, bucket: str) -> None:
        col = _BUCKET_COLOR[bucket]
        title = (row.get("title") or "Untitled task").strip()
        detail = (row.get("detail") or "").strip()
        due_text = _fmt_due(row, bucket)
        src_kind = _source_kind(row)

        ROW_H = _ff(80)

        card = _Card(ct=_ROW_T, cb=_ROW_B, bdr=_BDR,
                     r=_ff(14.13),
                     size_hint=(1, None), height=ROW_H)

        # Status dot — 11.3 px diameter (morning_brief _add_dot size)
        D = _ff(11.3)
        dot = _Dot(color=col,
                   size_hint=(None, None), size=(D, D),
                   pos_hint={"x": _ff(18) / 1200,
                             "y": 0.5 - D / (2 * ROW_H)})
        card.add_widget(dot)

        # Task title — 21.19 px SemiBold (morning_brief section heading size)
        title_x = _ff(42) / 1200
        if detail:
            # Title at top 55 %, detail at bottom 35 %
            card.add_widget(_lbl(
                title, _FSB, _ff(21.19), _WHITE,
                ha="left", va="bottom",
                size_hint=(0.60, 0.52),
                pos_hint={"x": title_x, "y": 0.42}))
            card.add_widget(_lbl(
                detail[:80], _FMD, _ff(14.13), _MUTED,
                ha="left", va="top",
                size_hint=(0.60, 0.35),
                pos_hint={"x": title_x, "y": 0.08}))
        else:
            card.add_widget(_lbl(
                title, _FSB, _ff(21.19), _WHITE,
                ha="left", va="middle",
                size_hint=(0.60, 1.0),
                pos_hint={"x": title_x, "y": 0.0}))

        # Source icon — 22.6 px (morning_brief icon sizes)
        src_img = _brief_asset(_SRC_ICONS.get(src_kind, "icon_tick.png"))
        if src_img:
            card.add_widget(Image(source=src_img, fit_mode="contain",
                                  size_hint=(None, 0.40), width=_ff(22.6),
                                  pos_hint={"x": 0.70, "y": 0.30}))

        # Source type label — 14.13 px Medium (smallest Figma size in morning_brief)
        card.add_widget(_lbl(
            src_kind.capitalize(), _FMD, _ff(14.13), _DIM,
            ha="left", va="middle",
            size_hint=(0.12, 1.0),
            pos_hint={"x": 0.745, "y": 0.0}))

        # Due date — 16.95 px Medium, coloured per bucket
        card.add_widget(_lbl(
            due_text, _FMD, _ff(16.95), col,
            ha="right", va="middle",
            size_hint=(0.16, 1.0),
            pos_hint={"x": 0.83, "y": 0.0}))

        self._list_box.add_widget(card)
        self._list_box.add_widget(Widget(size_hint=(1, None), height=_ff(7)))

    # ── Count badges ──────────────────────────────────────────────────────────

    def _update_counts(self) -> None:
        n_today    = len(self._rows["due_today"])
        n_upcoming = len(self._rows["upcoming"])
        n_unplanned = len(self._rows["unplanned"])
        total = n_today + n_upcoming + n_unplanned

        counts = {
            "all":       total,
            "due_today": n_today,
            "upcoming":  n_upcoming,
            "unplanned": n_unplanned,
        }
        for tid, lbl in self._count_labels.items():
            n = counts.get(tid, 0)
            lbl.text = str(n) if n > 0 else ""

        if self._header_count_lbl is not None:
            if total == 0:
                self._header_count_lbl.text = "No tasks"
            else:
                self._header_count_lbl.text = (
                    f"{total} task{'s' if total != 1 else ''}"
                )

    def _update_last_fetched_label(self) -> None:
        if self._last_updated_lbl is None or self._last_fetch_dt is None:
            return
        delta = int((display_now() - self._last_fetch_dt).total_seconds())
        if delta < 10:
            txt = "Updated just now"
        elif delta < 60:
            txt = f"Updated {delta}s ago"
        elif delta < 3600:
            txt = f"Updated {delta // 60} min ago"
        else:
            txt = f"Updated {delta // 3600}h ago"
        self._last_updated_lbl.text = txt

    # ── Data loading ───────────────────────────────────────────────────────────

    def _load_tasks(self, *_) -> None:
        """Fetch live commitments from the backend API and rebuild the list."""
        async def _go():
            try:
                result = await self.backend.get_commitments(status="", limit=100)
            except Exception as exc:
                logger.warning("tasks: get_commitments error: %s", exc)
                result = {"commitments": [], "count": 0}

            rows = result.get("commitments") or []
            bucketed: dict[str, list] = {
                "due_today": [], "upcoming": [], "unplanned": []
            }
            for r in rows:
                b = _categorize(r)
                if b is not None:
                    bucketed[b].append(r)

            def _apply(_dt):
                self._loading = False
                self._rows = bucketed
                self._last_fetch_dt = display_now()
                self._update_counts()
                self._update_last_fetched_label()
                self._rebuild_task_list()

            Clock.schedule_once(_apply, 0)

        run_async(_go())

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_enter(self) -> None:
        self._loading = True
        # Show loading state immediately
        if self._list_box is not None:
            self._list_box.clear_widgets()
            self._list_box.add_widget(_lbl(
                "Loading tasks…", _FMD, _ff(21.19), _MUTED,
                ha="center", va="middle",
                size_hint=(1, None), height=_ff(100)))
        # Fetch on enter
        Clock.schedule_once(self._load_tasks, 0)
        # Schedule periodic real-time refresh (60 s interval, same as calendar tick)
        if self._refresh_ev is None:
            self._refresh_ev = Clock.schedule_interval(
                self._load_tasks, _REFRESH_INTERVAL)

    def on_leave(self) -> None:
        if self._refresh_ev is not None:
            self._refresh_ev.cancel()
            self._refresh_ev = None

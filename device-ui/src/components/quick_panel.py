"""
QuickPanel — swipe-down quick-settings overlay for MeetingBox device UI.

Floats above all screens as a FloatLayout sibling in root_layout (main.py).
Triggered by a downward swipe starting within the top 40 px of the screen.

Layout (top → bottom, dark glass card):
  ┌────────────────────────────────────────┐
  │  🔋 87%  Charging     11:40      ✕    │  header
  ├────────────────────────────────────────┤
  │  🔊 ──────●─────────────────     75%  │  volume slider
  │  ☀  ───────────●───────────────  80%  │  brightness slider
  ├────────────────────────────────────────┤
  │  [📶 Wi-Fi ]  [🔵 BT ]                │  quick tiles
  │  [✈ Airplane] [⚙ Settings]            │
  ├────────────────────────────────────────┤
  │  Wi-Fi Networks ›                      │  expandable
  │    MyNetwork  ████░░ 🔒  ● connected  │
  ├────────────────────────────────────────┤
  │  Bluetooth Devices ›                   │  expandable
  │    My Speaker   AA:BB            PAIR  │
  ├────────────────────────────────────────┤
  │  [🔒 Lock]  [↺ Restart]  [⏻ Power Off]│  footer
  └────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Callable, Optional

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.widget import Widget

import hardware
import wifi_nmcli_local
import bluetooth_local
from config import COLORS, DISPLAY_HEIGHT, DISPLAY_WIDTH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scaling helpers
# ---------------------------------------------------------------------------

def _sv(px: float) -> int:
    """Scale a vertical pixel value against the 600 px reference height."""
    return max(1, int(round(px * DISPLAY_HEIGHT / 600)))


def _sh(px: float) -> int:
    """Scale a horizontal pixel value against the 1024 px reference width."""
    return max(1, int(round(px * DISPLAY_WIDTH / 1024)))


def _sf(fs: float) -> int:
    """Scale a font size against the smaller axis ratio."""
    ratio = min(DISPLAY_HEIGHT / 600, DISPLAY_WIDTH / 1024)
    return max(6, int(round(fs * ratio)))


# ---------------------------------------------------------------------------
# _PressableRow  (generic tappable row base)
# ---------------------------------------------------------------------------

class _PressableRow(ButtonBehavior, BoxLayout):
    """ButtonBehavior + BoxLayout with no extra styling."""


# ---------------------------------------------------------------------------
# _Tile  — quick toggle/action tile (WiFi, BT, Airplane, Settings)
# ---------------------------------------------------------------------------

class _Tile(ButtonBehavior, BoxLayout):
    """Square quick-settings tile with icon + label, highlighted when active."""

    _ACTIVE_BG   = None  # set after class body: COLORS['blue']
    _INACTIVE_BG = None  # set after class body: COLORS['surface_light']

    def __init__(self, icon: str, label: str, active: bool = False, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", _sv(60))
        kwargs.setdefault("padding", [_sh(8), _sv(6)])
        kwargs.setdefault("spacing", _sv(2))
        super().__init__(**kwargs)

        self._active = active
        self._icon_lbl = Label(
            text=icon,
            font_size=_sf(18),
            size_hint_y=None,
            height=_sv(24),
            color=COLORS["white"] if active else COLORS["gray_400"],
        )
        self._name_lbl = Label(
            text=label,
            font_size=_sf(11),
            size_hint_y=None,
            height=_sv(16),
            color=COLORS["white"] if active else COLORS["gray_400"],
        )
        self.add_widget(self._icon_lbl)
        self.add_widget(self._name_lbl)

        with self.canvas.before:
            self._bg_color = Color(*(COLORS["blue"] if active else COLORS["surface_light"]))
            self._bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[_sv(10)]
            )
        self.bind(pos=self._sync_bg, size=self._sync_bg)

    def _sync_bg(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def set_active(self, active: bool):
        self._active = active
        col = COLORS["blue"] if active else COLORS["surface_light"]
        self._bg_color.rgba = col
        txt_col = COLORS["white"] if active else COLORS["gray_400"]
        self._icon_lbl.color = txt_col
        self._name_lbl.color = txt_col


# ---------------------------------------------------------------------------
# _NetRow — single Wi-Fi network row
# ---------------------------------------------------------------------------

class _NetRow(_PressableRow):
    def __init__(self, ssid: str, signal: int, secured: bool, connected: bool, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", _sv(40))
        kwargs.setdefault("padding", [_sh(16), _sv(4)])
        kwargs.setdefault("spacing", _sh(6))
        super().__init__(**kwargs)

        filled = max(0, min(4, signal // 25))
        bars = "█" * filled + "░" * (4 - filled)
        lock = " 🔒" if secured else ""
        dot_text = " ●" if connected else ""
        text_col = COLORS["blue"] if connected else COLORS["white"]

        self.add_widget(Label(
            text=f"{ssid}{lock}{dot_text}",
            font_size=_sf(12),
            color=text_col,
            halign="left",
            size_hint=(1, 1),
        ))
        self.add_widget(Label(
            text=bars,
            font_size=_sf(10),
            color=COLORS["gray_400"],
            size_hint=(None, 1),
            width=_sh(40),
            halign="right",
        ))


# ---------------------------------------------------------------------------
# _BtRow — single Bluetooth device row
# ---------------------------------------------------------------------------

class _BtRow(_PressableRow):
    def __init__(self, name: str, mac: str, paired: bool, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", _sv(40))
        kwargs.setdefault("padding", [_sh(16), _sv(4)])
        kwargs.setdefault("spacing", _sh(6))
        super().__init__(**kwargs)

        self.mac = mac
        self.add_widget(Label(
            text=name or mac,
            font_size=_sf(12),
            color=COLORS["white"],
            halign="left",
            size_hint=(1, 1),
        ))
        action = "REMOVE" if paired else "PAIR"
        self._action_lbl = Label(
            text=action,
            font_size=_sf(11),
            color=COLORS["blue"],
            size_hint=(None, 1),
            width=_sh(60),
            halign="right",
        )
        self.add_widget(self._action_lbl)


# ---------------------------------------------------------------------------
# _SectionHeader — tappable section label with expand arrow
# ---------------------------------------------------------------------------

class _SectionHeader(_PressableRow):
    def __init__(self, title: str, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", _sv(34))
        kwargs.setdefault("padding", [_sh(12), _sv(4)])
        super().__init__(**kwargs)

        self._title = title
        self._lbl = Label(
            text=f"{title}  ›",
            font_size=_sf(12),
            bold=True,
            color=COLORS["gray_400"],
            halign="left",
            size_hint=(1, 1),
        )
        self._lbl.bind(size=self._lbl.setter("text_size"))
        self.add_widget(self._lbl)

    def set_expanded(self, expanded: bool):
        self._lbl.text = f"{self._title}  ‹" if expanded else f"{self._title}  ›"


# ---------------------------------------------------------------------------
# _FooterBtn — footer action button (Lock / Restart / Power Off)
# ---------------------------------------------------------------------------

class _FooterBtn(ButtonBehavior, BoxLayout):
    def __init__(self, icon: str, label: str, danger: bool = False, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint", (1, 1))
        kwargs.setdefault("padding", [_sh(4), _sv(6)])
        kwargs.setdefault("spacing", _sv(2))
        super().__init__(**kwargs)

        col = (1.0, 0.3, 0.26, 1) if danger else COLORS["gray_300"]
        self._icon_lbl = Label(
            text=icon,
            font_size=_sf(16),
            color=col,
            size_hint_y=None,
            height=_sv(22),
        )
        self._name_lbl = Label(
            text=label,
            font_size=_sf(10),
            color=col,
            size_hint_y=None,
            height=_sv(14),
        )
        self.add_widget(self._icon_lbl)
        self.add_widget(self._name_lbl)

        with self.canvas.before:
            self._bg_color = Color(*COLORS["surface_light"])
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[_sv(8)])
        self.bind(pos=self._sync_bg, size=self._sync_bg)
        self.bind(on_press=lambda *_: self._press_look(True))
        self.bind(on_release=lambda *_: self._press_look(False))

    def _sync_bg(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _press_look(self, pressed: bool):
        self._bg_color.rgba = COLORS["gray_700"] if pressed else COLORS["surface_light"]


# ---------------------------------------------------------------------------
# QuickPanel — the main overlay widget
# ---------------------------------------------------------------------------

PANEL_H = min(int(DISPLAY_HEIGHT * 0.65), 390)


class QuickPanel(FloatLayout):
    """Full-screen FloatLayout overlay.

    Passes all touches through when hidden (``_visible = False``).
    Call ``show()`` / ``hide()`` to animate the panel in / out.
    Set ``panel.app`` to the running ``App`` instance so Settings tile
    can navigate to the settings screen.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (1, 1)
        self._visible = False
        self._wifi_expanded = False
        self._bt_expanded = False
        self._airplane_on = False
        self._vol_debounce = None
        self._bri_debounce = None
        self.app: Optional[object] = None  # set by main.py

        self._build_ui()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Full-screen scrim (semi-transparent dark)
        with self.canvas.before:
            self._scrim_col = Color(0, 0, 0, 0)
            self._scrim_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_scrim, size=self._sync_scrim)

        # Panel card
        self._card = BoxLayout(
            orientation="vertical",
            size_hint=(1, None),
            height=PANEL_H,
        )
        with self._card.canvas.before:
            Color(0.10, 0.10, 0.12, 0.97)
            self._card_bg = RoundedRectangle(
                pos=self._card.pos,
                size=self._card.size,
                radius=[0, 0, _sv(16), _sv(16)],
            )
        self._card.bind(
            pos=lambda w, v: setattr(self._card_bg, "pos", v),
            size=lambda w, v: setattr(self._card_bg, "size", v),
        )

        # Sections
        self._card.add_widget(self._make_header())
        self._card.add_widget(self._make_scroll())
        self._card.add_widget(self._make_footer())

        # Start fully above screen (will animate down on show())
        self._card.pos = (0, Window.height)
        self.add_widget(self._card)

    def _sync_scrim(self, *_):
        self._scrim_rect.pos = self.pos
        self._scrim_rect.size = self.size

    # -- header row --------------------------------------------------------

    def _make_header(self) -> BoxLayout:
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=_sv(44),
            padding=[_sh(14), _sv(8), _sh(14), _sv(4)],
            spacing=_sh(8),
        )

        self._battery_lbl = Label(
            text="🔋",
            font_size=_sf(12),
            color=COLORS["gray_300"],
            size_hint=(None, 1),
            width=_sh(90),
            halign="left",
        )
        self._battery_lbl.bind(size=self._battery_lbl.setter("text_size"))

        self._header_time_lbl = Label(
            text=self._now_str(),
            font_size=_sf(13),
            bold=True,
            color=COLORS["white"],
            size_hint=(1, 1),
            halign="center",
        )

        close_lbl = Label(
            text="✕",
            font_size=_sf(16),
            color=COLORS["gray_500"],
            size_hint=(None, 1),
            width=_sh(36),
            halign="right",
        )
        close_lbl.bind(size=close_lbl.setter("text_size"))
        close_lbl.bind(on_touch_down=lambda w, t: self._close_touch(w, t))

        row.add_widget(self._battery_lbl)
        row.add_widget(self._header_time_lbl)
        row.add_widget(close_lbl)
        return row

    def _close_touch(self, widget, touch):
        if widget.collide_point(*touch.pos):
            self.hide()
            return True
        return False

    # -- scrollable middle content -----------------------------------------

    def _make_scroll(self) -> ScrollView:
        scroll = ScrollView(do_scroll_x=False, size_hint=(1, 1))

        inner = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[_sh(12), _sv(4), _sh(12), _sv(4)],
            spacing=_sv(6),
        )
        inner.bind(minimum_height=inner.setter("height"))

        # Volume slider
        inner.add_widget(self._make_slider_row("🔊", "Volume", "vol"))
        # Brightness slider
        inner.add_widget(self._make_slider_row("☀", "Brightness", "bri"))

        # Divider
        div = Widget(size_hint_y=None, height=1)
        with div.canvas:
            Color(*COLORS["gray_700"])
            _div_rect = Rectangle(pos=div.pos, size=div.size)
        div.bind(
            pos=lambda w, v: setattr(_div_rect, "pos", v),
            size=lambda w, v: setattr(_div_rect, "size", v),
        )
        inner.add_widget(div)

        # Quick tiles (2 × 2 grid)
        tiles = GridLayout(
            cols=2,
            size_hint_y=None,
            height=_sv(134),
            spacing=_sh(8),
        )
        self._wifi_tile = _Tile("📶", "Wi-Fi", active=True)
        self._wifi_tile.bind(on_press=self._on_wifi_tile)

        self._bt_tile = _Tile("🔵", "Bluetooth", active=False)
        self._bt_tile.bind(on_press=self._on_bt_tile)

        self._airplane_tile = _Tile("✈", "Airplane", active=False)
        self._airplane_tile.bind(on_press=self._on_airplane_tile)

        self._settings_tile = _Tile("⚙", "Settings", active=False)
        self._settings_tile.bind(on_press=self._on_settings_tile)

        for t in (self._wifi_tile, self._bt_tile,
                  self._airplane_tile, self._settings_tile):
            tiles.add_widget(t)
        inner.add_widget(tiles)

        # WiFi expandable section
        self._wifi_sec_hdr = _SectionHeader("Wi-Fi Networks")
        self._wifi_sec_hdr.bind(on_press=lambda *_: self._toggle_wifi_section())
        inner.add_widget(self._wifi_sec_hdr)

        self._wifi_list = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=0,
            spacing=_sv(2),
        )
        inner.add_widget(self._wifi_list)

        # BT expandable section
        self._bt_sec_hdr = _SectionHeader("Bluetooth Devices")
        self._bt_sec_hdr.bind(on_press=lambda *_: self._toggle_bt_section())
        inner.add_widget(self._bt_sec_hdr)

        self._bt_list = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=0,
            spacing=_sv(2),
        )
        inner.add_widget(self._bt_list)

        scroll.add_widget(inner)
        return scroll

    def _make_slider_row(self, icon: str, label: str, key: str) -> BoxLayout:
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=_sv(40),
            spacing=_sh(8),
            padding=[0, _sv(4)],
        )
        row.add_widget(Label(
            text=icon,
            font_size=_sf(14),
            size_hint=(None, 1),
            width=_sh(24),
            color=COLORS["gray_300"],
        ))
        slider = Slider(min=0, max=100, value=75, size_hint=(1, 1))
        val_lbl = Label(
            text="75%",
            font_size=_sf(11),
            color=COLORS["gray_400"],
            size_hint=(None, 1),
            width=_sh(36),
            halign="right",
        )
        val_lbl.bind(size=val_lbl.setter("text_size"))

        if key == "vol":
            self._vol_slider = slider
            self._vol_lbl = val_lbl
            slider.bind(value=self._on_vol_change)
        else:
            self._bri_slider = slider
            self._bri_lbl = val_lbl
            slider.bind(value=self._on_bri_change)

        row.add_widget(slider)
        row.add_widget(val_lbl)
        return row

    # -- footer row --------------------------------------------------------

    def _make_footer(self) -> BoxLayout:
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=_sv(52),
            padding=[_sh(12), _sv(6)],
            spacing=_sh(8),
        )
        lock_btn = _FooterBtn("🔒", "Lock")
        lock_btn.bind(on_release=lambda *_: self._on_lock())
        row.add_widget(lock_btn)

        restart_btn = _FooterBtn("↺", "Restart")
        restart_btn.bind(on_release=lambda *_: self._on_restart())
        row.add_widget(restart_btn)

        power_btn = _FooterBtn("⏻", "Power Off", danger=True)
        power_btn.bind(on_release=lambda *_: self._on_poweroff())
        row.add_widget(power_btn)

        with row.canvas.before:
            Color(*COLORS["gray_800"])
            self._footer_div = Rectangle(
                pos=(row.x, row.top - 1) if row.height > 1 else (0, 0),
                size=(row.width, 1),
            )
        row.bind(pos=self._sync_footer_div, size=self._sync_footer_div)
        return row

    def _sync_footer_div(self, row, *_):
        if hasattr(self, "_footer_div"):
            self._footer_div.pos = (row.x, row.top - 1)
            self._footer_div.size = (row.width, 1)

    # ------------------------------------------------------------------
    # Show / Hide
    # ------------------------------------------------------------------

    def show(self):
        if self._visible:
            return
        self._visible = True
        self._header_time_lbl.text = self._now_str()
        # Place card above visible area, then animate down
        self._card.pos = (0, Window.height)
        Animation(a=0.55, d=0.2).start(self._scrim_col)
        target_y = max(0, Window.height - PANEL_H)
        Animation(y=target_y, d=0.25, t="out_cubic").start(self._card)
        # Refresh data shortly after panel starts sliding
        Clock.schedule_once(lambda _dt: self._refresh(), 0.1)

    def hide(self):
        if not self._visible:
            return
        Animation(a=0, d=0.15).start(self._scrim_col)
        anim = Animation(y=Window.height, d=0.2)
        anim.bind(on_complete=lambda *_: setattr(self, "_visible", False))
        anim.start(self._card)

    # ------------------------------------------------------------------
    # Touch routing — pass-through when hidden
    # ------------------------------------------------------------------

    def on_touch_down(self, touch):
        if not self._visible:
            return False
        # Dismiss on tap outside the card
        if not self._card.collide_point(*touch.pos):
            self.hide()
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if not self._visible:
            return False
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if not self._visible:
            return False
        return super().on_touch_up(touch)

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def _refresh(self):
        """Kick off a background thread to fetch all status values."""
        threading.Thread(target=self._fetch_status, daemon=True).start()

    def _fetch_status(self):
        batt    = _safe(hardware.get_battery_info, {"percent": None, "charging": None})
        wifi_on = _safe(wifi_nmcli_local.get_wifi_radio_enabled, None)
        bt_on   = _safe(bluetooth_local.get_power_state, None)
        vol     = _safe(hardware.get_sink_volume_pct, None)
        bri     = _safe(hardware.get_brightness_pct, None)

        def _apply(_dt):
            # Battery label
            pct = batt.get("percent")
            charging = batt.get("charging")
            if pct is not None:
                icon = "⚡" if charging else "🔋"
                self._battery_lbl.text = f"{icon} {pct}%"
            else:
                self._battery_lbl.text = "🔌 AC"

            # Volume slider
            if vol is not None:
                self._vol_slider.unbind(value=self._on_vol_change)
                self._vol_slider.value = vol
                self._vol_lbl.text = f"{int(vol)}%"
                self._vol_slider.bind(value=self._on_vol_change)

            # Brightness slider
            if bri is not None:
                self._bri_slider.unbind(value=self._on_bri_change)
                self._bri_slider.value = bri
                self._bri_lbl.text = f"{int(bri)}%"
                self._bri_slider.bind(value=self._on_bri_change)

            # Tiles
            self._wifi_tile.set_active(bool(wifi_on))
            self._bt_tile.set_active(bool(bt_on))

        Clock.schedule_once(_apply, 0)

    # ------------------------------------------------------------------
    # Slider callbacks (debounced)
    # ------------------------------------------------------------------

    def _on_vol_change(self, slider, val: float):
        self._vol_lbl.text = f"{int(val)}%"
        if self._vol_debounce:
            self._vol_debounce.cancel()
        v = int(val)
        self._vol_debounce = Clock.schedule_once(
            lambda _dt: threading.Thread(
                target=lambda: hardware.set_sink_volume_pct(v), daemon=True
            ).start(),
            0.15,
        )

    def _on_bri_change(self, slider, val: float):
        self._bri_lbl.text = f"{int(val)}%"
        if self._bri_debounce:
            self._bri_debounce.cancel()
        v = int(val)
        self._bri_debounce = Clock.schedule_once(
            lambda _dt: threading.Thread(
                target=lambda: hardware.set_brightness_pct(v), daemon=True
            ).start(),
            0.15,
        )

    # ------------------------------------------------------------------
    # Tile callbacks
    # ------------------------------------------------------------------

    def _on_wifi_tile(self, *_):
        current = bool(self._wifi_tile._active)
        new_state = not current
        self._wifi_tile.set_active(new_state)
        threading.Thread(
            target=lambda: wifi_nmcli_local.set_wifi_radio(new_state),
            daemon=True,
        ).start()

    def _on_bt_tile(self, *_):
        current = bool(self._bt_tile._active)
        new_state = not current
        self._bt_tile.set_active(new_state)
        threading.Thread(
            target=lambda: bluetooth_local.set_power(new_state),
            daemon=True,
        ).start()

    def _on_airplane_tile(self, *_):
        self._airplane_on = not self._airplane_on
        self._airplane_tile.set_active(self._airplane_on)
        cmd = "off" if self._airplane_on else "on"
        threading.Thread(
            target=lambda: _run_nmcli_radio(cmd), daemon=True
        ).start()
        if self._airplane_on:
            # Reflect in wifi/bt tiles
            self._wifi_tile.set_active(False)
            self._bt_tile.set_active(False)

    def _on_settings_tile(self, *_):
        self.hide()
        if self.app and hasattr(self.app, "screen_manager"):
            self.app.screen_manager.current = "settings"

    # ------------------------------------------------------------------
    # Expandable WiFi section
    # ------------------------------------------------------------------

    def _toggle_wifi_section(self):
        self._wifi_expanded = not self._wifi_expanded
        self._wifi_sec_hdr.set_expanded(self._wifi_expanded)
        if self._wifi_expanded:
            self._populate_wifi_loading()
            threading.Thread(target=self._load_wifi_networks, daemon=True).start()
        else:
            self._wifi_list.clear_widgets()
            self._wifi_list.height = 0

    def _populate_wifi_loading(self):
        self._wifi_list.clear_widgets()
        self._wifi_list.height = _sv(36)
        self._wifi_list.add_widget(Label(
            text="Scanning…",
            font_size=_sf(12),
            color=COLORS["gray_400"],
            size_hint_y=None,
            height=_sv(36),
        ))

    def _load_wifi_networks(self):
        try:
            nets = wifi_nmcli_local.scan_wifi_networks(rescan=False)
        except Exception:
            nets = []

        def _apply(_dt):
            if not self._wifi_expanded:
                return
            self._wifi_list.clear_widgets()
            if not nets:
                self._wifi_list.add_widget(Label(
                    text="No networks found",
                    font_size=_sf(12),
                    color=COLORS["gray_500"],
                    size_hint_y=None,
                    height=_sv(36),
                ))
                self._wifi_list.height = _sv(36)
                return

            shown = nets[:5]
            for net in shown:
                row = _NetRow(
                    ssid=net.get("ssid", ""),
                    signal=net.get("signal_strength", 0),
                    secured=(net.get("security", "open") != "open"),
                    connected=net.get("connected", False),
                )
                row.bind(on_release=lambda r, n=net: self._on_wifi_row_tap(n))
                self._wifi_list.add_widget(row)
            self._wifi_list.height = _sv(40) * len(shown)

        Clock.schedule_once(_apply, 0)

    def _on_wifi_row_tap(self, net: dict):
        ssid = net.get("ssid", "")
        if net.get("connected"):
            return  # Already connected — do nothing
        secured = net.get("security", "open") != "open"
        if secured:
            self._ask_wifi_password(ssid)
        else:
            threading.Thread(
                target=lambda: wifi_nmcli_local.connect_wifi_network(ssid, None),
                daemon=True,
            ).start()

    def _ask_wifi_password(self, ssid: str):
        """Open a TextInputDialog for the Wi-Fi password."""
        try:
            from components.text_input_dialog import TextInputDialog
        except ImportError:
            return

        def _on_connect(pwd: str):
            threading.Thread(
                target=lambda: wifi_nmcli_local.connect_wifi_network(ssid, pwd or None),
                daemon=True,
            ).start()

        dlg = TextInputDialog(
            title=f"Connect to {ssid}",
            message="Enter the Wi-Fi password",
            placeholder="Password",
            confirm_text="CONNECT",
            on_confirm=_on_connect,
        )
        # Attach to root_layout so it floats above everything
        if self.app and hasattr(self.app, "root_layout"):
            self.app.root_layout.add_widget(dlg)
        elif self.parent:
            self.parent.add_widget(dlg)

    # ------------------------------------------------------------------
    # Expandable Bluetooth section
    # ------------------------------------------------------------------

    def _toggle_bt_section(self):
        self._bt_expanded = not self._bt_expanded
        self._bt_sec_hdr.set_expanded(self._bt_expanded)
        if self._bt_expanded:
            self._populate_bt_loading()
            threading.Thread(target=self._load_bt_devices, daemon=True).start()
        else:
            self._bt_list.clear_widgets()
            self._bt_list.height = 0

    def _populate_bt_loading(self):
        self._bt_list.clear_widgets()
        self._bt_list.height = _sv(36)
        self._bt_list.add_widget(Label(
            text="Scanning…",
            font_size=_sf(12),
            color=COLORS["gray_400"],
            size_hint_y=None,
            height=_sv(36),
        ))

    def _load_bt_devices(self):
        try:
            paired = bluetooth_local.list_paired_devices()
        except Exception:
            paired = []
        try:
            nearby = bluetooth_local.scan_and_list_nearby(scan_seconds=5)
        except Exception:
            nearby = []

        paired_macs = {d.get("mac", "").upper() for d in paired}
        all_devices: list[dict] = list(paired)
        seen = set(paired_macs)
        for d in nearby:
            mac = d.get("mac", "").upper()
            if mac and mac not in seen:
                all_devices.append(d)
                seen.add(mac)

        def _apply(_dt):
            if not self._bt_expanded:
                return
            self._bt_list.clear_widgets()
            if not all_devices:
                self._bt_list.add_widget(Label(
                    text="No devices found",
                    font_size=_sf(12),
                    color=COLORS["gray_500"],
                    size_hint_y=None,
                    height=_sv(36),
                ))
                self._bt_list.height = _sv(36)
                return

            shown = all_devices[:5]
            for dev in shown:
                mac = dev.get("mac", "")
                name = dev.get("name", mac)
                is_paired = mac.upper() in paired_macs
                row = _BtRow(name=name, mac=mac, paired=is_paired)
                row.bind(on_release=lambda r, d=dev, p=is_paired: self._on_bt_row_tap(d, p))
                self._bt_list.add_widget(row)
            self._bt_list.height = _sv(40) * len(shown)

        Clock.schedule_once(_apply, 0)

    def _on_bt_row_tap(self, dev: dict, is_paired: bool):
        mac = dev.get("mac", "")
        if not mac:
            return
        if is_paired:
            threading.Thread(
                target=lambda: bluetooth_local.remove_device(mac), daemon=True
            ).start()
        else:
            threading.Thread(
                target=lambda: bluetooth_local.pair_device(mac), daemon=True
            ).start()

    # ------------------------------------------------------------------
    # Footer callbacks
    # ------------------------------------------------------------------

    def _on_lock(self):
        self.hide()
        if self.app and hasattr(self.app, "screen_manager"):
            Clock.schedule_once(
                lambda _dt: setattr(self.app.screen_manager, "current", "idle"), 0.25
            )

    def _on_restart(self):
        self.hide()
        threading.Thread(target=hardware.request_system_reboot, daemon=True).start()

    def _on_poweroff(self):
        self.hide()
        threading.Thread(target=hardware.request_system_poweroff, daemon=True).start()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now_str() -> str:
        return datetime.now().strftime("%H:%M")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _safe(fn: Callable, default):
    """Call fn(); return default on any exception."""
    try:
        return fn()
    except Exception:
        return default


def _run_nmcli_radio(state: str):
    """Toggle all radios (airplane mode) via nmcli."""
    import shutil as _shutil
    import subprocess as _sp
    exe = _shutil.which("nmcli")
    if not exe:
        return
    try:
        r = _sp.run(
            ["nmcli", "radio", "all", state],
            capture_output=True, timeout=8,
        )
        if r.returncode != 0 and _shutil.which("sudo"):
            _sp.run(
                ["sudo", "-n", "/usr/bin/nmcli", "radio", "all", state],
                capture_output=True, timeout=8,
            )
    except Exception:
        pass

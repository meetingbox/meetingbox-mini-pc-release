"""
Bluetooth screen — list paired devices, toggle power, pair new device.
Routes through backend API so bluetoothctl runs on the host.
"""

import logging

from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from async_helper import run_async
from components.button import PrimaryButton, SecondaryButton
from components.modal_dialog import ModalDialog
from components.settings_item import SettingsItem
from components.status_bar import StatusBar
from components.text_input_dialog import TextInputDialog
from config import COLORS, FONT_SIZES, SPACING
from screens.base_screen import BaseScreen

logger = logging.getLogger(__name__)


class BluetoothScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")
        self.make_dark_bg(root)
        self.status_bar = StatusBar(
            status_text="Bluetooth",
            device_name="Bluetooth",
            back_button=True,
            on_back=self.go_back,
            show_settings=False,
        )
        root.add_widget(self.status_bar)

        pad = self.suh(SPACING["screen_padding"])
        inner = BoxLayout(
            orientation="vertical",
            padding=[pad, self.suv(8), pad, self.suv(8)],
            spacing=self.suv(8),
        )

        self.bt_power_item = SettingsItem(
            title="Bluetooth",
            subtitle="Loading…",
            mode="toggle",
            active=False,
            on_toggle=self._on_power_toggle,
        )
        inner.add_widget(self.bt_power_item)

        self.status_lbl = Label(
            text="Paired devices",
            font_size=self.suf(FONT_SIZES["small"]),
            bold=True,
            color=COLORS["gray_500"],
            halign="left",
            size_hint_y=None,
            height=self.suv(24),
        )
        self.status_lbl.bind(size=self.status_lbl.setter("text_size"))
        inner.add_widget(self.status_lbl)

        self.device_grid = GridLayout(cols=1, spacing=self.suv(6), size_hint_y=None)
        self.device_grid.bind(minimum_height=self.device_grid.setter("height"))
        sc = ScrollView(do_scroll_x=False, size_hint=(1, 1))
        sc.add_widget(self.device_grid)
        inner.add_widget(sc)

        pair_row = BoxLayout(size_hint=(1, None), height=self.suv(52), spacing=self.suh(10))
        self.pair_btn = PrimaryButton(text="Pair new device", size_hint=(1, 1))
        self.pair_btn.bind(on_press=lambda *_: self._show_pair_dialog())
        self.scan_btn = SecondaryButton(text="Refresh", size_hint=(None, 1), width=self.suh(100))
        self.scan_btn.bind(on_press=lambda *_: self._load())
        pair_row.add_widget(self.pair_btn)
        pair_row.add_widget(self.scan_btn)
        inner.add_widget(pair_row)

        root.add_widget(inner)
        root.add_widget(self.build_footer())
        self.add_widget(root)

    def on_enter(self):
        self._load()

    def _load(self):
        async def _fetch():
            try:
                data = await self.backend.bluetooth_devices()
                paired = data.get("paired", [])

                def _apply(_dt):
                    self.device_grid.clear_widgets()
                    if not paired:
                        self.device_grid.add_widget(
                            Label(
                                text="No paired devices.",
                                color=COLORS["gray_500"],
                                size_hint_y=None,
                                height=self.suv(36),
                            )
                        )
                        self.status_lbl.text = "Paired devices"
                    else:
                        self.status_lbl.text = f"{len(paired)} paired device(s)"
                        for dev in paired:
                            name = dev.get("name", dev.get("mac", "Unknown"))
                            mac = dev.get("mac", "")
                            row = SettingsItem(
                                title=name,
                                subtitle=mac,
                                mode="arrow",
                                on_press=lambda _, m=mac, n=name: self._device_options(m, n),
                            )
                            self.device_grid.add_widget(row)

                Clock.schedule_once(_apply, 0)
            except Exception as e:
                logger.debug("Bluetooth load: %s", e)

        run_async(_fetch())

    def _on_power_toggle(self, active: bool):
        async def _set():
            try:
                await self.backend.bluetooth_radio(active)
            except Exception as e:
                logger.debug("Bluetooth radio: %s", e)

        run_async(_set())

    def _show_pair_dialog(self):
        self.add_widget(
            TextInputDialog(
                title="Pair device",
                message="Enter the Bluetooth MAC address (e.g. AA:BB:CC:DD:EE:FF).",
                placeholder="AA:BB:CC:DD:EE:FF",
                confirm_text="PAIR",
                on_confirm=self._execute_pair,
            )
        )

    def _execute_pair(self, mac: str):
        mac = (mac or "").strip()
        if not mac:
            return

        async def _pair():
            try:
                result = await self.backend.bluetooth_pair(mac)
                ok = result.get("ok", False)
                msg = result.get("message", "")

                def _done(_dt):
                    if ok:
                        self._load()
                    else:
                        self.add_widget(
                            ModalDialog(
                                title="Pairing failed",
                                message=msg[:400] or "Could not pair device.",
                                confirm_text="OK",
                                cancel_text="",
                            )
                        )

                Clock.schedule_once(_done, 0)
            except Exception as e:
                logger.warning("Pair: %s", e)

        run_async(_pair())

    def _device_options(self, mac: str, name: str):
        self.add_widget(
            ModalDialog(
                title=name,
                message=f"MAC: {mac}",
                confirm_text="OK",
                cancel_text="",
            )
        )

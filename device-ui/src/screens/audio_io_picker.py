"""
Mic + speaker output selection (persisted via /api/device/settings).

Scans PortAudio inputs (USB / built-in) and ALSA playback cards (aplay -l),
writes ``audio_input_*`` / ``audio_output_pcm``, and mirrors them into
``os.environ`` so Vosk / Realtime / mic test pick up changes without restart.
"""

from __future__ import annotations

import logging

from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from async_helper import run_async
from audio_routing import (
    apply_device_settings_audio_env,
    list_alsa_playback_targets,
    list_portaudio_input_devices,
)
from components.button import PrimaryButton
from components.status_bar import StatusBar
from config import COLORS, FONT_SIZES, SPACING
from screens.base_screen import BaseScreen
from screens.picker_base import _RadioRow

logger = logging.getLogger(__name__)

_MIC_DEFAULT = "__mic_default__"
_SPK_DEFAULT = "__spk_default__"


class AudioDevicesPickerScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mic_rows: list = []
        self._spk_rows: list = []
        self._mic_map: dict[str, tuple[str, str]] = {_MIC_DEFAULT: ("", "")}
        self._spk_map: dict[str, str] = {_SPK_DEFAULT: ""}
        self._sel_mic = _MIC_DEFAULT
        self._sel_spk = _SPK_DEFAULT
        self._mic_box = None
        self._spk_box = None
        self._build_ui()

    def _section_label(self, title: str) -> Label:
        lb = Label(
            text=title,
            font_size=self.suf(FONT_SIZES["small"]),
            bold=True,
            color=COLORS["gray_500"],
            halign="left",
            valign="bottom",
            size_hint_y=None,
            height=self.suv(28),
            padding=[self.suh(SPACING["screen_padding"]), 0],
        )
        lb.bind(size=lb.setter("text_size"))
        return lb

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")
        self.make_dark_bg(root)
        root.add_widget(
            StatusBar(
                status_text="Audio devices",
                device_name="Audio devices",
                back_button=True,
                on_back=self.go_back,
                show_settings=False,
            )
        )
        dsc = Label(
            text=(
                "Microphone: used for wake word, cloud voice, and mic test (PortAudio indices). "
                "Speaker: ALSA node passed to aplay for assistant speech (experimental)."
            ),
            font_size=self.suf(13),
            color=COLORS["gray_400"],
            halign="left",
            valign="top",
            size_hint_y=None,
            height=self.suv(58),
            padding=[self.suh(SPACING["screen_padding"]), self.suv(4)],
        )
        dsc.bind(size=dsc.setter("text_size"))
        root.add_widget(dsc)

        scroll = ScrollView(do_scroll_x=False)
        body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=self.suv(8))
        body.bind(minimum_height=body.setter("height"))

        body.add_widget(self._section_label("MICROPHONE"))
        self._mic_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=self.suv(6))
        self._mic_box.bind(minimum_height=self._mic_box.setter("height"))
        body.add_widget(self._mic_box)

        body.add_widget(Widget(size_hint_y=None, height=self.suv(8)))
        body.add_widget(self._section_label("SPEAKER (PLAYBACK)"))
        self._spk_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=self.suv(6))
        self._spk_box.bind(minimum_height=self._spk_box.setter("height"))
        body.add_widget(self._spk_box)

        scroll.add_widget(body)
        root.add_widget(scroll)

        root.add_widget(
            PrimaryButton(
                text="Save",
                size_hint=(0.88, None),
                height=self.suv(54),
                pos_hint={"center_x": 0.5},
                on_release=lambda *_: self._save(),
            )
        )
        root.add_widget(Widget(size_hint_y=None, height=self.suv(8)))
        root.add_widget(self.build_footer())
        self.add_widget(root)

    def on_enter(self):
        run_async(self._load_and_build())

    async def _load_and_build(self):
        try:
            settings = await self.backend.get_settings()
        except Exception:
            settings = {}
        mic_idx = str(settings.get("audio_input_device_index") or "").strip()
        mic_name = str(settings.get("audio_input_device_name") or "").strip()
        spk_pcm = str(settings.get("audio_output_pcm") or "").strip()

        def _rebuild(_dt):
            self._rebuild_lists(mic_idx, mic_name, spk_pcm)

        Clock.schedule_once(_rebuild, 0)

    def _rebuild_lists(self, saved_ix: str, saved_name: str, saved_pcm: str):
        self._mic_box.clear_widgets()
        self._spk_box.clear_widgets()
        self._mic_rows.clear()
        self._spk_rows.clear()
        self._mic_map = {_MIC_DEFAULT: ("", "")}
        self._spk_map = {_SPK_DEFAULT: ""}

        self._mic_box.add_widget(
            self._mk_mic_row("System default (PortAudio)", _MIC_DEFAULT, False)
        )

        found_mic_val = _MIC_DEFAULT
        for d in list_portaudio_input_devices():
            idx = int(d["index"])
            name = str(d.get("name") or "")
            label = f"{idx}: {name[:72]}"
            key = f"mic_{idx}"
            self._mic_map[key] = (str(idx), name)
            sel = saved_ix.isdigit() and int(saved_ix) == idx
            if sel:
                found_mic_val = key
            self._mic_box.add_widget(self._mk_mic_row(label, key, sel))

        if not saved_ix.isdigit() and saved_name.strip():
            low = saved_name.strip().lower()
            for key, (_i, nm) in self._mic_map.items():
                if key == _MIC_DEFAULT:
                    continue
                if low and low in nm.lower():
                    found_mic_val = key
                    break

        self._set_mic_selection(found_mic_val)

        self._spk_box.add_widget(
            self._mk_spk_row("System default (no extra aplay device)", _SPK_DEFAULT, False)
        )
        found_spk = _SPK_DEFAULT
        for t in list_alsa_playback_targets():
            pcm = t["pcm"]
            key = f"pcm_{pcm}"
            self._spk_map[key] = pcm
            lab = t.get("label") or pcm
            sel = bool(saved_pcm) and saved_pcm == pcm
            if sel:
                found_spk = key
            self._spk_box.add_widget(self._mk_spk_row(lab, key, sel))
        self._set_spk_selection(found_spk)

    def _mk_mic_row(self, label: str, value: str, selected: bool) -> _RadioRow:
        row = _RadioRow(label_text=label, selected=selected)
        row._pick_value = value
        row.bind(on_press=self._on_mic_row)
        self._mic_rows.append(row)
        return row

    def _mk_spk_row(self, label: str, value: str, selected: bool) -> _RadioRow:
        row = _RadioRow(label_text=label, selected=selected)
        row._pick_value = value
        row.bind(on_press=self._on_spk_row)
        self._spk_rows.append(row)
        return row

    def _on_mic_row(self, row):
        self._set_mic_selection(row._pick_value)

    def _on_spk_row(self, row):
        self._set_spk_selection(row._pick_value)

    def _set_mic_selection(self, val: str):
        self._sel_mic = val if val in self._mic_map else _MIC_DEFAULT
        for r in self._mic_rows:
            r.set_selected(getattr(r, "_pick_value", "") == self._sel_mic)

    def _set_spk_selection(self, val: str):
        self._sel_spk = val if val in self._spk_map else _SPK_DEFAULT
        for r in self._spk_rows:
            r.set_selected(getattr(r, "_pick_value", "") == self._sel_spk)

    def _save(self):
        mi = self._mic_map.get(self._sel_mic, ("", ""))
        pcm = self._spk_map.get(self._sel_spk, "") or ""

        async def _go():
            try:
                body = {
                    "audio_input_device_index": mi[0],
                    "audio_input_device_name": mi[1],
                    "audio_output_pcm": pcm if pcm.lower() != "default" else "",
                }
                await self.backend.update_settings(body)
                apply_device_settings_audio_env(body)
                va = getattr(self.app, "voice_assistant", None)
                if va:
                    va.refresh_input_device()
                logger.info(
                    "Audio routing saved: mic index=%r name=%r pcm=%r",
                    mi[0],
                    mi[1][:48] if mi[1] else "",
                    pcm,
                )
            except Exception as e:
                logger.warning("Audio devices save failed: %s", e)

        run_async(_go())
        self.go_back()

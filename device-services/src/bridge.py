"""
Local device bridge — exposes OS/hardware helpers to the Flutter UI.

Reuses proven Python modules from `device-ui/src` where possible.
Run alongside the Flutter app on the Ubuntu appliance.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Sibling device-ui source tree (wifi, brightness, bluetooth, audio).
_DEVICE_UI_SRC = Path(__file__).resolve().parents[2] / "device-ui" / "src"
if _DEVICE_UI_SRC.is_dir() and str(_DEVICE_UI_SRC) not in sys.path:
    sys.path.insert(0, str(_DEVICE_UI_SRC))

app = FastAPI(title="MeetingBox Device Bridge", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class BrightnessBody(BaseModel):
    percent: int = Field(ge=0, le=100)


class WifiConnectBody(BaseModel):
    ssid: str
    password: str = ""


class WifiRadioBody(BaseModel):
    on: bool


class SsidBody(BaseModel):
    ssid: str


class BluetoothDeviceBody(BaseModel):
    mac: str


class PowerBody(BaseModel):
    on: bool


class VolumeBody(BaseModel):
    # Which mixer to set: speech / notification / mic, plus 0-100 level.
    target: str = "speech"
    percent: int = Field(ge=0, le=100)


class DefaultDeviceBody(BaseModel):
    id: str


class PowerActionBody(BaseModel):
    # "reboot" | "shutdown"
    action: str


class TimezoneBody(BaseModel):
    timezone: str


def _call(module, name: str, *args, **kwargs):
    """Call ``module.name(*args)`` if it exists, else raise 503."""
    fn = getattr(module, name, None) if module is not None else None
    if not callable(fn):
        raise HTTPException(503, f"{name} not available on this host")
    return fn(*args, **kwargs)


def _import_optional(name: str):
    try:
        return __import__(name)
    except Exception as exc:
        logger.debug("Optional module %s unavailable: %s", name, exc)
        return None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Voice / audio / recording event stream
#
# The Python voice + audio runtime (voice_assistant.py, realtime_voice_session.py,
# audio capture) publishes UI lifecycle events here. The Flutter UI subscribes
# over a WebSocket and renders the matching overlays — Python keeps owning Vosk,
# realtime audio, echo cancellation, and subprocess management.
# ---------------------------------------------------------------------------
class _EventHub:
    """Fan-out broadcaster: one queue per connected client + last-state cache."""

    def __init__(self) -> None:
        self._clients: set[asyncio.Queue[dict[str, Any]]] = set()
        self._last: dict[str, Any] = {"type": "voice_state", "state": "idle"}

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
        self._clients.add(q)
        # Replay the most recent state so a fresh client renders immediately.
        await q.put(self._last)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._clients.discard(q)

    async def publish(self, event: dict[str, Any]) -> int:
        if event.get("type") == "voice_state":
            self._last = event
        dead: list[asyncio.Queue[dict[str, Any]]] = []
        for q in self._clients:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._clients.discard(q)
        return len(self._clients)


_events = _EventHub()


class VoiceEventBody(BaseModel):
    # type: voice_state | audio_level | mic_test_level | recording_state | error
    type: str
    state: str | None = None
    level: float | None = None
    text: str | None = None
    detail: str | None = None


@app.post("/v1/events/publish")
async def publish_event(body: VoiceEventBody) -> dict[str, Any]:
    event = {k: v for k, v in body.model_dump().items() if v is not None}
    listeners = await _events.publish(event)
    return {"ok": True, "listeners": listeners}


@app.websocket("/v1/events")
async def events_ws(ws: WebSocket) -> None:
    await ws.accept()
    queue = await _events.subscribe()
    try:
        while True:
            event = await queue.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("events websocket closed: %s", exc)
    finally:
        _events.unsubscribe(queue)


@app.get("/v1/wifi/scan")
def wifi_scan() -> dict[str, Any]:
    wifi = _import_optional("wifi_nmcli_local")
    if wifi is None:
        raise HTTPException(503, "WiFi module not available on this host")
    try:
        networks = wifi.scan_wifi_networks(rescan=True)
        return {"networks": networks}
    except Exception as exc:
        logger.exception("wifi scan failed")
        raise HTTPException(500, str(exc)) from exc


@app.post("/v1/wifi/connect")
def wifi_connect(body: WifiConnectBody) -> dict[str, Any]:
    wifi = _import_optional("wifi_nmcli_local")
    if wifi is None:
        raise HTTPException(503, "WiFi module not available on this host")
    try:
        result = wifi.connect_wifi_network(body.ssid, body.password or None)
        return {"ssid": body.ssid, **result}
    except Exception as exc:
        logger.exception("wifi connect failed")
        raise HTTPException(500, str(exc)) from exc


@app.get("/v1/brightness")
def get_brightness() -> dict[str, Any]:
    hw = _import_optional("hardware")
    if hw is None:
        return {"percent": None, "available": False}
    pct = hw.get_brightness_pct()
    return {"percent": pct, "available": pct is not None}


@app.post("/v1/brightness")
def set_brightness(body: BrightnessBody) -> dict[str, Any]:
    hw = _import_optional("hardware")
    if hw is None:
        raise HTTPException(503, "Brightness control not available")
    try:
        hw.set_brightness_pct(body.percent)
        return {"ok": True, "percent": body.percent}
    except Exception as exc:
        logger.exception("set brightness failed")
        raise HTTPException(500, str(exc)) from exc


@app.get("/v1/bluetooth/status")
def bluetooth_status() -> dict[str, Any]:
    bt = _import_optional("bluetooth_local")
    if bt is None:
        return {"available": False}
    try:
        return {
            "available": bt.has_bluetoothctl(),
            "power_on": bt.get_power_state(),
            "paired": bt.list_paired_devices(),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


@app.get("/v1/audio/devices")
def audio_devices() -> dict[str, Any]:
    hw = _import_optional("hardware")
    if hw is None:
        return {"inputs": [], "outputs": []}
    try:
        inputs = [{"id": d[0], "name": d[1]} for d in hw.list_pulse_sources()]
        outputs = [{"id": d[0], "name": d[1]} for d in hw.list_pulse_sinks()]
        return {"inputs": inputs, "outputs": outputs}
    except Exception as exc:
        logger.exception("audio device list failed")
        raise HTTPException(500, str(exc)) from exc


# ---------------------------------------------------------------------------
# WiFi radio + saved networks
# ---------------------------------------------------------------------------
@app.get("/v1/wifi/status")
def wifi_status() -> dict[str, Any]:
    wifi = _import_optional("wifi_nmcli_local")
    if wifi is None:
        return {"available": False}
    try:
        return {
            "available": _call(wifi, "has_nmcli"),
            "radio_on": _call(wifi, "get_wifi_radio_enabled"),
            "saved": _call(wifi, "list_saved_wifi_connection_names"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        return {"available": False, "error": str(exc)}


@app.post("/v1/wifi/radio")
def wifi_radio(body: WifiRadioBody) -> dict[str, Any]:
    wifi = _import_optional("wifi_nmcli_local")
    if wifi is None:
        raise HTTPException(503, "WiFi module not available on this host")
    try:
        return {"on": body.on, **_call(wifi, "set_wifi_radio", body.on)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("wifi radio toggle failed")
        raise HTTPException(500, str(exc)) from exc


@app.post("/v1/wifi/forget")
def wifi_forget(body: SsidBody) -> dict[str, Any]:
    wifi = _import_optional("wifi_nmcli_local")
    if wifi is None:
        raise HTTPException(503, "WiFi module not available on this host")
    try:
        return {"ssid": body.ssid, **_call(wifi, "forget_wifi_connection", body.ssid)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("wifi forget failed")
        raise HTTPException(500, str(exc)) from exc


# ---------------------------------------------------------------------------
# Bluetooth scan / pair / connect / remove
# ---------------------------------------------------------------------------
@app.post("/v1/bluetooth/power")
def bluetooth_power(body: PowerBody) -> dict[str, Any]:
    bt = _import_optional("bluetooth_local")
    if bt is None:
        raise HTTPException(503, "Bluetooth not available on this host")
    try:
        return {"on": body.on, **_call(bt, "set_power", body.on)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("bluetooth power failed")
        raise HTTPException(500, str(exc)) from exc


@app.get("/v1/bluetooth/scan")
def bluetooth_scan(seconds: int = 7) -> dict[str, Any]:
    bt = _import_optional("bluetooth_local")
    if bt is None:
        raise HTTPException(503, "Bluetooth not available on this host")
    try:
        return {"devices": _call(bt, "scan_and_list_nearby", seconds)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("bluetooth scan failed")
        raise HTTPException(500, str(exc)) from exc


@app.post("/v1/bluetooth/pair")
def bluetooth_pair(body: BluetoothDeviceBody) -> dict[str, Any]:
    bt = _import_optional("bluetooth_local")
    if bt is None:
        raise HTTPException(503, "Bluetooth not available on this host")
    try:
        return {"mac": body.mac, **_call(bt, "pair_device", body.mac)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("bluetooth pair failed")
        raise HTTPException(500, str(exc)) from exc


@app.post("/v1/bluetooth/connect")
def bluetooth_connect(body: BluetoothDeviceBody) -> dict[str, Any]:
    bt = _import_optional("bluetooth_local")
    if bt is None:
        raise HTTPException(503, "Bluetooth not available on this host")
    try:
        return {"mac": body.mac, **_call(bt, "connect_device", body.mac)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("bluetooth connect failed")
        raise HTTPException(500, str(exc)) from exc


@app.post("/v1/bluetooth/remove")
def bluetooth_remove(body: BluetoothDeviceBody) -> dict[str, Any]:
    bt = _import_optional("bluetooth_local")
    if bt is None:
        raise HTTPException(503, "Bluetooth not available on this host")
    try:
        return {"mac": body.mac, **_call(bt, "remove_device", body.mac)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("bluetooth remove failed")
        raise HTTPException(500, str(exc)) from exc


# ---------------------------------------------------------------------------
# Audio volumes + default devices
# ---------------------------------------------------------------------------
@app.get("/v1/audio/volume")
def audio_volume() -> dict[str, Any]:
    hw = _import_optional("hardware")
    if hw is None:
        return {"available": False}
    pct = getattr(hw, "get_sink_volume_pct", lambda: None)()
    return {"available": pct is not None, "percent": pct}


@app.post("/v1/audio/volume")
def set_audio_volume(body: VolumeBody) -> dict[str, Any]:
    hw = _import_optional("hardware")
    if hw is None:
        raise HTTPException(503, "Audio control not available")
    try:
        if body.target == "mic":
            _call(hw, "set_source_volume_pct", body.percent)
        else:
            _call(hw, "set_sink_volume_pct", body.percent)
        return {"ok": True, "target": body.target, "percent": body.percent}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("set volume failed")
        raise HTTPException(500, str(exc)) from exc


@app.post("/v1/audio/default-sink")
def set_default_sink(body: DefaultDeviceBody) -> dict[str, Any]:
    hw = _import_optional("hardware")
    if hw is None:
        raise HTTPException(503, "Audio control not available")
    return {"ok": bool(_call(hw, "set_default_sink", body.id)), "id": body.id}


@app.post("/v1/audio/default-source")
def set_default_source(body: DefaultDeviceBody) -> dict[str, Any]:
    hw = _import_optional("hardware")
    if hw is None:
        raise HTTPException(503, "Audio control not available")
    return {"ok": bool(_call(hw, "set_default_source", body.id)), "id": body.id}


# ---------------------------------------------------------------------------
# Display on/off + power + system info
# ---------------------------------------------------------------------------
@app.post("/v1/display")
def set_display(body: PowerBody) -> dict[str, Any]:
    hw = _import_optional("hardware")
    if hw is None:
        raise HTTPException(503, "Display control not available")
    try:
        if body.on:
            _call(hw, "screen_on")
        else:
            _call(hw, "screen_off")
        return {"ok": True, "on": body.on}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("display toggle failed")
        raise HTTPException(500, str(exc)) from exc


@app.post("/v1/power")
def power_action(body: PowerActionBody) -> dict[str, Any]:
    hw = _import_optional("hardware")
    if hw is None:
        raise HTTPException(503, "Power control not available")
    action = body.action.lower()
    try:
        if action == "reboot":
            return {"ok": bool(_call(hw, "request_system_reboot")), "action": action}
        if action in ("shutdown", "poweroff"):
            return {"ok": bool(_call(hw, "request_system_poweroff")), "action": action}
        raise HTTPException(400, f"unknown power action: {body.action}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("power action failed")
        raise HTTPException(500, str(exc)) from exc


@app.get("/v1/system/usb")
def system_usb() -> dict[str, Any]:
    hw = _import_optional("hardware")
    if hw is None:
        return {"available": False, "devices": []}
    try:
        return {"available": True, "devices": _call(hw, "get_usb_devices_one_liners")}
    except HTTPException:
        raise
    except Exception as exc:
        return {"available": False, "error": str(exc), "devices": []}


@app.get("/v1/system/battery")
def system_battery() -> dict[str, Any]:
    hw = _import_optional("hardware")
    if hw is None:
        return {"available": False}
    try:
        return {"available": True, **_call(hw, "get_battery_info")}
    except HTTPException:
        raise
    except Exception as exc:
        return {"available": False, "error": str(exc)}

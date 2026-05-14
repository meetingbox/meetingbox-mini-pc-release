"""
OpenAI Realtime voice bridge for the device UI.

Connects to wss://api.openai.com/v1/realtime with the ephemeral client_secret from
the MeetingBox API, streams PCM16 mic audio (24 kHz), plays model audio, and runs
Mem0/briefing tools via POST /api/voice/realtime/tools/invoke.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import queue
import shutil
import subprocess
import threading
from typing import Any
from urllib.parse import quote

import numpy as np
from api_client import invoke_realtime_tool_sync
from kivy.clock import Clock

logger = logging.getLogger(__name__)

try:
    import sounddevice as sd
except ImportError:
    sd = None

import websockets

# Feature flag: main.py only launches Realtime when this is True.
REALTIME_VOICE_IMPLEMENTED = True

_REALTIME_WS_HOST = "api.openai.com"
_REALTIME_RATE = 24000
_APPEND_CHUNK_MS = 40


def build_realtime_websocket_url(model: str) -> str:
    """Return OpenAI Realtime WebSocket URL with URL-encoded model id."""
    m = (model or "").strip() or "gpt-realtime-2"
    return f"wss://{_REALTIME_WS_HOST}/v1/realtime?model={quote(m, safe='')}"


def resample_pcm16_mono(data: bytes, src_sr: int, dst_sr: int) -> bytes:
    """Linear resample mono int16 PCM bytes."""
    if src_sr == dst_sr or not data:
        return data
    s = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
    n_src = int(s.shape[0])
    if n_src < 2:
        return data
    dur = n_src / float(src_sr)
    n_dst = max(1, int(dur * dst_sr))
    x_src = np.linspace(0.0, dur, num=n_src, endpoint=False)
    x_dst = np.linspace(0.0, dur, num=n_dst, endpoint=False)
    out = np.interp(x_dst, x_src, s)
    out_i16 = (np.clip(out, -1.0, 1.0) * 32767.0).astype(np.int16)
    return out_i16.tobytes()


class RealtimeVoiceSession:
    """Runs OpenAI Realtime WebSocket + mic capture on a background thread."""

    def __init__(
        self,
        *,
        client_secret: str,
        model: str,
        backend_base_url: str,
        device_token: str,
        on_session_end,
        on_error,
        on_connected,
        on_device_navigate=None,
    ):
        self._client_secret = (client_secret or "").strip()
        self._model = (model or "").strip()
        self._backend_base_url = (backend_base_url or "").strip()
        self._device_token = (device_token or "").strip()
        self._on_session_end_cb = on_session_end
        self._on_error_cb = on_error
        self._on_connected_cb = on_connected
        self._on_device_navigate_cb = on_device_navigate
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws: Any = None
        self._connected_fired = False
        self._audio_q: queue.Queue[bytes | None] = queue.Queue(maxsize=100)
        self._mic_stream = None
        self._mic_native_sr = _REALTIME_RATE
        self._aplay_proc: subprocess.Popen | None = None
        self._aplay_for_response: str | None = None

    def start(self) -> None:
        def _run() -> None:
            try:
                asyncio.run(self._async_main())
            except Exception:
                logger.exception("Realtime voice asyncio.run failed")
                self._emit_error("Realtime voice failed unexpectedly.")

        self._thread = threading.Thread(target=_run, name="realtime-voice", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Best-effort stop: close WebSocket and microphone stream."""
        self._stop.set()
        try:
            self._audio_q.put_nowait(None)
        except Exception:
            pass
        try:
            loop = self._loop
            ws = self._ws
            if loop is not None and ws is not None and not loop.is_closed():

                async def _close() -> None:
                    try:
                        await ws.close()
                    except Exception:
                        logger.debug("Realtime ws close", exc_info=True)

                try:
                    fut = asyncio.run_coroutine_threadsafe(_close(), loop)
                    fut.result(timeout=3.0)
                except Exception:
                    logger.debug("Realtime stop: could not close ws in time", exc_info=True)
        except Exception:
            logger.debug("Realtime stop", exc_info=True)
        self._close_aplay()
        self._close_mic()

    def _emit_error(self, msg: str) -> None:
        def _emit(_dt):
            try:
                self._on_error_cb(msg)
            except Exception:
                logger.exception("Realtime on_error callback failed")

        Clock.schedule_once(_emit, 0)

    def _emit_connected(self) -> None:
        def _emit(_dt):
            try:
                self._on_connected_cb()
            except Exception:
                logger.exception("Realtime on_connected callback failed")

        Clock.schedule_once(_emit, 0)

    def _emit_session_end(self) -> None:
        def _emit(_dt):
            try:
                self._on_session_end_cb()
            except Exception:
                logger.exception("Realtime on_session_end callback failed")

        Clock.schedule_once(_emit, 0)

    def _emit_device_navigation(self, tool_output_json: str) -> None:
        """Parse navigate_device_ui tool result and run Kivy navigation on the main thread."""
        cb = self._on_device_navigate_cb
        if not cb:
            return
        try:
            data = json.loads(tool_output_json)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(data, dict) or not data.get("ok"):
            return
        screen = data.get("device_navigate")
        if not isinstance(screen, str) or not screen.strip():
            return

        nav = screen.strip()

        def _emit(_dt):
            try:
                cb(nav)
            except Exception:
                logger.exception("Realtime on_device_navigate failed screen=%s", nav)

        Clock.schedule_once(_emit, 0)

    def _resolve_input_device(self):
        from config import AUDIO_INPUT_DEVICE_INDEX, AUDIO_INPUT_DEVICE_NAME

        idx_s = (AUDIO_INPUT_DEVICE_INDEX or "").strip()
        if idx_s.isdigit():
            return int(idx_s)
        name_sub = (AUDIO_INPUT_DEVICE_NAME or "").strip().lower()
        if not name_sub or sd is None:
            return None
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if int(dev.get("max_input_channels") or 0) > 0 and name_sub in (
                    (dev.get("name") or "").lower()
                ):
                    return idx
        except Exception:
            logger.exception("Realtime: could not enumerate audio devices")
        return None

    def _samplerates_to_try(self, device_id) -> list[int]:
        rates = [_REALTIME_RATE, 16000, 22050, 32000, 44100, 48000]
        if sd is None or device_id is None:
            return rates
        try:
            info = sd.query_devices(device_id)
            dr = int(float(info.get("default_samplerate") or 0))
            if dr > 0 and dr not in rates:
                rates.insert(0, dr)
        except Exception:
            pass
        return rates

    def _open_mic(self, device_id) -> bool:
        if sd is None:
            return False

        def callback(indata, frames, t_info, status):
            del frames, t_info
            if status and str(status):
                logger.debug("Realtime mic: %s", status)
            if self._stop.is_set():
                return
            try:
                b = bytes(indata)
                if self._audio_q.full():
                    try:
                        self._audio_q.get_nowait()
                    except queue.Empty:
                        pass
                self._audio_q.put_nowait(b)
            except Exception:
                logger.debug("Realtime mic queue", exc_info=True)

        last_err = None
        for sr in self._samplerates_to_try(device_id):
            blocksize = max(int(sr * _APPEND_CHUNK_MS / 1000), 400)
            try:
                kwargs: dict = {
                    "channels": 1,
                    "samplerate": sr,
                    "blocksize": blocksize,
                    "dtype": "int16",
                    "callback": callback,
                }
                if device_id is not None:
                    kwargs["device"] = device_id
                stream = sd.RawInputStream(**kwargs)
                stream.start()
                self._mic_stream = stream
                self._mic_native_sr = sr
                logger.info("Realtime mic open: device=%s samplerate=%s", device_id, sr)
                return True
            except Exception as e:
                last_err = e
        logger.warning("Realtime: could not open microphone: %s", last_err)
        return False

    def _close_mic(self) -> None:
        if self._mic_stream is not None:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None

    def _close_aplay(self) -> None:
        proc = self._aplay_proc
        self._aplay_proc = None
        self._aplay_for_response = None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=2.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _ensure_aplay(self, response_id: str | None) -> None:
        if not shutil.which("aplay"):
            return
        rid = response_id or "_"
        if (
            self._aplay_proc
            and self._aplay_for_response == rid
            and self._aplay_proc.poll() is None
        ):
            return
        self._close_aplay()
        try:
            self._aplay_proc = subprocess.Popen(
                [
                    "aplay",
                    "-q",
                    "-t",
                    "raw",
                    "-f",
                    "S16_LE",
                    "-r",
                    str(_REALTIME_RATE),
                    "-c",
                    "1",
                    "-",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._aplay_for_response = rid
        except Exception:
            logger.exception("Realtime: could not start aplay")
            self._aplay_proc = None

    def _play_delta(self, response_id: str | None, delta_b64: str) -> None:
        if not delta_b64:
            return
        try:
            raw = base64.b64decode(delta_b64)
        except Exception:
            return
        if not raw:
            return
        self._ensure_aplay(response_id)
        proc = self._aplay_proc
        if proc is None or proc.stdin is None:
            return
        try:
            proc.stdin.write(raw)
            proc.stdin.flush()
        except BrokenPipeError:
            self._close_aplay()
        except Exception:
            logger.debug("Realtime aplay write", exc_info=True)

    def _queue_get_audio(self):
        try:
            return self._audio_q.get(timeout=0.2)
        except queue.Empty:
            return b""

    async def _pump_out_audio(self) -> None:
        assert self._ws is not None
        ws = self._ws
        native_sr = getattr(self, "_mic_native_sr", _REALTIME_RATE)
        # Size chunks in the *native* sample rate so each resampled block is
        # _APPEND_CHUNK_MS of audio at 24 kHz (fix: using 24 kHz counts at 48 kHz
        # halved the effective chunk duration).
        _native_chunk_samples = max(1, int(native_sr * _APPEND_CHUNK_MS / 1000))
        chunk_bytes = _native_chunk_samples * 2
        buf = bytearray()
        loop = asyncio.get_event_loop()

        while not self._stop.is_set():
            piece = await loop.run_in_executor(None, self._queue_get_audio)
            if piece is None:
                break
            if piece == b"":
                continue
            buf.extend(piece)
            while len(buf) >= chunk_bytes:
                take = bytes(buf[:chunk_bytes])
                del buf[:chunk_bytes]
                out = resample_pcm16_mono(take, native_sr, _REALTIME_RATE)
                payload = base64.b64encode(out).decode("ascii")
                evt = {"type": "input_audio_buffer.append", "audio": payload}
                try:
                    await ws.send(json.dumps(evt))
                except Exception:
                    logger.exception("Realtime: append failed")
                    return

    async def _handle_response_done(self, msg: dict) -> None:
        assert self._ws is not None
        ws = self._ws
        response = msg.get("response") or {}
        outputs = response.get("output") or []
        if not isinstance(outputs, list):
            return
        for item in outputs:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "function_call":
                continue
            call_id = (item.get("call_id") or "").strip()
            name = (item.get("name") or "").strip()
            arguments = item.get("arguments")
            if arguments is None:
                arguments = "{}"
            elif not isinstance(arguments, str):
                arguments = json.dumps(arguments)
            if not call_id or not name:
                continue
            out = invoke_realtime_tool_sync(
                self._backend_base_url,
                self._device_token,
                call_id=call_id,
                name=name,
                arguments=arguments,
            )
            if name == "navigate_device_ui":
                self._emit_device_navigation(out)
            out_evt = {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": out,
                },
            }
            try:
                await ws.send(json.dumps(out_evt))
                await ws.send(json.dumps({"type": "response.create"}))
            except Exception:
                logger.exception("Realtime: tool round-trip send failed")

    def _event_audio_delta(self, msg: dict) -> tuple[str | None, str]:
        """Return (response_id, base64_delta) from a streaming audio delta event."""
        rid = msg.get("response_id")
        if not isinstance(rid, str):
            r = msg.get("response")
            if isinstance(r, dict):
                rid = r.get("id")
        if not isinstance(rid, str):
            rid = None
        d = msg.get("delta")
        if d is None:
            d = msg.get("audio")
        if isinstance(d, dict):
            d = d.get("audio") or d.get("delta")
        if d is None:
            return rid, ""
        return rid, str(d)

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        ws = self._ws
        try:
            async for raw in ws:
                if self._stop.is_set():
                    break
                try:
                    if isinstance(raw, (bytes, bytearray)):
                        raw = raw.decode("utf-8")
                    msg = json.loads(raw)
                except Exception:
                    continue
                t = msg.get("type", "")

                if t == "session.created" and not self._connected_fired:
                    self._connected_fired = True
                    try:
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "session.update",
                                    "session": {
                                        "type": "realtime",
                                        "input_audio_format": "pcm16",
                                        "output_audio_format": "pcm16",
                                        "turn_detection": {
                                            "type": "server_vad",
                                            "threshold": 0.5,
                                            "prefix_padding_ms": 300,
                                            "silence_duration_ms": 800,
                                        },
                                    },
                                }
                            )
                        )
                    except Exception:
                        logger.debug("session.update", exc_info=True)
                    self._emit_connected()

                if t in ("response.output_audio.delta", "response.audio.delta"):
                    rid, d64 = self._event_audio_delta(msg)
                    self._play_delta(rid, d64)

                elif t in ("response.output_audio.done", "response.audio.done"):
                    self._close_aplay()

                elif t == "response.done":
                    self._close_aplay()
                    await self._handle_response_done(msg)

                elif t == "error":
                    err = msg.get("error")
                    if isinstance(err, dict):
                        em = (err.get("message") or err.get("code") or str(err))
                    else:
                        em = str(err or msg)
                    logger.warning("Realtime server error: %s", em)
                    self._emit_error(str(em))
                    break

                elif t == "invalid_request_error":
                    self._emit_error(msg.get("message") or "invalid_request_error")
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Realtime recv loop failed")

    async def _async_main(self) -> None:
        if not self._client_secret or not self._model:
            self._emit_error("Missing client secret or model for Realtime.")
            self._emit_session_end()
            return

        self._loop = asyncio.get_running_loop()
        url = build_realtime_websocket_url(self._model)
        headers = [("Authorization", f"Bearer {self._client_secret}")]

        try:
            async with websockets.connect(
                url,
                additional_headers=headers,
                max_size=None,
                ping_interval=20,
                ping_timeout=20,
            ) as ws:
                self._ws = ws
                device_id = self._resolve_input_device()
                if not self._open_mic(device_id):
                    self._emit_error("Realtime: microphone unavailable.")
                    await ws.close()
                    self._emit_session_end()
                    return

                recv_task = asyncio.create_task(self._recv_loop())
                pump_task = asyncio.create_task(self._pump_out_audio())

                done, _pending = await asyncio.wait(
                    {recv_task, pump_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for d in done:
                    if d.done() and not d.cancelled():
                        exc = d.exception()
                        if exc:
                            logger.debug("Realtime task failed: %s", exc)

                self._stop.set()
                recv_task.cancel()
                pump_task.cancel()
                await asyncio.gather(recv_task, pump_task, return_exceptions=True)

        except Exception as e:
            logger.exception("Realtime WebSocket session failed")
            self._emit_error(str(e))
        finally:
            self._ws = None
            self._close_aplay()
            self._close_mic()
            self._emit_session_end()

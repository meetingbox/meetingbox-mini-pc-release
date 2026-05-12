"""
OpenAI Realtime (speech-to-speech) session for MeetingBox device UI.

Runs in a background thread: captures PCM16 mono 24kHz mic, streams to the Realtime
WebSocket using an ephemeral client secret, plays model audio, and proxies tool
calls to the MeetingBox API (Mem0 + briefing bundle).
"""

from __future__ import annotations

import base64
import json
import logging
import queue
import threading
from collections.abc import Callable

import httpx
import numpy as np
import sounddevice as sd
from openai import OpenAI

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000


class _QueueAudioPlayer:
    """sounddevice OutputStream callback that drains a queue of PCM16 chunks."""

    def __init__(self, audio_queue: queue.Queue[bytes | None]) -> None:
        self._q = audio_queue
        self._buf = bytearray()

    def __call__(self, outdata, frames, time, status) -> None:  # noqa: ANN001
        if status:
            logger.debug("audio out status: %s", status)
        need_bytes = frames * 2
        while len(self._buf) < need_bytes:
            try:
                piece = self._q.get_nowait()
            except queue.Empty:
                break
            if piece is None:
                break
            self._buf.extend(piece)
        take = min(need_bytes, len(self._buf))
        if take:
            outdata[: take // 2, 0] = np.frombuffer(memoryview(self._buf)[:take], dtype=np.int16).copy()
            del self._buf[:take]
        if take < need_bytes:
            outdata[take // 2 :, 0] = 0


class RealtimeVoiceSession:
    def __init__(
        self,
        *,
        client_secret: str,
        model: str,
        backend_base_url: str,
        device_token: str,
        on_session_end: Callable[[], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_connected: Callable[[], None] | None = None,
    ) -> None:
        self._client_secret = client_secret
        self._model = model
        self._backend_base = backend_base_url.rstrip("/")
        self._token = (device_token or "").strip()
        self._on_session_end = on_session_end
        self._on_error = on_error
        self._on_connected = on_connected
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="realtime-voice", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        th = self._thread
        self._thread = None
        if th and th.is_alive():
            th.join(timeout=8.0)

    def _invoke_tool_sync(self, call_id: str, name: str, arguments: str) -> str:
        try:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(
                    f"{self._backend_base}/api/voice/realtime/tools/invoke",
                    headers={"Authorization": f"Bearer {self._token}"},
                    json={"call_id": call_id, "name": name, "arguments": arguments or "{}"},
                )
                r.raise_for_status()
                data = r.json()
                return str(data.get("output") or "")
        except Exception as e:
            logger.exception("Realtime tool invoke failed")
            return json.dumps({"error": str(e), "call_id": call_id, "tool": name})

    def _run(self) -> None:
        conn_mgr = None
        conn = None
        out_stream = None
        rt: threading.Thread | None = None
        stop_recv = threading.Event()
        audio_out: queue.Queue[bytes | None] = queue.Queue()

        try:
            oai = OpenAI(api_key=self._client_secret)
            conn_mgr = oai.realtime.connect(model=self._model)
            conn = conn_mgr.__enter__()
        except Exception as e:
            logger.exception("Realtime WebSocket connect failed")
            if self._on_error:
                try:
                    self._on_error(str(e))
                except Exception:
                    pass
        else:
            player = _QueueAudioPlayer(audio_out)
            try:
                out_stream = sd.OutputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="int16",
                    blocksize=2048,
                    callback=player,
                )
                out_stream.start()
            except Exception:
                logger.exception("audio output stream failed")
                try:
                    conn.close()
                except Exception:
                    pass
                try:
                    if conn_mgr is not None:
                        conn_mgr.__exit__(None, None, None)
                except Exception:
                    pass
                if self._on_session_end:
                    try:
                        self._on_session_end()
                    except Exception:
                        pass
                return

            if self._on_connected:
                try:
                    self._on_connected()
                except Exception:
                    logger.exception("Realtime on_connected failed")

            def recv_loop() -> None:
                try:
                    while not self._stop.is_set() and not stop_recv.is_set():
                        try:
                            ev = conn.recv()
                        except Exception:
                            break
                        et = getattr(ev, "type", None)
                        if et == "response.output_audio.delta":
                            delta = getattr(ev, "delta", None) or ""
                            if delta:
                                try:
                                    pcm = base64.b64decode(delta)
                                    audio_out.put(pcm)
                                except Exception:
                                    logger.debug("bad audio delta", exc_info=True)
                        elif et == "response.function_call_arguments.done":
                            call_id = getattr(ev, "call_id", "") or ""
                            name = getattr(ev, "name", "") or ""
                            arguments = getattr(ev, "arguments", "") or "{}"
                            out = self._invoke_tool_sync(call_id, name, arguments)
                            try:
                                conn.conversation.item.create(
                                    item={
                                        "type": "function_call_output",
                                        "call_id": call_id,
                                        "output": out,
                                    }
                                )
                                conn.response.create()
                            except Exception:
                                logger.exception("submit tool output failed")
                        elif et == "error":
                            logger.warning("Realtime error event: %s", ev)
                finally:
                    stop_recv.set()
                    try:
                        audio_out.put(None)
                    except Exception:
                        pass

            rt = threading.Thread(target=recv_loop, name="realtime-recv", daemon=True)
            rt.start()

            try:
                with sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="int16",
                    blocksize=2400,
                ) as in_stream:
                    while not self._stop.is_set():
                        data, _overflowed = in_stream.read(2400)
                        b64 = base64.b64encode(data.tobytes()).decode("ascii")
                        try:
                            conn.input_audio_buffer.append(audio=b64)
                        except Exception:
                            logger.info("Realtime append ended")
                            break
            except Exception:
                logger.exception("mic capture failed")
            self._stop.set()
            stop_recv.set()
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
            try:
                if conn_mgr is not None:
                    conn_mgr.__exit__(None, None, None)
            except Exception:
                pass
            try:
                if out_stream is not None:
                    out_stream.stop()
                    out_stream.close()
            except Exception:
                pass
            if rt is not None:
                rt.join(timeout=4.0)

        if self._on_session_end:
            try:
                self._on_session_end()
            except Exception:
                pass


__all__ = ["RealtimeVoiceSession", "SAMPLE_RATE"]

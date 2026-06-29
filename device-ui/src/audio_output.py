"""Cross-platform audio playback for the MeetingBox device UI.

On the Linux appliance, model/TTS audio is played by piping PCM/WAV to
``aplay`` (ALSA). Windows has no ``aplay``; this module provides a small,
dependency-light playback layer built on :mod:`sounddevice` (PortAudio),
which is already a project dependency and works on Windows, macOS and Linux.

Two surfaces are exposed:

* :func:`play_pcm16` — blocking playback of raw little-endian PCM16 mono bytes
  at a given sample rate. Used by the local TTS fallback.
* :class:`PcmStreamPlayer` — a low-latency streaming sink for the OpenAI
  Realtime path: ``write()`` queues PCM frames, ``stop()`` performs an
  immediate barge-in flush (drop queued audio + abort the stream).

Both honour an explicit output device via the ``device`` argument or the
``MEETINGBOX_OUTPUT_DEVICE_INDEX`` env var; otherwise the system default
output device is used (the user's selected Windows playback device).
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import wave

logger = logging.getLogger(__name__)

try:  # sounddevice is a hard dependency, but never let import break the app.
    import numpy as np
except Exception:  # pragma: no cover - numpy is required elsewhere
    np = None  # type: ignore

try:
    import sounddevice as _sd
except Exception:  # pragma: no cover
    _sd = None  # type: ignore


def is_available() -> bool:
    """True when a PortAudio backend and numpy are importable."""
    return _sd is not None and np is not None


def _resolve_output_device(device):
    """Return an explicit output device id, or None for the system default."""
    if device is not None:
        return device
    env = (os.getenv("MEETINGBOX_OUTPUT_DEVICE_INDEX") or "").strip()
    if env.isdigit():
        return int(env)
    return None


def play_pcm16(
    pcm_bytes: bytes,
    sample_rate: int = 24000,
    channels: int = 1,
    device=None,
    blocking: bool = True,
) -> bool:
    """Play raw PCM16 audio. Returns True on success.

    This is a best-effort helper: any failure returns False so callers can
    fall through to another engine instead of raising.
    """
    if not is_available() or not pcm_bytes:
        return False
    try:
        arr = np.frombuffer(pcm_bytes, dtype=np.int16)
        if channels > 1:
            arr = arr.reshape(-1, channels)
        _sd.play(arr, samplerate=sample_rate, device=_resolve_output_device(device))
        if blocking:
            _sd.wait()
        return True
    except Exception as exc:  # noqa: BLE001 - playback is best-effort
        logger.debug("play_pcm16 failed: %s", exc)
        return False


def play_wav_file(path: str, device=None, blocking: bool = True) -> bool:
    """Play a WAV file (PCM16 expected). Returns True on success."""
    if not is_available():
        return False
    try:
        with wave.open(path, "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            frames = wf.readframes(wf.getnframes())
        return play_pcm16(frames, sample_rate=sr, channels=ch, device=device, blocking=blocking)
    except Exception as exc:  # noqa: BLE001
        logger.debug("play_wav_file failed (%s): %s", path, exc)
        return False


def stop_all() -> None:
    """Immediately stop any audio started via :func:`play_pcm16`/:func:`play_wav_file`."""
    if _sd is None:
        return
    try:
        _sd.stop()
    except Exception:  # noqa: BLE001
        pass


class PcmStreamPlayer:
    """Low-latency streaming PCM16 sink with barge-in support.

    Mirrors the semantics the Linux path got from a long-lived ``aplay`` pipe:
    audio frames are written continuously and playback can be killed instantly
    when the user starts speaking (barge-in). Internally a background thread
    feeds a :class:`sounddevice.RawOutputStream` from a queue.

    Usage::

        player = PcmStreamPlayer(sample_rate=24000)
        player.start()
        player.write(pcm_frame_bytes)   # repeatedly
        player.stop()                   # barge-in: drop queue + abort stream
        player.close()                  # on teardown
    """

    def __init__(self, sample_rate: int = 24000, channels: int = 1, device=None):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self._device = _resolve_output_device(device)
        self._stream = None
        self._queue: "queue.Queue[bytes | None]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._active = False

    def is_supported(self) -> bool:
        return _sd is not None

    def start(self) -> bool:
        if not self.is_supported():
            return False
        with self._lock:
            if self._active:
                return True
            self._active = True
            # Drain any stale sentinels from a previous stop().
            self._drain_queue()
            self._thread = threading.Thread(
                target=self._run, name="PcmStreamPlayer", daemon=True
            )
            self._thread.start()
            return True

    def _run(self) -> None:
        try:
            self._stream = _sd.RawOutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                device=self._device,
                blocksize=0,
            )
            self._stream.start()
        except Exception as exc:  # noqa: BLE001
            logger.warning("PcmStreamPlayer could not open output stream: %s", exc)
            self._active = False
            return
        try:
            while True:
                chunk = self._queue.get()
                if chunk is None:  # stop sentinel
                    break
                if not self._active:
                    break
                try:
                    self._stream.write(chunk)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("PcmStreamPlayer write error: %s", exc)
                    break
        finally:
            try:
                if self._stream is not None:
                    self._stream.stop()
                    self._stream.close()
            except Exception:  # noqa: BLE001
                pass
            self._stream = None

    def write(self, pcm_bytes: bytes) -> None:
        if not pcm_bytes or not self._active:
            return
        self._queue.put(pcm_bytes)

    def _drain_queue(self) -> None:
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass

    def stop(self) -> None:
        """Barge-in: drop queued audio and abort the active stream immediately."""
        with self._lock:
            if not self._active:
                return
            self._active = False
            self._drain_queue()
            self._queue.put(None)
            st = self._stream
        if st is not None:
            try:
                st.abort()
            except Exception:  # noqa: BLE001
                pass
        t = self._thread
        if t is not None:
            t.join(timeout=1.0)
        self._thread = None

    def close(self) -> None:
        self.stop()

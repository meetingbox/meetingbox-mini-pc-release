"""
Local wake-word voice control for the device UI.

Listens for a configurable wake phrase (default: "hey tony"), then accepts
simple follow-up voice commands such as "start meeting".
"""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import shutil
import threading
import time
import zipfile
from difflib import SequenceMatcher
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable
from urllib.request import Request, urlopen

from config import AUDIO_INPUT_DEVICE_INDEX, AUDIO_INPUT_DEVICE_NAME, resolve_device_config_dir

logger = logging.getLogger(__name__)

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    from vosk import KaldiRecognizer, Model, SetLogLevel
except ImportError:
    KaldiRecognizer = None
    Model = None
    SetLogLevel = None

if SetLogLevel is not None:
    try:
        SetLogLevel(-1)
    except Exception:
        pass

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off", ""}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(str(raw).strip())
    except ValueError:
        logger.warning("%s=%r is not a float; using %s", name, raw, default)
        return default


def _normalize_text(text: str) -> str:
    return " ".join(_NON_ALNUM_RE.sub(" ", (text or "").lower()).split())


def _phrase_windows(text: str, target: str) -> list[str]:
    words = text.split()
    target_len = max(1, len(target.split()))
    sizes = sorted({max(1, target_len - 1), target_len, target_len + 1})
    if len(words) <= max(sizes):
        return [text]

    windows: list[str] = []
    for size in sizes:
        if size > len(words):
            continue
        for idx in range(len(words) - size + 1):
            windows.append(" ".join(words[idx:idx + size]))
    return windows or [text]


def _best_phrase_similarity(text: str, target: str) -> float:
    norm_text = _normalize_text(text)
    norm_target = _normalize_text(target)
    if not norm_text or not norm_target:
        return 0.0
    if norm_target in norm_text:
        return 1.0
    return max(
        SequenceMatcher(None, candidate, norm_target).ratio()
        for candidate in _phrase_windows(norm_text, norm_target)
    )


class VoiceCommandInterpreter:
    """Small state machine for wake phrase + follow-up command recognition."""

    def __init__(
        self,
        wake_phrase: str,
        start_commands: list[str],
        command_timeout_seconds: float = 6.0,
        action_cooldown_seconds: float = 8.0,
    ):
        self.wake_phrase = _normalize_text(wake_phrase)
        self.start_commands = [_normalize_text(cmd) for cmd in start_commands if _normalize_text(cmd)]
        self.command_timeout_seconds = max(1.0, command_timeout_seconds)
        self.action_cooldown_seconds = max(1.0, action_cooldown_seconds)
        self._awaiting_command_until = 0.0
        self._last_action_at = 0.0

    def reset(self) -> None:
        self._awaiting_command_until = 0.0

    def _heard_wake_phrase(self, text: str) -> bool:
        return _best_phrase_similarity(text, self.wake_phrase) >= 0.72

    def _heard_start_command(self, text: str) -> bool:
        return any(_best_phrase_similarity(text, cmd) >= 0.78 for cmd in self.start_commands)

    def heard_wake_phrase(self, text: str) -> bool:
        return self._heard_wake_phrase(_normalize_text(text))

    def heard_start_command(self, text: str) -> bool:
        return self._heard_start_command(_normalize_text(text))

    def handle_transcript(self, text: str, now: float | None = None) -> str | None:
        now = time.monotonic() if now is None else now
        norm = _normalize_text(text)
        if not norm:
            if now > self._awaiting_command_until:
                self.reset()
            return None

        if now - self._last_action_at < self.action_cooldown_seconds:
            return None

        heard_wake = self._heard_wake_phrase(norm)
        heard_start = self._heard_start_command(norm)

        if heard_wake and heard_start:
            self.reset()
            self._last_action_at = now
            return "start_meeting"

        if heard_wake:
            self._awaiting_command_until = now + self.command_timeout_seconds
            return None

        if heard_start and now <= self._awaiting_command_until:
            self.reset()
            self._last_action_at = now
            return "start_meeting"

        if now > self._awaiting_command_until:
            self.reset()
        return None


class VoiceAssistant:
    """
    Background speech listener backed by Vosk + sounddevice.

    The assistant only exposes a single action for now: start the current
    meeting recording.
    """

    def __init__(
        self,
        on_start_meeting: Callable[[], None],
        on_wake_phrase: Callable[[str], None] | None = None,
    ):
        self._on_start_meeting = on_start_meeting
        self._on_wake_phrase = on_wake_phrase
        self.enabled = _env_flag("VOICE_ASSISTANT_ENABLED", True)
        self.wake_phrase = (os.getenv("VOICE_ASSISTANT_WAKE_PHRASE") or "hey tony").strip() or "hey tony"
        self.start_commands = [
            cmd.strip()
            for cmd in (os.getenv("VOICE_ASSISTANT_START_COMMANDS") or "start meeting,start the meeting,start recording").split(",")
            if cmd.strip()
        ]
        self.command_timeout_seconds = _env_float("VOICE_ASSISTANT_COMMAND_TIMEOUT", 6.0)
        self.action_cooldown_seconds = _env_float("VOICE_ASSISTANT_ACTION_COOLDOWN", 8.0)
        self.model_name = (
            os.getenv("VOICE_ASSISTANT_MODEL_NAME") or "vosk-model-small-en-us-0.15"
        ).strip() or "vosk-model-small-en-us-0.15"
        self.model_url = (
            os.getenv("VOICE_ASSISTANT_MODEL_URL")
            or f"https://alphacephei.com/vosk/models/{self.model_name}.zip"
        ).strip()
        configured_model_dir = (os.getenv("VOICE_ASSISTANT_MODEL_DIR") or "").strip()
        if configured_model_dir:
            self.model_dir = Path(configured_model_dir)
        else:
            self.model_dir = resolve_device_config_dir() / "voice" / self.model_name

        self._interpreter = VoiceCommandInterpreter(
            wake_phrase=self.wake_phrase,
            start_commands=self.start_commands,
            command_timeout_seconds=self.command_timeout_seconds,
            action_cooldown_seconds=self.action_cooldown_seconds,
        )
        self._audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=32)
        self._stop_event = threading.Event()
        self._pause_lock = threading.Lock()
        self._paused = True
        self._thread: threading.Thread | None = None
        self._stream = None
        self._stream_samplerate = 0
        self._recognizer = None
        self._model = None
        self._model_lock = threading.Lock()
        self._warned_unavailable = False

    @property
    def available(self) -> bool:
        return self.enabled and sd is not None and Model is not None and KaldiRecognizer is not None

    def start(self) -> bool:
        if not self._can_run():
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="voice-assistant", daemon=True)
        self._thread.start()
        logger.info("Voice assistant starting (wake phrase: %s)", self.wake_phrase)
        return True

    def stop(self) -> None:
        self._stop_event.set()
        self._close_stream()
        self._clear_audio_queue()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def set_paused(self, paused: bool) -> None:
        with self._pause_lock:
            changed = self._paused != paused
            self._paused = paused
        if not changed:
            return
        if paused:
            logger.info("Voice assistant paused")
            self._interpreter.reset()
            self._close_stream()
            self._clear_audio_queue()
        else:
            logger.info("Voice assistant listening")

    def _can_run(self) -> bool:
        if not self.enabled:
            return False
        if sd is None or Model is None or KaldiRecognizer is None:
            if not self._warned_unavailable:
                logger.warning(
                    "Voice assistant disabled: install sounddevice and vosk dependencies"
                )
                self._warned_unavailable = True
            return False
        return True

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if self._is_paused():
                self._stop_event.wait(0.25)
                continue
            if not self._ensure_model_ready():
                self._stop_event.wait(10.0)
                continue
            if self._stream is None and not self._open_stream():
                self._stop_event.wait(4.0)
                continue
            try:
                chunk = self._audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if self._recognizer is None:
                continue
            try:
                if self._recognizer.AcceptWaveform(chunk):
                    result = json.loads(self._recognizer.Result() or "{}")
                    self._handle_transcript(result.get("text", ""))
            except Exception:
                logger.exception("Voice assistant recognition failed")
                self._reset_recognizer()

        self._close_stream()

    def _is_paused(self) -> bool:
        with self._pause_lock:
            return self._paused

    def _handle_transcript(self, text: str) -> None:
        norm = _normalize_text(text)
        if not norm:
            return
        logger.debug("Voice assistant heard: %s", norm)
        if (
            self._on_wake_phrase is not None
            and self._interpreter.heard_wake_phrase(norm)
            and not self._interpreter.heard_start_command(norm)
        ):
            try:
                self._on_wake_phrase(norm)
            except Exception:
                logger.exception("Voice assistant wake callback failed")
        action = self._interpreter.handle_transcript(norm)
        if action == "start_meeting":
            logger.info('Voice command accepted: "%s" -> start meeting', norm)
            try:
                self._on_start_meeting()
            except Exception:
                logger.exception("Voice assistant callback failed")

    def _resolve_input_device(self):
        idx_s = (AUDIO_INPUT_DEVICE_INDEX or "").strip()
        if idx_s.isdigit():
            return int(idx_s)
        name_sub = (AUDIO_INPUT_DEVICE_NAME or "").strip().lower()
        if not name_sub or sd is None:
            return None
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if int(dev.get("max_input_channels") or 0) > 0 and name_sub in (
                    dev.get("name") or ""
                ).lower():
                    return idx
        except Exception:
            logger.exception("Voice assistant could not enumerate audio devices")
        return None

    def _samplerates_to_try(self, device_id) -> list[int]:
        out = [16000, 22050, 32000, 44100, 48000]
        if sd is None or device_id is None:
            return out
        try:
            info = sd.query_devices(device_id)
            default_rate = int(float(info.get("default_samplerate") or 0))
            if default_rate > 0 and default_rate not in out:
                out.insert(0, default_rate)
        except Exception:
            pass
        return out

    def _open_stream(self) -> bool:
        if sd is None or self._model is None:
            return False

        device_id = self._resolve_input_device()

        def callback(indata, frames, time_info, status):
            del frames, time_info
            if status and str(status):
                logger.debug("Voice assistant sounddevice status: %s", status)
            if self._stop_event.is_set() or self._is_paused():
                return
            try:
                self._audio_queue.put_nowait(bytes(indata))
            except queue.Full:
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._audio_queue.put_nowait(bytes(indata))
                except queue.Full:
                    pass

        last_err = None
        for samplerate in self._samplerates_to_try(device_id):
            try:
                kwargs = {
                    "channels": 1,
                    "samplerate": samplerate,
                    "blocksize": 4000,
                    "dtype": "int16",
                    "callback": callback,
                }
                if device_id is not None:
                    kwargs["device"] = device_id
                self._stream = sd.RawInputStream(**kwargs)
                self._stream.start()
                self._stream_samplerate = samplerate
                self._recognizer = KaldiRecognizer(self._model, samplerate)
                logger.info(
                    "Voice assistant input stream started (device=%s samplerate=%s)",
                    device_id,
                    samplerate,
                )
                return True
            except Exception as exc:
                last_err = exc
                self._close_stream()

        logger.warning("Voice assistant could not open microphone: %s", last_err)
        return False

    def _close_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._reset_recognizer()

    def _reset_recognizer(self) -> None:
        self._recognizer = None
        self._stream_samplerate = 0

    def _clear_audio_queue(self) -> None:
        while True:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                return

    def _ensure_model_ready(self) -> bool:
        if self._model is not None:
            return True

        with self._model_lock:
            if self._model is not None:
                return True

            model_dir = self.model_dir
            if not self._looks_like_model_dir(model_dir):
                try:
                    self._download_model(model_dir)
                except Exception as exc:
                    logger.warning("Voice assistant model download failed: %s", exc)
                    return False

            try:
                self._model = Model(str(model_dir))
                logger.info("Voice assistant model ready: %s", model_dir)
                return True
            except Exception as exc:
                logger.warning("Voice assistant could not load model %s: %s", model_dir, exc)
                return False

    @staticmethod
    def _looks_like_model_dir(path: Path) -> bool:
        return path.is_dir() and (path / "am").is_dir() and (path / "conf").is_dir()

    def _download_model(self, target_dir: Path) -> None:
        target_dir = target_dir.resolve()
        target_parent = target_dir.parent
        target_parent.mkdir(parents=True, exist_ok=True)

        if self._looks_like_model_dir(target_dir):
            return

        logger.info("Downloading offline voice model to %s", target_dir)
        with TemporaryDirectory(dir=str(target_parent)) as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            zip_path = tmpdir / f"{self.model_name}.zip"
            req = Request(self.model_url, headers={"User-Agent": "MeetingBox Voice Assistant"})
            with urlopen(req, timeout=120) as response, zip_path.open("wb") as fh:
                shutil.copyfileobj(response, fh)

            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(tmpdir)

            extracted_dirs = [p for p in tmpdir.iterdir() if p.is_dir()]
            if not extracted_dirs:
                raise RuntimeError("voice model archive did not contain a directory")

            extracted_dir = next(
                (p for p in extracted_dirs if self._looks_like_model_dir(p)),
                extracted_dirs[0],
            )
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            shutil.move(str(extracted_dir), str(target_dir))

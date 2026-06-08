"""
Tiny publisher for bridge UI events.

The Python voice + audio runtime (voice_assistant.py, realtime_voice_session.py,
audio capture) used to drive the Kivy UI directly through Clock-scheduled
callbacks. In the Flutter architecture the UI lives in a separate process, so
those callbacks instead publish lifecycle events to the local device bridge,
which fans them out to the Flutter UI over a WebSocket.

This module is deliberately dependency-light (stdlib + best-effort) so it can be
imported from any runtime daemon without pulling in Kivy or FastAPI.

Usage from the voice runtime::

    from bridge_events import publish_voice_state, publish_audio_level

    publish_voice_state("listening")
    publish_audio_level(0.42)
    publish_voice_state("speaking", text="Sure, scheduling that now.")
    publish_voice_state("idle")
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.request

logger = logging.getLogger(__name__)

# Local bridge base URL; overridable so the daemon and bridge can live apart.
_BRIDGE_URL = os.getenv("DEVICE_BRIDGE_URL", "http://127.0.0.1:8765").rstrip("/")
_PUBLISH_PATH = "/v1/events/publish"
_TIMEOUT = 1.5


def _post(payload: dict) -> None:
    url = f"{_BRIDGE_URL}{_PUBLISH_PATH}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=_TIMEOUT).close()
    except Exception as exc:  # bridge may be down; UI events are best-effort
        logger.debug("bridge event publish failed: %s", exc)


def _post_async(payload: dict) -> None:
    """Fire-and-forget so audio/voice callbacks never block on the UI bridge."""
    threading.Thread(target=_post, args=(payload,), daemon=True).start()


def publish_voice_state(state: str, *, text: str | None = None) -> None:
    """state: idle | listening | thinking | speaking | error."""
    event = {"type": "voice_state", "state": state}
    if text:
        event["text"] = text
    _post_async(event)


def publish_audio_level(level: float) -> None:
    """Live mic amplitude 0..1 for the recording wavebar / listening orb."""
    _post_async({"type": "audio_level", "level": float(level)})


def publish_mic_test_level(level: float) -> None:
    """Mic-test amplitude 0..1 used by the audio settings mic test."""
    _post_async({"type": "mic_test_level", "level": float(level)})


def publish_recording_state(state: str) -> None:
    """state: started | recording | paused | stopped."""
    _post_async({"type": "recording_state", "state": state})


def publish_error(detail: str) -> None:
    _post_async({"type": "error", "detail": detail})

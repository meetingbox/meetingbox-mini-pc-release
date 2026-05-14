"""Realtime WebSocket helpers and sync tool invoke."""

import sys
import types
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Kivy is optional in CI; stub minimal clock API before importing realtime_voice_session.
_mod_kivy = types.ModuleType("kivy")
_mod_clock = types.ModuleType("kivy.clock")


class _Clock:
    @staticmethod
    def schedule_once(fn, dt=0):
        return None


_mod_clock.Clock = _Clock
sys.modules.setdefault("kivy", _mod_kivy)
sys.modules.setdefault("kivy.clock", _mod_clock)

from realtime_voice_session import (  # noqa: E402
    build_realtime_websocket_url,
    resample_pcm16_mono,
)


def test_build_realtime_websocket_url_encodes_model():
    u = build_realtime_websocket_url("gpt-realtime-2")
    assert u.startswith("wss://api.openai.com/v1/realtime?model=")
    assert "gpt-realtime-2" in u


def test_build_realtime_websocket_url_defaults_when_blank():
    u = build_realtime_websocket_url("")
    assert "gpt-realtime-2" in u


def test_resample_pcm16_mono_noop_at_same_rate():
    samples = (np.ones(100, dtype=np.int16) * 1000).tobytes()
    out = resample_pcm16_mono(samples, 24000, 24000)
    assert out == samples


def test_resample_pcm16_mono_changes_rate():
    x = np.linspace(-1, 1, num=240, dtype=np.float32)
    pcm = (x * 30000).astype(np.int16).tobytes()
    out48000 = resample_pcm16_mono(pcm, 24000, 48000)
    assert len(out48000) > len(pcm)


def test_invoke_realtime_tool_sync_uses_httpx(monkeypatch):
    import api_client

    post_resp = mock.MagicMock()
    post_resp.raise_for_status = mock.MagicMock()
    post_resp.json.return_value = {"output": '{"snip":"ok"}'}

    ctx = mock.MagicMock()
    ctx.__enter__.return_value.post.return_value = post_resp
    ctx.__exit__.return_value = None
    monkeypatch.setattr(api_client.httpx, "Client", lambda **kwargs: ctx)

    out = api_client.invoke_realtime_tool_sync(
        "http://127.0.0.1:8000",
        "mbd_test",
        call_id="call_1",
        name="memory_search",
        arguments='{"query":"x"}',
    )
    assert out == '{"snip":"ok"}'
    assert ctx.__enter__.return_value.post.called

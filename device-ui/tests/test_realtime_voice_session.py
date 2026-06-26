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
    _APPEND_CHUNK_MS,
    _DEFAULT_INPUT_TRANSCRIPTION_MODEL,
    _INPUT_TRANSCRIPTION_PROMPT,
    _MIC_QUEUE_POLL_S,
    RealtimeVoiceSession,
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


def test_resolve_sounddevice_capture_prefers_usb_then_builtin_then_first(monkeypatch):
    import mic_input_resolve as mir

    class _SD:
        @staticmethod
        def query_devices():
            return [
                {"name": "Internal Mic Array", "max_input_channels": 2},
                {"name": "USB PnP Sound Device", "max_input_channels": 1},
                {"name": "HDMI Output", "max_input_channels": 0},
            ]

    assert mir.resolve_sounddevice_capture_device_index(_SD) == 1

    monkeypatch.setenv("MEETINGBOX_USB_MIC_STRICT", "0")

    class _SDNoUsb:
        @staticmethod
        def query_devices():
            return [
                {"name": "Built-in Audio Analog Stereo", "max_input_channels": 2},
                {"name": "Another Capture", "max_input_channels": 1},
            ]

    assert mir.resolve_sounddevice_capture_device_index(_SDNoUsb) == 0

    class _SDNoHints:
        @staticmethod
        def query_devices():
            return [
                {"name": "Mic Device A", "max_input_channels": 1},
                {"name": "Mic Device B", "max_input_channels": 1},
            ]

    assert mir.resolve_sounddevice_capture_device_index(_SDNoHints) == 0


def test_capture_device_fallback_candidates_include_default_and_none():
    import mic_input_resolve as mir

    class _SD:
        default = type("D", (), {"device": [2, 0]})

        @staticmethod
        def query_devices():
            return [
                {"name": "A", "max_input_channels": 1},
                {"name": "B", "max_input_channels": 1},
                {"name": "C", "max_input_channels": 1},
            ]

    out = mir.capture_device_fallback_candidates(_SD, preferred=1)
    assert out[0] == 1
    assert 2 in out
    assert None in out


def test_realtime_latency_tuning_constants():
    # 20 ms avoids PortAudio input overflow on the appliance while staying
    # comfortably below perceptible turn-latency boundaries.
    assert _APPEND_CHUNK_MS <= 20
    assert _MIC_QUEUE_POLL_S <= 0.01


def test_realtime_transcription_defaults_are_accuracy_first():
    assert _DEFAULT_INPUT_TRANSCRIPTION_MODEL == "gpt-4o-transcribe"
    assert _INPUT_TRANSCRIPTION_PROMPT == ""


def test_local_barge_in_uses_reference_and_consecutive_frames(monkeypatch):
    import realtime_voice_session as rtv

    monkeypatch.setattr(rtv, "sd", None)
    session = RealtimeVoiceSession(
        client_secret="ek_test",
        model="gpt-realtime-2",
        backend_base_url="http://127.0.0.1:8000",
        device_token="mbd_test",
        on_session_end=lambda: None,
        on_error=lambda _msg: None,
        on_connected=lambda: None,
    )
    session._response_in_progress = True

    ref = (np.ones(480, dtype=np.int16) * 200).tobytes()
    quiet = (np.ones(480, dtype=np.int16) * 250).tobytes()
    speech = (np.ones(480, dtype=np.int16) * 4000).tobytes()
    session._aec_far_buf.extend(ref)

    detected, *_ = session._detect_local_barge_in(quiet, now=10.0)
    assert detected is False

    detected, *_ = session._detect_local_barge_in(speech, now=10.02)
    assert detected is False
    detected, mic_rms, ref_rms, threshold, echo_similarity = session._detect_local_barge_in(speech, now=10.04)
    assert detected is True
    assert mic_rms > threshold
    assert ref_rms > 0
    assert echo_similarity <= 1.0


def test_local_barge_in_triggers_on_echo_divergence_without_rms_spike(monkeypatch):
    import realtime_voice_session as rtv

    monkeypatch.setattr(rtv, "sd", None)
    session = RealtimeVoiceSession(
        client_secret="ek_test",
        model="gpt-realtime-2",
        backend_base_url="http://127.0.0.1:8000",
        device_token="mbd_test",
        on_session_end=lambda: None,
        on_error=lambda _msg: None,
        on_connected=lambda: None,
    )
    session._response_in_progress = True

    t = np.linspace(0.0, 2.0 * np.pi, 480, endpoint=False, dtype=np.float32)
    ref_wave = (np.sin(t * 4.0) * 900.0).astype(np.int16)
    pure_echo = ref_wave.tobytes()
    # Use a different voice-like waveform than the far-end reference. It keeps
    # RMS below the strict spike threshold while dropping echo similarity.
    mixed = (np.sin(t * 11.0 + 0.7) * 1300.0).astype(np.int16).tobytes()
    session._aec_far_buf.extend(pure_echo)

    detected, *_ = session._detect_local_barge_in(pure_echo, now=20.0)
    assert detected is False
    detected, *_ = session._detect_local_barge_in(mixed, now=20.02)
    assert detected is False
    detected, mic_rms, ref_rms, threshold, similarity = session._detect_local_barge_in(mixed, now=20.04)
    assert detected is True
    assert mic_rms < threshold
    assert ref_rms > 0.0
    assert similarity < 0.72

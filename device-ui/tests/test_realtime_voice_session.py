"""Realtime WebSocket helpers and sync tool invoke."""

import asyncio
import json
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
    _extract_silent_hold_phrase,
    _silent_hold_phrase_heard,
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


def test_realtime_session_end_callback_is_idempotent(monkeypatch):
    import realtime_voice_session as rtv

    monkeypatch.setattr(rtv, "sd", None)

    class _ImmediateClock:
        @staticmethod
        def schedule_once(fn, _dt=0):
            fn(0)

    monkeypatch.setattr(rtv, "Clock", _ImmediateClock)
    ended = []
    session = RealtimeVoiceSession(
        client_secret="ek_test",
        model="gpt-realtime-2",
        backend_base_url="http://127.0.0.1:8000",
        device_token="mbd_test",
        on_session_end=lambda: ended.append(True),
        on_error=lambda _msg: None,
        on_connected=lambda: None,
    )

    session._emit_session_end()
    session._emit_session_end()

    assert ended == [True]


def test_device_session_lock_rejects_second_owner(tmp_path, monkeypatch):
    import config
    import realtime_voice_session as rtv

    monkeypatch.setattr(rtv, "sd", None)
    monkeypatch.setattr(config, "resolve_device_config_dir", lambda: tmp_path)

    class _FakeFcntl:
        LOCK_EX = 1
        LOCK_NB = 2
        LOCK_UN = 4
        locked = False

        @classmethod
        def flock(cls, _fd, operation):
            if operation == cls.LOCK_UN:
                cls.locked = False
            elif cls.locked:
                raise BlockingIOError
            else:
                cls.locked = True

    monkeypatch.setattr(rtv, "fcntl", _FakeFcntl)

    def _session():
        return RealtimeVoiceSession(
            client_secret="ek_test",
            model="gpt-realtime-2",
            backend_base_url="http://127.0.0.1:8000",
            device_token="mbd_test",
            on_session_end=lambda: None,
            on_error=lambda _msg: None,
            on_connected=lambda: None,
        )

    first = _session()
    second = _session()
    assert first._acquire_device_session_lock() is True
    assert second._acquire_device_session_lock() is False
    first._release_device_session_lock()
    assert second._acquire_device_session_lock() is True
    second._release_device_session_lock()


def test_stop_cancels_inflight_async_connection(monkeypatch):
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
    loop = mock.MagicMock()
    loop.is_closed.return_value = False
    task = mock.MagicMock()
    session._loop = loop
    session._async_task = task

    session.stop()

    loop.call_soon_threadsafe.assert_called_once_with(task.cancel)


def test_extract_silent_hold_phrase_from_user_request():
    assert (
        _extract_silent_hold_phrase("Nexa, pause until I say continue Nexa.")
        == "continue nexa"
    )
    assert (
        _extract_silent_hold_phrase("Stay quiet till I say the magic words welcome back.")
        == "welcome back"
    )
    assert (
        _extract_silent_hold_phrase(
            "Go into quiet mode until I say continue Nexa while I take this call."
        )
        == "continue nexa"
    )
    assert (
        _extract_silent_hold_phrase(
            "Mute yourself till I say resume Nexa, I need to speak with someone."
        )
        == "resume nexa"
    )
    assert (
        _extract_silent_hold_phrase("Please go into quiet mode for a while.")
        == "continue nexa"
    )
    assert _extract_silent_hold_phrase("Pause the recording.") == ""


def test_silent_hold_requires_complete_resume_phrase():
    assert _silent_hold_phrase_heard("Okay, continue Nexa now.", "continue nexa")
    assert _silent_hold_phrase_heard("Continue next.", "continue nexa")
    assert not _silent_hold_phrase_heard("Please continue.", "continue nexa")
    assert not _silent_hold_phrase_heard("Nexa is still paused.", "continue nexa")


def test_silent_hold_suppresses_audio_playback(monkeypatch):
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
    session._silent_hold_phrase = "continue nexa"
    ensure_aplay = mock.MagicMock()
    monkeypatch.setattr(session, "_ensure_aplay", ensure_aplay)

    session._play_delta("AQI=")

    ensure_aplay.assert_not_called()


def test_silent_hold_cancels_ambient_responses_and_resumes(monkeypatch):
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

    class _FakeWS:
        def __init__(self):
            self.events = iter([
                {
                    "type": "conversation.item.input_audio_transcription.completed",
                    "transcript": "Nexa pause until I say continue Nexa",
                },
                {"type": "response.created"},
                {"type": "response.done", "response": {}},
                {
                    "type": "conversation.item.input_audio_transcription.completed",
                    "transcript": "This conversation is not for Nexa",
                },
                {"type": "response.created"},
                {"type": "response.done", "response": {}},
                {
                    "type": "conversation.item.input_audio_transcription.completed",
                    "transcript": "Continue Nexa",
                },
                {"type": "response.created"},
                {"type": "response.done", "response": {}},
            ])
            self.sent = []

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return json.dumps(next(self.events))
            except StopIteration:
                raise StopAsyncIteration

        async def send(self, raw):
            self.sent.append(json.loads(raw))

    ws = _FakeWS()
    session._ws = ws
    asyncio.run(session._recv_loop())

    assert session._silent_hold_phrase == ""
    assert session._silent_hold_resume_pending is False
    assert sum(msg["type"] == "response.cancel" for msg in ws.sent) >= 3
    resumed = [msg for msg in ws.sent if msg["type"] == "response.create"]
    assert len(resumed) == 1
    assert "silent hold is now over" in resumed[0]["response"]["instructions"]


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
    monkeypatch.setattr(rtv, "_LOCAL_BARGE_IN_ECHO_DIVERGENCE_ENABLED", True)
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


def test_local_barge_in_ignores_echo_divergence_by_default(monkeypatch):
    import realtime_voice_session as rtv

    monkeypatch.setattr(rtv, "sd", None)
    monkeypatch.setattr(rtv, "_LOCAL_BARGE_IN_ECHO_DIVERGENCE_ENABLED", False)
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
    mixed = (np.sin(t * 11.0 + 0.7) * 1300.0).astype(np.int16).tobytes()
    session._aec_far_buf.extend(ref_wave.tobytes())

    detected, *_ = session._detect_local_barge_in(mixed, now=30.0)
    assert detected is False


def test_local_barge_in_blocks_echo_like_rms_spike(monkeypatch):
    import realtime_voice_session as rtv

    monkeypatch.setattr(rtv, "sd", None)
    monkeypatch.setattr(rtv, "_LOCAL_BARGE_IN_ECHO_DIVERGENCE_ENABLED", False)
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
    # Simulate a stale low baseline so threshold is dominated by ref ratio.
    session._barge_in_noise_rms = 120.0

    t = np.linspace(0.0, 2.0 * np.pi, 480, endpoint=False, dtype=np.float32)
    ref_wave = (np.sin(t * 5.0) * 1000.0).astype(np.int16)
    echo_spike = (ref_wave.astype(np.float32) * 1.85).astype(np.int16).tobytes()
    session._aec_far_buf.extend(ref_wave.tobytes())

    # Similarity is near-echo and mic/ref ratio is modest; should be vetoed.
    detected, mic_rms, ref_rms, threshold, similarity = session._detect_local_barge_in(
        echo_spike,
        now=40.0,
    )
    assert mic_rms > threshold
    assert ref_rms > 0.0
    assert similarity > 0.9
    assert detected is False


def test_far_ref_slice_uses_most_recent_audio(monkeypatch):
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
    old = (np.ones(120, dtype=np.int16) * 100).tobytes()
    new = (np.ones(120, dtype=np.int16) * 2000).tobytes()
    session._aec_far_buf.extend(old + new)

    ref = session._far_ref_slice(len(new))
    ref_rms = session._pcm_rms(ref)
    assert ref_rms > 1500

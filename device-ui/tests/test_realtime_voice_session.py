"""Realtime WebSocket helpers and sync tool invoke."""

import asyncio
import base64
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


def test_wake_greeting_varies_and_uses_account_name_only_occasionally(monkeypatch):
    rtv = sys.modules["realtime_voice_session"]
    monkeypatch.setattr(rtv, "sd", None)
    monkeypatch.setattr(rtv, "_wake_greeting_style_index", 0)
    session = RealtimeVoiceSession(
        client_secret="ek_test",
        model="gpt-realtime-2",
        backend_base_url="http://127.0.0.1:8000",
        device_token="mbd_test",
        display_name="Shiva Kumar",
        on_session_end=lambda: None,
        on_error=lambda _msg: None,
        on_connected=lambda: None,
    )
    ws = mock.AsyncMock()

    asyncio.run(session._send_wake_greeting(ws))

    payload = json.loads(ws.send.await_args.args[0])
    instructions = payload["response"]["instructions"]
    assert '"Shiva"' in instructions
    assert "exactly one natural greeting clause" in instructions
    assert "Vary the wording" in instructions
    assert "Never use garu, sir, madam" in instructions
    assert "Yes, I'm listening" not in instructions

    next_session = RealtimeVoiceSession(
        client_secret="ek_test",
        model="gpt-realtime-2",
        backend_base_url="http://127.0.0.1:8000",
        device_token="mbd_test",
        display_name="Shiva Kumar",
        on_session_end=lambda: None,
        on_error=lambda _msg: None,
        on_connected=lambda: None,
    )
    next_ws = mock.AsyncMock()
    asyncio.run(next_session._send_wake_greeting(next_ws))
    next_instructions = json.loads(next_ws.send.await_args.args[0])["response"]["instructions"]
    assert '"Shiva"' not in next_instructions
    assert next_instructions != instructions


def test_audio_route_snapshot_includes_hotplug_inventory(monkeypatch):
    outputs = iter(
        (
            "built_in_source\n",
            "built_in_sink\n",
            (
                "1\tbuilt_in_source\tPipeWire\n"
                "2\tusb_input\tPipeWire\n"
                "3\tbuilt_in_sink.monitor\tPipeWire\n"
            ),
            "4\tbuilt_in_sink\tPipeWire\n5\tbluez_output.AM_W45\tPipeWire\n",
        )
    )
    monkeypatch.setattr(
        "realtime_voice_session.subprocess.run",
        lambda *_args, **_kwargs: types.SimpleNamespace(stdout=next(outputs)),
    )

    route = RealtimeVoiceSession._pulse_default_route()

    assert route == (
        "built_in_source",
        "built_in_sink",
        "built_in_source,usb_input",
        "bluez_output.AM_W45,built_in_sink",
    )


def test_realtime_mic_skips_unsupported_alsa_identifier(monkeypatch):
    rtv = sys.modules["realtime_voice_session"]
    import mic_input_resolve
    mic_resolve = mic_input_resolve
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
    session._audio_pair.capture = "plughw:1,0"
    session._audio_pair.capture_name = "USB PnP Sound Device"

    class _FakeSoundDevice:
        @staticmethod
        def query_devices(device, _kind=None):
            if device == "plughw:1,0":
                raise ValueError("unsupported PortAudio identifier")
            return {"name": "USB PnP Sound Device"}

    monkeypatch.setattr(rtv, "sd", _FakeSoundDevice())
    monkeypatch.setattr(
        mic_resolve, "resolve_sounddevice_capture_device_index", lambda _sd: 8
    )
    monkeypatch.setattr(
        mic_resolve,
        "capture_device_fallback_candidates",
        lambda _sd, _preferred: [8, None],
    )

    preferred, candidates = session._resolve_input_device()

    assert preferred == 8
    assert candidates == [8, None]
    assert "plughw:1,0" not in candidates


def test_resample_pcm16_mono_noop_at_same_rate():
    samples = (np.ones(100, dtype=np.int16) * 1000).tobytes()
    out = resample_pcm16_mono(samples, 24000, 24000)
    assert out == samples


def test_resample_pcm16_mono_changes_rate():
    x = np.linspace(-1, 1, num=240, dtype=np.float32)
    pcm = (x * 30000).astype(np.int16).tobytes()
    out48000 = resample_pcm16_mono(pcm, 24000, 48000)
    assert len(out48000) > len(pcm)


def test_bluetooth_duplex_keeps_software_echo_cancellation(monkeypatch):
    audio_device_resolve = __import__("audio_device_resolve")

    class _FakeAEC:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_aec_module = types.ModuleType("_aec")
    fake_aec_module.SpeexAEC = _FakeAEC
    fake_aec_module.is_available = lambda: True
    monkeypatch.setitem(sys.modules, "_aec", fake_aec_module)
    monkeypatch.setattr(
        audio_device_resolve,
        "resolve_audio_pair",
        lambda _sd: types.SimpleNamespace(
            capture=None,
            playback=None,
            capture_name="bluez_input.AM_W45",
            playback_name="bluez_output.AM_W45",
            is_combined=True,
        ),
    )

    session = RealtimeVoiceSession(
        client_secret="test",
        model="test",
        backend_base_url="http://localhost",
        device_token="test",
        on_session_end=lambda: None,
        on_error=lambda _msg: None,
        on_connected=lambda: None,
    )
    try:
        assert isinstance(session._aec, _FakeAEC)
    finally:
        session._aplay_writer.shutdown(wait=False)


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


def test_verbal_email_send_uses_authoritative_visible_fields(monkeypatch):
    rtv = sys.modules["realtime_voice_session"]
    monkeypatch.setattr(rtv, "sd", None)
    captured = {}

    def _invoke(_base, _token, *, call_id, name, arguments):
        captured.update(
            call_id=call_id,
            name=name,
            arguments=json.loads(arguments),
        )
        return json.dumps({"ok": True})

    monkeypatch.setattr(rtv, "invoke_realtime_tool_sync", _invoke)
    session = RealtimeVoiceSession(
        client_secret="ek_test",
        model="gpt-realtime-2",
        backend_base_url="http://127.0.0.1:8000",
        device_token="mbd_test",
        on_session_end=lambda: None,
        on_error=lambda _msg: None,
        on_connected=lambda: None,
    )
    session._visible_email_draft = {
        "to": ["visible@example.com"],
        "cc": [],
        "bcc": [],
        "subject": "Visible subject",
        "body": "Visible body",
    }
    ws = mock.AsyncMock()
    msg = {
        "response": {
            "output": [{
                "type": "function_call",
                "call_id": "email-call",
                "name": "send_visible_email_draft",
                "arguments": json.dumps({
                    "to": ["wrong@example.com"],
                    "subject": "Wrong",
                    "body": "Wrong",
                    "confirmed_by_user": True,
                    "confirmation_phrase": "yes send it",
                }),
            }],
        },
    }

    asyncio.run(session._handle_response_done(ws, msg))

    assert captured["name"] == "send_visible_email_draft"
    assert captured["arguments"] == {
        **session._visible_email_draft,
        "confirmed_by_user": True,
        "confirmation_phrase": "yes send it",
    }


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
    # The continuous capture path supplies 20 ms frames. A 50 ms blocking wait
    # runs off-loop so incoming assistant audio cannot be starved.
    assert 0.02 <= _MIC_QUEUE_POLL_S <= 0.05


def test_warm_session_is_held_only_after_session_update(monkeypatch):
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
        prewarm=True,
    )
    session._ws = object()

    assert session.is_held() is False
    session._session_ready.set()
    assert session.is_held() is True


def test_session_update_uses_bounded_server_vad(monkeypatch):
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
    ws = mock.AsyncMock()

    asyncio.run(session._send_session_update(ws))

    payload = json.loads(ws.send.await_args.args[0])
    transcription = payload["session"]["audio"]["input"]["transcription"]
    assert transcription["model"] == _DEFAULT_INPUT_TRANSCRIPTION_MODEL
    assert "language" not in transcription
    assert payload["session"]["audio"]["input"]["noise_reduction"] == {
        "type": "far_field",
    }
    turn_detection = payload["session"]["audio"]["input"]["turn_detection"]
    assert turn_detection == {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 500,
        "silence_duration_ms": 900,
        "create_response": True,
        "interrupt_response": True,
    }

    session._audio_pair = types.SimpleNamespace(
        capture_name="USB PnP Sound Device / USB Audio",
    )
    ws.reset_mock()
    asyncio.run(session._send_session_update(ws))
    usb_payload = json.loads(ws.send.await_args.args[0])
    assert usb_payload["session"]["audio"]["input"]["noise_reduction"] == {
        "type": "near_field",
    }


def test_live_caption_coalesces_to_latest_pending_partial(monkeypatch):
    import realtime_voice_session as rtv

    monkeypatch.setattr(rtv, "sd", None)
    scheduled = []

    class _QueuedClock:
        @staticmethod
        def schedule_once(fn, dt=0):
            scheduled.append((fn, dt))

    monkeypatch.setattr(rtv, "Clock", _QueuedClock)
    rendered = []
    session = RealtimeVoiceSession(
        client_secret="ek_test",
        model="gpt-realtime-2",
        backend_base_url="http://127.0.0.1:8000",
        device_token="mbd_test",
        on_session_end=lambda: None,
        on_error=lambda _msg: None,
        on_connected=lambda: None,
        on_user_transcript=lambda text, is_final: rendered.append((text, is_final)),
    )
    session._caption_active = True

    session._queue_live_caption("hello")
    session._queue_live_caption("hello there")

    assert len(scheduled) == 1
    fn, delay = scheduled.pop()
    assert delay <= 1.0 / 30.0
    fn(0)
    assert rendered == [("hello there", False)]


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


def test_half_duplex_barge_in_uses_aec_cleaned_voice_not_speaker_reference(monkeypatch):
    rtv = sys.modules["realtime_voice_session"]

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
    speaker = (np.ones(480, dtype=np.int16) * 5000).tobytes()
    echo_residual = (np.ones(480, dtype=np.int16) * 250).tobytes()
    user_voice = (np.ones(480, dtype=np.int16) * 2200).tobytes()
    session._aec_far_buf.extend(speaker)

    for now in (50.0, 50.02, 50.04):
        detected, *_ = session._detect_local_barge_in(
            echo_residual,
            now=now,
            echo_suppressed=True,
        )
        assert detected is False

    detected, *_ = session._detect_local_barge_in(
        user_voice,
        now=50.06,
        echo_suppressed=True,
    )
    assert detected is False
    detected, mic_rms, ref_rms, threshold, _ = session._detect_local_barge_in(
        user_voice,
        now=50.08,
        echo_suppressed=True,
    )
    assert detected is True
    assert mic_rms > threshold
    assert ref_rms > mic_rms


def test_half_duplex_barge_in_waits_for_aec_convergence(monkeypatch):
    rtv = sys.modules["realtime_voice_session"]

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
    session._half_duplex = True
    session._barge_in_armed_at = 60.9
    loud_early_echo = (np.ones(480, dtype=np.int16) * 12000).tobytes()

    for now in (60.1, 60.2, 60.3):
        detected, *_ = session._detect_local_barge_in(
            loud_early_echo,
            now=now,
            echo_suppressed=True,
        )
        assert detected is False


def test_separate_usb_mic_rejects_measured_echo_but_keeps_strong_barge_in(monkeypatch):
    rtv = sys.modules["realtime_voice_session"]

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
    session._half_duplex = True
    session._separate_usb_mic = True
    measured_echo = (np.ones(480, dtype=np.int16) * 6100).tobytes()
    strong_user_voice = (np.ones(480, dtype=np.int16) * 12000).tobytes()

    for now in (80.0, 80.02, 80.04, 80.06):
        detected, mic_rms, _, threshold, _ = session._detect_local_barge_in(
            measured_echo,
            now=now,
            echo_suppressed=True,
            near_voice_detected=False,
        )
        assert mic_rms < threshold
        assert detected is False

    for now in (80.08, 80.10):
        detected, *_ = session._detect_local_barge_in(
            strong_user_voice,
            now=now,
            echo_suppressed=True,
            near_voice_detected=True,
        )
        assert detected is False
    detected, mic_rms, _, threshold, _ = session._detect_local_barge_in(
        strong_user_voice,
        now=80.12,
        echo_suppressed=True,
        near_voice_detected=True,
    )
    assert mic_rms > threshold
    assert detected is True


def test_mic_pump_uploads_barge_preroll_before_cancel_clears_state(monkeypatch):
    rtv = sys.modules["realtime_voice_session"]
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
    frame = (np.arange(480, dtype=np.int16) * 3).tobytes()
    session._ws = mock.AsyncMock()
    session._mic_native_sr = 24000
    session._response_in_progress = True
    session._mute_mic_uplink_until = rtv.time.monotonic() + 10.0
    session._aec = mock.MagicMock()
    session._aec_near_voice_detected = True
    session._apply_aec = mock.MagicMock(return_value=frame)
    session._detect_local_barge_in = mock.MagicMock(
        return_value=(True, 3000.0, 1000.0, 1200.0, 0.1)
    )

    async def cancel_and_clear(*_args, **_kwargs):
        session._reset_local_barge_state()

    async def upload_and_stop(*_args, **_kwargs):
        session._stop.set()

    session._cancel_for_local_barge_in = mock.AsyncMock(side_effect=cancel_and_clear)
    session._upload_resampled_audio = mock.AsyncMock(side_effect=upload_and_stop)
    session._audio_q.put_nowait(frame)

    asyncio.run(session._pump_mic())

    session._upload_resampled_audio.assert_awaited_once_with(
        session._ws,
        frame,
        aec_already_applied=True,
    )


def test_live_mic_piece_discards_seconds_of_stale_audio_and_keeps_aec_aligned(
    monkeypatch,
):
    rtv = sys.modules["realtime_voice_session"]
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
    frames = [bytes([index]) * 960 for index in range(40)]
    for frame in frames:
        session._audio_q.put_nowait(frame)
    session._aec_far_buf.extend(b"x" * (40 * session._aec_frame_bytes))

    piece = session._get_live_mic_piece()

    assert piece == frames[14]
    assert session._audio_q.qsize() == 25
    assert session._audio_q_drops == 14
    assert len(session._aec_far_buf) == 26 * session._aec_frame_bytes


def test_aec_process_uses_webrtc_near_end_voice_decision(monkeypatch):
    rtv = sys.modules["realtime_voice_session"]

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

    class _FakeAEC:
        last_voice_detected = False

        @staticmethod
        def cancel(near, _far):
            return near

    class _FakeVad:
        @staticmethod
        def is_speech(frame, sample_rate):
            assert sample_rate == 8000
            assert len(frame) == 160 * 2
            return True

    session._aec = _FakeAEC()
    session._near_vad = _FakeVad()
    frame = (np.ones(480, dtype=np.int16) * 3000).tobytes()
    session._aec_far_buf.extend(frame)

    assert session._aec_process(frame) == frame
    assert session._aec_near_voice_detected is True


def test_new_playback_clears_stale_aec_reference_and_arms_barge_in(monkeypatch):
    rtv = sys.modules["realtime_voice_session"]

    monkeypatch.setattr(rtv, "sd", None)
    monkeypatch.setattr(rtv.time, "monotonic", lambda: 70.0)
    session = RealtimeVoiceSession(
        client_secret="ek_test",
        model="gpt-realtime-2",
        backend_base_url="http://127.0.0.1:8000",
        device_token="mbd_test",
        on_session_end=lambda: None,
        on_error=lambda _msg: None,
        on_connected=lambda: None,
    )
    session._aec = mock.MagicMock()
    session._aec_far_buf.extend(b"stale")
    session._aec_near_buf.extend(b"near")
    session._ensure_aplay = mock.MagicMock()
    raw = (np.ones(480, dtype=np.int16) * 1000).tobytes()

    session._play_delta(base64.b64encode(raw).decode("ascii"))

    assert session._aec_far_buf == bytearray()
    assert session._aec_near_buf == bytearray()
    assert session._barge_in_armed_at == 70.9

    proc = mock.MagicMock()
    session._aplay_proc = proc
    session._write_to_aplay(raw, session._aplay_generation)

    proc.stdin.write.assert_called_once_with(raw)
    assert bytes(session._aec_far_buf) == raw


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


def test_speaker_writer_restarts_dead_aplay_and_retries_chunk(monkeypatch):
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
    dead = mock.MagicMock()
    dead.stdin.write.side_effect = BrokenPipeError()
    healthy = mock.MagicMock()
    session._aplay_proc = dead

    def _ensure():
        if session._aplay_proc is None:
            session._aplay_proc = healthy

    monkeypatch.setattr(session, "_ensure_aplay", _ensure)
    session._write_to_aplay(b"audio", session._aplay_generation)

    healthy.stdin.write.assert_called_once_with(b"audio")
    session._aplay_writer.shutdown(wait=False, cancel_futures=True)


def test_speaker_writer_does_not_restart_after_intentional_abort(monkeypatch):
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
    proc = mock.MagicMock()

    def _aborted_write(_raw):
        session._aplay_generation += 1
        raise BrokenPipeError()

    proc.stdin.write.side_effect = _aborted_write
    session._aplay_proc = proc
    ensure = mock.MagicMock()
    monkeypatch.setattr(session, "_ensure_aplay", ensure)
    generation = session._aplay_generation

    session._write_to_aplay(b"audio", generation)

    ensure.assert_called_once()
    session._aplay_writer.shutdown(wait=False, cancel_futures=True)


def test_live_caption_starts_from_local_mic_before_server_vad(monkeypatch):
    import queue
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
    session._aec = None
    session._caption_q = queue.Queue(maxsize=4)
    session._emit_user_speech_started = mock.MagicMock()
    pcm = (np.ones(480, dtype=np.int16) * 1200).tobytes()
    ws = mock.AsyncMock()

    asyncio.run(session._upload_resampled_audio(ws, pcm))

    assert session._caption_active is True
    assert session._caption_started_locally is True
    session._emit_user_speech_started.assert_called_once()
    assert session._caption_q.get_nowait() == pcm
    session._aplay_writer.shutdown(wait=False, cancel_futures=True)

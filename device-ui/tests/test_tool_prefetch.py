"""Realtime tool prefetch registry: concurrency, single-execution, gating."""

import asyncio
import sys
import time
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Kivy is optional in CI; stub minimal clock API before importing the session.
_mod_kivy = types.ModuleType("kivy")
_mod_clock = types.ModuleType("kivy.clock")


class _Clock:
    @staticmethod
    def schedule_once(fn, dt=0):
        return None


_mod_clock.Clock = _Clock
sys.modules.setdefault("kivy", _mod_kivy)
sys.modules.setdefault("kivy.clock", _mod_clock)

import realtime_voice_session as R  # noqa: E402

_LATENCY_S = 0.20
_CAP = R._MAX_INFLIGHT_TOOL_CALLS


class _Stub:
    """Carries only the attributes the prefetch helpers touch."""

    _submit_tool_call = R.RealtimeVoiceSession._submit_tool_call
    _prefetch_safe_tools = R.RealtimeVoiceSession._prefetch_safe_tools
    _await_tool_result = R.RealtimeVoiceSession._await_tool_result

    def __init__(self):
        self._backend_base_url = "http://backend"
        self._device_token = "token"
        self._tool_executor = ThreadPoolExecutor(max_workers=4)
        self._tool_futures = {}


def _fake_invoke(calls, latency=_LATENCY_S):
    def invoke(base, token, *, call_id, name, arguments, timeout=90.0):
        calls.append((call_id, name))
        time.sleep(latency)
        return '{"ok": true}'
    return invoke


def _outputs(*pairs):
    return [
        {"type": "function_call", "call_id": c, "name": n, "arguments": "{}"}
        for c, n in pairs
    ]


def test_safe_tools_run_concurrently(monkeypatch):
    """Three read-only tools should overlap rather than sum their latencies."""
    calls = []
    monkeypatch.setattr(R, "invoke_realtime_tool_sync", _fake_invoke(calls))
    stub = _Stub()
    pairs = (
        ("c1", "show_email_draft"),
        ("c2", "navigate_device_ui"),
        ("c3", "memory_search"),
    )

    async def run():
        stub._prefetch_safe_tools(_outputs(*pairs))
        started = time.monotonic()
        for call_id, name in pairs:
            await stub._await_tool_result(call_id, name, "{}")
        return time.monotonic() - started

    elapsed = asyncio.run(run())
    assert len(calls) == 3
    # Sequential would be ~3x latency; allow generous headroom for slow CI.
    assert elapsed < _LATENCY_S * 2, f"tools serialized ({elapsed:.3f}s)"


def test_each_call_id_executes_once(monkeypatch):
    """A prefetched call must not be re-issued when the loop claims it."""
    calls = []
    monkeypatch.setattr(R, "invoke_realtime_tool_sync", _fake_invoke(calls, 0.01))
    stub = _Stub()
    outs = _outputs(("d1", "show_email_draft"))

    async def run():
        stub._prefetch_safe_tools(outs)
        stub._prefetch_safe_tools(outs)  # duplicate prefetch must be ignored
        return await stub._await_tool_result("d1", "show_email_draft", "{}")

    result = asyncio.run(run())
    assert calls == [("d1", "show_email_draft")]
    assert '"ok": true' in result


def test_mutating_tools_are_never_prefetched(monkeypatch):
    """Committing tools stay sequential so a cancelled response can gate them."""
    calls = []
    monkeypatch.setattr(R, "invoke_realtime_tool_sync", _fake_invoke(calls, 0.01))
    stub = _Stub()
    stub._prefetch_safe_tools(_outputs(
        ("m1", "send_visible_email_draft"),
        ("m2", "approve_pending_action"),
        ("m3", "memory_remember"),
        ("m4", "confirm_calendar_event"),
        ("m5", "discard_task_creation"),
    ))
    assert calls == []
    assert stub._tool_futures == {}


def test_unprefetched_tool_still_invoked(monkeypatch):
    """Tools outside the allowlist fall back to a direct invoke when awaited."""
    calls = []
    monkeypatch.setattr(R, "invoke_realtime_tool_sync", _fake_invoke(calls, 0.01))
    stub = _Stub()
    result = asyncio.run(
        stub._await_tool_result("z1", "send_visible_email_draft", "{}")
    )
    assert calls == [("z1", "send_visible_email_draft")]
    assert '"ok": true' in result


def test_registry_is_bounded(monkeypatch):
    """A long session must not accumulate futures for unclaimed calls."""
    calls = []
    monkeypatch.setattr(R, "invoke_realtime_tool_sync", _fake_invoke(calls, 0.0))
    stub = _Stub()
    stub._prefetch_safe_tools(
        _outputs(*[(f"b{i}", "memory_search") for i in range(_CAP * 2)])
    )
    assert len(stub._tool_futures) <= _CAP

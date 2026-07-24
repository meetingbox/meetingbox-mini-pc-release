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
    _maybe_early_invoke = R.RealtimeVoiceSession._maybe_early_invoke

    def __init__(self):
        self._backend_base_url = "http://backend"
        self._device_token = "token"
        self._tool_executor = ThreadPoolExecutor(max_workers=4)
        self._tool_futures = {}
        # No live session here, so the early-paint callback bails out early
        # instead of raising inside a done-callback. _PaintStub overrides this.
        self._ws = None
        self._emitted_call_ids = set()


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


def test_early_invoke_starts_safe_tool_at_arguments_done(monkeypatch):
    """A read-only tool fires immediately at arguments.done, before response.done."""
    calls = []
    monkeypatch.setattr(R, "invoke_realtime_tool_sync", _fake_invoke(calls, 0.05))
    stub = _Stub()

    started = stub._maybe_early_invoke("c1", "show_email_draft", '{"state":"drafting"}')
    assert started is True
    assert "c1" in stub._tool_futures

    # The later response.done path reuses the in-flight future, so the tool runs once.
    out = asyncio.run(stub._await_tool_result("c1", "show_email_draft", "{}"))
    assert '"ok": true' in out
    assert len(calls) == 1


def test_early_invoke_skips_mutations(monkeypatch):
    """Mutations must not fire early — they wait for a non-cancelled response.done."""
    calls = []
    monkeypatch.setattr(R, "invoke_realtime_tool_sync", _fake_invoke(calls, 0.01))
    stub = _Stub()
    for name in (
        "send_visible_email_draft",
        "approve_pending_action",
        "memory_remember",
        "confirm_calendar_event",
        "discard_task_creation",
    ):
        assert stub._maybe_early_invoke(f"m-{name}", name, "{}") is False
    assert stub._tool_futures == {}
    assert calls == []


def test_early_invoke_is_idempotent_per_call_id(monkeypatch):
    """Two arguments.done deliveries for one call_id start the tool once."""
    calls = []
    monkeypatch.setattr(R, "invoke_realtime_tool_sync", _fake_invoke(calls, 0.05))
    stub = _Stub()
    assert stub._maybe_early_invoke("c1", "navigate_device_ui", "{}") is True
    assert stub._maybe_early_invoke("c1", "navigate_device_ui", "{}") is False
    asyncio.run(stub._await_tool_result("c1", "navigate_device_ui", "{}"))
    assert len(calls) == 1


# --- early UI paint -------------------------------------------------------

class _PaintStub(_Stub):
    """Adds the emit surface so early painting can be observed."""

    _paint_early_result = R.RealtimeVoiceSession._paint_early_result

    def __init__(self):
        super().__init__()
        self._ws = object()          # session considered live
        self._emitted_call_ids = set()
        self.painted = []

    def _emit_email_draft(self, out):
        self.painted.append(("draft", out))

    def _emit_recipient_picker(self, out):
        self.painted.append(("picker", out))

    def _emit_email_view(self, out):
        self.painted.append(("view", out))


def _settle(stub, call_id, timeout=2.0):
    """Wait for the in-flight future (and its done-callback) to finish."""
    fut = stub._tool_futures.get(call_id)
    if fut is not None:
        fut.result(timeout=timeout)
    time.sleep(0.05)  # let add_done_callback run


def test_display_tool_paints_early_without_waiting_for_response_done(monkeypatch):
    calls = []
    monkeypatch.setattr(R, "invoke_realtime_tool_sync", _fake_invoke(calls, 0.02))
    stub = _PaintStub()

    assert stub._maybe_early_invoke("c1", "show_email_draft", "{}") is True
    _settle(stub, "c1")

    assert [p[0] for p in stub.painted] == ["draft"], "draft should paint on early result"
    assert "c1" in stub._emitted_call_ids


def test_early_paint_claims_call_id_so_response_done_does_not_repaint(monkeypatch):
    calls = []
    monkeypatch.setattr(R, "invoke_realtime_tool_sync", _fake_invoke(calls, 0.02))
    stub = _PaintStub()
    stub._maybe_early_invoke("c1", "show_recipient_picker", "{}")
    _settle(stub, "c1")

    # response.done consults this set; the claim must already be present.
    assert "c1" in stub._emitted_call_ids
    assert len(stub.painted) == 1
    # A second delivery of the same call_id must not paint again.
    stub._paint_early_result("c1", "show_recipient_picker", stub._tool_futures.get("c1"))
    assert len(stub.painted) == 1


def test_navigation_is_not_early_painted(monkeypatch):
    """navigate_device_ui drives the brief carousel — it must stay on response.done."""
    calls = []
    monkeypatch.setattr(R, "invoke_realtime_tool_sync", _fake_invoke(calls, 0.02))
    stub = _PaintStub()
    assert stub._maybe_early_invoke("c1", "navigate_device_ui", "{}") is True  # still prefetched
    _settle(stub, "c1")
    assert stub.painted == [], "navigation must not paint early"
    assert "c1" not in stub._emitted_call_ids


def test_mutations_never_early_paint(monkeypatch):
    calls = []
    monkeypatch.setattr(R, "invoke_realtime_tool_sync", _fake_invoke(calls, 0.01))
    stub = _PaintStub()
    for name in ("send_visible_email_draft", "approve_pending_action", "memory_remember"):
        assert stub._maybe_early_invoke(f"m-{name}", name, "{}") is False
    assert stub.painted == []
    assert stub._emitted_call_ids == set()


# --- session teardown must not block the caller ---------------------------

def test_stop_does_not_block_the_caller_when_wait_is_false(monkeypatch):
    """stop() blocks up to ~7s (3s ws close + 4s join).

    Run from the Kivy main thread that froze the UI — the window manager showed
    "python3.11 is not responding" and recording start stalled behind it.
    wait=False must return promptly and signal completion via the event.
    """
    import threading

    sess = R.RealtimeVoiceSession.__new__(R.RealtimeVoiceSession)
    sess._user_ended = False
    sess._stop = threading.Event()
    sess._audio_q = _DummyQueue()
    sess._loop = None
    sess._ws = None
    sess._async_task = None
    sess._thread = None
    slow = {"aborted": False}

    def _slow_abort():
        time.sleep(0.6)          # stand in for the real close/join cost
        slow["aborted"] = True

    sess._cancel_briefing = lambda: None
    sess._abort_aplay = _slow_abort
    sess._close_mic = lambda: None

    started = time.monotonic()
    done = sess.stop(wait=False)
    elapsed = time.monotonic() - started

    assert elapsed < 0.2, f"stop(wait=False) blocked the caller for {elapsed:.2f}s"
    assert done.wait(3.0), "teardown never signalled completion"
    assert slow["aborted"] is True
    assert sess._stop.is_set()


class _DummyQueue:
    def put_nowait(self, _item):
        return None


# --- start_recording hand-off must survive teardown cancellation ----------

def test_start_recording_callback_is_scheduled_before_websocket_close():
    """The recording hand-off must not sit behind `await ws.close()`.

    Setting _stop makes the recv loop exit, and its finally cancels every
    response-done task — including this one while it is suspended inside
    ws.close(). When the Clock.schedule_once came after the close it was never
    reached: the log showed "starting recording" and then nothing, and no
    recording ever began. Assert the scheduling happens first.
    """
    import inspect

    src = inspect.getsource(R.RealtimeVoiceSession._handle_response_done)
    block = src[src.index("if start_recording_requested:"):]
    # Strip comments: the explanatory comment in that block quotes both
    # "await ws.close()" and "Clock.schedule_once", which would otherwise be
    # matched instead of the actual statements.
    code = "\n".join(
        line for line in block.split("\n") if not line.strip().startswith("#")
    )
    sched = code.index("Clock.schedule_once")
    closed = code.index("await ws.close()")
    assert sched < closed, (
        "start_recording callback must be scheduled BEFORE ws.close(); "
        "otherwise teardown cancellation can drop the hand-off"
    )

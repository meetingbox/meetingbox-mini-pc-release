"""Screen awareness: the device mirrors the visible screen/tab to the model.

Without this the model has no idea what is displayed, so "which screen am I
on?" is unanswerable and it falls back to offering to navigate.
"""

import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Kivy is optional in CI; stub the clock before importing the session. The stub
# runs scheduled callbacks immediately so the debounce is testable.
_mod_kivy = types.ModuleType("kivy")
_mod_clock = types.ModuleType("kivy.clock")

_SCHEDULED = []


class _Timer:
    def __init__(self, fn):
        self.fn = fn
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _Clock:
    @staticmethod
    def schedule_once(fn, dt=0):
        timer = _Timer(fn)
        _SCHEDULED.append(timer)
        return timer


_mod_clock.Clock = _Clock
sys.modules.setdefault("kivy", _mod_kivy)
sys.modules.setdefault("kivy.clock", _mod_clock)

import realtime_voice_session as R  # noqa: E402


def _fire_pending():
    """Run debounce callbacks that were not cancelled."""
    pending, _SCHEDULED[:] = list(_SCHEDULED), []
    for timer in pending:
        if not timer.cancelled:
            timer.fn(0)


class _Session:
    """Just the screen-context surface of RealtimeVoiceSession."""

    set_screen_context = R.RealtimeVoiceSession.set_screen_context
    _flush_screen_context = R.RealtimeVoiceSession._flush_screen_context

    def __init__(self, live=True):
        self._screen_context = ""
        self._screen_context_sent = ""
        self._screen_context_timer = None
        self.sent = []
        if live:
            self._loop = self
            self._ws = object()
        else:
            self._loop = None
            self._ws = None

    # Stand in for the asyncio loop.
    def is_closed(self):
        return False

    async def _send_screen_context(self, ws, line, with_preamble=False):
        return None


def _capture(monkeypatch, session):
    """Drive the debounce timer and record what would go over the wire.

    Clock is patched on the module reference rather than via sys.modules: the
    suite's conftest imports real Kivy first, so a sys.modules stub would never
    take effect and the real Clock never fires without a running Kivy loop.
    """
    _SCHEDULED.clear()
    monkeypatch.setattr(R, "Clock", _Clock)

    def fake_threadsafe(coro, loop):
        coro.close()  # never awaited in this harness
        session.sent.append(session._screen_context_sent)
        return None

    monkeypatch.setattr(R.asyncio, "run_coroutine_threadsafe", fake_threadsafe)


def test_formats_screen_with_tab():
    assert R._format_screen_context("tasks", "Unplanned") == '[Screen] Tasks — "Unplanned" tab'


def test_formats_screen_without_tab():
    assert R._format_screen_context("calendar") == "[Screen] Calendar"


def test_unreported_screens_produce_nothing():
    """Setup wizard and pickers are noise, not context."""
    assert R._format_screen_context("brightness_picker") == ""
    assert R._format_screen_context("wifi_setup") == ""
    assert R._format_screen_context("") == ""


def test_tasks_unplanned_reaches_the_model(monkeypatch):
    """The exact reported case: Tasks -> Unplanned must be reported."""
    s = _Session()
    _capture(monkeypatch, s)
    s.set_screen_context("tasks", "Unplanned")
    _fire_pending()
    assert s.sent == ['[Screen] Tasks — "Unplanned" tab']


def test_rapid_navigation_is_debounced(monkeypatch):
    """Five screens in a row must not send five items."""
    s = _Session()
    _capture(monkeypatch, s)
    for name in ("home", "calendar", "emails", "meetings", "tasks"):
        s.set_screen_context(name)
    _fire_pending()
    assert s.sent == ["[Screen] Tasks"], f"expected one coalesced item, got {s.sent}"


def test_repeat_of_same_screen_sends_nothing_further(monkeypatch):
    s = _Session()
    _capture(monkeypatch, s)
    s.set_screen_context("tasks", "Today")
    _fire_pending()
    s.set_screen_context("tasks", "Today")
    _fire_pending()
    assert len(s.sent) == 1


def test_tab_change_on_same_screen_is_reported(monkeypatch):
    """Switching tabs changes what the user sees even without navigating."""
    s = _Session()
    _capture(monkeypatch, s)
    s.set_screen_context("tasks", "Today")
    _fire_pending()
    s.set_screen_context("tasks", "Unplanned")
    _fire_pending()
    assert s.sent[-1] == '[Screen] Tasks — "Unplanned" tab'
    assert len(s.sent) == 2


def test_no_live_session_retains_value_without_sending(monkeypatch):
    """With no session the value is kept for injection at the next start."""
    s = _Session(live=False)
    _capture(monkeypatch, s)
    s.set_screen_context("tasks", "Unplanned")
    _fire_pending()
    assert s.sent == []
    assert s._screen_context == '[Screen] Tasks — "Unplanned" tab'


def test_context_item_never_requests_a_response():
    """A screen change must never make the assistant speak unprompted."""
    import inspect
    src = inspect.getsource(R.RealtimeVoiceSession._send_screen_context)
    assert "response.create" not in src.replace("# Deliberately NO response.create", "")


def test_preamble_tells_model_not_to_use_a_tool():
    text = R._SCREEN_CONTEXT_PREAMBLE.lower()
    assert "never call a tool" in text

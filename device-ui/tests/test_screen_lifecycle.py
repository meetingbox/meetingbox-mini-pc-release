"""BaseScreen lifecycle guard.

Kivy's ScreenManager dispatches 'on_enter'/'on_leave' when the transition
animation completes (`screenmanager.py::TransitionBase._on_complete`), while
App.goto_screen() calls the same hooks eagerly so the incoming screen is
populated during the animation. Without the guard both fire, so every
navigation runs each screen's enter/leave work twice.

Kivy is skipped rather than stubbed here: this asserts real dispatch semantics.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

pytest.importorskip("kivy.uix.screenmanager")

from kivy.uix.screenmanager import Screen  # noqa: E402


class _Guarded(Screen):
    """Mirror of the BaseScreen guard, without BaseScreen's canvas/App deps."""

    _pending_lifecycle_skip = None

    def skip_next_lifecycle(self, event_type):
        skip = self._pending_lifecycle_skip
        if skip is None:
            skip = self._pending_lifecycle_skip = set()
        skip.add(event_type)

    def dispatch(self, event_type, *args, **kwargs):
        skip = self._pending_lifecycle_skip
        if skip and event_type in skip:
            skip.discard(event_type)
            return
        return super().dispatch(event_type, *args, **kwargs)


class _Probe(_Guarded):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.enters = 0
        self.leaves = 0
        self.touches = 0

    def on_enter(self):
        self.enters += 1

    def on_leave(self):
        self.leaves += 1

    def on_touch_down(self, touch):
        self.touches += 1
        return super().on_touch_down(touch)


class _Touch:
    def __init__(self):
        self.x = self.y = 1.0
        self.pos = (1.0, 1.0)
        self.grab_current = None

    def push(self, *a, **k):
        pass

    def pop(self, *a, **k):
        pass

    def apply_transform_2d(self, *a, **k):
        pass


def _navigate(screen, event="on_enter"):
    """One navigation as goto_screen performs it: eager call, then Kivy's."""
    screen.skip_next_lifecycle(event)
    getattr(screen, event)()
    screen.dispatch(event)


def test_guard_collapses_duplicate_enter():
    screen = _Probe(name="a")
    _navigate(screen)
    assert screen.enters == 1


def test_guard_is_one_shot_per_navigation():
    """A consumed guard must not swallow the next navigation's hook."""
    screen = _Probe(name="a")
    _navigate(screen)
    _navigate(screen)
    assert screen.enters == 2


def test_unguarded_dispatch_still_runs():
    """Kivy-only entries (no eager call) must not be suppressed."""
    screen = _Probe(name="a")
    screen.dispatch("on_enter")
    assert screen.enters == 1


def test_enter_and_leave_guard_independently():
    screen = _Probe(name="b")
    _navigate(screen, "on_leave")
    screen.dispatch("on_enter")
    assert screen.leaves == 1
    assert screen.enters == 1


def test_non_lifecycle_events_are_untouched():
    """An armed guard must never intercept touch dispatch."""
    screen = _Probe(name="c")
    screen.skip_next_lifecycle("on_enter")
    screen.dispatch("on_touch_down", _Touch())
    assert screen.touches == 1
    assert screen.enters == 0

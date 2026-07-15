from __future__ import annotations

from components.pepper_dock import DockController, PepperDock


class _FakeDock:
    def __init__(self):
        self.active = None
        self.recording_updates = []
        self.notice = None
        self.notice_dismissed = False

    def set_recording_state(self, active, paused, elapsed):
        self.recording_updates.append((active, paused, elapsed))

    def show_summary_notice(self, *, is_note, title, summary_ready=True):
        self.notice = (is_note, title, summary_ready)

    def dismiss_summary_notice(self):
        self.notice_dismissed = True

    def set_active(self, key):
        self.active = key


class _FakeHome:
    def __init__(self):
        self._shown_summary_ids = set()


class _FakeScreenManager:
    def __init__(self, home):
        self.home = home

    def get_screen(self, name):
        assert name == "home"
        return self.home


class _FakeApp:
    def __init__(self):
        self.recording_state = {"active": True, "paused": False}
        self.elapsed = 65
        self.pause_calls = 0
        self.resume_calls = 0
        self.stop_calls = 0
        self.opened_summary = None
        self.home = _FakeHome()
        self.screen_manager = _FakeScreenManager(self.home)

    def _current_recording_elapsed_seconds(self):
        return self.elapsed

    def pause_recording(self):
        self.pause_calls += 1

    def resume_recording(self):
        self.resume_calls += 1

    def stop_recording(self):
        self.stop_calls += 1

    def _voice_open_summary_review(self, meeting_id, summary):
        self.opened_summary = (meeting_id, summary)


def _controller():
    controller = object.__new__(DockController)
    controller.app = _FakeApp()
    controller.dock = _FakeDock()
    controller.state = "collapsed"
    controller._engaged = True
    controller._suppress_tap = False
    controller._last_recording_state = None
    controller._summary_meeting_id = None
    controller._summary_data = {}
    controller._consumed_summary_ids = set()
    controller._stop_breathing = lambda: None
    controller._start_breathing = lambda: None
    controller._show_surface = lambda: None
    controller._animate_expand = lambda: None
    return controller


def test_recording_capsule_uses_shared_elapsed_state():
    controller = _controller()

    controller._sync_recording_state()
    assert controller.dock.recording_updates == [(True, False, 65)]

    controller.app.recording_state["paused"] = True
    controller.app.elapsed = 66
    controller._sync_recording_state()
    assert controller.dock.recording_updates[-1] == (True, True, 66)


def test_recording_controls_use_existing_pause_resume_stop_paths():
    controller = _controller()

    controller._on_icon("record_pause")
    assert controller.app.pause_calls == 1

    controller.app.recording_state["paused"] = True
    controller._on_icon("record_pause")
    assert controller.app.resume_calls == 1

    controller._on_icon("record_stop")
    assert controller.app.stop_calls == 1


def test_collapsing_panel_does_not_stop_active_recording():
    controller = _controller()
    controller.state = "screen_open"
    controller.dock.set_active = lambda _key: None
    controller._animate_collapse = lambda: None
    controller._hide_surface = lambda: None
    controller._update_pulse = lambda: None
    controller._reanchor_voice_bar = lambda: None

    controller.collapse()

    assert controller.state == "collapsed"
    assert controller.app.stop_calls == 0
    assert controller.app.recording_state["active"] is True


def test_closed_panel_note_notice_opens_correct_summary_once():
    controller = _controller()
    controller.app.recording_state["active"] = False
    summary = {"recording_mode": "note", "title": "Project Atlas"}

    controller.notify_summary_ready("note-1", summary)
    assert controller.dock.notice == (True, "Project Atlas", True)

    controller._on_icon("summary_view")
    assert controller.app.opened_summary == ("note-1", summary)
    assert "note-1" in controller.app.home._shown_summary_ids
    assert "note-1" in controller._consumed_summary_ids
    assert controller.dock.notice_dismissed is True

    controller.state = "collapsed"
    controller.dock.notice = None
    controller.notify_summary_ready("note-1", summary)
    assert controller.dock.notice is None


def test_summary_notice_close_dismisses_without_opening_panel():
    controller = _controller()
    controller.app.recording_state["active"] = False
    summary = {"recording_mode": "meeting", "title": "Weekly review"}

    controller.notify_summary_ready("meeting-1", summary)
    controller._on_icon("summary_close")

    assert controller.app.opened_summary is None
    assert controller.dock.notice_dismissed is True
    assert "meeting-1" in controller.app.home._shown_summary_ids
    assert "meeting-1" in controller._consumed_summary_ids


def test_open_panel_keeps_existing_in_panel_notification_path():
    controller = _controller()
    controller.state = "screen_open"

    controller.notify_summary_ready(
        "meeting-2",
        {"recording_mode": "meeting", "title": "Planning"},
    )

    assert controller.dock.notice is None


def test_recording_elapsed_format_matches_dock_design():
    assert PepperDock._format_elapsed(0) == "00:00:00"
    assert PepperDock._format_elapsed(3599) == "00:59:59"
    assert PepperDock._format_elapsed(3601) == "01:00:01"

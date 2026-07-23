"""Summary-ready notification: shows app-wide, not just on Home.

Regression: the card was built inside HomeScreen and polled only while Home was
visible, so a summary finishing while the user sat on Tasks/Calendar/Emails was
silently missed until they navigated back Home. It now lives on the app's
root_layout with an app-level poll, gated by NOTIFY_BLOCKED_SCREENS.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Kivy is optional in CI; stub the clock before importing the component.
_mod_kivy = types.ModuleType("kivy")
_mod_clock = types.ModuleType("kivy.clock")


class _Clock:
    @staticmethod
    def schedule_once(fn, dt=0):
        return None

    @staticmethod
    def schedule_interval(fn, dt=0):
        return None


_mod_clock.Clock = _Clock
sys.modules.setdefault("kivy", _mod_kivy)
sys.modules.setdefault("kivy.clock", _mod_clock)

from components.summary_notification import (  # noqa: E402
    NOTIFY_BLOCKED_SCREENS,
    summary_title,
)


# --- where the notification is allowed to appear -------------------------

def test_shows_on_the_everyday_screens():
    """The whole point of the change: not just Home."""
    for screen in (
        "home", "tasks", "calendar", "emails", "meetings",
        "settings", "morning_brief", "voice_session", "meeting_detail",
    ):
        assert screen not in NOTIFY_BLOCKED_SCREENS, (
            f"{screen} should surface the summary-ready card"
        )


def test_suppressed_during_setup_flow():
    """Onboarding must not be interrupted by a summary card."""
    for screen in (
        "splash", "welcome", "room_name", "network_choice", "wifi_setup",
        "wifi_connected", "setup_progress", "pair_device",
        "meetingbox_ready", "all_set", "complete",
    ):
        assert screen in NOTIFY_BLOCKED_SCREENS, f"{screen} should suppress the card"


def test_suppressed_where_redundant_or_intrusive():
    # processing already shows this summary's progress; summary_review shows the
    # summary itself; recording and idle shouldn't be covered by a card.
    for screen in ("recording", "processing", "summary_review", "idle"):
        assert screen in NOTIFY_BLOCKED_SCREENS, f"{screen} should suppress the card"


# --- title / mode handling ------------------------------------------------

def test_meeting_title_prefers_explicit_title():
    title, is_note = summary_title({"title": "Product sync"})
    assert title == "Product sync"
    assert is_note is False


def test_falls_back_through_title_keys():
    title, _ = summary_title({"meeting_title": "Q3 planning"})
    assert title == "Q3 planning"


def test_note_mode_detected_and_defaults_to_notes():
    title, is_note = summary_title({"recording_mode": "note"})
    assert is_note is True
    assert title == "Notes"


def test_note_mode_keeps_a_real_title():
    title, is_note = summary_title({"content_type": "notes", "title": "Standup notes"})
    assert is_note is True
    assert title == "Standup notes"


def test_empty_summary_is_safe():
    title, is_note = summary_title({})
    assert title == "Your meeting"
    assert is_note is False

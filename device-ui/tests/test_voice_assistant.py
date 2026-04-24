from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voice_assistant import VoiceCommandInterpreter


def _mk() -> VoiceCommandInterpreter:
    return VoiceCommandInterpreter(
        wake_phrase="hey tony",
        start_commands=["start meeting"],
        command_timeout_seconds=6.0,
        action_cooldown_seconds=2.0,
    )


def test_combined_wake_and_command_starts_meeting():
    interpreter = _mk()
    assert interpreter.handle_transcript("hey tony start meeting", now=10.0) == "start_meeting"


def test_separate_wake_then_command_starts_meeting():
    interpreter = _mk()
    assert interpreter.handle_transcript("hey tony", now=10.0) is None
    assert interpreter.handle_transcript("start meeting", now=12.0) == "start_meeting"


def test_command_without_wake_is_ignored():
    interpreter = _mk()
    assert interpreter.handle_transcript("start meeting", now=10.0) is None


def test_fuzzy_wake_phrase_allows_minor_transcript_variation():
    interpreter = _mk()
    assert interpreter.handle_transcript("hey toni", now=10.0) is None
    assert interpreter.handle_transcript("start meeting", now=11.0) == "start_meeting"


def test_wake_phrase_times_out():
    interpreter = _mk()
    assert interpreter.handle_transcript("hey tony", now=10.0) is None
    assert interpreter.handle_transcript("start meeting", now=17.0) is None

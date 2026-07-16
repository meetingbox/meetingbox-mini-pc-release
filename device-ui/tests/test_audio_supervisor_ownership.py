import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import audio_supervisor as supervisor  # noqa: E402


def test_existing_audio_capture_pids_reads_host_proc(tmp_path, monkeypatch):
    monkeypatch.setattr(supervisor.sys, "platform", "linux")
    own = tmp_path / str(supervisor.os.getpid())
    own.mkdir()
    (own / "cmdline").write_bytes(b"python\x00audio_capture.py\x00")
    other = tmp_path / "4242"
    other.mkdir()
    (other / "cmdline").write_bytes(b"python3\x00/app/audio/audio_capture.py\x00")
    unrelated = tmp_path / "4343"
    unrelated.mkdir()
    (unrelated / "cmdline").write_bytes(b"python3\x00worker.py\x00")

    assert supervisor._existing_audio_capture_pids(tmp_path) == [4242]


def test_audio_supervisor_refuses_duplicate_capture(tmp_path, monkeypatch):
    script = tmp_path / "audio_capture.py"
    script.write_text("", encoding="utf-8")
    audio = supervisor.AudioSupervisor(script, "python")
    monkeypatch.setattr(supervisor, "_existing_audio_capture_pids", lambda: [4242])

    with pytest.raises(RuntimeError, match="existing host PIDs"):
        audio.start()

    assert audio._thread is None

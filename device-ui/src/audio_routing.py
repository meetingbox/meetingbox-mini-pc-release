"""
Runtime mic/speaker routing for the appliance UI.

Device settings PATCH stores preferences in server JSON; we mirror them into
``os.environ`` so sounddevice/aplay picks them up **without restarting** the UI.
Imported constants alone are insufficient — env must be read at use time after sync.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def get_audio_input_device_index() -> str:
    return (os.getenv("AUDIO_INPUT_DEVICE_INDEX", "") or "").strip()


def get_audio_input_device_name() -> str:
    return (os.getenv("AUDIO_INPUT_DEVICE_NAME", "") or "").strip()


def aplay_pcm_device_args() -> list[str]:
    """Extra aplay CLI args when ``MEETINGBOX_APLAY_PCM`` is set (e.g. hw:2,0)."""
    pcm = (os.getenv("MEETINGBOX_APLAY_PCM", "") or "").strip()
    return ["-D", pcm] if pcm else []


def apply_device_settings_audio_env(settings: dict | None) -> bool:
    """
    Copy audio fields from persisted device settings into the process environment.
    Returns True if any value changed (caller may reopen mic streams).
    """
    if not isinstance(settings, dict):
        return False
    prev = (
        get_audio_input_device_index(),
        get_audio_input_device_name(),
        (os.getenv("MEETINGBOX_APLAY_PCM", "") or "").strip(),
    )
    ix = settings.get("audio_input_device_index")
    if ix is not None:
        s = str(ix).strip()
        if s.lower() in ("default", "none", ""):
            os.environ["AUDIO_INPUT_DEVICE_INDEX"] = ""
        elif s.isdigit():
            os.environ["AUDIO_INPUT_DEVICE_INDEX"] = s
        else:
            os.environ["AUDIO_INPUT_DEVICE_INDEX"] = ""

    nm = settings.get("audio_input_device_name")
    if nm is not None:
        os.environ["AUDIO_INPUT_DEVICE_NAME"] = str(nm).strip()

    op = settings.get("audio_output_pcm")
    if op is not None:
        v = str(op).strip()
        if v.lower() in ("default", "", "none"):
            os.environ.pop("MEETINGBOX_APLAY_PCM", None)
        else:
            os.environ["MEETINGBOX_APLAY_PCM"] = v

    cur = (
        get_audio_input_device_index(),
        get_audio_input_device_name(),
        (os.getenv("MEETINGBOX_APLAY_PCM", "") or "").strip(),
    )
    return cur != prev


def list_portaudio_input_devices() -> list[dict[str, Any]]:
    """Enumerate PortAudio inputs (index + channel count + human name)."""
    try:
        import sounddevice as sd
    except ImportError:
        return []
    out: list[dict[str, Any]] = []
    try:
        for i, dev in enumerate(sd.query_devices()):
            if int(dev.get("max_input_channels") or 0) <= 0:
                continue
            out.append(
                {
                    "index": i,
                    "name": str(dev.get("name") or "").strip() or f"device {i}",
                    "channels": int(dev.get("max_input_channels") or 0),
                }
            )
    except Exception:
        logger.exception("list_portaudio_input_devices failed")
    return out


def list_alsa_playback_targets() -> list[dict[str, str]]:
    """
    Parse ``aplay -l`` PLAYBACK sections into ``{'pcm': 'hw:C,D', 'label': str}``.
    Falls back to [] if aplay missing or parsing fails.
    """
    exe = "aplay"
    try:
        r = subprocess.run(
            [exe, "-l"],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
        if r.returncode != 0:
            return []
        text = r.stdout or ""
    except Exception as e:
        logger.debug("aplay -l unavailable: %s", e)
        return []

    pairs: list[tuple[int, int, str]] = []
    for line in text.splitlines():
        m = re.search(r"^card\s+(\d+):.*device\s+(\d+):\s*(.+)$", line.strip())
        if not m:
            continue
        card, dev, tail = int(m.group(1)), int(m.group(2)), m.group(3).strip()
        pairs.append((card, dev, tail))

    targets: list[dict[str, str]] = []
    seen: set[str] = set()
    for card, dev, tail in pairs:
        pcm = f"hw:{card},{dev}"
        if pcm in seen:
            continue
        seen.add(pcm)
        targets.append({"pcm": pcm, "label": f"{pcm} · {tail[:80]}"})
    return targets
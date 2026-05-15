"""
Pick the PortAudio (sounddevice) capture device index for the device UI.

When AUDIO_INPUT_DEVICE_INDEX / AUDIO_INPUT_DEVICE_NAME are unset, we prefer an
external USB-class microphone so built-in laptop/tablet mics are not used by default.
"""

from __future__ import annotations

import logging
import os

from config import AUDIO_INPUT_DEVICE_INDEX, AUDIO_INPUT_DEVICE_NAME

logger = logging.getLogger(__name__)


def _usb_autopick_disabled() -> bool:
    v = (os.getenv("MEETINGBOX_AUTO_SELECT_USB_MIC") or "1").strip().lower()
    return v in ("0", "false", "no", "off")


def _usb_like_name(name: str) -> bool:
    low = (name or "").lower()
    if "usb" in low:
        return True
    # Some Class-2 listings use UAC rather than the word "USB"
    if "uac" in low:
        return True
    return False


def _match_name_substring(sd, name_sub: str) -> int | None:
    try:
        for idx, dev in enumerate(sd.query_devices()):
            if int(dev.get("max_input_channels") or 0) <= 0:
                continue
            if name_sub in ((dev.get("name") or "").lower()):
                return idx
    except Exception:
        logger.exception("Audio device enumeration failed (name=%r)", name_sub)
    return None


def _first_usb_like_capture(sd) -> int | None:
    try:
        for idx, dev in enumerate(sd.query_devices()):
            if int(dev.get("max_input_channels") or 0) <= 0:
                continue
            nm = dev.get("name") or ""
            if _usb_like_name(nm):
                logger.info("Auto-selected USB-like capture device [%s]: %s", idx, nm)
                return idx
        logger.debug("No USB-like capture device found; using PortAudio host default")
    except Exception:
        logger.exception("USB-like capture device search failed")
    return None


def resolve_sounddevice_capture_device_index(sd) -> int | None:
    """
    Return a PortAudio device index for input, or None to use the host default device.

    Precedence:
    1. AUDIO_INPUT_DEVICE_INDEX (integer)
    2. AUDIO_INPUT_DEVICE_NAME (substring match, case-insensitive)
    3. If MEETINGBOX_AUTO_SELECT_USB_MIC is not disabled: first capture device whose
       name suggests USB / UAC (see _usb_like_name)
    4. None — PortAudio default (previous behaviour when nothing matched)
    """
    if sd is None:
        return None

    idx_s = (AUDIO_INPUT_DEVICE_INDEX or "").strip()
    if idx_s.isdigit():
        return int(idx_s)

    name_sub = (AUDIO_INPUT_DEVICE_NAME or "").strip().lower()
    if name_sub:
        return _match_name_substring(sd, name_sub)

    if _usb_autopick_disabled():
        return None

    return _first_usb_like_capture(sd)

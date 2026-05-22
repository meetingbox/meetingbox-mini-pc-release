"""Best-effort host clock/timezone changes from the kiosk UI container."""

from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


def try_set_timezone(tz: str) -> bool:
    tz = (tz or "").strip()
    if not tz:
        return False
    exe = shutil.which("timedatectl")
    if not exe:
        return False
    for args in ([exe, "set-timezone", tz],):
        try:
            r = subprocess.run(
                ["sudo", "-n", *args[1:]] if shutil.which("sudo") else args,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if r.returncode == 0:
                return True
            r2 = subprocess.run(args, capture_output=True, text=True, timeout=20)
            return r2.returncode == 0
        except Exception as e:
            logger.debug("set timezone %s: %s", tz, e)
    return False


def try_set_time(iso_fragment: str) -> bool:
    """*iso_fragment* e.g. ``2026-05-21 14:35:00`` (local)."""
    s = (iso_fragment or "").strip()
    if not s:
        return False
    exe = shutil.which("timedatectl")
    if not exe:
        return False
    try:
        r = subprocess.run(
            [exe, "set-time", s],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if r.returncode == 0:
            return True
        if shutil.which("sudo"):
            r2 = subprocess.run(
                ["sudo", "-n", exe, "set-time", s],
                capture_output=True,
                text=True,
                timeout=20,
            )
            return r2.returncode == 0
    except Exception as e:
        logger.debug("set-time: %s", e)
    return False


def try_set_ntp(enabled: bool) -> bool:
    exe = shutil.which("timedatectl")
    if not exe:
        return False
    arg = "true" if enabled else "false"
    try:
        r = subprocess.run(
            [exe, "set-ntp", arg],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return r.returncode == 0
    except Exception:
        return False

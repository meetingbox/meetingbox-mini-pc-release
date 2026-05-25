"""
On-device Bluetooth control via bluetoothctl.

Mirrors the pattern of wifi_nmcli_local.py — all commands run inside the
device-ui container which has bluetoothctl installed and /run/dbus/system_bus_socket
mounted from the host, so the container's bluetoothctl talks to the host's
BlueZ daemon.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)

_BLUETOOTHCTL = None


def _bt() -> Optional[str]:
    global _BLUETOOTHCTL
    if _BLUETOOTHCTL is None:
        _BLUETOOTHCTL = shutil.which("bluetoothctl")
    return _BLUETOOTHCTL


def has_bluetoothctl() -> bool:
    return _bt() is not None


def _run(args: list[str], timeout: float = 15, allow_sudo: bool = False) -> subprocess.CompletedProcess:
    bt = _bt()
    if not bt:
        return subprocess.CompletedProcess(args, 127, "", "bluetoothctl not found")
    res = subprocess.run(
        [bt, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if res.returncode != 0 and allow_sudo and shutil.which("sudo"):
        combined = ((res.stderr or "") + (res.stdout or "")).lower()
        if any(s in combined for s in ("not authorized", "permission denied", "not permitted", "polkit")):
            res2 = subprocess.run(
                ["sudo", "-n", bt, *args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if res2.returncode == 0:
                return res2
    return res


def _run_interactive(commands: list[str], timeout: float = 12) -> str:
    """
    Feed a sequence of newline-terminated commands into bluetoothctl's stdin
    and capture stdout.  Used for scan + discovery which require an open session.
    """
    bt = _bt()
    if not bt:
        return ""
    script = "\n".join(commands) + "\n"
    try:
        res = subprocess.run(
            [bt],
            input=script,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return res.stdout or ""
    except Exception as e:
        logger.debug("bluetoothctl interactive failed: %s", e)
        return ""


def get_power_state() -> Optional[bool]:
    """Return True if Bluetooth controller is powered on, None if unknown."""
    try:
        out = _run_interactive(["show", "quit"], timeout=6)
        for line in out.splitlines():
            s = line.strip().lower()
            if s.startswith("powered:"):
                return "yes" in s
    except Exception:
        pass
    return None


def set_power(enabled: bool) -> dict:
    """Power on or off the default Bluetooth controller."""
    arg = "on" if enabled else "off"
    try:
        r = _run(["power", arg], allow_sudo=True)
        out = (r.stdout or "").lower()
        if r.returncode == 0 or f"power: {arg}" in out or "succeeded" in out:
            return {"ok": True}
        return {"ok": False, "message": (r.stderr or r.stdout or "").strip()[:400]}
    except Exception as e:
        return {"ok": False, "message": str(e)[:400]}


def list_paired_devices() -> list[dict]:
    """Return [{"mac": ..., "name": ...}] for paired devices."""
    try:
        r = _run(["devices", "Paired"], timeout=10)
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if not line.startswith("Device "):
                continue
            parts = line.split(None, 2)
            if len(parts) >= 3:
                rows.append({"mac": parts[1], "name": parts[2]})
            elif len(parts) == 2:
                rows.append({"mac": parts[1], "name": parts[1]})
        return rows
    except Exception as e:
        logger.debug("list_paired_devices: %s", e)
        return []


def scan_and_list_nearby(scan_seconds: int = 7) -> list[dict]:
    """
    Start a short scan then return all discovered + paired devices.
    Devices already in the paired list are included too so the UI can
    show a combined "known nearby" list.
    """
    # Power on first (best-effort)
    set_power(True)
    time.sleep(0.3)

    # Run: scan on → wait → scan off → devices → quit
    commands = [
        "power on",
        f"scan on",
    ]
    # Quick scan: just open the session and let BlueZ accumulate for a bit
    script = "power on\nscan on\n"
    # We rely on the interactive timeout to stop the process after scan_seconds
    bt = _bt()
    if not bt:
        return []
    try:
        subprocess.run(
            [bt],
            input=script,
            capture_output=True,
            text=True,
            timeout=scan_seconds,
        )
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        logger.debug("scan_and_list_nearby scan phase: %s", e)

    # Now collect all known devices (paired + recently discovered)
    try:
        r = _run(["devices"], timeout=8)
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if not line.startswith("Device "):
                continue
            parts = line.split(None, 2)
            if len(parts) >= 3:
                rows.append({"mac": parts[1], "name": parts[2]})
            elif len(parts) == 2:
                rows.append({"mac": parts[1], "name": parts[1]})
        return rows
    except Exception as e:
        logger.debug("scan_and_list_nearby collect: %s", e)
        return []


def pair_device(mac: str) -> dict:
    """Pair a device by MAC address."""
    mac = (mac or "").strip()
    if not mac:
        return {"ok": False, "message": "MAC address required"}
    try:
        r = _run(["pair", mac], timeout=40)
        if r.returncode == 0:
            return {"ok": True, "message": ""}
        return {"ok": False, "message": (r.stderr or r.stdout or "").strip()[:400]}
    except Exception as e:
        return {"ok": False, "message": str(e)[:400]}


def connect_device(mac: str) -> dict:
    """Connect to an already-paired device."""
    mac = (mac or "").strip()
    if not mac:
        return {"ok": False, "message": "MAC address required"}
    try:
        r = _run(["connect", mac], timeout=20)
        if r.returncode == 0:
            return {"ok": True}
        return {"ok": False, "message": (r.stderr or r.stdout or "").strip()[:400]}
    except Exception as e:
        return {"ok": False, "message": str(e)[:400]}


def remove_device(mac: str) -> dict:
    """Remove (unpair) a device."""
    mac = (mac or "").strip()
    if not mac:
        return {"ok": False, "message": "MAC address required"}
    try:
        r = _run(["remove", mac], timeout=15)
        if r.returncode == 0:
            return {"ok": True}
        return {"ok": False, "message": (r.stderr or r.stdout or "").strip()[:400]}
    except Exception as e:
        return {"ok": False, "message": str(e)[:400]}

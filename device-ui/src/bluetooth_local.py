"""
On-device Bluetooth control via bluetoothctl.

Power on/off uses the mountd helper script meetingbox-bluetooth which
runs bluetoothctl via nsenter into the host namespace.  This is the
same pattern as meetingbox-host-reboot / meetingbox-wifi-nmcli and
reliably bypasses polkit even when the container D-Bus root check differs
from the host's polkit rules.

Read-only commands (show, devices, scan) run bluetoothctl directly in
the container via the mounted /run/dbus/system_bus_socket — these don't
need polkit authorization.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)

_BLUETOOTHCTL = None
_HELPER = "/usr/local/bin/meetingbox-bluetooth"

# Cache the last explicitly-set power state for a short window so
# _load_radio_states() re-reads don't race against BlueZ propagation
# and flip the toggle back immediately after the user changed it.
_cached_power_state: Optional[bool] = None
_cached_power_time: float = 0.0
_CACHE_TTL = 12.0  # seconds


def _bt() -> Optional[str]:
    global _BLUETOOTHCTL
    if _BLUETOOTHCTL is None:
        _BLUETOOTHCTL = shutil.which("bluetoothctl")
    return _BLUETOOTHCTL


def has_bluetoothctl() -> bool:
    return _bt() is not None


def _run_helper(args: list[str], timeout: float = 12) -> subprocess.CompletedProcess:
    """Run bluetoothctl via the nsenter helper script as root (sudo -n sh helper ...)."""
    sudo = shutil.which("sudo")
    if not sudo:
        return subprocess.CompletedProcess(args, 1, "", "sudo not found")
    if not os.path.exists(_HELPER):
        return subprocess.CompletedProcess(args, 1, "", f"helper not found: {_HELPER}")
    return subprocess.run(
        [sudo, "-n", "sh", _HELPER, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


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


_RFKILL_PATHS = ["/usr/bin/rfkill", "/usr/sbin/rfkill", "/sbin/rfkill", "rfkill"]


def _find_rfkill() -> Optional[str]:
    for p in _RFKILL_PATHS:
        found = shutil.which(p)
        if found:
            return found
    return None


def _rfkill_run(args: list[str], timeout: float = 8) -> subprocess.CompletedProcess:
    """Run rfkill, trying each known path and retrying with sudo if needed."""
    exe = _find_rfkill()
    if not exe:
        return subprocess.CompletedProcess(args, 127, "", "rfkill not found")

    # Try direct first (works in privileged container)
    res = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout)
    if res.returncode == 0:
        return res

    # Retry with sudo using every known path so the sudoers entry always matches
    sudo = shutil.which("sudo")
    if sudo:
        for path in _RFKILL_PATHS:
            full = shutil.which(path)
            if not full:
                continue
            try:
                res2 = subprocess.run(
                    [sudo, "-n", full, *args],
                    capture_output=True, text=True, timeout=timeout,
                )
                if res2.returncode == 0:
                    logger.debug("rfkill via sudo %s succeeded", full)
                    return res2
            except Exception:
                continue
    return res


def get_power_state() -> Optional[bool]:
    """Return True if Bluetooth adapter is powered on, False if off, None if unknown.

    Returns the cached value for _CACHE_TTL seconds after set_power() is called
    to prevent race conditions where _load_radio_states() re-reads an outdated
    BlueZ state and flips the toggle back.

    Uses the nsenter helper for live reads so the result reflects the host adapter.
    """
    # Return cached state if set recently (avoids flip-back on quick re-entry)
    if _cached_power_state is not None and (time.time() - _cached_power_time) < _CACHE_TTL:
        logger.debug("get_power_state: using cached %s", _cached_power_state)
        return _cached_power_state

    # Primary: query via helper (nsenter → host bluetoothctl show)
    try:
        r = _run_helper(["show"], timeout=8)
        for line in (r.stdout or "").splitlines():
            s = line.strip().lower()
            if s.startswith("powered:"):
                state = "yes" in s
                logger.debug("get_power_state via helper: %s", state)
                return state
    except Exception as e:
        logger.debug("get_power_state helper failed: %s", e)

    # Fallback: direct bluetoothctl show in container (may work via D-Bus socket)
    bt = _bt()
    if bt:
        try:
            r2 = subprocess.run([bt, "show"], capture_output=True, text=True, timeout=6)
            for line in (r2.stdout or "").splitlines():
                s = line.strip().lower()
                if s.startswith("powered:"):
                    return "yes" in s
        except Exception:
            pass

    # Last resort: rfkill
    try:
        r3 = _rfkill_run(["list", "bluetooth"])
        for line in (r3.stdout or "").splitlines():
            s = line.strip().lower()
            if "soft blocked: yes" in s:
                return False
            if "soft blocked: no" in s:
                return True
    except Exception:
        pass
    return None


def _mark_power_cache(enabled: bool) -> None:
    global _cached_power_state, _cached_power_time
    _cached_power_state = enabled
    _cached_power_time = time.time()


def set_power(enabled: bool) -> dict:
    """Enable or disable Bluetooth using the nsenter helper script.

    The helper runs bluetoothctl via nsenter into the host namespace so
    polkit sees a native host process (root) — same pattern as WiFi nmcli.
    """
    arg = "on" if enabled else "off"

    # Primary: nsenter helper (runs bluetoothctl in host context as root)
    try:
        r = _run_helper(["power", arg], timeout=12)
        logger.info("set_power %s via helper: rc=%s stdout=%s stderr=%s",
                    arg, r.returncode, (r.stdout or "").strip()[:120], (r.stderr or "").strip()[:120])
        if r.returncode == 0:
            _mark_power_cache(enabled)
            return {"ok": True}
        err_msg = (r.stdout or r.stderr or "").strip()[:400]
        # sudo -n failing means sudoers entry is missing — report clearly
        if "command not found in sudoers" in err_msg.lower() or "not allowed" in err_msg.lower():
            return {"ok": False, "message": "Permission denied — rebuild container to apply sudoers update"}
        # Don't give up yet; fall through to direct sudo
        logger.warning("set_power helper rc=%s, trying direct sudo: %s", r.returncode, err_msg[:80])
    except Exception as e:
        logger.warning("set_power helper exception: %s", e)

    # Fallback: direct sudo -n bluetoothctl power on/off (works if polkit accepts root via D-Bus)
    bt = _bt()
    sudo = shutil.which("sudo")
    if bt and sudo:
        try:
            r2 = subprocess.run(
                [sudo, "-n", bt, "power", arg],
                capture_output=True, text=True, timeout=10,
            )
            sudo_err = (r2.stderr or "").lower()
            sudo_needs_pw = any(s in sudo_err for s in ("password is required", "no tty present", "sudo: a password"))
            logger.info("set_power %s direct sudo: rc=%s needs_pw=%s", arg, r2.returncode, sudo_needs_pw)
            if not sudo_needs_pw and r2.returncode == 0:
                _mark_power_cache(enabled)
                return {"ok": True}
            if not sudo_needs_pw and r2.returncode != 0:
                return {"ok": False, "message": (r2.stdout or r2.stderr or "bluetoothctl failed").strip()[:400]}
        except Exception as e:
            logger.debug("set_power direct sudo exception: %s", e)

    # Last resort: no sudo
    if bt:
        try:
            r3 = subprocess.run([bt, "power", arg], capture_output=True, text=True, timeout=10)
            if r3.returncode == 0:
                _mark_power_cache(enabled)
                return {"ok": True}
            return {"ok": False, "message": (r3.stderr or r3.stdout or "Failed").strip()[:400]}
        except Exception as e:
            return {"ok": False, "message": str(e)[:400]}

    return {"ok": False, "message": "bluetoothctl not found"}


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
    # Ensure Bluetooth is powered on before scanning (via nsenter helper)
    set_power(True)
    time.sleep(0.5)

    # Feed scan on/off into bluetoothctl stdin; we rely on the timeout to stop it
    bt = _bt()
    if not bt:
        return []
    scan_script = "scan on\n"
    try:
        subprocess.run(
            [bt],
            input=scan_script,
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

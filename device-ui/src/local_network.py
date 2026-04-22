"""
Best-effort primary IPv4 for on-device status UI (e.g. home footer).

Tries a UDP local-address probe first, then ``hostname -I`` on Linux.
"""

from __future__ import annotations

import logging
import shutil
import socket
import subprocess

logger = logging.getLogger(__name__)

_FALLBACK = "—"


def get_primary_ipv4() -> str:
    """Return a non-loopback IPv4 string, or ``"—"`` if unknown."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.3)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip and not ip.startswith("127."):
            return ip
    except OSError as e:
        logger.debug("UDP local-IP probe failed: %s", e)

    if shutil.which("hostname"):
        try:
            out = subprocess.run(
                ["hostname", "-I"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            for tok in (out.stdout or "").split():
                t = (tok or "").split("%")[0]
                if t and not t.startswith("127."):
                    return t
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            logger.debug("hostname -I failed: %s", e)

    return _FALLBACK

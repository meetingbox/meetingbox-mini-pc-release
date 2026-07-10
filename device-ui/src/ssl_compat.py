"""Shared TLS trust configuration for outbound HTTPS/WebSocket connections.

The AI features (realtime voice → ``wss://api.openai.com``, the ephemeral-token
REST call, and the device-events socket) all depend on TLS handshakes succeeding.
Two *different* antivirus behaviours can break those handshakes:

1. **HTTPS / SSL scanning (MITM).** Products like Kaspersky, ESET, Avast and
   BitDefender intercept TLS and re-sign the server certificate with their own
   root CA, which they install into the **OS system trust store**. If we verify
   against *only* the bundled ``certifi`` list (which does not contain the AV's
   root), every AI connection fails with ``CERTIFICATE_VERIFY_FAILED`` even
   though the app is otherwise running — i.e. "the AI stopped working".
2. **Stale / expired OS root.** Occasionally the OS store has an expired root
   that breaks a chain ``certifi`` would still validate.

To be robust against both, the trust context loads the **OS system store AND the
certifi bundle** as trust anchors. OpenSSL's default "trusted first" chain
building then picks whichever valid path exists, so:
  * behind an HTTPS-scanning AV → the AV's root (in the OS store) validates it;
  * with a stale OS root → certifi still validates the real chain.

Override with ``MEETINGBOX_TLS_TRUST``:
  * ``auto`` / ``both`` (default) – OS store + certifi
  * ``system``                    – OS store only
  * ``certifi``                   – certifi only (previous behaviour)
"""

from __future__ import annotations

import logging
import os
import ssl
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_CONTEXT: ssl.SSLContext | None = None
_CONTEXT_FAILED = False


def _certifi_path() -> str | None:
    try:
        import certifi

        return certifi.where()
    except Exception:  # pragma: no cover - defensive
        return None


def _build_context() -> ssl.SSLContext | None:
    trust = (os.environ.get("MEETINGBOX_TLS_TRUST", "auto").strip().lower()
             or "auto")
    certifi_path = _certifi_path()
    try:
        if trust == "certifi" and certifi_path:
            ctx = ssl.create_default_context(cafile=certifi_path)
            logger.info("TLS trust: certifi only (%s)", certifi_path)
            return ctx

        # Default/"system": start from the OS trust store. This is what makes
        # the AI work behind AV "HTTPS scanning" — the AV's interception root
        # CA lives in the OS store, not in certifi.
        ctx = ssl.create_default_context()
        if trust != "system" and certifi_path:
            # Also add certifi roots so a stale/expired OS root cannot break a
            # chain that certifi still trusts.
            try:
                ctx.load_verify_locations(cafile=certifi_path)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("TLS: could not merge certifi roots: %s", e)
        logger.info(
            "TLS trust: %s (OS store%s)",
            trust,
            "+certifi" if (trust != "system" and certifi_path) else "",
        )
        return ctx
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("TLS context build failed (%s); using default", e)
        try:
            return ssl.create_default_context()
        except Exception:
            return None


def certifi_ssl_context() -> ssl.SSLContext | None:
    """Process-wide TLS context (built once) trusting OS store + certifi."""
    global _CONTEXT, _CONTEXT_FAILED
    if _CONTEXT is None and not _CONTEXT_FAILED:
        _CONTEXT = _build_context()
        if _CONTEXT is None:
            _CONTEXT_FAILED = True
    return _CONTEXT


def httpx_verify():
    """Trust config for ``httpx`` clients.

    Returns the shared OS-store+certifi SSL context so REST calls (including the
    realtime ephemeral-token fetch) trust the same anchors as the WebSocket
    paths. Falls back to ``True`` (httpx's own certifi default) if we could not
    build a context.
    """
    ctx = certifi_ssl_context()
    return ctx if ctx is not None else True


def ws_ssl_context(url: str) -> ssl.SSLContext | None:
    """Return a certifi-backed context for ``wss://`` URLs, else ``None``.

    Plain ``ws://`` needs no TLS, so we return ``None`` (passing a context for a
    non-TLS URL makes ``websockets`` raise).
    """
    try:
        scheme = urlparse(url).scheme.lower()
    except Exception:
        scheme = ""
    if scheme != "wss":
        return None
    return certifi_ssl_context()

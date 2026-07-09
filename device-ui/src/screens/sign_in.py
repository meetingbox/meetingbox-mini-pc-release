"""
Desktop onboarding - wait for Dashboard sign-in.

On Windows the Dashboard app is the single sign-in surface. When the user signs
in there, the Dashboard writes the user JWT to a shared session file; this screen
polls for it and then self-pairs the companion (mints + persists its device
token) with no companion-side Google flow. Shown after the splash when no device
auth token is stored yet, and again if the device is de-authed.
"""

from __future__ import annotations

import logging
import socket
from pathlib import Path

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from async_helper import run_async
from config import ASSETS_DIR, COLORS, FONT_SIZES, read_dashboard_session_jwt
from platform_compat import bring_app_to_foreground
from screens.base_screen import BaseScreen
from setup_finalize import post_setup_complete_safe, write_local_setup_complete_marker

logger = logging.getLogger(__name__)

WELCOME_DIR = ASSETS_DIR / "welcome"
LOGO_PATH = str(WELCOME_DIR / "LOGO.png")

# How often to look for the Dashboard's shared session while waiting.
_SESSION_POLL_INTERVAL = 2.0


def _default_device_name() -> str:
    """A sensible auto room name for a desktop install (renameable later)."""
    try:
        host = (socket.gethostname() or "").split(".")[0].strip()
    except Exception:
        host = ""
    return f"Nexa AI - {host}" if host else "Nexa AI Desktop"


class SignInScreen(BaseScreen):
    """Waits for the Dashboard app's sign-in, then self-pairs the companion."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._busy = False
        self._poll = None
        self._build_ui()

    def _build_ui(self):
        sv = self.suv
        sf = self.suf
        root = BoxLayout(
            orientation="vertical",
            padding=[sv(36), sv(40), sv(36), sv(36)],
            spacing=sv(14),
            size_hint=(1, 1),
        )
        self.make_dark_bg(root)

        root.add_widget(Widget(size_hint=(1, 0.2)))

        if Path(LOGO_PATH).exists():
            logo = Image(source=LOGO_PATH, size_hint=(1, None), height=sv(72), fit_mode="contain")
            root.add_widget(logo)
        else:
            logo = Label(
                text="Nexa AI",
                font_size=sf(FONT_SIZES["huge"]),
                bold=True,
                color=COLORS["white"],
                size_hint=(1, None),
                height=sv(56),
            )
            root.add_widget(logo)

        title = Label(
            text="Sign in from the Nexa AI Dashboard",
            font_size=sf(FONT_SIZES["title"]),
            bold=True,
            color=COLORS["white"],
            halign="center",
            valign="middle",
            size_hint=(1, None),
            height=sv(44),
        )
        title.bind(size=title.setter("text_size"))
        root.add_widget(title)

        subtitle = Label(
            text=(
                "Open the Nexa AI Dashboard and sign in with Google. "
                "This companion connects automatically once you do."
            ),
            font_size=sf(FONT_SIZES["body"]),
            color=COLORS["gray_300"],
            halign="center",
            valign="top",
            size_hint=(1, None),
            height=sv(54),
        )
        subtitle.bind(size=subtitle.setter("text_size"))
        root.add_widget(subtitle)

        root.add_widget(Widget(size_hint=(1, None), height=dp(8)))

        self._status = Label(
            text="Waiting for you to sign in on the Dashboard...",
            font_size=sf(FONT_SIZES["small"]),
            color=COLORS["gray_400"],
            halign="center",
            valign="middle",
            size_hint=(1, None),
            height=sv(40),
        )
        self._status.bind(size=self._status.setter("text_size"))
        root.add_widget(self._status)

        root.add_widget(Widget(size_hint=(1, 1)))

        self.add_widget(root)

    # ------------------------------------------------------------------
    def on_enter(self):
        self._set_status("Waiting for you to sign in on the Dashboard...")
        self._start_poll()

    def on_leave(self):
        self._stop_poll()

    def _start_poll(self):
        self._stop_poll()
        # Check immediately, then on an interval.
        self._check_session(0)
        self._poll = Clock.schedule_interval(self._check_session, _SESSION_POLL_INTERVAL)

    def _stop_poll(self):
        if self._poll is not None:
            try:
                self._poll.cancel()
            except Exception:
                pass
            self._poll = None

    def _set_status(self, text: str, error: bool = False):
        if not getattr(self, "_status", None):
            return
        self._status.text = text or ""
        self._status.color = (1.0, 0.42, 0.38, 1) if error else COLORS["gray_400"]

    def _check_session(self, _dt):
        """Poll for the Dashboard's shared JWT; when present, self-pair once."""
        if self._busy:
            return
        jwt = read_dashboard_session_jwt()
        if not jwt:
            return
        self._busy = True
        self._stop_poll()
        self._set_status("Signing you in...")
        device_name = (getattr(self.app, "device_name", "") or "").strip() or _default_device_name()
        self.app.device_name = device_name

        async def _flow():
            try:
                data = await self.backend.finalize_google_signin(jwt, device_name)
            except Exception as exc:
                logger.exception("Self-pair from Dashboard session failed")
                Clock.schedule_once(
                    lambda _dt, m=str(exc): self._retry(
                        "Could not connect: " + (m or "unknown error")
                    ),
                    0,
                )
                return
            owner = ((data or {}).get("owner_email") or "").strip()
            self.app.paired_owner_email = owner
            try:
                await post_setup_complete_safe(self.backend, "", "dashboard_session_v1")
                write_local_setup_complete_marker(
                    "", device_name, "dashboard_session_v1",
                    extra={"owner_email": owner} if owner else None,
                )
            except Exception:
                logger.debug("post-setup marker failed", exc_info=True)
            Clock.schedule_once(lambda _dt: self._succeed(), 0)

        if run_async(_flow()) is None:
            self._retry("App is still starting up. Retrying...")

    def _retry(self, message: str):
        """A pairing attempt failed; show why and resume polling."""
        self._busy = False
        self._set_status(message, error=True)
        self._start_poll()

    def _succeed(self):
        self._busy = False
        poll = getattr(self.app, "_setup_poll", None)
        if poll:
            try:
                poll.cancel()
            except Exception:
                pass
            self.app._setup_poll = None
        # Onboarding is handled by the Dashboard, so go straight to home once
        # paired instead of running the companion's capabilities/ready tour.
        # NoTransition: avoid a visible slide of the full home window before the
        # floating dock engages (desktop companion).
        self._returned_to_app("You're connected.")
        self.goto("home", transition="none")

    def _returned_to_app(self, status: str = ""):
        try:
            bring_app_to_foreground()
        except Exception:
            pass
        if status:
            self._set_status(status)

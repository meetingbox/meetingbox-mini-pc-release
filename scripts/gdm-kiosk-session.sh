#!/usr/bin/env bash
# GDM X session: no GNOME Shell — black screen, tiny Openbox, then Docker MeetingBox UI.
# Installed as /usr/local/bin/meetingbox-gdm-kiosk-session by install-gdm-kiosk-session.sh
#
# Keep this process running until logout, or GDM will end the session.

set +e

RELEASE="${MEETINGBOX_RELEASE:-$HOME/meetingbox-mini-pc-release}"
if [[ -f /etc/meetingbox/release ]]; then
  RELEASE=$(tr -d '\n' </etc/meetingbox/release)
fi
RELEASE=$(cd "$RELEASE" 2>/dev/null && pwd || echo "$RELEASE")

export PATH="/usr/sbin:/usr/bin:/usr/local/bin:$PATH"

# Lock panel mode + rotation (DSI / HDMI) — see /etc/meetingbox/panel-xrandr.env
if [[ -x /usr/local/bin/meetingbox-apply-kiosk-display-orientation ]]; then
  /usr/local/bin/meetingbox-apply-kiosk-display-orientation
elif [[ -f "$RELEASE/scripts/apply-kiosk-display-orientation.sh" ]]; then
  bash "$RELEASE/scripts/apply-kiosk-display-orientation.sh"
fi

# Solid black while Docker / UI start (no Ubuntu wallpaper or dock).
xsetroot -solid '#000000' 2>/dev/null || true

# Minimal WM so SDL/Kivy fullscreen behaves; ~2 MB RAM vs full GNOME.
if command -v openbox >/dev/null 2>&1; then
  openbox >/dev/null 2>&1 &
  sleep 0.2
fi

# meetingbox-appliance.service is the single owner of Docker Compose startup.
# This session only provides X11 + Openbox, avoiding duplicate compose calls
# and Xauthority copy races during boot.
logger -t meetingbox-kiosk "X11/Openbox session ready; systemd owns appliance startup"

# Hold the X session open (required by GDM).
exec tail -f /dev/null

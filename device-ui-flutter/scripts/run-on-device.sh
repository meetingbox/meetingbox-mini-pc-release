#!/usr/bin/env bash
# Launch the built Flutter device UI on the mini PC's active GNOME Wayland
# session. Run on the device (via SSH). Joins the user graphical session so the
# window appears on the physical panel.
set -euo pipefail

UID_NUM=1000
export XDG_RUNTIME_DIR="/run/user/${UID_NUM}"
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${UID_NUM}/bus"
export WAYLAND_DISPLAY="wayland-0"
export DISPLAY=":0"

BUNDLE="/home/meetingbox/meetingbox-mini-pc-release/device-ui-flutter/build/linux/x64/release/bundle"
BIN="${BUNDLE}/meetingbox_device_ui"

if [[ ! -x "$BIN" ]]; then
  echo "Binary not found: $BIN" >&2
  exit 1
fi

# Stop any previous instance.
systemctl --user stop meetingbox-flutter-ui.service 2>/dev/null || true
systemctl --user reset-failed meetingbox-flutter-ui.service 2>/dev/null || true

cd "$BUNDLE"
exec systemd-run --user --collect \
  --unit=meetingbox-flutter-ui \
  --setenv=XDG_RUNTIME_DIR="/run/user/${UID_NUM}" \
  --setenv=WAYLAND_DISPLAY="wayland-0" \
  --setenv=DISPLAY=":0" \
  --setenv=GDK_BACKEND="wayland,x11" \
  --working-directory="$BUNDLE" \
  "$BIN"

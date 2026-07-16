#!/usr/bin/env bash
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 2
fi

STATE_DIR="/var/lib/meetingbox/bluetooth"
ROLLBACK_DIR="$STATE_DIR/rollback"
AUDIO_USER="${MEETINGBOX_AUDIO_USER:-meetingbox}"
if [[ -r /etc/default/meetingbox-amw45 ]]; then
  # shellcheck disable=SC1091
  source /etc/default/meetingbox-amw45
  AUDIO_USER="${MEETINGBOX_AUDIO_USER:-$AUDIO_USER}"
fi

systemctl disable --now meetingbox-amw45.service 2>/dev/null || true
rm -f \
  /etc/systemd/system/meetingbox-amw45.service \
  /usr/local/sbin/meetingbox-amw45-route \
  /usr/local/sbin/meetingbox-amw45-watch \
  /etc/wireplumber/bluetooth.lua.d/51-meetingbox-amw45.lua \
  /etc/default/meetingbox-amw45 \
  /run/meetingbox-amw45-ready
systemctl daemon-reload

rollback_package="$(
  find "$ROLLBACK_DIR" -maxdepth 1 -type f \
    -name 'libspa-0.2-bluetooth_*.deb' | sort | tail -n 1
)"
if [[ -z "$rollback_package" ]]; then
  echo "Rollback package not found in $ROLLBACK_DIR" >&2
  exit 1
fi
dpkg -i "$rollback_package"

if [[ -f "$STATE_DIR/legacy-wireplumber.lua" ]]; then
  legacy_dir="/home/$AUDIO_USER/.config/wireplumber/bluetooth.lua.d"
  install -d -o "$AUDIO_USER" -g "$AUDIO_USER" -m 0755 "$legacy_dir"
  install -o "$AUDIO_USER" -g "$AUDIO_USER" -m 0644 \
    "$STATE_DIR/legacy-wireplumber.lua" "$legacy_dir/51-enable-hfp-hsp.lua"
fi

audio_uid="$(id -u "$AUDIO_USER")"
runuser -u "$AUDIO_USER" -- env \
  XDG_RUNTIME_DIR="/run/user/$audio_uid" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$audio_uid/bus" \
  systemctl --user restart wireplumber pipewire pipewire-pulse

echo "AM-W45 compatibility rolled back to $(basename "$rollback_package")"

#!/usr/bin/env bash
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "Run as root: sudo $0 /path/to/libspa-0.2-bluetooth_*.deb [MAC]" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_PATH="${1:-}"
DEVICE_MAC="${2:-}"
AUDIO_USER="${MEETINGBOX_AUDIO_USER:-meetingbox}"
STATE_DIR="/var/lib/meetingbox/bluetooth"
ROLLBACK_DIR="$STATE_DIR/rollback"

[[ -f "$PACKAGE_PATH" ]] || {
  echo "Patched libspa-0.2-bluetooth package is required" >&2
  exit 2
}
package_name="$(dpkg-deb -f "$PACKAGE_PATH" Package)"
[[ "$package_name" == "libspa-0.2-bluetooth" ]] || {
  echo "Unexpected package: $package_name" >&2
  exit 2
}
id "$AUDIO_USER" >/dev/null

install -d -m 0755 "$STATE_DIR" "$ROLLBACK_DIR"
current_version="$(dpkg-query -W -f='${Version}' libspa-0.2-bluetooth)"
if ! compgen -G "$ROLLBACK_DIR/libspa-0.2-bluetooth_*.deb" >/dev/null; then
  (
    cd "$ROLLBACK_DIR"
    apt-get download "libspa-0.2-bluetooth=$current_version"
  )
fi

sha256sum "$PACKAGE_PATH" >"$STATE_DIR/installed-package.sha256"
printf 'previous_version=%q\ninstalled_from=%q\n' \
  "$current_version" "$(readlink -f "$PACKAGE_PATH")" >"$STATE_DIR/install.state"

install -D -m 0644 "$ROOT_DIR/51-meetingbox-amw45.lua" \
  /etc/wireplumber/bluetooth.lua.d/51-meetingbox-amw45.lua
install -D -m 0755 "$ROOT_DIR/meetingbox-amw45-route" \
  /usr/local/sbin/meetingbox-amw45-route
install -D -m 0755 "$ROOT_DIR/meetingbox-amw45-watch" \
  /usr/local/sbin/meetingbox-amw45-watch
install -D -m 0644 "$ROOT_DIR/meetingbox-amw45.service" \
  /etc/systemd/system/meetingbox-amw45.service

if [[ -z "$DEVICE_MAC" ]]; then
  DEVICE_MAC="$(
    bluetoothctl devices Paired |
      awk '$1 == "Device" { mac=$2; $1=$2=""; sub(/^  */, ""); if ($0 == "AM-W45") print mac }' |
      head -n 1
  )"
fi
cat >/etc/default/meetingbox-amw45 <<EOF
MEETINGBOX_AUDIO_USER=$AUDIO_USER
MEETINGBOX_BLUETOOTH_NAME=AM-W45
MEETINGBOX_BLUETOOTH_MAC=$DEVICE_MAC
MEETINGBOX_BT_CONNECT_ATTEMPTS=6
MEETINGBOX_BT_CHECK_INTERVAL=20
EOF

dpkg -i "$PACKAGE_PATH"

audio_uid="$(id -u "$AUDIO_USER")"
runuser -u "$AUDIO_USER" -- env \
  XDG_RUNTIME_DIR="/run/user/$audio_uid" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$audio_uid/bus" \
  systemctl --user restart wireplumber pipewire pipewire-pulse

systemctl daemon-reload
systemctl enable --now meetingbox-amw45.service
systemctl --no-pager --full status meetingbox-amw45.service
echo "AM-W45 support installed. Roll back with rollback-amw45-support.sh"

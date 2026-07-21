#!/usr/bin/env bash
# Configure the mini-PC as a deterministic MeetingBox appliance.
# Usage:
#   sudo bash scripts/install-production-hardening.sh [apply|restore]

set -euo pipefail

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Run as root: sudo $0 [apply|restore]" >&2
  exit 2
fi

ACTION="${1:-apply}"
STATE_DIR="/var/lib/meetingbox/production-hardening"
UNIT_STATE="$STATE_DIR/unit-state"
APT_AUTO="/etc/apt/apt.conf.d/20auto-upgrades"
APPORT_DEFAULT="/etc/default/apport"
RELEASE_UPGRADES="/etc/update-manager/release-upgrades"
AUDIO_USER="${MEETINGBOX_AUDIO_USER:-${SUDO_USER:-meetingbox}}"
APPLIANCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ENV="$APPLIANCE_DIR/.env"

UNITS=(
  apt-daily.service
  apt-daily.timer
  apt-daily-upgrade.service
  apt-daily-upgrade.timer
  unattended-upgrades.service
  packagekit.service
  packagekit-offline-update.service
  fwupd-refresh.service
  fwupd-refresh.timer
  snapd.service
  snapd.socket
  snapd.seeded.service
  snapd.autoimport.service
  apport.service
  whoopsie.service
  whoopsie.path
  bluetooth.service
  meetingbox-amw45.service
  meetingbox-docker-audio.service
)

unit_exists() {
  systemctl cat "$1" >/dev/null 2>&1
}

backup_file() {
  local path="$1" name
  name="${path#/}"
  name="${name//\//__}"
  if [[ -e "$path" && ! -e "$STATE_DIR/files/$name" ]]; then
    cp -a "$path" "$STATE_DIR/files/$name"
  fi
}

restore_file() {
  local path="$1" name
  name="${path#/}"
  name="${name//\//__}"
  if [[ -e "$STATE_DIR/files/$name" ]]; then
    cp -a "$STATE_DIR/files/$name" "$path"
  else
    rm -f "$path"
  fi
}

restore_if_backed_up() {
  local path="$1" name
  name="${path#/}"
  name="${name//\//__}"
  if [[ -e "$STATE_DIR/files/$name" ]]; then
    cp -a "$STATE_DIR/files/$name" "$path"
  fi
}

record_unit_states() {
  : >"$UNIT_STATE"
  local unit state
  for unit in "${UNITS[@]}"; do
    unit_exists "$unit" || continue
    state="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
    printf '%s\t%s\n' "$unit" "${state:-disabled}" >>"$UNIT_STATE"
  done
}

restore_unit_states() {
  [[ -r "$UNIT_STATE" ]] || return 0
  local unit state
  while IFS=$'\t' read -r unit state; do
    systemctl unmask "$unit" >/dev/null 2>&1 || true
    case "$state" in
      enabled|enabled-runtime|linked|linked-runtime|alias)
        systemctl enable "$unit" >/dev/null 2>&1 || true
        ;;
      masked|masked-runtime)
        systemctl mask "$unit" >/dev/null 2>&1 || true
        ;;
      *)
        systemctl disable "$unit" >/dev/null 2>&1 || true
        ;;
    esac
  done <"$UNIT_STATE"
}

write_autostart_override() {
  local name="$1" target
  target="/home/$AUDIO_USER/.config/autostart/$name"
  install -d -o "$AUDIO_USER" -g "$AUDIO_USER" -m 0755 "$(dirname "$target")"
  cat >"$target" <<EOF
[Desktop Entry]
Type=Application
Name=Disabled on MeetingBox appliance
Hidden=true
EOF
  chown "$AUDIO_USER:$AUDIO_USER" "$target"
  chmod 0644 "$target"
}

set_env_value() {
  local key="$1" value="$2"
  [[ -f "$APP_ENV" ]] || return 0
  if grep -qE "^[[:space:]]*${key}=" "$APP_ENV"; then
    sed -i "s|^[[:space:]]*${key}=.*|${key}=${value}|" "$APP_ENV"
  else
    printf '\n%s=%s\n' "$key" "$value" >>"$APP_ENV"
  fi
}

restore_stock_bluetooth_audio() {
  local rollback_dir="/var/lib/meetingbox/bluetooth/rollback"
  local rollback_package=""
  if [[ -d "$rollback_dir" ]]; then
    rollback_package="$(
      compgen -G "$rollback_dir/libspa-0.2-bluetooth_*.deb" |
        sort | tail -n 1 || true
    )"
  fi
  if [[ -n "$rollback_package" ]]; then
    dpkg -i "$rollback_package"
  else
    echo "No saved stock Bluetooth package found; leaving the installed package unchanged." >&2
  fi
}

apply_hardening() {
  install -d -m 0755 "$STATE_DIR/files"
  if [[ ! -e "$STATE_DIR/applied" ]]; then
    record_unit_states
    backup_file "$APT_AUTO"
    backup_file "$APPORT_DEFAULT"
    backup_file "$RELEASE_UPGRADES"
    backup_file "$APP_ENV"
    # Restore the stock PipeWire library before disabling Bluetooth. The old
    # rollback helper is intentionally not used because it re-enables legacy HFP.
    systemctl disable --now meetingbox-amw45.service >/dev/null 2>&1 || true
    restore_stock_bluetooth_audio
  fi

  systemctl disable --now meetingbox-amw45.service >/dev/null 2>&1 || true
  rm -f \
    /etc/systemd/system/meetingbox-amw45.service \
    /usr/local/sbin/meetingbox-amw45-route \
    /usr/local/sbin/meetingbox-amw45-watch \
    /etc/wireplumber/bluetooth.lua.d/51-meetingbox-amw45.lua \
    "/home/$AUDIO_USER/.config/wireplumber/bluetooth.lua.d/51-enable-hfp-hsp.lua" \
    /etc/default/meetingbox-amw45 \
    /run/meetingbox-amw45-ready
  ln -sfn /dev/null /etc/systemd/system/meetingbox-amw45.service
  ln -sfn /dev/null /etc/systemd/system/meetingbox-docker-audio.service

  cat >"$APT_AUTO" <<'EOF'
APT::Periodic::Enable "0";
APT::Periodic::Update-Package-Lists "0";
APT::Periodic::Download-Upgradeable-Packages "0";
APT::Periodic::AutocleanInterval "0";
APT::Periodic::Unattended-Upgrade "0";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

  set_env_value MEETINGBOX_BLUETOOTH_ENABLED 0
  set_env_value MEETINGBOX_USB_MIC_STRICT 0

  install -d -m 0755 "$(dirname "$APPORT_DEFAULT")"
  printf 'enabled=0\n' >"$APPORT_DEFAULT"
  if [[ -e "$RELEASE_UPGRADES" ]]; then
    if grep -q '^Prompt=' "$RELEASE_UPGRADES"; then
      sed -i 's/^Prompt=.*/Prompt=never/' "$RELEASE_UPGRADES"
    else
      printf '\nPrompt=never\n' >>"$RELEASE_UPGRADES"
    fi
  fi

  local unit
  for unit in "${UNITS[@]}"; do
    unit_exists "$unit" || continue
    systemctl disable --now "$unit" >/dev/null 2>&1 || true
    systemctl mask "$unit" >/dev/null 2>&1 || true
  done

  if command -v rfkill >/dev/null 2>&1; then
    rfkill block bluetooth || true
  fi

  write_autostart_override update-notifier.desktop
  write_autostart_override update-notifier-release.desktop
  write_autostart_override snap-userd-autostart.desktop

  # Old crash reports cause Ubuntu to reopen the popup on every login.
  if [[ -d /var/crash ]]; then
    find /var/crash -mindepth 1 -maxdepth 1 -type f -delete
  fi

  systemctl daemon-reload
  systemctl reset-failed meetingbox-amw45.service bluetooth.service >/dev/null 2>&1 || true
  date --iso-8601=seconds >"$STATE_DIR/applied"
  echo "MeetingBox production hardening applied."
}

restore_hardening() {
  restore_file "$APT_AUTO"
  restore_file "$APPORT_DEFAULT"
  restore_file "$RELEASE_UPGRADES"
  restore_if_backed_up "$APP_ENV"
  rm -f \
    "/home/$AUDIO_USER/.config/autostart/update-notifier.desktop" \
    "/home/$AUDIO_USER/.config/autostart/update-notifier-release.desktop" \
    "/home/$AUDIO_USER/.config/autostart/snap-userd-autostart.desktop"
  restore_unit_states
  if command -v rfkill >/dev/null 2>&1; then
    rfkill unblock bluetooth || true
  fi
  systemctl daemon-reload
  rm -f "$STATE_DIR/applied"
  echo "MeetingBox production hardening restored to its recorded unit state."
  echo "Reinstall AM-W45 support separately if Bluetooth audio is required again."
}

case "$ACTION" in
  apply) apply_hardening ;;
  restore) restore_hardening ;;
  *)
    echo "Usage: sudo $0 [apply|restore]" >&2
    exit 2
    ;;
esac

#!/usr/bin/env bash
# Run OS updates only during an attended MeetingBox maintenance window.

set -euo pipefail

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 2
fi

if [[ "${MEETINGBOX_MAINTENANCE_CONFIRM:-}" != "YES" ]]; then
  cat >&2 <<'EOF'
Automatic OS updates are disabled on this appliance.
To run an attended update, use:
  sudo MEETINGBOX_MAINTENANCE_CONFIRM=YES bash scripts/meetingbox-maintenance-update.sh
EOF
  exit 2
fi

echo "Stopping MeetingBox before package maintenance..."
systemctl stop meetingbox-appliance.service >/dev/null 2>&1 || true

cleanup() {
  echo "Reapplying appliance hardening and restarting MeetingBox..."
  bash "$(dirname "$0")/install-production-hardening.sh" apply
  systemctl start meetingbox-appliance.service
}
trap cleanup EXIT

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
apt-get autoremove -y
apt-get clean

echo "Package maintenance finished. Reboot manually after validation if required."

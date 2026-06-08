#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${HOME}/meetingbox-mini-pc-release/device-ui-flutter/device-ui-flutter.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
export FULLSCREEN="${FULLSCREEN:-1}"

cd "${HOME}/meetingbox-mini-pc-release/device-ui-flutter/build/linux/x64/release/bundle"
exec ./meetingbox_device_ui

#!/usr/bin/env bash
# Apply panel mode + rotation once X is up (GDM kiosk session).
# Config: /etc/meetingbox/panel-xrandr.env (installed from panel-xrandr.env.example).
# Disable: MEETINGBOX_SKIP_PANEL_XRANDR=1 in that file.

set +e

[[ -n "${DISPLAY:-}" ]] || export DISPLAY=:0

ENV_FILE="${MEETINGBOX_PANEL_XRANDR_ENV:-/etc/meetingbox/panel-xrandr.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

if [[ "${MEETINGBOX_SKIP_PANEL_XRANDR:-0}" == "1" ]]; then
  exit 0
fi

command -v xrandr >/dev/null 2>&1 || exit 0

OUT="${MEETINGBOX_PANEL_OUTPUT:-DSI-1}"
MODE="${MEETINGBOX_PANEL_MODE:-800x1280}"
ROT="${MEETINGBOX_PANEL_ROTATE:-right}"

# One shot: mode + rotation (matches common DSI portrait panels used as landscape).
if xrandr --output "$OUT" --mode "$MODE" --rotate "$ROT" 2>/dev/null; then
  logger -t meetingbox-kiosk "xrandr ok: --output $OUT --mode $MODE --rotate $ROT"
  exit 0
fi
# Fallback: rotation only (mode may already be set by firmware).
if xrandr --output "$OUT" --rotate "$ROT" 2>/dev/null; then
  logger -t meetingbox-kiosk "xrandr ok: --output $OUT --rotate $ROT (mode fallback)"
  exit 0
fi
logger -t meetingbox-kiosk "xrandr: could not apply orientation for output '$OUT' (edit $ENV_FILE)"
exit 0

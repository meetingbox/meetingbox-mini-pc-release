#!/usr/bin/env bash
# Apply panel mode + rotation once X is up (GDM kiosk session).
# Config: /etc/meetingbox/panel-xrandr.env (installed from panel-xrandr.env.example).
# Disable: MEETINGBOX_SKIP_PANEL_XRANDR=1 in that file.
#
# After rotation, map touchscreen devices to the same output (otherwise touch stays
# in the panel's native coordinates). Requires: xinput (apt install xinput).

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

XR_OK=0
# One shot: mode + rotation (matches common DSI portrait panels used as landscape).
if xrandr --output "$OUT" --mode "$MODE" --rotate "$ROT" 2>/dev/null; then
  logger -t meetingbox-kiosk "xrandr ok: --output $OUT --mode $MODE --rotate $ROT"
  XR_OK=1
elif xrandr --output "$OUT" --rotate "$ROT" 2>/dev/null; then
  logger -t meetingbox-kiosk "xrandr ok: --output $OUT --rotate $ROT (mode fallback)"
  XR_OK=1
else
  logger -t meetingbox-kiosk "xrandr: could not apply orientation for output '$OUT' (edit $ENV_FILE)"
fi

# Map touchscreen XInput devices to the same output as the panel (critical after --rotate).
_map_touch_to_output() {
  if [[ "${MEETINGBOX_MAP_TOUCH_TO_OUTPUT:-1}" != "1" ]]; then
    return 0
  fi
  command -v xinput >/dev/null 2>&1 || {
    logger -t meetingbox-kiosk "touch: install xinput (apt install xinput) to align touch with display"
    return 0
  }
  local devname mapped=0
  # Primary: common touchscreen vendor / product name substrings
  while IFS= read -r devname; do
    [[ -z "$devname" ]] && continue
    case "$devname" in
      'Virtual core pointer'|'Virtual core XTEST pointer'|'Virtual core keyboard') continue ;;
    esac
    if xinput map-to-output "$devname" "$OUT" 2>/dev/null; then
      logger -t meetingbox-kiosk "xinput: map-to-output '$devname' -> $OUT"
      mapped=1
    fi
  done < <(xinput list --name-only 2>/dev/null | grep -iE 'touch|touchscreen|goodix|ilitek|elan|stylus|digitizer|wacom|atmel|zeafte|hid|finger' | grep -viE 'keyboard|video bus' || true)

  # Optional explicit names from `xinput list --name-only`. One device: MEETINGBOX_TOUCH_XINPUT_DEVICE='ILITEK ILITEK-TP'
  # Multiple: MEETINGBOX_TOUCH_XINPUT_NAMES='first device|second device' (pipe-separated).
  if [[ -n "${MEETINGBOX_TOUCH_XINPUT_DEVICE:-}" ]]; then
    if xinput map-to-output "${MEETINGBOX_TOUCH_XINPUT_DEVICE}" "$OUT" 2>/dev/null; then
      logger -t meetingbox-kiosk "xinput: map-to-output '${MEETINGBOX_TOUCH_XINPUT_DEVICE}' -> $OUT (MEETINGBOX_TOUCH_XINPUT_DEVICE)"
      mapped=1
    fi
  fi
  if [[ -n "${MEETINGBOX_TOUCH_XINPUT_NAMES:-}" ]]; then
    IFS='|' read -r -a _touch_arr <<<"${MEETINGBOX_TOUCH_XINPUT_NAMES}"
    for devname in "${_touch_arr[@]}"; do
      devname="${devname#"${devname%%[![:space:]]*}"}"
      devname="${devname%"${devname##*[![:space:]]}"}"
      [[ -z "$devname" ]] && continue
      if xinput map-to-output "$devname" "$OUT" 2>/dev/null; then
        logger -t meetingbox-kiosk "xinput: map-to-output '$devname' -> $OUT (MEETINGBOX_TOUCH_XINPUT_NAMES)"
        mapped=1
      fi
    done
  fi

  if [[ "$mapped" -eq 0 ]]; then
    logger -t meetingbox-kiosk "touch: no device mapped — on the panel: xinput list --name-only ; add MEETINGBOX_TOUCH_XINPUT_NAMES to /etc/meetingbox/panel-xrandr.env ; sudo usermod -aG input \$USER"
  fi
}

if [[ "$XR_OK" -eq 1 ]]; then
  _map_touch_to_output
fi

exit 0

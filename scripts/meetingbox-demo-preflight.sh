#!/usr/bin/env bash
set -u

REPO_DIR="${MEETINGBOX_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CONTAINER="${MEETINGBOX_CONTAINER:-meetingbox-appliance-ui}"
EXPECTED_SHA="${1:-$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null)}"
failures=0

check() {
  local label="$1"
  shift
  if "$@"; then
    printf 'PASS  %s\n' "$label"
  else
    printf 'FAIL  %s\n' "$label" >&2
    failures=$((failures + 1))
  fi
}

is_clean_dev_device() {
  [[ "$(git -C "$REPO_DIR" branch --show-current)" == "dev_device" ]] &&
    [[ -z "$(git -C "$REPO_DIR" status --porcelain)" ]]
}

container_sha_matches() {
  local deployed
  deployed="$(docker exec "$CONTAINER" printenv MEETINGBOX_BUILD_SHA 2>/dev/null)"
  [[ "$deployed" == "$EXPECTED_SHA" ]]
}

single_owner() {
  [[ "$(pgrep -af 'python(3)? .*[/ ]main.py' | wc -l)" -eq 1 ]] &&
    [[ "$(pgrep -af 'python(3)? .*audio_capture.py' | wc -l)" -eq 1 ]]
}

warm_ready() {
  docker logs --since 10m "$CONTAINER" 2>&1 |
    grep -q "warm-standby session ready for instant activation"
}

bluetooth_disabled() {
  ! systemctl is-active --quiet bluetooth.service &&
    ! systemctl is-active --quiet meetingbox-amw45.service &&
    [[ "$(docker exec "$CONTAINER" printenv MEETINGBOX_BLUETOOTH_ENABLED 2>/dev/null)" == "0" ]]
}

automatic_updates_disabled() {
  local unit
  for unit in apt-daily.timer apt-daily-upgrade.timer unattended-upgrades.service; do
    if systemctl is-active --quiet "$unit"; then
      return 1
    fi
  done
  [[ -r /etc/apt/apt.conf.d/20auto-upgrades ]] &&
    grep -q 'APT::Periodic::Enable "0"' /etc/apt/apt.conf.d/20auto-upgrades
}

audio_fallback_ready() {
  [[ "$(docker exec "$CONTAINER" printenv MEETINGBOX_USB_MIC_STRICT 2>/dev/null)" == "0" ]] &&
    docker exec "$CONTAINER" arecord -l 2>/dev/null |
      grep -q '^card '
}

no_legacy_audio_stack() {
  [[ ! -e /etc/systemd/system/meetingbox-docker-audio.service ||
     "$(readlink /etc/systemd/system/meetingbox-docker-audio.service 2>/dev/null)" == "/dev/null" ]] &&
    ! systemctl is-active --quiet meetingbox-docker-audio.service &&
    ! docker ps -a --format '{{.Names}}' |
      grep -Eq '^meetingbox-(appliance-)?redis$'
}

idle_cpu_bounded() {
  local raw whole max
  max="${MEETINGBOX_PREFLIGHT_MAX_CPU_PERCENT:-85}"
  raw="$(docker stats --no-stream --format '{{.CPUPerc}}' "$CONTAINER" 2>/dev/null)"
  whole="${raw%%%}"
  whole="${whole%%.*}"
  [[ "$whole" =~ ^[0-9]+$ ]] && (( whole <= max ))
}

backend_reachable() {
  local backend
  backend="$(docker exec "$CONTAINER" printenv BACKEND_URL 2>/dev/null)"
  [[ -n "$backend" ]] && curl -fsS --max-time 5 "${backend%/}/health" >/dev/null
}

openai_reachable() {
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 5 \
    --max-time 8 https://api.openai.com/v1/models)"
  [[ "$code" == "401" || "$code" == "200" ]]
}

check "clean dev_device worktree" is_clean_dev_device
check "deployed build SHA $EXPECTED_SHA" container_sha_matches
check "single UI and audio owner" single_owner
check "held warm Realtime session" warm_ready
check "Bluetooth disabled by appliance policy" bluetooth_disabled
check "automatic Ubuntu updates disabled" automatic_updates_disabled
check "USB with built-in audio fallback available" audio_fallback_ready
check "no legacy Redis/audio stack" no_legacy_audio_stack
check "backend health" backend_reachable
check "OpenAI network reachability" openai_reachable
check "container CPU within demo threshold" idle_cpu_bounded

printf 'INFO  container CPU: %s\n' \
  "$(docker stats --no-stream --format '{{.CPUPerc}}' "$CONTAINER" 2>/dev/null)"

if [[ "$failures" -ne 0 ]]; then
  printf '%d preflight check(s) failed\n' "$failures" >&2
  exit 1
fi
echo "MeetingBox demo preflight passed"

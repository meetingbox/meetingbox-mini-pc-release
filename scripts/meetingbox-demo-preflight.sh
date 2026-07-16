#!/usr/bin/env bash
set -u

REPO_DIR="${MEETINGBOX_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CONTAINER="${MEETINGBOX_CONTAINER:-meetingbox-appliance-ui}"
EXPECTED_SHA="${1:-$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null)}"
AUDIO_USER="${MEETINGBOX_AUDIO_USER:-meetingbox}"
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

amw45_duplex() {
  [[ -s /run/meetingbox-amw45-ready ]] || return 1
  local uid runtime source sink
  uid="$(id -u "$AUDIO_USER")"
  runtime="/run/user/$uid"
  source="$(runuser -u "$AUDIO_USER" -- env XDG_RUNTIME_DIR="$runtime" pactl get-default-source)"
  sink="$(runuser -u "$AUDIO_USER" -- env XDG_RUNTIME_DIR="$runtime" pactl get-default-sink)"
  [[ "$source" == bluez_* && "$sink" == bluez_* ]] &&
    grep -q '^profile=headset-head-unit-msbc$' /run/meetingbox-amw45-ready
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
check "AM-W45 mSBC microphone and speaker" amw45_duplex
check "backend health" backend_reachable
check "OpenAI network reachability" openai_reachable

printf 'INFO  container CPU: %s\n' \
  "$(docker stats --no-stream --format '{{.CPUPerc}}' "$CONTAINER" 2>/dev/null)"

if [[ "$failures" -ne 0 ]]; then
  printf '%d preflight check(s) failed\n' "$failures" >&2
  exit 1
fi
echo "MeetingBox demo preflight passed"

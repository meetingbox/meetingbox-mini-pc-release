#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${MEETINGBOX_DATA_ROOT:-$HOME/meetingbox-mini-pc-release}"
AUDIO_DIR="$HOME/meetingbox-mini-pc-release/audio"
ENV_FILE="$HOME/meetingbox-mini-pc-release/device-ui-flutter/device-ui-flutter.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

export MEETINGBOX_DATA_ROOT="${MEETINGBOX_DATA_ROOT:-$DATA_ROOT}"
export RECORDINGS_DIR="${RECORDINGS_DIR:-$MEETINGBOX_DATA_ROOT/data/audio/recordings}"
export TEMP_SEGMENTS_DIR="${TEMP_SEGMENTS_DIR:-$MEETINGBOX_DATA_ROOT/data/audio/temp}"
export DEVICE_AUTH_TOKEN_FILE="${DEVICE_AUTH_TOKEN_FILE:-$MEETINGBOX_DATA_ROOT/data/config/device_auth_token}"
export UPLOAD_AUDIO_API_URL="${UPLOAD_AUDIO_API_URL:-https://meetingboxai.lucratechsol.com/api/meetings/upload-audio}"
export AUDIO_POLL_BASE_URL="${AUDIO_POLL_BASE_URL:-https://meetingboxai.lucratechsol.com}"
export UPLOAD_AUDIO_ON_STOP="${UPLOAD_AUDIO_ON_STOP:-1}"
export UPLOAD_AUDIO_TIMEOUT_SECONDS="${UPLOAD_AUDIO_TIMEOUT_SECONDS:-1200}"
export MEETINGBOX_AUDIO_NO_RESPAWN="${MEETINGBOX_AUDIO_NO_RESPAWN:-0}"

mkdir -p "$RECORDINGS_DIR" "$TEMP_SEGMENTS_DIR" "$(dirname "$DEVICE_AUTH_TOKEN_FILE")"

if [[ -f "$AUDIO_DIR/.venv/bin/python3" ]]; then
  PYTHON="$AUDIO_DIR/.venv/bin/python3"
else
  PYTHON="python3"
fi

cd "$AUDIO_DIR"
exec "$PYTHON" audio_capture.py

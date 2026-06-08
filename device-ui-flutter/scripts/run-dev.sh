#!/usr/bin/env bash
# Dev launch — windowed, local backend.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

flutter run -d linux \
  --dart-define=BACKEND_URL="${BACKEND_URL:-http://localhost:8000}" \
  --dart-define=DEVICE_BRIDGE_URL="${DEVICE_BRIDGE_URL:-http://127.0.0.1:8765}" \
  --dart-define=MOCK_BACKEND="${MOCK_BACKEND:-0}" \
  --dart-define=DISPLAY_WIDTH="${DISPLAY_WIDTH:-1260}" \
  --dart-define=DISPLAY_HEIGHT="${DISPLAY_HEIGHT:-800}" \
  --dart-define=FULLSCREEN="${FULLSCREEN:-0}"

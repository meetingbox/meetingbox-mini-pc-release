#!/usr/bin/env bash
# One-time setup: generate Linux runner + fetch deps (requires Flutter SDK on PATH).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v flutter >/dev/null 2>&1; then
  echo "Flutter SDK not found. Install from https://docs.flutter.dev/get-started/install/linux" >&2
  exit 1
fi

# Generate linux/ runner if missing (safe to re-run).
if [[ ! -f linux/CMakeLists.txt ]]; then
  flutter create . --platforms=linux --project-name meetingbox_device_ui
fi

bash "$ROOT/scripts/sync-assets.sh"
flutter pub get
echo "Ready. Run: flutter run -d linux"

#!/usr/bin/env bash
# Copy shared assets + fonts from Kivy device-ui into the Flutter project.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/../device-ui/assets"

if [[ ! -d "$SRC" ]]; then
  echo "Source assets not found: $SRC" >&2
  exit 1
fi

FOLDERS=(welcome home recording processing summary brief calendar idle fonts)

for f in "${FOLDERS[@]}"; do
  [[ -d "$SRC/$f" ]] || continue
  mkdir -p "$ROOT/assets/$f"
  rsync -a "$SRC/$f/" "$ROOT/assets/$f/" 2>/dev/null \
    || cp -a "$SRC/$f/." "$ROOT/assets/$f/" 2>/dev/null || true
done

echo "Assets synced to $ROOT/assets"

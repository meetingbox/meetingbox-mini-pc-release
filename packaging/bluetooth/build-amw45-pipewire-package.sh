#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH_FILE="$ROOT_DIR/patches/0001-am-w45-optional-hfp-queries.patch"
WORK_DIR="${1:-$ROOT_DIR/build}"
OUT_DIR="${2:-$ROOT_DIR/dist}"

command -v apt-get >/dev/null
command -v dpkg-buildpackage >/dev/null
[[ -r "$PATCH_FILE" ]]

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR" "$OUT_DIR"
cd "$WORK_DIR"

apt-get source pipewire
source_dir="$(find . -mindepth 1 -maxdepth 1 -type d -name 'pipewire-*' | sort | tail -n 1)"
if [[ -z "$source_dir" ]]; then
  echo "PipeWire source directory was not created" >&2
  exit 1
fi

cd "$source_dir"
patch --forward --batch -p1 <"$PATCH_FILE"
base_version="$(dpkg-parsechangelog -S Version)"
package_source="$(dpkg-parsechangelog -S Source)"
custom_version="${base_version}+meetingbox1"
maintainer_date="$(date -R)"
python3 - "$package_source" "$custom_version" "$maintainer_date" <<'PY'
from pathlib import Path
import sys

source, version, date = sys.argv[1:]
changelog = Path("debian/changelog")
previous = changelog.read_text(encoding="utf-8")
entry = f"""{source} ({version}) noble; urgency=medium

  * Accept optional AM-W45 HFP phone queries without ModemManager.

 -- MeetingBox Release <release@meetingbox.local>  {date}

"""
changelog.write_text(entry + previous, encoding="utf-8")
PY

DEB_BUILD_OPTIONS="nocheck" dpkg-buildpackage -b -uc -us
cd ..

package="$(find . -maxdepth 1 -type f -name 'libspa-0.2-bluetooth_*_amd64.deb' | sort | tail -n 1)"
if [[ -z "$package" ]]; then
  echo "libspa-0.2-bluetooth package was not produced" >&2
  exit 1
fi
cp -f "$package" "$OUT_DIR/"
sha256sum "$OUT_DIR/$(basename "$package")" | tee "$OUT_DIR/SHA256SUMS"
echo "Built $(basename "$package")"

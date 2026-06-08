# MeetingBox Flutter UI — native Linux packaging

Builds a `.deb` that ships the native Flutter kiosk UI **and** the Python
`device-services` bridge, with systemd units for both. This mirrors the legacy
Kivy `build-device-ui-deb.sh` flow and replaces the `meetingbox-ui` package.

## 1. Build host prerequisites (Ubuntu mini PC)

```bash
sudo apt update
sudo apt install -y clang cmake ninja-build pkg-config libgtk-3-dev \
                    python3-venv dpkg-dev
# Flutter SDK must be on PATH:
flutter --version
```

## 2. Configure backend

Edit `device-ui-flutter.env` (baked into the binary at build time via
`--dart-define`, and read at runtime for display/session settings):

- `BACKEND_URL`, `BACKEND_WS_URL`, `DASHBOARD_PUBLIC_URL`
- `MOCK_BACKEND=1` for an offline demo build
- `DISPLAY_WIDTH` / `DISPLAY_HEIGHT` to match the physical panel

## 3. Build the package

```bash
cd mini-pc
./scripts/build-device-ui-flutter-deb.sh
# -> dist/meetingbox-ui-flutter_0.1.0_amd64.deb
```

The script scaffolds the Linux runner (`flutter create --platforms=linux .`)
on first run, builds `flutter build linux --release`, then assembles the bundle
+ bridge + systemd units into the `.deb`.

## 4. Install on the device

```bash
sudo apt install ./meetingbox-ui-flutter_0.1.0_amd64.deb
```

`postinst` creates a venv for the bridge, installs its requirements, then
enables + starts:

- `meetingbox-device-bridge.service` — FastAPI bridge on `127.0.0.1:8765`
- `meetingbox-flutter-ui.service` — Flutter kiosk UI on `DISPLAY=:0`

## 5. Logs / status

```bash
systemctl status meetingbox-flutter-ui.service meetingbox-device-bridge.service
journalctl -u meetingbox-flutter-ui.service -f
journalctl -u meetingbox-device-bridge.service -f
```

## 6. Rollback to the Kivy UI

The Flutter package declares `Conflicts: meetingbox-ui`, so only one UI is
installed at a time. To roll back while parity is being signed off:

```bash
sudo apt remove meetingbox-ui-flutter
sudo apt install ./meetingbox-ui_<version>_amd64.deb   # legacy Kivy build
```

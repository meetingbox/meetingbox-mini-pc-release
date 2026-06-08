# MeetingBox Device UI (Flutter)

Flutter Linux desktop app — incremental replacement for the Kivy `device-ui`.

**Phase 0–1 (this scaffold):** Splash → Welcome → Home, backend API client, local device bridge client.

## Architecture

```
Flutter UI (this folder)
    ├── REST  → MeetingBox backend (BACKEND_URL)
    └── REST  → device-services bridge (DEVICE_BRIDGE_URL, localhost:8765)
                    └── reuses device-ui Python modules (WiFi, brightness, audio)
```

The existing Kivy app in `../device-ui/` stays installed until Flutter reaches feature parity.

## Prerequisites

- Flutter SDK 3.22+ with Linux desktop enabled (`flutter config --enable-linux-desktop`)
- Ubuntu build host (same arch as appliance) for release builds
- `device-services` running for WiFi/brightness (optional in dev)

### Run on your Windows dev PC (before Ubuntu)

Yes — you can preview UI on Windows first:

1. **Install Flutter** (if missing): clone to `%USERPROFILE%\flutter` or `choco install flutter -y` (admin).
2. **Enable Windows Developer Mode** (required for `flutter run -d windows`):
   - Settings → Privacy & security → For developers → **Developer Mode** ON
   - Or run: `start ms-settings:developers`
3. **Init + run:**

```powershell
cd mini-pc\device-ui-flutter
.\scripts\sync-assets.ps1
.\scripts\init-project.ps1
.\scripts\run-dev.ps1
```

**Without Developer Mode:** use Chrome preview instead:

```powershell
flutter create . --platforms=web
flutter run -d chrome --dart-define=MOCK_BACKEND=1
```

On Windows, `device-services` (WiFi/brightness) does **not** run — `MOCK_BACKEND=1` is the default in `run-dev.ps1`. Backend API still works if your server is reachable at `BACKEND_URL`.

## First-time setup

```bash
cd mini-pc/device-ui-flutter
bash scripts/init-project.sh    # flutter create linux runner + pub get + sync assets
```

On Windows (assets only):

```powershell
.\scripts\sync-assets.ps1
```

Then on a Linux machine with Flutter:

```bash
flutter pub get
flutter run -d linux
```

## Development

```bash
# Terminal 1 — device bridge (Ubuntu)
cd ../device-services && python src/main.py

# Terminal 2 — Flutter UI
cd ../device-ui-flutter
bash scripts/run-dev.sh
```

Env vars are passed via `--dart-define` (see `.env.example`).

Mock backend (no server):

```bash
MOCK_BACKEND=1 bash scripts/run-dev.sh
```

## Project layout

```
lib/
  config/          # BACKEND_URL, display size, etc.
  core/theme/      # Dark theme + Figma colors
  routing/         # go_router
  screens/         # splash, welcome, home (more in later phases)
  services/        # api_client, device_bridge_client, setup_state
  widgets/         # PrimaryButton, GlassCard
```

## Build release (Ubuntu)

```bash
flutter build linux --release \
  --dart-define=BACKEND_URL=https://your-server.example.com \
  --dart-define=FULLSCREEN=1 \
  --dart-define=DISPLAY_WIDTH=1260 \
  --dart-define=DISPLAY_HEIGHT=800
```

Output: `build/linux/x64/release/bundle/`

Packaging as `.deb` is a follow-up (mirror `scripts/build-device-ui-deb.sh` for Flutter bundle).

## Migration phases

| Phase | Screens / features |
|-------|-------------------|
| **0–1** ✅ | Splash, Welcome, Home scaffold, API + bridge clients |
| 2 | Recording, Processing, Summary |
| 3 | Onboarding (WiFi, pair), Settings |
| 4 | Emails, Calendar, Tasks, Voice |
| 5 | `.deb`, systemd, kiosk boot |

## Assets

Figma/Kivy assets are **not** committed here. Sync from the Kivy tree:

```bash
bash scripts/sync-assets.sh
```

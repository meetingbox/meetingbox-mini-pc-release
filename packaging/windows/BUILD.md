# Building MeetingBox for Windows

**Release overview (install layout, upgrade/uninstall, SmartScreen, QA):**
[WINDOWS_DESKTOP.md](WINDOWS_DESKTOP.md).

This produces the Windows desktop build of the MeetingBox **companion** (PyInstaller
one-dir) and bundles it with the **dashboard** (Tauri) into a single Inno Setup
installer (`MeetingBoxSetup.exe`).

The companion folder contains `MeetingBox.exe` (Kivy UI), its bundled
audio-capture child `meetingbox-audio.exe`, and a shared `_internal\` payload.

> **Why two .exe files?** This mirrors the Docker appliance exactly. In
> `docker-compose.yml` there is one `device-ui` container that runs
> `python main.py` and internally spawns `audio_capture.py` as a child process
> (via `audio_supervisor.py`). Once frozen by PyInstaller, the UI binary can't
> run a `.py` script, so the audio child ships as a sibling `meetingbox-audio.exe`.
> It is **not** a separate service — `MeetingBox.exe` launches and manages it
> automatically. Keep the whole `MeetingBox\` folder together.

---

## Prerequisites (install once)

- **Python 3.11** (64-bit) from [python.org](https://www.python.org/downloads/) —
  during install, tick **"Add python.exe to PATH"**.
  - Use **3.11 specifically.** The required wheels (`vosk`, `pyaudio`,
    `kivy_deps.sdl2/glew/angle`, Kivy 2.3.1) ship prebuilt `cp311` wheels.
    Newer Python (3.13+) may have no matching wheels and the install can fail.
- **Git** — [git-scm.com](https://git-scm.com/download/win).
- *(Optional, only to build the installer)* **Inno Setup 6** —
  [jrsoftware.org](https://jrsoftware.org/isdl.php).

Verify Python:

```powershell
py -3.11 --version
# Python 3.11.x
```

---

## One command (full monorepo)

From any folder, with **Python 3.11**, **Node**, **Rust**, and **Inno Setup 6** installed:

```powershell
powershell -ExecutionPolicy Bypass -File C:\meetingbox\meetingbox\mini-pc\packaging\windows\build-all.ps1
```

**Output:** `mini-pc\packaging\windows\Output\MeetingBoxSetup.exe`

```powershell
# Reuse an existing dashboard exe (faster):
build-all.ps1 -SkipDashboard

# Sign exes + installer (needs code-signing cert on this machine):
build-all.ps1 -Sign
```

---

## Build commands (PowerShell, step by step)

Run from wherever you want the source checkout to live.

```powershell
# 1. Get the code
git clone https://github.com/trilokpotluri27/meetingbox-mini-pc-release.git
cd meetingbox-mini-pc-release

# 2. Create + activate a Python 3.11 virtual environment
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install the app deps + the build toolchain
python -m pip install --upgrade pip
python -m pip install -r device-ui\requirements.txt
python -m pip install -r packaging\windows\requirements-build.txt

# 4. Build both exes (UI + audio child) into one folder
python -m PyInstaller packaging\windows\MeetingBox.spec --noconfirm `
  --distpath packaging\windows\dist --workpath packaging\windows\build
```

**Output:** `packaging\windows\dist\MeetingBox\MeetingBox.exe`, with
`meetingbox-audio.exe` and `_internal\` beside it. Ship the whole folder.

### Notes on harmless build output
PyInstaller prints a few `ERROR: Hidden import '...' not found` lines for
`soundfile`, `redis`, `scipy`, and `scipy.signal`. These are **optional**
imports listed defensively in the spec; they are not needed on Windows and do
not affect the build. Likewise the `CRITICAL [Camera]` / `[Spelling]` lines from
Kivy are normal (those providers don't exist on a headless build machine).

---

## Build the Dashboard app (Tauri + WebView2)

The installer bundles a **second app** — the MeetingBox Dashboard, a Tauri v2 +
WebView2 shell around the React SPA (`frontend/`). This requires the **full
monorepo checkout** (both `frontend/` and `mini-pc/` present), not just the
mini-pc release repo.

Extra prerequisites (build machine only):
- **Node.js + npm** (already used by the frontend).
- **Rust** (stable, `x86_64-pc-windows-msvc`) with the **Visual Studio C++ Build
  Tools** — <https://www.rust-lang.org/tools/install>.
- Edge **WebView2** runtime is only needed on the *run* machine (the installer
  provisions it; see below).

```powershell
cd frontend
npm ci
npm run tauri:build     # builds the SPA (--mode desktop, win. backend) + compiles the exe
```

**Output:** `frontend\src-tauri\target\release\MeetingBoxDashboard.exe` — a single
self-contained exe (WebView2 is a shared system runtime). This is the exact path
`MeetingBox.iss` copies into `{app}\Dashboard\`.

> The desktop SPA build reads `frontend\.env.desktop` (points at
> `https://win.meetingboxai.lucratechsol.com`), so it does **not** affect the
> normal web-dashboard build (`npm run build`).

### WebView2 runtime bootstrapper
Download the Evergreen bootstrapper and place it next to `MeetingBox.iss` as
`MicrosoftEdgeWebview2Setup.exe`
(<https://developer.microsoft.com/microsoft-edge/webview2/>). The installer runs
it silently **only if** the runtime is missing. (Optional: drop `vc_redist.x64.exe`
there too if a clean-VM test shows the target lacks the VC++ runtime.)

---

## Code-sign the executables

For distribution without SmartScreen / "unknown publisher" / AV warnings, all
three exes must be Authenticode-signed with an **EV** (or OV) code-signing
certificate. EV certs live on a hardware token; its middleware prompts for the
PIN. Run **after** building the appliance and dashboard, **before** ISCC:

```powershell
# Auto-select the code-signing cert on the token, SHA-256 + RFC3161 timestamp:
powershell -ExecutionPolicy Bypass -File packaging\windows\sign.ps1
# or select by thumbprint:
#   packaging\windows\sign.ps1 -Thumbprint <SHA1_THUMBPRINT>
```

This signs `MeetingBox.exe`, `meetingbox-audio.exe`, and `MeetingBoxDashboard.exe`.

The **installer and its uninstaller** are signed by Inno Setup itself via the
`SignTool=meetingbox` / `SignedUninstaller=yes` directives in `MeetingBox.iss`.
These are guarded by `#ifdef SIGN`, so pass `/DSIGN` to enable them and register
the "meetingbox" sign tool (or define it via *Tools > Configure Sign Tools* in
the Inno IDE):

```powershell
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DSIGN `
  /Ssigntool="signtool.exe sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a $f" `
  packaging\windows\MeetingBox.iss
```

> For an **unsigned local test build**, just omit `/DSIGN` — ISCC compiles the
> installer without requiring a sign tool.

---

## Build the unified installer (`MeetingBoxSetup.exe`)

The Inno Setup script now bundles **both apps**. Full build order:

1. Appliance: PyInstaller → `packaging\windows\dist\MeetingBox\` (step above).
2. Dashboard: `npm run tauri:build` → `MeetingBoxDashboard.exe` (step above).
3. Stage `MicrosoftEdgeWebview2Setup.exe` next to `MeetingBox.iss`.
4. Sign all three exes: `packaging\windows\sign.ps1`.
5. Compile (and sign) the installer:

```powershell
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DSIGN `
  /Ssigntool="signtool.exe sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a $f" `
  packaging\windows\MeetingBox.iss
```

(Omit `/DSIGN` for an unsigned local test build.)

**Output:** `packaging\windows\Output\MeetingBoxSetup.exe`. It installs both apps
into Program Files (`{app}` + `{app}\Dashboard`), ensures the WebView2 runtime,
seeds `%PROGRAMDATA%\MeetingBox\device-ui.env` (only if absent), shows the EULA,
installs `THIRD-PARTY-NOTICES.txt`, creates Start Menu / optional desktop
shortcuts for both apps, and (opt-out) registers both to auto-start at login
(the dashboard starts minimized to the tray).

### Install, upgrade, and uninstall (behavior)

| Action | Behavior |
|--------|----------|
| **First install** | EULA → files to `%ProgramFiles%\MeetingBox\` + config seed to `%ProgramData%\MeetingBox\` |
| **Re-run installer** | Same `AppId` → **in-place upgrade** (one entry in Settings → Apps) |
| **Apps running during upgrade** | `CloseApplications=force` closes companion + dashboard (no “files in use” dialog) |
| **Uninstall** | `CurUninstallStepChanged` runs `taskkill` on `MeetingBox.exe`, `meetingbox-audio.exe`, and `MeetingBoxDashboard.exe` before deleting files |
| **Config after uninstall** | `%ProgramData%\MeetingBox\device-ui.env` is kept (`uninsneveruninstall`) |

Companion window on Windows desktop: fixed **1120×680** (see `device-ui.env`), clamped to the usable desktop area in `main.py`.

### SmartScreen

Unsigned builds (ISCC without `/DSIGN`) trigger **“Windows protected your PC”** after
download. Sign all exes + installer before publishing; prefer an **EV** certificate.
See [WINDOWS_DESKTOP.md](WINDOWS_DESKTOP.md).

### Regenerate the Word release guide

```powershell
python packaging\windows\generate_windows_docx.py
```

Writes `packaging\windows\MeetingBox_Windows.docx` and updates
`Desktop\MeetingBox Windows.docx` when that path is writable.

---

## Running the build

Launch `MeetingBox.exe` from inside the `MeetingBox\` folder (it needs its
`_internal\` payload and sibling audio exe next to it).

Configuration comes from `device-ui.env`. For an installed copy this lives at
`%PROGRAMDATA%\MeetingBox\device-ui.env`; the bundled default
(`packaging\windows\device-ui.env`) points at the cloud backend.

- **Real backend:** set `BACKEND_URL` (and pair the device) in `device-ui.env`.
- **Quick local UI test (no backend):** set `MOCK_BACKEND=1`. In mock mode the
  app does not spawn the audio child (there is no backend to record/upload to),
  so you won't see audio-command polling.

```powershell
$env:MOCK_BACKEND = "1"
.\packaging\windows\dist\MeetingBox\MeetingBox.exe
```

### If Windows blocks the exe
On machines with an **Application Control policy** (WDAC / AppLocker / Smart App
Control), an unsigned `MeetingBox.exe` may be blocked
(*"An Application Control policy has blocked this file"*). For distribution to
such machines the executables need to be **code-signed**, or the policy must
allow them. This is a Windows security-policy issue, not a build problem.

---

## Verify on clean Windows 10/11 VMs

Run this checklist on **clean** VMs (no Python / Rust / dev tools) with the
**signed** `MeetingBoxSetup.exe`:

- [ ] **SmartScreen / publisher:** no "unknown publisher" block; UAC prompt shows
      *Lucratech Solutions*. Signed installer + all three exes.
- [ ] **Antivirus:** installer and both apps pass common AV (incl. an env with
      HTTPS inspection). No quarantine.
- [ ] **EULA:** the license page appears and must be accepted before install.
- [ ] **WebView2:** on a VM without the runtime, the installer auto-installs it;
      on a VM that already has it, it is skipped.
- [ ] **Install layout:** `…\MeetingBox\MeetingBox.exe`, `meetingbox-audio.exe`,
      `…\MeetingBox\Dashboard\MeetingBoxDashboard.exe`, `THIRD-PARTY-NOTICES.txt`,
      Start Menu links for both apps + Third-party notices.
- [ ] **Auto-start:** after reboot/sign-in, the companion launches and the
      dashboard appears in the tray (minimized). Unchecking the Startup task at
      install removes both `HKLM…\Run` entries.
- [ ] **Dashboard theme:** light + periwinkle (`#7b61ff`), consistent with the
      companion across Home / Calendar / Meetings / Tasks / Emails / Assistant
      (Settings is web-only; hidden on Windows companion).
- [ ] **Companion window:** 1120×680 fits 1366×768; title bar and controls on-screen.
- [ ] **Dashboard consent gate:** first login shows the EULA/Privacy/recording
      consent step and blocks until accepted; not shown again afterwards.
- [ ] **Backend flows:** dashboard sign-in + companion voice/recording work
      against `https://win.meetingboxai.lucratechsol.com`.
- [ ] **Tray behavior:** closing the dashboard window hides to tray; tray
      left-click / "Open Dashboard" restores it; "Quit" exits. Relaunch focuses
      the existing window (single instance).
- [ ] **Upgrade & uninstall:** re-running the installer upgrades in place with
      running apps closed automatically; uninstall leaves **no** MeetingBox
      processes in Task Manager; Run entries removed when startup task was used.
- [ ] **Companion regression:** onboarding, voice, and recording behave exactly
      as before — only the exe metadata/signature changed.

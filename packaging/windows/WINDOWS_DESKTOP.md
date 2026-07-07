# MeetingBox Windows desktop — release guide

This document describes the **Windows desktop port** only (companion + dashboard). The **Linux appliance** is unchanged.

**Build details:** see [BUILD.md](BUILD.md).

---

## What ships today

| Item | Status |
|------|--------|
| **Single installer** | `MeetingBoxSetup.exe` (Inno Setup 6) installs **two apps** into one folder under Program Files |
| **Companion** | `MeetingBox.exe` + child `meetingbox-audio.exe` + `_internal\` (PyInstaller one-dir) |
| **Dashboard** | `Dashboard\MeetingBoxDashboard.exe` (Tauri v2 + WebView2 + React SPA) |
| **Backend (Windows only)** | `https://win.meetingboxai.lucratechsol.com` via `device-ui.env` and `frontend/.env.desktop` |
| **Linux / cloud mini-PC** | Still uses the original backend URL (not `win.*`) |
| **Settings UI** | Hidden on desktop (`IS_DESKTOP`) — appliance only |
| **System check overlay** | Skipped on desktop — appliance only |
| **EULA** | Shown in the installer (`EULA.rtf`); must accept before install |
| **Recording / legal gate (dashboard)** | First-login `ConsentGate` (EULA, privacy, recording consent) in `localStorage` |
| **Third-party notices** | `THIRD-PARTY-NOTICES.txt` in the install folder + Start Menu link |
| **WebView2** | Evergreen bootstrapper bundled; installed silently only if missing |
| **Auto-start** | Optional task (checked by default): `HKLM\…\Run` for companion + dashboard (`--minimized` for tray) |
| **Shortcuts** | Start Menu for both apps; optional desktop icons |
| **Config** | `%PROGRAMDATA%\MeetingBox\device-ui.env` seeded on first install only (`uninsneveruninstall`) |
| **Version metadata** | `version_info.txt` on companion exes; Inno `AppVersion` 1.0.0 |
| **Dashboard theme** | Light UI + brand periwinkle (`#7b61ff` / `#5b3ff0`), aligned with companion / nora site |
| **Companion window** | Fixed **1120×680** window (non-resizable), clamped to the usable desktop area so it never overflows small laptop screens |
| **Upgrade** | Same `AppId` → **in-place upgrade** when the user runs a newer `MeetingBoxSetup.exe` (not a second product entry) |
| **Install with apps running** | `CloseApplications=force` — Restart Manager closes companion/dashboard during upgrade (no “files in use” prompt) |
| **Uninstall** | Stops `MeetingBox.exe`, `meetingbox-audio.exe`, and `MeetingBoxDashboard.exe` before deleting files; removes `HKLM\…\Run` entries when the startup task was used |
| **Code signing (build wiring)** | `sign.ps1` + Inno `#ifdef SIGN` — **must run with EV/OV cert before public download** |

---

## Install layout (end user)

```
%ProgramFiles%\MeetingBox\
  MeetingBox.exe
  meetingbox-audio.exe
  _internal\
  THIRD-PARTY-NOTICES.txt
  Dashboard\
    MeetingBoxDashboard.exe

%ProgramData%\MeetingBox\
  device-ui.env          (created on first install; kept on uninstall)
```

---

## SmartScreen and signing

Unsigned builds (local/CI without `/DSIGN`) show **“Windows protected your PC”** after download. That is expected.

**Distribution fix:**

1. Sign `MeetingBox.exe`, `meetingbox-audio.exe`, and `MeetingBoxDashboard.exe` with `packaging\windows\sign.ps1`.
2. Compile the installer with `/DSIGN` so the setup and uninstaller are signed too.

Prefer an **EV** code-signing certificate for immediate SmartScreen trust. **OV** certs need reputation over time.

For internal testing: **More info** → **Run anyway** on the SmartScreen page.

---

## Upgrade and uninstall behavior

- **Re-run installer:** upgrades files in the same directory; does not create duplicate “MeetingBox” entries in Settings → Apps.
- **EULA / config:** existing `%PROGRAMDATA%\MeetingBox\device-ui.env` is **not** overwritten on upgrade.
- **Uninstall (Control Panel):** new installers kill running processes first, then remove Program Files payload and registry Run values. Config under `%PROGRAMData%\MeetingBox` may remain by design so reinstall preserves pairing edits.

If an old build was installed **before** the uninstall process-kill fix, uninstall once manually after ending tasks in Task Manager, then install the latest `MeetingBoxSetup.exe`.

---

## Auth between companion and dashboard

The companion uses the **device pairing token** (`device-ui.env` / API client). The dashboard uses the **user JWT** in WebView2 `localStorage` (`auth_token`). **Logging into one app does not automatically log into the other** today.

---

## Build order (summary)

1. PyInstaller → `packaging\windows\dist\MeetingBox\`
2. `cd frontend && npm run tauri:build` → `MeetingBoxDashboard.exe`
3. Stage `MicrosoftEdgeWebview2Setup.exe` next to `MeetingBox.iss`
4. (Release) `sign.ps1` then `ISCC.exe` with `/DSIGN`
5. Output: `packaging\windows\Output\MeetingBoxSetup.exe`

Full commands: [BUILD.md](BUILD.md).

---

## QA checklist (clean Windows 10/11 VM)

Use a **signed** installer for production validation.

- [ ] SmartScreen / publisher: Lucratech Solutions on UAC; no unknown-publisher block when EV-signed
- [ ] EULA page before install; dashboard consent gate on first login
- [ ] WebView2 provisioned on VM without runtime
- [ ] Both apps in Start Menu; optional desktop shortcuts
- [ ] Auto-start: companion visible; dashboard in tray (`--minimized`); opt-out task clears Run keys
- [ ] Companion window fits 1366×768 (title bar reachable)
- [ ] Dashboard theme: light + periwinkle across main pages
- [ ] Backend: `win.meetingboxai.lucratechsol.com` — Google sign-in (redirect URI registered), voice/recording
- [ ] Upgrade over running install: no files-in-use dialog; apps closed and replaced
- [ ] Uninstall: no `MeetingBox*` processes left in Task Manager
- [ ] Tray: close hides; Quit exits; second launch focuses single instance

---

## Still on the roadmap (not blocking local builds)

These were in the original commercial checklist; most are **not** implemented in the client yet:

- Google OAuth **verification** + CASA for restricted Gmail/Calendar scopes
- **License / subscription** enforcement and payments
- Desktop **auto-update** channel
- Opt-in **crash reporting** / analytics on desktop
- Formal legal review of EULA/privacy text (installer uses product placeholders — counsel should review)
- MSIX / Microsoft Store packaging (optional future)

---

## Related docs

- [BUILD.md](BUILD.md) — prerequisites, PyInstaller, Tauri, signing, ISCC
- [frontend/src-tauri/README.md](../../../frontend/src-tauri/README.md) — dashboard shell behavior
- [server/WINDOWS_INSTANCE.md](../../../server/WINDOWS_INSTANCE.md) — optional separate Docker API instance on port 8100 (dev/ops; production Windows clients use `win.meetingboxai.lucratechsol.com`)

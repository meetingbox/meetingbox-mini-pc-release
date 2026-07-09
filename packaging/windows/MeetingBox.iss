; Inno Setup script for the Nexa Windows desktop port.
; Build with:
;   "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" packaging\windows\MeetingBox.iss
; Produces: packaging\windows\Output\NexaSetup.exe
;
; Installs the PyInstaller one-dir payload (Nexa.exe + nexa-audio.exe
; + _internal\) into Program Files, seeds a per-machine device-ui.env under
; %PROGRAMDATA%\Nexa (only if absent, so upgrades keep the user's edits),
; and creates Start Menu / optional desktop shortcuts.

#define MyAppName "Nexa"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Nexa"
#define MyAppExeName "Nexa.exe"
#define MyAppURL "https://win.meetingboxai.lucratechsol.com/"

; --- Second app: the Nexa Dashboard (Tauri + WebView2) ---------------
; Built separately (see BUILD.md): `npm run tauri:build` in the frontend produces
; this single self-contained exe. Path is relative to this .iss file
; (mini-pc\packaging\windows -> repo root -> frontend\...).
#define MyDashName "Nexa Dashboard"
#define MyDashExeName "NexaDashboard.exe"
#define MyAudioExeName "nexa-audio.exe"
#define DashSrcDir "..\..\..\frontend\src-tauri\target\release"
; Brand logo (Group.png -> multi-size .ico). Shipped into {app} and used as the
; explicit shortcut / uninstall icon so branding never depends on whatever icon
; the exe happens to have embedded (or on a stale Windows icon cache).
#define BrandIcon "..\..\..\frontend\src-tauri\icons\icon.ico"
; Edge WebView2 Evergreen bootstrapper (place next to this script before ISCC).
#define WebView2Bootstrapper "MicrosoftEdgeWebview2Setup.exe"
; Optional VC++ 2015-2022 x64 redistributable (bundle only if the clean-VM test
; shows the target lacks vcruntime140.dll).
#define VCRedist "vc_redist.x64.exe"

[Setup]
; Keep AppId stable so Windows treats this as an upgrade of the same product.
AppId={{8B6E2C44-2E2C-49A2-9C9F-7F2E1B3A6D11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=NexaSetup
SetupIconFile=meetingbox.ico
; Programs & Features / uninstall icon: use the bundled brand .ico so the entry
; always shows the Nexa logo, independent of the exe's embedded icon.
UninstallDisplayIcon={app}\Nexa.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
; Same AppId = in-place upgrade of an existing Nexa / MeetingBox install.
; Do NOT use CloseApplications=force: that still shows Restart Manager's
; "Preparing to Install / close these applications" page (with Nexa Dashboard
; listed). Instead we silently taskkill our processes in PrepareToInstall
; before any files are copied — the normal silent-upgrade pattern.
CloseApplications=no
RestartApplications=no
UsePreviousAppDir=yes
; Show the EULA and require acceptance before install proceeds.
LicenseFile=EULA.rtf
; Sign the installer AND its uninstaller with the "meetingbox" sign tool, but
; only when compiled with /DSIGN so unsigned local/CI builds still compile.
; Enable signing by first registering the tool and passing /DSIGN, e.g.:
;   ISCC.exe /DSIGN /Ssigntool="signtool.exe sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a $f" MeetingBox.iss
; (or define the tool via the Inno Setup IDE: Tools > Configure Sign Tools).
#ifdef SIGN
SignTool=meetingbox
SignedUninstaller=yes
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
; Checked by default: register the app to start at login (opt-out).
Name: "startupicon"; Description: "Automatically start Nexa when I sign in to Windows"; GroupDescription: "Startup:"

[Registry]
; Login auto-start (per-machine; installer runs as admin). Only the Dashboard
; is registered: it is the primary app and spawns the companion itself.
; --minimized keeps it in the notification-area tray. Removed on uninstall.
; Stale values from older MeetingBox installs are deleted.
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "MeetingBox"; Flags: deletevalue
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "MeetingBoxDashboard"; Flags: deletevalue
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "NexaDashboard"; ValueData: """{app}\Dashboard\{#MyDashExeName}"" --minimized"; Flags: uninsdeletevalue; Tasks: startupicon

[Files]
; The entire PyInstaller one-dir output (the Nexa companion app).
Source: "dist\Nexa\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; The Nexa Dashboard desktop app (single Tauri exe) into its own subfolder.
Source: "{#DashSrcDir}\{#MyDashExeName}"; DestDir: "{app}\Dashboard"; Flags: ignoreversion
; Edge WebView2 Evergreen bootstrapper — staged to {tmp}, run only if the runtime
; is missing (see [Run] + WebView2Needed), then deleted.
Source: "{#WebView2Bootstrapper}"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist
; Optional VC++ runtime — staged only if you drop the file next to the script.
Source: "{#VCRedist}"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist
; Open-source third-party license notices (OSS compliance).
Source: "THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
; Per-machine config seed (only copied if it does not already exist).
Source: "device-ui.env"; DestDir: "{commonappdata}\Nexa"; Flags: onlyifdoesntexist uninsneveruninstall
; Brand logo used as the explicit shortcut / uninstall icon.
Source: "{#BrandIcon}"; DestDir: "{app}"; DestName: "Nexa.ico"; Flags: ignoreversion skipifsourcedoesntexist

[Dirs]
Name: "{commonappdata}\Nexa"; Permissions: users-modify

[Icons]
; Single entry point: the Dashboard is the primary app (it launches the
; companion itself), so there is exactly ONE shortcut named "Nexa".
Name: "{group}\{#MyAppName}"; Filename: "{app}\Dashboard\{#MyDashExeName}"; WorkingDir: "{app}\Dashboard"; IconFilename: "{app}\Nexa.ico"
Name: "{group}\Edit Nexa configuration"; Filename: "notepad.exe"; Parameters: """{commonappdata}\Nexa\device-ui.env"""
Name: "{group}\Third-party notices"; Filename: "{app}\THIRD-PARTY-NOTICES.txt"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Dashboard\{#MyDashExeName}"; WorkingDir: "{app}\Dashboard"; IconFilename: "{app}\Nexa.ico"; Tasks: desktopicon

[Run]
; Provision the Edge WebView2 runtime (needed by the dashboard) only if absent.
Filename: "{tmp}\{#WebView2Bootstrapper}"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft Edge WebView2 runtime..."; Flags: waituntilterminated; Check: WebView2Needed
; Install the VC++ runtime only if bundled and not already present.
Filename: "{tmp}\{#VCRedist}"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Visual C++ runtime..."; Flags: waituntilterminated; Check: VCRedistNeeded
; Launch only the Dashboard: it spawns the companion itself.
Filename: "{app}\Dashboard\{#MyDashExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\Dashboard"

[Code]
// Stop our apps so upgrades/uninstalls never hit "files in use".
// Dashboard + companion lock exes under the install dir; Restart Manager's
// CloseApplications dialog is what the user saw. Kill by image name instead.
procedure KillNexaProcesses;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'),
    '/F /T /IM "{#MyAppExeName}" /IM "{#MyAudioExeName}" /IM "{#MyDashExeName}" /IM "MeetingBox.exe" /IM "meetingbox-audio.exe" /IM "MeetingBoxDashboard.exe"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  // Give Windows a moment to release file handles before Setup copies over them.
  Sleep(800);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  // After wizard, before [Files] — clear locks for in-place upgrade silently.
  NeedsRestart := False;
  KillNexaProcesses;
  Result := '';
end;

{ --- Edge WebView2 runtime detection (Evergreen client GUID) --- }
function WebView2Installed(): Boolean;
var
  pv: String;
begin
  Result := False;
  if RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', pv) then
    if (pv <> '') and (pv <> '0.0.0.0') then
      Result := True;
  if not Result then
    if RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', pv) then
      if (pv <> '') and (pv <> '0.0.0.0') then
        Result := True;
end;

function WebView2Needed(): Boolean;
begin
  { Only run the bootstrapper when the runtime is missing AND we actually staged it. }
  Result := (not WebView2Installed()) and FileExists(ExpandConstant('{tmp}\{#WebView2Bootstrapper}'));
end;

{ --- VC++ 2015-2022 x64 runtime detection --- }
function VCRedistInstalled(): Boolean;
var
  installed: Cardinal;
begin
  Result := RegQueryDWordValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', installed) and (installed = 1);
end;

function VCRedistNeeded(): Boolean;
begin
  Result := (not VCRedistInstalled()) and FileExists(ExpandConstant('{tmp}\{#VCRedist}'));
end;

// Clean uninstall: stop running apps first (CloseApplications is install-only).
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    KillNexaProcesses;
end;

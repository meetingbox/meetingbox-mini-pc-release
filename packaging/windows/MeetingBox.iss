; Inno Setup script for the MeetingBox Windows desktop port.
; Build with:
;   "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" packaging\windows\MeetingBox.iss
; Produces: packaging\windows\Output\MeetingBoxSetup.exe
;
; Installs the PyInstaller one-dir payload (MeetingBox.exe + meetingbox-audio.exe
; + _internal\) into Program Files, seeds a per-machine device-ui.env under
; %PROGRAMDATA%\MeetingBox (only if absent, so upgrades keep the user's edits),
; and creates Start Menu / optional desktop shortcuts.

#define MyAppName "MeetingBox"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Lucratech Solutions"
#define MyAppExeName "MeetingBox.exe"
#define MyAppURL "https://meetingboxai.lucratechsol.com/"

; --- Second app: the MeetingBox Dashboard (Tauri + WebView2) ---------------
; Built separately (see BUILD.md): `npm run tauri:build` in the frontend produces
; this single self-contained exe. Path is relative to this .iss file
; (mini-pc\packaging\windows -> repo root -> frontend\...).
#define MyDashName "MeetingBox Dashboard"
#define MyDashExeName "MeetingBoxDashboard.exe"
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
AppId={{8B6E2C44-2E2C-49A2-9C9F-7F2E1B3A6D11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=MeetingBoxSetup
SetupIconFile=meetingbox.ico
; Programs & Features / uninstall icon: use the bundled brand .ico so the entry
; always shows the MeetingBox logo, independent of the exe's embedded icon.
UninstallDisplayIcon={app}\MeetingBox.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
; Both apps auto-start at login, so they're running during an upgrade. Close
; them automatically (Restart Manager) instead of showing the "files in use"
; prompt, and don't let Setup relaunch them (the Finish page / auto-start do).
CloseApplications=force
RestartApplications=no
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
Name: "startupicon"; Description: "Automatically start MeetingBox when I sign in to Windows"; GroupDescription: "Startup:"

[Registry]
; Login auto-start (per-machine; installer runs as admin). Only the Dashboard
; is registered: it is the primary app and spawns the companion itself.
; --minimized keeps it in the notification-area tray. Removed on uninstall.
; Stale value from older installs ("MeetingBox" -> companion) is deleted.
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "MeetingBox"; Flags: deletevalue
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "MeetingBoxDashboard"; ValueData: """{app}\Dashboard\{#MyDashExeName}"" --minimized"; Flags: uninsdeletevalue; Tasks: startupicon

[Files]
; The entire PyInstaller one-dir output (the MeetingBox companion app).
Source: "dist\MeetingBox\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; The MeetingBox Dashboard desktop app (single Tauri exe) into its own subfolder.
Source: "{#DashSrcDir}\{#MyDashExeName}"; DestDir: "{app}\Dashboard"; Flags: ignoreversion
; Edge WebView2 Evergreen bootstrapper — staged to {tmp}, run only if the runtime
; is missing (see [Run] + WebView2Needed), then deleted.
Source: "{#WebView2Bootstrapper}"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist
; Optional VC++ runtime — staged only if you drop the file next to the script.
Source: "{#VCRedist}"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist
; Open-source third-party license notices (OSS compliance).
Source: "THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
; Per-machine config seed (only copied if it does not already exist).
Source: "device-ui.env"; DestDir: "{commonappdata}\MeetingBox"; Flags: onlyifdoesntexist uninsneveruninstall
; Brand logo used as the explicit shortcut / uninstall icon.
Source: "{#BrandIcon}"; DestDir: "{app}"; DestName: "MeetingBox.ico"; Flags: ignoreversion skipifsourcedoesntexist

[Dirs]
Name: "{commonappdata}\MeetingBox"; Permissions: users-modify

[Icons]
; Single entry point: the Dashboard is the primary app (it launches the
; companion itself), so there is exactly ONE shortcut named "MeetingBox".
Name: "{group}\{#MyAppName}"; Filename: "{app}\Dashboard\{#MyDashExeName}"; WorkingDir: "{app}\Dashboard"; IconFilename: "{app}\MeetingBox.ico"
Name: "{group}\Edit MeetingBox configuration"; Filename: "notepad.exe"; Parameters: """{commonappdata}\MeetingBox\device-ui.env"""
Name: "{group}\Third-party notices"; Filename: "{app}\THIRD-PARTY-NOTICES.txt"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Dashboard\{#MyDashExeName}"; WorkingDir: "{app}\Dashboard"; IconFilename: "{app}\MeetingBox.ico"; Tasks: desktopicon

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

{ --- Clean uninstall: stop the running apps first ---------------------------
  Both apps auto-start and run in the background (the dashboard sits in the
  tray), so at uninstall time they're almost always running. CloseApplications
  only applies during install, so without this the processes keep running in
  Task Manager after uninstall and their locked files are left behind. Kill the
  companion (and its audio child, via /T) and the dashboard before files are
  removed. taskkill returns non-zero when a process isn't running, which is
  fine and ignored. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec(ExpandConstant('{sys}\taskkill.exe'),
      '/F /T /IM "{#MyAppExeName}" /IM "meetingbox-audio.exe" /IM "{#MyDashExeName}"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    { Give Windows a moment to release the file handles before deletion. }
    Sleep(700);
  end;
end;

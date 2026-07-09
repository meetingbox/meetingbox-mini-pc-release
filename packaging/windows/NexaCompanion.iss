; Inno Setup script — COMPANION-ONLY Nexa installer.
; Build with:
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" packaging\windows\NexaCompanion.iss
; Produces: packaging\windows\Output\NexaSetup.exe
;
; This variant ships ONLY the PyInstaller companion (Nexa.exe + nexa-audio.exe
; + _internal\). It intentionally omits the Tauri "Nexa Dashboard" (whose source
; is not present in this checkout). The companion runs standalone as the floating
; dock / 7-inch panel UI, so the Start-menu / desktop shortcut launches Nexa.exe
; directly.

#define MyAppName "Nexa"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Nexa"
#define MyAppExeName "Nexa.exe"
#define MyAudioExeName "nexa-audio.exe"
#define MyAppURL "https://win.meetingboxai.lucratechsol.com/"
; Brand logo used as the explicit shortcut / uninstall icon. The dedicated
; src-tauri brand .ico is absent in this checkout, so reuse the setup icon.
#define BrandIcon "meetingbox.ico"

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
UninstallDisplayIcon={app}\Nexa.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
; Silently taskkill our processes before copying files (in-place upgrade).
CloseApplications=no
RestartApplications=no
UsePreviousAppDir=yes
LicenseFile=EULA.rtf
#ifdef SIGN
SignTool=meetingbox
SignedUninstaller=yes
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Automatically start Nexa when I sign in to Windows"; GroupDescription: "Startup:"

[Registry]
; Login auto-start (per-machine; installer runs as admin). Removed on uninstall.
; Stale values from older MeetingBox / Dashboard installs are deleted.
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "MeetingBox"; Flags: deletevalue
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "MeetingBoxDashboard"; Flags: deletevalue
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "NexaDashboard"; Flags: deletevalue
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Nexa"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Files]
; The entire PyInstaller one-dir output (the Nexa companion app).
Source: "dist\Nexa\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Open-source third-party license notices (OSS compliance).
Source: "THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
; Per-machine config seed (only copied if it does not already exist).
Source: "device-ui.env"; DestDir: "{commonappdata}\Nexa"; Flags: onlyifdoesntexist uninsneveruninstall
; Brand logo used as the explicit shortcut / uninstall icon.
Source: "{#BrandIcon}"; DestDir: "{app}"; DestName: "Nexa.ico"; Flags: ignoreversion skipifsourcedoesntexist

[Dirs]
Name: "{commonappdata}\Nexa"; Permissions: users-modify

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\Nexa.ico"
Name: "{group}\Edit Nexa configuration"; Filename: "notepad.exe"; Parameters: """{commonappdata}\Nexa\device-ui.env"""
Name: "{group}\Third-party notices"; Filename: "{app}\THIRD-PARTY-NOTICES.txt"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\Nexa.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
// Stop our apps so upgrades/uninstalls never hit "files in use".
procedure KillNexaProcesses;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'),
    '/F /T /IM "{#MyAppExeName}" /IM "{#MyAudioExeName}" /IM "MeetingBox.exe" /IM "meetingbox-audio.exe"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(800);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  NeedsRestart := False;
  KillNexaProcesses;
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    KillNexaProcesses;
end;

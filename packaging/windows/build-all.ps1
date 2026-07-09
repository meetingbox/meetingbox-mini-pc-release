# Build companion + dashboard + NexaSetup.exe (full monorepo).
# Usage (from anywhere):
#   powershell -ExecutionPolicy Bypass -File C:\meetingbox\meetingbox\mini-pc\packaging\windows\build-all.ps1
# Options:
#   -SkipDashboard   Skip npm/tauri (reuse existing NexaDashboard.exe)
#   -Sign            Run sign.ps1 and ISCC with /DSIGN (requires code-signing cert)

param(
    [switch]$SkipDashboard,
    [switch]$Sign
)

$ErrorActionPreference = "Stop"
$WinPack = $PSScriptRoot
$MiniPc = (Resolve-Path (Join-Path $WinPack "..\..")).Path
$RepoRoot = (Resolve-Path (Join-Path $MiniPc "..")).Path
$Frontend = Join-Path $RepoRoot "frontend"
$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"

if (-not (Test-Path $Frontend)) {
    throw "frontend/ not found at $Frontend - use the full monorepo checkout."
}
if (-not (Test-Path $Iscc)) {
    throw "Inno Setup 6 not found. Install from https://jrsoftware.org/isdl.php"
}

$VenvPy = Join-Path $MiniPc "device-ui\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Write-Host "Creating device-ui venv..."
    py -3.11 -m venv (Join-Path $MiniPc "device-ui\.venv")
    if (-not (Test-Path $VenvPy)) { $VenvPy = Join-Path $MiniPc "device-ui\.venv\Scripts\python.exe" }
}
if (-not (Test-Path $VenvPy)) {
    throw "Python venv missing. Install Python 3.11 and run: py -3.11 -m venv mini-pc\device-ui\.venv"
}

Write-Host "=== 1/3 Companion (PyInstaller) ===" -ForegroundColor Cyan
Push-Location $MiniPc
& $VenvPy -m pip install -q -r device-ui\requirements.txt -r packaging\windows\requirements-build.txt
Get-Process Nexa, nexa-audio, MeetingBox, meetingbox-audio -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
foreach ($old in @("dist\Nexa", "dist\MeetingBox")) {
    $dist = Join-Path $WinPack $old
    if (Test-Path $dist) { Remove-Item -Recurse -Force $dist -ErrorAction SilentlyContinue }
}
& $VenvPy -m PyInstaller packaging\windows\MeetingBox.spec --noconfirm `
    --distpath packaging\windows\dist --workpath packaging\windows\build
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
Pop-Location

if (-not $SkipDashboard) {
    Write-Host "=== 2/3 Dashboard (Tauri) ===" -ForegroundColor Cyan
    $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
    Push-Location $Frontend
    npm ci
    if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
    npm run tauri:build
    if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
    Pop-Location
} else {
    Write-Host "=== 2/3 Dashboard skipped (-SkipDashboard) ===" -ForegroundColor Yellow
}

$DashExe = Join-Path $Frontend "src-tauri\target\release\NexaDashboard.exe"
if (-not (Test-Path $DashExe)) {
    throw "Missing $DashExe - build dashboard or remove -SkipDashboard."
}

$Wv2 = Join-Path $WinPack "MicrosoftEdgeWebview2Setup.exe"
if (-not (Test-Path $Wv2)) {
    Write-Warning "MicrosoftEdgeWebview2Setup.exe not beside MeetingBox.iss - installer still builds; WebView2 auto-install may be skipped."
}

if ($Sign) {
    Write-Host "=== Signing exes ===" -ForegroundColor Cyan
    & powershell -ExecutionPolicy Bypass -File (Join-Path $WinPack "sign.ps1")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "=== 3/3 Installer (Inno Setup) ===" -ForegroundColor Cyan
Push-Location $WinPack
if ($Sign) {
    # Single-quoted so PowerShell passes it verbatim: $f is an Inno Setup
    # placeholder (the file to sign) and must reach ISCC literally, not be
    # expanded by PowerShell.
    & $Iscc /DSIGN '/Ssigntool=signtool.exe sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a $f' MeetingBox.iss
} else {
    & $Iscc MeetingBox.iss
}
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { exit $code }

$Out = Join-Path $WinPack "Output\NexaSetup.exe"
Write-Host ""
Write-Host "Done: $Out" -ForegroundColor Green
if (Test-Path $Out) {
    $f = Get-Item $Out
    Write-Host ("  {0:N1} MB  {1}" -f ($f.Length / 1MB), $f.LastWriteTime)
}

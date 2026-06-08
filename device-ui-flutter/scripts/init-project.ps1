# One-time setup on Windows: generate Windows runner + fetch deps.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    Write-Host "Flutter SDK not found."
    Write-Host "Install: choco install flutter -y"
    Write-Host "Or: https://docs.flutter.dev/get-started/install/windows"
    exit 1
}

flutter config --enable-windows-desktop | Out-Null

if (-not (Test-Path "windows\runner\main.cpp")) {
    flutter create . --platforms=windows --project-name meetingbox_device_ui
}

& "$PSScriptRoot\sync-assets.ps1"
flutter pub get
Write-Host "Ready. Run: .\scripts\run-dev.ps1"

# Dev launch on Windows — windowed UI, optional mock backend.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    Write-Error "Flutter not on PATH. Run: choco install flutter -y then reopen terminal."
}

$backend = if ($env:BACKEND_URL) { $env:BACKEND_URL } else { "http://localhost:8000" }
$bridge = if ($env:DEVICE_BRIDGE_URL) { $env:DEVICE_BRIDGE_URL } else { "http://127.0.0.1:8765" }
$mock = if ($env:MOCK_BACKEND) { $env:MOCK_BACKEND } else { "1" }
$width = if ($env:DISPLAY_WIDTH) { $env:DISPLAY_WIDTH } else { "1260" }
$height = if ($env:DISPLAY_HEIGHT) { $env:DISPLAY_HEIGHT } else { "800" }
$fullscreen = if ($env:FULLSCREEN) { $env:FULLSCREEN } else { "0" }

Write-Host "MOCK_BACKEND=$mock (device bridge is Linux-only; use mock on Windows)"
flutter run -d windows `
  --dart-define=BACKEND_URL=$backend `
  --dart-define=DEVICE_BRIDGE_URL=$bridge `
  --dart-define=MOCK_BACKEND=$mock `
  --dart-define=DISPLAY_WIDTH=$width `
  --dart-define=DISPLAY_HEIGHT=$height `
  --dart-define=FULLSCREEN=$fullscreen

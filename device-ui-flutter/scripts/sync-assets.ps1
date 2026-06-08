# Copy shared assets + fonts from Kivy device-ui into the Flutter project.
$Root = Split-Path -Parent $PSScriptRoot
$Src = Join-Path $Root "..\device-ui\assets"

if (-not (Test-Path $Src)) {
    Write-Error "Source assets not found: $Src"
    exit 1
}

$Folders = @("welcome", "home", "recording", "processing", "summary", "brief", "calendar", "idle", "fonts")

foreach ($f in $Folders) {
    $SrcDir = Join-Path $Src $f
    if (-not (Test-Path $SrcDir)) { continue }
    $Dst = Join-Path $Root "assets\$f"
    New-Item -ItemType Directory -Force -Path $Dst | Out-Null
    Copy-Item -Path (Join-Path $SrcDir "*") -Destination $Dst -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Assets synced to $Root\assets"

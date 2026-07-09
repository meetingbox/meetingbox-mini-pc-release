<#
.SYNOPSIS
  Authenticode-signs the three Nexa executables with an EV (or OV)
  code-signing certificate using signtool (SHA-256 + RFC3161 timestamp).

.DESCRIPTION
  Run this AFTER building the appliance (PyInstaller) and the dashboard (Tauri),
  and BEFORE compiling the installer with ISCC. The installer itself and its
  uninstaller are signed by Inno Setup via the SignTool directive (see
  MeetingBox.iss + BUILD.md).

  EV certificates live on a hardware token / HSM. signtool selects the cert
  automatically (/a) or by the parameters below; the token PIN is prompted by
  its middleware (e.g. SafeNet) on first use.

.PARAMETER Thumbprint
  SHA-1 thumbprint of the code-signing cert in the Windows cert store.

.PARAMETER SubjectName
  Cert subject substring (used with /n) if you prefer name-based selection.

.PARAMETER TimestampUrl
  RFC3161 timestamp server. Defaults to DigiCert.

.PARAMETER Files
  Explicit list of files to sign. Defaults to the three Nexa exes.

.EXAMPLE
  # Auto-select the only code-signing cert on the token:
  .\sign.ps1

.EXAMPLE
  .\sign.ps1 -Thumbprint 0123456789ABCDEF0123456789ABCDEF01234567
#>
[CmdletBinding()]
param(
  [string]$Thumbprint,
  [string]$SubjectName,
  [string]$TimestampUrl = 'http://timestamp.digicert.com',
  [string[]]$Files
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Resolve-SignTool {
  $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  # Fall back to the newest signtool.exe under the Windows SDK.
  $roots = @("${env:ProgramFiles(x86)}\Windows Kits\10\bin", "$env:ProgramFiles\Windows Kits\10\bin")
  foreach ($root in $roots) {
    if (Test-Path $root) {
      $found = Get-ChildItem -Path $root -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\' } |
        Sort-Object FullName -Descending | Select-Object -First 1
      if ($found) { return $found.FullName }
    }
  }
  throw "signtool.exe not found. Install the Windows 10/11 SDK (Signing Tools)."
}

$signtool = Resolve-SignTool
Write-Host "Using signtool: $signtool"

if (-not $Files -or $Files.Count -eq 0) {
  $Files = @(
    (Join-Path $here 'dist\Nexa\Nexa.exe'),
    (Join-Path $here 'dist\Nexa\nexa-audio.exe'),
    (Join-Path $here '..\..\..\frontend\src-tauri\target\release\NexaDashboard.exe')
  )
}

# Build the cert-selection arguments.
$selectArgs = @()
if ($Thumbprint)      { $selectArgs = @('/sha1', $Thumbprint) }
elseif ($SubjectName) { $selectArgs = @('/n', $SubjectName) }
else                  { $selectArgs = @('/a') }  # auto-select

$failed = $false
foreach ($f in $Files) {
  $full = (Resolve-Path -LiteralPath $f -ErrorAction SilentlyContinue)
  if (-not $full) {
    Write-Warning "SKIP (missing): $f"
    $failed = $true
    continue
  }
  Write-Host "`nSigning: $full"
  & $signtool sign /fd SHA256 /tr $TimestampUrl /td SHA256 @selectArgs "$full"
  if ($LASTEXITCODE -ne 0) { $failed = $true; Write-Warning "sign FAILED: $full"; continue }

  & $signtool verify /pa /v "$full"
  if ($LASTEXITCODE -ne 0) { $failed = $true; Write-Warning "verify FAILED: $full" }
}

if ($failed) { Write-Error "One or more files failed to sign/verify."; exit 1 }
Write-Host "`nAll executables signed and verified." -ForegroundColor Green

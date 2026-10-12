# Adept UI installation bootstrap.
# This script does not download branch contents from GitHub.
# It runs only when an approved catalog and lifecycle manager are supplied.
# The public adeptui.org endpoints stay unpublished until release certification.

param(
  [string]$Catalog = $env:ADEPT_RELEASE_CATALOG,
  [string]$Manager = $env:ADEPT_LIFECYCLE_ROOT
)

$ErrorActionPreference = "Stop"

if (-not $Catalog -or -not $Manager -or -not $env:ADEPT_RELEASE_PAYLOAD) {
  Write-Host "Adept UI command-line installation is not published yet."
  Write-Host "Install only from the official command shown on https://adeptui.org."
  Write-Host "A GitHub branch is not an installation source."
  exit 2
}

$os = "windows"
$arch = if ([Environment]::Is64BitOperatingSystem) { "x64" } else { "unsupported" }
if ($arch -eq "unsupported") {
  Write-Host "Adept UI does not have a certified build for this Windows architecture."
  exit 3
}

Write-Host "Detected $os $arch."
$env:PYTHONPATH = $Manager
python -m adept_lifecycle install --catalog $Catalog --payload $env:ADEPT_RELEASE_PAYLOAD --noninteractive --no-shortcut
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

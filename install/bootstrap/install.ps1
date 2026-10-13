# Adept UI installation bootstrap.
# Official catalog: https://adeptui.org/releases/current.json
# A GitHub branch is not an installation source.
# The public command is not open until the owner pins the release manager hash.

$ErrorActionPreference = "Stop"

$CatalogUrl = if ($env:ADEPT_RELEASE_CATALOG) { $env:ADEPT_RELEASE_CATALOG } else { "https://adeptui.org/releases/current.json" }
# Both values stay empty until the owner publishes a signed release.
$PinnedManagerSha256 = ""
$PinnedPublicModulus = ""

if (-not [Environment]::Is64BitOperatingSystem) {
  Write-Host "Adept UI does not have a certified build for this Windows architecture."
  exit 3
}

Write-Host "Detected windows x64."
Write-Host "Release catalog: $CatalogUrl"

if (-not $PinnedManagerSha256 -or -not $PinnedPublicModulus) {
  Write-Host "Adept UI public installation is not open yet."
  Write-Host "Release signing is not pinned, so this command will not download or run anything."
  Write-Host "Install only from the official command shown on https://adeptui.org after publication."
  exit 2
}

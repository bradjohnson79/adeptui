#Requires -Version 5.1
param(
  [switch]$NoBrowser,
  [switch]$Foreground,
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$RepoRoot = (Resolve-Path $RepoRoot).Path
if ($Force) {
  & (Join-Path $RepoRoot "Stop-AdeptUI-Beta.ps1") -Force
} else {
  & (Join-Path $RepoRoot "Stop-AdeptUI-Beta.ps1")
}
Start-Sleep -Seconds 2
if ($Foreground) {
  if ($NoBrowser) {
    & (Join-Path $RepoRoot "Start-AdeptUI-Beta.ps1") -Foreground -NoBrowser
  } else {
    & (Join-Path $RepoRoot "Start-AdeptUI-Beta.ps1") -Foreground
  }
} elseif ($NoBrowser) {
  & (Join-Path $RepoRoot "Start-AdeptUI-Beta.ps1") -NoBrowser
} else {
  & (Join-Path $RepoRoot "Start-AdeptUI-Beta.ps1")
}
exit $LASTEXITCODE

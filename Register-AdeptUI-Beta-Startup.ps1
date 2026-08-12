#Requires -Version 5.1
<#
.SYNOPSIS
  Opt-in: register Adept UI Beta to start when the user signs into Windows.
  Does NOT enable automatically — owner must run this script.
#>
param(
  [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Startup = [Environment]::GetFolderPath("Startup")
$lnk = Join-Path $Startup "Adept UI Beta.lnk"
$Wsh = New-Object -ComObject WScript.Shell
$pwsh = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

if ($Unregister) {
  if (Test-Path $lnk) {
    Remove-Item $lnk -Force
    Write-Host "Removed startup shortcut: $lnk"
  } else {
    Write-Host "No startup shortcut present."
  }
  exit 0
}

$sc = $Wsh.CreateShortcut($lnk)
$sc.TargetPath = $pwsh
$sc.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$(Join-Path $RepoRoot 'Start-AdeptUI-Beta.ps1')`" -NoBrowser"
$sc.WorkingDirectory = $RepoRoot
$sc.Save()
Write-Host "Registered opt-in startup: $lnk"
Write-Host "Unregister later with: .\Register-AdeptUI-Beta-Startup.ps1 -Unregister"

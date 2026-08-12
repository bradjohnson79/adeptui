#Requires -Version 5.1
<#
.SYNOPSIS
  Install Desktop shortcuts for Adept UI Beta (Start / Stop / Restart / Open Logs).
#>
$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$Wsh = New-Object -ComObject WScript.Shell

$icon = Join-Path $RepoRoot "studio-web\public\favicon.svg"
# Prefer PNG hero as Windows .lnk icon fallback when no .ico
$iconPng = Join-Path $RepoRoot "studio-web\public\images\hero\Adept_UI_Hero_header.png"
$iconPath = if (Test-Path $iconPng) { $iconPng } else { $icon }

function New-Shortcut([string]$Name, [string]$TargetCmd, [string]$Args, [string]$WorkDir, [string]$Icon = $iconPath) {
  $path = Join-Path $Desktop "$Name.lnk"
  $sc = $Wsh.CreateShortcut($path)
  $sc.TargetPath = $TargetCmd
  $sc.Arguments = $Args
  $sc.WorkingDirectory = $WorkDir
  if ($Icon -and (Test-Path $Icon)) { $sc.IconLocation = $Icon }
  $sc.Save()
  Write-Host "Created $path"
}

$pwsh = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$flags = "-NoProfile -ExecutionPolicy Bypass -File"

New-Shortcut "Adept UI Beta" $pwsh "$flags `"$(Join-Path $RepoRoot 'Start-AdeptUI-Beta.ps1')`"" $RepoRoot
New-Shortcut "Stop Adept UI Beta" $pwsh "$flags `"$(Join-Path $RepoRoot 'Stop-AdeptUI-Beta.ps1')`"" $RepoRoot
New-Shortcut "Restart Adept UI Beta" $pwsh "$flags `"$(Join-Path $RepoRoot 'Restart-AdeptUI-Beta.ps1')`"" $RepoRoot
New-Shortcut "Open Adept UI Logs" "explorer.exe" "`"$(Join-Path $RepoRoot 'data\runtime\logs\beta')`"" $RepoRoot

Write-Host "Desktop shortcuts installed."

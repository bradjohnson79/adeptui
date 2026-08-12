#Requires -Version 5.1
<#
.SYNOPSIS
  Register the Adept UI Beta Backend Manager for Windows auto-start via Task Scheduler.
.DESCRIPTION
  Creates a hidden Task Scheduler task that starts the backend manager on logon.
  The task runs Watch-AdeptBetaBackend.ps1 in a detached background process.
  Opt-in: does not enable until this script is run explicitly.
#>
param(
  [string]$TaskName = "AdeptBetaBackendManager"
)

$ErrorActionPreference = "Stop"
$common = Join-Path $PSScriptRoot "scripts\beta-backend\BetaBackendCommon.ps1"
. $common

$watchScript = Join-Path $RepoRoot "Watch-AdeptBetaBackend.ps1"
$startScript = Join-Path $RepoRoot "Start-AdeptBetaBackend.ps1"

if (-not (Test-Path $watchScript)) { Write-Error "Watch script not found: $watchScript"; exit 1 }
if (-not (Test-Path $startScript)) { Write-Error "Start script not found: $startScript"; exit 1 }

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed existing task: $TaskName"
}

# Build the action: start the backend, then launch the watchdog
$actionScript = @"
`$ErrorActionPreference = 'Stop'
. '$startScript' -NoBrowser 2>&1 | Out-File -Append '$LogsDir\autostart.log' -Encoding UTF8
Start-Sleep -Seconds 5
`$proc = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','$watchScript' -WindowStyle Hidden -PassThru
"@

$bootstrapPath = Join-Path $StateDir "autostart_bootstrap.ps1"
Ensure-BetaBackendDirs
Set-Content -Path $bootstrapPath -Value $actionScript -Encoding UTF8

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$bootstrapPath`""

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Adept UI Beta Backend Manager - starts Studio API, ComfyUI, Cloudflare Tunnel, and watchdog on logon."

Write-Host ""
Write-Host "ADEPT UI BETA BACKEND - AUTO-START REGISTERED" -ForegroundColor Green
Write-Host "  Task:       $TaskName"
Write-Host "  Trigger:    At logon ($env:USERNAME)"
Write-Host "  Bootstrap:  $bootstrapPath"
Write-Host "  Watch:      $watchScript"
Write-Host ""
Write-Host "  The backend manager will start automatically on next logon."
Write-Host "  To test now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
exit 0

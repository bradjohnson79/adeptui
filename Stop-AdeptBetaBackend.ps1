#Requires -Version 5.1
<#
.SYNOPSIS
  Stop only the Adept UI Beta Backend Manager's owned processes.
.DESCRIPTION
  Reads PID files and stops only processes the manager started or adopted.
  Leaves unrelated Python, Node, Ollama, and user processes untouched.
#>
param([switch]$Force)

$ErrorActionPreference = "Stop"
$common = Join-Path $PSScriptRoot "scripts\beta-backend\BetaBackendCommon.ps1"
. $common

Ensure-BetaBackendDirs
Write-BetaLog "manager" "=== Stop-AdeptBetaBackend ==="

$stopped = @()
$failed  = @()

foreach ($svc in $Services) {
    $info = Read-ServicePid $svc
    if (-not $info) {
        Write-BetaLog $svc "No PID record - skipping."
        continue
    }
    if (-not $info.owned -and -not $Force) {
        Write-BetaLog $svc "Process was adopted (not owned) - skipping unless -Force. PID=$($info.pid)"
        continue
    }
    $ok = Stop-OwnedService $svc
    if ($ok) { $stopped += $svc } else { $failed += $svc }
}

Write-BackendState @{
    stopped_at = (Get-Date).ToUniversalTime().ToString("o")
    stopped    = $stopped
    failed     = $failed
}

Write-Host ""
Write-Host "ADEPT UI BETA BACKEND - STOP" -ForegroundColor Cyan
foreach ($svc in $Services) {
    $status = if ($svc -in $stopped) { "STOPPED" } elseif ($svc -in $failed) { "FAILED" } else { "N/A" }
    $color = if ($status -eq "STOPPED") { "Green" } elseif ($status -eq "FAILED") { "Red" } else { "Gray" }
    Write-Host "  $svc $status" -ForegroundColor $color
}
Write-Host ""

if ($failed.Count -eq 0) { exit 0 } else { exit 1 }

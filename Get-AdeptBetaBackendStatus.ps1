#Requires -Version 5.1
<#
.SYNOPSIS
  Print the status of all Adept UI Beta Backend services.
#>
$ErrorActionPreference = "Stop"
$common = Join-Path $PSScriptRoot "scripts\beta-backend\BetaBackendCommon.ps1"
. $common

Ensure-BetaBackendDirs

$studioApi  = Test-StudioApiHealth
$comfyui   = Test-ComfyUiHealth
$cloudflared = Test-CloudflareHealth
$ollama    = Test-OllamaHealth
$gpu       = Get-GpuInfo
$hostedApi = Test-CloudflareHealth

# Check for storm protection state
$stormBlocked = @()
foreach ($svc in $Services) {
    if (Test-StormProtection $svc) { $stormBlocked += $svc }
}

$overall = if ($studioApi -and $comfyui) { "READY" } else { "NOT READY" }

Write-Host ""
Write-Host "ADEPT UI BETA BACKEND" -ForegroundColor Cyan
Write-Host ""

function Write-StatusLine($label, $ok, $extra = "") {
    $status = if ($ok) { "ONLINE" } else { "OFFLINE" }
    $color = if ($ok) { "Green" } else { "Red" }
    $line = "  $label".PadRight(20) + $status
    if ($extra) { $line += "  $extra" }
    Write-Host $line -ForegroundColor $color
}

Write-StatusLine "Studio API" $studioApi
Write-StatusLine "ComfyUI" $comfyui
Write-StatusLine "Cloudflare Tunnel" $cloudflared
Write-StatusLine "Ollama" $ollama
if ($gpu) {
    Write-Host "  GPU               $gpu DETECTED" -ForegroundColor Green
} else {
    Write-Host "  GPU               NOT DETECTED" -ForegroundColor Red
}
Write-StatusLine "Hosted API" $hostedApi
Write-Host "  Overall           $overall" -ForegroundColor $(if ($studioApi -and $comfyui) { 'Green' } else { 'Red' })

if ($stormBlocked.Count -gt 0) {
    Write-Host ""
    Write-Host "  STORM-PROTECTED (restart paused): $($stormBlocked -join ', ')" -ForegroundColor Yellow
}

# PID info
Write-Host ""
Write-Host "  Owned processes:" -ForegroundColor Gray
foreach ($svc in $Services) {
    $info = Read-ServicePid $svc
    if ($info) {
        $alive = Test-ServicePidAlive $svc
        $pidStr = "PID $($info.pid)"
        if (-not $alive) { $pidStr += " (DEAD)" }
        $owned = if ($info.owned) { "owned" } else { "adopted" }
        Write-Host "    $svc".PadRight(20) "$pidStr ($owned)" -ForegroundColor Gray
    } else {
        Write-Host "    $svc".PadRight(20) "no PID record" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "  Logs:   $LogsDir" -ForegroundColor Gray
Write-Host "  State:  $StateDir" -ForegroundColor Gray
Write-Host ""

if ($studioApi -and $comfyui) { exit 0 } else { exit 1 }

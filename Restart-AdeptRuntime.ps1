#Requires -Version 5.1
<#
.SYNOPSIS
    Restart all owned Adept Runtime background services.
    Performs a clean stop then start of owned services.
#>
param(
    [switch]$NoBrowser,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ScriptHome = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$StopScript  = Join-Path $ScriptHome "Stop-AdeptRuntime.ps1"
$StartScript = Join-Path $ScriptHome "Start-AdeptRuntime.ps1"

Write-Host "`n=== Adept UI Background Runtime Manager â€” Restart ===`n" -ForegroundColor Cyan

# --- Stop phase ---
Write-Host "[PHASE 1] Stopping services..." -ForegroundColor Yellow
$stopArgs = @()
if ($Force) { $stopArgs += "-Force" }
& $StopScript @stopArgs

Write-Host "`nWaiting 3 seconds before restart...`n" -ForegroundColor Gray
Start-Sleep -Seconds 3

# --- Start phase ---
Write-Host "[PHASE 2] Starting services..." -ForegroundColor Yellow
& $StartScript

Write-Host "`n=== Restart Complete ===`n" -ForegroundColor Cyan

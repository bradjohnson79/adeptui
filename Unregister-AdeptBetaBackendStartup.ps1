#Requires -Version 5.1
<#
.SYNOPSIS
  Unregister the Adept UI Beta Backend Manager from Windows auto-start.
#>
param(
  [string]$TaskName = "AdeptBetaBackendManager"
)

$ErrorActionPreference = "Stop"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host ""
    Write-Host "ADEPT UI BETA BACKEND - AUTO-START UNREGISTERED" -ForegroundColor Yellow
    Write-Host "  Task: $TaskName removed."
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "ADEPT UI BETA BACKEND - AUTO-START" -ForegroundColor Cyan
    Write-Host "  Task: $TaskName not found - nothing to unregister."
    Write-Host ""
}

exit 0

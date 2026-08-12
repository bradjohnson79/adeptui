#Requires -Version 5.1
<#
.SYNOPSIS
    Remove the Adept Runtime Manager auto-start registration.
#>
param()

$ErrorActionPreference = "Stop"

$TaskName = "AdeptUI-Runtime-Manager"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $existing) {
    Write-Host "[INFO] No auto-start registration found for '$TaskName'" -ForegroundColor Gray
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

Write-Host "[OK] Adept Runtime auto-start unregistered." -ForegroundColor Green
Write-Host "  Task name: $TaskName" -ForegroundColor Gray

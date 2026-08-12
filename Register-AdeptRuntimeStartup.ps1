#Requires -Version 5.1
<#
.SYNOPSIS
    Register Adept Runtime Manager to start automatically at Windows login.
    Uses Task Scheduler (not Startup folder) for reliability across
    different Windows configurations.
    Opt-in only â€” does not run automatically after registration.
#>
param(
    [switch]$CurrentUserOnly = $true,
    [switch]$AtBoot
)

$ErrorActionPreference = "Stop"

$ScriptHome = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$StartScript = Join-Path $ScriptHome "Start-AdeptRuntime.ps1"
$TaskName = "AdeptUI-Runtime-Manager"

if (-not (Test-Path $StartScript)) {
    Write-Error "Start script not found: $StartScript"
    exit 1
}

$description = "Adept UI Background Runtime Manager â€” starts Studio API, ComfyUI headless, Cloudflare Tunnel, and checks Ollama"

$triggerArgs = @()
if ($AtBoot) {
    $triggerArgs = @("-AtStartup")
    $triggerDesc = "system boot"
} else {
    $triggerArgs = @("-AtLogOn")
    $triggerDesc = "user logon"
}
if ($CurrentUserOnly) {
    $triggerArgs += "-User", $env:USERNAME
}

# Check if task already exists
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[INFO] Task '$TaskName' already exists." -ForegroundColor Yellow
    $answer = Read-Host "Overwrite existing task? (y/N)"
    if ($answer -ne "y" -and $answer -ne "Y") {
        Write-Host "Cancelled."
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$StartScript`" -WindowStyle Hidden"
$trigger = if ($AtBoot) {
    New-ScheduledTaskTrigger -AtStartup
} else {
    New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
}
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -Hidden

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Limited
$task = New-ScheduledTask -Action $action -Principal $principal -Trigger $trigger -Settings $settings -Description $description

Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force

Write-Host ""
Write-Host "[OK] Adept Runtime auto-start registered." -ForegroundColor Green
Write-Host "  Task name: $TaskName" -ForegroundColor Gray
Write-Host "  Trigger:   At $triggerDesc" -ForegroundColor Gray
Write-Host "  Script:    $StartScript" -ForegroundColor Gray
Write-Host ""
Write-Host "To unregister: .\Unregister-AdeptRuntimeStartup.ps1" -ForegroundColor Yellow
Write-Host ""

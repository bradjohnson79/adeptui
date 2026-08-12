#Requires -Version 5.1
<#
.SYNOPSIS
  Restart one or all Adept UI Beta Backend services.
#>
param(
  [string]$Service = "all",
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$common = Join-Path $PSScriptRoot "scripts\beta-backend\BetaBackendCommon.ps1"
. $common

Ensure-BetaBackendDirs
$paths = Get-BetaBackendPaths

# Load Beta env files (mirrors old supervisor behavior)
$envApplied = Import-BetaEnv
Write-BetaLog "manager" "Loaded $($envApplied.Count) env vars from beta-local.env + beta-local.local.env"

Write-BetaLog "manager" "=== Restart-AdeptBetaBackend (service=$Service) ==="

$targets = if ($Service -eq "all") { $Services } else { @($Service) }

function Restart-OneService {
    param([string]$Svc)

    # Stop
    $info = Read-ServicePid $Svc
    if ($info -and ($info.owned -or $Force)) {
        Stop-OwnedService $Svc | Out-Null
    } elseif ($info -and -not $info.owned) {
        Write-BetaLog $Svc "Adopted process - stopping with -Force equivalent."
        Stop-OwnedService $Svc | Out-Null
    }
    Start-Sleep -Seconds 2

    # Start
    switch ($Svc) {
        "studio_api" {
            $py = $paths.StudioApiPython
            $apiDir = $paths.StudioApiDir
            if (-not (Test-Path $py)) { Write-BetaLog $Svc "venv Python not found." "ERROR"; return $false }
            $logFile = Join-Path $LogsDir "studio_api_stdout.log"
            $proc = Start-Process -FilePath $py -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8758" -WorkingDirectory $apiDir -WindowStyle Hidden -PassThru -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $LogsDir "studio_api_err.log")
            Write-ServicePid $Svc $proc.Id $proc.StartInfo.FileName
        }
        "comfyui" {
            $py = $paths.ComfyPython
            $installRoot = $paths.ComfyInstallRoot
            if (-not (Test-Path $py)) { Write-BetaLog $Svc "ComfyUI Python not found." "ERROR"; return $false }
            $logFile = Join-Path $LogsDir "comfyui_stdout.log"
            $cArgs = @("-s","ComfyUI\main.py","--enable-manager")
            if ($paths.ComfySharedPaths) { $cArgs += @("--extra-model-paths-config","`"$($paths.ComfySharedPaths)`"") }
            if ($paths.ComfyInputDir)  { $cArgs += @("--input-directory",$paths.ComfyInputDir) }
            if ($paths.ComfyOutputDir) { $cArgs += @("--output-directory",$paths.ComfyOutputDir) }
            $proc = Start-Process -FilePath $py -ArgumentList $cArgs -WorkingDirectory $installRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $LogsDir "comfyui_err.log")
            Write-ServicePid $Svc $proc.Id $proc.StartInfo.FileName
        }
        "cloudflared" {
            $cf = $paths.Cloudflared
            $cfg = $paths.TunnelConfig
            if (-not (Test-Path $cf)) { Write-BetaLog $Svc "cloudflared not found." "ERROR"; return $false }
            $logFile = Join-Path $LogsDir "cloudflared_stdout.log"
            $proc = Start-Process -FilePath $cf -ArgumentList "tunnel","--config","`"$cfg`"","run",$paths.TunnelName -WindowStyle Hidden -PassThru -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $LogsDir "cloudflared_err.log")
            Write-ServicePid $Svc $proc.Id $proc.StartInfo.FileName
        }
        "ollama" {
            $ol = $paths.Ollama
            if (-not (Test-Path $ol)) { Write-BetaLog $Svc "Ollama not found." "WARN"; return $false }
            $logFile = Join-Path $LogsDir "ollama_stdout.log"
            $proc = Start-Process -FilePath $ol -ArgumentList "serve" -WindowStyle Hidden -PassThru -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $LogsDir "ollama_err.log")
            Write-ServicePid $Svc $proc.Id $proc.StartInfo.FileName
        }
    }

    # Wait for health
    $timeout = switch ($Svc) { "comfyui" { 45 } "studio_api" { 60 } default { 20 } }
    $deadline = (Get-Date).AddSeconds($timeout)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if (Get-ServiceHealth $Svc) { Write-BetaLog $Svc "Restarted successfully."; return $true }
    }
    Write-BetaLog $Svc "Did not become healthy after restart." "ERROR"
    return $false
}

$results = @{}
foreach ($svc in $targets) {
    if ($svc -notin $Services) { Write-BetaLog "manager" "Unknown service: $svc" "WARN"; continue }
    $results[$svc] = Restart-OneService $svc
}

Write-Host ""
Write-Host "ADEPT UI BETA BACKEND - RESTART" -ForegroundColor Cyan
foreach ($svc in $results.Keys) {
    $status = if ($results[$svc]) { "ONLINE" } else { "FAILED" }
    $color = if ($results[$svc]) { "Green" } else { "Red" }
    Write-Host "  $svc $status" -ForegroundColor $color
}
Write-Host ""

$allOk = $true
foreach ($v in $results.Values) { if (-not $v) { $allOk = $false } }
if ($allOk) { exit 0 } else { exit 1 }

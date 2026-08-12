#Requires -Version 5.1
<#
.SYNOPSIS
  Continuous watchdog for the Adept UI Beta Backend.
.DESCRIPTION
  Monitors all managed services at a sane interval. Automatically restarts
  failed owned services with bounded retries, exponential backoff, and
  restart-storm protection. Survives terminal closure (run via Start-Process).
#>
param(
  [int]$IntervalSec = 15,
  [int]$MaxRestarts = 5,
  [int]$StormWindowSec = 300,
  [int]$BaseBackoffSec = 5,
  [switch]$Once
)

$ErrorActionPreference = "Stop"
$common = Join-Path $PSScriptRoot "scripts\beta-backend\BetaBackendCommon.ps1"
. $common

# Override storm protection params
$script:MaxRestarts    = $MaxRestarts
$script:StormWindowSec = $StormWindowSec
$script:BaseBackoffSec = $BaseBackoffSec

Ensure-BetaBackendDirs
$paths = Get-BetaBackendPaths

# Load Beta env files (mirrors old supervisor behavior)
$envApplied = Import-BetaEnv
Write-BetaLog "manager" "Loaded $($envApplied.Count) env vars from beta-local.env + beta-local.local.env"

Write-BetaLog "manager" "=== Watch-AdeptBetaBackend started (interval=${IntervalSec}s) ==="

# Backoff state per service
$backoffState = @{}
foreach ($svc in $Services) { $backoffState[$svc] = @{ consecutiveFailures = 0; nextRetryAt = $null } }

function Invoke-ServiceRestart {
    param([string]$Svc)

    # Storm protection
    if (Test-StormProtection $Svc) {
        Write-BetaLog $Svc "Storm protection active - max $MaxRestarts restarts in $StormWindowSec s. Pausing." "WARN"
        $backoffState[$Svc].nextRetryAt = (Get-Date).AddSeconds($StormWindowSec)
        return $false
    }

    # Backoff
    $failures = $backoffState[$Svc].consecutiveFailures
    $backoff = [Math]::Min($BaseBackoffSec * [Math]::Pow(2, $failures), 120)
    Write-BetaLog $Svc "Backing off ${backoff}s before restart (consecutive failures: $failures)."
    Start-Sleep -Seconds $backoff

    # Attempt restart
    Add-RestartEvent $Svc | Out-Null
    $info = Read-ServicePid $Svc
    if ($info) { Stop-OwnedService $Svc | Out-Null; Start-Sleep -Seconds 2 }

    $ok = switch ($Svc) {
        "studio_api" {
            $py = $paths.StudioApiPython; $apiDir = $paths.StudioApiDir
            if (-not (Test-Path $py)) { return $false }
            $logFile = Join-Path $LogsDir "studio_api_stdout.log"
            $proc = Start-Process -FilePath $py -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8758" -WorkingDirectory $apiDir -WindowStyle Hidden -PassThru -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $LogsDir "studio_api_err.log")
            Write-ServicePid $Svc $proc.Id $proc.StartInfo.FileName
            $deadline = (Get-Date).AddSeconds(30)
            while ((Get-Date) -lt $deadline) { Start-Sleep -Seconds 2; if (Test-StudioApiHealth) { return $true } }
            return $false
        }
        "comfyui" {
            $py = $paths.ComfyPython; $installRoot = $paths.ComfyInstallRoot
            if (-not (Test-Path $py)) { return $false }
            $logFile = Join-Path $LogsDir "comfyui_stdout.log"
            $cArgs = @("-s","ComfyUI\main.py","--enable-manager")
            if ($paths.ComfySharedPaths) { $cArgs += @("--extra-model-paths-config","`"$($paths.ComfySharedPaths)`"") }
            if ($paths.ComfyInputDir)  { $cArgs += @("--input-directory",$paths.ComfyInputDir) }
            if ($paths.ComfyOutputDir) { $cArgs += @("--output-directory",$paths.ComfyOutputDir) }
            $proc = Start-Process -FilePath $py -ArgumentList $cArgs -WorkingDirectory $installRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $LogsDir "comfyui_err.log")
            Write-ServicePid $Svc $proc.Id $proc.StartInfo.FileName
            $deadline = (Get-Date).AddSeconds(45)
            while ((Get-Date) -lt $deadline) { Start-Sleep -Seconds 3; if (Test-ComfyUiHealth) { return $true } }
            return $false
        }
        "cloudflared" {
            $cf = $paths.Cloudflared; $cfg = $paths.TunnelConfig
            if (-not (Test-Path $cf) -or -not (Test-Path $cfg)) { return $false }
            $logFile = Join-Path $LogsDir "cloudflared_stdout.log"
            $proc = Start-Process -FilePath $cf -ArgumentList "tunnel","--config","`"$cfg`"","run",$paths.TunnelName -WindowStyle Hidden -PassThru -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $LogsDir "cloudflared_err.log")
            Write-ServicePid $Svc $proc.Id $proc.StartInfo.FileName
            $deadline = (Get-Date).AddSeconds(20)
            while ((Get-Date) -lt $deadline) { Start-Sleep -Seconds 2; if (Test-CloudflareHealth) { return $true } }
            return $false
        }
        "ollama" {
            $ol = $paths.Ollama
            if (-not (Test-Path $ol)) { return $false }
            $logFile = Join-Path $LogsDir "ollama_stdout.log"
            $proc = Start-Process -FilePath $ol -ArgumentList "serve" -WindowStyle Hidden -PassThru -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $LogsDir "ollama_err.log")
            Write-ServicePid $Svc $proc.Id $proc.StartInfo.FileName
            $deadline = (Get-Date).AddSeconds(15)
            while ((Get-Date) -lt $deadline) { Start-Sleep -Seconds 2; if (Test-OllamaHealth) { return $true } }
            return $false
        }
    }
    return $ok
}

function Invoke-WatchCycle {
    $cycleResults = @{}
    foreach ($svc in $Services) {
        $healthy = Get-ServiceHealth $svc
        $cycleResults[$svc] = $healthy

        if ($healthy) {
            if ($backoffState[$svc].consecutiveFailures -gt 0) {
                Write-BetaLog $svc "Recovered after $($backoffState[$svc].consecutiveFailures) failure(s)."
            }
            $backoffState[$svc].consecutiveFailures = 0
            $backoffState[$svc].nextRetryAt = $null
        } else {
            # Service is down
            $info = Read-ServicePid $svc
            $isOwned = $info -and $info.owned

            if (-not $isOwned) {
                # Not our owned service - just report, don't restart
                Write-BetaLog $svc "Unhealthy but not owned - monitoring only." "WARN"
                continue
            }

            # Check backoff
            if ($backoffState[$svc].nextRetryAt -and (Get-Date) -lt $backoffState[$svc].nextRetryAt) {
                continue
            }

            $backoffState[$svc].consecutiveFailures++
            Write-BetaLog $svc "Service unhealthy - attempting restart #$($backoffState[$svc].consecutiveFailures)." "WARN"

            $restartOk = Invoke-ServiceRestart $svc
            if ($restartOk) {
                Write-BetaLog $svc "Restart succeeded."
                $backoffState[$svc].consecutiveFailures = 0
                $backoffState[$svc].nextRetryAt = $null
            } else {
                Write-BetaLog $svc "Restart failed." "ERROR"
                # Next retry with increased backoff
                $failures = $backoffState[$svc].consecutiveFailures
                $nextBackoff = [Math]::Min($BaseBackoffSec * [Math]::Pow(2, $failures), 120)
                $backoffState[$svc].nextRetryAt = (Get-Date).AddSeconds($nextBackoff)
            }
        }
    }

    # Update state
    $gpu = Get-GpuInfo
    Write-BackendState @{
        studio_api  = $cycleResults["studio_api"]
        comfyui     = $cycleResults["comfyui"]
        cloudflared = $cycleResults["cloudflared"]
        ollama      = $cycleResults["ollama"]
        gpu         = $gpu
        watchdog    = $true
    }

    return $cycleResults
}

# Main loop
if ($Once) {
    $results = Invoke-WatchCycle
    $allOk = $true
    foreach ($v in $results.Values) { if (-not $v) { $allOk = $false; break } }
    if ($allOk) { exit 0 } else { exit 1 }
} else {
    while ($true) {
        Invoke-WatchCycle | Out-Null
        Start-Sleep -Seconds $IntervalSec
    }
}

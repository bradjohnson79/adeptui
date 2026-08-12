#Requires -Version 5.1
<#
.SYNOPSIS
  Start the Adept UI Beta Backend Manager services.
.DESCRIPTION
  Starts Studio API, ComfyUI (headless), Cloudflare Tunnel, and verifies Ollama.
  Reuses already-healthy services. Prevents duplicate processes.
  Does NOT start the old :8760 Beta/Vite frontend.
#>
param(
  [switch]$Force,
  [switch]$NoCloudflare
)

$ErrorActionPreference = "Stop"
$common = Join-Path $PSScriptRoot "scripts\beta-backend\BetaBackendCommon.ps1"
. $common

Ensure-BetaBackendDirs
$paths = Get-BetaBackendPaths

# Load Beta env files (mirrors old supervisor behavior)
$envApplied = Import-BetaEnv
Write-BetaLog "manager" "Loaded $($envApplied.Count) env vars from beta-local.env + beta-local.local.env"

Write-BetaLog "manager" "=== Start-AdeptBetaBackend ==="

# ---------------------------------------------------------------------------
# 1. Studio API
# ---------------------------------------------------------------------------

function Start-StudioApi {
    if (Test-StudioApiHealth) {
        Write-BetaLog "studio_api" "Already healthy - reusing."
        $portPid = _Get-PortOwnerPid 8758
        if ($portPid) { Write-ServicePid "studio_api" $portPid "adopted" $true }
        return $true
    }
    $py = $paths.StudioApiPython
    $apiDir = $paths.StudioApiDir
    if (-not (Test-Path $py)) { Write-BetaLog "studio_api" "venv Python not found at $py" "ERROR"; return $false }
    $logFile = Join-Path $LogsDir "studio_api_stdout.log"
    Write-BetaLog "studio_api" "Starting uvicorn on :8758..."
    $proc = Start-Process -FilePath $py `
        -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8758" `
        -WorkingDirectory $apiDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $LogsDir "studio_api_err.log")
    Write-ServicePid "studio_api" $proc.Id $proc.StartInfo.FileName
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if (Test-StudioApiHealth) { Write-BetaLog "studio_api" "Healthy."; return $true }
    }
    Write-BetaLog "studio_api" "Did not become healthy within 60s." "ERROR"
    return $false
}

# ---------------------------------------------------------------------------
# 2. ComfyUI (headless - never opens Desktop GUI)
# ---------------------------------------------------------------------------

function Start-ComfyUi {
    if (Test-ComfyUiHealth) {
        Write-BetaLog "comfyui" "Already healthy - reusing."
        $portPid = _Get-PortOwnerPid 8188
        if ($portPid) { Write-ServicePid "comfyui" $portPid "adopted" $true }
        return $true
    }
    $py = $paths.ComfyPython
    $installRoot = $paths.ComfyInstallRoot
    if (-not (Test-Path $py)) { Write-BetaLog "comfyui" "ComfyUI Python not found." "ERROR"; return $false }
    $logFile = Join-Path $LogsDir "comfyui_stdout.log"
    $args = @("-s","ComfyUI\main.py","--enable-manager")
    if ($paths.ComfySharedPaths) { $args += @("--extra-model-paths-config", "`"$($paths.ComfySharedPaths)`"") }
    if ($paths.ComfyInputDir)  { $args += @("--input-directory", $paths.ComfyInputDir) }
    if ($paths.ComfyOutputDir) { $args += @("--output-directory", $paths.ComfyOutputDir) }
    Write-BetaLog "comfyui" "Starting ComfyUI headless on :8188..."
    $proc = Start-Process -FilePath $py -ArgumentList $args `
        -WorkingDirectory $installRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $LogsDir "comfyui_err.log")
    Write-ServicePid "comfyui" $proc.Id $proc.StartInfo.FileName
    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 3
        if (Test-ComfyUiHealth) { Write-BetaLog "comfyui" "Healthy."; return $true }
    }
    Write-BetaLog "comfyui" "Did not become healthy within 45s." "ERROR"
    return $false
}

# ---------------------------------------------------------------------------
# 3. Cloudflare Tunnel
# ---------------------------------------------------------------------------

function Start-Cloudflared {
    if ($NoCloudflare) { Write-BetaLog "cloudflared" "Skipped (-NoCloudflare)."; return $true }
    if (Test-CloudflareHealth) {
        Write-BetaLog "cloudflared" "Already healthy - reusing."
        $cfProc = Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" | Select-Object -First 1
        if ($cfProc) { Write-ServicePid "cloudflared" $cfProc.ProcessId "adopted" $true }
        return $true
    }
    $cf = $paths.Cloudflared
    $cfg = $paths.TunnelConfig
    $tunnelName = $paths.TunnelName
    if (-not (Test-Path $cf)) { Write-BetaLog "cloudflared" "cloudflared not found." "ERROR"; return $false }
    if (-not (Test-Path $cfg)) { Write-BetaLog "cloudflared" "Tunnel config not found." "ERROR"; return $false }
    $logFile = Join-Path $LogsDir "cloudflared_stdout.log"
    Write-BetaLog "cloudflared" "Starting tunnel '$tunnelName'..."
    $proc = Start-Process -FilePath $cf `
        -ArgumentList "tunnel","--config","`"$cfg`"","run",$tunnelName `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $LogsDir "cloudflared_err.log")
    Write-ServicePid "cloudflared" $proc.Id $proc.StartInfo.FileName
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if (Test-CloudflareHealth) { Write-BetaLog "cloudflared" "Healthy."; return $true }
    }
    Write-BetaLog "cloudflared" "Did not become healthy within 20s." "WARN"
    return $false
}

# ---------------------------------------------------------------------------
# 4. Ollama (check/adopt - may run as Windows service or user process)
# ---------------------------------------------------------------------------

function Start-Ollama {
    if (Test-OllamaHealth) {
        Write-BetaLog "ollama" "Already healthy - reusing."
        $olProc = Get-CimInstance Win32_Process -Filter "Name='ollama.exe'" | Select-Object -First 1
        if ($olProc) { Write-ServicePid "ollama" $olProc.ProcessId "adopted" $true }
        return $true
    }
    $ol = $paths.Ollama
    if (-not (Test-Path $ol)) { Write-BetaLog "ollama" "Ollama not found - skipping (optional)." "WARN"; return $false }
    Write-BetaLog "ollama" "Starting ollama serve..."
    $logFile = Join-Path $LogsDir "ollama_stdout.log"
    $proc = Start-Process -FilePath $ol -ArgumentList "serve" -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $LogsDir "ollama_err.log")
    Write-ServicePid "ollama" $proc.Id $proc.StartInfo.FileName
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if (Test-OllamaHealth) { Write-BetaLog "ollama" "Healthy."; return $true }
    }
    Write-BetaLog "ollama" "Did not become healthy within 15s." "WARN"
    return $false
}

# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------

$results = @{}
$results.studio_api  = Start-StudioApi
$results.comfyui    = Start-ComfyUi
$results.cloudflared = Start-Cloudflared
$results.ollama     = Start-Ollama

$allOk = $results.studio_api -and $results.comfyui
$tunnelOk = $results.cloudflared
$ollamaOk = $results.ollama

$gpu = Get-GpuInfo

Write-BackendState @{
    studio_api  = $results.studio_api
    comfyui     = $results.comfyui
    cloudflared = $results.cloudflared
    ollama      = $results.ollama
    gpu         = $gpu
}

Write-Host ""
Write-Host "ADEPT UI BETA BACKEND" -ForegroundColor Cyan
function _WriteSvcStatus($label, $ok) {
    $status = if ($ok) { "ONLINE" } else { "OFFLINE" }
    $color = if ($ok) { "Green" } else { "Red" }
    Write-Host "  $label".PadRight(20) $status -ForegroundColor $color
}
_WriteSvcStatus "Studio API"       $results.studio_api
_WriteSvcStatus "ComfyUI"          $results.comfyui
_WriteSvcStatus "Cloudflare Tunnel" $results.cloudflared
_WriteSvcStatus "Ollama"           $results.ollama
if ($gpu) { Write-Host "  GPU               $gpu DETECTED" -ForegroundColor Green }
$hostedApi = Test-CloudflareHealth
_WriteSvcStatus "Hosted API"       $hostedApi
$overall = if ($allOk) { "READY" } else { "NOT READY" }
$overallColor = if ($allOk) { "Green" } else { "Red" }
Write-Host "  Overall           $overall" -ForegroundColor $overallColor
Write-Host ""

if ($allOk) { exit 0 } else { exit 1 }

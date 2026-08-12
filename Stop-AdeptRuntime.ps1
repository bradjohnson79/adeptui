#Requires -Version 5.1
<#
.SYNOPSIS
    Stop only Adept Runtime managed background services (ComfyUI, Cloudflare
    Tunnel, Studio API) that were started by Start-AdeptRuntime.ps1.
    Uses stored PID files and command-line verification to avoid killing
    unrelated processes.
#>
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# --- Paths ----------------------------------------------------------------
$ScriptHome = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$RepoRoot    = (Resolve-Path (Join-Path $ScriptHome ".")).Path
$ConfigFile  = Join-Path $RepoRoot "config\runtime-manager.env"

# --- Helper: load env file ------------------------------------------------
function Load-EnvFile {
    param([string]$Path, [switch]$Optional)
    if (-not (Test-Path $Path)) {
        if (-not $Optional) { Write-Warning "Config not found: $Path" }
        return @{}
    }
    $result = @{}
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -and $line -notmatch '^\s*#') {
            $eq = $line.IndexOf('=')
            if ($eq -gt 0) {
                $key = $line.Substring(0, $eq).Trim()
                $val = $line.Substring($eq + 1).Trim()
                $result[$key] = $val
            }
        }
    }
    return $result
}

$config = Load-EnvFile $ConfigFile
$pidDir = if ($config['RUNTIME_PID_DIR']) { $config['RUNTIME_PID_DIR'] } else { "data/runtime/runtime-manager/pids" }
$apiPort = if ($config['STUDIO_API_PORT']) { $config['STUDIO_API_PORT'] } else { 8758 }
$comfyPort = if ($config['STUDIO_COMFY_PORT']) { $config['STUDIO_COMFY_PORT'] } else { 8188 }

if (-not ([System.IO.Path]::IsPathRooted($pidDir))) { $pidDir = Join-Path $RepoRoot $pidDir }

# --- Helper: wait for port to close ---------------------------------------
function Wait-PortFree {
    param([int]$Port, [int]$TimeoutSeconds = 15, [string]$Label = "port")
    $elapsed = 0
    while ($elapsed -lt $TimeoutSeconds * 1000) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $async = $tcp.BeginConnect("127.0.0.1", $Port, $null, $null)
            $waited = $async.AsyncWaitHandle.WaitOne(1000)
            if (-not $waited -or -not $tcp.Connected) {
                $tcp.Close()
                Write-Host "[OK] $Label port $Port is free after ${elapsed}ms" -ForegroundColor Green
                return $true
            }
            $tcp.EndConnect($async) | Out-Null
            $tcp.Close()
        } catch {
            Write-Host "[OK] $Label port $Port is free" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Milliseconds 1000
        $elapsed += 1000
    }
    Write-Warning "[TIMEOUT] $Label port $Port did not free within ${TimeoutSeconds}s"
    return $false
}

# --- Helper: kill by PID with verification ---------------------------------
function Stop-OwnedProcess {
    param([int]$Pid, [string]$ExpectedPattern, [string]$ServiceName)
    try {
        $proc = Get-Process -Id $Pid -ErrorAction Stop
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $Pid" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdLine -and $cmdLine -notmatch $ExpectedPattern) {
            Write-Warning "PID $Pid does not match expected pattern '$ExpectedPattern' â€” command line: $cmdLine"
            if (-not $Force) {
                Write-Warning "Skipping. Use -Force to override."
                return $false
            }
            Write-Warning "Force override â€” killing PID $Pid anyway"
        }
        $proc.Kill()
        Write-Host "[STOP] $ServiceName (PID $Pid) terminated" -ForegroundColor Yellow
        return $true
    } catch {
        if ($_.Exception.Message -match 'not found|does not exist|has exited') {
            Write-Host "[INFO] $ServiceName (PID $Pid) was already stopped" -ForegroundColor Gray
            return $true
        }
        throw
    }
}

# --- Helper: stop cloudflared by tunnel name ------------------------------
function Stop-CloudflareTunnel {
    param([string]$TunnelName)
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'cloudflared.exe'" -ErrorAction SilentlyContinue
    $matched = $procs | Where-Object { $_.CommandLine -match $TunnelName }
    if (-not $matched) {
        Write-Host "[INFO] No cloudflared tunnel '$TunnelName' process found" -ForegroundColor Gray
        return $true
    }
    foreach ($p in $matched) {
        try {
            $proc = Get-Process -Id $p.ProcessId -ErrorAction Stop
            $proc.Kill()
            Write-Host "[STOP] Cloudflare Tunnel '$TunnelName' (PID $($p.ProcessId)) terminated" -ForegroundColor Yellow
        } catch {
            if ($_.Exception.Message -match 'not found|has exited') {
                Write-Host "[INFO] Cloudflare Tunnel (PID $($p.ProcessId)) was already stopped" -ForegroundColor Gray
            } else { throw }
        }
    }
    return $true
}

# ==========================================================================
# MAIN
# ==========================================================================

Write-Host "`n=== Adept UI Background Runtime Manager â€” Stop ===`n" -ForegroundColor Cyan

$anyStopped = $false

# --- 1. Stop ComfyUI -------------------------------------------------------
Write-Host "--- ComfyUI ---" -ForegroundColor Yellow
$comfyPid = $null
$comfyPidPath = Join-Path $pidDir "comfy.pid"
if (Test-Path $comfyPidPath) {
    $content = (Get-Content $comfyPidPath -Raw).Trim()
    if ($content -match '^\d+$') { $comfyPid = [int]$content }
}
if ($comfyPid) {
    $stopped = Stop-OwnedProcess -Pid $comfyPid -ExpectedPattern "main\.py" -ServiceName "ComfyUI"
    if ($stopped) {
        Remove-Item $comfyPidPath -Force -ErrorAction SilentlyContinue
        $anyStopped = $true
    }
} else {
    # Fallback: find by command-line match
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue
    $comfyProcs = $procs | Where-Object { $_.CommandLine -match 'main\.py' -and $_.CommandLine -match '--port\s+' + $comfyPort }
    if ($comfyProcs) {
        foreach ($p in $comfyProcs) {
            try {
                $proc = Get-Process -Id $p.ProcessId -ErrorAction Stop
                Write-Warning "Found orphaned ComfyUI process (PID $($p.ProcessId)) â€” no PID file"
                if ($Force) {
                    $proc.Kill()
                    Write-Host "[STOP] Orphaned ComfyUI (PID $($p.ProcessId)) terminated" -ForegroundColor Yellow
                    $anyStopped = $true
                } else {
                    Write-Host "[SKIP] Use -Force to stop orphaned ComfyUI" -ForegroundColor Gray
                }
            } catch { }
        }
    } else {
        Write-Host "[INFO] No ComfyUI process found" -ForegroundColor Gray
    }
}

# --- 2. Stop Cloudflare Tunnel ---------------------------------------------
Write-Host "--- Cloudflare Tunnel ---" -ForegroundColor Yellow
$tunnelPid = $null
$tunnelPidPath = Join-Path $pidDir "tunnel.pid"
if (Test-Path $tunnelPidPath) {
    $content = (Get-Content $tunnelPidPath -Raw).Trim()
    if ($content -match '^\d+$') { $tunnelPid = [int]$content }
}
$tunnelName = if ($config['CLOUDFLARE_TUNNEL_NAME']) { $config['CLOUDFLARE_TUNNEL_NAME'] } else { "adept-ui-beta" }

if ($tunnelPid) {
    $stopped = Stop-OwnedProcess -Pid $tunnelPid -ExpectedPattern "cloudflared.*tunnel" -ServiceName "Cloudflare Tunnel"
    if ($stopped) {
        Remove-Item $tunnelPidPath -Force -ErrorAction SilentlyContinue
        $anyStopped = $true
    }
} else {
    $stopped = Stop-CloudflareTunnel -TunnelName $tunnelName
    if ($stopped -eq $true) { $anyStopped = $true }  # Stub â€” actual result tracked inside function
}

# --- 3. Stop Studio API (if we started it) ----------------------------------
Write-Host "--- Studio API ---" -ForegroundColor Yellow
$apiPid = $null
$apiPidPath = Join-Path $pidDir "api.pid"
if (Test-Path $apiPidPath) {
    $content = (Get-Content $apiPidPath -Raw).Trim()
    if ($content -match '^\d+$') { $apiPid = [int]$content }
}
if ($apiPid) {
    $stopped = Stop-OwnedProcess -Pid $apiPid -ExpectedPattern "uvicorn.*app\.main" -ServiceName "Studio API"
    if ($stopped) {
        Remove-Item $apiPidPath -Force -ErrorAction SilentlyContinue
        $anyStopped = $true
    }
} else {
    Write-Host "[INFO] No managed Studio API process (not started by this script)" -ForegroundColor Gray
}

# --- 4. Wait for ports to free (if we stopped anything) --------------------
if ($anyStopped) {
    Write-Host "`n--- Waiting for ports to free ---" -ForegroundColor Yellow
    $null = Wait-PortFree -Port $comfyPort -Label "ComfyUI"
    $null = Wait-PortFree -Port $apiPort -Label "Studio API"
}

# --- 5. Clean up PID directory if empty ------------------------------------
$remaining = Get-ChildItem -Path $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue
if (-not $remaining) {
    Remove-Item $pidDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] PID directory cleaned up" -ForegroundColor Green
} else {
    Write-Host "[INFO] Remaining PID files: $($remaining.Count)" -ForegroundColor Gray
    foreach ($f in $remaining) { Write-Host "  $($f.Name)" -ForegroundColor Gray }
}

Write-Host "`n=== Adept Runtime Stopped ===`n" -ForegroundColor Cyan

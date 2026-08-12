#Requires -Version 5.1
<#
.SYNOPSIS
  Shared configuration and helpers for the Adept UI Beta Backend Manager.
  Dot-sourced by all Beta-Backend scripts - never run directly.
#>

$script:RepoRoot = if ($PSScriptRoot) {
    # PSScriptRoot = .../AIVideoStudio/scripts/beta-backend
    # Go up 2 levels to reach the repo root
    (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
} else {
    (Resolve-Path $PWD.ProviderPath).Path
}

$script:StateDir   = Join-Path $script:RepoRoot ".runtime\beta-backend"
$script:PidDir     = Join-Path $script:StateDir "pids"
$script:StateFile  = Join-Path $script:StateDir "state.json"
$script:RestartLog = Join-Path $script:StateDir "restart_history.json"
$script:LogsDir    = Join-Path $script:RepoRoot "logs\runtime\beta-backend"

$script:Services = @("studio_api", "comfyui", "cloudflared", "ollama")

# Storm protection defaults
$script:MaxRestarts    = 5
$script:StormWindowSec = 300
$script:BaseBackoffSec = 5

# ---------------------------------------------------------------------------
# Discover executable paths from the machine
# ---------------------------------------------------------------------------

function Get-BetaBackendPaths {
    $paths = @{}

    # Studio API venv Python
    $apiVenv = Join-Path $script:RepoRoot "studio-api\.venv\Scripts\python.exe"
    $paths.StudioApiPython = if (Test-Path $apiVenv) { $apiVenv } else { $null }
    $paths.StudioApiDir = Join-Path $script:RepoRoot "studio-api"

    # ComfyUI - discover from Comfy Desktop install
    $comfyDesktopRoot = Join-Path $env:LOCALAPPDATA "Comfy-Desktop\ComfyUI-Installs"
    $comfyFound = $false
    if (Test-Path $comfyDesktopRoot) {
        Get-ChildItem $comfyDesktopRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            if ($comfyFound) { return }
            $installDir = Join-Path $_.FullName "ComfyUI"
            $mainPy = Join-Path $installDir "main.py"
            $venvPy = Join-Path $installDir ".venv\Scripts\python.exe"
            if ((Test-Path $mainPy) -and (Test-Path $venvPy)) {
                $paths.ComfyInstallRoot = $_.FullName
                $paths.ComfyRoot = $installDir
                $paths.ComfyPython = $venvPy
                $paths.ComfyMainPy = $mainPy
                $comfyFound = $true
            }
        }
    }
    if (-not $comfyFound) {
        $standaloneMain = Join-Path $script:RepoRoot "comfyui\main.py"
        if (Test-Path $standaloneMain) {
            $paths.ComfyRoot = Join-Path $script:RepoRoot "comfyui"
            $paths.ComfyPython = (Get-Command python -ErrorAction SilentlyContinue).Source
            $paths.ComfyMainPy = $standaloneMain
            $paths.ComfyInstallRoot = $paths.ComfyRoot
        }
    }

    # ComfyUI shared model paths
    $comfySharedPaths = Join-Path $env:APPDATA "Comfy Desktop\shared_model_paths.yaml"
    $paths.ComfySharedPaths = if (Test-Path $comfySharedPaths) { $comfySharedPaths } else { $null }

    $comfySharedBase = Join-Path $env:LOCALAPPDATA "Comfy-Desktop\ComfyUI-Shared"
    $paths.ComfyInputDir  = Join-Path $comfySharedBase "input"
    $paths.ComfyOutputDir = Join-Path $comfySharedBase "output"

    # cloudflared
    $cfCmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cfCmd) {
        $paths.Cloudflared = $cfCmd.Source
    } else {
        $cfPath = Join-Path ${env:ProgramFiles(x86)} "cloudflared\cloudflared.exe"
        $paths.Cloudflared = if (Test-Path $cfPath) { $cfPath } else { $null }
    }

    # Cloudflare tunnel config
    $tunnelConfig = Join-Path $script:RepoRoot "config\cloudflared\adept-ui-beta-tunnel.yml"
    $paths.TunnelConfig = if (Test-Path $tunnelConfig) { $tunnelConfig } else { $null }
    $paths.TunnelName = "adept-ui-beta"

    # Ollama
    $olCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($olCmd) {
        $paths.Ollama = $olCmd.Source
    } else {
        $olPath = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
        $paths.Ollama = if (Test-Path $olPath) { $olPath } else { $null }
    }

    return $paths
}

# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

function Ensure-BetaBackendDirs {
    foreach ($d in @($script:StateDir, $script:PidDir, $script:LogsDir)) {
        if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
    }
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

function Write-BetaLog {
    param([Parameter(Mandatory)][string]$Service, [Parameter(Mandatory)][string]$Message, [string]$Level = "INFO")
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $line = "[$ts] [$Level] [$Service] $Message"
    $logFile = Join-Path $script:LogsDir "$Service.log"
    if (-not (Test-Path $script:LogsDir)) { New-Item -ItemType Directory -Path $script:LogsDir -Force | Out-Null }
    try { Add-Content -Path $logFile -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue } catch {}
    try { Add-Content -Path (Join-Path $script:LogsDir "manager.log") -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue } catch {}
    Write-Host $line
}

# ---------------------------------------------------------------------------
# PID file helpers
# ---------------------------------------------------------------------------

function Write-ServicePid {
    param([string]$Service, [int]$ProcessId, [string]$CmdLine = "", [bool]$Owned = $true)
    Ensure-BetaBackendDirs
    $pidFile = Join-Path $script:PidDir "$Service.pid"
    $data = [pscustomobject]@{ pid = $ProcessId; cmdLine = $CmdLine; startedAt = (Get-Date).ToUniversalTime().ToString("o"); owned = $Owned } | ConvertTo-Json -Compress
    Set-Content -Path $pidFile -Value $data -Encoding UTF8
}

function Read-ServicePid {
    param([string]$Service)
    $pidFile = Join-Path $script:PidDir "$Service.pid"
    if (-not (Test-Path $pidFile)) { return $null }
    try { return Get-Content $pidFile -Raw | ConvertFrom-Json } catch { return $null }
}

function Remove-ServicePid {
    param([string]$Service)
    $pidFile = Join-Path $script:PidDir "$Service.pid"
    if (Test-Path $pidFile) { Remove-Item $pidFile -Force -ErrorAction SilentlyContinue }
}

function Test-ServicePidAlive {
    param([string]$Service)
    $info = Read-ServicePid $Service
    if (-not $info) { return $false }
    return [bool](Get-Process -Id $info.pid -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

function Test-StudioApiHealth {
    try { $r = Invoke-WebRequest -Uri "http://127.0.0.1:8758/api/healthz" -UseBasicParsing -TimeoutSec 5; return ($r.StatusCode -eq 200) } catch { return $false }
}

function Test-ComfyUiHealth {
    try { $r = Invoke-WebRequest -Uri "http://127.0.0.1:8188/system_stats" -UseBasicParsing -TimeoutSec 5; return ($r.StatusCode -eq 200) } catch { return $false }
}

function Test-CloudflareHealth {
    try { $r = Invoke-WebRequest -Uri "https://api-beta.adeptui.org/api/healthz" -UseBasicParsing -TimeoutSec 10; return ($r.StatusCode -eq 200) } catch { return $false }
}

function Test-OllamaHealth {
    try { $r = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 5; return ($r.StatusCode -eq 200) } catch { return $false }
}

function Get-ServiceHealth {
    param([string]$Service)
    switch ($Service) {
        "studio_api"  { return Test-StudioApiHealth }
        "comfyui"     { return Test-ComfyUiHealth }
        "cloudflared" { return Test-CloudflareHealth }
        "ollama"      { return Test-OllamaHealth }
        default       { return $false }
    }
}

# ---------------------------------------------------------------------------
# GPU detection
# ---------------------------------------------------------------------------

function Get-GpuInfo {
    try {
        $h = Invoke-WebRequest -Uri "http://127.0.0.1:8758/api/comfy/health" -UseBasicParsing -TimeoutSec 10
        $j = $h.Content | ConvertFrom-Json
        if ($j.devices -and $j.devices.Count -gt 0) { return ($j.devices[0].name -replace " :.*","") }
    } catch {}
    try { $smi = & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null; if ($smi) { return ($smi -replace "`r`n","").Trim() } } catch {}
    return $null
}

# ---------------------------------------------------------------------------
# Port owner PID helper
# ---------------------------------------------------------------------------

function _Get-PortOwnerPid {
    param([int]$Port)
    try {
        $line = netstat -ano | Select-String ":$Port.*LISTENING" | Select-Object -First 1
        if ($line) { return [int]($line -replace '.*LISTENING\s+','').Trim() }
    } catch {}
    return $null
}

# ---------------------------------------------------------------------------
# Restart history / storm protection
# ---------------------------------------------------------------------------

function Read-RestartHistory {
    if (-not (Test-Path $script:RestartLog)) { return @() }
    try { return @(Get-Content $script:RestartLog -Raw | ConvertFrom-Json) } catch { return @() }
}

function Write-RestartHistory {
    param([array]$History)
    Ensure-BetaBackendDirs
    $History | ConvertTo-Json -Depth 5 | Set-Content -Path $script:RestartLog -Encoding UTF8
}

function Add-RestartEvent {
    param([string]$Service)
    $history = @(Read-RestartHistory)
    $now = [datetimeoffset]::UtcNow.ToUnixTimeSeconds()
    $history += [pscustomobject]@{ service = $Service; timestamp = $now }
    $cutoff = $now - 3600
    $history = @($history | Where-Object { $_.timestamp -ge $cutoff })
    Write-RestartHistory $history
    return $history
}

function Test-StormProtection {
    param([string]$Service)
    $history = @(Read-RestartHistory | Where-Object { $_.service -eq $Service })
    $now = [datetimeoffset]::UtcNow.ToUnixTimeSeconds()
    $cutoff = $now - $script:StormWindowSec
    $recent = @($history | Where-Object { $_.timestamp -ge $cutoff })
    return ($recent.Count -ge $script:MaxRestarts)
}

# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------

function Write-BackendState {
    param([hashtable]$State)
    Ensure-BetaBackendDirs
    $State.timestamp = (Get-Date).ToUniversalTime().ToString("o")
    $State | ConvertTo-Json -Depth 5 | Set-Content -Path $script:StateFile -Encoding UTF8
}

function Read-BackendState {
    if (-not (Test-Path $script:StateFile)) { return @{} }
    try { return Get-Content $script:StateFile -Raw | ConvertFrom-Json -AsHashtable } catch { return @{} }
}

# ---------------------------------------------------------------------------
# Environment file loading (mirrors scripts/beta_runtime/envutil.py)
# ---------------------------------------------------------------------------

function Import-BetaEnv {
    <#
    .SYNOPSIS
      Load config/beta-local.env and config/beta-local.local.env into the
      current process environment, matching the old supervisor behavior.
    #>
    $envFiles = @(
        (Join-Path $script:RepoRoot "config\beta-local.env"),
        (Join-Path $script:RepoRoot "config\beta-local.local.env")
    )
    $applied = @{}
    foreach ($file in $envFiles) {
        if (-not (Test-Path $file)) { continue }
        foreach ($line in (Get-Content $file -Encoding UTF8)) {
            $line = $line.Trim()
            if (-not $line -or $line.StartsWith("#")) { continue }
            $eq = $line.IndexOf("=")
            if ($eq -lt 1) { continue }
            $key = $line.Substring(0, $eq).Trim()
            $val = $line.Substring($eq + 1).Trim()
            # Strip surrounding quotes
            if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
                $val = $val.Substring(1, $val.Length - 2)
            }
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
            $applied[$key] = $val
        }
    }
    return $applied
}

# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------

function Stop-OwnedService {
    param([string]$Service)
    $info = Read-ServicePid $Service
    if (-not $info) { Write-BetaLog $Service "No PID record - nothing to stop."; return $true }
    $pidVal = [int]$info.pid
    $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
    if (-not $proc) { Write-BetaLog $Service "Process $pidVal already gone."; Remove-ServicePid $Service; return $true }
    try { taskkill /F /T /PID $pidVal 2>$null | Out-Null; Start-Sleep -Seconds 3 } catch {}
    $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
    if ($proc) { try { Stop-Process -Id $pidVal -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2 } catch {} }
    $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
    if ($proc) { Write-BetaLog $Service "Failed to stop process $pidVal." "WARN"; return $false }
    Write-BetaLog $Service "Stopped process $pidVal."
    Remove-ServicePid $Service
    # Wait for file handles to be released
    Start-Sleep -Seconds 1
    return $true
}

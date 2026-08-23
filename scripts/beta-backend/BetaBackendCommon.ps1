#Requires -Version 5.1
<#
.SYNOPSIS
  Shared configuration and helpers for the Adept UI Beta Backend Manager.
  Dot-sourced by all Beta-Backend scripts - never run directly.
#>

function Resolve-AdeptRepoRoot {
    # Walk up from this script until studio-api/ is found.
    # Required because Restart-AdeptBetaBackend.ps1 is also copied under
    # .adept-tmp\setup-api-key-deploy\, where "..\.." is NOT the repo root.
    $start = if ($PSScriptRoot) { $PSScriptRoot } else { $PWD.ProviderPath }
    $cursor = (Resolve-Path $start).Path
    while ($cursor) {
        $apiDir = Join-Path $cursor "studio-api"
        $apiApp = Join-Path $apiDir "app"
        $apiPy  = Join-Path $apiDir ".venv\Scripts\python.exe"
        # Require the venv interpreter. .adept-tmp deploy copies have studio-api/app
        # but no .venv — those must not win over the real repo root.
        if ((Test-Path $apiDir) -and (Test-Path $apiApp) -and (Test-Path $apiPy)) {
            return $cursor
        }
        $parent = Split-Path $cursor -Parent
        if (-not $parent -or $parent -eq $cursor) { break }
        $cursor = $parent
    }
    if ($PSScriptRoot) {
        return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    }
    return (Resolve-Path $PWD.ProviderPath).Path
}

$script:RepoRoot = Resolve-AdeptRepoRoot else {
    (Resolve-Path $PWD.ProviderPath).Path
}

$script:StateDir   = Join-Path $script:RepoRoot ".runtime\beta-backend"
$script:PidDir     = Join-Path $script:StateDir "pids"
$script:StateFile  = Join-Path $script:StateDir "state.json"
$script:RestartLog = Join-Path $script:StateDir "restart_history.json"
$script:LogsDir    = Join-Path $script:RepoRoot "logs\runtime\beta-backend"
$script:RestartLockFile = Join-Path $script:StateDir "restart.lock"

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


function Set-BetaRestartLock {
    param([string]$Service = "all")
    Ensure-BetaBackendDirs
    # Phase 7: single-instance lifecycle lock - EXCLUSIVE claim. A live holder
    # (another Start/Restart/Watchdog operation) refuses concurrent work so two
    # operations can never race on stop/start and stack duplicate processes.
    if (Test-Path $script:RestartLockFile) {
        try {
            $info = Get-Content $script:RestartLockFile -Raw | ConvertFrom-Json
            if ($info.holderPid -and (Get-Process -Id $info.holderPid -ErrorAction SilentlyContinue)) {
                if ($info.holderPid -ne $PID) {
                    Write-BetaLog "manager" "Lifecycle lock held by live PID $($info.holderPid) - refusing concurrent operation." "WARN"
                    return $false
                }
            } else {
                # Stale lock (holder died) - reclaim.
                Remove-Item $script:RestartLockFile -Force -ErrorAction SilentlyContinue
            }
        } catch { Remove-Item $script:RestartLockFile -Force -ErrorAction SilentlyContinue }
    }
    # Atomic claim: CreateNew fails if the file appeared between test and create.
    try {
        $fs = [System.IO.File]::Open($script:RestartLockFile, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        $fs.Close()
    } catch {
        Write-BetaLog "manager" "Lifecycle lock raced - another operation claimed it. Refusing." "WARN"
        return $false
    }
    $data = [pscustomobject]@{ service = $Service; holderPid = $PID; at = (Get-Date).ToUniversalTime().ToString("o") } | ConvertTo-Json -Compress
    Set-Content -Path $script:RestartLockFile -Value $data -Encoding UTF8
    return $true
}

function Test-BetaRestartLock {
    if (-not (Test-Path $script:RestartLockFile)) { return $false }
    try {
        $info = Get-Content $script:RestartLockFile -Raw | ConvertFrom-Json
        if ($info.holderPid -and -not (Get-Process -Id $info.holderPid -ErrorAction SilentlyContinue)) {
            Remove-Item $script:RestartLockFile -Force -ErrorAction SilentlyContinue
            return $false
        }
        return $true
    } catch { return $false }
}

function Clear-BetaRestartLock {
    if (Test-Path $script:RestartLockFile) {
        try {
            $info = Get-Content $script:RestartLockFile -Raw | ConvertFrom-Json
            if ($info.holderPid -and $info.holderPid -ne $PID) { return }  # not ours - leave it
        } catch {}
        Remove-Item $script:RestartLockFile -Force -ErrorAction SilentlyContinue
    }
}

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

# ---------------------------------------------------------------------------
# Authoritative Studio API process identity (ONE owner, ONE port).
#
# A netstat LISTENING entry is NOT sufficient proof a process is the Studio
# API: the owning PID may be a phantom (socket survives a dead/hung process
# that taskkill cannot reach). Every lifecycle decision must distinguish:
#   - reachable Studio API process (Get-Process + /api/healthz)
#   - reachable but unrelated process (Get-Process, not uvicorn)
#   - phantom / unreachable owner (in netstat, NOT in Get-Process)
# ---------------------------------------------------------------------------

function Get-PortOwnerPid {
    param([int]$Port)
    try {
        $line = netstat -ano | Select-String ":$Port.*LISTENING" | Select-Object -First 1
        if (-not $line) { return $null }
        $parts = ($line.ToString() -split "\s+") | Where-Object { $_ }
        if ($parts.Count -lt 2) { return $null }
        $pidVal = 0
        if ([int]::TryParse($parts[-1], [ref]$pidVal) -and $pidVal -gt 0) { return $pidVal }
        return $null
    } catch { return $null }
}

function Test-PortIsFree {
    param([int]$Port)
    $owner = Get-PortOwnerPid $Port
    return ($null -eq $owner)
}

function Wait-PortReleased {
    param([int]$Port, [int]$TimeoutSec = 15)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortIsFree $Port) { return $true }
        Start-Sleep -Seconds 1
    }
    return (Test-PortIsFree $Port)
}

# Classify the :8758 owner. Returns:
#   healthy   - reachable Studio API answering /api/healthz
#   ours      - reachable process whose command line matches uvicorn app.main
#   reachable - reachable process that is NOT the Studio API
#   phantom   - in netstat but NOT in Get-Process (orphaned socket)
function Get-StudioApiPortState {
    $owner = Get-PortOwnerPid 8758
    if (-not $owner) { return @{ state = "free"; pid = $null } }
    $proc = Get-Process -Id $owner -ErrorAction SilentlyContinue
    if (-not $proc) { return @{ state = "phantom"; pid = $owner } }
    $healthy = Test-StudioApiHealth
    if ($healthy) { return @{ state = "healthy"; pid = $owner; healthy = $true } }
    $cmd = ""
    try { $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$owner" -ErrorAction SilentlyContinue; $cmd = [string]$cim.CommandLine } catch {}
    $isUvicorn = ($cmd -match "uvicorn" -and $cmd -match "app.main")
    if ($isUvicorn) { return @{ state = "starting"; pid = $owner; healthy = $false; cmd = $cmd } }
    return @{ state = "unrelated"; pid = $owner; cmd = $cmd }
}


function Test-ComfyUiHealth {
    # Official SenseNova (and similar) loaders block the prompt worker for many
    # minutes while still serving /queue. A 5s /system_stats miss is not a dead
    # Comfy and must not drive a watchdog kill mid-load.
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8188/system_stats" -UseBasicParsing -TimeoutSec 15
        if ($r.StatusCode -eq 200) { return $true }
    } catch { }
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8188/queue" -UseBasicParsing -TimeoutSec 15
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Test-CloudflareHealth {
    # Phase 13: the tunnel's health is the tunnel PROCESS, not the API behind it.
    # A dead API must never drive cloudflared restart churn. If no tunnel PID is
    # recorded, fall back to the tunnel hostname only if the API is healthy.
    $info = Read-ServicePid "cloudflared"
    if ($info) {
        $proc = Get-Process -Id $info.pid -ErrorAction SilentlyContinue
        if ($proc) { return $true }
        return $false
    }
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


function Clear-StalePortOwner {
    param([int]$Port)
    $portPid = Get-PortOwnerPid $Port
    if (-not $portPid) { return $true }
    $proc = Get-Process -Id $portPid -ErrorAction SilentlyContinue
    if (-not $proc) {
        # Phantom / orphaned socket: the PID is in netstat but the process is
        # gone or unreachable. It MUST be surfaced as a hard failure with the
        # exact recovery command - silently proceeding causes a bind collision
        # that reads as a false "Did not become healthy".
        Write-BetaLog "studio_api" "Port $Port held by PHANTOM PID $portPid (in netstat, no live process). Run: taskkill /F /PID $portPid (elevated) or reboot." "ERROR"
        return $false
    }
    $cmd = ""
    try { $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$portPid" -ErrorAction SilentlyContinue; $cmd = [string]$cim.CommandLine } catch {}
    if ($cmd -notmatch "uvicorn" -or $cmd -notmatch "--port\s+$Port") {
        Write-BetaLog "studio_api" "Port $Port held by PID $portPid - not studio uvicorn, leaving it." "WARN"
        return $false
    }
    Write-BetaLog "studio_api" "Clearing stale uvicorn on :$Port (PID $portPid)."
    try { taskkill /F /T /PID $portPid 2>$null | Out-Null; Start-Sleep -Seconds 2 } catch {}
    return (Test-PortIsFree $Port)
}

# ---------------------------------------------------------------------------
# Restart history / storm protection
# ---------------------------------------------------------------------------

function Read-RestartHistory {
    if (-not (Test-Path $script:RestartLog)) { return @() }
    try { $parsed = Get-Content $script:RestartLog -Raw | ConvertFrom-Json; if ($null -eq $parsed) { return @() }; return @($parsed) } catch { return @() }
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

# Phase 6 - PID identity verification.
# A pid-file PID must NEVER be killed on the number alone: Windows reuses PIDs.
# Verify the process matches the service signature (cmdline) or owns the port.
function Test-ProcessIdentity {
    param([string]$Service, [int]$ProcId)
    $cmd = ""
    try { $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcId" -ErrorAction SilentlyContinue; $cmd = [string]$cim.CommandLine } catch {}
    switch ($Service) {
        "studio_api" {
            if ($cmd -match "uvicorn" -and $cmd -match "app.main") { return $true }
            $owner = Get-PortOwnerPid 8758
            return ($owner -eq $ProcId)
        }
        "comfyui" {
            if ($cmd -match "ComfyUI" -and $cmd -match "main.py") { return $true }
            $owner = Get-PortOwnerPid 8188
            return ($owner -eq $ProcId)
        }
        "cloudflared" { return ($cmd -match "cloudflared") }
        "ollama" {
            if ($cmd -match "ollama") { return $true }
            $owner = Get-PortOwnerPid 11434
            return ($owner -eq $ProcId)
        }
        default { return $true }
    }
}

# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------

function Stop-OwnedService {
    param([string]$Service)
    $info = Read-ServicePid $Service
    if (-not $info) {
        # No PID record. For the Studio API, a stop/restart request may still need
        # to stop a VERIFIED uvicorn on :8758 (e.g. manually launched, pid file
        # lost). Only stop when identity is proven (cmdline or port ownership) -
        # never on a number alone. Phantom/unrelated owners fail closed.
        if ($Service -eq "studio_api" -and -not (Test-PortIsFree 8758)) {
            $st = Get-StudioApiPortState
            if ($st.state -eq "healthy" -or $st.state -eq "starting") {
                $owner = Get-PortOwnerPid 8758
                if ($owner -and (Test-ProcessIdentity "studio_api" $owner)) {
                    Write-BetaLog $Service "No PID record but verified Studio API PID $owner on :8758 - stopping (identity verified)."
                    try { taskkill /F /T /PID $owner 2>$null | Out-Null; Start-Sleep -Seconds 3 } catch {}
                    if (-not (Wait-PortReleased 8758 -TimeoutSec 15)) {
                        Write-BetaLog $Service "Verified owner stopped but :8758 still held by PID $(Get-PortOwnerPid 8758)." "ERROR"
                        return $false
                    }
                    return $true
                }
                Write-BetaLog $Service "No PID record and :8758 owner not verified - nothing to stop." "WARN"
            } elseif ($st.state -eq "phantom") {
                Write-BetaLog $Service "FAIL CLOSED: :8758 owned by PHANTOM PID $($st.pid) (no pid record). Run: taskkill /F /PID $($st.pid) (elevated) or reboot." "ERROR"
                return $false
            } else {
                Write-BetaLog $Service "No PID record and :8758 owner unrelated - nothing to stop." "WARN"
            }
        }
    }
    $pidVal = [int]$info.pid
    $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
    if (-not $proc) { Write-BetaLog $Service "Process $pidVal already gone."; Remove-ServicePid $Service; return $true }
    # Phase 6: NEVER kill on the pid-file number alone (Windows reuses PIDs).
    if (-not (Test-ProcessIdentity $Service $pidVal)) {
        Write-BetaLog $Service ("Refusing to kill PID " + $pidVal + ": identity mismatch (possible PID reuse). Removing stale pid file.") "WARN"
        Remove-ServicePid $Service
        return $true
    }
    try { taskkill /F /T /PID $pidVal 2>$null | Out-Null; Start-Sleep -Seconds 3 } catch {}
    $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
    if ($proc) { try { Stop-Process -Id $pidVal -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2 } catch {} }
    $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
    if ($proc) { Write-BetaLog $Service "Failed to stop process $pidVal." "WARN"; return $false }
    Write-BetaLog $Service "Stopped process $pidVal."
    Remove-ServicePid $Service
    # Studio API: verify the port is actually released before returning, so a
    # phantom/orphaned socket surfaces as a hard failure instead of a later
    # bind collision that reads as a false "Did not become healthy".
    if ($Service -eq "studio_api") {
        if (-not (Wait-PortReleased 8758 -TimeoutSec 15)) {
            $owner = Get-PortOwnerPid 8758
            Write-BetaLog $Service "Process $pidVal stopped but :8758 still held by PID $owner (phantom/orphaned). Run: taskkill /F /PID $owner (elevated) or reboot." "ERROR"
            return $false
        }
    }
    Start-Sleep -Seconds 1
    return $true
}

# ---------------------------------------------------------------------------
# Authoritative Studio API lifecycle (single owner).
#
# Start-StudioApiAuthoritative is IDEMPOTENT:
#   healthy reachable API  -> adopt, no-op success
#   reachable starting API -> wait bounded readiness, no second launch
#   free port              -> launch exactly one, wait health
#   phantom / unrelated    -> FAIL CLOSED with actionable message
# ---------------------------------------------------------------------------
function Start-StudioApiAuthoritative {
    param([switch]$Force)
    $paths = Get-BetaBackendPaths
    $py = $paths.StudioApiPython
    $apiDir = $paths.StudioApiDir
    if (-not $py -or -not (Test-Path $py)) { Write-BetaLog "studio_api" "venv Python not found at $py" "ERROR"; return $false }

    $state = Get-StudioApiPortState

    if ($state.state -eq "healthy") {
        Write-BetaLog "studio_api" "Already healthy - reusing (PID $($state.pid))."
        Write-ServicePid "studio_api" $state.pid "adopted" $true
        return $true
    }
    if ($state.state -eq "starting") {
        Write-BetaLog "studio_api" "Process $($state.pid) starting on :8758 - waiting for readiness (no second launch)."
        # Measured cold start (beta env, H3 readiness probes): typical 50-60s, observed up to ~4 min under load.
        # Bound at 120s. React to state changes instead of blind-waiting: if the starter DIES, launch fresh;
        # if the port turns phantom/unrelated, fail closed immediately.
        $deadline = (Get-Date).AddSeconds(120)
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 2
            if (Test-StudioApiHealth) { Write-BetaLog "studio_api" "Healthy (PID $($state.pid))."; Write-ServicePid "studio_api" $state.pid "adopted" $true; return $true }
            $now = Get-StudioApiPortState
            if ($now.state -eq "free") {
                Write-BetaLog "studio_api" "Starter PID $($state.pid) exited - launching fresh."
                return Start-StudioApiAuthoritative
            }
            if ($now.state -eq "phantom" -or $now.state -eq "unrelated") {
                Write-BetaLog "studio_api" "Starter replaced by $($now.state) PID $($now.pid) - FAIL CLOSED." "ERROR"
                return $false
            }
        }
        Write-BetaLog "studio_api" "Existing uvicorn PID $($state.pid) did not become healthy in 120s." "ERROR"
        return $false
    }
    if ($state.state -eq "phantom") {
        Write-BetaLog "studio_api" "FAIL CLOSED: :8758 owned by PHANTOM PID $($state.pid). Run: taskkill /F /PID $($state.pid) (elevated) or reboot." "ERROR"
        return $false
    }
    if ($state.state -eq "unrelated") {
        Write-BetaLog "studio_api" "FAIL CLOSED: :8758 owned by unrelated process PID $($state.pid). Do not kill arbitrary processes." "ERROR"
        return $false
    }

    # Port free - launch exactly one.
    Write-BetaLog "studio_api" "Starting uvicorn on :8758..."
    $logFile = Join-Path $script:LogsDir "studio_api_stdout.log"
    $proc = Start-Process -FilePath $py `
        -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8758" `
        -WorkingDirectory $apiDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $logFile -RedirectStandardError (Join-Path $script:LogsDir "studio_api_err.log")
    Write-ServicePid "studio_api" $proc.Id $proc.StartInfo.FileName
    # Measured cold start (beta env, H3 readiness probes): typical 50-60s, observed 42-92s. Bound at 120s.
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if (Test-StudioApiHealth) { Write-BetaLog "studio_api" "Healthy (PID $($proc.Id))."; return $true }
        $st = Get-StudioApiPortState
        if ($st.state -eq "phantom" -or $st.state -eq "unrelated") {
            Write-BetaLog "studio_api" "Launch failed: :8758 taken by $($st.state) PID $($st.pid)." "ERROR"
            return $false
        }
    }
    Write-BetaLog "studio_api" "Did not become healthy within 120s." "ERROR"
    return $false
}


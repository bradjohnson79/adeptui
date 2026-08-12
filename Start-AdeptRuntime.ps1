#Requires -Version 5.1
<#
.SYNOPSIS
    Start Adept UI background runtime services (Studio API, ComfyUI headless,
    Cloudflare Tunnel, Ollama check) without opening any desktop GUI.

.DESCRIPTION
    Detects already-running services and reuses them. Starts only missing
    services. Uses bounded startup waits with health verification. Prevents
    duplicate processes. Prints a concise final status table.

    Complements (does not replace) Start-AdeptUI-Beta.ps1.
#>
param()

$ErrorActionPreference = "Stop"

# --- Paths ----------------------------------------------------------------
$ScriptHome = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$RepoRoot    = (Resolve-Path (Join-Path $ScriptHome ".")).Path
$ConfigFile  = Join-Path $RepoRoot "config\runtime-manager.env"
$LocalConfig = Join-Path $RepoRoot "config\beta-local.local.env"

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

# --- Helper: HTTP health probe --------------------------------------------
function Test-ServiceHealth {
    param([string]$Url, [int]$TimeoutSeconds = 5)
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSeconds -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) { return "ONLINE" }
        return "UNHEALTHY ($($response.StatusCode))"
    } catch {
        return "OFFLINE"
    }
}

# --- Helper: bounded wait for health --------------------------------------
function Wait-ForHealth {
    param([string]$Url, [int]$TimeoutSeconds = 30, [int]$IntervalMs = 2000, [string]$Label = "service")
    $elapsed = 0
    while ($elapsed -lt $TimeoutSeconds * 1000) {
        $status = Test-ServiceHealth -Url $Url -TimeoutSeconds 3
        if ($status -eq "ONLINE") {
            Write-Host "[OK] $Label is ONLINE after ${elapsed}ms"
            return $true
        }
        Start-Sleep -Milliseconds $IntervalMs
        $elapsed += $IntervalMs
    }
    Write-Warning "[TIMEOUT] $Label did not become healthy within ${TimeoutSeconds}s (last status: $status)"
    return $false
}

# --- Helper: is port listening? -------------------------------------------
function Test-PortListening {
    param([int]$Port)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $async = $tcp.BeginConnect("127.0.0.1", $Port, $null, $null)
        $waited = $async.AsyncWaitHandle.WaitOne(2000)
        if ($waited -and $tcp.Connected) {
            $tcp.EndConnect($async) | Out-Null
            $tcp.Close()
            return $true
        }
        $tcp.Close()
        return $false
    } catch { return $false }
}

# --- Helper: find process by command-line pattern -------------------------
function Get-MyProcess {
    param([string]$CommandLinePattern)
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'cloudflared.exe'" -ErrorAction SilentlyContinue
    return $procs | Where-Object { $_.CommandLine -match $CommandLinePattern }
}

# --- Helper: write PID file -----------------------------------------------
function Save-PidFile {
    param([string]$ServiceName, [int]$Pid, [string]$PidDir)
    $null = New-Item -ItemType Directory -Path $PidDir -Force
    $path = Join-Path $PidDir "$ServiceName.pid"
    Set-Content -Path $path -Value $Pid.ToString()
}

# --- Helper: read PID file ------------------------------------------------
function Read-PidFile {
    param([string]$ServiceName, [string]$PidDir)
    $path = Join-Path $PidDir "$ServiceName.pid"
    if (Test-Path $path) {
        $content = (Get-Content $path -Raw).Trim()
        if ($content -match '^\d+$') { return [int]$content }
    }
    return $null
}

# --- Helper: append log ---------------------------------------------------
function Write-ServiceLog {
    param([string]$LogDir, [string]$ServiceName, [string]$Message)
    $null = New-Item -ItemType Directory -Path $LogDir -Force
    $path = Join-Path $LogDir "$ServiceName.log"
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $path -Value "[$timestamp] $Message"
}

# --- Helper: parse command string into executable + args ------------------
function Parse-LaunchCommand {
    param([string]$CommandLine)
    $parts = @()
    $current = ""
    $inQuote = $false
    for ($i = 0; $i -lt $CommandLine.Length; $i++) {
        $c = $CommandLine[$i]
        if ($c -eq '"' -or $c -eq "'") {
            $inQuote = -not $inQuote
            continue
        }
        if (-not $inQuote -and $c -eq ' ') {
            if ($current -ne "") {
                $parts += $current
                $current = ""
            }
            continue
        }
        $current += $c
    }
    if ($current -ne "") { $parts += $current }
    return $parts
}

# --- Helper: GPU detection ------------------------------------------------
function Get-GpuInfo {
    $results = @()
    $nvidiaSmi = "$env:ProgramFiles\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
    if (Test-Path $nvidiaSmi) {
        try {
            $output = & $nvidiaSmi --query-gpu=name,driver_version,memory.total --format=csv,noheader,nounits -ErrorAction Stop
            foreach ($line in $output) {
                $parts = $line -split ','
                $results += @{
                    Vendor = "NVIDIA"
                    Name   = $parts[0].Trim()
                    Driver = $parts[1].Trim()
                    Memory = $parts[2].Trim()
                }
            }
        } catch { }
    }
    if ($results.Count -eq 0) {
        $wmi = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Where-Object { $_.Name }
        foreach ($g in $wmi) {
            $results += @{
                Vendor = "WMI"
                Name   = $g.Name
                Driver = $g.DriverVersion
                Memory = "unknown"
            }
        }
    }
    return $results
}

# --- Helper: format GPU status as string ----------------------------------
function Get-GpuStatus {
    $gpuList = Get-GpuInfo
    if (-not $gpuList -or $gpuList.Count -eq 0) { return "NOT DETECTED" }
    $parts = @()
    foreach ($g in $gpuList) {
        $parts += "$($g.Name) (VRAM: $($g.Memory) MiB)"
    }
    return "DETECTED â€” $($parts -join '; ')"
}

# ==========================================================================
# MAIN
# ==========================================================================

Write-Host "`n=== Adept UI Background Runtime Manager ===`n" -ForegroundColor Cyan

# --- Load config -----------------------------------------------------------
$config = Load-EnvFile $ConfigFile
$local  = Load-EnvFile $LocalConfig -Optional

$apiPort          = if ($config['STUDIO_API_PORT'])          { $config['STUDIO_API_PORT'] }          else { 8758 }
$comfyPort        = if ($config['STUDIO_COMFY_PORT'])        { $config['STUDIO_COMFY_PORT'] }        else { 8188 }
$apiHealthzUrl    = if ($config['STUDIO_API_HEALTHZ_URL'])   { $config['STUDIO_API_HEALTHZ_URL'] }   else { "http://127.0.0.1:$apiPort/api/healthz" }
$apiHealthUrl     = if ($config['STUDIO_API_HEALTH_URL'])    { $config['STUDIO_API_HEALTH_URL'] }    else { "http://127.0.0.1:$apiPort/api/health" }
$comfyUrl         = "http://127.0.0.1:$comfyPort"
$comfyHealthUrl   = if ($config['STUDIO_COMFY_HEALTH_URL'])  { $config['STUDIO_COMFY_HEALTH_URL'] }  else { "$comfyUrl/system_stats" }
$ollamaHealthUrl  = if ($config['STUDIO_OLLAMA_HEALTH_URL']) { $config['STUDIO_OLLAMA_HEALTH_URL'] } else { "http://127.0.0.1:11434/api/tags" }
$tunnelName       = if ($config['CLOUDFLARE_TUNNEL_NAME'])   { $config['CLOUDFLARE_TUNNEL_NAME'] }   else { "adept-ui-beta" }
$publicHostname   = if ($config['PUBLIC_API_HOSTNAME'])      { $config['PUBLIC_API_HOSTNAME'] }      else { "api-beta.adeptui.org" }
$tunnelHealthUrl  = if ($config['CLOUDFLARE_HEALTH_URL'])    { $config['CLOUDFLARE_HEALTH_URL'] }    else { "https://$publicHostname/api/healthz" }
$logDir           = if ($config['RUNTIME_LOG_DIR'])          { $config['RUNTIME_LOG_DIR'] }          else { "logs/runtime" }
$pidDir           = if ($config['RUNTIME_PID_DIR'])          { $config['RUNTIME_PID_DIR'] }          else { "data/runtime/runtime-manager/pids" }

# Resolve relative paths to absolute
if (-not ([System.IO.Path]::IsPathRooted($logDir)))  { $logDir  = Join-Path $RepoRoot $logDir }
if (-not ([System.IO.Path]::IsPathRooted($pidDir)))  { $pidDir  = Join-Path $RepoRoot $pidDir }

$comfyLaunchCmd  = $local['ADEPT_COMFY_LAUNCH']

# Ensure directories exist
$null = New-Item -ItemType Directory -Path $pidDir -Force
$null = New-Item -ItemType Directory -Path $logDir -Force

Write-Host "Log directory: $logDir"
Write-Host "PID directory: $pidDir`n"

# ==========================================================================
# 1. Studio API
# ==========================================================================
Write-Host "--- Studio API (port $apiPort) ---" -ForegroundColor Yellow
$apiStatus = Test-ServiceHealth -Url $apiHealthzUrl -TimeoutSeconds 3
if ($apiStatus -eq "ONLINE") {
    Write-Host "[REUSE] Studio API is already ONLINE" -ForegroundColor Green
    Write-ServiceLog $logDir "api" "Already ONLINE â€” reused"
} else {
    Write-Host "[START] Launching Studio API..." -ForegroundColor Yellow
    $venvPython = Join-Path $RepoRoot "studio-api\.venv\Scripts\python.exe"
    $apiModule   = "app.main:app"
    if (-not (Test-Path $venvPython)) {
        Write-Error "Venv Python not found at $venvPython"
        $apiStatus = "FAILED"
    } else {
        $apiArgs = "-m uvicorn $apiModule --host 127.0.0.1 --port $apiPort --workers 2"
        $apiProc = Start-Process -FilePath $venvPython -ArgumentList $apiArgs -WindowStyle Hidden -PassThru -NoNewWindow
        Save-PidFile -ServiceName "api" -Pid $apiProc.Id -PidDir $pidDir
        Write-ServiceLog $logDir "api" "Launching: $venvPython $apiArgs (PID $($apiProc.Id))"
        $ready = Wait-ForHealth -Url $apiHealthzUrl -TimeoutSeconds 30 -Label "Studio API"
        $apiStatus = if ($ready) { "ONLINE" } else { "TIMEOUT" }
        if (-not $ready) { Write-ServiceLog $logDir "api" "FAILED â€” timed out after 30s" }
    }
}
Write-Host "Status: $apiStatus`n"

# ==========================================================================
# 2. ComfyUI (headless)
# ==========================================================================
Write-Host "--- ComfyUI Headless (port $comfyPort) ---" -ForegroundColor Yellow
$comfyStatus = "OFFLINE"

# Check if already running
if (Test-PortListening -Port $comfyPort) {
    $comfyCheck = Test-ServiceHealth -Url $comfyHealthUrl -TimeoutSeconds 5
    if ($comfyCheck -eq "ONLINE") {
        Write-Host "[REUSE] ComfyUI is already ONLINE on port $comfyPort" -ForegroundColor Green
        $comfyStatus = "ONLINE"
        Write-ServiceLog $logDir "comfy" "Already ONLINE on port $comfyPort â€” reused"
    } else {
        Write-Warning "Port $comfyPort is listening but health check failed ($comfyCheck)"
        $comfyStatus = "UNHEALTHY"
    }
}

if ($comfyStatus -ne "ONLINE") {
    if (-not $comfyLaunchCmd) {
        Write-Warning "ADEPT_COMFY_LAUNCH not set in $LocalConfig. ComfyUI cannot be started automatically."
        Write-ServiceLog $logDir "comfy" "Cannot start â€” ADEPT_COMFY_LAUNCH not configured"
        $comfyStatus = "NOT_CONFIGURED"
    } else {
        # Parse the launch command: first token is python, rest are args
        $tokens = Parse-LaunchCommand $comfyLaunchCmd
        $pythonExe = $tokens[0]
        $pythonArgs = $tokens[1..($tokens.Length - 1)] -join " "

        if (-not (Test-Path $pythonExe)) {
            Write-Error "ComfyUI Python not found at: $pythonExe"
            Write-ServiceLog $logDir "comfy" "FAILED â€” Python not found at $pythonExe"
            $comfyStatus = "FAILED"
        } else {
            Write-Host "[START] Launching ComfyUI headlessly..." -ForegroundColor Yellow
            $comfyProc = Start-Process -FilePath $pythonExe -ArgumentList $pythonArgs -WindowStyle Hidden -PassThru -NoNewWindow
            Save-PidFile -ServiceName "comfy" -Pid $comfyProc.Id -PidDir $pidDir
            Write-ServiceLog $logDir "comfy" "Launching: $pythonExe $pythonArgs (PID $($comfyProc.Id))"
            Write-Host "  Waiting up to 60s for ComfyUI to become ready..." -ForegroundColor Gray
            $ready = Wait-ForHealth -Url $comfyHealthUrl -TimeoutSeconds 60 -IntervalMs 3000 -Label "ComfyUI"
            $comfyStatus = if ($ready) { "ONLINE" } else { "TIMEOUT" }
            if (-not $ready) { Write-ServiceLog $logDir "comfy" "FAILED â€” timed out after 60s" }
        }
    }
}
Write-Host "Status: $comfyStatus`n"

# ==========================================================================
# 3. Cloudflare Tunnel
# ==========================================================================
Write-Host "--- Cloudflare Tunnel ($tunnelName) ---" -ForegroundColor Yellow
$tunnelStatus = "OFFLINE"

# Check tunnel process
$tunnelProcs = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
$tunnelAlreadyRunning = $tunnelProcs.Count -gt 0

if ($tunnelAlreadyRunning) {
    Write-Host "[REUSE] cloudflared process already running (PID: $($tunnelProcs[0].Id))" -ForegroundColor Green
    $tunnelStatus = Test-ServiceHealth -Url $tunnelHealthUrl -TimeoutSeconds 5
    if ($tunnelStatus -eq "ONLINE") {
        Write-Host "[REUSE] Tunnel endpoint is reachable" -ForegroundColor Green
        Write-ServiceLog $logDir "tunnel" "Already running (PID $($tunnelProcs[0].Id)) â€” reused"
    } else {
        Write-Warning "cloudflared is running but public endpoint is unreachable ($tunnelStatus)"
        $tunnelStatus = "UNREACHABLE"
    }
} else {
    Write-Host "[START] Launching Cloudflare Tunnel..." -ForegroundColor Yellow
    $tunnelLog = Join-Path $logDir "tunnel.log"
    $tunnelProc = Start-Process -FilePath "cloudflared" -ArgumentList "tunnel run $tunnelName" -WindowStyle Hidden -PassThru -NoNewWindow -RedirectStandardOutput $tunnelLog -RedirectStandardError "$tunnelLog.err"
    Save-PidFile -ServiceName "tunnel" -Pid $tunnelProc.Id -PidDir $pidDir
    Write-ServiceLog $logDir "tunnel" "Launching: cloudflared tunnel run $tunnelName (PID $($tunnelProc.Id))"
    Start-Sleep -Seconds 5
    $tunnelStatus = Test-ServiceHealth -Url $tunnelHealthUrl -TimeoutSeconds 10
    if ($tunnelStatus -eq "ONLINE") {
        Write-Host "[OK] Tunnel endpoint is reachable" -ForegroundColor Green
        Write-ServiceLog $logDir "tunnel" "ONLINE â€” endpoint reachable"
    } else {
        Write-Warning "Tunnel launched but endpoint not yet reachable ($tunnelStatus)"
        Write-ServiceLog $logDir "tunnel" "Launched but endpoint $tunnelHealthUrl returned $tunnelStatus"
    }
}
Write-Host "Status: $tunnelStatus`n"

# ==========================================================================
# 4. Ollama (check only â€” user-managed)
# ==========================================================================
Write-Host "--- Ollama ---" -ForegroundColor Yellow
$ollamaStatus = Test-ServiceHealth -Url $ollamaHealthUrl -TimeoutSeconds 3
if ($ollamaStatus -eq "ONLINE") {
    Write-Host "[OK] Ollama is ONLINE" -ForegroundColor Green
    Write-ServiceLog $logDir "ollama" "Ollama is ONLINE"
} else {
    Write-Host "[INFO] Ollama is $ollamaStatus (user-managed â€” not started by this script)" -ForegroundColor Gray
    Write-ServiceLog $logDir "ollama" "Ollama is $ollamaStatus (user-managed)"
}
Write-Host "Status: $ollamaStatus`n"

# ==========================================================================
# 5. GPU Detection
# ==========================================================================
Write-Host "--- GPU ---" -ForegroundColor Yellow
Write-Host "$(Get-GpuStatus)`n"

# ==========================================================================
# Final Status Table
# ==========================================================================
Write-Host "=== Adept Runtime Status ===" -ForegroundColor Cyan
Write-Host ("{0,-25} {1,-15}" -f "Service", "Status")
Write-Host "-" * 42
Write-Host ("{0,-25} {1,-15}" -f "Studio API", $apiStatus)
Write-Host ("{0,-25} {1,-15}" -f "ComfyUI", $comfyStatus)
Write-Host ("{0,-25} {1,-15}" -f "Cloudflare Tunnel", $tunnelStatus)
Write-Host ("{0,-25} {1,-15}" -f "Ollama", $ollamaStatus)
Write-Host ("{0,-25} {1,-15}" -f "GPU", (Get-GpuStatus))
Write-Host ""

if ($apiStatus -eq "ONLINE") {
    Write-Host "Adept UI Frontend: http://127.0.0.1:8760/" -ForegroundColor Blue
    Write-Host "Studio API:         http://127.0.0.1:$apiPort/api/healthz" -ForegroundColor Blue
    if ($tunnelStatus -eq "ONLINE") {
        Write-Host "Public API:         https://$publicHostname/api/healthz" -ForegroundColor Blue
    }
}
Write-Host ""

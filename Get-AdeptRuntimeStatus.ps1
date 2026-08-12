#Requires -Version 5.1
<#
.SYNOPSIS
    Report the current status of all Adept Runtime background services.
    Non-destructive â€” never starts or stops anything.
#>
param()

$ErrorActionPreference = "Stop"

# --- Paths ----------------------------------------------------------------
$ScriptHome = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$RepoRoot    = (Resolve-Path (Join-Path $ScriptHome ".")).Path
$ConfigFile  = Join-Path $RepoRoot "config\runtime-manager.env"

# --- Helper: load env file ------------------------------------------------
function Load-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return @{} }
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
        return "UNHEALTHY (HTTP $($response.StatusCode))"
    } catch {
        $msg = $_.Exception.Message
        if ($msg -match 'Unable to connect|Could not connect|connection refused|Name or service not known') {
            return "OFFLINE"
        }
        return "OFFLINE ($($_.Exception.GetType().Name))"
    }
}

# --- Helper: port listener check ------------------------------------------
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

# --- Helper: GPU detection ------------------------------------------------
function Get-GpuInfo {
    $results = @()
    # NVIDIA via nvidia-smi
    $nvidiaSmi = "$env:ProgramFiles\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
    if (Test-Path $nvidiaSmi) {
        try {
            $output = & $nvidiaSmi --query-gpu=name,driver_version,memory.total --format=csv,noheader,nounits -ErrorAction Stop
            foreach ($line in $output) {
                $parts = $line -split ','
                $results += @{
                    Vendor  = "NVIDIA"
                    Name    = $parts[0].Trim()
                    Driver  = $parts[1].Trim()
                    Memory  = $parts[2].Trim()
                }
            }
        } catch { }
    }
    # Fallback: WMI
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

# --- Helper: format GPU ---------------------------------------------------
function Format-GpuStatus {
    param($GpuList)
    if (-not $GpuList -or $GpuList.Count -eq 0) { return "NOT DETECTED" }
    $parts = @()
    foreach ($g in $GpuList) {
        $parts += "$($g.Name) (VRAM: $($g.Memory) MiB, Driver: $($g.Driver))"
    }
    return "DETECTED â€” $($parts -join '; ')"
}

# ==========================================================================
# MAIN
# ==========================================================================

$config = Load-EnvFile $ConfigFile

$apiPort        = if ($config['STUDIO_API_PORT'])         { $config['STUDIO_API_PORT'] }         else { 8758 }
$comfyPort      = if ($config['STUDIO_COMFY_PORT'])       { $config['STUDIO_COMFY_PORT'] }       else { 8188 }
$apiHealthzUrl  = if ($config['STUDIO_API_HEALTHZ_URL'])  { $config['STUDIO_API_HEALTHZ_URL'] }  else { "http://127.0.0.1:$apiPort/api/healthz" }
$comfyHealthUrl = if ($config['STUDIO_COMFY_HEALTH_URL']) { $config['STUDIO_COMFY_HEALTH_URL'] } else { "http://127.0.0.1:$comfyPort/system_stats" }
$ollamaHealthUrl= if ($config['STUDIO_OLLAMA_HEALTH_URL']){ $config['STUDIO_OLLAMA_HEALTH_URL'] }else { "http://127.0.0.1:11434/api/tags" }
$tunnelHealthUrl= if ($config['CLOUDFLARE_HEALTH_URL'])   { $config['CLOUDFLARE_HEALTH_URL'] }   else { "https://api-beta.adeptui.org/api/healthz" }
$publicHost     = if ($config['PUBLIC_API_HOSTNAME'])     { $config['PUBLIC_API_HOSTNAME'] }     else { "api-beta.adeptui.org" }

Write-Host "`n=== Adept Runtime Status ===`n" -ForegroundColor Cyan

# --- Probe all services in parallel-ish (sequential but fast) -------------
$apiStatus    = Test-ServiceHealth -Url $apiHealthzUrl -TimeoutSeconds 5
$apiFullStatus = $apiStatus
if ($apiStatus -eq "ONLINE") {
    $apiFull = Test-ServiceHealth -Url ("http://127.0.0.1:$apiPort/api/health") -TimeoutSeconds 8
    if ($apiFull -ne "ONLINE") { $apiFullStatus = "DEGRADED (healthz OK, health: $apiFull)" }
}

$comfyStatus = if (Test-PortListening -Port $comfyPort) {
    $h = Test-ServiceHealth -Url $comfyHealthUrl -TimeoutSeconds 5
    if ($h -eq "ONLINE") { "ONLINE" } else { "LISTENING_UNHEALTHY" }
} else { "OFFLINE" }

$ollamaStatus = Test-ServiceHealth -Url $ollamaHealthUrl -TimeoutSeconds 3

$tunnelStatus = Test-ServiceHealth -Url $tunnelHealthUrl -TimeoutSeconds 8

$gpuList = Get-GpuInfo
$gpuStatus = Format-GpuStatus $gpuList

# --- PID file info --------------------------------------------------------
$pidDir = if ($config['RUNTIME_PID_DIR']) { $config['RUNTIME_PID_DIR'] } else { "data/runtime/runtime-manager/pids" }
if (-not ([System.IO.Path]::IsPathRooted($pidDir))) { $pidDir = Join-Path $RepoRoot $pidDir }
$pidFiles = Get-ChildItem -Path $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue
$pidCount = if ($pidFiles) { $pidFiles.Count } else { 0 }

# --- Display --------------------------------------------------------------
Write-Host ("{0,-25} {1,-20} {2,-15}" -f "Service", "Status", "Port")
Write-Host "-" * 62
Write-Host ("{0,-25} {1,-20} {2,-15}" -f "Studio API", $apiFullStatus, $apiPort)
Write-Host ("{0,-25} {1,-20} {2,-15}" -f "ComfyUI (headless)", $comfyStatus, $comfyPort)
Write-Host ("{0,-25} {1,-20} {2,-15}" -f "Ollama", $ollamaStatus, "11434")
Write-Host ("{0,-25} {1,-20} {2,-15}" -f "Cloudflare Tunnel", $tunnelStatus, "443 (api-beta.adeptui.org)")
Write-Host ("{0,-25} {1,-20}" -f "GPU", $gpuStatus)
Write-Host ""
Write-Host "Managed processes: found $pidCount PID file(s)" -ForegroundColor Gray
Write-Host ""

# --- Quick links ----------------------------------------------------------
if ($apiStatus -eq "ONLINE") {
    Write-Host "Access points:" -ForegroundColor Blue
    Write-Host "  Studio API:         http://127.0.0.1:$apiPort/api/healthz" -ForegroundColor Blue
    Write-Host "  ComfyUI:            http://127.0.0.1:$comfyPort/system_stats" -ForegroundColor Blue
    Write-Host "  Ollama:             http://127.0.0.1:11434/api/tags" -ForegroundColor Blue
    if ($tunnelStatus -eq "ONLINE") {
        Write-Host "  Public API:         https://$publicHost/api/healthz" -ForegroundColor Blue
    }
}
Write-Host ""

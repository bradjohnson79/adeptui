#Requires -Version 5.1
<#
.SYNOPSIS
  Start Adept UI V1.1 Owner Beta local production runtime (no Vite).
#>
param(
  [switch]$NoBrowser,
  [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$RepoRoot = (Resolve-Path $RepoRoot).Path
$VenvPython = Join-Path $RepoRoot "studio-api\.venv\Scripts\python.exe"
$Supervisor = Join-Path $RepoRoot "scripts\beta_runtime\supervisor.py"
$StatusFile = Join-Path $RepoRoot "data\runtime\beta\status.json"
$LauncherLog = Join-Path $RepoRoot "data\runtime\logs\beta\launcher.log"

function Test-BetaReady {
  try {
    $web = Invoke-WebRequest -Uri "http://127.0.0.1:8760/__beta_web_health" -UseBasicParsing -TimeoutSec 5
    $api = Invoke-WebRequest -Uri "http://127.0.0.1:8758/api/health" -UseBasicParsing -TimeoutSec 30
    return ($web.StatusCode -eq 200 -and $api.StatusCode -eq 200)
  } catch {
    return $false
  }
}

function Write-LauncherLog([string]$Message) {
  $dir = Split-Path -Parent $LauncherLog
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  $line = "[{0}] {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $Message
  Add-Content -Path $LauncherLog -Value $line -Encoding UTF8
  Write-Host $line
}

if (-not (Test-Path $VenvPython)) {
  Write-Error "Missing studio-api venv at $VenvPython. Run: npm run install:all"
  exit 1
}
if (-not (Test-Path $Supervisor)) {
  Write-Error "Missing supervisor at $Supervisor"
  exit 1
}

Write-LauncherLog "Start-AdeptUI-Beta root=$RepoRoot"

if (Test-BetaReady) {
  Write-LauncherLog "Runtime already READY"
  Write-Host ""
  Write-Host "READY - Adept UI Beta already running at http://127.0.0.1:8760/" -ForegroundColor Green
  Write-Host "API  http://127.0.0.1:8758/api/health"
  Write-Host ("Logs {0}" -f (Join-Path $RepoRoot "data\runtime\logs\beta"))
  if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:8760/"
  }
  exit 0
}

# Duplicate-supervisor guard: a live supervisor that is mid-startup or
# mid-restart fails the ready probe above. Launching a second supervisor
# would fight over ports 8758/8760 (bind failures -> crash loop). Attach
# instead: wait for the running supervisor to reach READY.
$SupervisorPidFile = Join-Path $RepoRoot "data\runtime\beta\pids\supervisor.pid"
$supervisorAlive = $false
if (Test-Path $SupervisorPidFile) {
  $supPid = 0
  [void][int]::TryParse((Get-Content $SupervisorPidFile -Raw).Trim(), [ref]$supPid)
  if ($supPid -gt 0) {
    $supProc = Get-CimInstance Win32_Process -Filter "ProcessId=$supPid" -ErrorAction SilentlyContinue
    if ($supProc -and $supProc.CommandLine -match "beta_runtime\\supervisor\.py") {
      $supervisorAlive = $true
    }
  }
}

if ($supervisorAlive) {
  Write-LauncherLog "Supervisor already running (pid $supPid) - attaching (waiting for READY)"
} else {

# Ensure httpx available for web proxy
& $VenvPython -c "import httpx, starlette, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-LauncherLog "Installing httpx into studio-api venv (proxy dependency)"
  & $VenvPython -m pip install --disable-pip-version-check httpx | Out-Null
}

$env:ADEPT_UI_BETA_RUNTIME = "1"
$env:PYTHONIOENCODING = "utf-8"
$argsList = @($Supervisor, "run")

if ($Foreground) {
  Write-LauncherLog "Starting supervisor in foreground"
  & $VenvPython @argsList
  exit $LASTEXITCODE
}

# Detach supervisor
$workDir = $RepoRoot
# Detach via cmd start so stdout is not buffered in this process
$cmdArgs = "/c start `"AdeptUI-Beta-Supervisor`" /B `"$VenvPython`" `"$Supervisor`" run"
$proc = Start-Process -FilePath "cmd.exe" -ArgumentList $cmdArgs -WorkingDirectory $workDir -WindowStyle Hidden -PassThru
Write-LauncherLog ("Supervisor launch helper PID {0}" -f $proc.Id)

}

$deadline = (Get-Date).AddSeconds(180)
$ready = $false
$state = "STARTING"
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 2
  if (Test-Path $StatusFile) {
    try {
      $status = Get-Content $StatusFile -Raw | ConvertFrom-Json
      $state = [string]$status.state
      if ($state -eq "READY" -or $state -eq "HEALTHY" -or $state -eq "SLOW" -or $state -eq "DEGRADED") {
        $ready = $true
        break
      }
      if ($state -eq "FAILED" -or $state -eq "CRASH_LOOP") { break }
    } catch { }
  }
  try {
    $h = Invoke-WebRequest -Uri "http://127.0.0.1:8760/__beta_web_health" -UseBasicParsing -TimeoutSec 5
    # /api/health can exceed 10s when ComfyUI is unreachable; keep this above that floor.
    $a = Invoke-WebRequest -Uri "http://127.0.0.1:8758/api/health" -UseBasicParsing -TimeoutSec 30
    if ($h.StatusCode -eq 200 -and $a.StatusCode -eq 200) {
      $ready = $true
      $state = "READY"
      break
    }
  } catch { }
}

if (-not $ready) {
  Write-LauncherLog "FAILED - runtime did not become READY/DEGRADED (last state=$state)"
  Write-Host ""
  Write-Host "FAILED - Adept UI Beta runtime did not become ready." -ForegroundColor Red
  Write-Host ("See logs: {0}" -f (Join-Path $RepoRoot "data\runtime\logs\beta"))
  exit 1
}

Write-LauncherLog "Runtime $state"
Write-Host ""
Write-Host ("{0} - Adept UI Beta at http://127.0.0.1:8760/" -f $state) -ForegroundColor Green
Write-Host "API  http://127.0.0.1:8758/api/health"
Write-Host ("Logs {0}" -f (Join-Path $RepoRoot "data\runtime\logs\beta"))

if (-not $NoBrowser) {
  Start-Process "http://127.0.0.1:8760/"
}
exit 0

#Requires -Version 5.1
<#
.SYNOPSIS
  Start the isolated MiniMax H3 Route A ComfyUI runtime (:8192) as a single instance.

.DESCRIPTION
  Idempotent: kills any stale H3 Route A python process, frees port 8192, then
  launches exactly one ComfyUI process with a dedicated database URL and a
  rotated log file. Waits for /system_stats + /object_info readiness.

  This is the canonical operator entrypoint for the H3 private owner-only
  runtime referenced by the Adept UI build laws. It prevents the multi-process
  SQLite-DB-lock + comfy-aimdo HostBuffer corruption that surfaced as
  `OSError [Errno 22] Invalid argument at SamplerCustomAdvanced` during
  graduation on Windows + RTX 5090.

  Usage from repo root:
    .\scripts\Start-AdeptUI-H3-RouteA.ps1
    .\scripts\Start-AdeptUI-H3-RouteA.ps1 -WaitSeconds 300
    .\scripts\Start-AdeptUI-H3-RouteA.ps1 -NoWait
#>
param(
  [int]$WaitSeconds = 300,
  [switch]$NoWait
)

$ErrorActionPreference = 'Stop'
$StartScript = 'C:\AdeptFilmWorks\AIVideoStudio-h3\runtime\minimax-h3\scripts\start_isolated_comfy_route_a.ps1'
$LogDir = 'C:\AdeptFilmWorks\AIVideoStudio\data\runtime\logs\beta'
$LogFile = Join-Path $LogDir 'h3-route-a.log'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not (Test-Path $StartScript)) {
  Write-Error "H3 Route A start script not found: $StartScript"
  exit 1
}

# The start script already enforces single-instance + dedicated DB URL.
# Launch it detached with output redirected to the rotated log.
$stamp = (Get-Date).ToString('yyyyMMddTHHmmssZ')
$rotated = $LogFile -replace '\.log$', ".$stamp.log"
if (Test-Path $LogFile) { Move-Item -Force $LogFile $rotated }

$cmd = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$StartScript`" *> `"$LogFile`""
Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-Command',$cmd -WindowStyle Hidden
Write-Host "Launched H3 Route A. Log: $LogFile"

if ($NoWait) { exit 0 }

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$lastErr = ''
while ((Get-Date) -lt $deadline) {
  $comfyOk = $false
  try {
    $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 8 -Uri 'http://127.0.0.1:8192/system_stats'
    if ($r.StatusCode -eq 200) { $comfyOk = $true }
  } catch { $lastErr = $_.Exception.Message }

  $objOk = $false
  if ($comfyOk) {
    try {
      $r2 = Invoke-WebRequest -UseBasicParsing -TimeoutSec 8 -Uri 'http://127.0.0.1:8192/object_info'
      if ($r2.StatusCode -eq 200) { $objOk = $true }
    } catch { $lastErr = $_.Exception.Message }
  }

  $readyOk = $false
  $readyBody = ''
  if ($objOk) {
    try {
      $r3 = Invoke-WebRequest -UseBasicParsing -TimeoutSec 8 -Uri 'http://127.0.0.1:8758/api/minimax-h3/readiness'
      if ($r3.StatusCode -eq 200) { $readyOk = $true; $readyBody = $r3.Content }
    } catch { $lastErr = $_.Exception.Message }
  }

  Write-Host ("[{0}] comfy={1} objInfo={2} ready={3}" -f (Get-Date -Format 'HH:mm:ss'), $comfyOk, $objOk, $readyOk)
  if ($comfyOk -and $objOk -and $readyOk) {
    Write-Host "H3 Route A READY"
    Write-Host "readiness: $readyBody"
    exit 0
  }
  Start-Sleep -Seconds 10
}
Write-Error "H3 Route A did not become ready in $WaitSeconds s. lastErr=$lastErr"
Write-Host ("Tail of " + $LogFile + ":")
Get-Content $LogFile -Tail 40 -ErrorAction SilentlyContinue
exit 1

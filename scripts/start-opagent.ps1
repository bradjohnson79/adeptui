param([int]$Port = 8761)
$ErrorActionPreference = "Stop"
$RepoRoot = "C:\AdeptFilmWorks\AIVideoStudio"
$VenvPython = Join-Path $RepoRoot "studio-api\.venv\Scripts\python.exe"
$ApiDir = Join-Path $RepoRoot "studio-api"
$LogFile = Join-Path $RepoRoot "data\runtime\logs\beta\opagent-$Port.log"
$LogErr = "$LogFile.err"
$LogDir = Split-Path $LogFile
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

if (-not (Test-Path $VenvPython)) { Write-Error "Missing venv python: $VenvPython"; exit 1 }

# Free the port if a stale repo-owned listener exists.
$existing = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
foreach ($procId in $existing) {
  $info = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
  if ($info.CommandLine -and $info.CommandLine -match [regex]::Escape($RepoRoot)) {
    Write-Host "Killing stale $Port listener PID $procId"
    & taskkill.exe /PID $procId /T /F 2>$null | Out-Null
  } else {
    Write-Warning "$Port in use by non-repo PID $procId - not killing"
  }
}
Start-Sleep -Seconds 2

$stamp = (Get-Date).ToString('yyyyMMddTHHmmssZ')
if (Test-Path $LogFile) { Move-Item -Force $LogFile ($LogFile -replace '\.log$', ".$stamp.log") }
if (Test-Path $LogErr) { Move-Item -Force $LogErr ($LogErr -replace '\.err$', ".$stamp.err") }

$env:STUDIO_API_HOST = "127.0.0.1"
$env:STUDIO_API_PORT = [string]$Port
$env:STUDIO_FEATURE_CODIRECTOR_OPERATIONAL_AGENT_V1 = "1"
$env:STUDIO_FEATURE_CODIRECTOR_INTELLIGENCE_V2 = "1"
$env:STUDIO_FEATURE_VISION_VALIDATION_V1 = "1"
$env:STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1 = "1"
$env:STUDIO_FEATURE_TIMELINE_REFERENCES_V1 = "1"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "Starting Studio API on $Port with op-agent flag ON"
Write-Host "Log: $LogFile"

$uvArgs = @("-m","uvicorn","app.main:app","--host","127.0.0.1","--port",[string]$Port)
$proc = Start-Process -FilePath $VenvPython -ArgumentList $uvArgs -WorkingDirectory $ApiDir -WindowStyle Hidden -RedirectStandardOutput $LogFile -RedirectStandardError $LogErr -PassThru
Write-Host "Launched PID $($proc.Id)"

$deadline = (Get-Date).AddSeconds(120)
$ready = $false
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 3
  try {
    $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 8 -Uri "http://127.0.0.1:$Port/api/health"
    if ($r.StatusCode -eq 200) { $ready = $true; break }
  } catch { }
}

if (-not $ready) {
  Write-Error "$Port did not become healthy in 120s"
  Write-Host "Tail of $LogFile :"
  Get-Content $LogFile -Tail 40 -ErrorAction SilentlyContinue
  Write-Host "Tail of $LogErr :"
  Get-Content $LogErr -Tail 40 -ErrorAction SilentlyContinue
  exit 1
}

Write-Host "READY - Studio API on $Port op-agent flag ON"
Write-Host "Health URL: http://127.0.0.1:$Port/api/health"

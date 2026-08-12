#Requires -Version 5.1
$ErrorActionPreference = "Continue"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$RepoRoot = (Resolve-Path $RepoRoot).Path
$StatusFile = Join-Path $RepoRoot "data\runtime\beta\status.json"
$PidDir = Join-Path $RepoRoot "data\runtime\beta\pids"

Write-Host "=== Adept UI Beta Health ==="
Write-Host "Root: $RepoRoot"
Write-Host ""

if (Test-Path $StatusFile) {
  Write-Host "status.json:"
  Get-Content $StatusFile -Raw
} else {
  Write-Host "status.json: (missing - runtime not started)"
}

Write-Host ""
Write-Host "PID files:"
if (Test-Path $PidDir) {
  Get-ChildItem $PidDir -Filter *.pid | ForEach-Object {
    Write-Host ("  {0} = {1}" -f $_.BaseName, (Get-Content $_.FullName -Raw).Trim())
  }
} else {
  Write-Host "  (none)"
}

Write-Host ""
foreach ($url in @(
  "http://127.0.0.1:8760/__beta_web_health",
  "http://127.0.0.1:8758/api/health",
  "http://127.0.0.1:8188/system_stats"
)) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
    Write-Host ("OK  {0} -> {1}" -f $url, $r.StatusCode)
  } catch {
    Write-Host ("DOWN {0}" -f $url)
  }
}

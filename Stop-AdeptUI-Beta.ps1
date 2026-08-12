#Requires -Version 5.1
<#
.SYNOPSIS
  Stop only Adept UI Beta runtime processes (PID files / tagged supervisor).
#>
param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$RepoRoot = (Resolve-Path $RepoRoot).Path
$VenvPython = Join-Path $RepoRoot "studio-api\.venv\Scripts\python.exe"
$Supervisor = Join-Path $RepoRoot "scripts\beta_runtime\supervisor.py"
$CertificationLock = Join-Path $RepoRoot "data\runtime\beta\certification.lock"
$ApiPort = 8758
$WebPort = 8760

function Get-BetaTaggedProcesses {
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and
    $_.CommandLine -like "*$RepoRoot*" -and (
      $_.CommandLine -match "scripts\\beta_runtime\\supervisor\.py" -or
      $_.CommandLine -match "scripts\\beta_runtime\\web_server\.py" -or
      $_.CommandLine -match "app\.main:app.*--port 8758"
    )
  }
}

function Wait-BetaDown {
  param(
    [int]$TimeoutSeconds = 60
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    $portListeners = @(
      Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue
      Get-NetTCPConnection -LocalPort $WebPort -State Listen -ErrorAction SilentlyContinue
    ) | Where-Object { $_ }
    $tagged = @(Get-BetaTaggedProcesses)
    if ($portListeners.Count -eq 0 -and $tagged.Count -eq 0) {
      return $true
    }
    Start-Sleep -Seconds 2
  } while ((Get-Date) -lt $deadline)
  return $false
}

if ((Test-Path $CertificationLock) -and -not $Force) {
  Write-Error "A Beta certification window lock is active. Refusing to stop the runtime without -Force."
  exit 1
}

Write-Host "[beta] stopping Adept UI Beta runtime..."
if (Test-Path $VenvPython) {
  & $VenvPython $Supervisor stop
} else {
  Write-Warning "venv missing - attempting PID-file cleanup only"
  $pidDir = Join-Path $RepoRoot "data\runtime\beta\pids"
  if (Test-Path $pidDir) {
    Get-ChildItem $pidDir -Filter *.pid | ForEach-Object {
      $pid = 0
      [void][int]::TryParse((Get-Content $_.FullName -Raw).Trim(), [ref]$pid)
      if ($pid -gt 0) {
        & taskkill.exe /PID $pid /T /F 2>$null | Out-Null
      }
      Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    }
  }
}
if (-not (Wait-BetaDown -TimeoutSeconds 60)) {
  $portListeners = @(
    Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue
    Get-NetTCPConnection -LocalPort $WebPort -State Listen -ErrorAction SilentlyContinue
  ) | Where-Object { $_ } | Select-Object LocalPort, OwningProcess, State
  $tagged = @(Get-BetaTaggedProcesses) | Select-Object ProcessId, ParentProcessId, Name, CommandLine
  Write-Error ("Adept UI Beta did not remain stopped within 60s.`nPorts:`n{0}`nProcesses:`n{1}" -f (
      ($portListeners | Out-String).Trim()
    ), (
      ($tagged | Out-String).Trim()
    ))
  exit 1
}
Write-Host "[beta] STOPPED (ports 8758/8760 down; project data left untouched)"
exit 0

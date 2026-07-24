#Requires -Version 5.1
<#
.SYNOPSIS
  Start / stop / restart Local AI Video Studio dev servers (API :8742, web :5173).

.DESCRIPTION
  Only targets listeners whose command line clearly belongs to this repo
  (studio-api uvicorn / studio-web vite). Safe to run from the repo root:

    .\scripts\dev.ps1 start
    .\scripts\dev.ps1 stop
    .\scripts\dev.ps1 restart
    .\scripts\dev.ps1 status

  Or via npm from the repo root:

    npm run dev
    npm run dev:stop
    npm run dev:restart
    npm run dev:status
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet("start", "stop", "restart", "status")]
  [string]$Action = "start",

  [int]$ApiPort = 8742,
  [int]$WebPort = 5173,
  [int]$WaitSeconds = 20
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$RepoMarker = [regex]::Escape($RepoRoot.Path)

function Get-ListenPids([int]$Port) {
  @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    Where-Object { $_ -and $_ -gt 0 })
}

function Get-ProcessInfo([int]$ProcessId) {
  Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
}

function Get-ProcessAncestryText([int]$ProcessId, [int]$MaxDepth = 6) {
  $chunks = New-Object System.Collections.Generic.List[string]
  $currentId = $ProcessId
  for ($i = 0; $i -lt $MaxDepth; $i++) {
    if (-not $currentId -or $currentId -le 0) { break }
    $info = Get-ProcessInfo $currentId
    if (-not $info) { break }
    if ($info.ExecutablePath) { $chunks.Add([string]$info.ExecutablePath) }
    if ($info.CommandLine) { $chunks.Add([string]$info.CommandLine) }
    $currentId = [int]$info.ParentProcessId
  }
  return ($chunks -join "`n")
}

function Test-StudioProcess([int]$ProcessId, [int]$Port) {
  $blob = Get-ProcessAncestryText $ProcessId
  if ([string]::IsNullOrWhiteSpace($blob)) { return $false }
  if ($blob -notmatch $RepoMarker) { return $false }

  if ($Port -eq $ApiPort) {
    return ($blob -match 'uvicorn|studio-api|app\.main:app|run-api\.mjs')
  }
  if ($Port -eq $WebPort) {
    return ($blob -match 'vite|studio-web')
  }
  return $false
}

function Get-StudioListeners([int]$Port) {
  $results = @()
  foreach ($procId in (Get-ListenPids $Port)) {
    $info = Get-ProcessInfo $procId
    if (-not $info) { continue }
    $cmd = [string]$info.CommandLine
    $owned = Test-StudioProcess $procId $Port
    $results += [pscustomobject]@{
      Port        = $Port
      Pid         = $procId
      Name        = $info.Name
      Owned       = $owned
      CommandLine = $cmd
    }
  }
  return $results
}

function Get-StudioRootPid([int]$ProcessId, [int]$Port) {
  # Prefer killing the highest ancestor that still belongs to this repo so
  # uvicorn --reload parent + child both go away.
  $rootId = $ProcessId
  $currentId = $ProcessId
  for ($i = 0; $i -lt 8; $i++) {
    $info = Get-ProcessInfo $currentId
    if (-not $info -or -not $info.ParentProcessId) { break }
    $parentId = [int]$info.ParentProcessId
    if ($parentId -le 0 -or $parentId -eq $currentId) { break }
    if (Test-StudioProcess $parentId $Port) {
      $rootId = $parentId
      $currentId = $parentId
      continue
    }
    break
  }
  return $rootId
}

function Stop-StudioPort([int]$Port) {
  $listeners = @(Get-StudioListeners $Port)
  if ($listeners.Count -eq 0) {
    Write-Host ('[dev] port {0}: nothing listening' -f $Port)
    return
  }

  foreach ($item in $listeners) {
    if (-not $item.Owned) {
      Write-Warning ('[dev] port {0}: PID {1} ({2}) does not look like this repo - leaving it alone' -f $Port, $item.Pid, $item.Name)
      Write-Warning ('[dev]   {0}' -f $item.CommandLine)
      continue
    }

    $killId = Get-StudioRootPid $item.Pid $Port
    Write-Host ('[dev] stopping PID {0} (tree root {1}) on :{2} ({3})' -f $item.Pid, $killId, $Port, $item.Name)
    & taskkill.exe /PID $killId /T /F 2>$null | Out-Null
  }
}

function Wait-PortFree([int]$Port, [int]$Seconds) {
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    $pids = @(Get-ListenPids $Port)
    if ($pids.Count -eq 0) { return $true }
    Start-Sleep -Milliseconds 250
  }
  return (@(Get-ListenPids $Port).Count -eq 0)
}

function Wait-HttpOk([string]$Url, [int]$Seconds) {
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
        return $true
      }
    } catch {
      # still starting
    }
    Start-Sleep -Milliseconds 400
  }
  return $false
}

function Show-Status {
  foreach ($port in @($ApiPort, $WebPort)) {
    $listeners = @(Get-StudioListeners $port)
    if ($listeners.Count -eq 0) {
      Write-Host ('[dev] :{0}  free' -f $port)
      continue
    }
    foreach ($item in $listeners) {
      $tag = if ($item.Owned) { 'studio' } else { 'OTHER' }
      Write-Host ('[dev] :{0}  PID {1}  [{2}]  {3}' -f $port, $item.Pid, $tag, $item.Name)
      if ($item.CommandLine) {
        Write-Host ('         {0}' -f $item.CommandLine)
      }
    }
  }
}

function Invoke-Stop {
  Write-Host ('[dev] stopping studio listeners on {0} / {1} ...' -f $ApiPort, $WebPort)
  Stop-StudioPort $ApiPort
  Stop-StudioPort $WebPort

  if (-not (Wait-PortFree $ApiPort $WaitSeconds)) {
    throw ('[dev] port {0} still in use after stop' -f $ApiPort)
  }
  if (-not (Wait-PortFree $WebPort $WaitSeconds)) {
    throw ('[dev] port {0} still in use after stop' -f $WebPort)
  }
  Write-Host '[dev] ports free'
}

function Invoke-Start {
  Push-Location $RepoRoot
  try {
    if (-not (Test-Path (Join-Path $RepoRoot 'node_modules\concurrently'))) {
      Write-Host '[dev] installing root npm deps (concurrently)...'
      npm install
    }

    Write-Host ('[dev] starting API (:{0}) + web (:{1}) via npm run dev' -f $ApiPort, $WebPort)
    Write-Host '[dev] Ctrl+C stops both (concurrently -k).'
    npm run dev
  } finally {
    Pop-Location
  }
}

switch ($Action) {
  'status' { Show-Status }
  'stop' { Invoke-Stop; Show-Status }
  'start' {
    # Clear stale studio listeners first so reload orphans cannot serve old code.
    Invoke-Stop
    Invoke-Start
  }
  'restart' {
    Invoke-Stop
    # Start in a new window so restart can return after health checks.
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'npm run dev' -WorkingDirectory $RepoRoot -WindowStyle Normal
    Write-Host '[dev] waiting for API health...'
    if (-not (Wait-HttpOk ("http://127.0.0.1:{0}/api/health" -f $ApiPort) $WaitSeconds)) {
      throw ('[dev] API did not become healthy on :{0}' -f $ApiPort)
    }
    Write-Host '[dev] waiting for web...'
    if (-not (Wait-HttpOk ("http://127.0.0.1:{0}/" -f $WebPort) $WaitSeconds)) {
      throw ('[dev] web did not respond on :{0}' -f $WebPort)
    }
    Write-Host '[dev] restart complete'
    Show-Status
  }
}

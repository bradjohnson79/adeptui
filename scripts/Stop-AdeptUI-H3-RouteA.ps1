#Requires -Version 5.1
<#
.SYNOPSIS
  Stop the isolated MiniMax H3 Route A ComfyUI runtime (:8192).

.DESCRIPTION
  Kills every python.exe running the isolated ComfyUI Route A main.py on port
  8192 and confirms the port is free. Safe to run repeatedly. Use before a
  clean restart or to recover from VRAM contention / DB-lock corruption.

  Usage from repo root:
    .\scripts\Stop-AdeptUI-H3-RouteA.ps1
#>
$ErrorActionPreference = 'SilentlyContinue'

$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
  $_.CommandLine -like '*minimax-h3*comfyui*main.py*' -and $_.CommandLine -like '*--port*8192*'
}
if (-not $procs) {
  Write-Host "NO_H3_PROCESSES_RUNNING"
} else {
  foreach ($p in $procs) {
    Write-Host ("KILLING PID " + $p.ProcessId)
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Seconds 5
}

$still = Get-NetTCPConnection -LocalPort 8192 -State Listen -ErrorAction SilentlyContinue
if ($still) {
  foreach ($owner in $still.OwningProcess) {
    $proc = Get-Process -Id $owner -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -eq 'python') {
      Write-Host ("FORCE KILLING OWNER PID " + $owner)
      Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
    }
  }
  Start-Sleep -Seconds 3
  $still2 = Get-NetTCPConnection -LocalPort 8192 -State Listen -ErrorAction SilentlyContinue
  if ($still2) {
    Write-Error ("8192 still occupied by PID " + $still2.OwningProcess)
    exit 1
  }
  Write-Host "OK: 8192 freed after force kill"
} else {
  Write-Host "OK: 8192 is free"
}

$leftover = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
  $_.CommandLine -like '*minimax-h3*comfyui*main.py*' -and $_.CommandLine -like '*--port*8192*'
}
if ($leftover) {
  Write-Error ("LEFTOVER_PIDS: " + ($leftover.ProcessId -join ','))
  exit 1
}
Write-Host "CLEAN: no H3 Route A processes remain"
exit 0

#Requires -Version 5.1
<#
.SYNOPSIS
  Thin shim to the Python Runtime Supervisor.
  Does NOT start retired :8760 (Law 15). Local creator UI is Vite :5173 or hosted Vercel.
#>
param(
  [switch]$NoBrowser,
  [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Resolve-Path ".").Path }
$py = Join-Path $RepoRoot "studio-api\.venv\Scripts\python.exe"
$launcher = Join-Path $RepoRoot "scripts\run_runtime_supervisor.py"
Write-Host "Starting Adept UI Runtime Supervisor (no :8760)."
& $py $launcher start
$code = $LASTEXITCODE
Write-Host "Creator UI (local): http://127.0.0.1:5173/"
Write-Host "Studio API:         http://127.0.0.1:8758/api/healthz"
Write-Host "Retired :8760 was not started."
exit $code

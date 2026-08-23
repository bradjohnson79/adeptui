#Requires -Version 5.1
<#
.SYNOPSIS
  Thin shim to the Python Runtime Supervisor (same owner as Start-AdeptBetaBackend).
  Does NOT start retired :8760.
#>
param()

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Resolve-Path ".").Path }
$py = Join-Path $RepoRoot "studio-api\.venv\Scripts\python.exe"
$launcher = Join-Path $RepoRoot "scripts\run_runtime_supervisor.py"
& $py $launcher start
exit $LASTEXITCODE

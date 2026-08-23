#Requires -Version 5.1
<#
.SYNOPSIS
  Thin shim: start Adept UI services via the Python Runtime Supervisor.
  Does NOT start retired :8760.
#>
param(
  [switch]$Force,
  [switch]$NoCloudflare,
  [switch]$NoBrowser,
  [switch]$StartOllama
)

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Resolve-Path ".").Path }
$py = Join-Path $RepoRoot "studio-api\.venv\Scripts\python.exe"
$launcher = Join-Path $RepoRoot "scripts\run_runtime_supervisor.py"
if (-not (Test-Path $py)) { Write-Error "Studio API venv Python not found: $py"; exit 1 }
$argList = @($launcher, "start")
if ($NoCloudflare) { $argList += "--no-cloudflare" }
if ($StartOllama) { $argList += "--start-ollama" }
# -Force and -NoBrowser are accepted for compatibility; supervisor never opens a browser or :8760.
& $py @argList
exit $LASTEXITCODE

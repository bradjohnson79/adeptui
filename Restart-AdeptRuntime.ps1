#Requires -Version 5.1
param([switch]$Force)

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Resolve-Path ".").Path }
$py = Join-Path $RepoRoot "studio-api\.venv\Scripts\python.exe"
$launcher = Join-Path $RepoRoot "scripts\run_runtime_supervisor.py"
$argList = @($launcher, "restart")
if ($Force) { $argList += "--force" }
& $py @argList
exit $LASTEXITCODE

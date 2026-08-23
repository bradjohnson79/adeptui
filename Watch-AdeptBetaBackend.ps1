#Requires -Version 5.1
<#
.SYNOPSIS
  Thin shim: one Python watchdog. Do not run this beside a second supervisor watch.
#>
param(
  [int]$IntervalSec = 15,
  [switch]$Once
)

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Resolve-Path ".").Path }
$py = Join-Path $RepoRoot "studio-api\.venv\Scripts\python.exe"
$launcher = Join-Path $RepoRoot "scripts\run_runtime_supervisor.py"
$argList = @($launcher, "watch", "--interval", "$IntervalSec")
if ($Once) { $argList += "--once" }
& $py @argList
exit $LASTEXITCODE

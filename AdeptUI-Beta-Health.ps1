#Requires -Version 5.1
<#
.SYNOPSIS
  Health for the product path: Studio API :8758. Does not treat :8760 as creator UI.
#>
$ErrorActionPreference = "Continue"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Resolve-Path ".").Path }
$py = Join-Path $RepoRoot "studio-api\.venv\Scripts\python.exe"
$launcher = Join-Path $RepoRoot "scripts\run_runtime_supervisor.py"
& $py $launcher status
$apiOk = $false
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:8758/api/healthz" -UseBasicParsing -TimeoutSec 5
  $apiOk = ($r.StatusCode -eq 200)
} catch {}
Write-Host ("API healthz :8758 = {0}" -f $(if ($apiOk) { "200" } else { "DOWN" }))
Write-Host "Retired :8760 is not a product health target."
if ($apiOk) { exit 0 } else { exit 1 }

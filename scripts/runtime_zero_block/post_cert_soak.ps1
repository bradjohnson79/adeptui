# Post-certification soak: 30–60 minutes of periodic health probes.
param(
  [int]$DurationMinutes = 30,
  [int]$IntervalSeconds = 60,
  [string]$ApiBase = "http://127.0.0.1:8758",
  [string]$ProjectId = "ae57714e-d43e-4cec-9bd9-0af2780fa185"
)

$ErrorActionPreference = "Continue"
$runId = Get-Content "C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\runtime-zero-block\artifacts\CURRENT_RUN_ID.txt"
$outDir = "C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\runtime-zero-block\artifacts\$runId\soak"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$end = (Get-Date).AddMinutes($DurationMinutes)
$samples = @()
$fail = 0
$idx = 0

Write-Host "Soak start $(Get-Date -Format o) for $DurationMinutes min → $outDir"

while ((Get-Date) -lt $end) {
  $idx++
  $sample = [ordered]@{
    index = $idx
    at = (Get-Date).ToUniversalTime().ToString("o")
  }
  try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $health = Invoke-RestMethod "$ApiBase/api/health" -TimeoutSec 20
    $sw.Stop()
    $sample.studioApiMs = $sw.ElapsedMilliseconds
    $sample.studioApiOk = [bool]$health.ok
  } catch {
    $sample.studioApiOk = $false
    $sample.studioApiError = $_.Exception.Message
    $fail++
  }
  try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $comfy = Invoke-RestMethod "$ApiBase/api/comfy/health" -TimeoutSec 30
    $sw.Stop()
    $sample.comfyMs = $sw.ElapsedMilliseconds
    $sample.comfyReachable = [bool]$comfy.reachable
  } catch {
    $sample.comfyReachable = $false
    $sample.comfyError = $_.Exception.Message
    $fail++
  }
  try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $caps = Invoke-RestMethod "$ApiBase/api/capabilities" -TimeoutSec 45
    $sw.Stop()
    $sample.capabilitiesMs = $sw.ElapsedMilliseconds
    $sample.blockerCount = @($caps.blockers).Count
    if ($sample.blockerCount -gt 0) { $fail++ }
  } catch {
    $sample.capabilitiesError = $_.Exception.Message
    $fail++
  }
  try {
    $body = @{ mode = "standard"; projectId = $ProjectId } | ConvertTo-Json
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $status = Invoke-RestMethod "$ApiBase/api/codirector/status/check" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 120
    $sw.Stop()
    $sample.statusMs = $sw.ElapsedMilliseconds
    $sample.statusIndicator = $status.summary.statusIndicator
    $sample.statusBlocked = $status.summary.blockedChecks
    $sample.timedOutChecks = @($status.results | Where-Object { $_.timedOut }).Count
    if ($sample.statusBlocked -gt 0) { $fail++ }
  } catch {
    $sample.statusError = $_.Exception.Message
    $fail++
  }
  try {
    $proc = Get-Process -Name "python","ComfyUI","node" -ErrorAction SilentlyContinue |
      Sort-Object WorkingSet64 -Descending |
      Select-Object -First 8 Name, Id, @{n="WS_MB";e={[math]::Round($_.WorkingSet64/1MB,1)}}
    $sample.topProcesses = $proc
  } catch {}

  $samples += [pscustomobject]$sample
  $samples | ConvertTo-Json -Depth 6 | Set-Content "$outDir\samples.json" -Encoding UTF8
  Write-Host ("[{0}] api={1}ms comfy={2} blockers={3} status={4}" -f $idx, $sample.studioApiMs, $sample.comfyMs, $sample.blockerCount, $sample.statusIndicator)
  Start-Sleep -Seconds $IntervalSeconds
}

$verdict = if ($fail -eq 0) { "GO - POST-CERTIFICATION SOAK STABLE" } else { "NO-GO - SOAK UNSTABLE" }
$summary = [ordered]@{
  durationMinutes = $DurationMinutes
  samples = $samples.Count
  failureEvents = $fail
  verdict = $verdict
  completedAt = (Get-Date).ToUniversalTime().ToString("o")
}
$summary | ConvertTo-Json -Depth 4 | Set-Content "$outDir\SOAK_SUMMARY.json" -Encoding UTF8
Write-Host $verdict
exit $(if ($fail -eq 0) { 0 } else { 1 })

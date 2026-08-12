# Adept UI Beta — 30-minute active soak monitor
$start = Get-Date
$end = $start.AddMinutes(30)
$failures = 0
$checks = 0
$log = "C:\AdeptFilmWorks\AIVideoStudio\data\runtime\logs\beta\soak_30min.log"

while ((Get-Date) -lt $end) {
  # Check healthz (fast path)
  try {
    $hz = Invoke-WebRequest -Uri "http://127.0.0.1:8758/api/healthz" -UseBasicParsing -TimeoutSec 5
    $hzOk = $hz.StatusCode -eq 200
  } catch {
    $hzOk = $false
  }
  if (!$hzOk) { $failures++ } else { $failures = 0 }

  # Check full health
  try {
    $api = Invoke-WebRequest -Uri "http://127.0.0.1:8758/api/health" -UseBasicParsing -TimeoutSec 30
    $apiOk = $api.StatusCode -eq 200
  } catch {
    $apiOk = $false
  }

  # Check web
  try {
    $web = Invoke-WebRequest -Uri "http://127.0.0.1:8760/__beta_web_health" -UseBasicParsing -TimeoutSec 10
    $webOk = $web.StatusCode -eq 200
  } catch {
    $webOk = $false
  }

  $checks++
  $elapsed = [math]::Round(((Get-Date) - $start).TotalMinutes, 1)
  $msg = "[${elapsed}min] web=$webOk api=$apiOk healthz=$hzOk consecutive_failures=$failures checks=$checks"
  Add-Content -Path $log -Value $msg
  Write-Host $msg
  Start-Sleep -Seconds 15
}

Add-Content -Path $log -Value "[SOAK_COMPLETE] checks=$checks consecutive_failures=$failures"
Write-Host "SOAK COMPLETE: $checks checks, $failures consecutive failures"
if ($failures -gt 0) { exit 1 } else { exit 0 }

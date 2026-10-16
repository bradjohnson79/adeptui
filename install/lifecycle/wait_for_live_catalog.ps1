# Wait until the live catalog and signature are byte-identical to the committed files.
$ErrorActionPreference = "Stop"
$catalog = if ($args.Count -ge 1) { $args[0] } else { "www/public/releases/current.json" }
$signature = if ($args.Count -ge 2) { $args[1] } else { "www/public/releases/current.sig" }
$expectedJson = (Get-FileHash -Algorithm SHA256 -Path $catalog).Hash.ToLower()
$expectedSig = (Get-FileHash -Algorithm SHA256 -Path $signature).Hash.ToLower()
for ($i = 1; $i -le 40; $i++) {
  $tmp = Join-Path $env:RUNNER_TEMP "live-catalog-$i"
  New-Item -ItemType Directory -Force -Path $tmp | Out-Null
  & curl.exe -fsSL "https://adeptui.org/releases/current.json" -o (Join-Path $tmp "current.json")
  if ($LASTEXITCODE -ne 0) { Write-Host "waiting for live catalog ($i/40): catalog download failed"; Start-Sleep -Seconds 30; continue }
  & curl.exe -fsSL "https://adeptui.org/releases/current.sig" -o (Join-Path $tmp "current.sig")
  if ($LASTEXITCODE -ne 0) { Write-Host "waiting for live catalog ($i/40): signature download failed"; Start-Sleep -Seconds 30; continue }
  $gotJson = (Get-FileHash -Algorithm SHA256 -Path (Join-Path $tmp "current.json")).Hash.ToLower()
  $gotSig = (Get-FileHash -Algorithm SHA256 -Path (Join-Path $tmp "current.sig")).Hash.ToLower()
  if ($gotJson -eq $expectedJson -and $gotSig -eq $expectedSig) {
    Write-Host "LIVE CATALOG MATCH: json=$gotJson sig=$gotSig"
    exit 0
  }
  Write-Host "waiting for live catalog ($i/40): json=$gotJson expected=$expectedJson"
  Start-Sleep -Seconds 30
}
Write-Host "FAIL: live catalog never matched the committed bytes"
exit 1

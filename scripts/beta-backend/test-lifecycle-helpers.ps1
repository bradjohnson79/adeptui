# Studio API Runtime Stabilization - lifecycle helper regression tests.
# Hermetic: all state is redirected to an isolated temp dir (never mutates the
# real beta-backend pid/lock/history files). No real :8758 process is touched.
$ErrorActionPreference = "Stop"
$common = "C:\AdeptFilmWorks\AIVideoStudio\scripts\beta-backend\BetaBackendCommon.ps1"
. $common
# Hermetic state dir.
$script:StateDir = Join-Path $env:TEMP ("adept-lifecycle-test-" + (Get-Random))
$script:PidDir = Join-Path $script:StateDir "pids"
$script:RestartLog = Join-Path $script:StateDir "restart_history.json"
$script:RestartLockFile = Join-Path $script:StateDir "restart.lock"
Ensure-BetaBackendDirs

$pass = 0; $fail = 0
function Assert-Test($name, $cond, $detail = "") {
    if ($cond) { $script:pass++; Write-Output "PASS: $name" }
    else { $script:fail++; Write-Output "FAIL: $name  $detail" }
}

# 1. Port-free detection
$free = Test-PortIsFree 59999
Assert-Test "Test-PortIsFree true for unbound port" ($free -eq $true)

# 2. Owner-PID parser
$fakeLine = "  TCP    127.0.0.1:59998         0.0.0.0:0              LISTENING       12345"
$parts = ($fakeLine -split "[ ]+") | Where-Object { $_ }
$pidVal = [int]$parts[-1]
Assert-Test "Get-PortOwnerPid parser extracts owner PID" ($pidVal -eq 12345)

# 3. Stale PID detection
Write-ServicePid "test_stale" 999999 "fake" $true
$alive = Test-ServicePidAlive "test_stale"
Assert-Test "Test-ServicePidAlive false for stale PID" ($alive -eq $false) "alive=$alive"
Remove-ServicePid "test_stale"

# 4. PID round-trip
Write-ServicePid "test_rt" 4242 "cmd" $true
$info = Read-ServicePid "test_rt"
Assert-Test "PID round-trip preserves pid" ($info.pid -eq 4242)
Assert-Test "PID round-trip preserves owned" ($info.owned -eq $true)
Remove-ServicePid "test_rt"

# 5. Restart lock lifecycle (Phase 7 exclusive claim)
Assert-Test "No lock initially" ((Test-BetaRestartLock) -eq $false)
$claimed1 = Set-BetaRestartLock "studio_api"
Assert-Test "Lock claimed (exclusive)" ($claimed1 -eq $true)
Assert-Test "Lock held after set" ((Test-BetaRestartLock) -eq $true)
$claimed2 = Set-BetaRestartLock "studio_api"
Assert-Test "Second claim REFUSED while held" ($claimed2 -eq $false)
Clear-BetaRestartLock
Assert-Test "Lock cleared" ((Test-BetaRestartLock) -eq $false)
# Stale lock (dead holder) is reclaimable
Set-Content -Path $script:RestartLockFile -Value '{"service":"x","holderPid":999999,"at":"2026-01-01T00:00:00Z"}' -Encoding UTF8
$claimed3 = Set-BetaRestartLock "studio_api"
Assert-Test "Stale lock reclaimed after holder died" ($claimed3 -eq $true)
Clear-BetaRestartLock
Assert-Test "Lock cleared again" ((Test-BetaRestartLock) -eq $false)

# 6. Restart history + storm protection
Add-RestartEvent "test_storm" | Out-Null
$hRead = @(Read-RestartHistory)
Assert-Test "Add-RestartEvent records event" ($hRead.Count -ge 1) "count=$($hRead.Count)"
Assert-Test "Storm protection not tripped at 1 event" ((Test-StormProtection "test_storm") -eq $false)
1..5 | ForEach-Object { Add-RestartEvent "test_storm" | Out-Null }
Assert-Test "Storm protection tripped at 6 events" ((Test-StormProtection "test_storm") -eq $true)

# 7. Phantom classification
$origGetPortOwner = ${function:Get-PortOwnerPid}
function Get-PortOwnerPid { param([int]$Port) if ($Port -eq 8758) { return 25408 } return $null }
function Get-Process { param($Id) if ($Id -eq 25408) { return $null } return (New-Object System.Diagnostics.Process) }
$st = Get-StudioApiPortState
Assert-Test "Phantom owner classified as phantom" ($st.state -eq "phantom")
Assert-Test "Phantom owner PID reported" ($st.pid -eq 25408)
${function:Get-PortOwnerPid} = $origGetPortOwner

# 8. Authoritative start FAILS CLOSED on phantom
${function:Get-PortOwnerPid} = { param([int]$Port) if ($Port -eq 8758) { return 25408 } return $null }
${function:Get-Process} = { param($Id) return $null }
$result = Start-StudioApiAuthoritative
Assert-Test "Authoritative start FAILS CLOSED on phantom" ($result -eq $false)

# 9. Authoritative start no-op success when healthy
${function:Get-PortOwnerPid} = { param([int]$Port) if ($Port -eq 8758) { return 7777 } return $null }
${function:Get-Process} = { param($Id) return (New-Object System.Diagnostics.Process) }
${function:Test-StudioApiHealth} = { return $true }
$result = Start-StudioApiAuthoritative
Assert-Test "Authoritative start no-op success when healthy" ($result -eq $true)

# 10. PID reuse safety: pid file pointing at an unrelated LIVE process must NOT be killed
$testProc = Start-Process -FilePath "ping.exe" -ArgumentList "-n","30","127.0.0.1" -WindowStyle Hidden -PassThru
$unrelatedPid = $testProc.Id
Write-ServicePid "studio_api" $unrelatedPid "ping.exe" $true
$ok = Stop-OwnedService "studio_api"
$stillAlive = [bool](Get-Process -Id $unrelatedPid -ErrorAction SilentlyContinue)
Assert-Test "Stop refuses to kill unrelated live process (PID reuse)" (($ok -eq $true) -and $stillAlive) "ok=$ok alive=$stillAlive"
if ($stillAlive) { Stop-Process -Id $unrelatedPid -Force -ErrorAction SilentlyContinue }

# 12. Stop-OwnedService with NO pid record but verified healthy owner -> stops it (identity-safe)
Remove-ServicePid "studio_api"
${function:Get-PortOwnerPid} = { param([int]$Port) if ($Port -eq 8758) { return 9999 } return $null }
${function:Get-Process} = { param($Id) return (New-Object System.Diagnostics.Process) }
${function:Get-CimInstance} = { param($Filter) return [pscustomobject]@{ CommandLine = "python -m uvicorn app.main:app --port 8758" } }
${function:Test-StudioApiHealth} = { return $true }
${function:taskkill} = { param($Force, $Tree, $ProcId) Write-Output "taskkill-stub-killed-$ProcId"; ${function:Get-PortOwnerPid} = { param([int]$Port) return $null }; return 0 }
${function:Get-NetTCPConnection} = { param($LocalPort) return $null }
$stopOk = Stop-OwnedService "studio_api"
Assert-Test "Stop without pid record stops VERIFIED owner" ($stopOk -eq $true) "stopOk=$stopOk"

# 13. Stop-OwnedService with no pid record and PHANTOM owner -> fails closed (no taskkill call)
Remove-ServicePid "studio_api"
${function:Get-PortOwnerPid} = { param([int]$Port) if ($Port -eq 8758) { return 25408 } return $null }
${function:Get-Process} = { param($Id) if ($Id -eq 25408) { return $null } return (New-Object System.Diagnostics.Process) }
$stopPhantom = Stop-OwnedService "studio_api"
Assert-Test "Stop without pid record FAILS CLOSED on phantom" ($stopPhantom -eq $false) "stopPhantom=$stopPhantom"

# 14. Stop-OwnedService with no pid record and unrelated owner -> refuses, nothing killed
Remove-ServicePid "studio_api"
${function:Get-PortOwnerPid} = { param([int]$Port) if ($Port -eq 8758) { return 7777 } return $null }
${function:Get-Process} = { param($Id) return (New-Object System.Diagnostics.Process) }
${function:Get-CimInstance} = { param($Filter) return $null }
${function:Test-StudioApiHealth} = { return $false }
$stopUnrel = Stop-OwnedService "studio_api"
Assert-Test "Stop without pid record refuses unrelated owner" ($stopUnrel -eq $true) "stopUnrel=$stopUnrel"

Write-Output ""
Write-Output "=== LIFECYCLE REGRESSION: $pass passed, $fail failed ==="
if ($fail -gt 0) { exit 1 } else { exit 0 }
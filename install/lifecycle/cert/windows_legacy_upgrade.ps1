$ErrorActionPreference = "Stop"
$evidence = Join-Path $env:RUNNER_TEMP "adept-cert-upgrade"
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$catalog = Get-Content -Raw (Join-Path $PSScriptRoot "legacy-releases.json") | ConvertFrom-Json

function Remove-IfInstalled {
  $program = Join-Path $env:LOCALAPPDATA "Programs\Adept UI"
  $uninstaller = Join-Path $program "Uninstall Adept UI.exe"
  if (Test-Path $uninstaller) {
    $removed = Start-Process -FilePath $uninstaller -ArgumentList "/S" -Wait -PassThru
    if ($removed.ExitCode -ne 0) { throw "Uninstall exited $($removed.ExitCode)" }
  }
}

function Install-Legacy([string]$version) {
  Remove-IfInstalled
  $spec = $catalog.$version.windows
  $dest = Join-Path $env:TEMP $spec.fileName
  Invoke-WebRequest -Uri $spec.url -OutFile $dest -UseBasicParsing
  $hash = (Get-FileHash -Algorithm SHA256 -Path $dest).Hash.ToLower()
  if ($hash -ne $spec.sha256) { throw "Legacy $version checksum $hash" }
  if ((Get-Item $dest).Length -ne [long]$spec.bytes) { throw "Legacy $version size" }
  $installed = Start-Process -FilePath $dest -ArgumentList "/S" -Wait -PassThru
  if ($installed.ExitCode -ne 0) { throw "Legacy $version install exited $($installed.ExitCode)" }
}

function Invoke-Automatic([string]$version) {
  Install-Legacy $version
  $program = Join-Path $env:LOCALAPPDATA "Programs\Adept UI"
  $keep = Join-Path $env:APPDATA "Adept UI\upgrade-keep.txt"
  New-Item -ItemType Directory -Force -Path (Split-Path $keep) | Out-Null
  Set-Content -Path $keep -Value "keep-$version" -NoNewline
  $launcher = Join-Path $program "Adept Launcher.exe"
  $log = Join-Path $evidence "launcher-$version.log"
  if (Test-Path $launcher) {
    $proc = Start-Process -FilePath $launcher -RedirectStandardOutput $log -RedirectStandardError "$log.err" -PassThru -WindowStyle Hidden
    if (-not $proc.WaitForExit(90000)) {
      Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
      "AUTOMATIC_UPGRADE_${version}: NO-GO launcher did not finish" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
    }
  } else {
    "AUTOMATIC_UPGRADE_${version}: NO-GO launcher was not beside Electron" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
  }
  $versionText = Get-Content (Join-Path $program "resources\version.json") -Raw
  if ((Get-Content $keep -Raw) -ne "keep-$version") { throw "User data lost during $version launch" }
  if ($versionText -match '"version": "1.1.6"') {
    "AUTOMATIC_UPGRADE_${version}: GO" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
  } else {
    "AUTOMATIC_UPGRADE_${version}: NO-GO installed version stayed $version. This published launcher cannot install 1.1.6 by itself. One public installer run is required." | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
  }
  Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "*\Programs\Adept UI\*" } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
}

Invoke-Automatic "1.1.3"
Invoke-Automatic "1.1.4"
Invoke-Automatic "1.1.5"

$env:ADEPT_ASSUME_YES = "1"
$env:ADEPT_NO_LAUNCH = "1"
& powershell -NoProfile -Command "irm https://adeptui.org/install.ps1 | iex"
if ($LASTEXITCODE -ne 0) { throw "Migration installer exited $LASTEXITCODE" }
$program = Join-Path $env:LOCALAPPDATA "Programs\Adept UI"
$versionText = Get-Content (Join-Path $program "resources\version.json") -Raw
if ($versionText -notmatch '"version": "1.1.6"') { throw "Migration did not install 1.1.6" }
if ((Get-Content (Join-Path $env:APPDATA "Adept UI\upgrade-keep.txt") -Raw) -ne "keep-1.1.5") { throw "Migration removed user data" }
"MIGRATION_REINSTALL: PASS" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
"LEGACY_REQUIRES_PUBLIC_INSTALLER: 1.1.3 1.1.4 1.1.5" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
Get-Content (Join-Path $evidence "result.txt")

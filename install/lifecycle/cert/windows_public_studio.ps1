$ErrorActionPreference = "Stop"
$evidence = Join-Path $env:RUNNER_TEMP "adept-cert-windows"
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$os = Get-CimInstance Win32_OperatingSystem
@(
  "CAPTION=$($os.Caption)"
  "VERSION=$($os.Version)"
  "ARCH=$($env:PROCESSOR_ARCHITECTURE)"
  "COMMIT=$($env:GITHUB_SHA)"
) | Set-Content -Path (Join-Path $evidence "os.txt")
"ENVIRONMENT: GitHub windows-latest desktop session." | Set-Content -Path (Join-Path $evidence "environment.txt")

$env:ADEPT_ASSUME_YES = "1"
$env:ADEPT_NO_LAUNCH = "1"
& powershell -NoProfile -Command "irm https://adeptui.org/install.ps1 | iex"
if ($LASTEXITCODE -ne 0) { throw "install.ps1 exited $LASTEXITCODE" }
"INSTALLATION: PASS" | Tee-Object -FilePath (Join-Path $evidence "result.txt")

$program = Join-Path $env:LOCALAPPDATA "Programs\Adept UI"
$launcher = Join-Path $program "Adept Launcher.exe"
$electron = Join-Path $program "Adept UI.exe"
if (-not (Test-Path $launcher)) { throw "Launcher missing at $launcher" }
if (-not (Test-Path $electron)) { throw "Electron missing at $electron" }
if ((Split-Path $launcher -Parent) -ne $program) { throw "Launcher is not beside Electron" }
"LAUNCHER_SIBLING: PASS" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append

$versionFile = Join-Path $program "resources\version.json"
$versionText = Get-Content $versionFile -Raw
if ($versionText -notmatch '"version": "1.1.5"') { throw "Installed version is not 1.1.5" }
"INSTALLED_VERSION: 1.1.5" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append

$shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Adept UI.lnk"
$target = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcut).TargetPath
if ($target -notlike "*\Adept Launcher.exe") { throw "SHORTCUT: FAIL $target" }
"SHORTCUT: PASS $target" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append

$keep = Join-Path $env:APPDATA "Adept UI\project-keep.txt"
New-Item -ItemType Directory -Force -Path (Split-Path $keep) | Out-Null
Set-Content -Path $keep -Value "disposable-project" -NoNewline

function Stop-Adept {
  Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "*\Programs\Adept UI\*" } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Seconds 2
}

function Wait-Studio([string]$label) {
  $seenParent = $false
  $deadline = (Get-Date).AddSeconds(25)
  while ((Get-Date) -lt $deadline) {
    $child = Get-CimInstance Win32_Process -Filter "Name = 'Adept UI.exe'" | Select-Object -First 1
    if ($child) {
      $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $($child.ParentProcessId)"
      if ($parent -and $parent.Name -eq "Adept Launcher.exe") { $seenParent = $true; break }
    }
    Start-Sleep -Milliseconds 100
  }
  $title = ""
  for ($i = 0; $i -lt 45; $i++) {
    $title = @(Get-Process | Where-Object { $_.MainWindowTitle -match "Adept UI" } | Select-Object -ExpandProperty MainWindowTitle -First 1)
    if ($title) { break }
    Start-Sleep -Seconds 2
  }
  if (-not $title) { throw "STUDIO_WINDOW_${label}: FAIL" }
  $startupFile = Join-Path $env:USERPROFILE ".adept-ui\startup-update.json"
  if (-not $seenParent -and -not (Test-Path $startupFile)) { throw "LAUNCHER_FIRST_${label}: FAIL" }
  $windowCount = @(Get-Process | Where-Object { $_.MainWindowTitle -match "Adept UI" }).Count
  if ($windowCount -ne 1) { throw "WINDOW_COUNT_${label}: FAIL $windowCount" }
  $consoles = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^(cmd|powershell|pwsh|conhost)\.exe$' -and $_.CommandLine -match 'Adept Launcher'
  })
  if ($consoles.Count -gt 0) { throw "TERMINAL_WINDOW_${label}: FAIL $($consoles[0].CommandLine)" }
  try {
    Add-Type -AssemblyName System.Windows.Forms,System.Drawing
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bitmap.Save((Join-Path $evidence "studio-$label.png"))
    $graphics.Dispose()
    $bitmap.Dispose()
    "SCREENSHOT_${label}: PASS" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
  } catch {
    "SCREENSHOT_${label}: FAIL $($_.Exception.Message)" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
  }
  if ($seenParent) {
    "LAUNCHER_PARENT_${label}: OBSERVED" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
  } else {
    "LAUNCHER_PARENT_${label}: NOT_OBSERVED" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
  }
  "LAUNCHER_FIRST_${label}: PASS" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
  "STUDIO_WINDOW_${label}: PASS $title" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
  "TERMINAL_WINDOW_${label}: PASS" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
}

Start-Process -FilePath $target | Out-Null
Wait-Studio "first"
$registryPath = Join-Path $env:USERPROFILE ".adept-ui\registry.json"
$startupPath = Join-Path $env:USERPROFILE ".adept-ui\startup-update.json"
if (-not (Test-Path $registryPath)) { throw "REGISTRY: FAIL" }
$registry = Get-Content $registryPath -Raw | ConvertFrom-Json
if ($registry.installedVersion -ne "1.1.5") { throw "REGISTRY_VERSION: FAIL $($registry.installedVersion)" }
$startup = Get-Content $startupPath -Raw | ConvertFrom-Json
if ($startup.code -ne "NO_UPDATE") { throw "UPDATE_CHECK: FAIL $($startup.code)" }
"UPDATE_CHECK: NO_UPDATE" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
Stop-Adept
if (Get-Process -Name "Adept UI" -ErrorAction SilentlyContinue) { throw "SHUTDOWN: FAIL" }
"SHUTDOWN: PASS" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
Start-Process -FilePath $target | Out-Null
Wait-Studio "restart"
Stop-Adept
"RESTART: PASS" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append

$uninstaller = Join-Path $program "Uninstall Adept UI.exe"
$removed = Start-Process -FilePath $uninstaller -ArgumentList "/S" -Wait -PassThru
if ($null -ne $removed.ExitCode -and $removed.ExitCode -ne 0) { throw "Uninstall exited $($removed.ExitCode)" }
if (Test-Path $electron) { throw "Electron remained after uninstall" }
if ((Get-Content $keep -Raw) -ne "disposable-project") { throw "User data was removed" }
"UNINSTALL_PRESERVES_USER_DATA: PASS" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append

& powershell -NoProfile -Command "irm https://adeptui.org/install.ps1 | iex"
if ($LASTEXITCODE -ne 0) { throw "reinstall exited $LASTEXITCODE" }
if (-not (Test-Path $launcher)) { throw "Launcher missing after reinstall" }
if ((Get-Content $keep -Raw) -ne "disposable-project") { throw "User data missing after reinstall" }
"REINSTALL: PASS" | Tee-Object -FilePath (Join-Path $evidence "result.txt") -Append
Get-Content (Join-Path $evidence "result.txt")

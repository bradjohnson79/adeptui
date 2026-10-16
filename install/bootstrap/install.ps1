# Adept UI installer.
# Official catalog: https://adeptui.org/releases/current.json
# Inspect this file before running it. A GitHub branch is not an installation source.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if (-not [Environment]::Is64BitOperatingSystem) {
  Write-Host "Adept UI does not have a certified build for this Windows architecture."
  exit 3
}

Write-Host "Detected windows x64."
$catalogUrl = "https://adeptui.org/releases/current.json"
$signatureUrl = "https://adeptui.org/releases/current.sig"
$modulus = "tuu/mw3fdps5KL/zeDHsrUFB++x17OEhlqThBknqp4Epl0Z63H/A2vLlEdST/pfoa1dqKbIpNAhdc/R3rAOPWXRstbgtxU+02Zq/Zm6dDHLZAEvmzwKgnzuvPc83kee4uIxqJMzzcYPoEK/cKMtXDak7n3U+D2ij11P2C96EomLdBwX5gXUPZjqHPDG8Y/1Vrzi8cVTGT8tsIhD3r3gY2z+poRvLbrJuMx1DyKL62cfVS5K9vub3+cpgF5NGiSWSThWg2GWfGJa0zXn+txtOvoUJoDLR0uRW8bAAs7VMSGcdOXuvQt9SCtfLDD8gflMvtVtgxuf1Rgwa8VJK5fS8xuiM+feZ/tLnhG5zti17BOSlHQsrzwpjbCYNHIrjMaHXszFVVcI9JugjmgWOCFUcFx0kj2EpxmBNqBdBipekT1RGh8QUxva7FGN6fnoBk2Jf8EiCED5kIp7/6Fals9Og4aVyrbOZ31pf+Ziq5fmjDbv7/wMiSHmje/FMcrplukdr"

try {
  $catalogBytes = (Invoke-WebRequest -Uri $catalogUrl -UseBasicParsing).Content
  $signatureText = (Invoke-WebRequest -Uri $signatureUrl -UseBasicParsing).Content.Trim()
} catch {
  Write-Host "The Adept UI release catalog could not be downloaded."
  exit 4
}

$catalogRaw = [Text.Encoding]::UTF8.GetBytes($catalogBytes)
$signature = [Convert]::FromBase64String($signatureText)
$rsa = [Security.Cryptography.RSA]::Create()
$parameters = New-Object Security.Cryptography.RSAParameters
$parameters.Modulus = [Convert]::FromBase64String($modulus)
$parameters.Exponent = [byte[]](1, 0, 1)
$rsa.ImportParameters($parameters)
$sha = [Security.Cryptography.HashAlgorithmName]::SHA256
$padding = [Security.Cryptography.RSASignaturePadding]::Pkcs1
$verified = $false
try {
  $verified = $rsa.VerifyData($catalogRaw, $signature, $sha, $padding)
} catch {
  $verified = $rsa.VerifyData($catalogRaw, $sha, $padding, $signature)
}
if (-not $verified) {
  Write-Host "The release catalog signature does not match the pinned Adept UI key."
  exit 4
}

$catalog = $catalogBytes | ConvertFrom-Json
$artifact = @($catalog.artifacts) | Where-Object { $_.platform -eq "windows" -and $_.arch -eq "x64" } | Select-Object -First 1
if (-not $artifact) {
  Write-Host "No approved Windows build is in the Adept UI release catalog."
  exit 3
}
if ($artifact.url -notmatch '^https://github\.com/bradjohnson79/adeptui/releases/download/v') {
  Write-Host "The catalog does not point at an official Adept UI release."
  exit 4
}

$destination = Join-Path $env:TEMP ([IO.Path]::GetFileName($artifact.fileName))
$expectedBytes = [long]$(if ($artifact.bytes) { $artifact.bytes } else { $artifact.size })
$expectedMB = [math]::Round($expectedBytes / 1MB, 1)
Write-Host "Downloading $($artifact.fileName) ($expectedMB MB)"
$downloadStart = Get-Date
try {
  Invoke-WebRequest -Uri $artifact.url -OutFile $destination -UseBasicParsing
} catch {
  if (Test-Path $destination) { Remove-Item $destination -Force }
  Write-Host "The download did not finish."
  exit 5
}
$actualBytes = (Get-Item $destination).Length
$elapsed = (Get-Date) - $downloadStart
$speedMBps = if ($elapsed.TotalSeconds -gt 0) { [math]::Round($actualBytes / 1MB / $elapsed.TotalSeconds, 1) } else { 0 }
$actualMB = [math]::Round($actualBytes / 1MB, 1)
Write-Host "Downloaded $actualMB MB in $([math]::Round($elapsed.TotalSeconds, 0))s ($speedMBps MB/s)"
$actual = (Get-FileHash -Algorithm SHA256 -Path $destination).Hash.ToLower()
if ($actual -ne ([string]$artifact.sha256).ToLower()) {
  Remove-Item $destination -Force
  Write-Host "The downloaded installer did not match the approved checksum."
  exit 5
}

function Read-Yes([string]$prompt) {
  if ($env:ADEPT_ASSUME_YES -eq "1") { return $true }
  $answer = Read-Host $prompt
  if ([string]::IsNullOrWhiteSpace($answer)) { return $true }
  return $answer.Trim().ToLower() -in @("y", "yes")
}

$createShortcut = Read-Yes "Create a desktop shortcut? [Y/n]"
$launchAfter = Read-Yes "Launch Adept UI after installation? [Y/n]"
$installed = Start-Process -FilePath $destination -ArgumentList "/S" -Wait -PassThru
if ($installed.ExitCode -ne 0) {
  Write-Host "Installation did not finish."
  exit $installed.ExitCode
}
$shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Adept UI.lnk"
if (-not $createShortcut -and (Test-Path $shortcut)) { Remove-Item $shortcut -Force }
$installDir = Join-Path $env:LOCALAPPDATA "Programs\Adept UI"
$launcher = Join-Path $installDir "Adept Launcher.exe"
$electron = Join-Path $installDir "Adept UI.exe"
$program = if (Test-Path $launcher) { $launcher } else { $electron }
if ($launchAfter -and $env:ADEPT_NO_LAUNCH -ne "1" -and (Test-Path $program)) { Start-Process $program }
Write-Host "Adept UI is installed."
exit 0

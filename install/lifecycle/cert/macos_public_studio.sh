#!/bin/bash
# Public macOS install. Gatekeeper is not bypassed and notarization is not claimed.
set -euo pipefail

evidence="${ADEPT_EVIDENCE:-$RUNNER_TEMP/adept-cert-macos}"
mkdir -p "$evidence"
{
  echo "SW_VERS=$(sw_vers -productVersion)"
  echo "BUILD=$(sw_vers -buildVersion)"
  echo "ARCH=$(uname -m)"
  echo "COMMIT=${GITHUB_SHA:-local}"
} | tee "$evidence/os.txt"
echo "ENVIRONMENT: GitHub macos-14 Apple Silicon desktop session." | tee "$evidence/environment.txt"
test "$(uname -m)" = "arm64"

export ADEPT_ASSUME_YES=1
export ADEPT_NO_LAUNCH=1
curl -fsSL "https://adeptui.org/install.sh" | bash
app="$HOME/Applications/Adept UI.app"
launcher="$app/Contents/MacOS/Adept UI"
electron="$app/Contents/MacOS/Adept UI.bin"
test -x "$launcher"
test -x "$electron"
echo "INSTALLATION: PASS" | tee "$evidence/result.txt"
echo "LAUNCHER: $launcher" | tee -a "$evidence/result.txt"
echo "ELECTRON: $electron" | tee -a "$evidence/result.txt"
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$app/Contents/Info.plist" | tee "$evidence/bundle-version.txt"
grep -q '1.1.6' "$evidence/bundle-version.txt"
echo "INSTALLED_VERSION: 1.1.6" | tee -a "$evidence/result.txt"
set +e
codesign --verify --deep --strict --verbose=2 "$app" >"$evidence/codesign.txt" 2>&1
codesign_status=$?
set -e
cat "$evidence/codesign.txt" || true
if [ "$codesign_status" -ne 0 ]; then
  echo "SIGNATURE_STRUCTURE: FAIL" | tee -a "$evidence/result.txt"
  exit 1
fi
echo "SIGNATURE_STRUCTURE: PASS" | tee -a "$evidence/result.txt"

keep="$HOME/Library/Application Support/Adept UI/project-keep.txt"
mkdir -p "$HOME/Library/Application Support/Adept UI"
echo "disposable-project" > "$keep"

set +e
spctl --assess --type execute "$app" >"$evidence/spctl.txt" 2>&1
spctl_status=$?
set -e
cat "$evidence/spctl.txt" || true
if [ "$spctl_status" -ne 0 ]; then
  echo "NOTARIZATION: EXTERNAL_BLOCKER" | tee -a "$evidence/result.txt"
  echo "GATEKEEPER: NOT_ACCEPTED" | tee -a "$evidence/result.txt"
  echo "STUDIO_WINDOW: EXTERNAL_BLOCKER Gatekeeper has not accepted the unsigned application. No quarantine bypass was used." | tee -a "$evidence/result.txt"
else
  echo "GATEKEEPER: ACCEPTED" | tee -a "$evidence/result.txt"
  open "$app"
  window_ok=0
  for _ in $(seq 1 30); do
    if pgrep -f "Adept UI.app/Contents/MacOS/Adept UI.bin" >/dev/null 2>&1; then
      window_ok=1
      break
    fi
    sleep 2
  done
  if [ "$window_ok" != "1" ]; then
    echo "STUDIO_WINDOW: FAIL" | tee -a "$evidence/result.txt"
    exit 1
  fi
  echo "ELECTRON: PASS" | tee -a "$evidence/result.txt"
  echo "STUDIO_WINDOW: PROCESS_STARTED" | tee -a "$evidence/result.txt"
  screencapture -x "$evidence/studio.png" || true
  pkill -f "Adept UI.app/Contents/MacOS" || true
  sleep 2
  if pgrep -f "Adept UI.app/Contents/MacOS" >/dev/null 2>&1; then
    echo "SHUTDOWN: FAIL" | tee -a "$evidence/result.txt"
    exit 1
  fi
  echo "SHUTDOWN: PASS" | tee -a "$evidence/result.txt"
  open "$app"
  sleep 5
  pgrep -f "Adept UI.app/Contents/MacOS/Adept UI.bin" >/dev/null
  echo "RESTART: PASS" | tee -a "$evidence/result.txt"
  pkill -f "Adept UI.app/Contents/MacOS" || true
fi

rm -rf "$app"
test ! -d "$app"
test "$(cat "$keep")" = "disposable-project"
echo "UNINSTALL_PRESERVES_USER_DATA: PASS" | tee -a "$evidence/result.txt"
curl -fsSL "https://adeptui.org/install.sh" | ADEPT_ASSUME_YES=1 ADEPT_NO_LAUNCH=1 bash
test -x "$launcher"
test "$(cat "$keep")" = "disposable-project"
echo "REINSTALL: PASS" | tee -a "$evidence/result.txt"
echo "NOTARIZATION: EXTERNAL_BLOCKER" | tee -a "$evidence/result.txt"
cat "$evidence/result.txt"

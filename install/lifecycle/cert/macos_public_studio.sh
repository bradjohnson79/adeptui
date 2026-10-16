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
app="$HOME/.adept-ui/app/Adept UI.app"
launcher="$app/Contents/MacOS/Adept UI"
electron="$app/Contents/MacOS/Adept UI.bin"
test -x "$launcher"
test -x "$electron"
echo "INSTALLATION: PASS" | tee "$evidence/result.txt"
echo "LAUNCHER: $launcher" | tee -a "$evidence/result.txt"
echo "ELECTRON: $electron" | tee -a "$evidence/result.txt"
bundle_exe="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$app/Contents/Info.plist")"
if [ "$bundle_exe" != "Adept UI" ]; then
  echo "BUNDLE_EXECUTABLE: FAIL $bundle_exe" | tee -a "$evidence/result.txt"
  exit 1
fi
echo "BUNDLE_EXECUTABLE: launcher" | tee -a "$evidence/result.txt"
version_file="$app/Contents/Resources/version.json"
test -f "$version_file"
cp "$version_file" "$evidence/version.json"
grep -q '"version": "1.1.5"' "$version_file"
echo "INSTALLED_VERSION: 1.1.5" | tee -a "$evidence/result.txt"
shortcut="$HOME/Desktop/Adept UI"
if [ -e "$shortcut" ]; then
  echo "DESKTOP_SHORTCUT: PASS $shortcut" | tee -a "$evidence/result.txt"
else
  echo "DESKTOP_SHORTCUT: NOT_VERIFIED" | tee -a "$evidence/result.txt"
fi
set +e
codesign --verify --deep --strict --verbose=2 "$app" >"$evidence/codesign.txt" 2>&1
codesign_status=$?
set -e
cat "$evidence/codesign.txt" || true
if [ "$codesign_status" -ne 0 ]; then
  echo "SIGNATURE_STRUCTURE: FAIL" | tee -a "$evidence/result.txt"
else
  echo "SIGNATURE_STRUCTURE: PASS" | tee -a "$evidence/result.txt"
fi

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
else
  echo "GATEKEEPER: ACCEPTED" | tee -a "$evidence/result.txt"
fi
set +e
open "$app" >"$evidence/open.txt" 2>&1
open_status=$?
set -e
cat "$evidence/open.txt" || true
window_ok=0
for _ in $(seq 1 30); do
  if pgrep -f "Adept UI.app/Contents/MacOS/Adept UI.bin" >/dev/null 2>&1; then
    window_ok=1
    break
  fi
  sleep 2
done
if [ "$window_ok" != "1" ]; then
  if [ "$spctl_status" -ne 0 ] || [ "$open_status" -ne 0 ]; then
    echo "STUDIO_WINDOW: EXTERNAL_BLOCKER the application did not launch. Gatekeeper was not bypassed." | tee -a "$evidence/result.txt"
  else
    echo "STUDIO_WINDOW: FAIL" | tee -a "$evidence/result.txt"
    exit 1
  fi
else
  echo "ELECTRON: PASS" | tee -a "$evidence/result.txt"
  titles="$(osascript -e 'tell application "System Events" to get name of every window of every process whose background only is false' 2>/dev/null || true)"
  printf '%s\n' "$titles" > "$evidence/window-titles.txt"
  if printf '%s\n' "$titles" | grep -q "Adept UI Studio"; then
    echo "STUDIO_WINDOW: PASS Adept UI Studio" | tee -a "$evidence/result.txt"
  else
    echo "STUDIO_WINDOW: PROCESS_STARTED title not confirmed" | tee -a "$evidence/result.txt"
  fi
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
  if pgrep -f "Adept UI.app/Contents/MacOS/Adept UI.bin" >/dev/null 2>&1; then
    echo "RESTART: PASS" | tee -a "$evidence/result.txt"
  else
    echo "RESTART: FAIL" | tee -a "$evidence/result.txt"
  fi
  pkill -f "Adept UI.app/Contents/MacOS" || true
fi

ADEPT_UNINSTALL=1 bash -c 'curl -fsSL "https://adeptui.org/install.sh" | bash'
test ! -d "$app"
test "$(cat "$keep")" = "disposable-project"
echo "UNINSTALL_PRESERVES_USER_DATA: PASS" | tee -a "$evidence/result.txt"
curl -fsSL "https://adeptui.org/install.sh" | ADEPT_ASSUME_YES=1 ADEPT_NO_LAUNCH=1 bash
test -x "$launcher"
test "$(cat "$keep")" = "disposable-project"
echo "REINSTALL: PASS" | tee -a "$evidence/result.txt"
cat "$evidence/result.txt"

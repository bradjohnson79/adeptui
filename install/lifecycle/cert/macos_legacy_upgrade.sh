#!/bin/bash
set -euo pipefail

evidence="${ADEPT_EVIDENCE:-$RUNNER_TEMP/adept-cert-upgrade}"
mkdir -p "$evidence"
test "$(uname -m)" = "arm64"

spec() {
  python3 - "$1" <<'PY'
import json, sys
from pathlib import Path
version = sys.argv[1]
row = json.loads(Path("install/lifecycle/cert/legacy-releases.json").read_text(encoding="utf-8"))[version]["dmg"]
print(row["url"])
print(row["sha256"])
print(row["bytes"])
print(row["fileName"])
PY
}

attempt() {
  local version="$1"
  rm -rf "$HOME/Applications/Adept UI.app"
  local url sha bytes name
  url="$(spec "$version" | sed -n '1p')"
  sha="$(spec "$version" | sed -n '2p')"
  bytes="$(spec "$version" | sed -n '3p')"
  name="$(spec "$version" | sed -n '4p')"
  local dest="/tmp/$name"
  curl -fL "$url" -o "$dest"
  echo "$sha  $dest" | shasum -a 256 -c -
  test "$(wc -c < "$dest" | tr -d ' ')" = "$bytes"
  local mount
  mount="$(mktemp -d)"
  hdiutil attach -readonly -nobrowse -mountpoint "$mount" "$dest"
  local app_src
  app_src="$(find "$mount" -maxdepth 2 -name 'Adept UI.app' -print -quit)"
  test -n "$app_src"
  ditto "$app_src" "$HOME/Applications/Adept UI.app"
  hdiutil detach "$mount" || true
  local keep="$HOME/Library/Application Support/Adept UI/upgrade-keep.txt"
  mkdir -p "$HOME/Library/Application Support/Adept UI"
  echo "keep-$version" > "$keep"
  local launcher="$HOME/Applications/Adept UI.app/Contents/MacOS/Adept UI"
  local log="$evidence/launcher-$version.log"
  "$launcher" >"$log" 2>&1 &
  local pid=$!
  local i
  for i in $(seq 1 30); do
    if ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    sleep 2
  done
  kill "$pid" 2>/dev/null || true
  pkill -f "Adept UI.app/Contents/MacOS" 2>/dev/null || true
  local bundle
  bundle="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$HOME/Applications/Adept UI.app/Contents/Info.plist")"
  if [ "$(cat "$keep")" != "keep-$version" ]; then
    echo "USER_DATA: FAIL" | tee -a "$evidence/result.txt"
    exit 1
  fi
  if [ "$bundle" = "1.1.5" ]; then
    echo "AUTOMATIC_UPGRADE_${version}: GO" | tee -a "$evidence/result.txt"
  else
    echo "AUTOMATIC_UPGRADE_${version}: NO-GO installed version stayed ${bundle}. The published launcher did not replace itself with 1.1.5." | tee -a "$evidence/result.txt"
  fi
}

attempt "1.1.3"
attempt "1.1.4"
curl -fsSL "https://adeptui.org/install.sh" | ADEPT_ASSUME_YES=1 ADEPT_NO_LAUNCH=1 bash
bundle="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$HOME/Applications/Adept UI.app/Contents/Info.plist")"
test "$bundle" = "1.1.5"
test "$(cat "$HOME/Library/Application Support/Adept UI/upgrade-keep.txt")" = "keep-1.1.4"
echo "MIGRATION_REINSTALL: PASS" | tee -a "$evidence/result.txt"
cat "$evidence/result.txt"
grep -q "AUTOMATIC_UPGRADE_1.1.3: GO" "$evidence/result.txt"
grep -q "AUTOMATIC_UPGRADE_1.1.4: GO" "$evidence/result.txt"

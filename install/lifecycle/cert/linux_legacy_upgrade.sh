#!/bin/bash
# Attempt a launcher upgrade from a published older package, then the public installer migration.
# An automatic NO-GO is reported and fails this script. It is not relabeled as a fresh install.
set -euo pipefail

evidence="${ADEPT_EVIDENCE:-/tmp/adept-cert-upgrade}"
mkdir -p "$evidence"
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
fi
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi
if command -v dnf >/dev/null 2>&1; then
  $SUDO dnf install -y curl ca-certificates openssl python3 findutils procps-ng
  KIND="rpm"
else
  $SUDO apt-get update
  $SUDO apt-get install -y curl ca-certificates openssl python3 findutils procps
  KIND="deb"
fi

spec() {
  python3 - "$1" "$KIND" <<'PY'
import json, sys
from pathlib import Path
version, kind = sys.argv[1], sys.argv[2]
row = json.loads(Path("install/lifecycle/cert/legacy-releases.json").read_text(encoding="utf-8"))[version][kind]
print(row["url"])
print(row["sha256"])
print(row["bytes"])
print(row["fileName"])
PY
}

remove_pkg() {
  if [ "$KIND" = "deb" ]; then
    $SUDO apt-get remove -y adept-ui || true
  else
    $SUDO dnf remove -y adept-ui || true
  fi
}

attempt() {
  local version="$1"
  remove_pkg
  mapfile -t row < <(spec "$version")
  local url="${row[0]}" sha="${row[1]}" bytes="${row[2]}" name="${row[3]}"
  local dest="/tmp/$name"
  curl -fL "$url" -o "$dest"
  echo "$sha  $dest" | sha256sum -c -
  test "$(wc -c < "$dest" | tr -d ' ')" = "$bytes"
  if [ "$KIND" = "deb" ]; then
    $SUDO apt-get install -y "$dest" || $SUDO dpkg -i "$dest" || $SUDO apt-get install -f -y
  else
    $SUDO dnf install -y "$dest" || $SUDO rpm -Uvh "$dest"
  fi
  local listing launcher
  if [ "$KIND" = "deb" ]; then listing="$(dpkg -L adept-ui)"; else listing="$(rpm -ql adept-ui)"; fi
  launcher="$(printf '%s\n' "$listing" | grep '/Adept UI$' | tail -n 1)"
  local keep="$HOME/.config/Adept UI/upgrade-keep.txt"
  mkdir -p "$HOME/.config/Adept UI"
  echo "keep-$version" > "$keep"
  local log="$evidence/launcher-$version.log"
  if [ -x "$launcher" ]; then
    "$launcher" >"$log" 2>&1 &
    local pid=$!
    local i
    for i in $(seq 1 45); do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 2
    done
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  else
    echo "launcher missing" >"$log"
  fi
  pkill -f "/opt/Adept UI" 2>/dev/null || true
  local version_file
  version_file="$(dirname "$launcher")/resources/version.json"
  if [ "$(cat "$keep")" != "keep-$version" ]; then
    echo "USER_DATA: FAIL" | tee -a "$evidence/result.txt"
    exit 1
  fi
  if grep -q '"version": "1.1.5"' "$version_file"; then
    echo "AUTOMATIC_UPGRADE_${version}: GO" | tee -a "$evidence/result.txt"
  else
    echo "AUTOMATIC_UPGRADE_${version}: NO-GO installed version stayed ${version}. The published launcher did not replace itself with 1.1.5." | tee -a "$evidence/result.txt"
  fi
}

attempt "1.1.3"
attempt "1.1.4"
curl -fsSL "https://adeptui.org/install.sh" | ADEPT_ASSUME_YES=1 ADEPT_NO_LAUNCH=1 bash
launcher="$( (command -v dpkg >/dev/null && dpkg -L adept-ui || rpm -ql adept-ui) | grep '/Adept UI$' | tail -n 1)"
grep -q '"version": "1.1.5"' "$(dirname "$launcher")/resources/version.json"
test "$(cat "$HOME/.config/Adept UI/upgrade-keep.txt")" = "keep-1.1.4"
echo "MIGRATION_REINSTALL: PASS" | tee -a "$evidence/result.txt"
cat "$evidence/result.txt"
grep -q "AUTOMATIC_UPGRADE_1.1.3: GO" "$evidence/result.txt"
grep -q "AUTOMATIC_UPGRADE_1.1.4: GO" "$evidence/result.txt"

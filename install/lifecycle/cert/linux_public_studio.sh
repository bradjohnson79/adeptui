#!/bin/bash
# Public Linux install, launcher-first startup, and a virtual Studio window.
# Xvfb is a virtual display. This script does not claim a physical desktop.
set -euo pipefail

evidence="${ADEPT_EVIDENCE:-/tmp/adept-cert}"
mkdir -p "$evidence"
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
fi
{
  echo "PRETTY_NAME=${PRETTY_NAME:-unknown}"
  echo "ID=${ID:-unknown}"
  echo "ARCH=$(uname -m)"
  echo "KERNEL=$(uname -r)"
  echo "COMMIT=${GITHUB_SHA:-local}"
} | tee "$evidence/os.txt"

if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
else
  SUDO="sudo"
fi

if command -v dnf >/dev/null 2>&1; then
  $SUDO dnf install -y --setopt=install_weak_deps=False \
    curl ca-certificates openssl python3 findutils grep procps-ng \
    xorg-x11-server-Xvfb gtk3 libnotify nss libXScrnSaver libXtst at-spi2-core \
    mesa-libgbm alsa-lib libdrm libxkbcommon pango cairo \
    libXcomposite libXdamage libXrandr libXfixes cups-libs xwininfo ImageMagick
  FAMILY="fedora"
  echo "ENVIRONMENT: Fedora container or VM with Xvfb. Not a physical desktop." | tee "$evidence/environment.txt"
else
  $SUDO apt-get update
  $SUDO apt-get install -y --no-install-recommends \
    curl ca-certificates openssl python3 findutils grep procps \
    libgtk-3-0 libnotify4 libnss3 libxss1 libxtst6 libatspi2.0-0 \
    libgbm1 libasound2 xvfb x11-utils imagemagick
  FAMILY="debian"
  echo "ENVIRONMENT: Ubuntu runner with Xvfb. Virtual display, not physical hardware." | tee "$evidence/environment.txt"
fi

export ADEPT_ASSUME_YES=1
export ADEPT_NO_LAUNCH=1
curl -fsSL "https://adeptui.org/install.sh" | bash
echo "CATALOG_INSTALL: PASS" | tee -a "$evidence/result.txt"

if [ "$FAMILY" = "debian" ]; then
  listing="$(dpkg -L adept-ui)"
else
  listing="$(rpm -ql adept-ui)"
fi
printf '%s\n' "$listing" > "$evidence/package-files.txt"
launcher="$(printf '%s\n' "$listing" | grep '/Adept UI$' | while read -r path; do
  if [ -x "$path" ]; then
    printf '%s\n' "$path"
  fi
done | tail -n 1)"
test -n "$launcher"
test -x "$launcher"
test -x "${launcher}.bin"
echo "LAUNCHER: $launcher" | tee -a "$evidence/result.txt"
echo "ELECTRON: ${launcher}.bin" | tee -a "$evidence/result.txt"

desktop="$(printf '%s\n' "$listing" | grep '\.desktop$' | head -n 1 || true)"
test -n "$desktop"
cp "$desktop" "$evidence/desktop-entry.txt"
grep -q '^Name=Adept UI$' "$desktop"
grep -q '^Terminal=false$' "$desktop"
exec_line="$(grep '^Exec=' "$desktop" | head -n 1 | sed 's/^Exec=//')"
if printf '%s\n' "$exec_line" | grep -q '^"'; then
  exec_path="$(printf '%s\n' "$exec_line" | sed -E 's/^"([^"]+)".*/\1/')"
else
  exec_path="$(printf '%s\n' "$exec_line" | awk '{print $1}')"
fi
resolved="$(readlink -f "$exec_path" 2>/dev/null || true)"
echo "DESKTOP_EXEC: $exec_line" | tee -a "$evidence/result.txt"
echo "DESKTOP_RESOLVED: ${resolved:-$exec_path}" | tee -a "$evidence/result.txt"
if [ "$resolved" != "$launcher" ] && [ "$exec_path" != "$launcher" ]; then
  echo "DESKTOP_ENTRY: FAIL" | tee -a "$evidence/result.txt"
  exit 1
fi
echo "DESKTOP_ENTRY: PASS" | tee -a "$evidence/result.txt"

version_file="$(dirname "$launcher")/resources/version.json"
test -f "$version_file"
cp "$version_file" "$evidence/version.json"
grep -q '"version": "1.1.6"' "$version_file"
echo "INSTALLED_VERSION: 1.1.6" | tee -a "$evidence/result.txt"

keep="$HOME/.config/Adept UI/project-keep.txt"
mkdir -p "$HOME/.config/Adept UI"
echo "disposable-project" > "$keep"

export DISPLAY="${DISPLAY:-:99}"
export ELECTRON_DISABLE_SANDBOX=1
export LIBGL_ALWAYS_SOFTWARE=1
# The launcher appends this value as one Electron argument.
export ADEPT_ELECTRON_ARGS="${ADEPT_ELECTRON_ARGS:---no-sandbox}"
echo "CI_ELECTRON_ARGS: ${ADEPT_ELECTRON_ARGS} (one argument; sandbox disabled for the CI session)" | tee -a "$evidence/result.txt"
if ! pgrep -f "Xvfb $DISPLAY" >/dev/null 2>&1; then
  Xvfb "$DISPLAY" -screen 0 1440x900x24 >"$evidence/xvfb.log" 2>&1 &
  sleep 1
fi

stop_app() {
  if [ -n "${app_pid:-}" ] && kill -0 "$app_pid" 2>/dev/null; then
    kill "$app_pid" 2>/dev/null || true
    wait "$app_pid" 2>/dev/null || true
  fi
  pkill -f "$launcher" 2>/dev/null || true
  pkill -f "${launcher}.bin" 2>/dev/null || true
  sleep 1
}

launch_and_prove() {
  local label="$1"
  : >"$evidence/launcher-$label.log"
  "$launcher" >"$evidence/launcher-$label.log" 2>&1 &
  app_pid=$!
  echo "LAUNCHER_PID_$label: $app_pid" | tee -a "$evidence/result.txt"
  local electron_pid=""
  local parent=""
  local i
  for i in $(seq 1 400); do
    electron_pid="$(pgrep -f "${launcher}.bin" | head -n 1 || true)"
    if [ -n "$electron_pid" ]; then
      parent="$(ps -o ppid= -p "$electron_pid" | tr -d ' ')"
      if [ "$parent" = "$app_pid" ]; then
        echo "ELECTRON_PID_$label: $electron_pid PARENT: $parent" | tee -a "$evidence/result.txt"
        echo "LAUNCHER_PARENT_$label: OBSERVED" | tee -a "$evidence/result.txt"
        break
      fi
    fi
    sleep 0.05
  done
  if [ -z "$electron_pid" ]; then
    echo "ELECTRON_$label: FAIL" | tee -a "$evidence/result.txt"
    tail -n 80 "$evidence/launcher-$label.log" || true
    exit 1
  fi
  if ! grep -q "LAUNCHER_PARENT_$label: OBSERVED" "$evidence/result.txt"; then
    echo "LAUNCHER_PARENT_$label: NOT_OBSERVED parent=${parent:-none}" | tee -a "$evidence/result.txt"
  fi
  if ! grep -Eq "Adept UI is up to date|Adept UI is starting|Adept UI is now" "$evidence/launcher-$label.log"; then
    if ! grep -q "LAUNCHER_PARENT_$label: OBSERVED" "$evidence/result.txt"; then
      echo "LAUNCHER_FIRST_$label: FAIL" | tee -a "$evidence/result.txt"
      exit 1
    fi
  fi
  echo "LAUNCHER_FIRST_$label: PASS" | tee -a "$evidence/result.txt"
  local window_ok=0
  for i in $(seq 1 45); do
    if xwininfo -root -tree 2>/dev/null | tee "$evidence/xwin-$label.txt" | grep -q '"Adept UI Studio"'; then
      window_ok=1
      break
    fi
    sleep 2
  done
  if [ "$window_ok" != "1" ]; then
    echo "STUDIO_WINDOW_$label: FAIL" | tee -a "$evidence/result.txt"
    tail -n 80 "$evidence/launcher-$label.log" || true
    exit 1
  fi
  local windows
  windows="$(grep -c 'Adept UI' "$evidence/xwin-$label.txt" || true)"
  echo "WINDOW_LINES_$label: $windows" | tee -a "$evidence/result.txt"
  echo "STUDIO_WINDOW_$label: PASS" | tee -a "$evidence/result.txt"
  sleep 4
  if command -v import >/dev/null 2>&1; then
    import -window root "$evidence/studio-$label.png" || true
  elif command -v magick >/dev/null 2>&1; then
    magick import -window root "$evidence/studio-$label.png" || true
  fi
}

launch_and_prove first
python3 - <<'PY' | tee -a "$evidence/result.txt"
import json
from pathlib import Path
root = Path.home() / ".adept-ui"
status_path = root / "startup-update.json"
registry_path = root / "registry.json"
if not status_path.is_file():
    raise SystemExit("UPDATE_CHECK: FAIL no startup record")
status = json.loads(status_path.read_text(encoding="utf-8"))
code = status.get("code")
registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {}
version = registry.get("installedVersion")
print(f"UPDATE_CHECK: {code}")
print(f"REGISTRY_VERSION: {version}")
if code not in {"NO_UPDATE", "UPDATE_SERVICE_UNAVAILABLE", "DEFERRED"}:
    raise SystemExit(f"UPDATE_CHECK: FAIL {code}")
if version not in {None, "", "1.1.6"}:
    raise SystemExit(f"REGISTRY_VERSION: FAIL {version}")
PY
stop_app
python3 - <<'PY'
import json
from pathlib import Path
root = Path.home() / ".adept-ui"
registry_path = root / "registry.json"
registry = json.loads(registry_path.read_text(encoding="utf-8"))
registry["installedVersion"] = "1.1.5"
registry_path.write_text(json.dumps(registry), encoding="utf-8")
status = root / "startup-update.json"
if status.exists():
    status.unlink()
PY
"$launcher" >"$evidence/launcher-update.log" 2>&1 &
app_pid=$!
update_ok=0
for _ in $(seq 1 240); do
  if [ -f "$HOME/.adept-ui/startup-update.json" ]; then
    code="$(python3 -c 'import json; print(json.load(open("'"$HOME/.adept-ui/startup-update.json"'"))["code"])')"
    if [ "$code" = "UPDATED" ]; then
      update_ok=1
      break
    fi
    echo "AUTOMATIC_UPDATE: FAIL $code" | tee -a "$evidence/result.txt"
    exit 1
  fi
  sleep 5
done
if [ "$update_ok" != "1" ]; then
  echo "AUTOMATIC_UPDATE: FAIL timed out" | tee -a "$evidence/result.txt"
  tail -n 40 "$evidence/launcher-update.log" || true
  exit 1
fi
python3 - <<'PY' | tee -a "$evidence/result.txt"
import json
from pathlib import Path
registry = json.loads((Path.home() / ".adept-ui" / "registry.json").read_text(encoding="utf-8"))
keep = Path.home() / ".config" / "Adept UI" / "project-keep.txt"
if registry.get("installedVersion") != "1.1.6" or keep.read_text(encoding="utf-8").strip() != "disposable-project":
    print("AUTOMATIC_UPDATE: FAIL registry or user data")
    raise SystemExit(1)
print("AUTOMATIC_UPDATE: PASS")
PY
grep -q '"Adept UI Studio"' "$evidence/xwin-update.txt" 2>/dev/null || true
window_ok=0
for _ in $(seq 1 45); do
  if xwininfo -root -tree 2>/dev/null | grep -q '"Adept UI Studio"'; then
    window_ok=1
    break
  fi
  sleep 2
done
if [ "$window_ok" != "1" ]; then
  echo "STUDIO_WINDOW_updated: FAIL" | tee -a "$evidence/result.txt"
  exit 1
fi
echo "STUDIO_WINDOW_updated: PASS" | tee -a "$evidence/result.txt"
stop_app
if pgrep -f "${launcher}.bin" >/dev/null 2>&1; then
  echo "SHUTDOWN: FAIL" | tee -a "$evidence/result.txt"
  exit 1
fi
echo "SHUTDOWN: PASS" | tee -a "$evidence/result.txt"
launch_and_prove restart
stop_app
echo "RESTART: PASS" | tee -a "$evidence/result.txt"

if [ "$FAMILY" = "debian" ]; then
  $SUDO apt-get remove -y adept-ui
else
  $SUDO dnf remove -y adept-ui
fi
test ! -e "$launcher"
test "$(cat "$keep")" = "disposable-project"
echo "UNINSTALL_PRESERVES_USER_DATA: PASS" | tee -a "$evidence/result.txt"
curl -fsSL "https://adeptui.org/install.sh" | ADEPT_ASSUME_YES=1 ADEPT_NO_LAUNCH=1 bash
test -x "$launcher"
test -x "${launcher}.bin"
test "$(cat "$keep")" = "disposable-project"
grep -q '"version": "1.1.6"' "$version_file"
echo "REINSTALL: PASS" | tee -a "$evidence/result.txt"
echo "DISPLAY: VIRTUAL_XVFB" | tee -a "$evidence/result.txt"

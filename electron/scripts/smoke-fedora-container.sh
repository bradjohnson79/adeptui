#!/bin/bash
# Install and launch the Adept UI RPM inside Fedora. This does not touch a host ComfyUI.
set -euo pipefail

dnf install -y \
  python3 \
  nodejs \
  xorg-x11-server-Xvfb \
  gtk3 libnotify nss libXScrnSaver libXtst at-spi2-core \
  mesa-libgbm alsa-lib libdrm libxkbcommon pango cairo \
  libXcomposite libXdamage libXrandr libXfixes cups-libs \
  procps-ng

rpmfile="$(ls /packages/Adept.UI-*-linux-x64.rpm | head -n 1)"
test -n "$rpmfile"
dnf install -y "$rpmfile"

bin="$(rpm -ql adept-ui | grep -E '/Adept UI$' | head -n 1)"
test -n "$bin"
test -f "$bin"
rpm -ql adept-ui | grep -q '\.desktop$'

renderer="$(dirname "$bin")/resources/renderer"
if ! grep -R -q "https://www.comfy.org/download" "$renderer"; then
  echo "FEDORA RENDERER MISSING COMFY DOWNLOAD"
  exit 1
fi

profile="/tmp/adept-fedora-profile"
rm -rf "$profile"
mkdir -p "$profile"
echo keep > "$profile/keep.txt"

export ELECTRON_DISABLE_SANDBOX=1
Xvfb :99 -screen 0 1440x900x24 >/tmp/xvfb.log 2>&1 &
export DISPLAY=:99
"$bin" --no-sandbox --disable-gpu --user-data-dir="$profile" >/tmp/adept-fedora.log 2>&1 &
app_pid=$!

healthy=0
for _ in $(seq 1 90); do
  if curl -sf "http://127.0.0.1:8760/api/healthz" >/tmp/adept-health.json; then
    healthy=1
    break
  fi
  if ! kill -0 "$app_pid" 2>/dev/null; then
    echo "FEDORA APP EXITED"
    tail -n 80 /tmp/adept-fedora.log || true
    exit 1
  fi
  sleep 2
done
if [ "$healthy" != "1" ]; then
  echo "FEDORA STUDIO API UNREACHABLE"
  tail -n 80 /tmp/adept-fedora.log || true
  exit 1
fi

node /scripts/setup-profile-smoke.mjs --base "http://127.0.0.1:8760" --temp "$profile"
python3 - <<'PY'
import json
from pathlib import Path
status = json.loads(Path("/tmp/adept-fedora-profile/desktop-status.json").read_text(encoding="utf-8"))
services = status.get("backgroundServices") or {}
if services.get("healthy") is not True:
    raise SystemExit(f"FEDORA BACKGROUND SERVICES {services}")
print("FEDORA BACKGROUND SERVICES = HEALTHY")
PY

boot="$(curl -sf --max-time 120 "http://127.0.0.1:8760/api/boot/certification" || true)"
printf '%s\n' "$boot" > /tmp/adept-boot.json
python3 - <<'PY'
import json
from pathlib import Path
raw = Path("/tmp/adept-boot.json").read_text(encoding="utf-8")
body = json.loads(raw)
failed = [row for row in body.get("checks") or [] if row.get("required") and row.get("result") != "PASS"]
if body.get("verdict") != "GO" or failed:
    raise SystemExit(f"FEDORA BOOT {body.get('verdict')} {failed}")
print("FEDORA BOOT = GO")
PY

kill "$app_pid" || true
sleep 2
pkill -f "adept-fedora-profile" || true
test -f "$profile/keep.txt"
dnf remove -y adept-ui
test ! -e "$bin"
test -f "$profile/keep.txt"
echo "FEDORA RPM LAUNCH = PASS"

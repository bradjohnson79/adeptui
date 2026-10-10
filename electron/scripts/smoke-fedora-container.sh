#!/bin/bash
# Install and launch the Adept UI RPM inside Fedora. This does not touch a host ComfyUI.
set -euo pipefail

dnf install -y --setopt=install_weak_deps=False \
  python3 \
  nodejs \
  xorg-x11-server-Xvfb \
  gtk3 libnotify nss libXScrnSaver libXtst at-spi2-core \
  mesa-libgbm alsa-lib libdrm libxkbcommon pango cairo \
  libXcomposite libXdamage libXrandr libXfixes cups-libs \
  procps-ng iproute xwininfo

echo "PACKAGE TREE"
find /packages -maxdepth 4 -type f -printf '%p\n' | head -n 40
rpmfile="$(find /packages -type f -name 'Adept.UI-*-linux-x64.rpm' -print -quit)"
test -n "$rpmfile"
echo "RPM $rpmfile"
dnf install -y "$rpmfile"

bin="$(rpm -ql adept-ui | grep -E '/Adept UI$' | head -n 1)"
test -n "$bin"
test -f "$bin"
rpm -ql adept-ui | grep -q '\.desktop$'

ADEPT_CONTROL_CLIENT="$(dirname "$bin")/resources/studio-api/runtime_supervisor/control_client.py" python3 - <<'PY'
import os
from pathlib import Path
installed = Path(os.environ["ADEPT_CONTROL_CLIENT"])
text = installed.read_text(encoding="utf-8")
if "def authenticated_adept_status" not in text:
    raise SystemExit(f"FEDORA RPM MISSING AUTHENTICATED CONTROL CHECK {installed}")
print("FEDORA PACKAGED CONTROL CLIENT = PRESENT")
PY

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

stop_app() {
  if [ -n "${app_pid:-}" ] && kill -0 "$app_pid" 2>/dev/null; then
    kill "$app_pid" || true
    wait "$app_pid" 2>/dev/null || true
  fi
  app_pid=""
  sleep 2
}

wait_health() {
  local label="$1"
  local healthy=0
  for _ in $(seq 1 90); do
    if curl -sf "http://127.0.0.1:8760/api/healthz" >/tmp/adept-health.json; then
      healthy=1
      break
    fi
    if ! kill -0 "$app_pid" 2>/dev/null; then
      echo "FEDORA APP EXITED $label"
      tail -n 80 /tmp/adept-fedora.log || true
      exit 1
    fi
    sleep 2
  done
  if [ "$healthy" != "1" ]; then
    echo "FEDORA STUDIO API UNREACHABLE $label"
    tail -n 80 /tmp/adept-fedora.log || true
    exit 1
  fi
}

launch_app() {
  "$bin" --no-sandbox --disable-gpu --user-data-dir="$profile" >/tmp/adept-fedora.log 2>&1 &
  app_pid=$!
}

launch_app
wait_health "first-launch"

python3 - <<'PY'
import json, urllib.request
from pathlib import Path
status = json.load(urllib.request.urlopen("http://127.0.0.1:8760/api/runtime-manager/status", timeout=60))
adept = status.get("adeptRuntime") or {}
ollama = status.get("ollama") or {}
if adept.get("controlPlaneReachable") is not True:
    raise SystemExit(f"FEDORA CONTROL PLANE {adept}")
if adept.get("comfyState") in {"ready", "busy"}:
    raise SystemExit(f"FEDORA UNEXPECTED COMFY {adept.get('comfyState')}")
if ollama.get("modelReady") is True:
    raise SystemExit(f"FEDORA OLLAMA MODEL CLAIMED READY {ollama}")
Path("/tmp/adept-runtime-status.json").write_text(json.dumps(status), encoding="utf-8")
print("FEDORA CONTROL PLANE = AUTHENTICATED")
print("FEDORA CREATOR ENGINE = OPTIONAL WHILE COMFY ABSENT")
print("FEDORA OLLAMA = NOT READY")
PY

ss -ltnpH 'sport = :8760' | tee /tmp/ss-8760.txt
ss -ltnpH 'sport = :8759' | tee /tmp/ss-8759.txt
grep -q 'pid=' /tmp/ss-8760.txt
grep -q 'pid=' /tmp/ss-8759.txt
echo "FEDORA SS LISTENER = PASS"

window_ok=0
for _ in $(seq 1 15); do
  if xwininfo -root -tree 2>/dev/null | tee /tmp/xwin.txt | grep -q "Adept UI"; then
    window_ok=1
    break
  fi
  sleep 1
done
if [ "$window_ok" != "1" ]; then
  echo "FEDORA WINDOW TITLE MISSING"
  cat /tmp/xwin.txt || true
  exit 1
fi
echo "FEDORA WINDOW = Adept UI"

curl -sf "http://127.0.0.1:8760/api/setup/comfy/prerequisite" >/tmp/adept-prerequisite.json
python3 - <<'PY'
import json
from pathlib import Path
body = json.loads(Path("/tmp/adept-prerequisite.json").read_text(encoding="utf-8"))
if body.get("downloadUrl") != "https://www.comfy.org/download":
    raise SystemExit(f"FEDORA SETUP PREREQUISITE {body}")
if body.get("healthy") is True:
    raise SystemExit("FEDORA COMFY REPORTED HEALTHY WHILE ABSENT")
print("FEDORA SETUP WIZARD = REACHABLE")
PY

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

supervisor_pid="$(sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' /tmp/ss-8759.txt | head -n 1)"
supervisor_cmd="$(ps -p "$supervisor_pid" -o args=)"
printf '%s\n' "$supervisor_cmd" | grep -q runtime_supervisor
kill "$supervisor_pid"
sleep 2
python3 - <<'PY'
import json, urllib.request
try:
    status = json.load(urllib.request.urlopen("http://127.0.0.1:8760/api/runtime-manager/status", timeout=20))
except Exception as exc:
    print(f"FEDORA MANAGER EXIT = API UNREACHABLE {exc}")
    raise SystemExit(0)
adept = status.get("adeptRuntime") or {}
if adept.get("controlPlaneReachable") is True:
    raise SystemExit(f"FEDORA DEAD MANAGER STILL TRUSTED {adept}")
print("FEDORA MANAGER EXIT = NOT TRUSTED")
PY

stop_app
launch_app
wait_health "relaunch"
echo "FEDORA RELAUNCH = PASS"
stop_app

python3 - <<'PY' >/tmp/adept-foreign-8759.log 2>&1 &
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, fmt, *args):
        return
ThreadingHTTPServer(("127.0.0.1", 8759), Handler).serve_forever()
PY
foreign_pid=$!
sleep 1
kill -0 "$foreign_pid"
launch_app
wait_health "occupied-8759"
kill -0 "$foreign_pid"
ss -ltnpH 'sport = :8759' | tee /tmp/ss-foreign.txt
grep -q "pid=${foreign_pid}" /tmp/ss-foreign.txt
ss -ltnpH 'sport = :8779' | tee /tmp/ss-8779.txt
grep -q 'pid=' /tmp/ss-8779.txt
python3 - <<'PY'
import json, urllib.request
status = json.load(urllib.request.urlopen("http://127.0.0.1:8760/api/runtime-manager/status", timeout=60))
adept = status.get("adeptRuntime") or {}
if adept.get("controlPlaneReachable") is not True:
    raise SystemExit(f"FEDORA FALLBACK CONTROL PLANE {adept}")
print("FEDORA OCCUPIED 8759 = LEFT ALONE")
PY
stop_app
kill "$foreign_pid" || true
wait "$foreign_pid" 2>/dev/null || true

cat > /tmp/adept-sim-comfy.py <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"system":{"os":"linux"},"devices":[{"name":"simulated"}]}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, fmt, *args):
        return
ThreadingHTTPServer(("127.0.0.1", 8188), Handler).serve_forever()
PY
python3 /tmp/adept-sim-comfy.py >/tmp/adept-sim-comfy.log 2>&1 &
sim_pid=$!
sim_ready=0
for _ in $(seq 1 20); do
  if curl -sf "http://127.0.0.1:8188/system_stats" >/tmp/adept-sim-comfy-body.json; then
    sim_ready=1
    break
  fi
  sleep 0.25
done
if [ "$sim_ready" != "1" ]; then
  echo "FEDORA SIMULATED COMFY DID NOT BIND"
  cat /tmp/adept-sim-comfy.log || true
  exit 1
fi
launch_app
wait_health "simulated-comfy"
curl -sf "http://127.0.0.1:8188/system_stats" >/tmp/adept-sim-still.json || echo "FEDORA SIMULATED COMFY DIED AFTER LAUNCH"
curl -sf "http://127.0.0.1:8760/api/setup/comfy/prerequisite" >/tmp/adept-sim-prerequisite.json
python3 - <<'PY'
import json
from pathlib import Path
body = json.loads(Path("/tmp/adept-sim-prerequisite.json").read_text(encoding="utf-8"))
if body.get("healthy") is not True:
    raise SystemExit(f"FEDORA SIMULATED COMFY NOT SEEN {body}")
print("FEDORA SIMULATED COMFY = DETECTED")
PY
boot="$(curl -sf --max-time 120 "http://127.0.0.1:8760/api/boot/certification" || true)"
printf '%s\n' "$boot" > /tmp/adept-boot-sim.json
python3 - <<'PY'
import json
from pathlib import Path
body = json.loads(Path("/tmp/adept-boot-sim.json").read_text(encoding="utf-8"))
failed = [row for row in body.get("checks") or [] if row.get("required") and row.get("result") != "PASS"]
if body.get("verdict") != "GO" or failed:
    raise SystemExit(f"FEDORA SIMULATED COMFY BOOT {body.get('verdict')} {failed}")
print("FEDORA SIMULATED COMFY BOOT = GO")
PY
stop_app
kill "$sim_pid" || true
wait "$sim_pid" 2>/dev/null || true

dnf reinstall -y "$rpmfile"
test -f "$bin"
launch_app
wait_health "reinstall"
echo "FEDORA REINSTALL = PASS"
stop_app
test -f "$profile/keep.txt"
dnf remove -y adept-ui
test ! -e "$bin"
test -f "$profile/keep.txt"
echo "FEDORA RPM LAUNCH = PASS"

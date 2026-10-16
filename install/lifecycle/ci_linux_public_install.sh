#!/bin/sh
# Public Linux install against the live catalog. Installation is verified.
# Graphical application startup is not claimed from this headless run.
set -eu

if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
fi
case "${ID:-}${ID_LIKE:-}" in
  *fedora*|*rhel*|*centos*)
    dnf install -y sudo curl openssl python3 findutils grep
    ;;
esac

curl -fsSL "https://adeptui.org/install.sh" | ADEPT_ASSUME_YES=1 ADEPT_NO_LAUNCH=1 bash

launcher="$HOME/.adept-ui/bin/Adept UI"
electron="$HOME/.adept-ui/app/Adept UI.bin"
test -x "$launcher"
test -x "$electron"
echo "INSTALLATION: PASS"
echo "LAUNCHER: $launcher"
echo "ELECTRON: $electron"
echo "GRAPHICAL_STARTUP: NOT_VERIFIED"

keep="$HOME/.config/Adept UI/keep.txt"
mkdir -p "$HOME/.config/Adept UI"
echo keep > "$keep"
curl -fsSL "https://adeptui.org/install.sh" | ADEPT_UNINSTALL=1 bash
test ! -e "$launcher"
test "$(cat "$keep")" = "keep"
curl -fsSL "https://adeptui.org/install.sh" | ADEPT_ASSUME_YES=1 ADEPT_NO_LAUNCH=1 bash
test -x "$launcher"
test -x "$electron"
test "$(cat "$keep")" = "keep"
echo "REINSTALL_AND_USER_DATA: PASS"

python3 - <<'PY'
import json
from pathlib import Path
root = Path.home() / ".adept-ui"
root.mkdir(parents=True, exist_ok=True)
(root / "registry.json").write_text(
    json.dumps({"installedVersion": "1.1.4", "channel": "beta", "health": "ok", "updateFailures": {}}),
    encoding="utf-8",
)
status = root / "startup-update.json"
if status.exists():
    status.unlink()
PY
"$HOME/.adept-ui/bin/Adept UI" >/tmp/adept-update.log 2>&1 &
update_pid="$!"
i=0
while [ "$i" -lt 120 ]; do
  if [ -f "$HOME/.adept-ui/startup-update.json" ]; then
    break
  fi
  sleep 2
  i=$((i + 1))
done
kill "$update_pid" >/dev/null 2>&1 || true
echo "UPDATE_PROGRESS: $(cat "$HOME/.adept-ui/update-progress.json" 2>/dev/null || true)"
echo "LAUNCHER_LOG: $(tail -n 40 /tmp/adept-update.log 2>/dev/null || true)"
echo "LIFECYCLE_LOG: $(tail -n 40 "$HOME/.adept-ui/logs/lifecycle.log" 2>/dev/null || true)"
python3 - <<'PY'
import json
from pathlib import Path
root = Path.home() / ".adept-ui"
status = json.loads((root / "startup-update.json").read_text(encoding="utf-8"))
registry = json.loads((root / "registry.json").read_text(encoding="utf-8"))
if status.get("code") != "UPDATED":
    raise SystemExit(f"UPDATE: FAIL {status}")
if registry.get("installedVersion") != "1.1.5":
    raise SystemExit(f"UPDATE_VERSION: FAIL {registry.get('installedVersion')}")
if not (root / "previous-app").exists():
    raise SystemExit("PREVIOUS_VERSION: FAIL")
print("UPDATE: PASS")
print("PREVIOUS_VERSION_PRESERVED: PASS")
PY

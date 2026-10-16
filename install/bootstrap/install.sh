#!/bin/sh
# Adept UI installer.
# Official catalog: https://adeptui.org/releases/current.json
# Inspect this file before running it. A GitHub branch is not an installation source.
# The macOS build is not notarized. This script does not change Gatekeeper.
set -eu

if [ "${ADEPT_UNINSTALL:-}" = "1" ] || [ "${1:-}" = "uninstall" ]; then
  rm -rf "$HOME/.adept-ui"
  rm -f "$HOME/.local/share/applications/adept-ui.desktop"
  rm -f "$HOME/Desktop/Adept UI.desktop"
  rm -f "$HOME/Desktop/Adept UI"
  echo "Adept UI was removed. Personal projects were kept."
  exit 0
fi

os_name="$(uname -s)"
machine="$(uname -m)"
platform=""
arch=""
kind=""
family=""

case "$os_name" in
  Linux) platform="linux" ;;
  Darwin) platform="darwin" ;;
  *)
    echo "Adept UI does not have a certified build for $os_name."
    exit 3
    ;;
esac

if [ "$platform" = "darwin" ]; then
  case "$machine" in
    arm64) arch="arm64"; kind="zip" ;;
    x86_64)
      echo "This Mac is Intel. Adept UI 1.1.1 is an Apple Silicon build. An Intel installer is not published."
      exit 3
      ;;
    *)
      echo "Adept UI does not have a certified build for $machine."
      exit 3
      ;;
  esac
  macos_version="$(sw_vers -productVersion)"
  macos_major="${macos_version%%.*}"
  if [ "$macos_major" -lt 11 ]; then
    echo "Adept UI requires macOS 11 or later. This Mac is running $macos_version."
    exit 3
  fi
  echo "Detected macOS $macos_version $arch."
else
  case "$machine" in
    x86_64|amd64) arch="x64" ;;
    *)
      echo "Adept UI does not have a certified build for $machine."
      exit 3
      ;;
  esac
  if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${ID:-}${ID_LIKE:-}" in
      *fedora*|*rhel*|*centos*) family="fedora"; kind="zip" ;;
      *debian*|*ubuntu*) family="debian"; kind="zip" ;;
    esac
  fi
  if [ -z "$kind" ]; then
    echo "This Linux distribution is not an approved Adept UI install target."
    echo "Certified systems are Fedora and Ubuntu or Debian."
    exit 3
  fi
  echo "Detected $platform $arch ($family)."
fi

command -v openssl >/dev/null 2>&1 || { echo "OpenSSL is required to verify the Adept UI release."; exit 4; }
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required to read the Adept UI release catalog."; exit 4; }

prompt_yes() {
  if [ "${ADEPT_ASSUME_YES:-}" = "1" ]; then
    return 0
  fi
  if [ ! -r /dev/tty ]; then
    return 0
  fi
  printf '%s' "$1" >/dev/tty
  read -r answer </dev/tty || answer="y"
  case "$answer" in
    ""|y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
if [ -n "${ADEPT_CATALOG_FILE:-}" ] && [ -n "${ADEPT_SIGNATURE_FILE:-}" ]; then
  cp "$ADEPT_CATALOG_FILE" "$workdir/current.json"
  cp "$ADEPT_SIGNATURE_FILE" "$workdir/current.sig"
else
  curl -fsSL "https://adeptui.org/releases/current.json" -o "$workdir/current.json"
  curl -fsSL "https://adeptui.org/releases/current.sig" -o "$workdir/current.sig"
fi
base64 -d "$workdir/current.sig" > "$workdir/current.sig.bin" 2>/dev/null || base64 -D -i "$workdir/current.sig" -o "$workdir/current.sig.bin"
cat > "$workdir/release.pub.pem" <<'PEM'
-----BEGIN PUBLIC KEY-----
MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAtuu/mw3fdps5KL/zeDHs
rUFB++x17OEhlqThBknqp4Epl0Z63H/A2vLlEdST/pfoa1dqKbIpNAhdc/R3rAOP
WXRstbgtxU+02Zq/Zm6dDHLZAEvmzwKgnzuvPc83kee4uIxqJMzzcYPoEK/cKMtX
Dak7n3U+D2ij11P2C96EomLdBwX5gXUPZjqHPDG8Y/1Vrzi8cVTGT8tsIhD3r3gY
2z+poRvLbrJuMx1DyKL62cfVS5K9vub3+cpgF5NGiSWSThWg2GWfGJa0zXn+txtO
voUJoDLR0uRW8bAAs7VMSGcdOXuvQt9SCtfLDD8gflMvtVtgxuf1Rgwa8VJK5fS8
xuiM+feZ/tLnhG5zti17BOSlHQsrzwpjbCYNHIrjMaHXszFVVcI9JugjmgWOCFUc
Fx0kj2EpxmBNqBdBipekT1RGh8QUxva7FGN6fnoBk2Jf8EiCED5kIp7/6Fals9Og
4aVyrbOZ31pf+Ziq5fmjDbv7/wMiSHmje/FMcrplukdrAgMBAAE=
-----END PUBLIC KEY-----
PEM
openssl dgst -sha256 -verify "$workdir/release.pub.pem" -signature "$workdir/current.sig.bin" "$workdir/current.json" >/dev/null

python3 - "$workdir/current.json" "$platform" "$arch" "$kind" <<'PY'
import hashlib, json, pathlib, sys, urllib.request
catalog = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
platform, arch, package_kind = sys.argv[2], sys.argv[3], sys.argv[4]
chosen = None
for artifact in catalog.get("artifacts") or []:
    if artifact.get("platform") != platform or artifact.get("arch") != arch or artifact.get("kind") != "zip":
        continue
    chosen = artifact
    break
if not chosen:
    raise SystemExit("No approved build for this system is in the Adept UI release catalog.")
url = str(chosen["url"])
if not url.startswith("https://github.com/bradjohnson79/adeptui/releases/download/v"):
    raise SystemExit("The catalog does not point at an official Adept UI release.")
destination = pathlib.Path(sys.argv[1]).parent / chosen["fileName"]
expected_bytes = int(chosen.get("bytes") or chosen.get("size") or 0)
expected_mb = round(expected_bytes / (1024 * 1024), 1)
print(f"Downloading {chosen['fileName']} ({expected_mb} MB)", file=sys.stderr)
import time
download_start = time.monotonic()
urllib.request.urlretrieve(url, destination)
elapsed = time.monotonic() - download_start
actual_bytes = destination.stat().st_size
actual_mb = round(actual_bytes / (1024 * 1024), 1)
speed = round(actual_bytes / (1024 * 1024) / elapsed, 1) if elapsed > 0 else 0
print(f"Downloaded {actual_mb} MB in {round(elapsed)}s ({speed} MB/s)", file=sys.stderr)
digest = hashlib.sha256(destination.read_bytes()).hexdigest()
if digest.lower() != str(chosen["sha256"]).lower():
    destination.unlink()
    raise SystemExit("The downloaded installer did not match the approved checksum.")
pathlib.Path(sys.argv[1]).with_name("payload-path.txt").write_text(str(destination), encoding="utf-8")
pathlib.Path(sys.argv[1]).with_name("payload-version.txt").write_text(str(chosen.get("version") or ""), encoding="utf-8")
pathlib.Path(sys.argv[1]).with_name("payload-kind.txt").write_text(str(chosen.get("kind") or ""), encoding="utf-8")
revision = chosen.get("revision", catalog.get("revision", 0))
try:
    revision = int(revision)
except (TypeError, ValueError):
    revision = 0
if revision < 0:
    revision = 0
pathlib.Path(sys.argv[1]).with_name("payload-revision.txt").write_text(str(revision), encoding="utf-8")
PY

payload="$(cat "$workdir/payload-path.txt")"
version="$(cat "$workdir/payload-version.txt")"
payload_kind="$(cat "$workdir/payload-kind.txt")"
revision="$(cat "$workdir/payload-revision.txt")"

record_installed_release() {
  python3 - "$root" "$version" "$revision" "$platform" "$arch" <<'PY'
import json, sys
from pathlib import Path
root, version, revision, platform, arch = sys.argv[1:6]
try:
    number = int(revision)
except ValueError:
    number = 0
if number < 0:
    number = 0
path = Path(root) / "registry.json"
data = {}
if path.is_file():
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    except (OSError, json.JSONDecodeError):
        data = {}
data["schema"] = data.get("schema") or 1
data["installedVersion"] = version
data["installedRevision"] = number
data["os"] = platform
data["arch"] = arch
data["location"] = str(Path(root) / "app")
data["method"] = "adept-lifecycle"
data["health"] = "installed"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
PY
}

if [ "$payload_kind" = "zip" ]; then
  root="$HOME/.adept-ui"
  app="$root/app"
  bin="$root/bin"
  previous="$root/previous-app"
  rm -rf "$previous"
  if [ -d "$app" ]; then
    mv "$app" "$previous"
  fi
  mkdir -p "$app" "$bin"
  if ! python3 - "$payload" "$app" <<'PY'
import sys, zipfile
from pathlib import Path
payload, app = Path(sys.argv[1]), Path(sys.argv[2])
with zipfile.ZipFile(payload) as archive:
    for info in archive.infolist():
        name = info.filename
        if not name or name.endswith("/"):
            continue
        destination = (app / name).resolve()
        if app.resolve() not in destination.parents and destination != app.resolve():
            raise SystemExit("The archive tried to write outside the installation folder.")
PY
  then
    rm -rf "$app"
    if [ -d "$previous" ]; then
      mv "$previous" "$app"
    fi
    echo "Installation did not finish."
    exit 5
  fi
  if [ "$platform" = "darwin" ]; then
    # Python's zip extractor writes macOS framework symlinks as plain files.
    # ditto restores the bundle the archive was packed with.
    extract_ok=0
    ditto -x -k "$payload" "$app" && extract_ok=1
  else
    extract_ok=0
    python3 - "$payload" "$app" <<'PY' && extract_ok=1
import sys, zipfile
from pathlib import Path
payload, app = Path(sys.argv[1]), Path(sys.argv[2])
with zipfile.ZipFile(payload) as archive:
    archive.extractall(app)
PY
  fi
  if [ "$extract_ok" != "1" ]; then
    rm -rf "$app"
    if [ -d "$previous" ]; then
      mv "$previous" "$app"
    fi
    echo "Installation did not finish."
    exit 5
  fi
  rm -rf "$previous"
  if [ "$platform" = "darwin" ]; then
    dest="$app/Adept UI.app"
    launcher="$dest/Contents/MacOS/Adept UI"
    chmod 755 "$launcher" "$dest/Contents/MacOS/Adept UI.bin" 2>/dev/null || true
    test -e "$launcher"
    record_installed_release
    if prompt_yes "Create a desktop shortcut? [Y/n] "; then
      if [ -d "$HOME/Desktop" ]; then
        osascript >/dev/null 2>&1 <<APPLESCRIPT || echo "macOS could not create a desktop alias. Adept UI is in $dest"
tell application "Finder"
  make alias file to POSIX file "$dest" at POSIX file "$HOME/Desktop"
end tell
APPLESCRIPT
      fi
    fi
    echo "Adept UI is installed in $dest"
    echo "This macOS build is not notarized."
    echo "If macOS asks before the first launch, Control-click Adept UI and choose Open."
    if [ "${ADEPT_NO_LAUNCH:-}" != "1" ] && prompt_yes "Launch Adept UI after installation? [Y/n] "; then
      open "$dest" || echo "macOS did not open Adept UI. The application is installed in $dest"
    fi
    exit 0
  fi
  cp "$app/Adept UI" "$bin/Adept UI"
  chmod 755 "$bin/Adept UI" "$app/Adept UI.bin"
  launcher="$bin/Adept UI"
  test -x "$launcher"
  test -x "$app/Adept UI.bin"
  record_installed_release
  mkdir -p "$HOME/.local/share/applications"
  entry="$HOME/.local/share/applications/adept-ui.desktop"
  printf '%s\n' "[Desktop Entry]" "Name=Adept UI" "Comment=Adept UI" "Exec=\"$launcher\"" "Terminal=false" "Type=Application" "Categories=AudioVideo;" > "$entry"
  chmod 755 "$entry"
  if prompt_yes "Create a desktop shortcut? [Y/n] "; then
    if [ -d "$HOME/Desktop" ]; then
      cp "$entry" "$HOME/Desktop/Adept UI.desktop"
      chmod 755 "$HOME/Desktop/Adept UI.desktop" || true
    fi
  fi
  echo "Adept UI is installed."
  if [ "${ADEPT_NO_LAUNCH:-}" != "1" ] && prompt_yes "Launch Adept UI after installation? [Y/n] "; then
    "$launcher" >/dev/null 2>&1 || true
  fi
  exit 0
fi

echo "The release catalog does not contain an Adept UI application archive."
exit 3

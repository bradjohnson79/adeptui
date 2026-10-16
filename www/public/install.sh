#!/bin/sh
# Adept UI installer.
# Official catalog: https://adeptui.org/releases/current.json
# Inspect this file before running it. A GitHub branch is not an installation source.
# The macOS build is not notarized. This script does not change Gatekeeper.
set -eu

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
    arm64) arch="arm64"; kind="dmg" ;;
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
      *fedora*|*rhel*|*centos*) family="fedora"; kind="rpm" ;;
      *debian*|*ubuntu*) family="debian"; kind="deb" ;;
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
for want in ("zip", package_kind):
    for artifact in catalog.get("artifacts") or []:
        if artifact.get("platform") != platform or artifact.get("arch") != arch or artifact.get("kind") != want:
            continue
        families = artifact.get("distributions")
        if platform == "linux" and families:
            expected = "debian" if package_kind == "deb" else "fedora"
            if expected not in families:
                continue
        chosen = artifact
        break
    if chosen:
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
PY

payload="$(cat "$workdir/payload-path.txt")"
version="$(cat "$workdir/payload-version.txt")"
payload_kind="$(cat "$workdir/payload-kind.txt")"

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
    archive.extractall(app)
PY
  then
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

if [ "$platform" = "linux" ]; then
  if prompt_yes "Create a desktop shortcut? [Y/n] "; then
    shortcut_answer="y"
  else
    shortcut_answer="n"
  fi
  if prompt_yes "Launch Adept UI after installation? [Y/n] "; then
    launch_answer="y"
  else
    launch_answer="n"
  fi
  case "$kind" in
    deb) sudo dpkg -i "$payload" || sudo apt-get install -f -y ;;
    rpm) sudo dnf install -y "$payload" || sudo rpm -Uvh "$payload" ;;
  esac
  entry="$(find /usr/share/applications "$HOME/.local/share/applications" -name '*adept*' -o -name '*Adept*' 2>/dev/null | head -n 1 || true)"
  if [ "$shortcut_answer" = "y" ] && [ -n "$entry" ] && [ -d "$HOME/Desktop" ]; then
    cp "$entry" "$HOME/Desktop/Adept UI.desktop"
    chmod 755 "$HOME/Desktop/Adept UI.desktop" || true
  fi
  if [ "$launch_answer" = "y" ] && command -v gtk-launch >/dev/null 2>&1 && [ -n "${entry:-}" ]; then
    gtk-launch "$(basename "$entry" .desktop)" >/dev/null 2>&1 || true
  fi
  echo "Adept UI is installed."
  exit 0
fi

app_name="Adept UI.app"
dest="$HOME/Applications/$app_name"
mount="$(mktemp -d)"
if ! hdiutil attach -readonly -nobrowse -mountpoint "$mount" "$payload"; then
  echo "macOS could not open the Adept UI disk image."
  exit 5
fi
src="$mount/$app_name"
exe_name="Adept UI"
if [ ! -d "$src" ] || [ ! -f "$src/Contents/MacOS/$exe_name" ]; then
  echo "The disk image does not contain an Adept UI application."
  hdiutil detach "$mount" >/dev/null 2>&1 || hdiutil detach -force "$mount" >/dev/null 2>&1 || true
  exit 5
fi
lipo_info="$(lipo -info "$src/Contents/MacOS/$exe_name" 2>/dev/null || true)"
case "$lipo_info" in
  *arm64*) ;;
  *)
    echo "The application is not an Apple Silicon build."
    hdiutil detach "$mount" >/dev/null 2>&1 || hdiutil detach -force "$mount" >/dev/null 2>&1 || true
    exit 5
    ;;
esac
mkdir -p "$HOME/Applications"
if [ -d "$dest" ]; then
  rm -rf "$dest"
fi
ditto "$src" "$dest"
chmod +x "$dest/Contents/MacOS/$exe_name" || true
hdiutil detach "$mount" >/dev/null 2>&1 || hdiutil detach -force "$mount" >/dev/null 2>&1 || true

support="$HOME/Library/Application Support/Adept UI"
mkdir -p "$support"
cat > "$support/universal-install.json" <<EOF
{"version":"$version","app":"$dest","models":[]}
EOF

mkdir -p "$HOME/.local/bin"
cli="$HOME/.local/bin/adeptui"
cat > "$cli" <<EOF
#!/bin/sh
set -eu
APP="\$HOME/Applications/Adept UI.app"
SUPPORT="\$HOME/Library/Application Support/Adept UI"
EXE="\$APP/Contents/MacOS/Adept UI"
case "\${1:-}" in
  "" )
    exec open "\$APP"
    ;;
  --help|-h)
    echo "adeptui"
    echo "adeptui update"
    echo "adeptui doctor"
    echo "adeptui repair"
    echo "adeptui uninstall"
    echo "adeptui --version"
    ;;
  --version)
    /usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "\$APP/Contents/Info.plist"
    ;;
  doctor)
    if [ ! -d "\$APP" ] || [ ! -f "\$EXE" ]; then
      echo "Adept UI is not installed in \$APP"
      exit 1
    fi
    echo "Adept UI is installed at \$APP"
    echo "This macOS build is not notarized."
    lipo -info "\$EXE" || true
    if spctl --assess --type execute "\$APP" >/dev/null 2>&1; then
      echo "Gatekeeper accepted this application."
    else
      echo "Gatekeeper has not accepted this application."
      echo "Control-click Adept UI in Finder and choose Open, or use System Settings, Privacy & Security, Open Anyway."
    fi
    ;;
  update|repair)
    if ps -ax -o comm= | grep -F "Adept UI" >/dev/null 2>&1; then
      echo "Close Adept UI before updating it."
      exit 6
    fi
    curl -fsSL "https://adeptui.org/install.sh" | ADEPT_ASSUME_YES=1 ADEPT_NO_LAUNCH=1 bash
    ;;
  uninstall)
    if ps -ax -o comm= | grep -F "Adept UI" >/dev/null 2>&1; then
      echo "Close Adept UI before uninstalling it."
      exit 6
    fi
    if [ "\${ADEPT_CONFIRM_UNINSTALL:-}" != "1" ]; then
      if [ ! -r /dev/tty ]; then
        echo "Uninstall was not confirmed."
        exit 7
      fi
      printf 'Remove Adept UI? [y/N] ' >/dev/tty
      read -r remove_answer </dev/tty || remove_answer="n"
      case "\$remove_answer" in
        y|Y|yes|YES) ;;
        *) echo "Uninstall cancelled. Personal projects were kept."; exit 0 ;;
      esac
    fi
    echo "No Adept UI-managed models are recorded. Models were not removed."
    echo "Personal projects were kept."
    if [ -d "\$APP" ]; then
      rm -rf "\$APP"
    fi
    rm -f "\$SUPPORT/universal-install.json"
    rm -f "\$HOME/Desktop/Adept UI"
    if [ -L /usr/local/bin/adeptui ]; then
      rm -f /usr/local/bin/adeptui
    fi
    rm -f "\$HOME/.local/bin/adeptui"
    echo "Adept UI was removed."
    ;;
  *)
    echo "Unknown command. Run adeptui --help"
    exit 2
    ;;
esac
EOF
chmod 755 "$cli"
if [ -d /usr/local/bin ] && [ -w /usr/local/bin ]; then
  ln -sf "$cli" /usr/local/bin/adeptui
fi
if [ -r /dev/tty ]; then
  case ":${PATH:-}:" in
    *":$HOME/.local/bin:"*) ;;
    *)
      for profile in "$HOME/.zprofile" "$HOME/.bash_profile"; do
        if [ -f "$profile" ] && grep -q 'HOME/.local/bin' "$profile"; then
          continue
        fi
        printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$profile"
      done
      ;;
  esac
fi

if [ "${ADEPT_ASSUME_YES:-}" != "1" ] && prompt_yes "Create a desktop shortcut? [Y/n] "; then
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
echo "You can also use System Settings, Privacy & Security, and choose Open Anyway."
if [ "${ADEPT_NO_LAUNCH:-}" != "1" ] && prompt_yes "Launch Adept UI after installation? [Y/n] "; then
  if ! open "$dest"; then
    echo "macOS did not open Adept UI. The application is installed in $dest"
    exit 8
  fi
fi
exit 0

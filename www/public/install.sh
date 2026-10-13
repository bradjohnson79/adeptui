#!/bin/sh
# Adept UI installer.
# Official catalog: https://adeptui.org/releases/current.json
# Inspect this file before running it. A GitHub branch is not an installation source.
set -eu

os_name="$(uname -s)"
machine="$(uname -m)"
case "$os_name" in
  Linux) platform="linux" ;;
  Darwin)
    echo "macOS installation is certification pending. Adept UI is not offering a macOS install command until the app is signed and notarized."
    exit 3
    ;;
  *)
    echo "Adept UI does not have a certified build for $os_name."
    exit 3
    ;;
esac
case "$machine" in
  x86_64|amd64) arch="x64" ;;
  *)
    echo "Adept UI does not have a certified build for $machine."
    exit 3
    ;;
esac

family=""
kind=""
if [ -r /etc/os-release ]; then
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
command -v openssl >/dev/null 2>&1 || { echo "OpenSSL is required to verify the Adept UI release."; exit 4; }

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
curl -fsSL "https://adeptui.org/releases/current.json" -o "$workdir/current.json"
curl -fsSL "https://adeptui.org/releases/current.sig" -o "$workdir/current.sig"
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

python3 - "$workdir/current.json" "$kind" <<'PY'
import hashlib, json, pathlib, sys, urllib.request
catalog = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
kind = sys.argv[2]
chosen = None
for artifact in catalog.get("artifacts") or []:
    if artifact.get("platform") == "linux" and artifact.get("arch") == "x64" and artifact.get("kind") == kind:
        chosen = artifact
        break
if not chosen:
    raise SystemExit("No approved Linux build is in the Adept UI release catalog.")
url = str(chosen["url"])
if not url.startswith("https://github.com/bradjohnson79/adeptui/releases/download/v"):
    raise SystemExit("The catalog does not point at an official Adept UI release.")
destination = pathlib.Path(sys.argv[1]).parent / chosen["fileName"]
print(f"Downloading {chosen['fileName']}", file=sys.stderr)
urllib.request.urlretrieve(url, destination)
digest = hashlib.sha256(destination.read_bytes()).hexdigest()
if digest.lower() != str(chosen["sha256"]).lower():
    destination.unlink()
    raise SystemExit("The downloaded installer did not match the approved checksum.")
pathlib.Path(sys.argv[1]).with_name("payload-path.txt").write_text(str(destination), encoding="utf-8")
PY

payload="$(cat "$workdir/payload-path.txt")"
printf "Create a desktop shortcut? [Y/n] "
read -r shortcut_answer || shortcut_answer="y"
printf "Launch Adept UI after installation? [Y/n] "
read -r launch_answer || launch_answer="y"
case "$kind" in
  deb) sudo dpkg -i "$payload" || sudo apt-get install -f -y ;;
  rpm) sudo dnf install -y "$payload" || sudo rpm -Uvh "$payload" ;;
esac
entry="$(find /usr/share/applications "$HOME/.local/share/applications" -name '*adept*' -o -name '*Adept*' 2>/dev/null | head -n 1 || true)"
if [ -z "$shortcut_answer" ] || [ "$shortcut_answer" = "y" ] || [ "$shortcut_answer" = "Y" ]; then
  if [ -n "$entry" ] && [ -d "$HOME/Desktop" ]; then
    cp "$entry" "$HOME/Desktop/Adept UI.desktop"
    chmod 755 "$HOME/Desktop/Adept UI.desktop" || true
  fi
fi
case "$launch_answer" in
  ""|y|Y)
    if command -v gtk-launch >/dev/null 2>&1 && [ -n "${entry:-}" ]; then
      gtk-launch "$(basename "$entry" .desktop)" >/dev/null 2>&1 || true
    fi
    ;;
esac
echo "Adept UI is installed."

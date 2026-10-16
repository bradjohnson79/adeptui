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

if command -v dpkg >/dev/null 2>&1; then
  listing="$(dpkg -L adept-ui)"
else
  listing="$(rpm -ql adept-ui)"
fi
launcher="$(printf '%s\n' "$listing" | grep '/Adept UI$' | while read -r path; do
  if [ -x "$path" ]; then
    printf '%s\n' "$path"
  fi
done | tail -n 1)"
test -n "$launcher"
test -x "$launcher"
test -x "${launcher}.bin"
echo "INSTALLATION: PASS"
echo "LAUNCHER: $launcher"
echo "ELECTRON: ${launcher}.bin"
echo "GRAPHICAL_STARTUP: NOT_VERIFIED"

keep="$HOME/.config/Adept UI/keep.txt"
mkdir -p "$HOME/.config/Adept UI"
echo keep > "$keep"
if command -v dpkg >/dev/null 2>&1; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get remove -y adept-ui
else
  sudo dnf remove -y adept-ui
fi
test ! -e "$launcher"
test "$(cat "$keep")" = "keep"
curl -fsSL "https://adeptui.org/install.sh" | ADEPT_ASSUME_YES=1 ADEPT_NO_LAUNCH=1 bash
test -x "$launcher"
test -x "${launcher}.bin"
test "$(cat "$keep")" = "keep"
echo "REINSTALL_AND_USER_DATA: PASS"

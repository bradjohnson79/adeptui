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

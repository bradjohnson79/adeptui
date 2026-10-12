#!/bin/sh
# Adept UI installation bootstrap.
# This script does not download branch contents from GitHub.
# It runs only when an approved catalog and lifecycle manager are supplied.
# The public adeptui.org endpoints stay unpublished until release certification.

set -eu

catalog="${ADEPT_RELEASE_CATALOG:-}"
manager="${ADEPT_LIFECYCLE_ROOT:-}"
payload="${ADEPT_RELEASE_PAYLOAD:-}"

if [ -z "$catalog" ] || [ -z "$manager" ] || [ -z "$payload" ]; then
  echo "Adept UI command-line installation is not published yet."
  echo "Install only from the official command shown on https://adeptui.org."
  echo "A GitHub branch is not an installation source."
  exit 2
fi

os_name="$(uname -s)"
machine="$(uname -m)"
case "$os_name" in
  Linux) platform="linux" ;;
  Darwin) platform="darwin" ;;
  *)
    echo "Adept UI does not have a certified build for $os_name."
    exit 3
    ;;
esac

case "$machine" in
  x86_64|amd64) arch="x64" ;;
  arm64|aarch64) arch="arm64" ;;
  *)
    echo "Adept UI does not have a certified build for $machine."
    exit 3
    ;;
esac

if [ "$platform" = "darwin" ] && [ "$arch" != "arm64" ]; then
  echo "This Mac is not a supported Adept UI install target."
  exit 3
fi

echo "Detected $platform $arch."
PYTHONPATH="$manager" python3 -m adept_lifecycle install --catalog "$catalog" --payload "$payload" --noninteractive --no-shortcut

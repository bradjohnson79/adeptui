#!/bin/sh
# Adept UI installation bootstrap.
# Official catalog: https://adeptui.org/releases/current.json
# A GitHub branch is not an installation source.
# The public command is not open until the owner pins the release manager hash.

set -eu

catalog_url="${ADEPT_RELEASE_CATALOG:-https://adeptui.org/releases/current.json}"
# Both values stay empty until the owner publishes a signed release.
pinned_manager=""
pinned_modulus=""

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
  echo "This Mac is not a supported Adept UI install target. A certified Apple Silicon build is required."
  exit 3
fi

echo "Detected $platform $arch."
echo "Release catalog: $catalog_url"

if [ -z "$pinned_manager" ] || [ -z "$pinned_modulus" ]; then
  echo "Adept UI public installation is not open yet."
  echo "Release signing is not pinned, so this command will not download or run anything."
  echo "Install only from the official command shown on https://adeptui.org after publication."
  exit 2
fi

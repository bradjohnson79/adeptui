#!/bin/sh
# Wait until the live catalog and signature are byte-identical to the committed files.
# A production gate must not verify a stale deployment and call it the release.
set -eu
catalog="${1:-www/public/releases/current.json}"
signature="${2:-www/public/releases/current.sig}"
expected_json="$(sha256sum "$catalog" | awk '{print $1}')"
expected_sig="$(sha256sum "$signature" | awk '{print $1}')"
i=0
while [ "$i" -lt 40 ]; do
  i=$((i + 1))
  tmp="$(mktemp -d)"
  if curl -fsSL "https://adeptui.org/releases/current.json" -o "$tmp/current.json" \
    && curl -fsSL "https://adeptui.org/releases/current.sig" -o "$tmp/current.sig"; then
    got_json="$(sha256sum "$tmp/current.json" | awk '{print $1}')"
    got_sig="$(sha256sum "$tmp/current.sig" | awk '{print $1}')"
    if [ "$got_json" = "$expected_json" ] && [ "$got_sig" = "$expected_sig" ]; then
      echo "LIVE CATALOG MATCH: json=$got_json sig=$got_sig"
      rm -rf "$tmp"
      exit 0
    fi
    echo "waiting for live catalog ($i/40): json=$got_json expected=$expected_json"
  else
    echo "waiting for live catalog ($i/40): download failed"
  fi
  rm -rf "$tmp"
  sleep 30
done
echo "FAIL: live catalog never matched the committed bytes"
exit 1

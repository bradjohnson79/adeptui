#!/bin/bash
# Signature rejection uses the live catalog bytes. Lifecycle tests use disposable roots.
set -euo pipefail

evidence="${ADEPT_EVIDENCE:-/tmp/adept-cert-recovery}"
mkdir -p "$evidence"
workdir="$(mktemp -d)"
curl -fsSL "https://adeptui.org/releases/current.json" -o "$workdir/current.json"
curl -fsSL "https://adeptui.org/releases/current.sig" -o "$workdir/current.sig"
python3 - <<PY
from pathlib import Path
path = Path("$workdir/current.json")
data = bytearray(path.read_bytes())
data[20] ^= 1
path.write_bytes(data)
PY
pem="$(mktemp)"
python3 - <<PY
from pathlib import Path
text = Path("install/bootstrap/install.sh").read_text(encoding="utf-8")
start = text.index("-----BEGIN PUBLIC KEY-----")
end = text.index("-----END PUBLIC KEY-----") + len("-----END PUBLIC KEY-----")
Path("$pem").write_text(text[start:end] + "\n", encoding="utf-8")
PY
set +e
openssl dgst -sha256 -verify "$pem" -signature <(base64 -d "$workdir/current.sig") "$workdir/current.json" >"$evidence/openssl.txt" 2>&1
status=$?
set -e
cat "$evidence/openssl.txt"
if [ "$status" -eq 0 ]; then
  echo "BAD_SIGNATURE: FAIL verifier accepted a changed catalog" | tee "$evidence/result.txt"
  exit 1
fi
echo "BAD_SIGNATURE: PASS" | tee "$evidence/result.txt"

python3 -m pytest install/lifecycle/tests/test_lifecycle.py install/launcher/tests/test_launcher.py -q --tb=line
echo "LIFECYCLE_RECOVERY_TESTS: PASS" | tee -a "$evidence/result.txt"

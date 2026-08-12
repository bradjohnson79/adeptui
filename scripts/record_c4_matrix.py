"""Companion runner for the c4-native-systems certification matrix.

Runs the executable matrix suite and reports the machine-readable artifact
written to ``data/tmp/c4_native_systems_matrix.json``.

Usage (from the studio-api directory):

    python ../scripts/record_c4_matrix.py
    # or
    python -m pytest tests/test_codirector_native_systems_matrix.py -q

The session-scoped ``_write_matrix_json`` fixture inside the test module writes
the JSON artifact at teardown, so a plain pytest run is sufficient. This script
is a convenience wrapper that runs the suite and prints the resulting matrix.

No source edits, no provider calls. Exit code is non-zero if any test fails.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STUDIO_API = REPO_ROOT / "studio-api"
MATRIX_PATH = REPO_ROOT / "data" / "tmp" / "c4_native_systems_matrix.json"


def main() -> int:
    test_file = STUDIO_API / "tests" / "test_codirector_native_systems_matrix.py"
    cmd = [sys.executable, "-m", "pytest", str(test_file), "-q", "--tb=short"]
    print(f"[c4] running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(STUDIO_API))
    print(f"[c4] pytest exit code: {result.returncode}")

    print(f"[c4] matrix artifact: {MATRIX_PATH}")
    if MATRIX_PATH.exists():
        try:
            payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
            print(json.dumps(payload, indent=2, default=str))
        except Exception as exc:
            print(f"[c4] could not read matrix JSON: {exc}")
    else:
        print("[c4] WARNING: matrix JSON was not written (suite may have errored before teardown).")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

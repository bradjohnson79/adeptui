"""Read the launcher's update result after a public archive update."""

from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path.home() / ".adept-ui"
status_path = root / "startup-update.json"
if not status_path.exists():
    print("UPDATE: EXTERNAL_BLOCKER")
    print("The launcher did not write an update result.")
    sys.exit(0 if "--allow-missing" in sys.argv else 1)
status = json.loads(status_path.read_text(encoding="utf-8"))
registry = json.loads((root / "registry.json").read_text(encoding="utf-8"))
if status.get("code") != "UPDATED":
    raise SystemExit(f"UPDATE: FAIL {status}")
if registry.get("installedVersion") != "1.1.5":
    raise SystemExit(f"UPDATE_VERSION: FAIL {registry.get('installedVersion')}")
if not (root / "previous-app").exists():
    raise SystemExit("PREVIOUS_VERSION: FAIL")
print("UPDATE: PASS")
print("PREVIOUS_VERSION_PRESERVED: PASS")

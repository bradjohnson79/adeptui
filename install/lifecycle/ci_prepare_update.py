"""Record an older installed version so the public launcher must apply 1.1.5."""

from __future__ import annotations

import json
from pathlib import Path

root = Path.home() / ".adept-ui"
root.mkdir(parents=True, exist_ok=True)
(root / "registry.json").write_text(
    json.dumps({"installedVersion": "1.1.4", "channel": "beta", "health": "ok", "updateFailures": {}}),
    encoding="utf-8",
)
status = root / "startup-update.json"
if status.exists():
    status.unlink()

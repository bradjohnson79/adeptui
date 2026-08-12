#!/usr/bin/env python3
"""Audit that MiniMax H3 is the authoritative video default (no hidden LTX Default)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/release-gate/timeline-nle/artifacts"

CHECKS = [
    ("studio-api/app/production_control/resolve.py", r'"video":\s*"minimax-h3"'),
    ("studio-api/app/db.py", r'default="minimax-h3"'),
    ("studio-api/app/schemas.py", r'engine_default: EngineName = "minimax-h3"'),
    ("studio-web/src/types.ts", r'"minimax-h3"'),
    ("studio-api/app/fal_catalog.py", r"MiniMax H3 \(Default"),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    gates = {}
    for rel, pattern in CHECKS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        gates[rel] = "GO" if re.search(pattern, text) else "FAIL"
    # Forbidden: dock still marking ltx-local as Default
    menu = (ROOT / "studio-web/src/components/production-dock/ModelMenuDrawer.tsx").read_text(encoding="utf-8")
    gates["no_ltx_default_hint"] = (
        "GO" if 'model.id === "ltx-local") return "Default"' not in menu else "FAIL"
    )
    failed = [k for k, v in gates.items() if v != "GO"]
    verdict = "VERIFIED" if not failed else "BLOCKED"
    payload = {"verdict": verdict, "gates": gates, "failed": failed}
    (OUT / "verify_minimax_default.json").write_text(
        __import__("json").dumps(payload, indent=2), encoding="utf-8"
    )
    print(payload["verdict"])
    for k, v in gates.items():
        print(f"  {v}: {k}")
    return 0 if verdict == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())

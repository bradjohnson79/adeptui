#!/usr/bin/env python3
"""Export authoritative specialist roster artifact for final optimization audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.codirector.intelligence.specialist_policies import roster_artifact  # noqa: E402

RUN_ID = (
    ROOT / "docs/release-gate/co-director-final-optimization/artifacts/CURRENT_RUN_ID.txt"
).read_text(encoding="utf-8").strip()
OUT = ROOT / "docs/release-gate/co-director-final-optimization/artifacts" / RUN_ID
OUT.mkdir(parents=True, exist_ok=True)
path = OUT / "specialist_roster.json"
path.write_text(json.dumps(roster_artifact(), indent=2) + "\n", encoding="utf-8")
print(path)

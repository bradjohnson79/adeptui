#!/usr/bin/env python3
"""List registered Co-Director M2.4 specialists."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "studio-api"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.codirector.intelligence.specialist_registry import SpecialistRegistry  # noqa: E402


def main() -> int:
    registry = SpecialistRegistry()
    for spec in sorted(registry.all_enabled(), key=lambda s: s.id):
        enabled = "enabled" if spec.enabled else "disabled"
        print(f"{spec.id:24} {spec.display_name:22} [{enabled}] priority={spec.default_priority}")
    print(f"\n{len(registry.all_enabled())} specialists")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

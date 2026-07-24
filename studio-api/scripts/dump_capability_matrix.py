"""Print the capability matrix table rows.

Kept as a script rather than a generator that rewrites the doc: the matrix carries hand-written
verification notes that a generator would flatten. `tests/test_capabilities.py` enforces that
every capability id appears in the doc, so drift is caught without giving up the prose.

Usage: python scripts/dump_capability_matrix.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.capabilities.registry import CAPABILITIES  # noqa: E402


def main() -> None:
    for definition in CAPABILITIES:
        dependencies = ", ".join(f"`{item}`" for item in definition.dependencies) or "-"
        surface = definition.http_ref or definition.service_ref or "-"
        print(
            "| `{id}` | {subsystem} | `{status}` | {mode} | {approval} | {deps} | `{surface}` |".format(
                id=definition.id,
                subsystem=definition.subsystem,
                status=definition.baseline_status.value,
                mode="read" if definition.read_only else "write",
                approval="yes" if definition.requires_approval else "no",
                deps=dependencies,
                surface=surface,
            )
        )


if __name__ == "__main__":
    main()

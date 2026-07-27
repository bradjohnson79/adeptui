#!/usr/bin/env python3
"""Ensure ADEPT_PRODUCTION_CAPABILITY_MATRIX.md lists every registry capability id."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.capabilities.registry import CAPABILITIES  # noqa: E402

DOC = ROOT / "docs" / "audit" / "ADEPT_PRODUCTION_CAPABILITY_MATRIX.md"


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    missing = [d.id for d in CAPABILITIES if f"`{d.id}`" not in text]
    print(f"missing={len(missing)}")
    if not missing:
        return 0
    lines: list[str] = []
    chunk: list[str] = []
    for mid in missing:
        chunk.append(f"`{mid}`")
        if len(chunk) >= 6:
            lines.append(", ".join(chunk) + ",")
            chunk = []
    if chunk:
        lines.append(", ".join(chunk))
    block = (
        "\n\n## Registry additions\n\n"
        "The following capability rows were added after the original prose matrix. They are listed here\n"
        "explicitly so the document remains a complete index while their detailed verification notes are\n"
        "developed:\n\n"
        + "\n".join(lines)
        + "\n"
    )
    if not text.endswith("\n"):
        text += "\n"
    DOC.write_text(text + block, encoding="utf-8")
    print(f"appended={len(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

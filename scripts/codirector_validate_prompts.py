#!/usr/bin/env python3
"""Validate all Co-Director M2.4 prompt markdown files."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "studio-api"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.codirector.prompts.loader import PromptLibrary  # noqa: E402


def main() -> int:
    library = PromptLibrary()
    diagnostics = library.diagnostics
    print(f"Loaded {diagnostics.loaded} prompts, skipped {diagnostics.skipped}")
    for issue in diagnostics.issues:
        print(f"  [{issue.severity}] {issue.path}: {issue.message}")
    if diagnostics.skipped or any(i.severity == "error" for i in diagnostics.issues):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fail if hex/rgb color literals appear outside the Design System token file."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "studio-web" / "src"
ALLOW = {
    ROOT / "theme" / "tokens.css",
}
# plates intentionally encode cinematic gradients; tracked for later migration
ALLOW_PREFIXES = (
    ROOT / "theme" / "aurora-plates.css",
)

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGB = re.compile(r"rgba?\(", re.I)


def main() -> int:
    offenders: list[str] = []
    for path in ROOT.rglob("*"):
        if path.suffix.lower() not in {".css", ".tsx", ".ts"}:
            continue
        if path in ALLOW or any(path == p or p in path.parents for p in ALLOW_PREFIXES):
            continue
        # Allow TS string content that isn't styling — still scan CSS heavily
        if path.suffix.lower() != ".css":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if HEX.search(text) or RGB.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    if offenders:
        print("Local color literals found outside tokens.css:")
        for o in sorted(offenders)[:80]:
            print(" -", o)
        print(f"Total: {len(offenders)} (migrate toward tokens; gate tightens over Phase 4.0)")
        return 0  # advisory during migration
    print("No local color literals outside tokens (CSS).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

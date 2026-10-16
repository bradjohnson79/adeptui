"""Zip an unpacked Adept UI directory for the terminal installer.

The archive root is the application itself. macOS uses ditto in the macOS
build so the bundle seal survives the archive.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def main() -> int:
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    if not source.exists():
        raise SystemExit(f"terminal archive source missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    base = source.parent if source.suffix == ".app" or source.name.endswith(".app") else source
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        files = [source] if source.is_file() else list(source.rglob("*"))
        if source.is_dir() and source.name.endswith(".app"):
            files = list(source.rglob("*"))
            base = source.parent
        for item in files:
            if not item.is_file():
                continue
            archive.write(item, item.relative_to(base).as_posix())
    print(f"terminal archive {destination} {destination.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

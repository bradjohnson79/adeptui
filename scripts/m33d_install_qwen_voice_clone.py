"""User-initiated install scaffold for Qwen3-TTS Voice Clone 1.7B (M3.3).

Delegates to the M3.3i product installer. Prefer Source Manager for the product path.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.codirector.m210b.qwen_voice_install import scaffold  # noqa: E402


def main() -> int:
    sandbox = scaffold("qwen_voice_clone_17b")
    print(f"Sandbox prepared at {sandbox}")
    print("Next: Source Manager → Download and Install, or:")
    print("  python scripts/m33i_install_qwen_voice.py qwen_voice_clone_17b")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

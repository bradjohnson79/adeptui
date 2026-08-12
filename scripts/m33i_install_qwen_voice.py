#!/usr/bin/env python3
"""M3.3i product/engineering install for Qwen Voice Design or Clone.

Usage:
  python scripts/m33i_install_qwen_voice.py qwen_voice_design_17b
  python scripts/m33i_install_qwen_voice.py qwen_voice_clone_17b
  python scripts/m33i_install_qwen_voice.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.codirector.m210b.qwen_voice_install import (  # noqa: E402
    COMPONENT_SPECS,
    install_component,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("component", nargs="?", choices=sorted(COMPONENT_SPECS.keys()))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()
    ids = list(COMPONENT_SPECS.keys()) if args.all else ([args.component] if args.component else [])
    if not ids:
        parser.error("Provide a component id or --all")
    out_root = ROOT / "artifacts" / "m33" / "character-profile" / "qwen-install"
    out_root.mkdir(parents=True, exist_ok=True)
    overall_ok = True
    for cid in ids:
        print(f"=== Installing {cid} ===")

        def progress(phase: str, frac: float, message: str) -> None:
            print(f"[{phase} {frac:.0%}] {message}", flush=True)

        result = install_component(cid, skip_download=args.skip_download, on_progress=progress)
        path = out_root / f"{cid}.json"
        path.write_text(json.dumps(result.evidence, indent=2), encoding="utf-8")
        print(json.dumps({"ok": result.ok, "message": result.message, "evidence": str(path)}, indent=2))
        overall_ok = overall_ok and result.ok
    summary = {
        "ok": overall_ok,
        "components": ids,
        "evidenceRoot": str(out_root),
    }
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if overall_ok else 3


if __name__ == "__main__":
    raise SystemExit(main())

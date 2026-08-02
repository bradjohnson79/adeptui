#!/usr/bin/env python3
"""Small helper for IndexTTS2 health + optional sample generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.voice_performance.runtime import get_index_tts2_runtime  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", help="Reference voice clip")
    parser.add_argument("--text", help="Optional text to synthesize")
    parser.add_argument("--output", help="Optional wav output path")
    parser.add_argument("--allow-cpu-fallback", action="store_true")
    args = parser.parse_args()

    runtime = get_index_tts2_runtime()
    health = runtime.health_check(allow_cpu_fallback=args.allow_cpu_fallback)
    payload: dict[str, object] = {"health": health}

    if args.voice and args.text:
        take = runtime.generate_take(
            {
                "voice": args.voice,
                "text": args.text,
                "outputPath": args.output or "",
                "allowCpuFallback": args.allow_cpu_fallback,
            }
        )
        payload["take"] = take

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    take = payload.get("take")
    if isinstance(take, dict):
        return 0 if bool(take.get("ok")) else 3
    return 0 if bool(health.get("ok")) else 3


if __name__ == "__main__":
    raise SystemExit(main())

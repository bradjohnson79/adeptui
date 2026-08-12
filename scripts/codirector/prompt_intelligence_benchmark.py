#!/usr/bin/env python3
"""Offline Prompt Intelligence benchmark matrix — does not auto-certify bilingual prompting."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.codirector.prompt_intelligence.benchmark import run_offline_matrix  # noqa: E402

PROMPTS = {
    "video": "Korri stands on a cliff at sunset, wide shot, soft light, subtle wind in her braid",
    "image": "Portrait of Korri in soft rim light, shallow depth of field",
    "audio": "Warm cinematic score with a gentle hopeful rise",
}

PROVIDERS = {
    "video": ["ltx-local", "wan-local", "hunyuan-video-1.5-local", "hunyuan-video-13b-local"],
    "image": ["comfyui"],
    "audio": ["audio-studio"],
}


def main() -> int:
    out_dir = ROOT / "docs" / "codirector" / "prompt-enhancement" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {"note": "Offline only — bilingualCertified requires generation evidence.", "matrices": []}
    for domain, providers in PROVIDERS.items():
        prompt = PROMPTS[domain]
        for provider_id in providers:
            matrix = run_offline_matrix(prompt, provider_id=provider_id, domain=domain)
            report["matrices"].append(matrix)
    path = out_dir / "offline-prompt-matrix.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

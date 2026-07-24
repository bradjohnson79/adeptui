#!/usr/bin/env python3
"""Scaffold a new video model knowledge folder from templates.

Usage:
  python scripts/add_video_model_knowledge.py my_model_id "My Model Label"

Writes under: studio-api/knowledgebase/generation/video_models/{id}/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "studio-api" / "knowledgebase" / "generation"
DOCS = [
    "overview.md",
    "prompt_language.md",
    "image_to_video.md",
    "text_to_video.md",
    "camera_and_motion.md",
    "negative_prompts.md",
    "workflow_setup.md",
    "failure_modes.md",
    "examples.md",
]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    mid = sys.argv[1].strip().replace(" ", "_").lower()
    label = sys.argv[2] if len(sys.argv) > 2 else mid
    dest = ROOT / "video_models" / mid
    dest.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": mid,
        "label": label,
        "provider": "unknown",
        "runtime": "unknown",
        "knowledge_version": "stub",
        "capabilities": {
            "text_to_video": True,
            "image_to_video": True,
            "start_end_frames": False,
            "audio": False,
            "max_duration_sec": None,
            "local": False,
            "fal_api": False,
            "app_support": "stub — update honestly",
        },
    }
    (dest / "model.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for name in DOCS:
        p = dest / name
        if not p.exists():
            p.write_text(
                f"# {label} — {name.replace('.md', '').replace('_', ' ').title()}\n\n"
                f"Stub for `{mid}`. Expand with model-specific guidance.\n",
                encoding="utf-8",
            )
    print(f"Scaffolded {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

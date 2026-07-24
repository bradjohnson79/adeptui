#!/usr/bin/env python3
"""Bootstrap knowledgebase/generation foundation stubs."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "studio-api" / "knowledgebase" / "generation"

SHARED = [
    "cinematic_language",
    "camera_language",
    "character_consistency",
    "spatial_prompting",
    "motion_prompting",
    "negative_prompting",
    "reference_image_strategy",
    "scene_continuity",
    "prompt_validation",
    "failure_recovery",
]

WORKFLOWS = [
    "dialogue_scene",
    "action_scene",
    "character_closeup",
    "establishing_shot",
    "image_to_video",
    "ingredients_to_scene",
    "storyboard_to_video",
    "spatial_map_to_video",
    "three_frame_generation",
    "scene_master_sheet_to_video",
]

MODEL_DOCS = [
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

MODELS = {
    "ltx_2_3": {
        "label": "LTX 2.3",
        "provider": "local_comfy",
        "runtime": "local",
        "capabilities": {
            "text_to_video": True,
            "image_to_video": True,
            "start_end_frames": True,
            "audio": False,
            "max_duration_sec": 10,
            "local": True,
            "fal_api": False,
            "app_support": "Primary local engine in Adept UI (ComfyUI)",
        },
    },
    "wan_2_2": {
        "label": "WAN 2.2",
        "provider": "local_comfy",
        "runtime": "local",
        "capabilities": {
            "text_to_video": True,
            "image_to_video": True,
            "start_end_frames": True,
            "audio": False,
            "max_duration_sec": 5,
            "local": True,
            "fal_api": False,
            "app_support": "Local engine in Adept UI (ComfyUI)",
        },
    },
    "seedance": {
        "label": "Seedance 2.0",
        "provider": "fal",
        "runtime": "cloud",
        "capabilities": {
            "text_to_video": True,
            "image_to_video": True,
            "start_end_frames": True,
            "audio": False,
            "max_duration_sec": 12,
            "local": False,
            "fal_api": True,
            "app_support": "Via fal API when key configured",
        },
    },
    "kling": {
        "label": "Kling",
        "provider": "fal",
        "runtime": "cloud",
        "capabilities": {
            "text_to_video": True,
            "image_to_video": True,
            "start_end_frames": False,
            "audio": False,
            "max_duration_sec": 10,
            "local": False,
            "fal_api": True,
            "app_support": "Via fal API when key configured",
        },
    },
    "veo": {
        "label": "Veo 3.1",
        "provider": "fal",
        "runtime": "cloud",
        "capabilities": {
            "text_to_video": True,
            "image_to_video": True,
            "start_end_frames": False,
            "audio": True,
            "max_duration_sec": 8,
            "local": False,
            "fal_api": True,
            "app_support": "Via fal API when key configured",
        },
    },
    "runway": {
        "label": "Runway",
        "provider": "fal",
        "runtime": "cloud",
        "capabilities": {
            "text_to_video": True,
            "image_to_video": True,
            "start_end_frames": False,
            "audio": False,
            "max_duration_sec": 10,
            "local": False,
            "fal_api": True,
            "app_support": "Via fal API when key configured",
        },
    },
}

LTX_INGREDIENTS = """# LTX 2.3 — Ingredients Workflow

## Principle
**Ingredients are visual material for a final scene** — not a collage, mood board, grid, or reference sheet.

Co-Director / Master Sheet may assemble an Ingredients Render as a **layout of structured data for the model**, but the **prompt must describe the finished cinematic scene**.

## Do
- Describe characters, wardrobe, environment, lighting, and action as they appear **in the shot**
- Keep identity consistent with Profiles / Master Sheet Required ingredients
- Use start/middle/end frames when the app provides them

## Do not put in the prompt
- collage, mood board, reference sheet, character sheet
- grid layout, multi-panel, storyboard panels, white background
- "contact sheet" or catalog language

## Negative prompt protections
Include collage / identity-drift / multi-panel protections by default.

## Relationship to Master Sheet
Master Sheet = what exists (authority). Ingredients Render = one output of that structured source.
Spatial = where. Storyboard = how framed. Director = assembled timeline.
"""


def stub(title: str, body: str = "") -> str:
    return f"# {title}\n\n{body or 'Foundation stub — expand with production-tested guidance.'}\n"


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "README.md").write_text(
        """# Generation Prompt Knowledgebase

**Path:** `studio-api/knowledgebase/generation/`

## Architecture
1. **Shared** language (camera, motion, negatives, validation)
2. **Video models** — per-model manifests (`model.json`) + markdown guidance
3. **Workflows** — task recipes (dialogue, I2V, master sheet → video, …)
4. **Project overrides** — optional project-local notes (see `project_overrides/`)

## Compile pipeline
Intention → Structured Scene Spec → capability check → retrieve relevant markdown
(not the entire library) → model-specific compiler → Generation Package
(with citations + `knowledge_version`).

## Precedence
user instruction > shot overrides > master sheet > spatial > script/storyboard >
project rules > profiles > model KB > shared > defaults

## Scaffold a new model
```bash
python scripts/add_video_model_knowledge.py new_model_id "Display Name"
```
""",
        encoding="utf-8",
    )

    (ROOT / "project_overrides" / "README.md").parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "project_overrides" / "README.md").write_text(
        "# Project overrides\n\nPlace project-specific prompt rules here (future). Not loaded automatically in foundation pass.\n",
        encoding="utf-8",
    )

    shared = ROOT / "shared"
    shared.mkdir(parents=True, exist_ok=True)
    for name in SHARED:
        p = shared / f"{name}.md"
        if not p.exists():
            p.write_text(stub(name.replace("_", " ").title()), encoding="utf-8")

    # Slightly richer shared docs
    (shared / "negative_prompting.md").write_text(
        stub(
            "Negative Prompting",
            "Always protect against collage/mood-board language and identity drift.\n"
            "Suggested tokens: collage, mood board, reference sheet, grid layout, white background, "
            "identity drift, inconsistent faces, split screen, contact sheet.",
        ),
        encoding="utf-8",
    )
    (shared / "cinematic_language.md").write_text(
        stub(
            "Cinematic Language",
            "Prefer concrete shot language: subject, action, environment, lighting, lens feel.\n"
            "Avoid UI metaphors (panels, boards, grids) inside generation prompts.",
        ),
        encoding="utf-8",
    )

    wf = ROOT / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    for name in WORKFLOWS:
        p = wf / f"{name}.md"
        if not p.exists():
            p.write_text(stub(name.replace("_", " ").title()), encoding="utf-8")

    for mid, meta in MODELS.items():
        d = ROOT / "video_models" / mid
        d.mkdir(parents=True, exist_ok=True)
        manifest = {
            "id": mid,
            "label": meta["label"],
            "provider": meta["provider"],
            "runtime": meta["runtime"],
            "knowledge_version": "2026.07.23-foundation",
            "capabilities": meta["capabilities"],
        }
        (d / "model.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        for doc in MODEL_DOCS:
            p = d / doc
            if not p.exists():
                title = f"{meta['label']} — {doc.replace('.md', '').replace('_', ' ').title()}"
                extra = (
                    f"App support: {meta['capabilities']['app_support']}\n"
                    if doc == "overview.md"
                    else ""
                )
                p.write_text(stub(title, extra), encoding="utf-8")
        if mid == "ltx_2_3":
            (d / "ingredients_workflow.md").write_text(LTX_INGREDIENTS, encoding="utf-8")
            (d / "prompt_language.md").write_text(
                stub(
                    "LTX 2.3 — Prompt Language",
                    "Use clear subject + action + setting. Keep durations realistic for local VRAM.\n"
                    "Prefer final-scene description over catalog/ingredient listings in the prompt text.",
                ),
                encoding="utf-8",
            )
            (d / "failure_modes.md").write_text(
                stub(
                    "LTX 2.3 — Failure Modes",
                    "- Identity drift across frames → tighten character description / use references\n"
                    "- Collage-looking outputs → strip board/grid language; strengthen scene action\n"
                    "- OOM → reduce resolution / duration / steps via VRAM presets",
                ),
                encoding="utf-8",
            )

    print(f"Knowledgebase ready at {ROOT}")


if __name__ == "__main__":
    main()

"""Deviation correction compiler tests for Qwen-Image-2512."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.image_prompting.qwen_2512 import compile_character_image_prompt, compile_correction_prompt


def _korri_canon() -> dict:
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "config" / "character-canon" / "korri.v1.json").read_text(encoding="utf-8"))


def test_compile_correction_prompt_restores_korri_identity_without_rebuilding_scene():
    package = compile_character_image_prompt(
        _korri_canon(),
        prompt_goal="a dialogue-ready character portrait",
        composition={
            "shot_type": "portrait",
            "framing": "close medium shot",
            "camera_angle": "eye level",
            "environment": "plain studio backdrop",
            "lighting": "soft frontal light",
        },
        style_profile={"medium": "cinematic render", "finish": "clean"},
    )

    correction = compile_correction_prompt(
        package.to_dict(),
        observed_deviations=[
            "the model made her blonde",
            "the model gave her rounded human ears",
            "the markings read like tattoos",
        ],
    )

    instruction_lower = correction["instruction"].lower()
    assert "correct only the listed identity drift" in instruction_lower
    assert "restore black twin ponytails" in instruction_lower
    assert "restore elongated sun sprite elf ears" in instruction_lower
    assert "replace tattoo language with light-circuitry markings (not tattoos)" in instruction_lower
    assert "preserve unchanged approved context" in instruction_lower
    assert "shot type: portrait" in instruction_lower
    assert "medium: cinematic render" in instruction_lower

    negative_lower = correction["negativePrompt"].lower()
    assert "blonde hair" in negative_lower
    assert "blue eyes" in negative_lower
    assert "human ears" in negative_lower

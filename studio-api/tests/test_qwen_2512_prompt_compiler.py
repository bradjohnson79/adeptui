"""Qwen-Image-2512 structured prompt compiler tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.image_prompting.qwen_2512 import BLOCK_ORDER, compile_character_image_prompt


def _korri_canon() -> dict:
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "config" / "character-canon" / "korri.v1.json").read_text(encoding="utf-8"))


def test_compile_korri_prompt_package_stable_order():
    package = compile_character_image_prompt(
        _korri_canon(),
        prompt_goal="a cinematic hero portrait",
        composition={
            "shot_type": "hero portrait",
            "framing": "medium full shot",
            "camera_angle": "eye level",
            "lens": "50mm",
            "environment": "soft forest edge",
            "lighting": "warm diffuse daylight",
            "pose": "hands on hips, teasing head tilt",
        },
        style_profile={
            "medium": "cinematic digital illustration",
            "palette": "muted woodland neutrals with violet accents",
            "finish": "clean polished render",
        },
        references=[{"reference_role": "hero_identity"}, {"reference_role": "closeup_front"}],
        sheet_request={"enabled": True, "views": ["front", "side_left", "back_closeup"]},
    )

    assert [block.key for block in package.blocks] == list(BLOCK_ORDER)
    assert [block.index for block in package.blocks] == list(range(1, 14))
    assert package.metadata["blockCount"] == 13
    assert package.validation["ok"] is True

    prompt_lower = package.prompt.lower()
    assert "black twin ponytails" in prompt_lower
    assert "purple eyes" in prompt_lower
    assert "pale skin" in prompt_lower
    assert "elongated sun sprite elf ears" in prompt_lower
    assert "light-circuitry markings (not tattoos)" in prompt_lower

    assert "medium: cinematic digital illustration" in package.block_map["style_profile"]
    assert "camera language" not in package.block_map["style_profile"].lower()
    assert "front->full_body_front" in package.block_map["character_sheet"]
    assert "back_closeup->closeup_back" in package.block_map["character_sheet"]

    negative_lower = package.negative_prompt.lower()
    assert "blonde hair" in negative_lower
    assert "blue eyes" in negative_lower
    assert "human ears" in negative_lower
    assert "anadriya resemblance" in negative_lower

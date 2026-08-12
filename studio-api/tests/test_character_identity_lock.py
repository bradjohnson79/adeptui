"""Korri identity lock tests for Qwen-Image-2512."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.image_prompting.qwen_2512 import (
    build_identity_lock,
    compile_character_image_prompt,
    detect_identity_violations,
    extract_character_blueprint,
)


def _korri_canon() -> dict:
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "config" / "character-canon" / "korri.v1.json").read_text(encoding="utf-8"))


def test_korri_identity_lock_contains_required_and_forbidden_traits():
    blueprint = extract_character_blueprint(_korri_canon())
    lock = build_identity_lock(blueprint)

    assert lock["is_korri"] is True
    assert "pale skin" in lock["locked_traits"]
    assert "purple eyes" in lock["locked_traits"]
    assert "black twin ponytails" in lock["locked_traits"]
    assert "elongated Sun Sprite Elf ears" in lock["locked_traits"]
    assert "light-circuitry markings (not tattoos)" in lock["locked_traits"]

    assert "blonde hair" in lock["forbidden_traits"]
    assert "blue eyes" in lock["forbidden_traits"]
    assert "human ears" in lock["forbidden_traits"]
    assert "Anadriya resemblance" in lock["forbidden_traits"]


def test_identity_violation_detector_flags_drift_and_accepts_positive_blocks():
    package = compile_character_image_prompt(_korri_canon(), prompt_goal="a close character portrait")
    positive_only = "\n".join(
        block.text for block in package.blocks if block.key != "negative_constraints"
    )
    safe_findings = detect_identity_violations(positive_only, package.identity_lock)
    assert safe_findings == []

    bad_text = (
        "Korri with blonde hair, blue eyes, human ears, and tattoo ink replacing her markings, "
        "styled like Anadriya."
    )
    findings = detect_identity_violations(bad_text, package.identity_lock)
    assert "forbidden trait present: blonde hair" in findings
    assert "forbidden trait present: blue eyes" in findings
    assert "forbidden trait present: human ears" in findings
    assert "forbidden trait present: Anadriya resemblance" in findings
    assert "incorrect markings language: use light-circuitry markings (not tattoos)" in findings

"""Official Kie id is bound before strengthen_kie_character_sheet_prompt.

Regression for UnboundLocalError in queue_worker._imagegen_kie
(cannot access local variable 'official').
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.hosted_providers.adapters.kie_adapter import (
    kie_image_model_id_for_dock,
    resolve_official_kie_image_model,
    strengthen_kie_character_sheet_prompt,
)


# Existing official Market map — do not invent ids.
_OFFICIAL_CASES = (
    ("nano-banana-kie", "nano-banana-2"),
    ("nano-banana-2", "nano-banana-2"),
    ("gpt-image-2-kie", "gpt-image-2-text-to-image"),
    ("gpt-image-2-text-to-image", "gpt-image-2-text-to-image"),
    ("gpt-image-2-image-to-image", "gpt-image-2-image-to-image"),
    ("seedream-kie", "seedream/5-pro-text-to-image"),
    ("seedream/5-pro-text-to-image", "seedream/5-pro-text-to-image"),
    ("seedream/5-pro-image-to-image", "seedream/5-pro-image-to-image"),
)


@pytest.mark.parametrize("model_id,expected", _OFFICIAL_CASES)
def test_resolve_official_kie_image_model_existing_map(model_id: str, expected: str) -> None:
    official = resolve_official_kie_image_model(model_id, {"kieImageModelId": model_id})
    assert official == expected
    text = strengthen_kie_character_sheet_prompt("a person", model=official)
    assert "professional four-panel character turnaround sheet" in text


def test_resolve_official_prefers_params_kie_image_model_id() -> None:
    official = resolve_official_kie_image_model(
        "nano-banana-kie",
        {"kieImageModelId": "nano-banana-2"},
    )
    assert official == "nano-banana-2"
    official = resolve_official_kie_image_model(
        "gpt-image-2-kie",
        {"kie_image_model_id": "gpt-image-2-text-to-image"},
    )
    assert official == "gpt-image-2-text-to-image"


def test_resolve_official_i2i_uses_existing_map() -> None:
    assert (
        resolve_official_kie_image_model("gpt-image-2-kie", image_to_image=True)
        == "gpt-image-2-image-to-image"
    )
    assert (
        resolve_official_kie_image_model("seedream-kie", image_to_image=True)
        == "seedream/5-pro-image-to-image"
    )
    assert resolve_official_kie_image_model("nano-banana-kie", image_to_image=True) == "nano-banana-2"


def test_imagegen_kie_assigns_official_before_strengthener() -> None:
    """Thin extract of assignment order in _imagegen_kie. Prevents UnboundLocalError."""
    src = (Path(__file__).resolve().parents[1] / "app" / "queue_worker.py").read_text(encoding="utf-8")
    start = src.index("async def _imagegen_kie")
    end = src.index("async def _imagegen_fal", start)
    body = src[start:end]
    official_at = body.index("official =")
    strengthen_at = body.index("strengthen_kie_character_sheet_prompt(prompt, model=official)")
    assert official_at < strengthen_at
    assert "resolve_official_kie_image_model" in body


def test_official_helper_matches_dock_map() -> None:
    assert kie_image_model_id_for_dock("nano-banana-kie") == "nano-banana-2"
    assert kie_image_model_id_for_dock("gpt-image-2-kie") == "gpt-image-2-text-to-image"
    assert kie_image_model_id_for_dock("seedream-kie") == "seedream/5-pro-text-to-image"
    for dock, expected in (
        ("nano-banana-kie", "nano-banana-2"),
        ("gpt-image-2-kie", "gpt-image-2-text-to-image"),
        ("seedream-kie", "seedream/5-pro-text-to-image"),
    ):
        assert resolve_official_kie_image_model(dock) == expected

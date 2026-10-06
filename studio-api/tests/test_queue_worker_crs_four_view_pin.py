"""Pin: worker must not four-view-strengthen CRS law-view singles.

CRS_GENERATION jobs share imageIntent.purpose=character_sheet with hosted
four-panel sheets. Evaluating imageIntent in isolation used to inject
FOUR_VIEW_SHEET_PROMPT (turnaround / four-panel) onto Qwen law-view tiles.
"""

from __future__ import annotations

from pathlib import Path

from app.character_identity.four_view_sheet import (
    FOUR_VIEW_SHEET_PROMPT,
    apply_job_four_view_prompt,
    is_single_image_four_view,
    strengthen_four_view_prompt,
)
from app.image_product.compile import prompt_purpose_for_expand
from app.image_product.prompt_intel import expand_prompt


FORBIDDEN_WORKER_TOKENS = (
    "four-panel",
    "four-view",
    "turnaround",
    "character sheet layout",
    "character turnaround sheet",
)


def _crs_job_params() -> dict:
    return {
        "taskType": "CRS_GENERATION",
        "purpose": "character_sheet",
        "presetId": "builtin-character-sheet",
        "fourViewSingleOutput": False,
        "layout": "crs_view",
        "viewRole": "full_body_side_left",
        "prompt": "PROFILE_GUIDED one camera side-profile of Korri, one person only",
        "imageIntent": {
            "purpose": "character_sheet",
            "prompt": "PROFILE_GUIDED one camera side-profile of Korri, one person only",
        },
        "creativeContext": {
            "taskType": "CRS_GENERATION",
            "fourViewSingleOutput": False,
            "layout": "law_views",
            "objective": "character_sheet",
        },
    }


def test_is_single_image_four_view_false_for_crs_law_view_job():
    params = _crs_job_params()
    assert is_single_image_four_view(params) is False
    assert is_single_image_four_view({
        "taskType": "CRS_GENERATION",
        "purpose": "character_sheet",
        "fourViewSingleOutput": False,
    }) is False
    assert is_single_image_four_view({
        "purpose": "character_sheet",
        "layout": "law_views",
    }) is False
    assert is_single_image_four_view({
        "purpose": "character_sheet",
        "sheet_layout": "crs_view",
    }) is False
    assert is_single_image_four_view({
        "taskType": "crs_single_view",
        "purpose": "character_sheet",
    }) is False


def test_hosted_four_panel_still_detects_purpose_character_sheet():
    assert is_single_image_four_view({"purpose": "character_sheet"}) is True
    assert is_single_image_four_view({
        "purpose": "character_sheet",
        "layout": "four_view",
        "fourViewSingleOutput": True,
    }) is True


def test_worker_does_not_strengthen_crs_law_view_when_imageintent_says_character_sheet():
    """Proven hole: is_single_image_four_view(imageIntent) was True and ORed in."""
    params = _crs_job_params()
    intent_block = params["imageIntent"]
    # Isolated imageIntent still looks like a hosted sheet -- that is why
    # the worker must not OR it.
    assert is_single_image_four_view(intent_block) is True

    seed = "PROFILE_GUIDED one camera side-profile of Korri, one person only"
    out_params, out_prompt, applied = apply_job_four_view_prompt(
        params, seed, family="qwen2512", ers_purpose="character_sheet"
    )
    assert applied is False
    assert out_prompt == seed
    low = out_prompt.lower()
    for token in FORBIDDEN_WORKER_TOKENS:
        assert token not in low
    assert FOUR_VIEW_SHEET_PROMPT not in out_prompt
    assert out_params.get("fourViewSingleOutput") is False
    assert out_params.get("layout") != "four_view"


def test_strengthen_four_view_prompt_skipped_for_crs_job():
    params = _crs_job_params()
    seed = params["prompt"]
    _, out, applied = apply_job_four_view_prompt(params, seed)
    assert applied is False
    # Direct strengthen still has four-view language (hosted path). Worker skip
    # is what prevents it from landing on CRS law views.
    raw = strengthen_four_view_prompt(seed)
    assert "four-panel" in raw.lower()
    assert "four-panel" not in out.lower()
    assert "turnaround" not in out.lower()


def test_hosted_four_panel_path_keeps_four_view_language():
    params = {
        "purpose": "character_sheet",
        "layout": "four_view",
        "fourViewSingleOutput": True,
    }
    _, out, applied = apply_job_four_view_prompt(params, "Korri in black cloth")
    assert applied is True
    assert FOUR_VIEW_SHEET_PROMPT in out
    assert "four-panel" in out.lower()


def test_compile_expand_still_omits_purpose_character_sheet_on_law_views():
    leftover = {
        "taskType": "CRS_GENERATION",
        "purpose": "character_sheet",
        "layout": "law_views",
        "fourViewSingleOutput": False,
        "creativeContext": {"taskType": "CRS_GENERATION", "layout": "law_views"},
    }
    purpose = prompt_purpose_for_expand(leftover, "character_sheet")
    assert purpose == ""
    expanded = expand_prompt("compiled single-camera prompt", purpose=purpose)["expandedPrompt"]
    assert "character sheet" not in expanded.lower()
    assert "purpose: character sheet" not in expanded.lower()


def test_queue_worker_no_longer_ors_stripped_imageintent():
    src = Path(__file__).resolve().parents[1].joinpath("app", "queue_worker.py").read_text(encoding="utf-8")
    assert "apply_job_four_view_prompt" in src
    assert "is_single_image_four_view(intent_block" not in src
    assert "is_single_image_four_view(\n            intent.metadata" not in src

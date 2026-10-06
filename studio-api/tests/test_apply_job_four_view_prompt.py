"""Worker four-view strengthen must not rewrite Character Angles or CRS singles."""

from app.character_identity.four_view_sheet import (
    FOUR_VIEW_SHEET_PROMPT,
    apply_job_four_view_prompt,
    is_single_image_four_view,
)


def test_hosted_four_panel_still_strengthens():
    params = {
        "purpose": "character_sheet",
        "layout": "four_view",
        "fourViewSingleOutput": True,
    }
    _, out, applied = apply_job_four_view_prompt(params, "Korri in black cloth")
    assert applied is True
    assert FOUR_VIEW_SHEET_PROMPT in out


def test_crs_law_view_not_strengthened():
    params = {
        "taskType": "CRS_GENERATION",
        "purpose": "character_sheet",
        "fourViewSingleOutput": False,
        "layout": "crs_view",
        "viewRole": "full_body_side_left",
        "prompt": "one camera side-profile",
        "imageIntent": {"purpose": "character_sheet", "prompt": "one camera side-profile"},
    }
    assert is_single_image_four_view(params) is False
    _, out, applied = apply_job_four_view_prompt(params, params["prompt"])
    assert applied is False
    assert "four-panel" not in out.lower()


def test_cc_v3_angles_not_strengthened():
    params = {
        "purpose": "character_sheet",
        "presetId": "builtin-character-sheet",
        "sheet_layout": "cc_v2",
        "ccV3": True,
        "taskType": "CC_V3_MULTIVIEW",
        "viewRole": "SIDE",
        "role": "SIDE",
        "cameraRole": "SIDE",
    }
    _, out, applied = apply_job_four_view_prompt(params, "Show this exact same person as one full-body right-side profile")
    assert applied is False
    assert "four-panel" not in out.lower()
    assert "turnaround" not in out.lower()

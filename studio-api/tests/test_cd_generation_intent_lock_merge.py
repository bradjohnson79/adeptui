"""Co-Director generationIntent lock-merge: user locks beat Bible/CD suggestions."""

from __future__ import annotations

from app.codirector.production_intent.generation_intent import (
    LOCKED_CREATIVE_FIELDS,
    apply_generation_intent_to_body,
    compile_and_apply_generation_intent,
    extract_user_locked_creative,
    merge_generation_intent,
)
from app.image_product.compile import build_creative_context
from app.image_studio.contracts import CinematicControls, CinematicGenerateRequest, cinematic_to_image_product_body


def test_locked_fields_constant() -> None:
    assert LOCKED_CREATIVE_FIELDS == ("visualStyle", "lighting", "colorGrade", "camera")


def test_extract_locks_from_cis_body_shape() -> None:
    body = cinematic_to_image_product_body(
        CinematicGenerateRequest(
            prompt="hero in alley",
            projectId="proj-lock",
            controls=CinematicControls(
                visualStyle="anime",
                lighting="neon",
                colorGradePreset="teal_orange",
                lens="85",
                shotIntent="close_up",
                category="general",
            ),
            spatialCameraId="cam-1",
        )
    )
    locks = extract_user_locked_creative(body)
    assert locks["visualStyle"] == "anime"
    assert locks["lighting"]["setup"] == "neon"
    assert locks["lighting"]["presetId"] == "neon"
    assert locks["colorGrade"] == "teal_orange"
    assert locks["camera"]["lens"] == "85"
    assert locks["camera"]["shotIntent"] == "close_up"
    assert locks["camera"]["spatialCameraId"] == "cam-1"


def test_merge_precedence_user_lock_beats_bible_and_cd() -> None:
    merged = merge_generation_intent(
        locked={
            "visualStyle": "live_action",
            "lighting": {"setup": "golden_hour", "presetId": "golden_hour"},
            "colorGrade": "natural",
            "camera": {"lens": "35", "shotIntent": "medium"},
        },
        cd_suggestions={
            "visualStyle": "anime",
            "lighting": {"setup": "horror", "presetId": "horror"},
            "colorGrade": "teal_orange",
            "camera": {"lens": "18", "shotIntent": "wide"},
        },
        bible_suggestions={
            "visualStyle": "comic_book",
            "lighting": {"setup": "moonlight", "presetId": "moonlight"},
            "colorGrade": "epic_blockbuster",
            "camera": {"lens": "50", "shotIntent": "close_up"},
        },
    )
    assert merged["visualStyle"] == "live_action"
    assert merged["lighting"]["setup"] == "golden_hour"
    assert merged["colorGrade"] == "natural"
    assert merged["camera"]["lens"] == "35"
    assert merged["camera"]["shotIntent"] == "medium"
    assert set(merged["lockPrecedence"]["lockedFields"]) == {
        "visualStyle",
        "lighting",
        "colorGrade",
        "camera",
    }


def test_merge_fills_gaps_from_cd_then_bible() -> None:
    merged = merge_generation_intent(
        locked={"visualStyle": "live_action"},
        cd_suggestions={"lighting": {"setup": "neon", "presetId": "neon"}},
        bible_suggestions={
            "visualStyle": "anime",  # must NOT clobber lock
            "colorGrade": "teal_orange",
            "camera": {"lens": "50"},
        },
    )
    assert merged["visualStyle"] == "live_action"
    assert merged["lighting"]["setup"] == "neon"
    assert merged["colorGrade"] == "teal_orange"
    assert merged["camera"]["lens"] == "50"
    assert merged["lockPrecedence"]["filledFromCd"] == ["lighting"]
    assert "colorGrade" in merged["lockPrecedence"]["filledFromBible"]
    assert "camera" in merged["lockPrecedence"]["filledFromBible"]


def test_apply_stamps_body_without_touching_workflow() -> None:
    body = {
        "prompt": "test",
        "creativeContext": {"workflowKey": "qwen2512.ref", "objective": "image_generate"},
        "forceWorkflowKey": "qwen2512.ref",
    }
    intent = merge_generation_intent(
        locked={"visualStyle": "anime", "lighting": {"setup": "neon", "presetId": "neon"}},
        cd_suggestions={},
        bible_suggestions={},
    )
    apply_generation_intent_to_body(body, intent)
    assert body["visualStyle"] == "anime"
    assert body["creativeContext"]["visualStyle"] == "anime"
    assert body["creativeContext"]["lighting"]["presetId"] == "neon"
    assert body["cinematic"]["lighting"] == "neon"
    assert body["generationIntent"]["visualStyle"] == "anime"
    # Strategy A fields untouched
    assert body["forceWorkflowKey"] == "qwen2512.ref"
    assert body["creativeContext"]["workflowKey"] == "qwen2512.ref"


def test_compile_and_apply_preserves_cis_locks_over_cd_visual_style() -> None:
    body = {
        "prompt": "locked style scene",
        "visualStyle": "live_action",
        "creativeContext": {
            "visualStyle": "live_action",
            "lighting": {"setup": "golden_hour", "presetId": "golden_hour"},
            "visualLanguage": {"colorGradePreset": "natural"},
            "cinematography": {"lens": "35", "shotIntent": "medium"},
        },
        "cinematic": {
            "visualStyle": "live_action",
            "lighting": "golden_hour",
            "colorGradePreset": "natural",
            "lens": "35",
            "shotIntent": "medium",
        },
    }
    intent = compile_and_apply_generation_intent(
        body,
        project_id="proj-no-bible",
        visual_style="anime",  # CD suggestion — must not clobber lock
        include_bible=False,
    )
    assert intent["visualStyle"] == "live_action"
    assert body["creativeContext"]["visualStyle"] == "live_action"
    assert body["creativeContext"]["lighting"]["setup"] == "golden_hour"
    assert body["generationIntent"]["lockPrecedence"]["lockedFields"]


def test_build_creative_context_preserves_visual_style_extra() -> None:
    ctx = build_creative_context(
        "proj-style",
        extras={
            "visualStyle": "anime",
            "lighting": {"setup": "neon", "presetId": "neon"},
            "colorGrade": "teal_orange",
        },
    )
    assert ctx.get("visualStyle") == "anime"
    assert ctx.get("lighting", {}).get("setup") == "neon"
    assert ctx.get("colorGrade") == "teal_orange"

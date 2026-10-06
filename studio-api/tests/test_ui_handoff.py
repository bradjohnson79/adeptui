from types import SimpleNamespace

from app.codirector.execution.ui_handoff import is_ui_handoff, lift_ui_handoff
from app.codirector.service import _apply_phase3_navigate_intent, _NAVIGATE_TARGET_TO_TOOL
from app.codirector.routing.unified_intent import DispatchStrategy, UnifiedIntentKind


def test_lift_ui_handoff_surfaces_nested_audio_studio_action() -> None:
    enveloped = {
        "status": "success",
        "summary": "audio.open_studio completed successfully.",
        "toolId": "audio.open_studio",
        "projectId": "beffd3d8-791d-4adf-9c4d-681ec9d4efb0",
        "data": {
            "ok": True,
            "uiAction": "open_audio_studio",
            "audioTab": "music",
            "workspaceUrl": "/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=audiostudio&audioTab=music",
            "projectId": "beffd3d8-791d-4adf-9c4d-681ec9d4efb0",
        },
    }
    lifted = lift_ui_handoff(enveloped)
    assert lifted["uiAction"] == "open_audio_studio"
    assert lifted["workspaceUrl"].endswith("workspace=audiostudio&audioTab=music")
    assert is_ui_handoff(enveloped) is True
    assert is_ui_handoff({"toolId": "audio.open_studio"}) is True
    assert is_ui_handoff({"toolId": "timeline.focus_ui"}) is False


def test_phase3_navigate_sets_audio_open_execution() -> None:
    decision = SimpleNamespace(
        target="audiostudio",
        targetWorkspace="audiostudio",
        capabilityAvailable=True,
    )
    intent = _apply_phase3_navigate_intent(decision, None)
    assert intent is not None
    assert intent.intent == UnifiedIntentKind.EXECUTION
    assert intent.capability == "audio.open"
    assert intent.dispatch == DispatchStrategy.DETERMINISTIC
    assert "audio.open_studio" in intent.curated_tool_ids


def test_navigate_map_includes_audiostudio() -> None:
    assert _NAVIGATE_TARGET_TO_TOOL["audiostudio"] == "audio.open_studio"


def test_navigate_map_includes_image_generator() -> None:
    assert _NAVIGATE_TARGET_TO_TOOL["imagegen"] == "workspace.open_image_generator"
    assert _NAVIGATE_TARGET_TO_TOOL["environment_creator"] == "workspace.open_scene_creator"


def test_lift_ui_handoff_surfaces_image_generator_action() -> None:
    enveloped = {
        "status": "success",
        "summary": "workspace.open_image_generator completed successfully.",
        "toolId": "workspace.open_image_generator",
        "data": {
            "ok": True,
            "uiAction": "open_image_generator",
            "workspace": "imagegen",
            "contentTab": "imagegen",
            "workspaceUrl": "/project/proj-1?workspace=imagegen",
            "projectId": "proj-1",
        },
    }
    lifted = lift_ui_handoff(enveloped)
    assert lifted["uiAction"] == "open_image_generator"
    assert lifted["contentTab"] == "imagegen"
    assert lifted["workspace"] == "imagegen"
    assert is_ui_handoff(enveloped) is True
    assert is_ui_handoff({"toolId": "workspace.open_image_generator"}) is True


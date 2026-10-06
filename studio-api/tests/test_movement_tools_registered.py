from app.codirector.tools.definitions import TOOL_IDS
from app.codirector.tools.registry import _MUTATION_HANDLERS, _READ_HANDLERS


def test_movement_tools_are_bound() -> None:
    for tool_id in (
        "spatial.save",
        "spatial.commit_map",
        "spatial.create_movement",
        "spatial.update_movement",
        "spatial.activate_movement",
        "spatial.delete_movement",
        "scene_creator_mini.create_take",
        "spatial.plan_movements",
        "workspace.open_scene_creator",
    ):
        assert tool_id in TOOL_IDS
        assert tool_id in _READ_HANDLERS or tool_id in _MUTATION_HANDLERS


def test_prompt_segment_declares_direction_fields() -> None:
    from app.codirector.tools.definitions import TOOL_DEFINITIONS

    tool = next(t for t in TOOL_DEFINITIONS if t.tool_id == "timeline.propose_add_prompt_segment")
    names = {p.name for p in tool.parameters}
    assert {"userDirection", "productionPrompt", "dialogue", "movementSegmentId"} <= names


def test_v11_open_image_generator_is_bound() -> None:
    for tool_id in (
        "workspace.open_scene_creator",
        "workspace.open_image_generator",
    ):
        assert tool_id in TOOL_IDS
        assert tool_id in _READ_HANDLERS


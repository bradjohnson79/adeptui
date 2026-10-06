"""Adept UI v1.1 Co-Director Spatial Map shelf + Environment Creator routing."""

from app.codirector.routing.atlas_intent import atlas_capability_for_message
from app.codirector.routing.contracts import RouteActionClass
from app.codirector.routing.deterministic import classify_deterministic
from app.codirector.routing.v11_spatial_shelf import (
    classify_v11_spatial_shelf_intent,
    environment_creator_content_tab,
    spatial_map_shelved_reply,
)
from app.codirector.tools.definitions import TOOL_IDS
from app.codirector.tools.exposure import expose
from app.codirector.tools.registry import _READ_HANDLERS


def test_a_spatial_map_ask_not_active():
    assert classify_v11_spatial_shelf_intent("open Spatial Map") == "spatial_map_shelved"
    decision = classify_deterministic("Please open the Spatial Map")
    assert decision is not None
    assert decision.actionClass == RouteActionClass.DISCUSS
    assert decision.target == "spatial_map.shelved_v1_1"
    reply = spatial_map_shelved_reply("open Spatial Map")
    assert "not active" in reply.lower()
    assert atlas_capability_for_message("create a spatial map") == ""


def test_b_create_environment_to_express():
    assert classify_v11_spatial_shelf_intent("create a mess hall environment") == "open_environment_creator"
    decision = classify_deterministic("create a mess hall environment")
    assert decision is not None
    assert decision.actionClass == RouteActionClass.NAVIGATE
    assert decision.target == "environment_creator"
    assert environment_creator_content_tab() == "scene_creator"
    assert "workspace.open_scene_creator" in TOOL_IDS
    assert "workspace.open_scene_creator" in _READ_HANDLERS


def test_c_scene_standard_path_still_reachable():
    # Scene shot generation must not be stolen by the Spatial Map shelf gate.
    assert classify_v11_spatial_shelf_intent("generate four scene stills") == ""
    decision = classify_deterministic("generate four shots from the ERS")
    assert decision is not None
    # Either scene.generate target or execute production — must not be spatial shelved
    assert decision.target != "spatial_map.shelved_v1_1"
    assert decision.target != "environment_creator"


def test_spatial_tools_dormant_not_deleted_and_not_exposed():
    assert "spatial.create_map" in TOOL_IDS
    exposed = expose(workspace_surface="chat", intent="create a spatial map")
    assert "spatial.create_map" not in exposed

"""Lighting layer assembly from SceneState + light avatars."""

from __future__ import annotations

from app.spatial_prompt_builder import assemble_prompt_layers, build_lighting_layer
from app.spatial_scene import CameraSpec, PromptLayers, SceneAvatar, SceneState, SpatialSceneDoc


def test_lighting_layer_from_state_and_light_avatars():
    char = SceneAvatar(
        id="char-1",
        label="Hitchhiker",
        initials="HH",
        entity_type="character",
        x=400,
        y=350,
    )
    cam = SceneAvatar(
        id="cam-1",
        label="A Cam",
        initials="CA",
        entity_type="camera",
        shape="camera",
        x=200,
        y=350,
        camera=CameraSpec(lens_mm=35, fov_deg=45, movement="dolly_in"),
    )
    key = SceneAvatar(
        id="light-1",
        label="Key",
        initials="KY",
        entity_type="light",
        shape="light",
        x=500,
        y=200,
        spatial_prompt="warm golden-hour key from camera left",
    )
    fill = SceneAvatar(
        id="light-2",
        label="Fill",
        initials="FL",
        entity_type="light",
        shape="light",
        x=600,
        y=400,
        spatial_prompt="soft cool fill opposite key",
    )
    state = SceneState(
        id="state-a",
        name="State A",
        camera_id=cam.id,
        lighting="Cinematic golden-hour side light along the highway.",
    )
    doc = SpatialSceneDoc(
        background_asset_id="bg-equirect",
        avatars=[char, cam, key, fill],
        states=[state],
        active_state_id=state.id,
        notes="Rural highway roadside",
    )

    lighting = build_lighting_layer(doc, state_id=state.id)
    assert "Cinematic golden-hour side light" in lighting
    assert "Key: warm golden-hour key" in lighting
    assert "Fill: soft cool fill" in lighting

    layers = assemble_prompt_layers(doc, state_id=state.id)
    assert layers.lighting == lighting
    assert "dolly_in" in layers.camera or "dolly_in" in layers.spatial
    assert "FOV 45" in layers.camera


def test_lighting_layer_skipped_when_manually_set():
    light = SceneAvatar(
        id="light-1",
        label="Key",
        entity_type="light",
        shape="light",
        spatial_prompt="should not overwrite",
    )
    state = SceneState(id="s1", lighting="auto lighting")
    doc = SpatialSceneDoc(
        avatars=[light],
        states=[state],
        active_state_id=state.id,
        prompt_layers=PromptLayers(lighting="Manual lighting override"),
    )
    layers = assemble_prompt_layers(doc)
    assert layers.lighting == "Manual lighting override"

from app.spatial_map.movement import create_inherited_movement, hydrate_movement_segments
from app.spatial_map.movement_compile import compile_generation_layers, layers_as_provider_text, parse_movement_alias
from app.spatial_map.schemas import MovementCreateBody, SpatialCharacterPlacement, SpatialMapDocument


def test_compile_layers_keep_unchanged_and_changed_separate() -> None:
    document = SpatialMapDocument(
        projectId="p1",
        characters=[
            SpatialCharacterPlacement(
                id="c1",
                characterId="korri",
                label="Korri",
                normalizedX=-0.4,
                normalizedY=0.2,
            )
        ],
    )
    hydrate_movement_segments(document)
    create_inherited_movement(document, MovementCreateBody(userDirection="Korri walks to the table."))
    document.characters[0].normalizedX = 0.6
    from app.spatial_map.movement import write_through_active

    write_through_active(document)
    layers = compile_generation_layers(document, document.movementSegments[1], timed_prompt="hold on her face")
    text = layers_as_provider_text(layers)
    assert "UNCHANGED FACTS" in text
    assert "STARTING STATE" in text
    assert "ENDING STATE" in text
    assert "ACTION / DIRECTION" in text
    assert "woman walks to table" not in text.lower()
    assert parse_movement_alias("~M2") == 2
    assert "Korri moved" in (layers.get("transition") or {}).get("changed", [])

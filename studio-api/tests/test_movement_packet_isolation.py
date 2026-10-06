from app.spatial_map.camera_shot_packet import compile_camera_shot_packet
from app.spatial_map.movement import create_inherited_movement, hydrate_movement_segments, write_through_active
from app.spatial_map.schemas import MovementCreateBody, SpatialCamera, SpatialCharacterPlacement, SpatialMapDocument


def test_m1_and_m2_packets_use_their_own_positions() -> None:
    document = SpatialMapDocument(
        projectId="p1",
        characters=[
            SpatialCharacterPlacement(
                id="c1",
                characterId="korri",
                label="Korri",
                normalizedX=-0.4,
                normalizedY=0.2,
                gridRow=3,
                gridColumn=2,
            )
        ],
        cameras=[SpatialCamera(id="cam-1", label="C1", cameraSlot=0)],
    )
    hydrate_movement_segments(document)
    m1 = document.movementSegments[0]
    create_inherited_movement(document, MovementCreateBody(userDirection="Korri walks to the table."))
    document.characters[0].normalizedX = 0.7
    write_through_active(document)
    m2 = document.movementSegments[1]
    camera = document.cameras[0]
    packet_m1 = compile_camera_shot_packet(None, "p1", document, camera, movement_segment=m1)
    packet_m2 = compile_camera_shot_packet(None, "p1", document, camera, movement_segment=m2)
    x1 = next(c.normalizedX for c in packet_m1.characters)
    x2 = next(c.normalizedX for c in packet_m2.characters)
    assert x1 == -0.4
    assert x2 == 0.7
    assert packet_m2.sceneIntent.action.startswith("Korri walks")
    assert packet_m1.sceneIntent.action == "" or "walks" not in packet_m1.sceneIntent.action

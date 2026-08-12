"""M4.8–M4.9 Wave 1 contract + continuity + storyboard document tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.image_studio.contracts import (
    CinematicControls,
    CinematicGenerateRequest,
    cinematic_to_image_product_body,
)
from app.image_studio.continuity import (
    approve_image,
    create_session,
    get_session,
    inherit_from_scene,
    list_sessions,
    session_to_creative_extras,
)
from app.storyboard_studio.script_sync import map_legacy_panel_sync, unify_status
from app.storyboard_studio.documents import ensure_document, reorder_panels, set_page_size
from app.storyboard_studio.timeline_prep import prepare_timeline_from_storyboard


@pytest.fixture()
def project_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    from app import config as cfg

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(cfg.settings, "data_dir", data)
    return "proj-m48-test"


def test_visual_continuity_session_roundtrip(project_id: str) -> None:
    s = create_session(
        project_id,
        scene_id="scene-1",
        character_ids=["char-a"],
        location_ids=["loc-1"],
        costume_ids=["cos-1"],
        reference_asset_ids=["ref-1"],
        lighting_direction="key left",
        color_treatment="teal-orange",
        lens_language="35mm anamorphic",
        aspect_ratio="2.39:1",
    )
    assert s.id
    assert s.projectId == project_id
    assert s.characterIds == ["char-a"]
    loaded = get_session(project_id, s.id)
    assert loaded is not None
    assert loaded.lensLanguage == "35mm anamorphic"
    updated = approve_image(project_id, s.id, "asset-99")
    assert updated is not None
    assert "asset-99" in updated.approvedImageIds
    assert len(list_sessions(project_id)) == 1


def test_inherit_from_scene_creates_session(project_id: str) -> None:
    s = inherit_from_scene(project_id, "scene-xyz")
    assert s.sceneId == "scene-xyz"
    again = inherit_from_scene(project_id, "scene-xyz")
    assert again.id == s.id


def test_cinematic_maps_to_image_product_body(project_id: str) -> None:
    req = CinematicGenerateRequest(
        prompt="wide establishing dusk alley",
        projectId=project_id,
        mode="best_match",
        batchSize=2,
        resolution="2K",
        controls=CinematicControls(
            lens="35mm",
            lighting="motivated neon",
            colorTreatment="noir",
            aspectRatio="16:9",
            shotIntent="establishing",
            category="storyboard",
        ),
        continuitySessionId="cont-1",
        sceneId="scene-1",
        inheritContinuityFromScene=True,
        spatialMapId="map-1",
        spatialMapVersion="2026-08-01T20:00:00Z",
        spatialCameraId="cam-hero",
    )
    body = cinematic_to_image_product_body(req)
    assert body["prompt"] == "wide establishing dusk alley"
    assert body["continuitySessionId"] == "cont-1"
    assert body["generationMode"] == "best_match"
    assert body["cinematic"]["lens"] == "35mm"
    assert body["creativeContext"]["continuitySessionId"] == "cont-1"
    assert body["batchSize"] == 2
    assert body["spatialMapId"] == "map-1"
    assert body["spatialMapVersion"] == "2026-08-01T20:00:00Z"
    assert body["spatialCameraId"] == "cam-hero"


def test_session_creative_extras_shape(project_id: str) -> None:
    s = create_session(project_id, scene_id="s1", reference_asset_ids=["r1"])
    extras = session_to_creative_extras(s)
    assert extras["continuitySessionId"] == s.id
    assert extras["continuity"]["sessionId"] == s.id
    assert isinstance(extras["approvedReferences"], list)


def test_script_sync_unification() -> None:
    assert map_legacy_panel_sync("ok") == "linked"
    assert map_legacy_panel_sync("script_changed") == "script_updated"
    assert unify_status(panel_sync="ok", has_segment_link=True) == "linked"
    assert unify_status(panel_sync="script_changed") == "script_updated"
    assert unify_status(creator_override=True) == "override"
    assert unify_status(scene_sync="conflict") == "conflict"
    assert unify_status() == "unlinked"


def test_storyboard_document_pages(project_id: str) -> None:
    doc = ensure_document(project_id, page_size=9)
    assert doc.pageSize == 9
    assert doc.pages
    order = [f"p{i}" for i in range(12)]
    doc2 = reorder_panels(project_id, doc.id, order)
    assert doc2 is not None
    assert len(doc2.panelOrder) == 12
    assert len(doc2.pages) == 2  # 9 + 3
    doc3 = set_page_size(project_id, doc.id, 6)
    assert doc3 is not None
    assert doc3.pageSize == 6
    assert len(doc3.pages) == 2  # 6 + 6


def test_timeline_prep_is_proposal_only(project_id: str) -> None:
    ensure_document(project_id)
    proposal = prepare_timeline_from_storyboard(project_id, approved_only=False)
    assert proposal.status == "draft"
    assert "silent" in proposal.note.lower() or "proposal" in proposal.note.lower()
    path = Path(__file__).resolve()
    assert path.exists()


def test_continuity_persists_under_data_dir(project_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import config as cfg

    data = tmp_path / "data"
    monkeypatch.setattr(cfg.settings, "data_dir", data)
    s = create_session(project_id, scene_id="persist")
    disk = data / "visual_continuity" / project_id / "sessions.json"
    assert disk.is_file()
    raw = json.loads(disk.read_text(encoding="utf-8"))
    assert raw[0]["id"] == s.id

"""Phase 5D remediation: CDX-030 atlas routing-prefix stripping + CDX-037 sheet identity.

- CDX-030: the Co-Director chat atlas path forwards the ENTIRE user message as the
  execution prompt; the atlas handler must strip the capability routing phrase
  ("create an atlas shot of ...") from the fallback description before it becomes
  the canonical SceneIntent summary (which is baked into the atlas prompt, the
  ERS prompt, and the semantic-gate text).
- CDX-037 (backend half): _pick_sheet must prefer the sheet bound to the active
  spatial map (sheet.spatialMap.mapId == map_id) before falling back to the
  sceneId match and then newest-with-composite. The frontend now passes
  sheetId + spatialMapId (5C), so the backend must pick the map\'s own sheet,
  not a sibling sheet from another map that is merely newer or shares the scene id.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.codirector.capabilities.handlers import atlas_generate
from app.environment_reference_sheet import orchestrator, store
from app.environment_reference_sheet.contracts import SpatialMapReference
from app.scene_creator.production_handoff import _pick_sheet, synchronize_production_handoff


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(name: str = "Handoff Identity") -> str:
    from app.db import Project, SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name=name))
        db.commit()
        return project_id
    finally:
        db.close()


def _make_map(db, project_id: str, *, title: str, scene_id: str):
    from app.spatial_map.schemas import SpatialMapCreateBody
    from app.spatial_map.service import create_document

    return create_document(db, project_id, SpatialMapCreateBody(title=title, sceneId=scene_id))


def _make_sheet(project_id: str, *, name: str, scene_id: str, map_id: str | None, updated_at: str):
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name=name,
        description=f"{name}: the location used by the handoff identity test.",
        scene_id=scene_id,
    )
    sheet.sheetId = str(uuid.uuid4())
    sheet.spatialMap = (
        SpatialMapReference(mapId=map_id, sceneId=scene_id, northLockDirection="north") if map_id else None
    )
    sheet.ers_composite_asset_id = f"composite-{name}"
    sheet.status = "registered"
    sheet.updatedAt = updated_at
    store.save_sheet(sheet)
    return sheet


class _FakeDb:
    """Minimal stand-in for the atlas handler: only db.get(Project, id) is used."""

    def get(self, model, project_id):
        return SimpleNamespace(name="Test Project")


def _patch_enqueue(monkeypatch, captured: list[dict]) -> None:
    class _Job:
        def __init__(self) -> None:
            self.id = "job-atlas-cdx030"

    def _fake(db, project_id, body, scene_id=None):
        captured.append(dict(body))
        return _Job()

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake)


# ── CDX-030: the routing prefix never becomes the SceneIntent summary ─────


def test_atlas_fallback_summary_strips_routing_prefix(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    atlas_generate.handle(
        db=_FakeDb(),
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="create an atlas shot of a warm neighborhood coffee shop",
    )
    assert captured
    body = captured[0]
    intent = body["creativeContext"]["sceneIntent"]
    assert intent["summary"] == "a warm neighborhood coffee shop"
    assert "create an atlas shot" not in intent["summary"].lower()
    # Provenance field keeps the full originating request; summary stays clean.
    assert intent["sourcePromptSummary"] == "create an atlas shot of a warm neighborhood coffee shop"


def test_atlas_fallback_summary_strips_make_an_atlas_of(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    atlas_generate.handle(
        db=_FakeDb(),
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="make an atlas of the courtyard garden",
    )
    assert captured
    intent = captured[0]["creativeContext"]["sceneIntent"]
    assert intent["summary"] == "the courtyard garden"
    assert "make an atlas" not in intent["summary"].lower()


def test_strip_atlas_routing_prefix_variants() -> None:
    cases = {
        "create an atlas shot of the courtyard": "the courtyard",
        "generate an atlas shot of the warehouse": "the warehouse",
        "make an atlas of the coffee shop": "the coffee shop",
        "render an atlas of the old mill": "the old mill",
        "build an atlas shot showing the main hall": "the main hall",
        "create a roofless shot of the courtyard": "the courtyard",
        "roofless view of the harbor": "the harbor",
        "A neighborhood coffee shop.": "A neighborhood coffee shop.",
        "Atlas of the city streets": "Atlas of the city streets",
        "": "",
    }
    for raw, expected in cases.items():
        assert atlas_generate.strip_atlas_routing_prefix(raw) == expected, raw


# ── CDX-037: _pick_sheet prefers the active map\'s sheet ──────────────────


def test_pick_sheet_prefers_active_map_match() -> None:
    project_id = f"proj-{uuid.uuid4()}"
    scene_id = "scene-x"
    sheet_a = _make_sheet(
        project_id, name="Sheet A", scene_id=scene_id, map_id="map-a", updated_at="2026-08-10T09:00:00Z"
    )
    _make_sheet(
        project_id, name="Sheet B", scene_id=scene_id, map_id="map-b", updated_at="2026-08-14T18:07:10Z"
    )
    picked = _pick_sheet(project_id, scene_id=scene_id, map_id="map-a")
    assert picked.sheetId == sheet_a.sheetId


def test_pick_sheet_no_map_match_uses_scene_id_then_newest() -> None:
    project_id = f"proj-{uuid.uuid4()}"
    scene_id = "scene-x"
    _make_sheet(
        project_id, name="Older", scene_id=scene_id, map_id="map-b", updated_at="2026-08-10T09:00:00Z"
    )
    newer = _make_sheet(
        project_id, name="Newer", scene_id=scene_id, map_id="map-b", updated_at="2026-08-14T18:07:10Z"
    )
    picked = _pick_sheet(project_id, scene_id=scene_id, map_id="map-nowhere")
    assert picked.sheetId == newer.sheetId


def test_synchronize_from_map_a_picks_sheet_a_not_sheet_b() -> None:
    project_id = _create_project("Map Identity")
    db = _session()
    try:
        from app.scene_creator.service import ensure_scene_id

        scene = ensure_scene_id(db, project_id, "")
        map_a = _make_map(db, project_id, title="Map A", scene_id=scene.id)
        map_b = _make_map(db, project_id, title="Map B", scene_id=scene.id)
        # sheet_b is NEWER and shares the sceneId: the old sceneId/newest
        # fallback would pick sheet_b. The map match must pick sheet_a.
        sheet_a = _make_sheet(
            project_id,
            name="Sheet A",
            scene_id=scene.id,
            map_id=map_a.id,
            updated_at="2026-08-10T09:00:00Z",
        )
        _make_sheet(
            project_id,
            name="Sheet B",
            scene_id=scene.id,
            map_id=map_b.id,
            updated_at="2026-08-14T18:07:10Z",
        )
        result = synchronize_production_handoff(db, project_id, spatial_map_id=map_a.id)
        assert result["sheetId"] == sheet_a.sheetId
        assert result["spatialMapId"] == map_a.id
    finally:
        db.close()


def test_synchronize_no_map_match_falls_back_to_scene_id_newest() -> None:
    project_id = _create_project("No Map Match")
    db = _session()
    try:
        from app.scene_creator.service import ensure_scene_id

        scene = ensure_scene_id(db, project_id, "")
        map_a = _make_map(db, project_id, title="Map A", scene_id=scene.id)
        map_b = _make_map(db, project_id, title="Map B", scene_id=scene.id)
        # Neither sheet is bound to map_a: the map branch must be a no-op and
        # the sceneId/newest behavior must stay unchanged.
        _make_sheet(
            project_id,
            name="Sheet A",
            scene_id=scene.id,
            map_id=map_b.id,
            updated_at="2026-08-10T09:00:00Z",
        )
        sheet_b = _make_sheet(
            project_id,
            name="Sheet B",
            scene_id=scene.id,
            map_id=map_b.id,
            updated_at="2026-08-14T18:07:10Z",
        )
        result = synchronize_production_handoff(db, project_id, spatial_map_id=map_a.id)
        assert result["sheetId"] == sheet_b.sheetId
    finally:
        db.close()

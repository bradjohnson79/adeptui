"""CDX-024 / CDX-021 — corrupt document_json quarantine + atlas reuse.

Defect (CDX-024): a stored Spatial Map whose `document_json` fails to parse or
validate was silently replaced with a blank document; the next write then
overwrote the raw row — permanent placement loss.

Required outcome:
  * corrupt stored JSON surfaces a typed DOCUMENT_CORRUPT error (never a silent
    blank document);
  * the raw row is never overwritten by a write path (quarantine);
  * regenerating an atlas after Remove keeps placements at the API level
    (CDX-021) — the flow the frontend now uses (reuse, never orphan).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest
from fastapi import HTTPException

from app.db import Project, SessionLocal, init_db
from app.spatial_map.models import SpatialMapDocumentRow
from app.spatial_map.schemas import (
    SpatialCharacterPlacementBody,
    SpatialMapUpdateBody,
)
from app.spatial_map.service import (
    get_document,
    list_documents,
    place_character,
    update_document,
)


def _session():
    init_db()
    return SessionLocal()


def _create_project(name: str = "Spatial Quarantine Test") -> str:
    db = _session()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name=name))
        db.commit()
        return project_id
    finally:
        db.close()


def _insert_row(project_id: str, document_json: str, doc_id: str | None = None) -> str:
    db = _session()
    try:
        doc_id = doc_id or str(uuid.uuid4())
        row = db.get(SpatialMapDocumentRow, doc_id)
        if row is None:
            row = SpatialMapDocumentRow(
                id=doc_id,
                project_id=project_id,
                title="Corrupt Map",
                document_json=document_json,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(row)
        else:
            # Corrupt an existing row (e.g. one created through the API) by
            # replacing its stored document_json with broken data.
            row.document_json = document_json
            row.title = "Corrupt Map"
        db.commit()
        return doc_id
    finally:
        db.close()


def _raw_row(doc_id: str) -> str:
    db = _session()
    try:
        return db.get(SpatialMapDocumentRow, doc_id).document_json
    finally:
        db.close()


CORRUPT_JSON = '{"id": "x", "projectId": "y", "characters": [not-json!!'


def test_corrupt_json_get_document_raises_typed_error_and_preserves_row() -> None:
    project_id = _create_project()
    doc_id = _insert_row(project_id, CORRUPT_JSON)
    db = _session()
    try:
        with pytest.raises(HTTPException) as exc_info:
            get_document(db, project_id, doc_id)
        assert exc_info.value.status_code == 500
        detail = exc_info.value.detail
        assert detail["code"] == "DOCUMENT_CORRUPT"
        assert detail["documentId"] == doc_id
        assert "NOT modified" in detail["message"]
    finally:
        db.close()
    # Quarantine: the raw row is untouched (never replaced by a blank doc).
    assert _raw_row(doc_id) == CORRUPT_JSON


def test_non_object_json_raises_typed_error() -> None:
    project_id = _create_project()
    doc_id = _insert_row(project_id, json.dumps([1, 2, 3]))
    db = _session()
    try:
        with pytest.raises(HTTPException) as exc_info:
            get_document(db, project_id, doc_id)
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail["code"] == "DOCUMENT_CORRUPT"
    finally:
        db.close()


def test_validation_failure_raises_typed_error() -> None:
    # Valid JSON that fails Pydantic validation (characters must be a list).
    project_id = _create_project()
    bad = json.dumps({"characters": "not-a-list", "projectId": project_id})
    doc_id = _insert_row(project_id, bad)
    db = _session()
    try:
        with pytest.raises(HTTPException) as exc_info:
            get_document(db, project_id, doc_id)
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail["code"] == "DOCUMENT_CORRUPT"
        assert "validation" in exc_info.value.detail["reason"]
    finally:
        db.close()
    assert _raw_row(doc_id) == bad


def test_write_paths_never_overwrite_corrupt_row() -> None:
    """Any write on a corrupt row must fail before mutating, never blank it."""
    project_id = _create_project()
    doc_id = _insert_row(project_id, CORRUPT_JSON)
    db = _session()
    try:
        with pytest.raises(HTTPException) as exc_info:
            update_document(db, project_id, doc_id, SpatialMapUpdateBody(notes="stamp"))
        assert exc_info.value.detail["code"] == "DOCUMENT_CORRUPT"
        with pytest.raises(HTTPException) as exc_info2:
            place_character(
                db,
                project_id,
                doc_id,
                SpatialCharacterPlacementBody(characterId="char-1", label="Hero", x=1.0, z=-1.0),
            )
        assert exc_info2.value.detail["code"] == "DOCUMENT_CORRUPT"
    finally:
        db.close()
    assert _raw_row(doc_id) == CORRUPT_JSON


def test_corrupt_row_breaks_list_with_typed_error() -> None:
    """A corrupt row is never silently dropped from the project map list."""
    project_id = _create_project()
    _insert_row(project_id, CORRUPT_JSON)
    db = _session()
    try:
        with pytest.raises(HTTPException) as exc_info:
            list_documents(db, project_id)
        assert exc_info.value.detail["code"] == "DOCUMENT_CORRUPT"
    finally:
        db.close()


def test_corrupt_map_api_get_returns_typed_error(client) -> None:
    res = client.post("/api/projects", json={"name": "Corrupt API"})
    assert res.status_code == 200
    project_id = res.json()["id"]
    create = client.post(f"/api/spatial-map/projects/{project_id}/maps", json={"title": "Stage"})
    assert create.status_code == 200
    document_id = create.json()["document"]["id"]
    _insert_row(project_id, CORRUPT_JSON, doc_id=document_id)

    got = client.get(f"/api/spatial-map/projects/{project_id}/maps/{document_id}")
    assert got.status_code == 500
    assert got.json()["detail"]["code"] == "DOCUMENT_CORRUPT"
    patched = client.patch(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}",
        json={"notes": "stamp"},
    )
    assert patched.status_code == 500
    assert patched.json()["detail"]["code"] == "DOCUMENT_CORRUPT"
    assert _raw_row(document_id) == CORRUPT_JSON


def _seed_character(project_id: str, character_id: str) -> None:
    """CDX-013: placements must reference a project-owned CharacterProfileRow."""
    from app.character_identity.models import CharacterProfileRow

    db = _session()
    try:
        existing = db.get(CharacterProfileRow, character_id)
        if existing is not None:
            db.delete(existing)
            db.commit()
        db.add(CharacterProfileRow(id=character_id, project_id=project_id, name=character_id))
        db.commit()
    finally:
        db.close()


def test_regenerate_after_remove_keeps_placements(client) -> None:
    """CDX-021 API guard: Remove Atlas then set a new Atlas reuses the same
    document — placements must survive (never orphaned into a new map)."""
    res = client.post("/api/projects", json={"name": "Atlas Reuse"})
    assert res.status_code == 200
    project_id = res.json()["id"]
    _seed_character(project_id, "char-1")

    create = client.post(
        f"/api/spatial-map/projects/{project_id}/maps",
        json={"title": "Stage", "backgroundAssetId": "atlas-1"},
    )
    assert create.status_code == 200
    document_id = create.json()["document"]["id"]

    placed = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
        json={"characterId": "char-1", "label": "Hero", "x": 2.0, "z": -2.0},
    )
    assert placed.status_code == 200
    placement_id = placed.json()["document"]["characters"][0]["id"]

    removed = client.patch(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}",
        json={"backgroundAssetId": None},
    )
    assert removed.status_code == 200
    assert removed.json()["document"]["backgroundAssetId"] is None
    assert len(removed.json()["document"]["characters"]) == 1

    regenerated = client.patch(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}",
        json={"backgroundAssetId": "atlas-2"},
    )
    assert regenerated.status_code == 200
    doc = regenerated.json()["document"]
    assert doc["id"] == document_id
    assert doc["backgroundAssetId"] == "atlas-2"
    assert len(doc["characters"]) == 1
    assert doc["characters"][0]["id"] == placement_id
    assert doc["characters"][0]["characterId"] == "char-1"

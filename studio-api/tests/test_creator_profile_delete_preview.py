"""Creator profile delete-preview + delete endpoints for Character, Prop, Environment."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import Asset, Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags
from app.scene_references.models import SceneReferenceBinding


def _apply_flags_in_place(environ: dict[str, str] | None = None) -> None:
    """Mutate the process singleton in place (modules import feature_flags by value)."""
    from dataclasses import fields as dataclass_fields

    import app.feature_flags as ff

    refreshed = FeatureFlags.from_env(environ if environ is not None else {})
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))


@pytest.fixture()
def enable_m33(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    _apply_flags_in_place(dict(os.environ))
    yield
    _apply_flags_in_place(dict(os.environ))


@pytest.fixture()
def project_id(enable_m33):
    init_db()
    from app.character_identity import ensure_character_identity_tables

    ensure_character_identity_tables()
    pid = f"del-{uuid.uuid4().hex[:10]}"
    session = SessionLocal()
    session.merge(Project(id=pid, name="Delete Preview Test"))
    session.commit()
    session.close()
    return pid


def _create_project(name: str = "Delete Preview Test") -> str:
    init_db()
    db = SessionLocal()
    try:
        pid = str(uuid.uuid4())
        db.add(Project(id=pid, name=name))
        db.commit()
        return pid
    finally:
        db.close()


def test_character_local_delete_preview_returns_local(client: TestClient, project_id: str):
    created = client.post(
        f"/api/projects/{project_id}/characters",
        json={"name": "Local Delete Preview", "role": "lead", "description": "A test character."},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["id"]

    preview = client.get(f"/api/projects/{project_id}/characters/{cid}/delete-preview")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["entityType"] == "character"
    assert body["entityId"] == cid
    assert body["isGlobal"] is False
    assert body["usageCount"] == 0
    assert body["projectCount"] == 0
    assert body["libraryAssetsKept"] is True
    assert body["canDelete"] is True
    assert body["blockReason"] is None


def test_character_global_delete_preview_returns_global(client: TestClient, project_id: str):
    created = client.post(
        f"/api/projects/{project_id}/characters",
        json={"name": "Global Delete Preview", "role": "support", "description": "A global test character."},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["id"]

    patch = client.patch(
        f"/api/projects/{project_id}/characters/{cid}",
        json={"is_global": True},
    )
    assert patch.status_code == 200, patch.text

    preview = client.get(f"/api/projects/{project_id}/characters/{cid}/delete-preview")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["entityType"] == "character"
    assert body["isGlobal"] is True


def test_prop_delete_preview_returns_library_assets_kept(client: TestClient):
    project_id = _create_project("Prop Delete Preview")
    created = client.post(
        f"/api/prop-creator/projects/{project_id}/props",
        json={"name": "Preview Prop", "description": "A prop to delete."},
    )
    assert created.status_code == 200, created.text
    prop_id = created.json()["prop"]["id"]

    preview = client.get(f"/api/prop-creator/projects/{project_id}/props/{prop_id}/delete-preview")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["entityType"] == "prop"
    assert body["libraryAssetsKept"] is True
    assert body["canDelete"] is True


def test_environment_delete_preview_returns_environment_entity(client: TestClient):
    project_id = _create_project("ERS Delete Preview")
    created = client.post(
        f"/api/environment-reference-sheets/projects/{project_id}/save",
        json={"name": "Preview Environment", "description": "An environment to preview delete."},
    )
    assert created.status_code == 200, created.text
    sheet_id = created.json()["sheet"]["sheetId"]

    preview = client.get(f"/api/environment-reference-sheets/projects/{project_id}/{sheet_id}/delete-preview")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["entityType"] == "environment"
    assert body["libraryAssetsKept"] is True
    assert body["canDelete"] is True


def test_global_character_cross_project_binding_blocks_delete(client: TestClient, project_id: str):
    created = client.post(
        f"/api/projects/{project_id}/characters",
        json={"name": "Global Bound Character", "role": "lead", "description": "Bound elsewhere."},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["id"]

    patch = client.patch(
        f"/api/projects/{project_id}/characters/{cid}",
        json={"is_global": True},
    )
    assert patch.status_code == 200, patch.text

    other_id = _create_project("Other Project")
    db = SessionLocal()
    try:
        asset = Asset(
            id=f"asset-{uuid.uuid4().hex[:8]}",
            project_id=other_id,
            tag="reference",
            kind="image",
            filename="ref.png",
            path="ref.png",
        )
        db.add(asset)
        binding = SceneReferenceBinding(
            id=str(uuid.uuid4()),
            project_id=other_id,
            asset_id=asset.id,
            scope_type="scene",
            scope_id=str(uuid.uuid4()),
            reference_type="character",
            identity_id=cid,
            alias="Global Bound Character",
        )
        db.add(binding)
        db.commit()
    finally:
        db.close()

    preview = client.get(f"/api/projects/{project_id}/characters/{cid}/delete-preview")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["isGlobal"] is True
    assert body["usageCount"] >= 1
    assert body["projectCount"] >= 1

    delete = client.delete(f"/api/projects/{project_id}/characters/{cid}")
    assert delete.status_code == 409


def test_environment_delete_with_confirmation_clears_canonical_and_keeps_assets(client: TestClient):
    project_id = _create_project("ERS Delete Confirmed")
    created = client.post(
        f"/api/environment-reference-sheets/projects/{project_id}/save",
        json={"name": "Delete Confirmed Environment", "description": "An environment to delete."},
    )
    assert created.status_code == 200, created.text
    sheet_id = created.json()["sheet"]["sheetId"]

    from app.environment_reference_sheet.store import set_canonical_sheet_id

    db = SessionLocal()
    try:
        set_canonical_sheet_id(project_id, sheet_id)
        assert set_canonical_sheet_id(project_id, sheet_id) is not None
    finally:
        db.close()

    delete = client.delete(
        f"/api/environment-reference-sheets/projects/{project_id}/{sheet_id}?confirm_cross_project=true"
    )
    assert delete.status_code == 200, delete.text
    body = delete.json()
    assert body["deleted"] is True
    assert body["sheet_id"] == sheet_id
    assert body["library_assets_kept"] is True

    from app.environment_reference_sheet.store import get_canonical_sheet_id

    db = SessionLocal()
    try:
        assert get_canonical_sheet_id(project_id) is None
    finally:
        db.close()

    preview_after = client.get(f"/api/environment-reference-sheets/projects/{project_id}/{sheet_id}/delete-preview")
    assert preview_after.status_code == 404

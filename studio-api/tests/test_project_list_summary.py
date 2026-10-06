"""Home project list is a card summary, not the full Library."""

from __future__ import annotations

import uuid

import pytest

from app.routers.api import _project_list_out, _project_out


@pytest.fixture()
def db_session():
    from app.db import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def project(db_session):
    from app.db import Project

    row = Project(id=str(uuid.uuid4()), name="List summary project")
    db_session.add(row)
    db_session.commit()
    return row


def test_list_payload_omits_scenes_assets_and_spatial_map(db_session, project):
    from app.db import Asset, Scene

    db_session.add(
        Scene(
            id="scene-list-1",
            project_id=project.id,
            name="Heavy scene",
            prompt="x" * 200,
            index=0,
        )
    )
    db_session.add(
        Asset(
            id="asset-list-1",
            project_id=project.id,
            filename="cover.png",
            kind="image",
            path="cover.png",
        )
    )
    project.spatial_map_json = '{"rooms":[' + ('{"id":1},' * 50) + "{}]}"
    db_session.commit()

    full = _project_out(db_session, project)
    card = _project_list_out(db_session, project)
    assert len(full.scenes) == 1
    assert len(full.assets) == 1
    assert full.spatial_map_json.startswith('{"rooms"')
    assert card.scenes == []
    assert card.assets == []
    assert card.spatial_map_json == "{}"
    assert card.scene_count == 1
    assert card.asset_count == 1
    assert card.id == project.id
    assert card.name == project.name


def test_list_projects_http_returns_empty_library_arrays(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    for row in resp.json():
        assert row.get("scenes") == []
        assert row.get("assets") == []
        assert row.get("spatial_map_json") in {"{}", "", None}

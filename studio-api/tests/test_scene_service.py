"""Slice 1: projects & scenes.

Exercises the real vertical slice — HTTP route → `SceneService` → SQLite → reload in a fresh
session — because that round trip is what lets `project.scenes.*` claim `locally_verified` in
the capability registry. Mock-only coverage would not qualify.
"""

from __future__ import annotations

import pytest


def _create_project(client, name: str = "Scene Slice Project") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


# --------------------------------------------------------------------------
# service layer
# --------------------------------------------------------------------------


def test_create_assigns_contiguous_indices_and_persists_summary(client) -> None:
    from app.services.scene_service import SceneService

    project_id = _create_project(client)
    db = _session()
    try:
        first = SceneService.create(
            db, project_id, {"name": "Arrival", "summary": "Ada steps off the train.", "prompt": "wide shot"}
        )
        second = SceneService.create(db, project_id, {"name": "Departure"})
        # A project is created with one scene already, so the new scenes continue from index 1.
        assert [scene.index for scene in SceneService.list_for_project(db, project_id)] == [0, 1, 2]
        assert first.summary == "Ada steps off the train."
        assert second.name == "Departure"
    finally:
        db.close()


def test_create_defaults_name_from_position(client) -> None:
    from app.services.scene_service import SceneService

    project_id = _create_project(client)
    db = _session()
    try:
        scene = SceneService.create(db, project_id, {"name": ""})
        assert scene.name == f"Scene {scene.index + 1}"
    finally:
        db.close()


def test_update_is_partial_and_does_not_clobber_unsent_fields(client) -> None:
    """The old router dumped the whole request model, so a rename blanked the prompt."""
    from app.services.scene_service import SceneService

    project_id = _create_project(client)
    db = _session()
    try:
        scene = SceneService.create(
            db, project_id, {"name": "Before", "prompt": "neon alley, rain", "duration_sec": 7.5}
        )
        SceneService.update(db, project_id, scene.id, {"name": "After"})
        reloaded = SceneService.get(db, project_id, scene.id)
        assert reloaded.name == "After"
        assert reloaded.prompt == "neon alley, rain"
        assert reloaded.duration_sec == 7.5
    finally:
        db.close()


def test_update_rejects_unknown_or_read_only_fields(client) -> None:
    from app.capabilities.errors import VALIDATION_ERROR, CapabilityError
    from app.services.scene_service import SceneService

    project_id = _create_project(client)
    db = _session()
    try:
        scene = SceneService.create(db, project_id, {"name": "Guarded"})
        with pytest.raises(CapabilityError) as err:
            SceneService.update(db, project_id, scene.id, {"index": 99})
        assert err.value.code == VALIDATION_ERROR
    finally:
        db.close()


def test_delete_repacks_indices(client) -> None:
    from app.services.scene_service import SceneService

    project_id = _create_project(client)
    db = _session()
    try:
        SceneService.create(db, project_id, {"name": "B"})
        middle = SceneService.create(db, project_id, {"name": "C"})
        SceneService.create(db, project_id, {"name": "D"})
        SceneService.delete(db, project_id, middle.id)
        scenes = SceneService.list_for_project(db, project_id)
        assert [scene.index for scene in scenes] == list(range(len(scenes)))
        assert "C" not in [scene.name for scene in scenes]
    finally:
        db.close()


def test_scene_ids_are_not_reachable_across_projects(client) -> None:
    from app.capabilities.errors import SCENE_NOT_FOUND, CapabilityError
    from app.services.scene_service import SceneService

    first_project = _create_project(client, "Project One")
    second_project = _create_project(client, "Project Two")
    db = _session()
    try:
        scene = SceneService.create(db, first_project, {"name": "Private"})
        with pytest.raises(CapabilityError) as err:
            SceneService.get(db, second_project, scene.id)
        assert err.value.code == SCENE_NOT_FOUND
    finally:
        db.close()


def test_missing_project_raises_project_not_found() -> None:
    from app.capabilities.errors import PROJECT_NOT_FOUND, CapabilityError
    from app.services.scene_service import SceneService

    db = _session()
    try:
        with pytest.raises(CapabilityError) as err:
            SceneService.create(db, "does-not-exist", {"name": "Orphan"})
        assert err.value.code == PROJECT_NOT_FOUND
    finally:
        db.close()


def test_create_many_replaces_and_keeps_indices_contiguous(client) -> None:
    from app.services.scene_service import SceneService

    project_id = _create_project(client)
    db = _session()
    try:
        created = SceneService.create_many(
            db,
            project_id,
            [{"name": "One"}, {"name": "Two"}, {"name": "Three"}],
            replace_existing=True,
        )
        assert [scene.index for scene in created] == [0, 1, 2]
        assert [scene.name for scene in SceneService.list_for_project(db, project_id)] == [
            "One",
            "Two",
            "Three",
        ]
    finally:
        db.close()


def test_summary_or_prompt_falls_back_and_clips() -> None:
    from app.db import Scene
    from app.services.scene_service import scene_summary_or_prompt

    with_summary = Scene(id="a", project_id="p", summary="A quiet reunion.", prompt="ignored")
    assert scene_summary_or_prompt(with_summary) == "A quiet reunion."

    long_prompt = Scene(id="b", project_id="p", summary="", prompt="x" * 400)
    clipped = scene_summary_or_prompt(long_prompt, limit=40)
    assert clipped is not None and len(clipped) == 40

    empty = Scene(id="c", project_id="p", summary="", prompt="")
    assert scene_summary_or_prompt(empty) is None


# --------------------------------------------------------------------------
# HTTP surface + reload
# --------------------------------------------------------------------------


def test_scene_crud_over_http_survives_reload(client) -> None:
    project_id = _create_project(client)

    created = client.post(
        f"/api/projects/{project_id}/scenes",
        json={"name": "Rooftop", "summary": "Ada confronts the courier.", "prompt": "dusk, wide"},
    )
    assert created.status_code == 200
    scene = created.json()
    assert scene["summary"] == "Ada confronts the courier."

    listed = client.get(f"/api/projects/{project_id}/scenes")
    assert listed.status_code == 200
    assert [item["index"] for item in listed.json()] == list(range(len(listed.json())))

    fetched = client.get(f"/api/projects/{project_id}/scenes/{scene['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["summary"] == "Ada confronts the courier."

    patched = client.patch(
        f"/api/projects/{project_id}/scenes/{scene['id']}",
        json={"summary": "Ada lets the courier go."},
    )
    assert patched.status_code == 200
    assert patched.json()["summary"] == "Ada lets the courier go."
    # The prompt was not part of the PATCH body and must survive it.
    assert patched.json()["prompt"] == "dusk, wide"

    # Reload through the project payload, which is what the Director workspace reads.
    reloaded = client.get(f"/api/projects/{project_id}")
    assert reloaded.status_code == 200
    persisted = next(item for item in reloaded.json()["scenes"] if item["id"] == scene["id"])
    assert persisted["summary"] == "Ada lets the courier go."
    assert persisted["prompt"] == "dusk, wide"

    deleted = client.delete(f"/api/projects/{project_id}/scenes/{scene['id']}")
    assert deleted.status_code == 200
    after = client.get(f"/api/projects/{project_id}/scenes")
    assert scene["id"] not in [item["id"] for item in after.json()]
    assert [item["index"] for item in after.json()] == list(range(len(after.json())))


def test_missing_scene_returns_structured_404(client) -> None:
    project_id = _create_project(client)
    res = client.get(f"/api/projects/{project_id}/scenes/nope")
    assert res.status_code == 404
    detail = res.json()["detail"]
    assert detail["code"] == "SCENE_NOT_FOUND"
    assert detail["message"] == "Scene not found"
    assert detail["recommendedAction"]


def test_missing_project_returns_structured_404(client) -> None:
    res = client.get("/api/projects/does-not-exist/scenes")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "PROJECT_NOT_FOUND"

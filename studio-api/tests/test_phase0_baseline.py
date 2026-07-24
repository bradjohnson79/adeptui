from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

from sqlalchemy import inspect


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_project.json"


def _sample_project() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_sqlite_initialization_is_isolated(isolated_data_dir: Path) -> None:
    from app.config import settings
    from app.db import engine, init_db

    assert settings.data_dir.resolve() == isolated_data_dir
    assert Path(engine.url.database or "").resolve() == isolated_data_dir / "studio.db"

    init_db()

    assert (isolated_data_dir / "studio.db").is_file()
    tables = set(inspect(engine).get_table_names())
    assert {"projects", "scenes", "assets", "jobs"}.issubset(tables)


def test_api_health_and_startup(client, monkeypatch, isolated_data_dir: Path) -> None:
    from app.routers import api

    monkeypatch.setattr(api.comfy, "health", AsyncMock(return_value={"status": "ok"}))
    monkeypatch.setattr(api, "Path", lambda _: isolated_data_dir / "missing-models")

    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["health"] == "/api/health"

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert health.json()["comfy_reachable"] is True


def test_project_scene_job_and_library_contracts(client, monkeypatch) -> None:
    from app import vram_profiles
    from app.routers import api

    sample = _sample_project()
    monkeypatch.setattr(vram_profiles, "detect_vram_gb", lambda: None)
    monkeypatch.setattr(
        api.comfy,
        "upload_file_copy",
        AsyncMock(return_value="sample_project.json"),
    )

    created = client.post("/api/projects", json=sample["create"])
    assert created.status_code == 200
    project = created.json()
    project_id = project["id"]
    assert project["name"] == sample["create"]["name"]
    assert len(project["scenes"]) == 1

    opened = client.get(f"/api/projects/{project_id}")
    assert opened.status_code == 200
    assert opened.json()["id"] == project_id

    saved = client.patch(f"/api/projects/{project_id}", json=sample["save"])
    assert saved.status_code == 200
    assert saved.json()["name"] == sample["save"]["name"]
    assert saved.json()["description"] == sample["save"]["description"]

    scene_response = client.post(
        f"/api/projects/{project_id}/scenes",
        json=sample["scene"],
    )
    assert scene_response.status_code == 200
    scene = scene_response.json()
    assert scene["project_id"] == project_id
    assert scene["name"] == sample["scene"]["name"]
    assert scene["index"] == 1

    job_response = client.post(
        f"/api/projects/{project_id}/render",
        json={"kind": "scene", "scene_id": scene["id"]},
    )
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["project_id"] == project_id
    assert job["scene_id"] == scene["id"]
    assert job["kind"] == "render_scene"
    assert job["status"] == "queued"

    jobs = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs.status_code == 200
    assert any(item["id"] == job["id"] for item in jobs.json())

    uploaded = client.post(
        f"/api/projects/{project_id}/assets",
        files={
            "file": (
                "sample_project.json",
                FIXTURE_PATH.read_bytes(),
                "application/json",
            )
        },
        data={"tag": "baseline_fixture", "kind": "document"},
    )
    assert uploaded.status_code == 200
    asset = uploaded.json()

    library = client.get(f"/api/projects/{project_id}/library")
    assert library.status_code == 200
    assert [item["id"] for item in library.json()] == [asset["id"]]
    assert library.json()[0]["tag"] == "baseline_fixture"

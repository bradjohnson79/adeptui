"""Phase 3: unified inspect bridge covers Studio queue jobs."""

from __future__ import annotations

import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import Job, Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags


@pytest.fixture()
def unified_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1", "1")
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    init_db()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_codirector_inspects_studio_job(unified_client: TestClient) -> None:
    project_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(Project(id=project_id, name="Unified jobs test"))
        db.add(
            Job(
                id=job_id,
                project_id=project_id,
                kind="video_generate",
                status="running",
                stage="retrieving",
                progress=0.0,
                params_json=json.dumps({"modelId": "demo/model", "api_key": "must-not-leak"}),
                history_json=json.dumps({"falRequestId": "req-123", "provider": "fal"}),
            )
        )
        db.commit()
    finally:
        db.close()

    response = unified_client.get(
        f"/api/codirector/jobs/{job_id}", params={"projectId": project_id}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "studio"
    assert body["job"]["job_id"] == job_id
    assert body["job"]["status"] == "retrieving"
    assert body["job"]["progress_mode"] == "state"
    assert body["job"]["provider_request_id"] == "req-123"
    assert "api_key" not in json.dumps(body)

    history = unified_client.get(f"/api/codirector/jobs/{job_id}/history")
    assert history.status_code == 200, history.text
    assert any(event["eventType"] == "falRequestId" for event in history.json()["events"])

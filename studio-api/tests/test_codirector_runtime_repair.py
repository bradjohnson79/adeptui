from __future__ import annotations

import json
import os
import uuid
from dataclasses import fields as dataclass_fields

import pytest

from app import feature_flags as ff
from app.codirector.m211.decisions import DecisionRecordStore
from app.codirector.plans.service import PlanService
from app.codirector.tools import registry as tool_registry
from app.db import CoDirectorProductionPlan, ProductionContextExtension, ProductionContextRow, SessionLocal
from app.feature_flags import FeatureFlags


@pytest.fixture()
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    refreshed = FeatureFlags.from_env(os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))
    yield


def _create_project(client, name: str = "Runtime Repair") -> dict:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200, res.text
    return res.json()


def _audited(client, project_id: str, tool_id: str, arguments: dict | None = None, request_id: str | None = None):
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/audited",
        json={
            "toolId": tool_id,
            "arguments": arguments or {},
            "requestId": request_id or str(uuid.uuid4()),
        },
    )


def _propose(client, project_id: str, tool_id: str, arguments: dict):
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": tool_id, "arguments": arguments, "requestId": str(uuid.uuid4()), "createdBy": "user"},
    )


def _approve(client, project_id: str, proposal_id: str):
    return client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/approve", json={})


def _save_conversation(client, project_id: str, messages: list[dict]) -> dict:
    res = client.post(
        f"/api/codirector/conversations/{project_id}",
        json={"messages": messages, "model": None, "provider_id": None},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_create_project_requires_trimmed_name(client):
    blank = client.post("/api/projects", json={"name": "   "})
    assert blank.status_code == 422, blank.text
    assert "Project name is required." in blank.text

    missing = client.post("/api/projects", json={})
    assert missing.status_code == 422, missing.text

    explicit_untitled = client.post("/api/projects", json={"name": "  Untitled Project  "})
    assert explicit_untitled.status_code == 200, explicit_untitled.text
    assert explicit_untitled.json()["name"] == "Untitled Project"


def test_active_plan_lookup_returns_typed_empty_for_new_project(client):
    project = _create_project(client, "Fresh Project")
    res = client.get(f"/api/codirector/projects/{project['id']}/plans/active")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body == {"ok": True, "status": "not_created", "plan": None}


def test_active_plan_lookup_returns_plan_and_plan_route_rejects_project_id(client, mock_provider_env):
    project = _create_project(client, "Plan Project")
    created = _audited(
        client,
        project["id"],
        "production_plan.create_draft",
        {
            "title": "Dreamweaver Setup",
            "objective": "Prepare the project",
            "stepsJson": json.dumps([{"stepId": "s1", "title": "Define title", "category": "director"}]),
            "requestId": str(uuid.uuid4()),
        },
    )
    assert created.status_code == 200, created.text
    plan = created.json()["result"]["plan"]

    active = client.get(f"/api/codirector/projects/{project['id']}/plans/active")
    assert active.status_code == 200, active.text
    assert active.json()["plan"]["planId"] == plan["planId"]

    fetched = client.get(f"/api/codirector/projects/{project['id']}/plans/{plan['planId']}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["plan"]["planId"] == plan["planId"]

    wrong = client.get(f"/api/codirector/projects/{project['id']}/plans/{project['id']}")
    assert wrong.status_code == 404, wrong.text
    assert wrong.json()["detail"]["code"] == "PLAN_NOT_FOUND"


def test_record_production_decision_is_registered_persists_and_updates_title(client):
    assert tool_registry.find("record_production_decision") is not None
    project = _create_project(client, "Untitled Project")
    proposed = _propose(
        client,
        project["id"],
        "record_production_decision",
        {
            "decision": "Project title confirmed as The Dreamweaver.",
            "rationale": "The creator picked the final title during setup.",
            "projectTitle": "The Dreamweaver",
        },
    )
    assert proposed.status_code == 200, proposed.text
    receipt = _approve(client, project["id"], proposed.json()["id"])
    assert receipt.status_code == 200, receipt.text
    body = receipt.json()
    result = body["toolResult"]
    assert result["project"]["name"] == "The Dreamweaver"
    assert result["projectTitleUpdated"] is True
    assert "renamed the project" in result["confirmation"]

    db = SessionLocal()
    try:
        decisions = DecisionRecordStore.list_for_project(db, project["id"], limit=10)
    finally:
        db.close()
    assert decisions
    assert decisions[0]["recommendation"] == "Project title confirmed as The Dreamweaver."

    refreshed = client.get(f"/api/projects/{project['id']}")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["name"] == "The Dreamweaver"


def test_record_production_decision_approval_is_idempotent(client):
    project = _create_project(client, "Retry Project")
    proposed = _propose(
        client,
        project["id"],
        "record_production_decision",
        {"decision": "Keep the opening intimate.", "rationale": "The creator wants a quieter tone."},
    )
    assert proposed.status_code == 200, proposed.text
    proposal_id = proposed.json()["id"]

    first = _approve(client, project["id"], proposal_id)
    second = _approve(client, project["id"], proposal_id)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["toolResult"]["decision"]["id"] == second.json()["toolResult"]["decision"]["id"]


def test_project_wiki_uses_creator_model_not_repository_diagnostics(client):
    project = _create_project(client, "Untitled Project")

    empty = client.get(f"/api/codirector/projects/{project['id']}/wiki")
    assert empty.status_code == 200, empty.text
    assert empty.json()["hasContent"] is False
    assert "first message" in empty.json()["emptyState"].lower()

    _save_conversation(
        client,
        project["id"],
        [{"id": "u1", "role": "user", "content": "Call this project The Dreamweaver and make it feel mythic."}],
    )
    wiki = client.get(f"/api/codirector/projects/{project['id']}/wiki")
    assert wiki.status_code == 200, wiki.text
    body = wiki.json()
    assert body["hasContent"] is True
    assert "overview" in body
    serialized = json.dumps(body)
    assert "project.get_summary" not in serialized
    assert "project.list_blockers" not in serialized
    assert "project_service" not in serialized
    assert "session_context" not in serialized
    assert "The Dreamweaver" in serialized


def test_project_wiki_exports_pdf_and_offline_html_without_internal_diagnostics(client):
    project = _create_project(client, "The Dreamweaver")
    _save_conversation(
        client,
        project["id"],
        [{"id": "u1", "role": "user", "content": "The Dreamweaver should feel mythic and intimate."}],
    )

    from io import BytesIO
    import zipfile
    from PIL import Image

    image_buffer = BytesIO()
    Image.new("RGB", (8, 8), color=(255, 180, 64)).save(image_buffer, format="PNG")
    image_bytes = image_buffer.getvalue()

    upload = client.post(
        f"/api/projects/{project['id']}/assets",
        files={"file": (r"C:\temp\550e8400-e29b-41d4-a716-446655440000-lantern-reference.png", image_bytes, "image/png")},
        data={"tag": "Hero Lantern", "kind": "image"},
    )
    assert upload.status_code == 200, upload.text
    uploaded_image = upload.json()

    audio_bytes = b"fake-audio-bytes"
    audio_upload = client.post(
        f"/api/projects/{project['id']}/assets",
        files={"file": (r"D:\exports\123e4567-e89b-12d3-a456-426614174000-whisper-guide.m4a", audio_bytes, "audio/mp4")},
        data={"tag": "Whisper Guide", "kind": "reference"},
    )
    assert audio_upload.status_code == 200, audio_upload.text
    uploaded_audio = audio_upload.json()

    video_upload = client.post(
        f"/api/projects/{project['id']}/assets",
        files={"file": ("/Users/test/9b4f4e9b-1d0d-4020-bf23-936622337abc-scene-preview.m4v", b"fake-video-bytes", "video/x-m4v")},
        data={"tag": "Scene Preview", "kind": "reference"},
    )
    assert video_upload.status_code == 200, video_upload.text
    uploaded_video = video_upload.json()
    os.remove(uploaded_video["path"])

    pdf = client.post(f"/api/codirector/projects/{project['id']}/wiki/export/pdf", json={})
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:4] == b"%PDF"

    html = client.post(f"/api/codirector/projects/{project['id']}/wiki/export/html", json={})
    assert html.status_code == 200, html.text
    assert html.headers["content-type"].startswith("application/zip")

    archive = zipfile.ZipFile(BytesIO(html.content))
    names = set(archive.namelist())
    assert any(name.endswith("/index.html") for name in names)
    assert any(name.endswith("/data/wiki.json") for name in names)
    data_name = next(name for name in names if name.endswith("/data/wiki.json"))
    payload = json.loads(archive.read(data_name).decode("utf-8"))
    serialized = json.dumps(payload)
    assert payload["exportType"] == "adept-project-wiki"
    assert payload["assets"]
    by_kind = {asset["kind"]: asset for asset in payload["assets"]}
    assert set(by_kind) == {"image", "audio", "video"}

    image_asset = by_kind["image"]
    assert image_asset["exportId"].startswith("image-")
    assert image_asset["title"] == "Hero Lantern"
    assert image_asset["status"] == "reference"
    assert image_asset["mimeType"] == "image/png"
    assert image_asset["caption"] == "Hero Lantern"
    assert image_asset["alt"] == "Hero Lantern"
    assert image_asset["relativePath"].startswith("assets/images/references/")
    image_member = next(name for name in names if name.endswith(image_asset["relativePath"]))
    assert archive.read(image_member) == image_bytes

    audio_asset = by_kind["audio"]
    assert audio_asset["exportId"].startswith("audio-")
    assert audio_asset["title"] == "Whisper Guide"
    assert audio_asset["status"] == "reference"
    assert audio_asset["mimeType"] == "audio/mp4"
    assert audio_asset["relativePath"].startswith("assets/audio/")
    audio_member = next(name for name in names if name.endswith(audio_asset["relativePath"]))
    assert archive.read(audio_member) == audio_bytes

    video_asset = by_kind["video"]
    assert video_asset["exportId"].startswith("video-")
    assert video_asset["title"] == "Scene Preview"
    assert video_asset["status"] == "reference"
    assert video_asset["mimeType"] == "video/x-m4v"
    assert "relativePath" not in video_asset
    assert any("Media bytes were not available for Scene Preview" in warning for warning in payload["warnings"])

    serialized_assets = json.dumps(payload["assets"])
    assert uploaded_image["id"] not in serialized_assets
    assert uploaded_audio["id"] not in serialized_assets
    assert uploaded_video["id"] not in serialized_assets
    assert project["id"] not in serialized
    assert "550e8400-e29b-41d4-a716-446655440000" not in serialized_assets
    assert "123e4567-e89b-12d3-a456-426614174000" not in serialized_assets
    assert "9b4f4e9b-1d0d-4020-bf23-936622337abc" not in serialized_assets
    assert r"C:\temp" not in serialized_assets
    assert r"D:\exports" not in serialized_assets
    assert "/Users/test" not in serialized_assets
    for name in names:
        assert uploaded_image["id"][:8] not in name
        assert uploaded_audio["id"][:8] not in name
        assert uploaded_video["id"][:8] not in name
    assert "project.get_summary" not in serialized
    assert "project.list_blockers" not in serialized
    assert "project_service" not in serialized
    assert "session_context" not in serialized
    assert '"projectId"' not in serialized
    assert '"sourceMessageId"' not in serialized


def test_delete_project_cleans_up_codirector_residue(client):
    project = _create_project(client, "Delete Me")
    context_id = str(uuid.uuid4())

    with SessionLocal() as db:
        db.add(
            CoDirectorProductionPlan(
                id=str(uuid.uuid4()),
                project_id=project["id"],
                request_id="delete-project-plan",
                title="Cleanup proof",
            )
        )
        context = ProductionContextRow(
            id=context_id,
            project_id=project["id"],
            scene_id="scene-1",
            context_json="{}",
        )
        db.add(context)
        db.flush()
        db.add(
            ProductionContextExtension(
                id=str(uuid.uuid4()),
                context_id=context.id,
                extension_type="note",
                payload_json="{}",
            )
        )
        db.commit()

    deleted = client.delete(f"/api/projects/{project['id']}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"ok": True}
    assert client.get(f"/api/projects/{project['id']}").status_code == 404

    with SessionLocal() as db:
        assert (
            db.query(CoDirectorProductionPlan).filter(CoDirectorProductionPlan.project_id == project["id"]).count() == 0
        )
        assert db.query(ProductionContextRow).filter(ProductionContextRow.project_id == project["id"]).count() == 0
        assert db.query(ProductionContextExtension).filter(ProductionContextExtension.context_id == context_id).count() == 0


def test_delete_project_isolated_to_target_project(client):
    doomed = _create_project(client, "Delete Target")
    survivor = _create_project(client, "Keep Target")
    doomed_context_id = str(uuid.uuid4())
    survivor_context_id = str(uuid.uuid4())

    with SessionLocal() as db:
        for project_id, request_id, context_id in (
            (doomed["id"], "delete-target-plan", doomed_context_id),
            (survivor["id"], "keep-target-plan", survivor_context_id),
        ):
            db.add(
                CoDirectorProductionPlan(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    request_id=request_id,
                    title=request_id,
                )
            )
            context = ProductionContextRow(
                id=context_id,
                project_id=project_id,
                scene_id="scene-1",
                context_json="{}",
            )
            db.add(context)
            db.flush()
            db.add(
                ProductionContextExtension(
                    id=str(uuid.uuid4()),
                    context_id=context.id,
                    extension_type="note",
                    payload_json="{}",
                )
            )
        db.commit()

    deleted = client.delete(f"/api/projects/{doomed['id']}")
    assert deleted.status_code == 200, deleted.text
    assert client.get(f"/api/projects/{doomed['id']}").status_code == 404
    assert client.get(f"/api/projects/{survivor['id']}").status_code == 200

    with SessionLocal() as db:
        assert db.query(CoDirectorProductionPlan).filter(CoDirectorProductionPlan.project_id == doomed["id"]).count() == 0
        assert db.query(ProductionContextRow).filter(ProductionContextRow.project_id == doomed["id"]).count() == 0
        assert db.query(ProductionContextExtension).filter(ProductionContextExtension.context_id == doomed_context_id).count() == 0

        assert db.query(CoDirectorProductionPlan).filter(CoDirectorProductionPlan.project_id == survivor["id"]).count() == 1
        assert db.query(ProductionContextRow).filter(ProductionContextRow.project_id == survivor["id"]).count() == 1
        assert db.query(ProductionContextExtension).filter(ProductionContextExtension.context_id == survivor_context_id).count() == 1


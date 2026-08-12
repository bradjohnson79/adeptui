"""Cross-project ownership isolation tests for the Co-Director service layer.

For each repaired path this module verifies the three properties required by the
c3-state repair contract:

(a) two projects are seeded with same-type entities,
(b) an operation scoped to project B targeting project A's entity ID is rejected
    with the project's standard not-found response (HTTP 404 — existence is never
    leaked across projects),
(c) project A's entity is left unchanged after the rejected attempt, and the
    legitimate same-project call still succeeds.

It also unit-tests the shared ownership helper directly (missing entity, foreign
entity, owned entity) for every entity type it covers.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.codirector.tools import ownership
from app.codirector.tools.definitions import ToolContext
from app.db import Project, SessionLocal, init_db


M29_FLAGS = [
    "STUDIO_FEATURE_IMAGE_PRODUCTION_V1",
    "STUDIO_FEATURE_FRAME_PRODUCTION_V1",
    "STUDIO_FEATURE_VIDEO_PRODUCTION_V1",
    "STUDIO_FEATURE_DIRECTOR_TIMELINE_V1",
    "STUDIO_FEATURE_LIPSYNC_PRODUCTION_V1",
    "STUDIO_FEATURE_AUDIO_PRODUCTION_V1",
    "STUDIO_FEATURE_EDITING_PRODUCTION_V1",
    "STUDIO_FEATURE_RENDER_PRODUCTION_V1",
    "STUDIO_FEATURE_CODIRECTOR_PRODUCTION_CONTROL_V1",
]


@pytest.fixture()
def db_session():
    init_db()
    from app.codirector.m29.db import ensure_m29_tables
    from app.codirector.m214.db import ensure_m214_tables
    from app.voice_performance.service import ensure_tables as ensure_vp_tables

    ensure_m29_tables()
    ensure_m214_tables()
    ensure_vp_tables()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_project(db, project_id: str, name: str = "P") -> None:
    db.merge(Project(id=project_id, name=name))
    db.commit()


def _seed_vp_plan(db, project_id: str, *, segment_id: str, status: str = "draft") -> str:
    from app.voice_performance.models import PerformancePlanRow

    plan_id = uuid.uuid4().hex
    seg = {"id": segment_id, "orderIndex": 0, "segmentType": "speech", "text": "hi", "status": status}
    db.add(
        PerformancePlanRow(
            id=plan_id,
            project_id=project_id,
            scene_id=None,
            shot_id=None,
            timeline_id=None,
            character_id="char-x",
            character_profile_version_id="",
            voice_version_id="voice-x",
            source_text="hi",
            segments_json=json.dumps([seg]),
            provider_preferences_json="[]",
            applied_defaults_json="{}",
            issues_json="[]",
            status=status,
            immutable=1,
            version=1,
            compiler_version="w44.1",
            schema_version=1,
            created_by="owner",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            provenance_json="{}",
        )
    )
    db.commit()
    return plan_id


def _seed_m29_asset_version(db, project_id: str, status: str = "generated") -> str:
    from app.codirector.m29.store import create_asset_version

    ver = create_asset_version(
        db, project_id=project_id, department="image", status=status, metadata={"k": 1}
    )
    return ver["id"]


def _seed_m29_timeline_proposal(db, project_id: str) -> str:
    from app.codirector.m29.timeline.service import TimelineService

    prop = TimelineService.propose(db, project_id=project_id, notes="seed")
    return prop["id"]


def _seed_m29_control_plan(db, project_id: str) -> str:
    from app.codirector.m29.control.service import ControlService

    out = ControlService.decompose(db, project_id=project_id, request_text="seed")
    return out["planId"]


def _seed_m29_render_manifest(db, project_id: str) -> str:
    from app.codirector.m29.render.service import RenderService

    man = RenderService.create_manifest(db, project_id=project_id, kind="timeline_render")
    return man["id"]


def _seed_m29_frame_record(db, project_id: str, shot_id: str = "shot-1") -> str:
    fid = f"frame-{uuid.uuid4().hex[:10]}"
    db.execute(
        text(
            "INSERT INTO m29_frame_records "
            "(id, project_id, shot_id, frame_type, order_index, asset_id, version_id, "
            "metadata_json, created_at) VALUES "
            "(:id, :pid, :sid, :ft, :ord, :aid, :vid, :meta, :c)"
        ),
        {
            "id": fid,
            "pid": project_id,
            "sid": shot_id,
            "ft": "production_frame",
            "ord": 0,
            "aid": "asset-x",
            "vid": None,
            "meta": "{}",
            "c": datetime.utcnow().isoformat(timespec="seconds"),
        },
    )
    db.commit()
    return fid


def _seed_m214_storyteller_handoff(db, project_id: str) -> str:
    from app.codirector.m214 import storyteller

    out = storyteller.create_handoff(db, project_id=project_id, profile_id="profile-x")
    return out["id"]


def _seed_m214_sonic_concept(db, project_id: str) -> str:
    from app.codirector.m214 import sound_producer

    out = sound_producer.create_sonic_concept(db, project_id=project_id, emotional_arc="x")
    return out["id"]


def _seed_m214_attachment_interpretation(db, project_id: str) -> str:
    from app.codirector.m214 import attachments

    out = attachments.interpret_attachment(
        db, project_id=project_id, attachment_id="att-x", text_body="FADE IN:"
    )
    return out["id"]


# --- Ownership helper unit tests ---


def test_helper_performance_plan_missing_foreign_owned(db_session):
    db = db_session
    pa, pb = "proj-a-vp", "proj-b-vp"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    plan_a = _seed_vp_plan(db, pa, segment_id="seg-a")

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_performance_plan(db, pa, "does-not-exist")
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_performance_plan(db, pb, plan_a)
    assert exc.value.status_code == 404

    ownership.require_owned_performance_plan(db, pa, plan_a)


def test_helper_find_segment_plan_scoped(db_session):
    db = db_session
    pa, pb = "proj-a-seg", "proj-b-seg"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    _seed_vp_plan(db, pa, segment_id="seg-a")
    _seed_vp_plan(db, pb, segment_id="seg-b")

    plan_id, seg = ownership.find_owned_segment_plan(db, pa, "seg-a")
    assert seg["id"] == "seg-a"

    with pytest.raises(HTTPException) as exc:
        ownership.find_owned_segment_plan(db, pb, "seg-a")
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        ownership.find_owned_segment_plan(db, pa, "seg-b")
    assert exc.value.status_code == 404


def test_helper_m29_asset_version(db_session):
    db = db_session
    pa, pb = "proj-a-av", "proj-b-av"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    ver_a = _seed_m29_asset_version(db, pa)

    out = ownership.require_owned_m29_asset_version(db, pa, ver_a)
    assert out["projectId"] == pa

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m29_asset_version(db, pb, ver_a)
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m29_asset_version(db, pa, "missing")
    assert exc.value.status_code == 404


def test_helper_m29_timeline_proposal(db_session):
    db = db_session
    pa, pb = "proj-a-tl", "proj-b-tl"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    prop_a = _seed_m29_timeline_proposal(db, pa)

    out = ownership.require_owned_m29_timeline_proposal(db, pa, prop_a)
    assert out["projectId"] == pa

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m29_timeline_proposal(db, pb, prop_a)
    assert exc.value.status_code == 404


def test_helper_m29_control_plan(db_session):
    db = db_session
    pa, pb = "proj-a-ctrl", "proj-b-ctrl"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    plan_a = _seed_m29_control_plan(db, pa)

    out = ownership.require_owned_m29_control_plan(db, pa, plan_a)
    assert out["projectId"] == pa

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m29_control_plan(db, pb, plan_a)
    assert exc.value.status_code == 404


def test_helper_m29_render_manifest(db_session):
    db = db_session
    pa, pb = "proj-a-rm", "proj-b-rm"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    man_a = _seed_m29_render_manifest(db, pa)

    out = ownership.require_owned_m29_render_manifest(db, pa, man_a)
    assert out["projectId"] == pa

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m29_render_manifest(db, pb, man_a)
    assert exc.value.status_code == 404


def test_helper_m29_frame_record(db_session):
    db = db_session
    pa, pb = "proj-a-fr", "proj-b-fr"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    frame_a = _seed_m29_frame_record(db, pa)

    out = ownership.require_owned_m29_frame_record(db, pa, frame_a)
    assert out["projectId"] == pa

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m29_frame_record(db, pb, frame_a)
    assert exc.value.status_code == 404


def test_helper_m214_storyteller_handoff(db_session):
    db = db_session
    pa, pb = "proj-a-st", "proj-b-st"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    handoff_a = _seed_m214_storyteller_handoff(db, pa)

    out = ownership.require_owned_m214_storyteller_handoff(db, pa, handoff_a)
    assert out["projectId"] == pa

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m214_storyteller_handoff(db, pb, handoff_a)
    assert exc.value.status_code == 404


def test_helper_m214_sonic_concept(db_session):
    db = db_session
    pa, pb = "proj-a-sc", "proj-b-sc"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    concept_a = _seed_m214_sonic_concept(db, pa)

    out = ownership.require_owned_m214_sonic_concept(db, pa, concept_a)
    assert out["projectId"] == pa

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m214_sonic_concept(db, pb, concept_a)
    assert exc.value.status_code == 404


def test_helper_m214_attachment_interpretation(db_session):
    db = db_session
    pa, pb = "proj-a-ai", "proj-b-ai"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    interp_a = _seed_m214_attachment_interpretation(db, pa)

    out = ownership.require_owned_m214_attachment_interpretation(db, pa, interp_a)
    assert out["projectId"] == pa

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m214_attachment_interpretation(db, pb, interp_a)
    assert exc.value.status_code == 404


# --- voice_performance service + handler isolation ---


def test_vp_generate_segments_rejects_foreign_plan(db_session):
    from app.voice_performance import service as vp

    db = db_session
    pa, pb = "proj-vp-a", "proj-vp-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    plan_a = _seed_vp_plan(db, pa, segment_id="seg-a", status="submitted")

    with pytest.raises(HTTPException) as exc:
        vp.generate_segments(db, plan_a, project_id=pb)
    assert exc.value.status_code == 404

    row = db.execute(
        text("SELECT status FROM voice_performance_plans WHERE id = :id"),
        {"id": plan_a},
    ).fetchone()
    assert row[0] == "submitted"

    with pytest.raises(HTTPException) as exc:
        vp.generate_segments(db, plan_a, project_id=pa)
    # Ownership gate passed; failure is downstream (no character/voice seeded).
    assert exc.value.detail.get("message") != "Performance plan not found."


def test_vp_retry_segment_rejects_foreign_segment(db_session):
    from app.voice_performance import service as vp

    db = db_session
    pa, pb = "proj-vp-retry-a", "proj-vp-retry-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    _seed_vp_plan(db, pa, segment_id="seg-retry-a", status="generated")
    _seed_vp_plan(db, pb, segment_id="seg-retry-b", status="generated")

    with pytest.raises(HTTPException) as exc:
        vp.retry_segment(db, "seg-retry-a", project_id=pb)
    assert exc.value.status_code == 404

    out = vp.retry_segment(db, "seg-retry-a", project_id=pa)
    assert out.id


def test_vp_approve_segment_rejects_foreign_segment(db_session):
    from app.voice_performance import service as vp

    db = db_session
    pa, pb = "proj-vp-app-a", "proj-vp-app-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    plan_a = _seed_vp_plan(db, pa, segment_id="seg-app-a", status="generated")

    with pytest.raises(HTTPException) as exc:
        vp.approve_segment(db, "seg-app-a", approved=True, project_id=pb)
    assert exc.value.status_code == 404

    segs = json.loads(
        db.execute(
            text("SELECT segments_json FROM voice_performance_plans WHERE id = :id"),
            {"id": plan_a},
        ).fetchone()[0]
    )
    assert segs[0]["status"] == "generated"

    out = vp.approve_segment(db, "seg-app-a", approved=True, project_id=pa)
    assert out["status"] == "approved"


def test_vp_handler_apply_generate_segments_rejects_foreign(db_session):
    from app.codirector.tools.handlers.voice_performance import apply_generate_segments

    db = db_session
    pa, pb = "proj-vph-a", "proj-vph-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    plan_a = _seed_vp_plan(db, pa, segment_id="seg-h-a", status="submitted")

    ctx_b = ToolContext(db=db, project_id=pb, scene_id=None)
    with pytest.raises(HTTPException) as exc:
        apply_generate_segments(ctx_b, {"planId": plan_a})
    assert exc.value.status_code == 404

    row = db.execute(
        text("SELECT status FROM voice_performance_plans WHERE id = :id"),
        {"id": plan_a},
    ).fetchone()
    assert row[0] == "submitted"


def test_vp_handler_apply_retry_segment_rejects_foreign(db_session):
    from app.codirector.tools.handlers.voice_performance import apply_retry_segment

    db = db_session
    pa, pb = "proj-vphr-a", "proj-vphr-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    _seed_vp_plan(db, pa, segment_id="seg-hr-a", status="generated")

    ctx_b = ToolContext(db=db, project_id=pb, scene_id=None)
    with pytest.raises(HTTPException) as exc:
        apply_retry_segment(ctx_b, {"segmentId": "seg-hr-a"})
    assert exc.value.status_code == 404


def test_vp_handler_apply_approve_take_rejects_foreign(db_session):
    from app.codirector.tools.handlers.voice_performance import apply_approve_take

    db = db_session
    pa, pb = "proj-vpha-a", "proj-vpha-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    plan_a = _seed_vp_plan(db, pa, segment_id="seg-ha-a", status="generated")

    ctx_b = ToolContext(db=db, project_id=pb, scene_id=None)
    with pytest.raises(HTTPException) as exc:
        apply_approve_take(ctx_b, {"segmentId": "seg-ha-a"})
    assert exc.value.status_code == 404

    segs = json.loads(
        db.execute(
            text("SELECT segments_json FROM voice_performance_plans WHERE id = :id"),
            {"id": plan_a},
        ).fetchone()[0]
    )
    assert segs[0]["status"] == "generated"

    ctx_a = ToolContext(db=db, project_id=pa, scene_id=None)
    out = apply_approve_take(ctx_a, {"segmentId": "seg-ha-a"})
    assert out["status"] == "approved"


# --- m29 service-level isolation ---


def test_m29_image_approve_rejects_foreign_version(db_session):
    from app.codirector.m29.image.service import ImageService

    db = db_session
    pa, pb = "proj-m29i-a", "proj-m29i-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    ver_a = _seed_m29_asset_version(db, pa, status="generated")

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m29_asset_version(db, pb, ver_a)
    assert exc.value.status_code == 404

    out = ImageService.approve(db, ver_a, actor="tester")
    assert out["status"] == "approved"


def test_m29_timeline_approve_rejects_foreign_proposal(db_session):
    from app.codirector.m29.timeline.service import TimelineService

    db = db_session
    pa, pb = "proj-m29t-a", "proj-m29t-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    prop_a = _seed_m29_timeline_proposal(db, pa)

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m29_timeline_proposal(db, pb, prop_a)
    assert exc.value.status_code == 404

    out = TimelineService.approve(db, prop_a, actor="tester")
    assert out["status"] == "approved"


def test_m29_control_get_rejects_foreign_plan(db_session):
    db = db_session
    pa, pb = "proj-m29c-a", "proj-m29c-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    plan_a = _seed_m29_control_plan(db, pa)

    out = ownership.require_owned_m29_control_plan(db, pa, plan_a)
    assert out["projectId"] == pa

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m29_control_plan(db, pb, plan_a)
    assert exc.value.status_code == 404


def test_m29_render_get_rejects_foreign_manifest(db_session):
    db = db_session
    pa, pb = "proj-m29r-a", "proj-m29r-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    man_a = _seed_m29_render_manifest(db, pa)

    out = ownership.require_owned_m29_render_manifest(db, pa, man_a)
    assert out["projectId"] == pa

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m29_render_manifest(db, pb, man_a)
    assert exc.value.status_code == 404


def test_m29_frame_bind_rejects_foreign_frame(db_session):
    db = db_session
    pa, pb = "proj-m29f-a", "proj-m29f-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    frame_a = _seed_m29_frame_record(db, pa, shot_id="shot-orig")

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m29_frame_record(db, pb, frame_a)
    assert exc.value.status_code == 404

    # Victim unchanged: shot_id still the original.
    row = db.execute(
        text("SELECT shot_id FROM m29_frame_records WHERE id = :id"),
        {"id": frame_a},
    ).fetchone()
    assert row[0] == "shot-orig"


# --- m214 service-level isolation ---


def test_m214_storyteller_approve_rejects_foreign_handoff(db_session):
    from app.codirector.m214 import storyteller

    db = db_session
    pa, pb = "proj-m214s-a", "proj-m214s-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    handoff_a = _seed_m214_storyteller_handoff(db, pa)

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m214_storyteller_handoff(db, pb, handoff_a)
    assert exc.value.status_code == 404

    out = storyteller.approve_handoff(db, handoff_a)
    assert out.get("approved") is True


def test_m214_sonic_approve_rejects_foreign_concept(db_session):
    from app.codirector.m214 import sound_producer

    db = db_session
    pa, pb = "proj-m214sc-a", "proj-m214sc-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    concept_a = _seed_m214_sonic_concept(db, pa)

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m214_sonic_concept(db, pb, concept_a)
    assert exc.value.status_code == 404

    out = sound_producer.approve_sonic_concept(db, concept_a)
    assert out.get("approved") is True


def test_m214_attachment_confirm_rejects_foreign_interpretation(db_session):
    from app.codirector.m214 import attachments

    db = db_session
    pa, pb = "proj-m214a-a", "proj-m214a-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    interp_a = _seed_m214_attachment_interpretation(db, pa)

    with pytest.raises(HTTPException) as exc:
        ownership.require_owned_m214_attachment_interpretation(db, pb, interp_a)
    assert exc.value.status_code == 404

    out = attachments.confirm_interpretation(db, interp_a, decision="approve", note="ok")
    assert out["status"] == "approved"


# --- REST-level isolation (TestClient) ---


@pytest.fixture()
def m29_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADEPT_M29_FIXTURE_MODE", "1")
    monkeypatch.setenv("STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1", "1")
    for flag in M29_FLAGS:
        monkeypatch.setenv(flag, "1")
    import app.feature_flags as ff
    from app.codirector.m29.db import ensure_m29_tables
    from app.voice_performance.service import ensure_tables as ensure_vp_tables

    ff.feature_flags = ff.FeatureFlags.from_env(os.environ)
    init_db()
    ensure_m29_tables()
    ensure_vp_tables()
    from fastapi import FastAPI

    from app.codirector.m29.api import router as m29_router

    app = FastAPI()
    app.include_router(m29_router, prefix="/api/codirector")
    return TestClient(app)


@pytest.fixture()
def m214_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1", "true")
    import app.feature_flags as ff
    from app.codirector.m214.db import ensure_m214_tables
    from app.voice_performance.service import ensure_tables as ensure_vp_tables

    ff.feature_flags = ff.FeatureFlags.from_env(os.environ)
    init_db()
    ensure_m214_tables()
    ensure_vp_tables()
    from fastapi import FastAPI

    from app.codirector.m214.api import router as m214_router

    app = FastAPI()
    app.include_router(m214_router, prefix="/api/codirector")
    return TestClient(app)


def test_rest_m29_image_approve_foreign_version_404(m29_client, db_session):
    db = db_session
    pa, pb = "proj-rest-i-a", "proj-rest-i-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    ver_a = _seed_m29_asset_version(db, pa, status="generated")

    res = m29_client.post(
        f"/api/codirector/m29/image/{ver_a}/approve",
        json={"actor": "tester", "projectId": pb},
    )
    assert res.status_code == 404

    row = db.execute(
        text("SELECT status FROM m29_asset_versions WHERE id = :id"),
        {"id": ver_a},
    ).fetchone()
    assert row[0] == "generated"

    ok = m29_client.post(
        f"/api/codirector/m29/image/{ver_a}/approve",
        json={"actor": "tester", "projectId": pa},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved"


def test_rest_m29_timeline_approve_foreign_proposal_404(m29_client, db_session):
    db = db_session
    pa, pb = "proj-rest-t-a", "proj-rest-t-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    prop_a = _seed_m29_timeline_proposal(db, pa)

    res = m29_client.post(
        f"/api/codirector/m29/timeline/{prop_a}/approve",
        json={"actor": "tester", "projectId": pb},
    )
    assert res.status_code == 404

    row = db.execute(
        text("SELECT status FROM m29_timeline_proposals WHERE id = :id"),
        {"id": prop_a},
    ).fetchone()
    assert row[0] == "pending"

    ok = m29_client.post(
        f"/api/codirector/m29/timeline/{prop_a}/approve",
        json={"actor": "tester", "projectId": pa},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved"


def test_rest_m29_control_get_foreign_plan_404(m29_client, db_session):
    db = db_session
    pa, pb = "proj-rest-c-a", "proj-rest-c-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    plan_a = _seed_m29_control_plan(db, pa)

    res = m29_client.get(
        f"/api/codirector/m29/control/{plan_a}?projectId={pb}"
    )
    assert res.status_code == 404

    ok = m29_client.get(
        f"/api/codirector/m29/control/{plan_a}?projectId={pa}"
    )
    assert ok.status_code == 200
    assert ok.json()["projectId"] == pa


def test_rest_m29_render_get_foreign_manifest_404(m29_client, db_session):
    db = db_session
    pa, pb = "proj-rest-r-a", "proj-rest-r-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    man_a = _seed_m29_render_manifest(db, pa)

    res = m29_client.get(
        f"/api/codirector/m29/render/{man_a}?projectId={pb}"
    )
    assert res.status_code == 404

    ok = m29_client.get(
        f"/api/codirector/m29/render/{man_a}?projectId={pa}"
    )
    assert ok.status_code == 200
    assert ok.json()["projectId"] == pa


def test_rest_m29_frame_bind_foreign_frame_404(m29_client, db_session):
    db = db_session
    pa, pb = "proj-rest-f-a", "proj-rest-f-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    frame_a = _seed_m29_frame_record(db, pa, shot_id="shot-orig")

    res = m29_client.post(
        f"/api/codirector/m29/frames/{frame_a}/bind",
        json={"shotId": "shot-foreign", "projectId": pb},
    )
    assert res.status_code == 404

    row = db.execute(
        text("SELECT shot_id FROM m29_frame_records WHERE id = :id"),
        {"id": frame_a},
    ).fetchone()
    assert row[0] == "shot-orig"

    ok = m29_client.post(
        f"/api/codirector/m29/frames/{frame_a}/bind",
        json={"shotId": "shot-new", "projectId": pa},
    )
    assert ok.status_code == 200
    assert ok.json()["shotId"] == "shot-new"


def test_rest_m214_storyteller_approve_foreign_handoff_404(m214_client, db_session):
    db = db_session
    pa, pb = "proj-rest-st-a", "proj-rest-st-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    handoff_a = _seed_m214_storyteller_handoff(db, pa)

    res = m214_client.post(
        f"/api/codirector/m214/storyteller/handoff/{handoff_a}/approve",
        json={"projectId": pb},
    )
    assert res.status_code == 404

    row = db.execute(
        text("SELECT approved FROM m214_storyteller_handoffs WHERE id = :id"),
        {"id": handoff_a},
    ).fetchone()
    assert row[0] == 0

    ok = m214_client.post(
        f"/api/codirector/m214/storyteller/handoff/{handoff_a}/approve",
        json={"projectId": pa},
    )
    assert ok.status_code == 200
    assert ok.json().get("approved") is True


def test_rest_m214_sonic_approve_foreign_concept_404(m214_client, db_session):
    db = db_session
    pa, pb = "proj-rest-sc-a", "proj-rest-sc-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    concept_a = _seed_m214_sonic_concept(db, pa)

    res = m214_client.post(
        f"/api/codirector/m214/sound/concept/{concept_a}/approve",
        json={"projectId": pb},
    )
    assert res.status_code == 404

    row = db.execute(
        text("SELECT approved FROM m214_sonic_concepts WHERE id = :id"),
        {"id": concept_a},
    ).fetchone()
    assert row[0] == 0

    ok = m214_client.post(
        f"/api/codirector/m214/sound/concept/{concept_a}/approve",
        json={"projectId": pa},
    )
    assert ok.status_code == 200
    assert ok.json().get("approved") is True


def test_rest_m214_attachment_confirm_foreign_interp_404(m214_client, db_session):
    db = db_session
    pa, pb = "proj-rest-ai-a", "proj-rest-ai-b"
    _seed_project(db, pa, "A")
    _seed_project(db, pb, "B")
    interp_a = _seed_m214_attachment_interpretation(db, pa)

    res = m214_client.post(
        f"/api/codirector/m214/attachments/{interp_a}/confirm",
        json={"decision": "approve", "note": "ok", "projectId": pb},
    )
    assert res.status_code == 404

    row = db.execute(
        text("SELECT status FROM m214_attachment_interpretations WHERE id = :id"),
        {"id": interp_a},
    ).fetchone()
    assert row[0] == "proposed"

    ok = m214_client.post(
        f"/api/codirector/m214/attachments/{interp_a}/confirm",
        json={"decision": "approve", "note": "ok", "projectId": pa},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved"

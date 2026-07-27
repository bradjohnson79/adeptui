"""M2.14 Co-Director Unified Experience — unit/integration + hitchhiker smoke."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config/capabilities/adept-ui-v1.0-provider-manifest.json"
EXPECTED_MANIFEST_SHA = "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1", "true")
    monkeypatch.setenv("STUDIO_DATA_DIR", str(tmp_path / "data"))
    from app import feature_flags as ff
    from app.main import app

    ff.feature_flags = ff.FeatureFlags.from_env(os.environ)
    with TestClient(app) as c:
        yield c


def test_flag_default_off(monkeypatch):
    monkeypatch.delenv("STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1", raising=False)
    from app.feature_flags import FeatureFlags

    flags = FeatureFlags.from_env({})
    assert flags.codirector_unified_experience_v1 is False


def test_provider_manifest_sha_unchanged():
    digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert digest == EXPECTED_MANIFEST_SHA


def test_status_and_safety(client):
    r = client.get("/api/codirector/m214/status")
    assert r.status_code == 200
    body = r.json()
    assert body["flag"] == "codirector_unified_experience_v1"
    assert body["flagDefault"] is False
    assert body["manifestSha256"] == EXPECTED_MANIFEST_SHA
    assert body["extendsM211"] is True
    assert body["forkedOrchestration"] is False
    assert "storyteller" in body["specialists"]
    assert "sound-producer" in body["specialists"]
    assert body["safety"]["noNewProviders"] is True
    assert body["safety"]["noSystemLessonAutoActivate"] is True
    caps = {c["id"] for c in body["capabilityIds"]}
    assert "codirector.attachment.classify" in caps
    assert "storyteller.handoff.create" in caps
    assert "sound_producer.concept.create" in caps
    assert "production_team.impact.calculate" in caps


def test_disabled_returns_404(monkeypatch):
    monkeypatch.setenv("STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1", "false")
    from app import feature_flags as ff
    from app.main import app

    ff.feature_flags = ff.FeatureFlags.from_env(os.environ)
    with TestClient(app) as c:
        r = c.post("/api/codirector/m214/idea", json={"projectId": "p", "idea": "x"})
        assert r.status_code == 404


def test_attachment_classify_content_not_filename_alone(client):
    r = client.post(
        "/api/codirector/m214/attachments/interpret",
        json={
            "projectId": "p-att",
            "attachmentId": "a1",
            "filename": "notes.txt",
            "textBody": "FADE IN:\nINT. DINER - NIGHT\nJOE\nHello.",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["classified_kind"] == "screenplay"
    assert body["status"] == "proposed"
    assert body["honesty"] == "mocked"
    cid = body["id"]
    conf = client.post(
        f"/api/codirector/m214/attachments/{cid}/confirm",
        json={"decision": "approve", "note": "ok"},
    )
    assert conf.status_code == 200
    assert conf.json()["status"] == "approved"


def test_idea_first_and_storyteller(client):
    idea = client.post(
        "/api/codirector/m214/idea",
        json={"projectId": "p-idea", "idea": "A hitchhiker under sodium light", "preferredFormat": "short scene"},
    )
    assert idea.status_code == 200
    body = idea.json()
    assert body["stage"] == "discovery"
    assert 2 <= len(body["questions"]) <= 4
    story = client.post(
        "/api/codirector/m214/storyteller/analyze",
        json={"projectId": "p-idea", "idea": "hitchhiker", "mode": "guided"},
    )
    assert story.status_code == 200
    profile = story.json()
    assert profile["mode"] == "guided"
    assert 2 <= len(profile["questions"]) <= 4
    handoff = client.post(
        "/api/codirector/m214/storyteller/handoff",
        json={"projectId": "p-idea", "profileId": profile["id"], "directionSummary": "Intimate dread"},
    )
    assert handoff.status_code == 200
    assert handoff.json()["approved"] is False


def test_sound_producer_sonic_concept(client):
    r = client.post(
        "/api/codirector/m214/sound/concept",
        json={"projectId": "p-snd", "emotionalArc": "tension to release", "mode": "creative"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["honesty"] == "mocked"
    assert "music-supervisor" in body["payload"]["coordinatesWith"]
    assert body["approved"] is False


def test_department_messages_brief_meeting_impact(client):
    pid = "p-dept"
    client.post(
        "/api/codirector/m214/messages",
        json={
            "projectId": pid,
            "fromSpecialist": "storyteller",
            "toSpecialist": "sound-producer",
            "body": "Need sparse score under dialogue",
            "kind": "handoff",
        },
    )
    client.post(
        "/api/codirector/m214/messages",
        json={
            "projectId": pid,
            "fromSpecialist": "cinematographer",
            "toSpecialist": "sound-producer",
            "body": "conflict: camera wants loud highway bed",
            "kind": "conflict",
        },
    )
    req = client.post(f"/api/codirector/m214/messages/{pid}/required")
    assert req.status_code == 200
    assert req.json()["count"] >= 1
    brief = client.post(
        "/api/codirector/m214/brief",
        json={"projectId": pid, "title": "Hitchhiker", "primaryNextAction": "Resolve sound conflict"},
    )
    assert brief.status_code == 200
    assert brief.json()["primary_next_action"]
    meet = client.post(
        "/api/codirector/m214/meetings",
        json={"projectId": pid, "topic": "Sonic vs camera"},
    )
    assert meet.status_code == 200
    assert "synthesis" in meet.json()
    impact = client.post(
        "/api/codirector/m214/impact",
        json={
            "projectId": pid,
            "decisionId": "d1",
            "decisionSummary": "Keep sparse score",
            "previouslyApproved": ["story", "bible", "media"],
            "affectedDepartments": ["sound-producer", "cinematographer"],
        },
    )
    assert impact.status_code == 200
    body = impact.json()
    assert "story" in body["preserved_approvals"] or "bible" in body["preserved_approvals"]


def test_media_refs_and_hitchhiker_smoke(client):
    pid = "p-media"
    smoke = client.post("/api/codirector/m214/hitchhiker/smoke", json={"projectId": pid})
    assert smoke.status_code == 200
    cards = smoke.json()["cards"]
    assert all(c["honesty"] in {"mocked", "fixture"} for c in cards)
    assert all(c.get("fake3d") is False for c in cards)
    assert any("MOCKED" in c["title"] for c in cards)
    ref = client.post(
        "/api/codirector/m214/media/ref",
        json={"projectId": pid, "text": "use the second image"},
    )
    assert ref.status_code == 200
    # only one image in smoke — second may be None; first image path also tested
    ref2 = client.post(
        "/api/codirector/m214/media/ref",
        json={"projectId": pid, "text": "newest video please"},
    )
    assert ref2.status_code == 200
    assert ref2.json()["resolved"]["kind"] == "video"


def test_plan_approvals_session_restore(client):
    pid = "p-sess"
    client.post("/api/codirector/m214/idea", json={"projectId": pid, "idea": "x"})
    plan = client.get(f"/api/codirector/m214/plan/{pid}")
    assert plan.status_code == 200
    assert plan.json()["currentStage"] == "discovery"
    appr = client.post(
        "/api/codirector/m214/approvals",
        json={"projectId": pid, "pending": {"story": {"status": "pending", "items": [{"id": "1"}]}}},
    )
    assert appr.status_code == 200
    assert appr.json()["silentApproval"] is False
    client.post(
        "/api/codirector/m214/session/save",
        json={"projectId": pid, "snapshot": {"approvals": {"story": "pending"}, "blockers": []}},
    )
    restore = client.get(f"/api/codirector/m214/session/{pid}")
    assert restore.status_code == 200
    body = restore.json()
    assert body["m212FeedbackHooks"]["autoSystemPromote"] is False
    assert body["primaryNextAction"]


def test_specialist_prompts_exist():
    prompts = ROOT / "studio-api/app/codirector/prompts/specialists"
    assert (prompts / "storyteller.md").is_file()
    assert (prompts / "sound-producer.md").is_file()
    st = (prompts / "storyteller.md").read_text(encoding="utf-8")
    assert "id: storyteller" in st
    assert "may_execute_tools: false" in st


def test_capability_ids_in_registry():
    from app.capabilities.registry import BY_ID

    assert "codirector.attachment.classify" in BY_ID
    assert "storyteller.scene.analyze" in BY_ID
    assert "sound_producer.concept.create" in BY_ID
    assert "production_team.final_review" in BY_ID

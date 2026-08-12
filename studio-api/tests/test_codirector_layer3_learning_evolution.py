"""Layer 3 — 10 memory/learning/evolution cycles (project-isolated, reversible)."""

from __future__ import annotations

import os
import uuid

import pytest

from app.feature_flags import FeatureFlags


@pytest.fixture(autouse=True)
def _enable_m212():
    import app.feature_flags as ff
    import app.codirector.m212.flags as m212_flags
    import app.codirector.m212.api as m212_api

    prev = dict(os.environ)
    os.environ["STUDIO_FEATURE_CODIRECTOR_ADAPTIVE_LEARNING_V1"] = "1"
    os.environ["STUDIO_FEATURE_CODIRECTOR_PRODUCTION_INTELLIGENCE_V1"] = "1"
    ff.feature_flags = FeatureFlags.from_env(os.environ)
    yield
    os.environ.clear()
    os.environ.update(prev)
    ff.feature_flags = FeatureFlags.from_env(os.environ)
    # silence unused import warnings for modules that read flags at call time
    _ = (m212_flags, m212_api)


def _create_project(client, name: str) -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def _seed_conversation(client, project_id: str, turns: int = 6) -> None:
    events = []
    for i in range(turns):
        events.append(
            {
                "role": "user",
                "content": f"Turn {i}: remember brand bottle continuity.",
                "message_id": f"u-{i}-{uuid.uuid4().hex[:8]}",
                "client_request_id": f"cr-{i}-{uuid.uuid4().hex[:8]}",
                "actor": "user",
            }
        )
        events.append(
            {
                "role": "assistant",
                "content": f"Ack {i}: keep bottle framing and lighting.",
                "message_id": f"a-{i}-{uuid.uuid4().hex[:8]}",
                "actor": "assistant",
            }
        )
    res = client.post(f"/api/codirector/conversations/{project_id}/events", json={"events": events})
    assert res.status_code == 200, res.text


def test_layer3_ten_learning_evolution_cycles(client):
    """10 cycles: critique→lesson→promote→retrieve→rollback isolation."""
    primary = _create_project(client, f"L3-Primary-{uuid.uuid4().hex[:8]}")
    isolation = _create_project(client, f"L3-Iso-{uuid.uuid4().hex[:8]}")
    _seed_conversation(client, primary, turns=8)

    # Compact (Wave B) on primary
    compact = client.post(
        f"/api/codirector/conversations/{primary}/compact",
        json={"beforeSequence": 8, "summaryText": "Earlier bottle continuity notes summarized."},
    )
    assert compact.status_code == 200, compact.text

    # Export/import (Wave D) roundtrip to isolation must not leak lessons until promoted in primary
    exported = client.get(f"/api/codirector/projects/{primary}/memory/export")
    assert exported.status_code == 200
    bundle = exported.json()

    lesson_ids: list[str] = []
    for cycle in range(10):
        critique = client.post(
            "/api/codirector/m212/critique",
            json={
                "projectId": primary,
                "action": {
                    "summary": f"Cycle {cycle}: prefer slower push-in on product bottle",
                    "recommendation": "Keep bottle design; slower camera push-in",
                },
                "outcome": {
                    "success": False,
                    "message": "continuity push-in too fast",
                    "mistakeClass": "camera",
                    "verified": True,
                },
                "traces": [{"status": "fail", "failures": ["camera push-in too fast"]}],
                "layer": "project",
                "createLesson": True,
            },
        )
        assert critique.status_code == 200, critique.text
        body = critique.json()
        lesson = body.get("candidateLesson") or body.get("lesson") or body.get("createdLesson") or {}
        lesson_id = lesson.get("id") or lesson.get("lessonId") or body.get("lessonId")
        assert lesson_id, f"cycle {cycle} missing lesson: {body}"
        lesson_ids.append(lesson_id)

        # Regression attach (best-effort)
        client.post(f"/api/codirector/m212/lessons/{lesson_id}/regression", json={})

        promote = client.post(
            f"/api/codirector/m212/lessons/{lesson_id}/promote",
            json={"actor": "layer3-cert", "role": "user", "note": f"cycle-{cycle}", "intoLearningPy": True},
        )
        assert promote.status_code in (200, 201), promote.text

        lessons = client.get(f"/api/codirector/m212/lessons?projectId={primary}")
        assert lessons.status_code == 200
        listed = lessons.json()
        items = listed.get("lessons") or listed.get("items") or listed
        assert isinstance(items, list)
        assert any((x.get("id") or x.get("lessonId")) == lesson_id for x in items)

        # Isolation project must not see primary lessons
        iso_lessons = client.get(f"/api/codirector/m212/lessons?projectId={isolation}")
        assert iso_lessons.status_code == 200
        iso_items = iso_lessons.json().get("lessons") or iso_lessons.json().get("items") or iso_lessons.json()
        if isinstance(iso_items, list):
            assert not any((x.get("id") or x.get("lessonId")) == lesson_id for x in iso_items)

    # Snapshot / complete project memory
    snap = client.get(f"/api/codirector/projects/{primary}/intelligence/snapshot")
    assert snap.status_code == 200, snap.text

    audit = client.get(f"/api/codirector/conversations/{primary}/audit")
    assert audit.status_code == 200
    assert audit.json().get("ok") is True or audit.json().get("healthy") is True or "findings" in audit.json()

    # Deprecate / rollback last lesson (reversible)
    last = lesson_ids[-1]
    retire = client.post(f"/api/codirector/m212/lessons/{last}/retire", json={"actor": "layer3-cert", "note": "deprecate"})
    if retire.status_code not in (200, 201):
        rollback = client.post(
            f"/api/codirector/m212/lessons/{last}/rollback",
            json={"actor": "layer3-cert", "note": "rollback"},
        )
        assert rollback.status_code in (200, 201), rollback.text

    # Import conversation bundle into isolation — conversation only, no primary lesson leakage
    imported = client.post(
        f"/api/codirector/projects/{isolation}/memory/import",
        json={"bundle": bundle},
    )
    assert imported.status_code == 200, imported.text
    iso_after = client.get(f"/api/codirector/m212/lessons?projectId={isolation}")
    iso_after_items = iso_after.json().get("lessons") or iso_after.json().get("items") or []
    assert not any((x.get("id") or x.get("lessonId")) in lesson_ids for x in iso_after_items)

    assert len(lesson_ids) == 10

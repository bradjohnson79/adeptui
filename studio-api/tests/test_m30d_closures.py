"""M3.0d focused regressions: B9 honesty, B13 syncEvent, B19 overrideReason, Director→Editor."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


def test_b9_normalize_rejects_contradictory_success():
    from app.codirector.m211.honesty import normalize_orchestration_response

    out = normalize_orchestration_response(
        {
            "status": "completed",
            "success": True,
            "specialists": [],
            "failures": [{"specialistId": "storyteller", "error": "boom"}],
            "errors": [],
            "warnings": [],
            "missingAssets": [],
            "timeouts": [],
        }
    )
    assert out["success"] is False or out["status"] != "completed"
    assert out["errors"]
    assert out["status"] in ("failed", "completed_with_warnings")


def test_b9_pending_approval_is_not_success():
    from app.codirector.m211.honesty import normalize_orchestration_response

    out = normalize_orchestration_response(
        {
            "status": "completed",
            "specialists": [{"specialistId": "vpc"}],
            "pendingApprovals": [{"stageId": "vpc"}],
            "failures": [],
            "errors": [],
            "warnings": [],
            "timeouts": [],
            "missingAssets": [],
        }
    )
    assert out["status"] == "pending_approval"
    assert out["success"] is False


def test_b13_sync_event_resolves_bar_timing():
    from app.codirector.m29.audio.service import _resolve_sync_start

    start, label = _resolve_sync_start(start_sec=0.0, sync_event="bar-3")
    assert label == "bar-3"
    assert start == 4.0


def test_b13_place_cue_persists_sync_event(monkeypatch):
    from app.codirector.m29.audio import service as audio_mod

    calls: list[dict] = []

    def fake_execute(stmt, params=None):
        calls.append(params or {})
        return MagicMock()

    db = MagicMock()
    db.execute.side_effect = fake_execute
    db.commit = MagicMock()
    db.get = MagicMock(return_value=None)

    monkeypatch.setattr(audio_mod, "ensure_m29_tables", lambda: None)
    monkeypatch.setattr(audio_mod, "_write_scene_clip", lambda *a, **k: False)

    out = audio_mod.AudioService.place_cue(
        db,
        project_id="p1",
        kind="sfx",
        asset_id="a1",
        start_sec=0.0,
        sync_event="bar-2",
        scene_id=None,
    )
    assert out["syncEvent"] == "bar-2"
    assert out["startSec"] == 2.0
    assert calls and '"syncEvent": "bar-2"' in (calls[0].get("meta") or "")


def test_b19_override_requires_reason(monkeypatch):
    from app.codirector.vision import approval as approval_mod

    session = MagicMock()
    session.reportId = "rep"
    session.assetId = None
    report = MagicMock()
    report.band = "reject"

    monkeypatch.setattr(
        approval_mod.VisionStore,
        "get_session",
        lambda db, sid, project_id=None: session,
    )
    monkeypatch.setattr(
        approval_mod.VisionStore,
        "get_report",
        lambda db, rid, project_id=None: report,
    )

    with pytest.raises(ValueError, match="overrideReason"):
        approval_mod.record_decision(
            MagicMock(),
            project_id="proj",
            session_id="sess",
            decision="override_approve",
            override=True,
            override_reason="",
            notes="",
        )


def test_b19_override_with_reason_records(monkeypatch):
    from app.codirector.vision import approval as approval_mod

    session = MagicMock()
    session.reportId = "rep"
    session.assetId = None
    report = MagicMock()
    report.band = "reject"
    saved = {}

    monkeypatch.setattr(
        approval_mod.VisionStore,
        "get_session",
        lambda db, sid, project_id=None: session,
    )
    monkeypatch.setattr(
        approval_mod.VisionStore,
        "get_report",
        lambda db, rid, project_id=None: report,
    )
    monkeypatch.setattr(
        approval_mod.VisionStore,
        "save_approval",
        lambda db, approval: saved.update(approval.model_dump(mode="json")),
    )
    monkeypatch.setattr(
        approval_mod.VisionStore,
        "update_session_status",
        lambda *a, **k: None,
    )

    out = approval_mod.record_decision(
        MagicMock(),
        project_id="proj",
        session_id="sess",
        decision="override_approve",
        override=True,
        override_reason="Creative exception for trailer cut",
    )
    assert out["status"] == "approved"
    assert "Creative exception" in (saved.get("notes") or "")


def test_director_to_editor_preserves_scene_and_order(client):
    """API-level handoff: Director sequence → Editor tracks (canonical transform model)."""
    proj = client.post("/api/projects", json={"name": "M30D Director Editor"})
    if proj.status_code >= 400:
        pytest.skip(f"project create unavailable: {proj.status_code}")
    project_id = proj.json()["id"]

    scene = client.post(
        f"/api/projects/{project_id}/scenes",
        json={"name": "Scene One", "prompt": "capstone open", "duration_sec": 4},
    )
    if scene.status_code >= 400:
        pytest.skip(f"scene create unavailable: {scene.status_code} {scene.text}")
    scene_id = scene.json()["id"]

    seq = client.post(
        f"/api/projects/{project_id}/director-sequences",
        json={"name": "Shot A", "scene_id": scene_id, "asset_id": "asset-visual-1"},
    )
    if seq.status_code >= 400:
        pytest.skip(f"director sequence create unavailable: {seq.status_code} {seq.text}")
    seq_body = seq.json()
    seq_id = seq_body.get("id")
    assert seq_id

    handoff = client.post(
        f"/api/projects/{project_id}/director-sequences/{seq_id}/send-to-editor",
        json={"track": "video", "include_audio": False, "length": 3.5},
    )
    assert handoff.status_code < 400, handoff.text
    body = handoff.json()
    clip = body.get("clip") or {}
    editor = body.get("editor") or {}
    tracks = (editor.get("tracks") or {}).get("video") or []
    assert clip.get("source_director_sequence_id") == seq_id
    assert clip.get("source_scene_id") == scene_id
    assert abs(float(clip.get("length") or 0) - 3.5) < 1e-6
    assert any(c.get("id") == clip.get("id") for c in tracks)

    loaded = client.get(f"/api/projects/{project_id}/editor")
    assert loaded.status_code < 400
    loaded_tracks = (loaded.json().get("tracks") or {}).get("video") or []
    assert any(c.get("source_director_sequence_id") == seq_id for c in loaded_tracks)

    # Editor mutation then reload
    mutated = dict(loaded.json())
    video = list((mutated.get("tracks") or {}).get("video") or [])
    if video:
        video[0] = {**video[0], "label": "editor-edit"}
        mutated.setdefault("tracks", {})["video"] = video
    put = client.put(f"/api/projects/{project_id}/editor", json=mutated)
    assert put.status_code < 400, put.text
    again = client.get(f"/api/projects/{project_id}/editor")
    assert any(
        c.get("label") == "editor-edit"
        for c in ((again.json().get("tracks") or {}).get("video") or [])
    )

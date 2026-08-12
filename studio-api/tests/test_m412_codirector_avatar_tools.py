from __future__ import annotations

import pytest

def _create_project(client, name: str = "Avatar CoDirector") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 200
    return response.json()["id"]


def _create_session(
    client,
    project_id: str,
    *,
    script: str,
    input_mode: str = "script",
    voice: dict | None = None,
    links: dict | None = None,
) -> dict:
    voice_payload = {
        "provider": "upload",
        "model": "",
        "speaker_id": "",
        "language": "en",
        "accent": "",
        "tone": "natural",
        "pitch": "medium",
        "pace": "moderate",
        "emotional_range": "restrained",
        "pronunciation_notes": "",
        "stability": "high",
        "usage_rights": "project",
        "audio_asset_id": None,
        "fallback_audio_asset_id": None,
        "profile_id": None,
        "approved_record_id": None,
        "approved_take_id": None,
    }
    if voice:
        voice_payload.update(voice)
    response = client.post(
        f"/api/projects/{project_id}/avatar-sessions",
        json={
            "name": "Korri Presentation",
            "character_profile_id": "char-korri",
            "character_name": "Korri",
            "mode": "cinematic_character",
            "bootstrap": {
                "character_profile_id": "char-korri",
                "character_name": "Korri",
                "dialogue_original": script,
                "duration_class": "story_section",
                "presentation_style": "direct_presenter",
                "framing_choice": "medium_presenter",
                "background_choice": "studio_gradient",
                "input_mode": input_mode,
                "provider_choice": "infinitetalk-local",
                "model_id": "infinitetalk-local",
                "voice": voice_payload,
                "links": links or {},
            },
        },
    )
    assert response.status_code == 200
    return response.json()


def _propose(client, project_id: str, tool_id: str, **arguments) -> dict:
    response = client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": tool_id, "arguments": arguments, "createdBy": "user"},
    )
    assert response.status_code == 200
    return response.json()


def test_avatar_codirector_tool_definitions_registered() -> None:
    from app.codirector.tools import registry

    assert registry.get("avatar.inspect").kind == "read"
    assert registry.get("avatar.create_plan").kind == "mutating"
    assert registry.get("avatar.request_retake").kind == "mutating"


def test_avatar_create_plan_is_proposal_gated(client) -> None:
    project_id = _create_project(client)
    session = _create_session(
        client,
        project_id,
        script=(
            "Korri opens the lesson with a confident hook. "
            "She explains the key idea. "
            "Then she lands a warm final invitation."
        ),
    )

    before = client.get(f"/api/projects/{project_id}/avatar-sessions/{session['id']}").json()
    assert before["presentation_plan"]["summary"] != "Break the lesson into three confident beats."

    proposal = _propose(
        client,
        project_id,
        "avatar.create_plan",
        sessionId=session["id"],
        summary="Break the lesson into three confident beats.",
        targetSectionDurationMs=5000,
        deliveryStyle="Clear, warm educator delivery.",
        chapterTransitionStyle="Pause briefly before each new chapter idea.",
    )
    assert proposal["status"] == "pending"
    assert proposal["toolCall"]["toolId"] == "avatar.create_plan"

    unchanged = client.get(f"/api/projects/{project_id}/avatar-sessions/{session['id']}").json()
    assert unchanged["presentation_plan"]["summary"] != "Break the lesson into three confident beats."

    approved = client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve",
        json={},
    )
    assert approved.status_code == 200

    after = client.get(f"/api/projects/{project_id}/avatar-sessions/{session['id']}").json()
    assert after["presentation_plan"]["summary"] == "Break the lesson into three confident beats."
    assert after["presentation_plan"]["sectionTargetSeconds"] == 5.0
    assert after["presentation_plan"]["deliveryStyle"] == "Clear, warm educator delivery."
    assert after["active_job_id"] is None


def test_avatar_request_retake_is_proposal_gated(client, monkeypatch) -> None:
    from app import avatar_studio as avatar

    project_id = _create_project(client, "Avatar Retake Proposal")
    session = _create_session(
        client,
        project_id,
        script=(
            "Korri opens with a strong setup. "
            "She follows with a second beat that should stay untouched."
        ),
    )

    def always_complete(_db, *, project_id, provider_id, session_data, job, section):
        del project_id, provider_id, session_data, job
        return {
            "ok": True,
            "outputVideoAssetId": f"video-{section['order']}",
            "continuationFrameAssetId": f"frame-{section['order']}",
        }

    monkeypatch.setattr(avatar, "_execute_section_generation", always_complete)

    job_response = client.post(
        f"/api/projects/{project_id}/avatar-sessions/{session['id']}/jobs",
        json={"providerId": "infinitetalk-local", "startImmediately": True},
    )
    assert job_response.status_code == 200
    job = job_response.json()
    section = next(item for item in job["sections"] if item["status"] == "completed")

    proposal = _propose(
        client,
        project_id,
        "avatar.request_retake",
        jobId=job["id"],
        sectionId=section["id"],
        note="Punch the ending harder while preserving the handoff.",
    )
    assert proposal["status"] == "pending"
    assert proposal["toolCall"]["toolId"] == "avatar.request_retake"

    unchanged_job = client.get(f"/api/projects/{project_id}/avatar-jobs/{job['id']}").json()
    unchanged_section = next(item for item in unchanged_job["sections"] if item["id"] == section["id"])
    assert unchanged_section["status"] == "completed"

    approved = client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve",
        json={},
    )
    assert approved.status_code == 200

    updated_job = client.get(f"/api/projects/{project_id}/avatar-jobs/{job['id']}").json()
    updated_section = next(item for item in updated_job["sections"] if item["id"] == section["id"])
    untouched = next(item for item in updated_job["sections"] if item["id"] != section["id"])
    assert updated_section["status"] == "retake_requested"
    assert updated_section["retakeNote"] == "Punch the ending harder while preserving the handoff."
    assert untouched["status"] == "completed"


def test_avatar_repair_lipsync_requires_musetalk_provider(client, monkeypatch) -> None:
    from fastapi import HTTPException

    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import avatar_m412
    from app.db import SessionLocal

    project_id = _create_project(client, "Avatar MuseTalk Gate")
    session = _create_session(client, project_id, script="Korri lines for repair.")
    job_response = client.post(
        f"/api/projects/{project_id}/avatar-sessions/{session['id']}/jobs",
        json={"providerId": "infinitetalk-local", "startImmediately": False},
    )
    assert job_response.status_code == 200
    job = job_response.json()

    monkeypatch.setattr(
        avatar_m412,
        "inspect_runtime",
        lambda _provider_id: {"runtimeReady": False, "healthState": "not_installed"},
    )
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        with pytest.raises(HTTPException) as excinfo:
            avatar_m412.apply_repair_lipsync(
                ctx,
                {
                    "jobId": job["id"],
                    "sectionId": job["sections"][0]["id"],
                    "note": "Repair mouth timing only.",
                },
            )
        assert excinfo.value.status_code == 409
        assert excinfo.value.detail["code"] == "AVATAR_LIPSYNC_REPAIR_PROVIDER_REQUIRED"
    finally:
        db.close()


def test_avatar_prepare_timeline_persists_provenance(client, monkeypatch) -> None:
    from app import avatar_studio as avatar

    project_id = _create_project(client, "Avatar Timeline Provenance")
    session = _create_session(
        client,
        project_id,
        script="Korri opens. Korri closes.",
        input_mode="approved_voice",
        voice={
            "provider": "voice-performance-m410",
            "model": "index-tts2-local",
            "audio_asset_id": "asset-approved-audio",
            "approved_record_id": "record-approved",
            "approved_take_id": "take-approved",
            "profile_id": "voice-korri",
        },
        links={
            "script_document_id": "doc-1",
            "script_scene_heading_id": "scene-heading-1",
            "script_scene_id": "scene-1",
            "script_source_label": "INT. STUDIO - DAY",
            "script_revision_version": 7,
            "voice_record_id": "record-approved",
            "voice_take_id": "take-approved",
        },
    )

    def always_complete(_db, *, project_id, provider_id, session_data, job, section):
        del project_id, provider_id, session_data, job
        return {
            "ok": True,
            "outputVideoAssetId": f"video-{section['order']}",
            "continuationFrameAssetId": f"frame-{section['order']}",
        }

    monkeypatch.setattr(avatar, "_execute_section_generation", always_complete)

    job_response = client.post(
        f"/api/projects/{project_id}/avatar-sessions/{session['id']}/jobs",
        json={"providerId": "infinitetalk-local", "startImmediately": True},
    )
    assert job_response.status_code == 200
    job = job_response.json()

    proposal = _propose(
        client,
        project_id,
        "avatar.prepare_timeline",
        jobId=job["id"],
        placementMode="full_presentation",
        trackId="avatar-presenter",
    )
    assert proposal["status"] == "pending"
    approved = client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve",
        json={},
    )
    assert approved.status_code == 200

    updated_job = client.get(f"/api/projects/{project_id}/avatar-jobs/{job['id']}").json()
    timeline_proposal = updated_job["timelineProposal"]
    assert timeline_proposal["placementMode"] == "full_presentation"
    assert timeline_proposal["provenance"]["avatarId"] == updated_job["avatarId"]
    assert timeline_proposal["provenance"]["voice"]["approvedTakeId"] == "take-approved"
    assert timeline_proposal["provenance"]["script"]["sceneHeadingId"] == "scene-heading-1"
    assert timeline_proposal["audioMix"]["dialogueStemAssetId"] == "asset-approved-audio"

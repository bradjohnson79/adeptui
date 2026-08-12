from __future__ import annotations

from pathlib import Path

import pytest

from app import avatar_studio as avatar


def _create_project(client, name: str = "Avatar Long Form") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 200
    return response.json()["id"]


def _create_session(
    client,
    project_id: str,
    *,
    script: str,
    duration_class: str = "story_section",
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
    payload = {
        "name": "Korri Presenter Session",
        "character_profile_id": "char-korri",
        "character_name": "Korri",
        "mode": "cinematic_character",
        "bootstrap": {
            "character_profile_id": "char-korri",
            "character_name": "Korri",
            "dialogue_original": script,
            "duration_class": duration_class,
            "presentation_style": "direct_presenter",
            "framing_choice": "medium_presenter",
            "background_choice": "studio_gradient",
            "input_mode": input_mode,
            "provider_choice": "infinitetalk-local",
            "model_id": "infinitetalk-local",
            "voice": voice_payload,
            "links": links or {},
        },
    }
    response = client.post(f"/api/projects/{project_id}/avatar-sessions", json=payload)
    assert response.status_code == 200
    return response.json()


def _plan_job(client, project_id: str, session_id: str, *, start_immediately: bool = False) -> dict:
    response = client.post(
        f"/api/projects/{project_id}/avatar-sessions/{session_id}/jobs",
        json={"providerId": "infinitetalk-local", "startImmediately": start_immediately},
    )
    assert response.status_code == 200
    return response.json()


def test_avatar_job_plans_persistent_sections(client) -> None:
    project_id = _create_project(client)
    session = _create_session(
        client,
        project_id,
        script=(
            "Korri opens with a calm introduction. She explains the problem clearly. "
            "Then she pivots to the solution with a warm invitation to keep watching."
        ),
    )

    job = _plan_job(client, project_id, session["id"], start_immediately=False)

    assert job["status"] == "queued"
    assert len(job["sections"]) >= 2
    assert job["requestedDurationMs"] > 0
    assert [section["order"] for section in job["sections"]] == list(range(len(job["sections"])))
    assert all(section["audioEndMs"] > section["audioStartMs"] for section in job["sections"])

    refreshed_session = client.get(f"/api/projects/{project_id}/avatar-sessions/{session['id']}").json()
    assert refreshed_session["active_job_id"] == job["id"]


def test_avatar_job_overlap_and_continuity_hooks(client) -> None:
    project_id = _create_project(client, "Avatar Continuity")
    session = _create_session(
        client,
        project_id,
        script=(
            "Korri sets the scene. She keeps the energy up through a second beat. "
            "A third beat lands the chapter close for the presenter."
        ),
    )

    job = _plan_job(client, project_id, session["id"], start_immediately=False)
    assert len(job["sections"]) >= 2

    first, second = job["sections"][0], job["sections"][1]
    assert first["overlapAfterMs"] > 0
    assert second["overlapBeforeMs"] > 0
    assert (
        first["presentationPlan"]["sharedStyleProfileId"]
        == second["presentationPlan"]["sharedStyleProfileId"]
    )
    assert second["presentationPlan"]["continuity"]["previousSectionId"] == first["id"]
    assert first["presentationPlan"]["transitionValidation"]["required"] is True
    assert job["transitionValidation"]["validated"] is False


def test_avatar_section_retry_is_independent(
    client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    del tmp_path  # tmp_path kept available for future executor expansion.
    project_id = _create_project(client, "Avatar Retry")
    session = _create_session(
        client,
        project_id,
        script=(
            "Korri opens with a direct statement. She follows with a second section that "
            "should stay untouched while the first section retries."
        ),
    )
    fail_once = {"done": False}

    def fake_execute(_db, *, project_id, provider_id, session_data, job, section):
        del project_id, provider_id, session_data, job
        if section["order"] == 0 and not fail_once["done"]:
            fail_once["done"] = True
            return {
                "ok": False,
                "errorCode": avatar.AvatarErrorCode.RUNTIME_UNAVAILABLE.value,
                "message": "Runtime unavailable for first attempt.",
            }
        return {
            "ok": True,
            "outputVideoAssetId": f"video-{section['order']}-attempt-{section.get('attempt', 1)}",
            "continuationFrameAssetId": f"frame-{section['order']}-attempt-{section.get('attempt', 1)}",
        }

    monkeypatch.setattr(avatar, "_execute_section_generation", fake_execute)

    first_job = _plan_job(client, project_id, session["id"], start_immediately=True)
    failed = next(section for section in first_job["sections"] if section["status"] == "failed")
    untouched = next(section for section in first_job["sections"] if section["status"] == "completed")
    untouched_asset = untouched["outputVideoAssetId"]

    retry = client.post(
        f"/api/projects/{project_id}/avatar-jobs/{first_job['id']}/sections/{failed['id']}/retry"
    )
    assert retry.status_code == 200
    retried_job = retry.json()
    retried_section = next(section for section in retried_job["sections"] if section["id"] == failed["id"])
    same_other_section = next(section for section in retried_job["sections"] if section["id"] == untouched["id"])

    assert retried_section["status"] == "completed"
    assert retried_section["attempt"] == 2
    assert same_other_section["outputVideoAssetId"] == untouched_asset
    assert retried_job["status"] == "assembling"


def test_avatar_job_persistence_reload(client) -> None:
    project_id = _create_project(client, "Avatar Reload")
    session = _create_session(
        client,
        project_id,
        script="Korri sets up one section. Korri lands a second section cleanly for reload persistence.",
    )

    job = _plan_job(client, project_id, session["id"], start_immediately=False)
    listed = client.get(f"/api/projects/{project_id}/avatar-sessions/{session['id']}/jobs")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == job["id"]

    fetched = client.get(f"/api/projects/{project_id}/avatar-jobs/{job['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["sections"][0]["scriptText"]
    assert fetched.json()["sessionId"] == session["id"]


def test_avatar_job_pause_resume_and_cancel(client, monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = _create_project(client, "Avatar Controls")
    session = _create_session(
        client,
        project_id,
        script=(
            "Korri starts one section. Another section follows so the pause resume control has "
            "real work to coordinate."
        ),
    )

    planned = _plan_job(client, project_id, session["id"], start_immediately=False)

    paused = client.post(f"/api/projects/{project_id}/avatar-jobs/{planned['id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    def always_complete(_db, *, project_id, provider_id, session_data, job, section):
        del project_id, provider_id, session_data, job
        return {
            "ok": True,
            "outputVideoAssetId": f"video-{section['order']}",
            "continuationFrameAssetId": f"frame-{section['order']}",
        }

    monkeypatch.setattr(avatar, "_execute_section_generation", always_complete)
    resumed = client.post(f"/api/projects/{project_id}/avatar-jobs/{planned['id']}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "assembling"

    planned_two = _plan_job(client, project_id, session["id"], start_immediately=False)
    cancelled = client.post(f"/api/projects/{project_id}/avatar-jobs/{planned_two['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert all(
        section["status"] == "failed" and section["errorCode"] == "AVATAR_SECTION_CANCELLED"
        for section in cancelled.json()["sections"]
    )


def test_avatar_job_requires_approved_voice_linkage_in_approved_voice_mode(client) -> None:
    project_id = _create_project(client, "Avatar Approved Voice Gate")
    session = _create_session(
        client,
        project_id,
        script="",
        input_mode="approved_voice",
        voice={
            "provider": "voice-performance-m410",
            "model": "index-tts2-local",
            "audio_asset_id": "asset-approved-audio",
        },
    )

    response = client.post(
        f"/api/projects/{project_id}/avatar-sessions/{session['id']}/jobs",
        json={"providerId": "infinitetalk-local", "startImmediately": False},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AVATAR_APPROVED_VOICE_REQUIRED"


def test_avatar_retake_preserves_prior_version(client, monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = _create_project(client, "Avatar Retake Lineage")
    session = _create_session(
        client,
        project_id,
        script=(
            "Korri opens with a strong setup. "
            "She follows with a second beat that should remain available while the first section retakes."
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

    job = _plan_job(client, project_id, session["id"], start_immediately=True)
    section = next(item for item in job["sections"] if item["status"] == "completed")
    response = client.post(
        f"/api/projects/{project_id}/avatar-jobs/{job['id']}/sections/{section['id']}/retake",
        json={
            "actionType": "regenerate_section",
            "reason": "Replace the timing drift",
            "note": "Keep the neighboring handoff intact.",
        },
    )
    assert response.status_code == 200
    updated = response.json()
    updated_section = next(item for item in updated["sections"] if item["id"] == section["id"])

    assert updated_section["status"] == "retake_requested"
    assert updated_section["retakeActionType"] == "regenerate_section"
    assert updated_section["retakeReason"] == "Replace the timing drift"
    assert updated_section["outputVideoAssetId"] == "video-0"
    assert len(updated_section["versionHistory"]) == 1
    assert updated_section["versionHistory"][0]["outputVideoAssetId"] == "video-0"
    assert updated_section["retakeHistory"][0]["neighboringContext"]["next"]["id"]

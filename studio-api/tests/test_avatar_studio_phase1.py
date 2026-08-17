from __future__ import annotations

from app import avatar_studio as avatar


def _create_project(client, name: str = "Avatar Phase 1") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 200
    return response.json()["id"]


def _create_session(client, project_id: str, **bootstrap) -> dict:
    payload = {
        "name": bootstrap.pop("name", "Korri Presenter Session"),
        "character_profile_id": bootstrap.get("character_profile_id", "char-korri"),
        "character_name": bootstrap.get("character_name", "Korri"),
        "mode": bootstrap.get("mode", "cinematic_character"),
        "bootstrap": {
            "character_profile_id": "char-korri",
            "character_name": "Korri",
            "dialogue_original": "Welcome to the briefing.",
            "input_mode": "script",
            "provider_choice": "infinitetalk-local",
            "model_id": "infinitetalk-local",
            **bootstrap,
        },
    }
    response = client.post(f"/api/projects/{project_id}/avatar-sessions", json=payload)
    assert response.status_code == 200
    return response.json()


def test_validate_script_mode_can_plan_without_audio() -> None:
    data = avatar._empty("proj-1", "Script Plan")
    data["character_profile_id"] = "char-korri"
    data["character_name"] = "Korri"
    data["input_mode"] = "script"
    data["dialogue_original"] = "Hello from the presenter."
    data["lip_sync_method"] = "external"
    issues = avatar._validate(data)
    assert not any(item["level"] == "bad" for item in issues)
    assert any("script mode can still plan" in item["text"] for item in issues)


def test_validate_approved_voice_stays_strict() -> None:
    data = avatar._empty("proj-1", "Approved Voice")
    data["character_profile_id"] = "char-korri"
    data["character_name"] = "Korri"
    data["input_mode"] = "approved_voice"
    issues = avatar._validate(data)
    assert any(
        item["level"] == "bad" and "Approved Voice" in item["text"]
        for item in issues
    )


def test_validate_matches_not_installed_reason_for_external_audio_in_approved_mode() -> None:
    data = avatar._empty("proj-1", "Approved Voice")
    data["input_mode"] = "approved_voice"
    data["voice"]["audio_asset_id"] = None
    data["lip_sync_method"] = "external"
    issues = avatar._validate(data)
    texts = [item["text"] for item in issues if item["level"] == "bad"]
    assert any("Approved Voice" in text or "Audio required" in text for text in texts)


def test_character_bind_uses_approved_still_not_name_only(client) -> None:
    project_id = _create_project(client)
    session = _create_session(
        client,
        project_id,
        source_still_asset_id="ast-hero-1",
        character_profile_id="char-korri",
        character_name="Korri",
    )
    assert session["character_name"] == "Korri"
    assert session["source_still_asset_id"] == "ast-hero-1"
    job = client.post(
        f"/api/projects/{project_id}/avatar-sessions/{session['id']}/jobs",
        json={"providerId": "infinitetalk-local", "startImmediately": False},
    )
    assert job.status_code == 200
    body = job.json()
    assert body["referenceStillAssetId"] == "ast-hero-1"
    assert body["identityProfileRef"] == "char-korri"
    assert body["sections"][0]["presentationPlan"]["referenceStillAssetId"] == "ast-hero-1"


def test_save_draft_and_new_session_do_not_overwrite(client) -> None:
    project_id = _create_project(client, "Avatar Sessions")
    first = _create_session(client, project_id, name="Session A", dialogue_original="First draft lines.")
    second = _create_session(client, project_id, name="Session B", dialogue_original="Second session lines.")
    assert first["id"] != second["id"]

    patched = client.patch(
        f"/api/projects/{project_id}/avatar-sessions/{first['id']}",
        json={"dialogue_original": "Updated first draft.", "name": "Session A saved"},
    )
    assert patched.status_code == 200
    assert patched.json()["dialogue_original"] == "Updated first draft."

    listed = client.get(f"/api/projects/{project_id}/avatar-sessions").json()
    ids = {item["id"] for item in listed}
    assert first["id"] in ids
    assert second["id"] in ids
    by_id = {item["id"]: item for item in listed}
    assert by_id[first["id"]]["dialogue_original"] == "Updated first draft."
    assert by_id[second["id"]]["dialogue_original"] == "Second session lines."
    assert by_id[second["id"]]["name"] != "Session A saved"


def test_live_generation_stays_uncertified(client) -> None:
    project_id = _create_project(client, "Avatar Uncertified")
    session = _create_session(client, project_id)
    response = client.post(
        f"/api/projects/{project_id}/avatar-sessions/{session['id']}/jobs",
        json={"providerId": "infinitetalk-local", "startImmediately": True},
    )
    assert response.status_code == 200
    job = response.json()
    assert job.get("assembly", {}).get("compositeVideoAssetId") in (None, "")
    section_assets = [section.get("outputVideoAssetId") for section in job.get("sections") or []]
    assert all(not asset for asset in section_assets)
    codes = {
        str((job.get("lastError") or {}).get("code") or ""),
        *[str(section.get("errorCode") or "") for section in job.get("sections") or []],
    }
    assert any(
        "PROVIDER_NOT_CERTIFIED" in code or "PROVIDER_NOT_INSTALLED" in code or "RUNTIME_UNAVAILABLE" in code
        for code in codes
    )
    assert job["status"] != "completed" or not any(section_assets)

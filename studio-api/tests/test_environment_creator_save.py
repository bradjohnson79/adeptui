"""Environment Creator canonical save: create vs update, Global, composite preserved."""

from __future__ import annotations

from app.environment_reference_sheet.orchestrator import create_sheet
from app.environment_reference_sheet.store import load_sheet, save_sheet


def _create_project(client, name: str = "Env Creator Save") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 200
    return response.json()["id"]


def test_environment_creator_save_requires_name(client) -> None:
    project_id = _create_project(client, "Env Save Validation")
    res = client.post(
        f"/api/environment-reference-sheets/projects/{project_id}/save",
        json={"name": "  ", "environmentPrompt": "fog"},
    )
    assert res.status_code == 400
    assert "name" in res.json()["detail"].lower()


def test_environment_creator_save_create_then_update_same_id(client) -> None:
    project_id = _create_project(client, "Env Save Upsert")
    created = client.post(
        f"/api/environment-reference-sheets/projects/{project_id}/save",
        json={
            "name": "Anadriya's Quarters",
            "environmentPrompt": "Warm cabin with amber lamps",
            "isGlobal": True,
            "aspectRatio": "16:9",
            "generator": "gpt-image-2",
            "characters": [{"characterId": "c1", "name": "Anadriya"}],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["created"] is True
    sheet_id = body["sheet"]["sheetId"]
    assert body["sheet"]["name"] == "Anadriya's Quarters"
    assert body["sheet"]["isGlobal"] is True
    assert body["sheet"]["description"] == "Warm cabin with amber lamps"
    plan = body["sheet"]["provenance"]["details"]["environmentCreatorPlan"]
    assert plan["environmentPrompt"] == "Warm cabin with amber lamps"
    assert plan["isGlobal"] is True

    sheet = load_sheet(project_id, sheet_id)
    assert sheet is not None
    sheet.ers_composite_asset_id = "ers-composite-keep"
    save_sheet(sheet)

    updated = client.post(
        f"/api/environment-reference-sheets/projects/{project_id}/save",
        json={
            "sheetId": sheet_id,
            "name": "Anadriya's Quarters",
            "environmentPrompt": "Updated quarters description",
            "isGlobal": False,
            "aspectRatio": "21:9",
        },
    )
    assert updated.status_code == 200, updated.text
    again = updated.json()
    assert again["created"] is False
    assert again["sheet"]["sheetId"] == sheet_id
    assert again["sheet"]["description"] == "Updated quarters description"
    assert again["sheet"]["isGlobal"] is False
    assert again["sheet"]["ers_composite_asset_id"] == "ers-composite-keep"

    named = client.post(
        f"/api/environment-reference-sheets/projects/{project_id}/save",
        json={
            "name": "Anadriya's Quarters",
            "environmentPrompt": "Third save same name",
            "isGlobal": True,
        },
    )
    assert named.status_code == 409, named.text
    detail = named.json()["detail"]
    if isinstance(detail, dict):
        assert detail.get("code") == "PROFILE_NAME_ALREADY_EXISTS"
        assert detail.get("existingId") == sheet_id
    listed = client.get(f"/api/environment-reference-sheets/projects/{project_id}")
    assert listed.status_code == 200
    names = [row["name"] for row in listed.json()["sheets"]]
    assert names.count("Anadriya's Quarters") == 1


def test_environment_creator_save_global_visible_in_other_project(client) -> None:
    project_a = _create_project(client, "Env Save Owner")
    project_b = _create_project(client, "Env Save Other")
    saved = client.post(
        f"/api/environment-reference-sheets/projects/{project_a}/save",
        json={"name": "Shared Quarters", "environmentPrompt": "global set", "isGlobal": True},
    )
    assert saved.status_code == 200, saved.text
    visible = client.get(f"/api/environment-reference-sheets/projects/{project_b}")
    assert visible.status_code == 200
    names = {row["name"] for row in visible.json()["sheets"]}
    assert "Shared Quarters" in names


def test_environment_creator_save_preserves_existing_generated_composite() -> None:
    project_id = "proj-env-save-composite"
    sheet = create_sheet(project_id=project_id, name="Keep Composite", description="original")
    sheet.ers_composite_asset_id = "generated-ers-1"
    save_sheet(sheet)
    from app.environment_reference_sheet.creator_save import apply_environment_creator_plan

    apply_environment_creator_plan(
        sheet,
        {
            "name": "Keep Composite",
            "environmentPrompt": "metadata only",
            "isGlobal": False,
            "characters": [],
            "props": [],
        },
    )
    assert sheet.ers_composite_asset_id == "generated-ers-1"
    assert sheet.description == "metadata only"

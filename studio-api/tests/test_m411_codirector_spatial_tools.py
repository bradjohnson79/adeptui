from __future__ import annotations

import pytest


def _create_project(client, name: str = "Spatial Tool Project") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Moody practical lighting."})
    assert res.status_code == 200
    return res.json()["id"]


def _first_scene_id(client, project_id: str) -> str:
    res = client.get(f"/api/projects/{project_id}")
    assert res.status_code == 200
    scenes = res.json()["scenes"]
    assert scenes
    return scenes[0]["id"]


def _read(client, project_id: str, tool_id: str, **arguments):
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={"toolId": tool_id, "arguments": arguments},
    )


def _propose(client, project_id: str, tool_id: str, **arguments):
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": tool_id, "arguments": arguments},
    )


def _approve(client, project_id: str, proposal_id: str):
    return client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/approve", json={})


def _receipt(client, project_id: str, proposal_id: str) -> dict:
    res = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/receipt")
    assert res.status_code == 200
    return res.json()


def _seed_character(project_id: str, character_id: str) -> None:
    """CDX-013: spatial.place_character must reference a project-owned CharacterProfileRow."""
    from app.character_identity.models import CharacterProfileRow
    from app.db import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        existing = db.get(CharacterProfileRow, character_id)
        if existing is not None:
            db.delete(existing)
            db.commit()
        db.add(CharacterProfileRow(id=character_id, project_id=project_id, name=character_id))
        db.commit()
    finally:
        db.close()


def _create_map(
    client,
    project_id: str,
    *,
    title: str = "Warehouse Map",
    master_prompt: str = "Abandoned warehouse interior, damp concrete floor, practical sodium lights.",
) -> str:
    _seed_character(project_id, "char-korri")
    proposal = _propose(
        client,
        project_id,
        "spatial.create_map",
        title=title,
        sceneId=_first_scene_id(client, project_id),
        masterEnvironmentPrompt=master_prompt,
    )
    assert proposal.status_code == 200
    approved = _approve(client, project_id, proposal.json()["id"])
    assert approved.status_code == 200
    receipt = _receipt(client, project_id, proposal.json()["id"])
    return receipt["toolResult"]["document"]["id"]


def _place_character(client, project_id: str, document_id: str, *, x: float = -1.0, z: float = 2.0) -> dict:
    proposal = _propose(
        client,
        project_id,
        "spatial.place_character",
        documentId=document_id,
        characterId="char-korri",
        label="Korri",
        x=x,
        y=0.0,
        z=z,
        pose="standing",
        expression="focused",
    )
    assert proposal.status_code == 200
    assert proposal.json()["status"] == "pending"
    approved = _approve(client, project_id, proposal.json()["id"])
    assert approved.status_code == 200
    return _receipt(client, project_id, proposal.json()["id"])


def test_spatial_list_and_get_map(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(client, project_id, title="Dockyard Blocking")

    listed = _read(client, project_id, "spatial.list_maps")
    assert listed.status_code == 200
    body = listed.json()["result"]["data"]
    assert body["count"] == 1
    assert body["documents"][0]["id"] == document_id
    assert body["documents"][0]["title"] == "Dockyard Blocking"

    fetched = _read(client, project_id, "spatial.get_map", documentId=document_id)
    assert fetched.status_code == 200
    result = fetched.json()["result"]["data"]
    assert result["document"]["id"] == document_id
    assert result["summary"]["documentId"] == document_id
    assert result["document"]["masterEnvironmentPrompt"].startswith("Abandoned warehouse interior")


def test_spatial_place_character_proposal_is_gated(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(client, project_id)

    proposal = _propose(
        client,
        project_id,
        "spatial.place_character",
        documentId=document_id,
        characterId="char-korri",
        label="Korri",
        x=-1.25,
        y=0.0,
        z=1.75,
        pose="standing",
    )
    assert proposal.status_code == 200
    assert proposal.json()["toolCall"]["preview"]["summary"]

    before = _read(client, project_id, "spatial.get_map", documentId=document_id)
    assert before.status_code == 200
    assert before.json()["result"]["data"]["document"]["characters"] == []

    approved = _approve(client, project_id, proposal.json()["id"])
    assert approved.status_code == 200
    receipt = _receipt(client, project_id, proposal.json()["id"])
    assert receipt["toolId"] == "spatial.place_character"
    assert receipt["toolResult"]["document"]["characters"][0]["characterId"] == "char-korri"

    after = _read(client, project_id, "spatial.get_map", documentId=document_id)
    assert after.status_code == 200
    characters = after.json()["result"]["data"]["document"]["characters"]
    assert len(characters) == 1
    assert characters[0]["label"] == "Korri"


def test_spatial_generate_360_plan_returns_shared_prompt_and_8_yaws(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(
        client,
        project_id,
        master_prompt="Rainy cyberpunk alley, reflective puddles, neon signs, consistent storefront layout.",
    )

    proposal = _propose(
        client,
        project_id,
        "spatial.generate_360_plan",
        documentId=document_id,
        includeCharacters=False,
        masterEnvironmentPrompt="Rainy cyberpunk alley, reflective puddles, neon signs, consistent storefront layout.",
        cameraHeightMeters=1.7,
        lensMm=24,
    )
    assert proposal.status_code == 200
    preview = proposal.json()["toolCall"]["preview"]
    assert any("shots: 8 directions" in line for line in preview["lines"])

    approved = _approve(client, project_id, proposal.json()["id"])
    assert approved.status_code == 200
    receipt = _receipt(client, project_id, proposal.json()["id"])
    plan = receipt["toolResult"]["plan"]

    assert plan["masterEnvironmentPrompt"] == (
        "Rainy cyberpunk alley, reflective puddles, neon signs, consistent storefront layout."
    )
    assert plan["captureMode"] == "environment_only"
    assert plan["cameraHeightMeters"] == pytest.approx(1.7)
    assert plan["lensMm"] == pytest.approx(24.0)
    assert [shot["yawDegrees"] for shot in plan["shots"]] == [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]
    assert all("Same environment" in shot["prompt"] for shot in plan["shots"])


def test_spatial_build_reference_bundle(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(client, project_id)
    _place_character(client, project_id, document_id, x=-0.75, z=2.25)

    bundle_res = _read(
        client,
        project_id,
        "spatial.build_reference_bundle",
        documentId=document_id,
        target="image",
    )
    assert bundle_res.status_code == 200
    bundle = bundle_res.json()["result"]["data"]["bundle"]
    assert bundle["documentId"] == document_id
    assert bundle["target"] == "image"
    assert bundle["environmentPrompt"].startswith("Abandoned warehouse interior")
    assert len(bundle["characters"]) == 1
    assert bundle["characters"][0]["label"] == "Korri"
    assert bundle["creatorPositionLabels"]

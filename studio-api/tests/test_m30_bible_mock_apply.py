"""M3.0 Completion Phase 2 (B10): the mock Bible proposal must actually apply.

Root cause these lock down: the deterministic provider proposed a character field named
`appearance`, but `CharacterData` forbids extras, so approval only failed at *apply* time
— after the user had already said yes. The payload shape is asserted directly against the
domain validator, and the full approve/reject lifecycle is asserted against the Bible.
"""

from __future__ import annotations

import asyncio
import json
import re

import pytest

from app.codirector.bible.domain.schemas import CharacterData, validate_entity_data
from app.codirector.providers.base import ChatRequest
from app.codirector.providers.mock import MockCoDirectorProvider
from app.codirector.structured_output import extract_proposal_block

_FENCE_RE = re.compile(r"```proposal\s*([\s\S]*?)```", re.IGNORECASE)


@pytest.fixture()
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    yield
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)


def _create_project(client, name: str = "B10 Bible Project") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _create_bible(client, project_id: str) -> dict:
    preview = client.post(
        f"/api/codirector/projects/{project_id}/bible/import/preview", json={}
    ).json()
    res = client.post(
        f"/api/codirector/projects/{project_id}/bible/import/confirm",
        json={"entities": preview["entities"], "facts": preview["facts"]},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _mock_reply(scenario: str, monkeypatch: pytest.MonkeyPatch, text: str = "She has a scar now") -> str:
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", scenario)
    provider = MockCoDirectorProvider()
    result = asyncio.run(
        provider.generate(
            ChatRequest(
                request_id="req-b10",
                messages=[{"role": "user", "content": text}],
                model_id="mock-model",
            )
        )
    )
    return result.reply


def _character_entity(bible: dict, key: str = "ava") -> dict | None:
    for entity in bible["currentVersion"]["entities"]:
        if entity["entityKey"] == key:
            return entity
    return None


def test_mock_character_proposal_payload_matches_character_data(monkeypatch) -> None:
    reply = _mock_reply("proposal_character_update", monkeypatch)
    fence = _FENCE_RE.search(reply)
    assert fence is not None, "scenario must emit a ```proposal fence"

    data = json.loads(fence.group(1))
    mutation = data["entityMutations"][0]
    assert mutation["entityType"] == "character"
    assert mutation["entityKey"] == "ava"

    # The exact call apply_mutation_set makes. It raises on any unknown key.
    validated = validate_entity_data("character", mutation["data"])
    assert "scar" in validated["appearanceSummary"]
    assert set(mutation["data"]) <= set(CharacterData.model_fields)
    assert "appearance" not in mutation["data"], "extras are forbidden by CharacterData"


def test_mock_proposal_parses_into_a_bible_mutation_set(monkeypatch) -> None:
    reply = _mock_reply("proposal_character_update", monkeypatch)
    parsed = extract_proposal_block(reply)
    assert parsed is not None
    assert parsed.error is None, parsed.error
    assert parsed.mutations is not None
    assert parsed.mutations.entityMutations[0].entityKey == "ava"


def test_approving_the_mock_proposal_creates_version_2(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "proposal_character_update")

    chat = client.post(
        "/api/codirector/chat",
        json={
            "messages": [{"role": "user", "content": "She has a scar now"}],
            "project_id": project_id,
        },
    )
    assert chat.status_code == 200, chat.text
    proposal_id = chat.json()["proposal"]["id"]

    approve = client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/approve",
        json={"decidedBy": "user"},
    )
    assert approve.status_code == 200, approve.text
    receipt = approve.json()
    assert receipt["status"] == "success", receipt
    assert receipt["resultingVersionNumber"] == 2

    bible = client.get(f"/api/codirector/projects/{project_id}/bible").json()
    assert bible["currentVersion"]["versionNumber"] == 2
    ava = _character_entity(bible)
    assert ava is not None
    assert "scar" in ava["data"]["appearanceSummary"]


def test_rejecting_the_mock_proposal_leaves_the_bible_unchanged(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "proposal_character_update")

    chat = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "Update her look"}], "project_id": project_id},
    )
    assert chat.status_code == 200, chat.text
    proposal_id = chat.json()["proposal"]["id"]

    reject = client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/reject",
        json={"decidedBy": "user"},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "rejected"

    bible = client.get(f"/api/codirector/projects/{project_id}/bible").json()
    assert bible["currentVersion"]["versionNumber"] == 1
    assert _character_entity(bible) is None


def test_unknown_character_field_still_fails_loudly(client, mock_provider_env) -> None:
    """The guard the mock used to trip. Kept so a future rename fails here, not at approval."""
    with pytest.raises(Exception):
        validate_entity_data("character", {"appearance": "a scar"})

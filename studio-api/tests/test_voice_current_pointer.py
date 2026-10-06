"""Character current voice is a mutable pointer; approved profile bytes stay immutable."""

from __future__ import annotations

import json
import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.character_identity.models import CharacterProfileRow, VoiceProfileRow
from app.character_identity.schemas import CharacterProfileCreate, VoiceProfileCreate
from app.character_identity.service import (
    approve_voice_profile,
    create_profile,
    create_voice_profile,
    fork_draft_voice_profile,
    list_voice_profiles,
)
from app.character_identity.voice_creator import approve_voice_candidate, get_voice_workspace
from app.db import Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags


def _apply_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import fields as dataclass_fields

    import app.feature_flags as ff

    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    refreshed = FeatureFlags.from_env(os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))


@pytest.fixture()
def db(monkeypatch: pytest.MonkeyPatch) -> Session:
    _apply_flags(monkeypatch)
    init_db()
    from app.character_identity import ensure_character_identity_tables

    ensure_character_identity_tables()
    session = SessionLocal()
    yield session
    session.close()


def _project(db: Session, name: str) -> str:
    pid = f"voice-ptr-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name=name))
    db.commit()
    return pid


def _character(db: Session, project_id: str, name: str = "Cade O'Connor", *, is_global: bool = False):
    token = uuid.uuid4().hex[:8]
    slug = f"{name.lower().replace(' ', '').replace(chr(39), '')}{token}"
    return create_profile(
        db,
        project_id,
        CharacterProfileCreate(name=f"{name} {token}", slug=slug, is_global=is_global),
    )


def _voice(db: Session, project_id: str, character_id: str, name: str):
    return create_voice_profile(
        db,
        project_id,
        character_id,
        VoiceProfileCreate(name=name, source_mode="CLONE", provider="qwen3-tts"),
    )


def _stamp_candidate(db: Session, voice_id: str, candidate_id: str, asset_id: str) -> None:
    row = db.get(VoiceProfileRow, voice_id)
    assert row is not None
    lineage = json.loads(row.lineage_json or "{}")
    lineage["candidatesMeta"] = [
        {"id": candidate_id, "assetId": asset_id, "status": "ready", "name": "Sample 1"},
    ]
    row.lineage_json = json.dumps(lineage)
    row.approved_preview_asset_id = asset_id
    db.commit()


def test_approve_moves_current_pointer_and_keeps_previous_approved(db: Session):
    project_id = _project(db, "Cade Scenes")
    character = _character(db, project_id)
    v1 = _voice(db, project_id, character.id, "Cade O'Connor Clone v1")
    first = approve_voice_profile(db, project_id, character.id, v1["id"])
    assert first["approval_status"] == "approved"
    row = db.get(CharacterProfileRow, character.id)
    assert row is not None
    assert row.active_voice_profile_id == v1["id"]

    v2 = _voice(db, project_id, character.id, "Cade O'Connor Clone v2")
    second = approve_voice_profile(db, project_id, character.id, v2["id"])
    assert second["id"] == v2["id"]
    assert second["approval_status"] == "approved"
    row = db.get(CharacterProfileRow, character.id)
    assert row is not None
    assert row.active_voice_profile_id == v2["id"]
    kept = db.get(VoiceProfileRow, v1["id"])
    assert kept is not None
    assert kept.approval_status == "approved"
    assert kept.name == "Cade O'Connor Clone v1"


def test_reapprove_existing_is_idempotent_pointer_not_409(db: Session):
    project_id = _project(db, "Cade Scenes")
    character = _character(db, project_id)
    v1 = _voice(db, project_id, character.id, "Cade Clone v1")
    v2 = _voice(db, project_id, character.id, "Cade Clone v2")
    approve_voice_profile(db, project_id, character.id, v1["id"])
    approve_voice_profile(db, project_id, character.id, v2["id"])
    again = approve_voice_profile(db, project_id, character.id, v1["id"])
    assert again["id"] == v1["id"]
    row = db.get(CharacterProfileRow, character.id)
    assert row is not None
    assert row.active_voice_profile_id == v1["id"]
    still = db.get(VoiceProfileRow, v2["id"])
    assert still is not None
    assert still.approval_status == "approved"
    third = approve_voice_profile(db, project_id, character.id, v1["id"])
    assert third["id"] == v1["id"]


def test_approve_candidate_does_not_mutate_already_approved_profile(db: Session):
    project_id = _project(db, "Cade Scenes")
    character = _character(db, project_id)
    v1 = _voice(db, project_id, character.id, "Cade Clone")
    _stamp_candidate(db, v1["id"], "cand-1", "asset-1")
    first = approve_voice_candidate(db, project_id, character.id, v1["id"], candidate_id="cand-1")
    assert first["ok"] is True
    assert first["pointerOnly"] is False
    before = db.get(VoiceProfileRow, v1["id"])
    assert before is not None
    lineage_before = before.lineage_json
    preview_before = before.approved_preview_asset_id
    v2 = _voice(db, project_id, character.id, "Cade Clone v2")
    _stamp_candidate(db, v2["id"], "cand-2", "asset-2")
    approve_voice_candidate(db, project_id, character.id, v2["id"], candidate_id="cand-2")
    reuse = approve_voice_candidate(db, project_id, character.id, v1["id"], candidate_id="cand-1")
    assert reuse["ok"] is True
    assert reuse["pointerOnly"] is True
    assert reuse["currentVoiceProfileId"] == v1["id"]
    after = db.get(VoiceProfileRow, v1["id"])
    assert after is not None
    assert after.lineage_json == lineage_before
    assert after.approved_preview_asset_id == preview_before
    row = db.get(CharacterProfileRow, character.id)
    assert row is not None
    assert row.active_voice_profile_id == v1["id"]


def test_fork_draft_does_not_steal_current_approved_voice(db: Session):
    project_id = _project(db, "Cade Scenes")
    character = _character(db, project_id)
    v1 = _voice(db, project_id, character.id, "Cade Clone")
    approve_voice_profile(db, project_id, character.id, v1["id"])
    draft, forked = fork_draft_voice_profile(db, project_id, character.id, v1["id"])
    assert forked is True
    assert draft.id != v1["id"]
    assert draft.approval_status == "draft"
    row = db.get(CharacterProfileRow, character.id)
    assert row is not None
    assert row.active_voice_profile_id == v1["id"]


def test_one_current_voice_and_history_on_workspace(db: Session):
    project_id = _project(db, "Cade Scenes")
    character = _character(db, project_id)
    v1 = _voice(db, project_id, character.id, "Cade Clone v1")
    v2 = _voice(db, project_id, character.id, "Cade Clone v2")
    v3 = _voice(db, project_id, character.id, "Cade Clone v3")
    approve_voice_profile(db, project_id, character.id, v1["id"])
    approve_voice_profile(db, project_id, character.id, v2["id"])
    approve_voice_profile(db, project_id, character.id, v3["id"])
    ws = get_voice_workspace(db, project_id, character.id)
    assert ws["activeVoiceProfileId"] == v3["id"]
    assert ws["activeVoice"]["approval_status"] == "approved"
    previous_ids = {item["id"] for item in ws["previousApprovedVoices"]}
    assert previous_ids == {v1["id"], v2["id"]}
    voices = list_voice_profiles(db, project_id, character.id)
    assert len(voices) == 3
    assert all(item["characterId"] == character.id for item in voices)


def test_global_character_voices_visible_from_other_project_approve_stays_owned(db: Session):
    project_a = _project(db, "Owner")
    project_b = _project(db, "Viewer")
    character = _character(db, project_a, "Global Cade", is_global=True)
    v1 = _voice(db, project_a, character.id, "Global Cade Clone")
    approve_voice_profile(db, project_a, character.id, v1["id"])
    listed = list_voice_profiles(db, project_b, character.id)
    assert [item["id"] for item in listed] == [v1["id"]]
    ws = get_voice_workspace(db, project_b, character.id)
    assert ws["activeVoiceProfileId"] == v1["id"]
    with pytest.raises(HTTPException) as exc:
        approve_voice_profile(db, project_b, character.id, v1["id"])
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "OWNER_REQUIRED"

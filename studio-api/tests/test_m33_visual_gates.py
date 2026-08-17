"""M3.3j visual gates — owner approval invariants."""

from __future__ import annotations

import json
import os
import uuid

import pytest
from sqlalchemy.orm import Session

from app.character_identity.schemas import CharacterProfileCreate
from app.character_identity.visual_gates import (
    GATE_ORDER,
    owner_select_concept,
    promote_to_canonical,
    propose_visual_directions,
    set_gate_status,
)
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
def enable_m33(monkeypatch: pytest.MonkeyPatch):
    _apply_flags(monkeypatch)
    yield
    _apply_flags(monkeypatch)


@pytest.fixture()
def db(enable_m33) -> Session:
    init_db()
    from app.character_identity import ensure_character_identity_tables

    ensure_character_identity_tables()
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def project_and_character(db: Session):
    from app.character_identity import service as ci

    pid = f"vg-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name="Visual Gates Test"))
    db.commit()
    profile = ci.create_profile(
        db,
        pid,
        CharacterProfileCreate(name="Gate Test", role="cert", description="Visual gate unit test."),
    )
    return pid, profile.id, profile.active_version_id


def test_propose_visual_directions_requires_three(db: Session, project_and_character):
    project_id, character_id, _ = project_and_character
    payload = propose_visual_directions(db, project_id, character_id)
    assert payload["status"] == "AWAITING_OWNER"
    assert len(payload["directions"]) >= 3
    assert payload["provenance"] == "PROPOSED_BY_CHARACTER_CREATOR"


def test_owner_select_concept_requires_owner(db: Session, project_and_character):
    project_id, character_id, _ = project_and_character
    payload = propose_visual_directions(db, project_id, character_id)
    direction_id = payload["directions"][0]["id"]
    selected = owner_select_concept(
        db,
        project_id,
        character_id,
        direction_id=direction_id,
        approved_by="owner",
    )
    assert selected["status"] == "OWNER_APPROVED"
    assert selected["approvedBy"] == "owner"
    assert selected["provenance"] == "USER_CONFIRMED"


def test_cannot_self_approve_without_approved_by(db: Session, project_and_character):
    project_id, character_id, _ = project_and_character
    set_gate_status(db, project_id, character_id, "hero_identity", status="PROPOSED")
    with pytest.raises(ValueError, match="approved_by"):
        set_gate_status(db, project_id, character_id, "hero_identity", status="OWNER_APPROVED")


def test_promote_requires_all_gates_owner_approved(db: Session, project_and_character):
    project_id, character_id, version_id = project_and_character
    proposed = propose_visual_directions(db, project_id, character_id)
    # CDX-002: non-Korri profiles get profile-derived directions — the Korri
    # lock id (wild_sun_sprite) is no longer selectable; pick the first
    # proposed direction instead.
    owner_select_concept(
        db,
        project_id,
        character_id,
        direction_id=proposed["directions"][0]["id"],
        approved_by="owner",
    )
    for gate in GATE_ORDER:
        if gate == "concept":
            continue
        set_gate_status(db, project_id, character_id, gate, status="PROPOSED")
        if gate != "performance":
            set_gate_status(
                db,
                project_id,
                character_id,
                gate,
                status="OWNER_APPROVED",
                approved_by="owner",
            )

    with pytest.raises(ValueError, match="not OWNER_APPROVED"):
        promote_to_canonical(db, project_id, character_id, version_id)

    set_gate_status(
        db,
        project_id,
        character_id,
        "performance",
        status="OWNER_APPROVED",
        approved_by="owner",
    )
    result = promote_to_canonical(db, project_id, character_id, version_id)
    assert result["ok"] is True
    assert result["provenance"] == "CANONICAL_FROM_USER_APPROVAL"

"""Phase 4 — Character approval truth (CDX-002 / CDX-003 / CDX-007 / CDX-008).

Backend regression tests for the character_identity approval/canon path:

1. non-Korri profile -> concept directions are NOT the Korri lock strings
2. concept gate is not OWNER_APPROVED until an explicit direction is selected
3. 3 candidates -> approve index 2 -> owner-approve -> gate assetId ==
   approved candidate assetId (pack + canonical agree)
4. (frontend unit — see studio-web/src/components/character/useCharacterProfile.test.ts)
5. approve-candidate with absent/foreign assetId -> typed 4xx, no canonical row
6. pack with details/performance NOT_STARTED -> status not OWNER_APPROVED
"""

from __future__ import annotations

import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.character_identity.schemas import CharacterProfileCreate
from app.character_identity.service import (
    approve_character_candidate,
    resolve_approved_reference,
)
from app.character_identity.visual_gates import (
    list_gates,
    owner_select_concept,
    propose_visual_directions,
)
from app.db import Asset, Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags

COVERAGE_ROLES = [
    "full_body_front",
    "full_body_side_left",
    "full_body_back",
    "closeup_front",
    "closeup_side_left",
    "closeup_back",
]
DETAIL_ROLES = [
    "skin_closeup",
    "hair_front",
    "hair_side",
    "hair_back",
    "wardrobe_reference",
    "accessory_reference",
]
PERFORMANCE_ROLES = ["expression_sheet", "pose_sheet"]


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

    pid = f"truth-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name="Approval Truth Test"))
    db.commit()
    profile = ci.create_profile(
        db,
        pid,
        CharacterProfileCreate(
            name="Mira",
            slug="mira",
            role="lead",
            description="A tall engineer with dark hair and a calm presence.",
            species_or_type="human",
            apparent_age="30s",
            gender_presentation="feminine",
        ),
    )
    return pid, profile.id, profile.active_version_id


def _make_asset(db: Session, project_id: str, *, tag: str = "image") -> str:
    aid = str(uuid.uuid4())
    db.add(
        Asset(
            id=aid,
            project_id=project_id,
            tag=tag,
            kind="image",
            filename=f"{tag}.png",
            path=f"{tag}.png",
        )
    )
    db.commit()
    return aid


def _seed_pack(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    role_assets: dict[str, str],
    include_details: bool = False,
    include_performance: bool = False,
) -> dict:
    """Persist a visual-sheet pack directly (no image jobs) for gate tests."""
    from app.character_identity.visual_sheet import _save_pack

    pack = {
        "schema_version": 2,
        "status": "READY_FOR_OWNER",
        "characterId": character_id,
        "projectId": project_id,
        "jobs": {},
        "roleAssets": dict(role_assets),
        "candidates": [],
        "candidateCount": 1,
        "includeDetails": include_details,
        "includePerformance": include_performance,
        "characterName": "Mira",
        "characterSlug": "mira",
        "phase": "awaiting_owner_approval",
        "mock": False,
    }
    return _save_pack(db, project_id, character_id, pack)


def _approve_concept(db: Session, project_id: str, character_id: str) -> None:
    payload = propose_visual_directions(db, project_id, character_id)
    owner_select_concept(
        db,
        project_id,
        character_id,
        direction_id=payload["directions"][0]["id"],
        approved_by="owner",
    )


def _full_role_assets(db: Session, project_id: str) -> dict[str, str]:
    assets: dict[str, str] = {"hero_identity": _make_asset(db, project_id, tag="hero_identity")}
    for role in COVERAGE_ROLES + DETAIL_ROLES + PERFORMANCE_ROLES:
        assets[role] = _make_asset(db, project_id, tag=role)
    return assets


# 1. CDX-002 — non-Korri characters get profile-derived directions, never the
#    Korri lock strings.
def test_non_korri_concept_directions_are_not_korri_locked(db: Session, project_and_character):
    project_id, character_id, _ = project_and_character
    payload = propose_visual_directions(db, project_id, character_id)
    assert payload["status"] == "AWAITING_OWNER"
    ids = [d["id"] for d in payload["directions"]]
    assert len(ids) >= 3
    assert "wild_sun_sprite" not in ids
    blob = json.dumps(payload).lower()
    for banned in (
        "black twin ponytails",
        "purple eyes",
        "sun sprite elf",
        "wild_sun_sprite",
        "wooden earrings",
        "circuit/light tattoos",
        "handmade black cloth",
    ):
        assert banned not in blob, f"Korri lock string leaked into non-Korri directions: {banned}"


def test_korri_seed_profile_keeps_korri_directions(db: Session, enable_m33):
    """The Korri-specific defaults remain ONLY for the actual Korri seed profile."""
    from app.character_identity.service import seed_korri_from_canon

    pid = f"korri-{uuid.uuid4().hex[:8]}"
    db.merge(Project(id=pid, name="Korri Test"))
    db.commit()
    profile = seed_korri_from_canon(db, pid)
    payload = propose_visual_directions(db, pid, profile.id)
    ids = [d["id"] for d in payload["directions"]]
    assert "wild_sun_sprite" in ids
    assert payload["status"] == "AWAITING_OWNER"


# 2. CDX-002 — the concept gate is never auto-approved; owner-approve requires
#    an explicit direction selection.
def test_concept_gate_not_owner_approved_until_explicit_selection(db: Session, project_and_character):
    from app.character_identity.visual_sheet import owner_approve_visual_sheet_gates

    project_id, character_id, _ = project_and_character
    _seed_pack(db, project_id, character_id, role_assets={"hero_identity": _make_asset(db, project_id, tag="hero")})
    payload = propose_visual_directions(db, project_id, character_id)
    assert payload["status"] == "AWAITING_OWNER"

    with pytest.raises(ValueError, match="Concept gate requires explicit owner"):
        owner_approve_visual_sheet_gates(db, project_id, character_id, approved_by="owner")

    gates = list_gates(db, project_id, character_id)
    assert gates["gates"]["concept"]["status"] == "AWAITING_OWNER"

    # Explicit owner selection unblocks owner-approve (but the pack still
    # reports pending gates because only the hero has an asset).
    owner_select_concept(
        db,
        project_id,
        character_id,
        direction_id=payload["directions"][0]["id"],
        approved_by="owner",
    )
    result = owner_approve_visual_sheet_gates(db, project_id, character_id, approved_by="owner")
    assert result["ok"] is True
    assert result["status"] == "OWNER_APPROVED_WITH_PENDING"


# 3. CDX-003 — owner-approved candidate is the gate/hero asset, not the
#    first-completed candidate the pack auto-attached.
def test_approved_candidate_becomes_gate_asset_pack_and_canonical_agree(db: Session, project_and_character):
    from app.character_identity.visual_sheet import _load_pack_raw, owner_approve_visual_sheet_gates

    project_id, character_id, _ = project_and_character
    cand_a = _make_asset(db, project_id, tag="cand_a")
    cand_b = _make_asset(db, project_id, tag="cand_b")
    cand_c = _make_asset(db, project_id, tag="cand_c")

    # Simulate batch generation: pack auto-attached the FIRST completed
    # candidate (cand_a) as roleAssets.hero_identity.
    role_assets = {"hero_identity": cand_a}
    role_assets.update({role: _make_asset(db, project_id, tag=role) for role in COVERAGE_ROLES})
    _seed_pack(db, project_id, character_id, role_assets=role_assets)
    _approve_concept(db, project_id, character_id)

    # Owner approves a DIFFERENT candidate (cand_c).
    approved = approve_character_candidate(
        db,
        project_id,
        character_id,
        asset_id=cand_c,
        reference_role="hero_identity",
        source_type="generation",
    )
    assert approved["canonical"] is True

    result = owner_approve_visual_sheet_gates(db, project_id, character_id, approved_by="owner")
    assert result["ok"] is True

    # Gate hero_identity points at the approved candidate.
    gates = list_gates(db, project_id, character_id)
    assert gates["gates"]["hero_identity"]["assetIds"] == [cand_c]

    # Canonical reference agrees.
    assert resolve_approved_reference(db, character_id, "hero_identity") == cand_c

    # Pack roleAssets agrees (approve_character_candidate syncs it).
    pack = _load_pack_raw(db, character_id)
    assert pack["roleAssets"]["hero_identity"] == cand_c


# 5. CDX-007 — approve-candidate with absent/foreign/non-image asset -> typed 4xx,
#    no canonical row.
def test_approve_candidate_rejects_absent_and_foreign_asset(client: TestClient, db: Session, project_and_character):
    project_id, character_id, _ = project_and_character

    r = client.post(
        f"/api/projects/{project_id}/characters/{character_id}/approve-candidate",
        json={"assetId": "does-not-exist", "referenceRole": "hero_identity"},
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"]["code"] == "ASSET_NOT_FOUND"

    other_pid = f"other-{uuid.uuid4().hex[:8]}"
    db.merge(Project(id=other_pid, name="Other Project"))
    db.commit()
    foreign = _make_asset(db, other_pid, tag="foreign")
    r2 = client.post(
        f"/api/projects/{project_id}/characters/{character_id}/approve-candidate",
        json={"assetId": foreign, "referenceRole": "hero_identity"},
    )
    assert r2.status_code == 400, r2.text
    assert r2.json()["detail"]["code"] == "ASSET_NOT_IN_PROJECT"

    # No canonical row was created by either attempt.
    assert resolve_approved_reference(db, character_id, "hero_identity") is None


def test_attach_reference_rejects_absent_and_non_image_asset(client: TestClient, db: Session, project_and_character):
    project_id, character_id, _ = project_and_character

    r = client.post(
        f"/api/projects/{project_id}/characters/{character_id}/references",
        json={"asset_id": "nope", "reference_role": "full_body_front", "source_type": "upload"},
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"]["code"] == "ASSET_NOT_FOUND"

    non_img = str(uuid.uuid4())
    db.add(
        Asset(
            id=non_img,
            project_id=project_id,
            tag="audio",
            kind="audio",
            filename="clip.mp3",
            path="clip.mp3",
        )
    )
    db.commit()
    r2 = client.post(
        f"/api/projects/{project_id}/characters/{character_id}/references",
        json={"asset_id": non_img, "reference_role": "full_body_front", "source_type": "upload"},
    )
    assert r2.status_code == 400, r2.text
    assert r2.json()["detail"]["code"] == "ASSET_NOT_IMAGE"


# 6. CDX-008 — pack status is not OWNER_APPROVED while detail/performance gates
#    have no assets.
def test_pack_status_not_owner_approved_while_gates_pending(db: Session, project_and_character):
    from app.character_identity.visual_sheet import _load_pack_raw, owner_approve_visual_sheet_gates

    project_id, character_id, _ = project_and_character
    role_assets: dict[str, str] = {"hero_identity": _make_asset(db, project_id, tag="hero_identity")}
    role_assets.update({role: _make_asset(db, project_id, tag=role) for role in COVERAGE_ROLES})
    _seed_pack(db, project_id, character_id, role_assets=role_assets)

    _approve_concept(db, project_id, character_id)
    result = owner_approve_visual_sheet_gates(db, project_id, character_id, approved_by="owner")

    assert result["status"] == "OWNER_APPROVED_WITH_PENDING"
    assert "detail" in result["pendingGates"]
    assert "performance" in result["pendingGates"]
    assert "hero_identity" not in result["pendingGates"]

    pack = _load_pack_raw(db, character_id)
    assert pack["status"] == "OWNER_APPROVED_WITH_PENDING"
    assert pack["status"] != "OWNER_APPROVED"
    assert set(pack["pendingGates"]) == {"detail", "performance"}


def test_pack_status_owner_approved_when_all_gates_have_assets(db: Session, project_and_character):
    from app.character_identity.visual_sheet import _load_pack_raw, owner_approve_visual_sheet_gates

    project_id, character_id, _ = project_and_character
    _seed_pack(db, project_id, character_id, role_assets=_full_role_assets(db, project_id))
    _approve_concept(db, project_id, character_id)

    result = owner_approve_visual_sheet_gates(db, project_id, character_id, approved_by="owner")
    assert result["status"] == "OWNER_APPROVED"
    assert result["pendingGates"] == []

    pack = _load_pack_raw(db, character_id)
    assert pack["status"] == "OWNER_APPROVED"

"""Character Creator Co-Director specialist scaffold (M3.3 Phase 2)."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy.orm import Session

from app.db import Project, Scene, SessionLocal, init_db
from app.feature_flags import FeatureFlags
from app.character_identity.schemas import CharacterProfileCreate, CharacterProfileUpdate, VoiceProfileCreate

HITCHHIKER_PROJECT = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
HITCHHIKER_LTX = "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f"
HITCHHIKER_TEST2 = "e277e621-189d-471e-b435-f01620f03d0d"


def _apply_flags_in_place(environ: dict[str, str] | os._Environ | None = None) -> None:
    from dataclasses import fields as dataclass_fields

    import app.feature_flags as ff

    refreshed = FeatureFlags.from_env(environ if environ is not None else os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))


@pytest.fixture()
def enable_m33(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    _apply_flags_in_place(os.environ)
    yield
    _apply_flags_in_place(os.environ)


@pytest.fixture()
def db(enable_m33) -> Session:
    init_db()
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def project_id(enable_m33, db: Session):
    init_db()
    from app.character_identity import ensure_character_identity_tables

    ensure_character_identity_tables()
    pid = f"cc-{uuid.uuid4().hex[:10]}"
    session = SessionLocal()
    session.merge(Project(id=pid, name="Character Creator Test"))
    session.commit()
    session.close()
    return pid


def test_character_creator_agent_registered():
    from app.codirector.intelligence.contracts import get_contract
    from app.codirector.intelligence.specialist_registry import SpecialistRegistry
    from app.codirector.tools import registry as tool_registry
    from app.codirector.tools.definitions import TOOL_IDS

    reg = SpecialistRegistry()
    assert "character-creator" in reg.ids()
    definition = reg.require("character-creator")
    assert definition.display_name == "Character Creator"
    assert definition.may_propose_tools is True
    assert definition.may_execute_tools is False

    contract = get_contract("character-creator")
    assert contract is not None
    assert contract.approval_required is True
    assert "readinessReport" in contract.output_keys

    for tid in (
        "character_creator.create_from_brief",
        "character_creator.create_from_script",
        "character_creator.audit_profile",
        "character_creator.inspect_readiness",
        "character_creator.build_reference_plan",
        "character_creator.build_expression_plan",
        "character_creator.build_pose_plan",
        "character_creator.build_voice_plan",
        "character_creator.build_wardrobe_plan",
        "character_creator.build_continuity_plan",
        "character_creator.propose_traits",
        "character_creator.propose_relationships",
        "character_creator.submit_for_review",
    ):
        assert tid in TOOL_IDS, tid
        assert tool_registry.find(tid) is not None


def test_create_character_intent_routes_character_creator():
    from app.codirector.intelligence.schemas import IntentClassification
    from app.codirector.intelligence.specialist_selector import SpecialistSelector

    sel = SpecialistSelector().select(
        IntentClassification(primaryIntent="create_character", complexity="standard", confidence=0.9)
    )
    assert "character-creator" in sel.all_selected
    assert "storyteller" in sel.all_selected
    assert "casting-director" in sel.all_selected
    assert "bible-manager" in sel.all_selected


def test_create_from_brief_creates_draft_with_provenance(db, project_id: str):
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import character_creator as cc

    ctx = ToolContext(db=db, project_id=project_id)
    result = cc.apply_create_from_brief(
        ctx,
        {
            "name": "Korri Test",
            "brief": "A resourceful engineer with warm eyes and practical wardrobe.",
            "role": "lead",
        },
    )
    assert result["ok"] is True
    assert result["provenance"] == "PROPOSED_BY_CHARACTER_CREATOR"
    profile = result["profile"]
    assert profile["status"] in ("DRAFT", "INCOMPLETE")
    assert profile["approval_status"] == "draft"
    traits = result["traits"]
    assert any(t.get("provenance") == "PROPOSED_BY_CHARACTER_CREATOR" for t in traits)
    assert any(t.get("key") == "source_brief" for t in traits)


def test_submit_for_review_does_not_approve(db, project_id: str):
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import character_creator as cc

    ctx = ToolContext(db=db, project_id=project_id)
    created = cc.apply_create_from_brief(
        ctx,
        {"name": "Review Me", "brief": "A character awaiting review.", "role": "supporting"},
    )
    cid = created["profile"]["id"]
    result = cc.apply_submit_for_review(ctx, {"characterId": cid})
    assert result["approvalStatus"] == "review"
    assert result["status"] != "APPROVED"
    assert "NOT approved" in result["note"]


def test_locked_mutation_rejected(db, project_id: str):
    from app.character_identity import service as ci
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import character_creator as cc

    ctx = ToolContext(db=db, project_id=project_id)
    created = cc.apply_create_from_brief(
        ctx,
        {"name": "Locked Char", "brief": "Will be locked.", "role": "lead"},
    )
    cid = created["profile"]["id"]
    versions = ci.list_versions(db, project_id, cid)
    vid = versions[0]["id"]
    ci.approve_version(db, project_id, cid, vid)
    ci.lock_version(db, project_id, cid, vid)

    with pytest.raises(Exception) as exc:
        cc.apply_propose_traits(
            ctx,
            {
                "characterId": cid,
                "traits": [{"category": "personality", "key": "trait", "value": "brave"}],
            },
        )
    assert "LOCKED" in str(exc.value).upper() or "locked" in str(exc.value).lower()


def test_hitchhiker_ids_untouched_by_character_creator_tools(db, enable_m33):
    from app.character_identity import ensure_character_identity_tables
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import character_creator as cc

    init_db()
    ensure_character_identity_tables()
    session = SessionLocal()
    session.merge(Project(id=HITCHHIKER_PROJECT, name="Hitchhiker PROTECTED"))
    for sid, name in ((HITCHHIKER_LTX, "LTX Shot1 PROTECTED"), (HITCHHIKER_TEST2, "Test2 PROTECTED")):
        existing = session.get(Scene, sid)
        if not existing:
            session.merge(
                Scene(
                    id=sid,
                    project_id=HITCHHIKER_PROJECT,
                    index=0 if sid == HITCHHIKER_LTX else 1,
                    name=name,
                    prompt="PROTECTED",
                    duration_sec=5.0,
                )
            )
    session.commit()
    before = {
        sid: (session.get(Scene, sid).name, session.get(Scene, sid).prompt)
        for sid in (HITCHHIKER_LTX, HITCHHIKER_TEST2)
    }
    session.close()

    disposable = f"cc-disp-{uuid.uuid4().hex[:8]}"
    session = SessionLocal()
    session.merge(Project(id=disposable, name="CC disposable"))
    session.commit()
    session.close()

    ctx = ToolContext(db=db, project_id=disposable)
    cc.apply_create_from_brief(ctx, {"name": "Safe Char", "brief": "Disposable project only.", "role": "cert"})

    with pytest.raises(ValueError, match="Hitchhiker"):
        cc.apply_create_from_brief(
            ToolContext(db=db, project_id=HITCHHIKER_PROJECT),
            {"name": "Bad", "brief": "Should fail.", "role": "cert"},
        )

    session = SessionLocal()
    after = {
        sid: (session.get(Scene, sid).name, session.get(Scene, sid).prompt)
        for sid in (HITCHHIKER_LTX, HITCHHIKER_TEST2)
    }
    session.close()
    assert after == before


def test_inspect_readiness_includes_category_readiness(db, project_id: str):
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import character_creator as cc

    ctx = ToolContext(db=db, project_id=project_id)
    created = cc.apply_create_from_brief(
        ctx,
        {"name": "Ready Check", "brief": "Incomplete character.", "role": "lead"},
    )
    cid = created["profile"]["id"]
    result = asyncio.run(cc.inspect_readiness(ctx, {"characterId": cid}))
    assert result["ok"] is True
    readiness = result["readiness"]
    categories = {c["category"] for c in readiness.get("category_readiness") or []}
    assert "VisualIdentity" in categories
    assert "ProductionReadiness" in categories
    assert readiness.get("score", 1.0) < 1.0


def test_critical_blockers_cap_score(db, project_id: str):
    from app.character_identity import service as ci
    from app.character_identity.schemas import VoiceProfileCreate

    created = ci.create_profile(
        db,
        project_id,
        CharacterProfileCreate(
            name="Clone No Consent",
            role="lead",
            description="Voice clone without consent",
        ),
    )
    vp = ci.create_voice_profile(
        db,
        project_id,
        created.id,
        VoiceProfileCreate(name="Clone draft", source_mode="CLONE"),
    )
    ci.update_profile(
        db,
        project_id,
        created.id,
        CharacterProfileUpdate(active_voice_profile_id=vp["id"]),
    )
    cov = ci.coverage(db, project_id, created.id)
    assert cov.critical_blockers
    assert cov.score <= 0.49

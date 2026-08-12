"""M42 W43 — Character Creator Completion / Korri certification tests."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Asset, Base, Project
from app.character_identity import models as _ci_models  # noqa: F401
from app.character_identity import service
from app.character_identity.canon import korri_v1
from app.character_identity.prompt_package import generate_prompt_package
from app.character_identity.promotion import promote_canonical
from app.character_identity.visual_gates import default_korri_directions
from app.m42_w43.production_gate import evaluate_m42_character_creator_gate


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    # Ensure W43 columns exist even if metadata order differs
    with engine.connect() as conn:
        for col, default in (
            ("motion_json", "'{}'"),
            ("emotion_json", "'{}'"),
            ("relationships_json", "'[]'"),
            ("prompt_package_json", "'{}'"),
        ):
            try:
                conn.execute(text(f"ALTER TABLE character_profiles ADD COLUMN {col} TEXT DEFAULT {default}"))
                conn.commit()
            except Exception:
                pass
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-w43", name="W43 Test"))
    session.add(
        Asset(
            id="asset-hero",
            project_id="proj-w43",
            tag="korri_sheet",
            kind="image",
            filename="korri.png",
            path="korri.png",
        )
    )
    session.commit()
    yield session
    session.close()


def test_korri_canon_locked_traits():
    c = korri_v1()
    hair = (c.get("appearance") or {}).get("hair") or {}
    assert hair.get("primary_color") == "black"
    assert "twin" in (hair.get("canonical_style") or "").lower()
    assert (c.get("appearance") or {}).get("eyes") == "purple"
    assert "blonde" in " ".join(c.get("forbidInvention") or []).lower()
    assert len(c.get("relationships") or []) >= 6
    assert (c.get("motion") or {}).get("energyLevel")
    perf = c.get("performance") or {}
    assert perf.get("speakingCadence")
    assert len(perf.get("signatureMannerisms") or []) >= 4
    anadriya = next(r for r in c["relationships"] if r["targetCharacter"] == "Anadriya")
    assert anadriya.get("communicationStyle")
    assert anadriya.get("authorityBalance")
    assert anadriya.get("protectiveness")


def test_directions_respect_locked_identity():
    dirs = default_korri_directions()
    assert len(dirs) >= 3
    blob = str(dirs).lower()
    assert "black" in blob and "twin" in blob
    assert "blonde" not in blob or "must not" in blob


def test_seed_korri_motion_relationships(db):
    profile = service.seed_korri_from_canon(db, "proj-w43")
    assert profile.slug == "korri"
    assert (profile.hair or {}).get("primary_color") == "black"
    assert (profile.skin or {}).get("skin_tone") == "pale"
    assert profile.motion.get("idleTendencies")
    assert profile.performance.get("speakingCadence")
    assert profile.performance.get("signatureMannerisms")
    assert len(profile.relationships) >= 6
    targets = {r.get("targetCharacter") for r in profile.relationships}
    assert "Anadriya" in targets
    assert "Hunter" in targets
    anadriya = next(r for r in profile.relationships if r.get("targetCharacter") == "Anadriya")
    assert anadriya.get("protectiveness")
    assert anadriya.get("authorityBalance")


def test_prompt_package_no_invention():
    pkg = generate_prompt_package(
        {
            "name": "Korri",
            "role": "Sass Queen",
            "hair": {"primary_color": "black", "canonical_style": "twin ponytails"},
            "skin": {"skin_tone": "pale", "tattoos": "circuit tattoos"},
            "motion": {"walkingStyle": "light-footed", "energyLevel": "high"},
            "emotion": {"sarcasmBehavior": "dry teasing"},
            "performance": {
                "speakingCadence": "Responds quickly with little hesitation",
                "humorStyle": "Sarcasm and dry teasing",
                "signatureMannerisms": ["Smirks before sarcastic remarks"],
            },
            "personality": {"core_personality": "mischievous"},
            "relationships": [
                {
                    "targetCharacter": "Anadriya",
                    "relationship": "Sister",
                    "tone": "teasing",
                    "communicationStyle": "Playful teasing",
                    "protectiveness": "Very high",
                    "authorityBalance": "Rejects authority publicly, accepts guidance privately",
                }
            ],
            "continuity": {"locked_features": ["black hair"], "forbid_invention": ["blonde hair"]},
            "wardrobe": {"description": "handmade black cloth"},
        }
    )
    assert "Korri" in pkg["imagePrompt"]
    assert "black" in pkg["imagePrompt"].lower()
    assert pkg["motionPrompt"]
    assert pkg["performancePrompt"]
    assert "Responds quickly" in pkg["performancePrompt"]
    assert pkg["voicePrompt"]
    assert "Anadriya" in pkg["referenceSummary"]
    assert "protectiveness" in pkg["referenceSummary"].lower() or "Very high" in pkg["referenceSummary"]


def test_promote_freezes_prompt_package(db):
    profile = service.seed_korri_from_canon(db, "proj-w43")
    # Attach hero ref
    from app.character_identity.schemas import ReferenceAttach

    service.attach_reference(
        db,
        "proj-w43",
        profile.id,
        ReferenceAttach(asset_id="asset-hero", reference_role="hero_identity", canonical=True),
    )
    result = promote_canonical(db, "proj-w43", profile.id, approved_by="owner")
    assert result["ok"] is True
    assert result["promptPackage"]["imagePrompt"]
    refreshed = service.get_profile(db, "proj-w43", profile.id)
    assert refreshed.approval_status == "approved"
    assert refreshed.prompt_package.get("referenceSummary")


def test_gate_structure():
    g = evaluate_m42_character_creator_gate()
    assert "characterCreatorGo" in g
    assert g["binaryOnly"] is True
    assert g["conditionalGoForbidden"] is True
    assert "korriGeneratedImageProfileOperational" in g["flags"]
    assert "korriVoiceCreatorWorkspaceOperational" in g["flags"]
    assert "korriVoiceNoMockData" in g["flags"]


def test_voice_design_brief_not_baritone():
    from app.character_identity.voice_creator import KORRI_DESIGN_BRIEF, compile_design_prompt

    prompt = compile_design_prompt(KORRI_DESIGN_BRIEF, character_name="Korri")
    assert "Young adult" in prompt
    assert "baritone" not in prompt.lower()
    assert "sarcasm" in prompt.lower()
    assert KORRI_DESIGN_BRIEF["perceivedAge"] == "Young adult"


def test_voice_workspace_methods(db):
    from app.character_identity.voice_creator import get_voice_workspace

    profile = service.seed_korri_from_canon(db, "proj-w43")
    ws = get_voice_workspace(db, "proj-w43", profile.id)
    assert ws["mock"] is False
    assert ws["performanceAttached"] is True
    assert ws["emotionAttached"] is True
    methods = {m["id"]: m for m in ws["methods"]}
    assert "DESIGN" in methods
    assert "CLONE" in methods
    assert methods["CLONE"]["consentRequired"] is True
    preview = __import__("app.character_identity.voice_creator", fromlist=["preview_voice_design"]).preview_voice_design(
        db, "proj-w43", profile.id
    )
    assert preview["provider"] == "qwen3-tts"
    assert "baritone" not in (preview.get("compiledVoiceDescription") or "").lower()


def test_prompt_package_voice_fields():
    pkg = generate_prompt_package(
        {
            "name": "Korri",
            "role": "Sass Queen",
            "performance": {"speakingCadence": "Fast"},
            "emotion": {"sarcasmBehavior": "dry"},
            "active_voice": {
                "id": "v1",
                "voice_design_prompt": "playful sarcastic young adult",
                "perceived_age": "Young adult",
                "source_mode": "DESIGN",
                "provider": "qwen3-tts",
                "pronunciations": [{"word": "Handari", "phonetic": "han-DAH-ree"}],
                "reactions": [{"id": "laugh", "label": "short amused laugh", "status": "ready"}],
            },
        }
    )
    assert "playful" in pkg["voicePrompt"].lower() or "young adult" in pkg["voicePrompt"].lower()
    assert "Handari" in pkg["pronunciationSummary"]
    assert "laugh" in pkg["reactionSummary"].lower() or "amused" in pkg["reactionSummary"].lower()
    assert "do not invent" in pkg["providerTranslationHints"].lower()


def test_character_sheet_role_map():
    from app.workflows.image_tools import CHARACTER_SHEET_ROLE_MAP, CHARACTER_SHEET_VIEWS

    assert CHARACTER_SHEET_ROLE_MAP["front"] == "full_body_front"
    assert CHARACTER_SHEET_ROLE_MAP["back_closeup"] == "closeup_back"
    keys = {v["key"] for v in CHARACTER_SHEET_VIEWS}
    assert "back_closeup" in keys
    assert set(CHARACTER_SHEET_ROLE_MAP) <= keys


def test_visual_sheet_start_enqueues_hero(db):
    from app.character_identity.visual_sheet import get_visual_sheet_pack, start_visual_sheet_generation
    from app.db import Job

    profile = service.seed_korri_from_canon(db, "proj-w43")
    pack = start_visual_sheet_generation(db, "proj-w43", profile.id, include_details=True)
    assert pack["status"] == "GENERATING"
    assert pack.get("mock") is False
    assert "hero" in (pack.get("jobs") or {})
    job_id = pack["jobs"]["hero"]["jobId"]
    job = db.get(Job, job_id)
    assert job is not None
    assert job.kind in ("imagegen", "imagegen_edit")
    stored = get_visual_sheet_pack(db, "proj-w43", profile.id)
    assert stored.get("characterId") == profile.id

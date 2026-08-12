#!/usr/bin/env python3
"""Create Korri Character Profile from written brief only (M3.3j creation test).

Does NOT import or inspect any Korri character sheet. Only media allowed later:
voice/Korri_Voice_Sample.mp3. Visuals start as PROPOSED_BY_CHARACTER_CREATOR.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))
os.environ.setdefault("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")

from app.db import SessionLocal, init_db  # noqa: E402
from app.character_identity import ensure_character_identity_tables, service as ci  # noqa: E402
from app.character_identity.models import CharacterProfileRow  # noqa: E402
from app.character_identity.schemas import (  # noqa: E402
    CharacterProfileCreate,
    CharacterProfileUpdate,
    TraitUpsert,
    VoiceProfileCreate,
    WardrobeCreate,
)
from app.character_identity.visual_gates import propose_visual_directions  # noqa: E402
from app.db import Project  # noqa: E402
import uuid  # noqa: E402

OUT = ROOT / "artifacts" / "m33" / "korri-character-profile"
BRIEF_PATH = ROOT / "artifacts" / "m33" / "korri-character-profile" / "korri-brief.txt"
# Creator-first: one project, one library — reuse instead of disposable projects per run.
STABLE_PROJECT_NAME = os.environ.get("ADEPT_KORRI_PROJECT_NAME", "Korri Character Production")
STABLE_PROJECT_ID = os.environ.get("ADEPT_PROJECT_ID", "").strip()

KORRI_BRIEF = """Korri is the biological sister of Anadriya in The Adept Chronicles (Providence).
She was created through etheric procreation involving Megan and Lar through Anadriya’s energetic field.
Although she appears approximately eighteen years old, her origin is unusual.
She is a Human / Sun Sprite Elf hybrid, a principal character, and Anadriya’s emotional counterweight.
Korri is highly intelligent, intensely present, irreverent, restless, emotionally transparent, and naturally rebellious.
She is funny, sarcastic, cheeky, and provocative — informally the “Sass Queen” — but not cruel by nature.
She challenges Anadriya’s seriousness and planning while remaining capable of deep affection and loyalty.
She must not be depicted as a child, sexualized, or as a duplicate of Anadriya.
Exact eye color, hair color, wardrobe colors, and markings are NOT established by this brief and must remain proposed until owner approval.
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    BRIEF_PATH.write_text(KORRI_BRIEF, encoding="utf-8")
    init_db()
    ensure_character_identity_tables()
    db = SessionLocal()
    try:
        existing = None
        if STABLE_PROJECT_ID:
            existing = db.get(Project, STABLE_PROJECT_ID)
            if existing is None:
                raise RuntimeError(f"ADEPT_PROJECT_ID={STABLE_PROJECT_ID} not found")
        else:
            existing = (
                db.query(Project).filter(Project.name == STABLE_PROJECT_NAME).order_by(Project.created_at.asc()).first()
            )
        if existing is not None:
            project_id = existing.id
            project_created = False
        else:
            project_id = str(uuid.uuid4())
            db.add(
                Project(
                    id=project_id,
                    name=STABLE_PROJECT_NAME,
                    created_at=_now_dt(),
                    updated_at=_now_dt(),
                )
            )
            db.commit()
            project_created = True
        print(
            f"[korri-create] using project {project_id} "
            f"({STABLE_PROJECT_NAME!r}, created={project_created})"
        )

        existing_korri = (
            db.query(CharacterProfileRow)
            .filter(CharacterProfileRow.project_id == project_id, CharacterProfileRow.slug == "korri")
            .first()
        )
        if existing_korri is not None:
            profile = ci.get_profile(db, project_id, existing_korri.id)
        else:
            profile = ci.create_profile(
                db,
                project_id,
                CharacterProfileCreate(
                    name="Korri",
                    slug="korri",
                    role="Principal — Anadriya’s biological sister / emotional counterweight",
                    description=KORRI_BRIEF.strip(),
                ),
            )
        ci.upsert_trait(
            db,
            project_id,
            profile.id,
            TraitUpsert(category="brief", key="source_brief", value=KORRI_BRIEF.strip(), provenance="PROPOSED_BY_CHARACTER_CREATOR"),
        )
        # Structured personality / performance / continuity (proposed)
        personality = {
            "core_personality": "Irreverent, spontaneous, highly intelligent, emotionally transparent, rebellious, funny, affectionate beneath provocation.",
            "strengths": "Notices emotional truth; challenges false composure; adapts rapidly; creates connection through humor.",
            "flaws": "Poor restraint; insensitive timing; impatience; provocation; impulsive decisions.",
            "fears": "Being controlled; treated as artificial; abandoned; forced into a role; compared unfavorably to Anadriya.",
            "motivations": "Understand who she is; experience life directly; remain free; connect with Anadriya.",
            "values": "Authenticity; presence; freedom; emotional truth; loyalty.",
            "when_calm": "Observes everything; spontaneous comments; teases people she likes.",
            "when_angry": "Direct rather than eloquent; interrupts; rejects patronizing.",
            "around_loved": "With Anadriya: teases, challenges seriousness, seeks closeness while pretending not to.",
            "speech_style": "Fast when excited; direct; informal; playful; capable of sudden emotional depth.",
        }
        performance = {
            "posture": "Relaxed, asymmetrical, informal; weight frequently shifts.",
            "gait": "Energetic; variable pace; sudden directional changes.",
            "eye_contact_behavior": "Strong when challenging; playful when teasing; brief avoidance when hurt.",
            "gestures": "Frequent hand movement; pointing; broad illustrative gestures.",
            "personal_space_behavior": "Loose boundaries with trusted people; moves close during teasing.",
            "reaction_style": "Immediate; readable; emotionally fast; often verbal.",
        }
        continuity = {
            "locked_features": [
                "young adult not child",
                "not visual duplicate of Anadriya",
                "subtle familial resemblance allowed",
                "humor must not erase intelligence",
                "not reduced to comic relief",
                "not sexualized",
            ],
            "forbid_invention": ["exact eye color", "exact hair color", "scars/tattoos without approval"],
            "notes": "Visual specifics remain PROPOSED_BY_CHARACTER_CREATOR until owner approval.",
        }
        ci.update_profile(
            db,
            project_id,
            profile.id,
            CharacterProfileUpdate(
                personality=personality,
                performance=performance,
                continuity=continuity,
                physical={
                    "apparent_age": "approximately 18 young adult",
                    "species": "Human / Sun Sprite Elf hybrid",
                    "heritage_note": "Unusual etheric origin; spiritually unusual without ceremonial distance.",
                    "provenance": "PROPOSED_BY_CHARACTER_CREATOR",
                },
            ),
        )
        if existing_korri is None:
            for look in (
                ("Korri Providence Default", "Organic practical youthful primary outfit; freer than Anadriya."),
                ("Korri Travel", "Practical layered mobile weather-aware."),
                ("Korri Ceremonial", "More formal than she prefers; may be worn slightly incorrectly."),
                ("Korri Earth Adaptation", "Curious experimental human-world combinations."),
            ):
                ci.create_wardrobe(
                    db,
                    project_id,
                    profile.id,
                    WardrobeCreate(name=look[0], description=look[1], continuity_rules="Proposed until owner approval."),
                )
        voices = ci.list_voice_profiles(db, project_id, profile.id)
        if voices:
            voice = voices[0]
        else:
            voice = ci.create_voice_profile(
                db,
                project_id,
                profile.id,
                VoiceProfileCreate(
                    name="Korri Voice (pending clone)",
                    source_mode="CLONE",
                    provider="qwen_voice_clone",
                    model_id="Qwen/Qwen3-TTS-12Hz-1.7B-Base",
                    pitch_description="youthful adult female",
                    pace_description="quick lively",
                    tone_description="playful irreverent; capable of vulnerability",
                    pronunciation_notes="UPLOAD_PENDING until voice/Korri_Voice_Sample.mp3 validated + consent. DRAFT only.",
                ),
            )
        ci.upsert_trait(
            db,
            project_id,
            profile.id,
            TraitUpsert(
                category="relationships",
                key="Anadriya",
                value="biological sister; emotional mirror; counterbalance; loyalty beneath teasing",
                provenance="PROPOSED_BY_CHARACTER_CREATOR",
            ),
        )
        directions = propose_visual_directions(db, project_id, profile.id)
        evidence = {
            "createdAt": _now_iso(),
            "projectId": project_id,
            "projectName": STABLE_PROJECT_NAME,
            "projectReused": not project_created,
            "stableProjectPolicy": "one-project-one-library",
            "characterId": profile.id,
            "activeVersionId": profile.active_version_id,
            "voiceProfileId": voice["id"],
            "briefPath": str(BRIEF_PATH),
            "visualDirections": directions,
            "mediaConstraint": "Only voice/Korri_Voice_Sample.mp3 may be supplied; no character sheet.",
            "provenance": "PROPOSED_BY_CHARACTER_CREATOR",
        }
        (OUT / "korri-profile-create.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

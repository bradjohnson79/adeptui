"""Owner visual approval gates for Character Creator (M3.3j).

Character Creator never self-approves. Gates promote provenance:
  PROPOSED_BY_CHARACTER_CREATOR → USER_CONFIRMED → CANONICAL_FROM_USER_APPROVAL
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from . import service
from .models import CharacterTraitRow
from .schemas import TraitUpsert

PROPOSED = "PROPOSED_BY_CHARACTER_CREATOR"
USER_CONFIRMED = "USER_CONFIRMED"
CANONICAL = "CANONICAL_FROM_USER_APPROVAL"

GATE_ORDER = (
    "concept",
    "hero_identity",
    "turnaround",
    "facial",
    "detail",
    "performance",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_trait(db: Session, character_id: str, key: str) -> CharacterTraitRow | None:
    return (
        db.query(CharacterTraitRow)
        .filter(CharacterTraitRow.character_profile_id == character_id, CharacterTraitRow.key == key)
        .order_by(CharacterTraitRow.id.desc())
        .first()
    )


def _generic_profile_directions(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Profile-derived concept directions for non-Korri characters (CDX-002).

    The Korri lock strings (black twin ponytails / purple eyes / Sun Sprite
    Elf / wild_sun_sprite) must never leak into another character's concept
    gate. Directions are generated from the actual Character Profile fields.
    """
    name = (profile.get("name") or "").strip() or "this character"
    slug = re.sub(r"[^a-z0-9]+", "-", (profile.get("slug") or "").lower()).strip("-") or "character"
    visual = (profile.get("visual_description") or "").strip()
    species = (profile.get("species_or_type") or "").strip()
    age = (profile.get("apparent_age") or "").strip()
    gender = (profile.get("gender_presentation") or "").strip()
    hair = profile.get("hair") or {}
    skin = profile.get("skin") or {}
    hair_color = (hair.get("primary_color") or "").strip()
    hair_style = (hair.get("canonical_style") or "").strip()
    skin_tone = (skin.get("skin_tone") or "").strip()
    traits = [x for x in (age, species, gender, hair_color, hair_style, skin_tone) if x]
    profile_traits = "; ".join(traits) if traits else "as described in the Character Profile"
    hair_summary = " ".join(x for x in (hair_color, hair_style) if x).strip() or "the profile's hair"
    brief = visual or profile_traits
    id_prefix = slug

    def _distinguishing() -> list[str]:
        return [brief, "consistent facial features, no invented identity traits"]

    return [
        {
            "id": f"{id_prefix}-grounded",
            "name": "Grounded Classic",
            "emphasis": [
                "faithful, believable everyday presence",
                "natural pose and soft studio lighting",
                "identity readable at a glance",
                "minimal styling interference",
            ],
            "hairstyleProposal": f"Retain {hair_summary} with simple, consistent styling.",
            "wardrobeProposal": "Wardrobe consistent with the character's role and story; no fabric/era drift.",
            "heritageTraits": [species] if species else ["as described in the profile"],
            "distinguishingFeatures": _distinguishing(),
            "strengths": "Communicates the profile faithfully and grounds the character.",
            "continuityRisks": "Must not drift from the appearance described in the Character Profile.",
            "reason": f"Balanced concept for {name} derived from the Character Profile.",
            "provenance": PROPOSED,
        },
        {
            "id": f"{id_prefix}-cinematic",
            "name": "Cinematic Presence",
            "emphasis": [
                "stronger contrast and directed lighting",
                "slightly elevated dramatic staging",
                "profile-faithful identity",
                "hero-like framing",
            ],
            "hairstyleProposal": f"Keep {hair_summary}; style with controlled volume and motion.",
            "wardrobeProposal": "Same wardrobe silhouette, presented with more contrast and texture detail.",
            "heritageTraits": [species] if species else ["as described in the profile"],
            "distinguishingFeatures": _distinguishing(),
            "strengths": "Best for key-art and hero-frame continuity.",
            "continuityRisks": "Lighting must not obscure identity-critical features.",
            "reason": f"Dramatic-but-faithful concept for {name}.",
            "provenance": PROPOSED,
        },
        {
            "id": f"{id_prefix}-editorial",
            "name": "Editorial Styling",
            "emphasis": [
                "stronger wardrobe/styling read",
                "fashion-presentation energy",
                "identity traits unchanged",
                "clean background for silhouette",
            ],
            "hairstyleProposal": f"Keep {hair_summary}; arranged with an intentional editorial finish.",
            "wardrobeProposal": "Refined styling of the profile wardrobe; no new identity elements.",
            "heritageTraits": [species] if species else ["as described in the profile"],
            "distinguishingFeatures": _distinguishing(),
            "strengths": "Useful for poster/merchandising continuity.",
            "continuityRisks": "Styling must not change hair color, eye color, or signature traits.",
            "reason": f"Editorial concept for {name} derived from the profile.",
            "provenance": PROPOSED,
        },
    ]


def propose_visual_directions(
    db: Session,
    project_id: str,
    character_id: str,
    directions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Store ≥3 proposed visual directions for Gate 1 (concept).

    CDX-002: directions are profile-derived for every character. The Korri
    lock directions are used ONLY for the actual Korri seed profile (slug
    "korri"). The concept gate is never auto-approved here — it stays
    AWAITING_OWNER until the owner explicitly selects a direction.
    """
    profile_out = service.get_profile(db, project_id, character_id)
    profile = profile_out.model_dump()
    if not directions or len(directions) < 3:
        if str(profile.get("slug") or "").lower() == "korri":
            directions = default_korri_directions()
        else:
            directions = _generic_profile_directions(profile)
    payload = {
        "gate": "concept",
        "status": "AWAITING_OWNER",
        "provenance": PROPOSED,
        "directions": directions,
        "selectedDirectionId": None,
        "createdAt": _now(),
    }
    service.upsert_trait(
        db,
        project_id,
        character_id,
        TraitUpsert(
            category="visual_gates",
            key="gate_concept",
            value=json.dumps(payload),
            provenance=PROPOSED,
        ),
    )
    return payload


def owner_select_concept(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    direction_id: str,
    approved_by: str = "owner",
    notes: str = "",
) -> dict[str, Any]:
    row = _get_trait(db, character_id, "gate_concept")
    if not row:
        raise ValueError("No concept directions proposed. Call propose_visual_directions first.")
    data = json.loads(row.value)
    ids = {d.get("id") for d in data.get("directions") or []}
    if direction_id not in ids and direction_id != "hybrid":
        raise ValueError(f"Unknown direction_id {direction_id}")
    data.update(
        {
            "status": "OWNER_APPROVED",
            "selectedDirectionId": direction_id,
            "approvedBy": approved_by,
            "approvedAt": _now(),
            "notes": notes,
            "provenance": USER_CONFIRMED,
        }
    )
    service.upsert_trait(
        db,
        project_id,
        character_id,
        TraitUpsert(
            category="visual_gates",
            key="gate_concept",
            value=json.dumps(data),
            provenance=USER_CONFIRMED,
        ),
    )
    return data


def set_gate_status(
    db: Session,
    project_id: str,
    character_id: str,
    gate: str,
    *,
    status: str,
    asset_ids: list[str] | None = None,
    approved_by: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    if gate not in GATE_ORDER:
        raise ValueError(f"Unknown gate {gate}")
    key = f"gate_{gate}"
    existing = _get_trait(db, character_id, key)
    data: dict[str, Any] = {}
    if existing:
        try:
            data = json.loads(existing.value)
        except Exception:
            data = {}
    data.update(
        {
            "gate": gate,
            "status": status,
            "assetIds": asset_ids or data.get("assetIds") or [],
            "updatedAt": _now(),
            "notes": notes or data.get("notes") or "",
        }
    )
    provenance = PROPOSED
    if status == "OWNER_APPROVED":
        if not approved_by:
            raise ValueError("approved_by is required for OWNER_APPROVED (Character Creator cannot self-approve).")
        data["approvedBy"] = approved_by
        data["approvedAt"] = _now()
        provenance = USER_CONFIRMED
        data["provenance"] = USER_CONFIRMED
    else:
        data["provenance"] = data.get("provenance") or PROPOSED
    service.upsert_trait(
        db,
        project_id,
        character_id,
        TraitUpsert(category="visual_gates", key=key, value=json.dumps(data), provenance=provenance),
    )
    return data


def promote_to_canonical(db: Session, project_id: str, character_id: str, version_id: str) -> dict[str, Any]:
    """After all gates owner-approved, mark visual traits canonical on approved version."""
    for gate in GATE_ORDER:
        row = _get_trait(db, character_id, f"gate_{gate}")
        if not row:
            raise ValueError(f"Missing gate {gate}")
        data = json.loads(row.value)
        if data.get("status") != "OWNER_APPROVED":
            raise ValueError(f"Gate {gate} is not OWNER_APPROVED")
        data["provenance"] = CANONICAL
        data["canonicalVersionId"] = version_id
        service.upsert_trait(
            db,
            project_id,
            character_id,
            TraitUpsert(
                category="visual_gates",
                key=f"gate_{gate}",
                value=json.dumps(data),
                provenance=CANONICAL,
            ),
        )
    return {"ok": True, "characterId": character_id, "versionId": version_id, "provenance": CANONICAL}


def list_gates(db: Session, project_id: str, character_id: str) -> dict[str, Any]:
    service.get_profile(db, project_id, character_id)
    gates = {}
    for gate in GATE_ORDER:
        row = _get_trait(db, character_id, f"gate_{gate}")
        if row:
            try:
                gates[gate] = json.loads(row.value)
            except Exception:
                gates[gate] = {"raw": row.value}
        else:
            gates[gate] = {"gate": gate, "status": "NOT_STARTED"}
    return {"characterId": character_id, "gates": gates}


def default_korri_directions() -> list[dict[str, Any]]:
    """Directions respect korri.v1 locked identity — style/motion variants only, no hair/eye/wardrobe rewrite."""
    locked = (
        "LOCKED: black twin ponytails, purple eyes, pale skin, pointed Sun Sprite Elf ears, "
        "wooden earrings, circuit/light tattoos, handmade black cloth wardrobe"
    )
    return [
        {
            "id": "wild_sun_sprite",
            "name": "Wild Sun Sprite",
            "emphasis": [
                "otherworldly Sun Sprite Elf heritage",
                "natural handmade materials",
                "kinetic twin-ponytail motion",
                "forest-compatible presence",
            ],
            "hairstyleProposal": "Retain black twin ponytails; freer flyaways reacting to motion (color/style locked).",
            "wardrobeProposal": "Retain uneven black cloth crop top, asymmetrical wraps, sash, brown sandals, wooden accessories.",
            "heritageTraits": ["pointed ears", "youthful adult hybrid presence"],
            "distinguishingFeatures": ["mischievous resting expression", "circuit/light tattoos", locked],
            "strengths": "Communicates heritage and spontaneity clearly.",
            "continuityRisks": "Must not recolor hair blonde or eyes aqua; no metallic wardrobe drift.",
            "reason": "Supports Korri’s restless energy while preserving korri.v1 canon.",
            "provenance": PROPOSED,
        },
        {
            "id": "rebellious_hybrid",
            "name": "Rebellious Hybrid",
            "emphasis": [
                "asymmetry in pose/stance",
                "self-fashioned handmade clothing attitude",
                "compact athletic energy",
                "irreverent Sass Queen attitude",
            ],
            "hairstyleProposal": "Black twin ponytails worn slightly imperfectly — construction locked.",
            "wardrobeProposal": "Same handmade black cloth set, styled more asymmetrically; no modern/metallic replacement.",
            "heritageTraits": ["human/Sun Sprite hybrid cues"],
            "distinguishingFeatures": ["weight-shifting posture", "hands on hips", locked],
            "strengths": "Maximizes contrast with Anadriya’s composed presence.",
            "continuityRisks": "Tattoo states may vary active/inactive only; wardrobe baseline locked.",
            "reason": "Matches Sass Queen irreverence without inventing a new identity.",
            "provenance": PROPOSED,
        },
        {
            "id": "sisterly_counterpoint",
            "name": "Sisterly Counterpoint",
            "emphasis": [
                "subtle familial resemblance to Anadriya in expression only",
                "stronger contrast in posture/energy",
                "immediate, less formal presence",
            ],
            "hairstyleProposal": "Black twin ponytails (locked) — freer arrangement than Anadriya’s composed style.",
            "wardrobeProposal": "Korri handmade aesthetic only — never Anadriya formal Adept styling.",
            "heritageTraits": ["familial resemblance without duplication"],
            "distinguishingFeatures": ["amused skeptical mouth", "teasing head tilt", locked],
            "strengths": "Best for sister-dynamic storytelling continuity.",
            "continuityRisks": "Must not visually duplicate Anadriya; hair/eyes/wardrobe remain Korri canon.",
            "reason": "Serves narrative role as Anadriya’s sister and emotional counterweight.",
            "provenance": PROPOSED,
        },
    ]

"""Certified promotion: CharacterProfile → VisualIdentity + Bible + relationships + Prompt Package."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import service
from .models import CharacterProfileRow, CharacterWardrobeRow
from .prompt_package import generate_prompt_package


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:80] or "character"


def promote_canonical(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    approved_by: str = "owner",
) -> dict[str, Any]:
    """Idempotent promotion — no invented traits; freezes Prompt Package; syncs Bible relationships."""
    row = db.get(CharacterProfileRow, character_id)
    if not row or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Character not found")

    profile_out = service.get_profile(db, project_id, character_id)
    profile = profile_out.model_dump()

    if row.active_wardrobe_id:
        w = db.get(CharacterWardrobeRow, row.active_wardrobe_id)
        if w:
            profile["wardrobe"] = {
                "name": w.name,
                "description": w.description,
                "colors": w.colors,
                "footwear": w.footwear,
                "accessories": w.accessories,
                "materials": w.materials,
            }

    package = generate_prompt_package(
        {**profile, "canon_version": "korri.v1" if (row.slug or "").lower() == "korri" else ""},
        character_version_id=row.active_version_id or "",
    )
    row.prompt_package_json = _dumps(package)
    row.approval_status = "approved"
    if row.status in ("DRAFT", "INCOMPLETE", "READY_FOR_GENERATION"):
        row.status = "APPROVED"
    row.updated_at = _now()
    db.flush()

    identity_error = None
    visual_identity_id = None
    try:
        from app.continuity import service as continuity_service
        from app.continuity.models import VisualIdentityRow

        existing = (
            db.query(VisualIdentityRow)
            .filter(
                VisualIdentityRow.project_id == project_id,
                VisualIdentityRow.character_profile_id == character_id,
            )
            .first()
        )
        if existing:
            visual_identity_id = existing.id
            existing.display_name = row.name
            existing.canonical_name = row.slug or row.name
            existing.description = row.description or row.role
            existing.updated_at = _now()
        else:
            created = continuity_service.create_identity(
                db,
                project_id,
                {
                    "identityType": "character",
                    "canonicalName": row.slug or row.name,
                    "displayName": row.name,
                    "description": row.description or row.role,
                    "characterProfileId": character_id,
                },
            )
            visual_identity_id = created.get("id")
            versions = continuity_service.list_versions(db, project_id, visual_identity_id)
            if versions:
                try:
                    continuity_service.approve_version(
                        db, project_id, versions[0]["id"], approved_by=approved_by
                    )
                except Exception:
                    pass
    except Exception as e:
        identity_error = str(e)

    bible_stable_id = None
    try:
        from app.codirector.bible.domain_service import BibleDomainService

        chars = BibleDomainService.list_by_type(db, project_id, "character")
        match = next(
            (
                c
                for c in chars
                if (c.get("data") or {}).get("characterProfileId") == character_id
                or (c.get("displayName") or "").lower() == row.name.lower()
            ),
            None,
        )
        hair = profile.get("hair") or {}
        skin = profile.get("skin") or {}
        data = {
            "description": row.description or row.role,
            "ageRange": row.apparent_age or "",
            "personality": (profile.get("personality") or {}).get("core_personality") or "",
            "appearanceSummary": (
                f"{hair.get('primary_color', '')} {hair.get('canonical_style', '')}, "
                f"{skin.get('skin_tone', '')} skin"
            ).strip(),
            "distinguishingFeatures": skin.get("tattoos") or "",
            "characterProfileId": character_id,
            "activeVoiceProfileId": row.active_voice_profile_id,
            "readiness": "production_ready",
            "notes": f"Promoted from Character Creator by {approved_by}",
        }
        if match:
            bible_stable_id = match.get("stableId")
            BibleDomainService.update_entity(
                db,
                project_id,
                str(bible_stable_id),
                display_name=row.name,
                data=data,
            )
        else:
            created = BibleDomainService.create_entity(
                db,
                project_id,
                entity_type="character",
                entity_key=_key(row.slug or row.name),
                display_name=row.name,
                data=data,
            )
            bible_stable_id = created.get("stableId")
        if visual_identity_id and bible_stable_id:
            from app.continuity.models import VisualIdentityRow

            vi = db.get(VisualIdentityRow, visual_identity_id)
            if vi:
                vi.bible_entity_stable_id = str(bible_stable_id)
    except Exception as e:
        if not identity_error:
            identity_error = f"bible:{e}"

    rels = _loads(row.relationships_json, [])
    synced_rels: list[dict[str, Any]] = []
    try:
        from app.codirector.bible.domain_service import BibleDomainService

        existing_rels = BibleDomainService.list_by_type(db, project_id, "relationship")
        for edge in rels:
            if not isinstance(edge, dict):
                continue
            target = edge.get("targetCharacter") or ""
            label = f"{row.name} → {target}: {edge.get('relationship') or 'related'}"
            desc = (
                f"tone={edge.get('tone')}; trust={edge.get('trust')}; "
                f"conflict={edge.get('conflict')}; physicalAggression={edge.get('physicalAggression')}; "
                f"comfortDistance={edge.get('comfortDistance')}; greeting={edge.get('typicalGreeting')}; "
                f"communicationStyle={edge.get('communicationStyle')}; humorStyle={edge.get('humorStyle')}; "
                f"conflictResolution={edge.get('typicalConflictResolution')}; "
                f"emotionalOpenness={edge.get('emotionalOpenness')}; "
                f"protectiveness={edge.get('protectiveness')}; "
                f"authorityBalance={edge.get('authorityBalance')}"
            )
            kind = "family" if "sister" in (edge.get("relationship") or "").lower() else "other"
            payload = {
                "fromStableId": str(bible_stable_id or ""),
                "toStableId": edge.get("targetStableId") or "",
                "kind": kind,
                "label": label,
                "description": desc,
                "asymmetric": True,
                "notes": _dumps(edge),
            }
            match = next(
                (r for r in existing_rels if (r.get("displayName") or "") == label),
                None,
            )
            if match:
                BibleDomainService.update_entity(
                    db, project_id, str(match.get("stableId")), display_name=label, data=payload
                )
                edge["bibleRelationshipId"] = match.get("stableId")
            else:
                created = BibleDomainService.create_entity(
                    db,
                    project_id,
                    entity_type="relationship",
                    entity_key=_key(f"{row.slug}-rel-{target}"),
                    display_name=label,
                    data=payload,
                )
                edge["bibleRelationshipId"] = created.get("stableId")
            synced_rels.append(edge)
        row.relationships_json = _dumps(synced_rels)
    except Exception:
        synced_rels = list(rels) if isinstance(rels, list) else []

    db.commit()
    db.refresh(row)

    return {
        "ok": True,
        "characterId": character_id,
        "visualIdentityId": visual_identity_id,
        "bibleStableId": bible_stable_id,
        "promptPackage": package,
        "relationshipsSynced": len(synced_rels),
        "identityError": identity_error,
        "approvedBy": approved_by,
        "promotedAt": _now(),
    }

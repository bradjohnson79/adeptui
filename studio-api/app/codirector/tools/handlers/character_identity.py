"""Co-Director tools for M3.3 Character Identity."""

from __future__ import annotations

from typing import Any

from ....character_identity import service as ci
from ....character_identity.schemas import CharacterProfileCreate
from .... import feature_flags as feature_flags_mod
from ..definitions import ToolContext, ToolPreview


def _require(ctx: ToolContext) -> None:
    if not feature_flags_mod.feature_flags.character_identity_v1:
        raise ValueError("Character Identity is disabled (STUDIO_FEATURE_CHARACTER_IDENTITY_V1).")
    if not ctx.project_id:
        raise ValueError("projectId is required")


def _feature_disabled_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "items": [],
        "count": 0,
        "_summary": "Character Identity feature is disabled.",
        "_unavailableSections": ["characters"],
        "_warnings": [
            {
                "code": "CHARACTERS_UNAVAILABLE",
                "message": "Character Identity is disabled (STUDIO_FEATURE_CHARACTER_IDENTITY_V1).",
                "section": "characters",
            }
        ],
        "_evidence": [],
    }


async def list_character_profiles(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    if not feature_flags_mod.feature_flags.character_identity_v1:
        return _feature_disabled_payload()
    if not ctx.project_id:
        raise ValueError("projectId is required")
    items = [p.model_dump() for p in ci.list_profiles(ctx.db, ctx.project_id)]
    return {
        "ok": True,
        "items": items,
        "count": len(items),
        "_summary": f"{len(items)} Character Identity profile(s).",
        "_evidence": [
            {
                "sourceType": "character",
                "sourceId": str(p.get("id")),
                "sourceName": p.get("name"),
                "repository": "character_identity",
            }
            for p in items
            if p.get("id")
        ],
    }


async def inspect_character_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require(ctx)
    character_id = str(args.get("characterId") or "").strip()
    if not character_id:
        raise ValueError("characterId is required")
    profile = ci.get_profile(ctx.db, ctx.project_id, character_id).model_dump()
    coverage = profile.get("coverage") or {}
    missing = coverage.get("missing_roles") or []
    notes = list(coverage.get("guidance") or [])
    if missing:
        notes.append(
            "Do not claim this identity pack is complete. Missing roles: " + ", ".join(missing)
        )
    if not coverage.get("ready_for_generation"):
        notes.append("Profile is not READY_FOR_GENERATION.")
    return {
        "ok": True,
        "profile": profile,
        "guidance": notes,
        "_summary": f"Character Profile '{profile.get('name') or character_id}' (stored; not fabricated).",
        "_evidence": [
            {
                "sourceType": "character",
                "sourceId": character_id,
                "sourceName": profile.get("name"),
                "repository": "character_identity",
            }
        ],
    }


async def inspect_character_coverage(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require(ctx)
    character_id = str(args.get("characterId") or "").strip()
    cov = ci.coverage(ctx.db, ctx.project_id, character_id).model_dump()
    return {"ok": True, "coverage": cov, "guidance": cov.get("guidance") or []}


async def inspect_character_voice(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require(ctx)
    character_id = str(args.get("characterId") or "").strip()
    items = ci.list_voice_profiles(ctx.db, ctx.project_id, character_id)
    for item in items:
        if item.get("source_mode") == "CLONE" and not item.get("consent_record_id"):
            item["warning"] = (
                "A voice reference may be present, but synthetic-use consent is not confirmed. "
                "Cloning cannot begin until that record is completed."
            )
    return {"ok": True, "voiceProfiles": items}


def preview_create_draft_character_profile(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _require(ctx)
    name = str(args.get("name") or "").strip() or "Untitled character"
    return ToolPreview(
        summary=f"Create draft Character Profile “{name}”.",
        lines=[
            "Creates a DRAFT Character Profile (not approved).",
            "Does not generate images or voice.",
            "Does not mutate locked Hitchhiker certification scenes.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_create_draft_character_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require(ctx)
    name = str(args.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    out = ci.create_profile(
        ctx.db,
        ctx.project_id,
        CharacterProfileCreate(
            name=name,
            role=str(args.get("role") or ""),
            description=str(args.get("description") or ""),
        ),
    )
    return {"ok": True, "created": "character_profile", "profile": out.model_dump()}

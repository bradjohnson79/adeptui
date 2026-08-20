"""Approve-side Co-Director registration. No identity embeddings."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


def register_character_canon(db: Session, project_id: str, character_id: str) -> dict[str, Any]:
    """Confirm the approved sheet is resolvable as @Name + pixel context."""
    from ...character_identity.models import CharacterProfileRow
    from ...character_identity.visual_context import resolve_character_visual_context
    from ..entity_resolver import resolve_character

    profile = db.get(CharacterProfileRow, character_id)
    name = str(getattr(profile, "name", "") or "").strip()
    by_name = resolve_character(db, project_id, name) if name else {}
    context = None
    try:
        context = resolve_character_visual_context(db, project_id, character_id)
    except Exception:
        context = None
    asset_id = ""
    if context is not None:
        asset_id = str(getattr(context, "asset_id", None) or "")
    if not asset_id and isinstance(by_name, dict):
        asset_id = str(by_name.get("approved_sheet_asset_id") or by_name.get("approved_casting_asset_id") or "")
    ok = bool(name and by_name and by_name.get("character_id") and asset_id)
    return {
        "ok": ok,
        "characterId": character_id,
        "name": name,
        "atTag": f"@{name}" if name else "",
        "approvedSheetAssetId": asset_id,
        "resolvesByName": bool(by_name and by_name.get("character_id")),
        "embeddings": False,
    }

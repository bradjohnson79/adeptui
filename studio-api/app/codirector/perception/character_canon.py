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
    if isinstance(by_name, dict):
        # Identity pixels are the Front view, never the composed 21:9 sheet.
        asset_id = str(
            by_name.get("visual_reference")
            or by_name.get("approved_casting_asset_id")
            or asset_id
            or by_name.get("approved_sheet_asset_id")
            or ""
        )
    lock_status = "none"
    try:
        from ...character_identity.cc_v2 import load_state

        lock_status = str((load_state(db, character_id).get("visualLock") or {}).get("status") or "none")
    except Exception:
        lock_status = "none"
    # Pre-V2 characters have no lock (`none`) and remain resolvable.
    lock_ok = lock_status in {"ok", "none"}
    ok = bool(name and by_name and by_name.get("character_id") and asset_id and lock_ok)
    return {
        "ok": ok,
        "characterId": character_id,
        "name": name,
        "atTag": f"@{name}" if name else "",
        "approvedSheetAssetId": asset_id,
        "resolvesByName": bool(by_name and by_name.get("character_id")),
        "visualLockOk": lock_ok,
        "embeddings": False,
    }

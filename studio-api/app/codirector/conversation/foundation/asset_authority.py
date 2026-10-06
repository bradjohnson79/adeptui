"""Per-turn visual asset authority.

Precedence (highest wins):
ATTACHED_THIS_TURN > APPROVED/ACTIVE CRS > hero_identity > CURRENT profile
> CANDIDATE/HISTORICAL/ARCHIVED

Current turn outranks old concept art. Never ask canon-arbitration questions.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AssetRank = Literal[
    "ATTACHED_THIS_TURN",
    "APPROVED_ACTIVE_CRS",
    "HERO_IDENTITY",
    "CURRENT_PROFILE",
    "CANDIDATE_HISTORICAL_ARCHIVED",
    "NONE",
]

_RANK_ORDER = {
    "ATTACHED_THIS_TURN": 50,
    "APPROVED_ACTIVE_CRS": 40,
    "HERO_IDENTITY": 30,
    "CURRENT_PROFILE": 20,
    "CANDIDATE_HISTORICAL_ARCHIVED": 10,
    "NONE": 0,
}


class AssetAuthority(BaseModel):
    rank: AssetRank = "NONE"
    asset_id: str = ""
    source: str = ""
    character_id: str = ""
    notes: list[str] = Field(default_factory=list)

    @property
    def outranks_historical(self) -> bool:
        return _RANK_ORDER.get(self.rank, 0) >= _RANK_ORDER["CURRENT_PROFILE"]


def classify_asset_rank(
    *,
    attached_this_turn: bool = False,
    attachment_asset_id: str = "",
    visual_context: Any = None,
    profile_reference_id: str = "",
    candidate_or_historical: bool = False,
) -> AssetAuthority:
    if attached_this_turn and attachment_asset_id:
        return AssetAuthority(
            rank="ATTACHED_THIS_TURN",
            asset_id=attachment_asset_id,
            source="attachment",
            notes=["Current-turn attachment outranks prior concept art."],
        )

    source = str(getattr(visual_context, "source", "") or "")
    asset_id = str(getattr(visual_context, "asset_id", "") or "")
    character_id = str(getattr(visual_context, "character_id", "") or "")
    if asset_id and source in {"crs_sheet", "approved_crs", "crs"}:
        return AssetAuthority(
            rank="APPROVED_ACTIVE_CRS",
            asset_id=asset_id,
            source=source,
            character_id=character_id,
        )
    if asset_id and source in {"hero_identity", "approved_hero"}:
        return AssetAuthority(
            rank="HERO_IDENTITY",
            asset_id=asset_id,
            source=source,
            character_id=character_id,
        )
    if asset_id and source in {"reference_image", "profile", "current_profile"}:
        return AssetAuthority(
            rank="CURRENT_PROFILE",
            asset_id=asset_id,
            source=source,
            character_id=character_id,
        )
    if profile_reference_id:
        return AssetAuthority(
            rank="CURRENT_PROFILE",
            asset_id=profile_reference_id,
            source="profile",
            character_id=character_id,
        )
    if candidate_or_historical:
        return AssetAuthority(
            rank="CANDIDATE_HISTORICAL_ARCHIVED",
            asset_id=asset_id,
            source=source or "historical",
            character_id=character_id,
            notes=["Historical/candidate art does not override the current request."],
        )
    return AssetAuthority(rank="NONE")


def resolve_authoritative_visual(
    db: Any,
    project_id: str,
    character_id: str,
    *,
    attachment_ids: list[str] | None = None,
) -> AssetAuthority:
    """Resolve the visual that should govern this turn. No arbitration questions."""

    attachments = [a for a in (attachment_ids or []) if a]
    if attachments:
        return classify_asset_rank(
            attached_this_turn=True,
            attachment_asset_id=attachments[0],
        )
    visual = None
    if db is not None and project_id and character_id:
        try:
            from app.character_identity.visual_context import resolve_character_visual_context

            visual = resolve_character_visual_context(db, project_id, character_id)
        except Exception:
            visual = None
    return classify_asset_rank(visual_context=visual)

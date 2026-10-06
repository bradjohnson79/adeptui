"""Resolve prompt-facing canonical tags from identity, never from collision aliases."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..creator_scope.identity_tag import (
    canonical_token_only,
    prefix_for,
    prompt_canonical_tag,
    prompt_canonical_token,
)

IDENTITY_REF_TYPES = frozenset(
    {
        "character",
        "prop",
        "vehicle",
        "wardrobe",
        "creature",
        "environment",
        "location",
    }
)
_SMOKE_MARKERS = ("uploadsmoke", "upload_smoke", "upload-smoke")


def is_identity_reference_type(reference_type: str | None) -> bool:
    return str(reference_type or "").strip().lower() in IDENTITY_REF_TYPES


def kind_for_reference_type(reference_type: str | None) -> str:
    ref = str(reference_type or "").strip().lower()
    if ref in {"environment", "location", "place", "scene"}:
        return "environment"
    if ref in {"character", "wardrobe", "creature"}:
        return "character"
    return "prop"


def is_smoke_test_asset(asset: Any | None) -> bool:
    blob = " ".join(
        [
            str(getattr(asset, "filename", "") or ""),
            str(getattr(asset, "tag", "") or ""),
            str(getattr(asset, "path", "") or ""),
        ]
    ).lower()
    return any(marker in blob.replace(" ", "") for marker in _SMOKE_MARKERS)


def load_prop_identity(db: Session, identity_id: str | None):
    token = str(identity_id or "").strip()
    if not token:
        return None
    try:
        from ..spatial_map.ers_persistence import load_prop_entity_anywhere

        return load_prop_entity_anywhere(db, token)
    except Exception:
        return None


def approved_prop_asset_id(prop: Any) -> str:
    from ..prop_creator.readiness import approved_primary_asset_id

    return str(
        getattr(prop, "advanced_sheet_asset_id", "")
        or approved_primary_asset_id(prop)
        or getattr(prop, "library_asset_id", "")
        or ""
    ).strip()


def canonical_tag_for_prop(prop: Any) -> str:
    label = str(getattr(prop, "display_label", "") or "")
    stored = str(getattr(prop, "canonical_tag", "") or "")
    return prompt_canonical_tag("prop", label, stored)


def canonical_tag_for_identity(
    db: Session,
    *,
    identity_id: str | None,
    reference_type: str | None,
    display_name: str = "",
    stored_alias: str = "",
    asset: Any | None = None,
) -> str:
    kind = kind_for_reference_type(reference_type)
    token = str(identity_id or "").strip()
    if token and kind == "prop":
        prop = load_prop_identity(db, token)
        if prop is not None:
            return canonical_tag_for_prop(prop)
    if token and kind == "character":
        try:
            from ..character_identity.models import CharacterProfileRow

            row = db.get(CharacterProfileRow, token)
            if row is not None:
                name = str(getattr(row, "name", "") or display_name)
                return prompt_canonical_tag("character", name, getattr(row, "slug", None))
        except Exception:
            pass
    if token and kind == "environment":
        try:
            from ..environment_reference_sheet.store import load_sheet

            sheet = load_sheet("", token)
            if sheet is None:
                from ..environment_reference_sheet.store import list_visible_sheets

                for item in list_visible_sheets(db, str(getattr(asset, "project_id", "") or "")):
                    if str(getattr(item, "sheetId", "")) == token:
                        sheet = item
                        break
            if sheet is not None:
                name = str(getattr(sheet, "name", "") or display_name)
                stored = str(getattr(sheet, "canonicalTag", "") or "")
                return prompt_canonical_tag("environment", name, stored)
        except Exception:
            pass
    name = display_name or str(getattr(asset, "filename", "") or "").rsplit(".", 1)[0].replace("_", " ")
    stored = stored_alias or str(getattr(asset, "tag", "") or "")
    return prompt_canonical_tag(kind, name, stored)


def enrich_binding_identity(db: Session, data: dict[str, Any]) -> dict[str, Any]:
    if not is_identity_reference_type(str(data.get("reference_type") or "")):
        return data
    asset = None
    asset_id = str(data.get("asset_id") or "").strip()
    if asset_id:
        try:
            from ..db import Asset

            asset = db.get(Asset, asset_id)
        except Exception:
            asset = None
    stored_alias = str(data.get("alias") or "")
    filename = str(getattr(asset, "filename", "") or "").rsplit(".", 1)[0].replace("_", " ")
    identity_id = str(data.get("identity_id") or "").strip()
    display = str(data.get("identity_name") or "").strip()
    if identity_id and kind_for_reference_type(str(data.get("reference_type") or "")) == "prop":
        prop = load_prop_identity(db, identity_id)
        if prop is not None:
            label = str(getattr(prop, "display_label", "") or "").strip()
            if label:
                data["identity_name"] = label
                display = label
    if not display:
        display = stored_alias
    if not display and filename and not any(
        marker in filename.lower() for marker in ("reference", "sheet", "prs")
    ):
        display = filename
    if display and any(marker in display.lower() for marker in ("reference", "sheet", "prs")):
        display = stored_alias if stored_alias and "sheet" not in stored_alias.lower() else ""
    tag = canonical_tag_for_identity(
        db,
        identity_id=str(data.get("identity_id") or "") or None,
        reference_type=str(data.get("reference_type") or ""),
        display_name=display,
        stored_alias=str(data.get("alias") or ""),
        asset=asset,
    )
    if tag:
        data["canonical_tag"] = tag
        data["display_token"] = tag
        data["alias"] = canonical_token_only(tag)
        if display and not data.get("identity_name"):
            data["identity_name"] = display
    return data


def desired_identity_alias(
    db: Session,
    body: dict[str, Any],
    *,
    reference_type: str,
) -> str:
    identity_id = str(body.get("identity_id") or "").strip()
    display = str(body.get("prompt_name") or body.get("alias") or "")
    tag = canonical_tag_for_identity(
        db,
        identity_id=identity_id or None,
        reference_type=reference_type,
        display_name=display,
        stored_alias=str(body.get("alias") or ""),
    )
    token = canonical_token_only(tag) or prompt_canonical_token(display)
    return token

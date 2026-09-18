"""MiniMax H3 Front-form identity helpers (Timeline Ref2V).

FM3 (2026-09-10 Brad GO): when Character Creator Front / hero_identity exists,
Timeline H3 packs that Front into ref_image_N (Front-only transport first).
Plain Front library bytes only — never crop CRS into a fake Front.

prefer_front / h3PreferFront remain the explicit remap levers. Default H3
request path uses front_transport=True (policy h3_front_transport), which packs
Front when available without inventing place/multi-ref companions and without
rewriting Timed Prompt. Opt out with providerOptions.h3FrontTransport=False or
h3CreatorCrsAuthority=True.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...character_identity.service import resolve_approved_reference
from ...db import Asset
from .contracts import TimelineGenerationRequest


def _asset_is_image(db: Session, asset_id: str | None) -> bool:
    aid = str(asset_id or "").strip()
    if not aid:
        return False
    asset = db.get(Asset, aid)
    if asset is None:
        return False
    kind = str(getattr(asset, "kind", "") or "").lower().strip()
    return kind == "image"


def _is_front_still_asset(db: Session, project_id: str, asset_id: str) -> bool:
    aid = str(asset_id or "").strip()
    if not aid:
        return False
    asset = db.get(Asset, aid)
    if asset is None:
        return False
    if project_id and getattr(asset, "project_id", None) not in (None, project_id):
        return False
    from ...scene_references.sheet_tags import classify_asset

    return classify_asset(asset).kind == "front_still"


def is_multi_panel_crs_asset(db: Session, project_id: str, asset_id: str) -> bool:
    """True when the Library asset is a multi-panel Character Reference Sheet."""
    aid = str(asset_id or "").strip()
    if not aid:
        return False
    asset = db.get(Asset, aid)
    if asset is None:
        return False
    if project_id and getattr(asset, "project_id", None) not in (None, project_id):
        return False
    from ...scene_references.sheet_tags import classify_asset

    return classify_asset(asset).kind == "crs"


def resolve_h3_front_character_asset(
    db: Session,
    project_id: str,
    hit: dict[str, Any],
    *,
    bound_assets: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Resolve Character Creator Front / hero_identity when present.

    Returns (asset_id, form) where form is "front" or "".
    Never returns a multi-panel CRS sheet. Used for warnings and for the
    opt-in prefer_front=True remap path — not applied silently by default.
    """
    character_id = str(hit.get("character_id") or "").strip()
    candidates: list[str] = []
    if character_id:
        hero = str(resolve_approved_reference(db, character_id, "hero_identity") or "").strip()
        if hero:
            candidates.append(hero)
        try:
            from ...character_identity.cc_v2 import load_state

            state = load_state(db, character_id)
            front_id = str(
                ((state.get("views") or {}).get("front") or {}).get("assetId") or ""
            ).strip()
            if front_id:
                candidates.append(front_id)
        except Exception:
            pass
        for item in bound_assets or []:
            if not isinstance(item, dict):
                continue
            ident = str(item.get("identityId") or item.get("characterId") or "").strip()
            aid = str(item.get("assetId") or "").strip()
            if not aid:
                continue
            if ident and ident != character_id:
                continue
            if _is_front_still_asset(db, project_id, aid):
                candidates.append(aid)
    for key in (
        "approved_reference_asset_id",
        "visual_reference",
        "approved_casting_asset_id",
    ):
        aid = str(hit.get(key) or "").strip()
        if aid:
            candidates.append(aid)

    seen: set[str] = set()
    for aid in candidates:
        if not aid or aid in seen:
            continue
        seen.add(aid)
        if not _asset_is_image(db, aid):
            continue
        if is_multi_panel_crs_asset(db, project_id, aid):
            continue
        return aid, "front"
    return "", ""


def apply_h3_front_identity_to_r2v_slots(
    db: Session,
    project_id: str,
    slots: list[Any],
    *,
    prefer_front: bool = False,
    front_transport: bool = False,
) -> dict[str, Any]:
    """Annotate / pack H3 character slots for Front vs CRS.

    front_transport=True (FM3 default on H3 request path): when Front exists,
    pack Front assetId into the character slot (plain Front bytes; no CRS crop).
    prefer_front=True: same packing (legacy J10 opt-in name).
    Both False: creator CRS authority — warn only, no swap.
    """
    replaced: list[dict[str, Any]] = []
    crs_only: list[str] = []
    front_available_kept_crs: list[str] = []
    warnings: list[str] = []
    pack_front = bool(prefer_front or front_transport)
    if prefer_front:
        policy = "prefer_front_over_crs"
    elif front_transport:
        policy = "h3_front_transport"
    else:
        policy = "creator_crs_authority"
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        if str(slot.get("role") or "") != "character":
            continue
        asset_id = str(slot.get("assetId") or "").strip()
        identity_id = str(slot.get("identityId") or slot.get("characterId") or "").strip()
        label = str(slot.get("label") or identity_id or asset_id or "Character").strip() or "Character"
        hit = {
            "character_id": identity_id,
            "name": label,
            "approved_reference_asset_id": asset_id,
            "visual_reference": asset_id,
        }
        front_id, form = resolve_h3_front_character_asset(
            db, project_id, hit, bound_assets=None
        )
        is_crs = bool(asset_id and is_multi_panel_crs_asset(db, project_id, asset_id))

        if pack_front and front_id and form == "front":
            if front_id != asset_id:
                slot["replacedCrsAssetId"] = asset_id or None
                slot["assetId"] = front_id
                slot["identityForm"] = "front"
                replaced.append(
                    {
                        "label": label,
                        "identityId": identity_id or None,
                        "fromAssetId": asset_id or None,
                        "toAssetId": front_id,
                        "form": "front",
                    }
                )
            else:
                slot["identityForm"] = "front"
            continue

        # Default / creator authority: never silent-swap the bound tensor.
        if front_id and form == "front" and front_id != asset_id and is_crs:
            slot["identityForm"] = "crs_sheet_kept"
            front_available_kept_crs.append(label)
            warnings.append(
                f"{label}: Character Creator Front is available, but the creator-attached "
                "CRS sheet is kept (no silent Front remap)."
            )
            continue
        if asset_id and not is_crs:
            slot["identityForm"] = (
                "front" if (front_id and front_id == asset_id) else "front_comparable"
            )
            continue
        if is_crs:
            slot["identityForm"] = "crs_sheet_only"
            crs_only.append(label)
            warnings.append(
                f"{label}: only a multi-panel Character Reference Sheet is bound. "
                "MiniMax H3 identity locks best with Character Creator Front "
                "(or a front-comparable single-subject portrait). "
                "CRS sheets alone often fail identity — prefer Front when available."
            )
            continue
        if not asset_id:
            warnings.append(f"{label}: no character identity picture on this H3 slot.")

    return {
        "ok": True,
        "replaced": replaced,
        "crsOnly": crs_only,
        "frontAvailableKeptCrs": front_available_kept_crs,
        "warnings": warnings,
        "policy": policy,
    }


def apply_h3_front_identity_to_request(
    db: Session,
    request: TimelineGenerationRequest,
    *,
    prefer_front: bool = False,
    front_transport: bool | None = None,
) -> dict[str, Any]:
    """Apply H3 Front transport packing (FM3 default) or annotation-only to r2v slots."""
    from .r2v import H3_MECHANISM, mechanism_for_generator

    opts = request.providerOptions or {}
    product = str(
        (opts.get("originalGeneratorId") if isinstance(opts, dict) else None)
        or (opts.get("selectedGenerator") if isinstance(opts, dict) else None)
        or request.generatorId
        or ""
    ).strip()
    mech = mechanism_for_generator(product)
    if mech != H3_MECHANISM and not product.startswith("minimax-h3"):
        return {"ok": True, "skipped": True, "reason": "not_h3"}
    # FM3: Front transport ON by default for H3. Opt-out via h3FrontTransport=False
    # or h3CreatorCrsAuthority=True. Legacy opt-in h3PreferFront still packs Front.
    if front_transport is None:
        front_transport = True
    if isinstance(opts, dict):
        flag = opts.get("h3PreferFront")
        if flag is None:
            flag = opts.get("preferFrontIdentity")
        if flag is True or str(flag).strip().lower() in {"1", "true", "yes"}:
            prefer_front = True
        if flag is False or str(flag).strip().lower() in {"0", "false", "no"}:
            # Explicit false on prefer flag alone does not force CRS authority;
            # use h3FrontTransport / h3CreatorCrsAuthority for opt-out.
            pass
        ft = opts.get("h3FrontTransport")
        if ft is None:
            ft = opts.get("frontTransport")
        if ft is False or str(ft).strip().lower() in {"0", "false", "no"}:
            front_transport = False
        if ft is True or str(ft).strip().lower() in {"1", "true", "yes"}:
            front_transport = True
        crs_auth = opts.get("h3CreatorCrsAuthority")
        if crs_auth is True or str(crs_auth).strip().lower() in {"1", "true", "yes"}:
            front_transport = False
            prefer_front = False
    opts = dict(opts or {})
    r2v = dict(opts.get("r2v") or {})
    slots = [dict(item) if isinstance(item, dict) else item for item in (r2v.get("slots") or [])]
    result = apply_h3_front_identity_to_r2v_slots(
        db,
        str(request.projectId or ""),
        slots,
        prefer_front=prefer_front,
        front_transport=bool(front_transport),
    )
    r2v["slots"] = slots
    r2v["h3FrontIdentity"] = {
        "replaced": result.get("replaced") or [],
        "crsOnly": result.get("crsOnly") or [],
        "frontAvailableKeptCrs": result.get("frontAvailableKeptCrs") or [],
        "warnings": result.get("warnings") or [],
        "policy": result.get("policy") or "h3_front_transport",
    }
    opts["r2v"] = r2v
    # Surface warnings on the request for UI / preflight report.
    existing = list(opts.get("warnings") or [])
    for msg in result.get("warnings") or []:
        if msg not in existing:
            existing.append(msg)
    if existing:
        opts["warnings"] = existing
    request.providerOptions = opts
    return result
